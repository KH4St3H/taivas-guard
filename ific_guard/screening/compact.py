"""Rewrites cases stored before the station-list cap into the shape the rules write now (ticket 31).

Screening an issue again would rewrite them anyway, but a case whose stored content changes goes back to
pending review. A change of storage shape isn't a change of content, so this applies the same summary the
rules now apply and recomputes the material hash. A case whose content really differs still changes on
the next screening, as it should.
"""
import json
from collections.abc import Callable
from typing import Any

from sqlalchemy import select

from ..db import session_scope
from ..models import Case, CaseOccurrence
from .engine import _digest
from .station_links import BAND_ID_SAMPLE, STATION_SAMPLE

TERRESTRIAL_ID_SAMPLE = 100  # rule_field_strength.STATION_SAMPLE


def compact_space(details: dict[str, Any]) -> dict[str, Any] | None:
    """The station and pfd cases' new shape, or None when there is nothing to change."""
    if "stations_overlapping" not in details or "station_count" in details:
        return None
    d = dict(details)
    linked = list(d["stations_overlapping"])  # stored worst first, as `ordered` leaves them
    not_visible = list(d.get("stations_not_visible", []))
    shown = linked[:STATION_SAMPLE]
    d.update(
        station_count=len(linked),
        station_ids=sorted(r["station_id"] for r in shown),
        stations_overlapping=shown,
        stations_listed=len(shown),
        stations_not_visible=not_visible[:STATION_SAMPLE],
        stations_not_visible_count=len(not_visible),
    )
    if isinstance(d.get("matched_on"), dict):
        d["matched_on"] = {side: len(v) if isinstance(v, list) else v for side, v in d["matched_on"].items()}
    if isinstance(d.get("station_band_flags"), dict):
        d["station_band_flags"] = {flag: len(v) if isinstance(v, list) else v for flag, v in d["station_band_flags"].items()}
    if isinstance(d.get("bands"), list):
        d["bands"] = [_compact_band(b) for b in d["bands"]]
    return d


def _compact_band(band: dict[str, Any]) -> dict[str, Any]:
    if "station_ids" not in band or "station_count" in band:
        return band
    ids = list(band["station_ids"])
    return {**band, "station_count": len(ids), "station_ids": ids[:BAND_ID_SAMPLE]}


def compact_terrestrial(details: dict[str, Any]) -> dict[str, Any] | None:
    """Terrestrial cases kept five full records already; only the id list was unbounded.

    The rule now keeps the ids of its first 100 stations in its own order. That order isn't stored, so a case
    with more than 100 is left alone and will change on the next screening.
    """
    ids = details.get("station_ids")
    if not isinstance(ids, list) or "station_count" in details or len(ids) > TERRESTRIAL_ID_SAMPLE:
        return None
    return {**details, "station_count": len(ids)}


def _compactor(domain: str) -> Callable[[dict[str, Any]], dict[str, Any] | None]:
    return compact_terrestrial if domain == "terrestrial" else compact_space


def _size(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, default=str))


def compact_stations(dry_run: bool = False) -> dict[str, int]:
    """Compacts every case and occurrence that needs it. Returns counts and stored bytes before and after."""
    out = {"cases": 0, "occurrences": 0, "skipped": 0, "bytes_before": 0, "bytes_after": 0}
    with session_scope() as s:
        cases = {c.id: c for c in s.scalars(select(Case))}
        for case in cases.values():
            new = _compactor(case.domain)(case.details or {})
            if new is None:
                if case.details and "station_ids" in case.details and "station_count" not in case.details:
                    out["skipped"] += 1
                continue
            out["cases"] += 1
            out["bytes_before"] += _size(case.details)
            out["bytes_after"] += _size(new)
            if not dry_run:
                case.details = new
                case.material_hash = _digest(case.severity, new)  # what the engine computes for this content
        for occurrence in s.scalars(select(CaseOccurrence)):
            hit = occurrence.hit or {}
            case = cases.get(occurrence.case_id)
            new = _compactor(case.domain if case else "space")(hit.get("details") or {})
            if new is None:
                continue
            out["occurrences"] += 1
            out["bytes_before"] += _size(hit.get("details"))
            out["bytes_after"] += _size(new)
            if not dry_run:
                occurrence.hit = {**hit, "details": new}
        if dry_run:
            s.rollback()  # nothing was assigned, but make sure nothing is written
    return out
