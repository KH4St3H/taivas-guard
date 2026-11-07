"""What the pfd rule found at each special-interest station (ticket 19).

The pfd rule writes these records and both it and the station rule read them, so one calculation
backs both kinds of case. A status always says what kind of evidence it is:

    exceeds         calculated at the station's coordinates, above the limit
    exceeds_flagged the same, but an input or the station's location is flagged, so it can't rank as one
    within_3db      calculated at the station, up to 3 dB below the limit
    bound_above     only the filing's non-GSO upper bound is above or near the limit. Never a value at a station
    no_calculation  the band overlaps, but no limit or input allows a calculation
    below           calculated at the station, more than 3 dB below the limit
    bound_below     the filing's upper bound is more than 3 dB below the limit
    not_visible     the satellite is always below this station's horizon

Severity from a status is our choice, not Traficom's (README, "Severity of station cases").
"""
from collections import Counter
from typing import Any

from .stations import OUTSIDE_FINLAND, SIDE_RX, SITE_NOT_RECEIVER, ProtectedBand, Station

STATUS_ORDER = {
    "not_visible": 0, "bound_below": 1, "below": 2, "no_calculation": 3, "bound_above": 4, "within_3db": 5,
    "exceeds_flagged": 6, "exceeds": 7,
}
CALCULATED = {"exceeds", "exceeds_flagged", "within_3db", "below"}
MEDIUM = {"exceeds_flagged", "within_3db", "bound_above", "no_calculation"}
SEVERITY_NOTE = "This severity is the project's choice, not Traficom's."


def severity_of(status: str) -> str:
    return "high" if status == "exceeds" else "medium" if status in MEDIUM else "low"


def record_for(station: Station, bands: tuple[ProtectedBand, ...], status: str, **evidence: Any) -> dict[str, Any]:
    """One station's evidence. A location flag stops an exceedance ranking as one, since the sheet is synthetic."""
    flagged_location = OUTSIDE_FINLAND in station.quality_flags
    if status == "exceeds" and flagged_location:
        status = "exceeds_flagged"
    record = {
        "station_id": station.key,
        "licence_class": station.licence_class,
        "lat": station.lat_deg,
        "lon": station.lon_deg,
        "matched_bands": [{"side": b.side, "low_mhz": b.low_mhz, "high_mhz": b.high_mhz} for b in bands],
        "status": status,
        **evidence,
    }
    if flagged_location:
        record["location_flagged"] = True
    if not any(b.side == SIDE_RX for b in bands):
        record["field_location"] = SITE_NOT_RECEIVER
    return record


def rank(record: dict[str, Any]) -> tuple[int, float]:
    margin = record.get("margin_db")
    return STATUS_ORDER[record["status"]], -1000.0 if margin is None else margin


def worst(records: list[dict[str, Any]]) -> dict[str, Any]:
    return max(records, key=lambda r: (*rank(r), r["station_id"]))


def ordered(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=lambda r: (-rank(r)[0], -rank(r)[1], r["station_id"]))


def status_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(r["status"] for r in records).items()))


class StationEvidence:
    """The worst record per station, by case and by the frequency range of a notice."""

    def __init__(self) -> None:
        self.by_range: dict[tuple[int, float, float, str], dict[str, Any]] = {}
        self.by_case: dict[tuple[int, str], dict[str, dict[str, Any]]] = {}

    def add(self, family_id: int, rule_id: str, ntc_id: int, low: float, high: float, record: dict[str, Any]) -> None:
        station = record["station_id"]
        for store, key in ((self.by_range, (ntc_id, low, high, station)), (self.by_case.setdefault((family_id, rule_id), {}), station)):
            if key not in store or rank(record) > rank(store[key]):
                store[key] = record

    def for_case(self, family_id: int, rule_id: str) -> list[dict[str, Any]]:
        return ordered(list(self.by_case.get((family_id, rule_id), {}).values()))

    def for_range(self, ntc_id: int, low: float, high: float, station_id: str) -> dict[str, Any] | None:
        return self.by_range.get((ntc_id, low, high, station_id))


# A case keeps the worst stations and counts, not every station: with the full national register a case
# can overlap millions, and the case is stored, hashed and sent whole. GET /cases/{id}/stations
# recomputes the full list on request. None keeps everything (that recomputation uses it).
STATION_SAMPLE = 100
BAND_ID_SAMPLE = 20


def capped(items: list[Any], limit: int | None) -> list[Any]:
    return items if limit is None else items[:limit]


def station_summary(records: list[dict[str, Any]], limit: int | None = STATION_SAMPLE) -> dict[str, Any]:
    """Counts over every record, and the worst `limit` of them. `records` must already be ordered worst first."""
    linked = [r for r in records if r["status"] != "not_visible"]
    not_visible = sorted(r["station_id"] for r in records if r["status"] == "not_visible")
    shown = capped(linked, limit)
    return {
        "station_count": len(linked),
        "station_ids": sorted(r["station_id"] for r in shown),
        "stations_overlapping": shown,
        "stations_listed": len(shown),
        "station_status_counts": status_counts(records),
        "stations_not_visible": capped(not_visible, limit),
        "stations_not_visible_count": len(not_visible),
        "special_interest": bool(linked),
    }
