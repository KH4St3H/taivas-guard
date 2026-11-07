"""One sync pass: discover issues, fetch the missing ones, announce each in the outbox."""
import logging
import threading
from datetime import date

import httpx
from sqlalchemy import func, select

from .. import events
from ..config import Settings, get_settings
from ..db import session_scope, utcnow
from ..models import Artifact, SyncRun
from .fetch import Stored, download
from .sources import DISCOVERERS, IssueRef

log = logging.getLogger(__name__)
_running = threading.Lock()  # one pass at a time per process; the unique key guards the rest


def record_artifact(
    domain: str, issue_no: int, stored: Stored, source_url: str, published_on: date | None = None
) -> tuple[Artifact, bool]:
    """Saves the artifact and its event in one commit. Returns (row, is_new)."""
    with session_scope() as s:
        row = s.scalars(
            select(Artifact).where(
                Artifact.domain == domain, Artifact.issue_no == issue_no, Artifact.sha256 == stored.sha256
            )
        ).first()
        if row is not None:
            row.etag = stored.etag or row.etag
            return row, False
        row = Artifact(
            domain=domain,
            issue_no=issue_no,
            published_on=published_on,
            source_url=source_url,
            sha256=stored.sha256,
            size_bytes=stored.size_bytes,
            etag=stored.etag,
            mdb_path=str(stored.mdb_path),
        )
        s.add(row)
        s.flush()
        events.publish(s, events.ISSUE_FETCHED, {"artifact_id": row.id})
        return row, True


def _needs_fetch(client: httpx.Client, ref: IssueRef, known: dict[int, str | None], latest: int | None) -> bool:
    if ref.issue_no not in known:
        return True
    # ITU can republish: check the newest issue's ETag so a correction is picked up as a new revision
    if ref.issue_no != latest or not known[ref.issue_no]:
        return False
    head = client.head(ref.url)
    return head.status_code == 200 and head.headers.get("etag") != known[ref.issue_no]


def _sync_domain(client: httpx.Client, domain: str, settings: Settings, run: dict) -> None:
    refs = sorted(DISCOVERERS[domain](client, settings), key=lambda r: r.issue_no)
    run["discovered"] += len(refs)
    with session_scope() as s:
        rows = s.execute(
            select(Artifact.issue_no, Artifact.etag).where(Artifact.domain == domain).order_by(Artifact.id)
        ).all()
    known = {n: etag for n, etag in rows}  # the newest revision of an issue wins
    latest = max((r.issue_no for r in refs), default=None)
    for ref in refs:  # oldest first, so issue-to-issue diffs run in publication order
        try:
            if not _needs_fetch(client, ref, known, latest):
                continue
            stored = download(client, ref.url, domain, ref.issue_no, settings)
            if stored is None:
                log.info("%s issue %s is not available yet", domain, ref.issue_no)
                continue
            _, is_new = record_artifact(domain, ref.issue_no, stored, ref.url, ref.published_on)
            if is_new:
                run["fetched"] += 1
                log.info("fetched %s issue %s (%s)", domain, ref.issue_no, stored.sha256[:12])
        except Exception as exc:
            log.exception("could not fetch %s issue %s", domain, ref.issue_no)
            run["errors"].append(f"{domain} {ref.issue_no}: {type(exc).__name__}: {exc}")


def run_sync(trigger: str = "schedule", client: httpx.Client | None = None) -> int | None:
    """Returns the run id, or None if another pass is already running in this process."""
    if not _running.acquire(blocking=False):
        return None
    settings = get_settings()
    own_client = client is None
    client = client or httpx.Client(
        timeout=settings.http_timeout_s, follow_redirects=True, headers={"User-Agent": settings.user_agent}
    )
    try:
        with session_scope() as s:
            row = SyncRun(trigger=trigger)
            s.add(row)
            s.flush()
            run_id = row.id
        run = {"discovered": 0, "fetched": 0, "errors": []}
        failed_domains = 0
        for domain in DISCOVERERS:
            try:  # one source being down must not stop the other
                _sync_domain(client, domain, settings, run)
            except Exception as exc:
                failed_domains += 1
                log.exception("sync failed for %s", domain)
                run["errors"].append(f"{domain}: {type(exc).__name__}: {exc}")
        status = "failed" if failed_domains == len(DISCOVERERS) else "partial" if run["errors"] else "ok"
        with session_scope() as s:
            row = s.get_one(SyncRun, run_id)
            row.status, row.finished_at = status, utcnow()
            row.discovered, row.fetched, row.errors = run["discovered"], run["fetched"], run["errors"]
            if run["errors"]:
                events.publish(
                    s,
                    events.OPS_ALERT,
                    {  # keyed by day, so a long ITU outage sends one mail a day rather than one per poll
                        "dedupe_key": f"sync-failed:{utcnow().date()}",
                        "subject": f"IFIC Guard: sync {status}",
                        "body": "Sync run {} finished as {}:\n\n{}".format(run_id, status, "\n".join(run["errors"])),
                    },
                )
        return run_id
    finally:
        _running.release()
        if own_client:
            client.close()


def scheduled_pass() -> float:
    """Runs one scheduled sync. Returns how long to wait: shorter if anything failed."""
    settings = get_settings()
    run_id = None
    try:
        run_id = run_sync("schedule")
    except Exception:  # e.g. database briefly unavailable
        log.exception("scheduled sync crashed")
        return settings.retry_interval_s
    if run_id is None:  # another pass, such as a manual one, is running
        return settings.retry_interval_s
    with session_scope() as s:
        status = s.get_one(SyncRun, run_id).status
    return settings.poll_interval_s if status == "ok" else settings.retry_interval_s


def freshness() -> dict[str, dict]:
    """The newest issue per domain, flagged stale if overdue. Stale means sync may be broken."""
    settings = get_settings()
    out = {}
    with session_scope() as s:
        for domain in DISCOVERERS:
            issue, published = s.execute(
                select(func.max(Artifact.issue_no), func.max(Artifact.published_on)).where(Artifact.domain == domain)
            ).one()
            age = (date.today() - published).days if published else None
            out[domain] = {
                "latest_issue": issue,
                "published_on": published,
                "age_days": age,
                "stale": issue is None or age is None or age > settings.stale_after_days,
            }
    return out
