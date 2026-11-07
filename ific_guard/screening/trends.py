"""Trends across stored issues: descriptive counts per issue, and plain flags where a count jumps.

The brief asks for "trends and planned usage of new satellites systems" (guiding question) and for "a small
number of trends or anomalies in neighboring countries administrations' notices" (terrestrial side quest).
Counts are descriptive, from the issue files only, and make no predictions. Each issue's counts are computed
once, when it is screened (or on the first request for an issue screened before this existed), and stored.
"""
import logging
import threading
from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from sqlalchemy import select

from ..config import get_settings
from ..db import session_scope, utcnow
from ..models import Artifact, IssueSummary
from ..sync.sources import SPACE, TERRESTRIAL
from .rules import visible_from_finland
from .space import SATELLITE_NOTICE_TYPES, MdbReader, SpaceIssue

log = logging.getLogger(__name__)
SUMMARY_VERSION = 2  # 2: a network published as two notices is listed once
JUMP_FACTOR = 2.0  # a count at least twice its average over the earlier issues shown...
JUMP_MIN = 5  # ...and at least this large, so a change from 1 to 2 isn't flagged
TOP_SYSTEMS = 8
_lock = threading.Lock()

# IEEE radar band letters, which spectrum engineers read at a glance. Upper edges in MHz.
BANDS = (
    ("below 1 GHz", 1_000), ("L, 1-2 GHz", 2_000), ("S, 2-4 GHz", 4_000), ("C, 4-8 GHz", 8_000),
    ("X, 8-12 GHz", 12_000), ("Ku, 12-18 GHz", 18_000), ("K, 18-27 GHz", 27_000), ("Ka, 27-40 GHz", 40_000),
    ("V, 40-75 GHz", 75_000), ("W and above, 75 GHz+", float("inf")),
)
ORBITS = {"G": "GSO", "N": "Non-GSO"}
REASONS = {"A": "API/A (9.1/IA)", "C": "CR/C (9.6)"}


def _band(frequency_mhz: float) -> str:
    return next(name for name, upper in BANDS if frequency_mhz < upper)


def summarise_space(issue: SpaceIssue) -> dict[str, Any]:
    """Filings in screening scope (API/A and CR/C, satellites), counted once per filing."""
    settings = get_settings()
    satellites = [n for n in issue.notices.values() if n.ntc_type in SATELLITE_NOTICE_TYPES]
    by_adm, by_orbit, by_reason, by_band, visible = Counter(), Counter(), Counter(), Counter(), 0
    systems = []
    for n in satellites:
        by_adm[n.adm or "unknown"] += 1
        by_orbit[ORBITS.get(n.ntc_type, n.ntc_type)] += 1
        by_reason[REASONS.get(n.reason or "", n.reason or "unknown")] += 1
        for band in {_band(float(a["freq_min"])) for a in n.assignments if a.get("emi_rcp") == "E" and a.get("freq_min") is not None}:
            by_band[band] += 1
        visible += visible_from_finland(n, settings)[0]
        if n.ntc_type == "N":
            count = sum(int(r.get("nbr_sat_pl") or 0) for r in issue.orbits.get(n.ntc_id, []))
            if count:
                systems.append({"ntc_id": n.ntc_id, "network": n.name, "adm": n.adm, "satellites": count,
                                "reason": REASONS.get(n.reason or "", n.reason)})
    # ITU often publishes one network as two notices (12xxx and 32xxx), so the list keeps each network once.
    largest: dict[tuple[str | None, str | None], dict[str, Any]] = {}
    for system in systems:
        key = (system["network"], system["adm"])
        if key not in largest or system["satellites"] > largest[key]["satellites"]:
            largest[key] = system
    systems = sorted(largest.values(), key=lambda x: (-x["satellites"], x["network"] or ""))
    return {
        "filings": len(satellites),
        "visible_from_finland": visible,
        "by_adm": dict(by_adm),
        "by_orbit": dict(by_orbit),
        "by_reason": dict(by_reason),
        "by_band": dict(by_band),
        "largest_ngso": systems[:TOP_SYSTEMS],
    }


def summarise_terrestrial(issue) -> dict[str, Any]:
    """The neighbour trend module's counts for one issue, so the page and the report agree."""
    from ..terrestrial.trends import analyse_neighbour_trends

    report = analyse_neighbour_trends([issue])
    no = issue.issue_no
    by_key = {o.key: o.counts for o in report.observations}
    pick = lambda counts: {k: v.get(no, 0) for k, v in counts.items()}  # noqa: E731
    return {
        "administrations": list(report.administrations),
        "by_adm": pick(report.activity),
        "screened_by_adm": pick(report.screened_activity),
        "screened_by_band": pick(by_key.get("frequency-band", {})),
        "screened_by_class": pick(by_key.get("station-class", {})),
        "screened_by_bandwidth": pick(by_key.get("bandwidth", {})),
        "assumptions": list(report.assumptions),
    }


def summarise(domain: str, issue) -> dict[str, Any]:
    return summarise_space(issue) if domain == SPACE else summarise_terrestrial(issue)


