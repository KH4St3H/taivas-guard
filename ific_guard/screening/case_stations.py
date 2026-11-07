"""A case's complete station list, recomputed on request.

A case keeps only the worst stations and counts (`station_links.station_summary`). With the full national
register a case can overlap millions of stations, which is too much to store, hash and send with every
case. The full list comes from rerunning the rules for the case's one family, on the issue file that last
changed the case, with no cap. It is held in memory for a few cases so paging through it is quick.
"""
import hashlib
import threading
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import select

from ..config import get_settings
from ..db import session_scope
from ..models import Artifact, Case, CaseOccurrence
from .issue_cache import stored_issue
from .m4 import load_m4_rows
from .rule_pfd import PfdRule
from .rule_stations import StationOverlapRule
from .stations import STATIONS_PATH, load_stations_cached

STATION_RULE = "station-rx-overlap"
CACHED_CASES = 4
_lock = threading.Lock()  # one recomputation at a time: each can hold a whole issue and register in memory


class NoStationList(Exception):
    """The case has no station list, or what it needs is gone. The message is for the reviewer."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class StationList:
    records: tuple[dict[str, Any], ...]  # every linked station, worst first
    not_visible: int
    issue_no: int
    dataset: dict[str, Any]
    dataset_changed: bool  # the register differs from the one the case was screened with


def has_station_list(rule_id: str) -> bool:
    return rule_id == STATION_RULE or rule_id.startswith("pfd-")


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _target(case_id: int) -> tuple[tuple[int, str, int, str, int, str, str | None], int]:
    with session_scope() as s:
        case = s.get(Case, case_id)
        if case is None:
            raise NoStationList(f"No case {case_id}.", 404)
        if not has_station_list(case.rule_id):
            raise NoStationList("This case has no station list.", 404)
        occurrences = list(s.scalars(select(CaseOccurrence).where(CaseOccurrence.case_id == case_id)))
        occurrence = next((o for o in occurrences if o.artifact_id == case.changed_artifact_id), None)
        if occurrence is None and occurrences:
            occurrence = max(occurrences, key=lambda o: o.artifact_id)
        if occurrence is None:
            raise NoStationList("No screened issue holds this case any more, so its stations can't be listed.", 409)
        artifact = s.get(Artifact, occurrence.artifact_id)
        if artifact is None or artifact.domain != "space":
            raise NoStationList("The issue this case came from is no longer stored.", 409)
        dataset = (case.details or {}).get("station_dataset") or {}
        return (case.id, case.material_hash, artifact.id, artifact.mdb_path, artifact.issue_no, case.rule_id,
                dataset.get("sha256")), int(occurrence.hit["family_id"])


@lru_cache(maxsize=CACHED_CASES)
def _compute(case_id: int, material_hash: str, artifact_id: int, mdb_path: str, issue_no: int, rule_id: str,
             screened_sha: str | None, family_id: int, register_sha: str) -> StationList:
    settings = get_settings()
    try:
        issue = stored_issue(artifact_id, mdb_path)
    except FileNotFoundError:
        raise NoStationList(f"The file for IFIC {issue_no} is no longer stored, so the stations can't be recomputed.", 409) from None
    stations = load_stations_cached(STATIONS_PATH)
    pfd = PfdRule(settings, stations, station_limit=None, families={family_id})
    if rule_id == STATION_RULE:
        dataset = {"file": STATIONS_PATH.name, "sha256": register_sha, "records": len(stations)}
        rule = StationOverlapRule(settings, stations, dataset, pfd, load_m4_rows(settings.m4_filter_path), station_limit=None, families={family_id})
        hits = list(rule.run(issue))
    else:
        hits = [h for h in pfd.run(issue) if h.rule_id == rule_id]
    details = hits[0].details if hits else {}
    return StationList(
        records=tuple(details.get("stations_overlapping", [])),
        not_visible=details.get("stations_not_visible_count", len(details.get("stations_not_visible", []))),
        issue_no=issue_no,
        dataset={"file": STATIONS_PATH.name, "sha256": register_sha, "records": len(stations)},
        dataset_changed=screened_sha is not None and screened_sha != register_sha,
    )


def station_list(case_id: int) -> StationList:
    key, family_id = _target(case_id)
    with _lock:
        return _compute(*key, family_id, _digest(STATIONS_PATH))


def matching(rows: tuple[dict[str, Any], ...], status: str | None, licence: str | None) -> Iterator[dict[str, Any]]:
    for r in rows:
        if status and r["status"] != status:
            continue
        if licence and (r.get("licence_class") or "no class") != licence:
            continue
        yield r


def counts(rows: tuple[dict[str, Any], ...]) -> dict[str, dict[str, int]]:
    return {
        "status": dict(Counter(r["status"] for r in rows).most_common()),
        "licence": dict(Counter(r.get("licence_class") or "no class" for r in rows).most_common()),
    }


CSV_COLUMNS = ("station_id", "licence_class", "status", "margin_db", "value_db", "limit_db", "angle_deg", "distance_km",
               "lat", "lon", "sides", "mask_id", "ntc_id", "location_flagged", "field_location", "reason")


def csv_row(r: dict[str, Any]) -> list[Any]:
    sides = "+".join(sorted({b["side"] for b in r.get("matched_bands", [])}))
    return [sides if c == "sides" else r.get(c, "") if r.get(c) is not None else "" for c in CSV_COLUMNS]
