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

from ..config import get_settings
from .issue_cache import CaseSource, Unavailable, case_source, load_issue
from .m4 import load_m4_rows
from .rule_pfd import PfdRule
from .rule_stations import StationOverlapRule
from .stations import STATIONS_PATH, load_stations_cached

STATION_RULE = "station-rx-overlap"
CACHED_CASES = 4
_lock = threading.Lock()  # one recomputation at a time: each can hold a whole issue and register in memory


NoStationList = Unavailable  # kept for the app's import


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


@lru_cache(maxsize=CACHED_CASES)
def _compute(source: CaseSource, register_sha: str) -> StationList:
    settings = get_settings()
    issue = load_issue(source)
    family_id, rule_id, issue_no = source.family_id, source.rule_id, source.issue_no
    screened_sha = (source.details.get("station_dataset") or {}).get("sha256")
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
    source = case_source(case_id, lambda c: has_station_list(c.rule_id), "This case has no station list.")
    with _lock:
        return _compute(source, _digest(STATIONS_PATH))


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