def store(artifact_id: int, domain: str, issue_no: int, summary: dict[str, Any]) -> None:
    with session_scope() as s:
        row = s.get(IssueSummary, artifact_id) or IssueSummary(artifact_id=artifact_id)
        row.domain, row.issue_no, row.version, row.summary, row.computed_at = domain, issue_no, SUMMARY_VERSION, summary, utcnow()
        s.add(row)


def _load(domain: str, mdb_path: str, issue_no: int):
    if domain == SPACE:
        return SpaceIssue(MdbReader(mdb_path))
    from ..terrestrial.adapter import TerrestrialIssue

    return TerrestrialIssue(MdbReader(mdb_path), expected_issue=issue_no)


def _latest_artifacts(domain: str, last: int) -> list[tuple[int, int, str]]:
    """(artifact id, issue, path) for the newest revision of each of the last `last` issues."""
    with session_scope() as s:
        rows = s.execute(select(Artifact.id, Artifact.issue_no, Artifact.mdb_path)
                         .where(Artifact.domain == domain, Artifact.screen_status == "done")
                         .order_by(Artifact.issue_no.desc(), Artifact.id.desc())).all()
    newest: dict[int, tuple[int, int, str]] = {}
    for artifact_id, issue_no, path in rows:
        newest.setdefault(issue_no, (artifact_id, issue_no, path))
    return sorted(newest.values(), key=lambda r: r[1])[-last:]


def _summaries(domain: str, last: int) -> tuple[dict[int, dict[str, Any]], list[str]]:
    """Stored summaries, computing any that are missing or out of date. Returns issue -> summary, and problems."""
    wanted = _latest_artifacts(domain, last)
    with session_scope() as s:
        have = {r.artifact_id: r.summary for r in s.scalars(select(IssueSummary).where(
            IssueSummary.artifact_id.in_([a for a, _, _ in wanted]), IssueSummary.version == SUMMARY_VERSION))}
    out, problems = {}, []
    for artifact_id, issue_no, path in wanted:
        if artifact_id not in have:
            try:
                have[artifact_id] = summarise(domain, _load(domain, path, issue_no))
                store(artifact_id, domain, issue_no, have[artifact_id])
            except Exception as exc:  # one unreadable issue shouldn't hide the others
                log.warning("trend summary for %s %s failed: %s", domain, issue_no, exc)
                problems.append(f"IFIC {issue_no}: {exc}")
                continue
        out[issue_no] = have[artifact_id]
    return out, problems


def jumps(series: dict[str, dict[int, int]], issues: list[int]) -> list[dict[str, Any]]:
    """Where the latest issue's count is at least JUMP_FACTOR times its earlier average and at least JUMP_MIN."""
    if len(issues) < 2:
        return []
    latest, earlier = issues[-1], issues[:-1]
    flags = []
    for name, counts in series.items():
        now = counts.get(latest, 0)
        before = mean(counts.get(i, 0) for i in earlier)
        if now >= JUMP_MIN and now >= JUMP_FACTOR * before:
            flags.append({"name": name, "issue": latest, "count": now, "earlier_average": round(before, 1)})
    return sorted(flags, key=lambda f: -f["count"])


def _series(summaries: dict[int, dict[str, Any]], key: str) -> dict[str, dict[int, int]]:
    out: dict[str, dict[int, int]] = defaultdict(dict)
    for issue_no, summary in summaries.items():
        for name, n in summary.get(key, {}).items():
            out[name][issue_no] = n
    return dict(out)


def trends(domain: str, last: int = 10) -> dict[str, Any]:
    with _lock:
        summaries, problems = _summaries(domain, last)
    issues = sorted(summaries)
    keys = (("by_adm", "by_orbit", "by_reason", "by_band") if domain == SPACE
            else ("by_adm", "screened_by_adm", "screened_by_band", "screened_by_class", "screened_by_bandwidth"))
    series = {key: _series(summaries, key) for key in keys}
    out: dict[str, Any] = {
        "domain": domain,
        "issues": issues,
        "series": series,
        "flags": {key: jumps(series[key], issues) for key in keys},
        "rule": f"A count is flagged when the latest issue's is at least {JUMP_FACTOR:g} times its average over the earlier "
                f"issues shown, and at least {JUMP_MIN}. This is a plain rule for attention, not a prediction.",
        "problems": problems,
    }
    if domain == SPACE:
        out["totals"] = {i: {"filings": summaries[i]["filings"], "visible_from_finland": summaries[i]["visible_from_finland"]} for i in issues}
        out["largest_ngso"] = {i: summaries[i]["largest_ngso"] for i in issues}
        out["assumptions"] = [
            "Counts are notices in screening scope: API/A and CR/C satellite notices in each issue. ITU often publishes one "
            "network as two notices, so a network can count twice; the comparison across issues is like for like.",
            "Only issues stored in this installation are shown, so consecutive columns can skip issue numbers.",
            "A filing counts in a band when any of its space-to-Earth assignments starts in it.",
            "Satellite numbers are the notified orbital planes' nbr_sat_pl summed per filing: what is planned, not launched.",
        ]
    else:
        out["assumptions"] = summaries[issues[-1]]["assumptions"] if issues else []
    return out
