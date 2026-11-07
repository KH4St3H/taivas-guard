"""A visible satellite transmits on a special-interest station's RX or TX frequency (tickets 05, 16, 19).

With the pfd rule's evidence, each station gets the calculated result at its own coordinates, and
the case's severity follows the strongest evidence (see `station_links`).
"""
import hashlib
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..config import Settings
from ..engines.pfd import gso_geometry
from .m4 import M4Row, finnish_notes, load_m4_rows, load_rr_footnotes_finland
from .rules import Hit, _deadline, _families, visible_from_finland
from .scoring import ScoringWeights, score_finding
from .space import SATELLITE_NOTICE_TYPES, SpaceIssue, SpaceNotice
from .station_links import BAND_ID_SAMPLE, CALCULATED, SEVERITY_NOTE, STATION_SAMPLE, capped, ordered, record_for, severity_of, station_summary, worst
from .stations import BW_MISMATCH, EARTH_STATIONS_PATH, NO_CHANNEL_BW, SIDE_TX, STATIONS_PATH, ProtectedBand, Station, StationIndex, load_stations

if TYPE_CHECKING:
    from .rule_pfd import PfdRule

NO_CLASS = "no class"  # the sheet leaves the class blank; what that means is ticket 02 question 10
BAND_FLAGS = (NO_CHANNEL_BW, BW_MISMATCH)  # the quality flags that can change a station's protected bands


def _downlinks(notice: SpaceNotice) -> dict[tuple[float, float], set[int]]:
    """Distinct space-to-Earth frequency ranges of a notice, with the groups using each."""
    ranges: dict[tuple[float, float], set[int]] = defaultdict(set)
    for a in notice.assignments:
        if a.get("emi_rcp") == "E" and a.get("freq_min") is not None and a.get("freq_max") is not None:
            ranges[float(a["freq_min"]), float(a["freq_max"])].add(int(a["grp_id"]))  # E = the space station transmits
    return ranges


def _class_summary(stations: Iterable[Station]) -> dict[str, int]:
    return dict(sorted(Counter(s.licence_class or NO_CLASS for s in stations).items()))


def _m4(low: float, high: float, rows: list[M4Row]) -> dict[str, Any]:
    """What M4 allocates across a band: its primary services, and whether space-to-Earth is allocated in Finland."""
    found = [r for r in rows if r.low_mhz < high and r.high_mhz > low]
    if not found:
        return {"m4_space_to_earth": "no M4 row", **finnish_notes(low, high, [], load_rr_footnotes_finland())}
    down = {r.space_down_allocated for r in found}
    joined = lambda values: "; ".join(sorted({v for value in values for v in value.split("; ") if v}))  # noqa: E731
    pages = sorted({p for r in found for p in r.pages.split("-") if p.strip().isdigit()}, key=int)
    return {
        "m4_primary_services": joined(r.primary_services for r in found),
        "finnish_use": joined(r.finnish_use for r in found),
        "m4_space_to_earth": "allocated" if down == {True} else "partly allocated" if True in down else "not allocated",
        **({"m4_space_down_unresolved": joined(r.space_down_unresolved for r in found)} if any(r.space_down_unresolved for r in found) else {}),
        "m4_terrestrial_primary": any(r.terrestrial_primary for r in found),
        "passive": any(r.passive for r in found),
        "m4_table_pages": f"{pages[0]}-{pages[-1]}" if len(pages) > 1 else "".join(pages),
        **finnish_notes(low, high, found, load_rr_footnotes_finland()),
    }


TITLE_EVIDENCE = {
    "exceeds": "; pfd exceeds the limit at {n} under worst-case assumptions",
    "exceeds_flagged": "; pfd above the limit at a station, but an input or its location is flagged",
    "within_3db": "; pfd within 3 dB below the limit at a listed station",
    "bound_above": "; only the filing's upper bound is near or above the limit",
    "no_calculation": "; no pfd calculation covers some of these stations",
    "below": "; pfd calculated below the limit at every listed station",
    "bound_below": "; the filing's upper bound is below the limit",
    "not_visible": "; below the horizon of every listed station",
}


def _bands(
    hits: dict[tuple[Station, ProtectedBand], set[int]], m4_rows: list[M4Row] | None = None, id_limit: int | None = BAND_ID_SAMPLE,
) -> list[dict[str, Any]]:
    """Joins the protected bands hit into contiguous bands, so a case stays readable."""
    merged: list[dict[str, Any]] = []
    for station, protected in sorted(hits, key=lambda hit: (hit[1].low_mhz, hit[1].high_mhz, hit[0].row, hit[1].side)):
        if not merged or protected.low_mhz > merged[-1]["high"]:
            merged.append({"low": protected.low_mhz, "high": protected.high_mhz, "stations": set(), "sides": [], "groups": set()})
        band = merged[-1]
        band["high"] = max(band["high"], protected.high_mhz)
        band["stations"].add(station)
        band["sides"].append(protected.side)
        band["groups"] |= hits[station, protected]
    return [
        {
            "low_mhz": round(b["low"], 6),
            "high_mhz": round(b["high"], 6),
            "classes": _class_summary(b["stations"]),
            "station_count": len(b["stations"]),
            "station_ids": capped(sorted(s.key for s in b["stations"]), id_limit),
            "sides": dict(sorted(Counter(b["sides"]).items())),
            "group_ids": sorted(b["groups"]),
            **(_m4(b["low"], b["high"], m4_rows) if m4_rows is not None else {}),
        }
        for b in merged
    ]


def _matched_on(hits: Iterable[tuple[Station, ProtectedBand]]) -> dict[str, int]:
    """How many stations matched on each side, so a reader can tell a TX-only result from an RX one."""
    sides: dict[str, set[str]] = defaultdict(set)
    for station, protected in hits:
        sides[protected.side].add(station.key)
    return {side: len(keys) for side, keys in sorted(sides.items())}


class StationOverlapRule:
    """A space-to-Earth assignment overlaps a band of a special-interest station, on its RX or TX side.

    The overlap finds the stations; `pfd` supplies what was calculated at each one. Without it every
    station is "no_calculation". The rule id predates TX protection and is kept so cases stay stable.
    """

    id = "station-rx-overlap"

    def __init__(
        self, settings: Settings, stations: list[Station], dataset: dict[str, Any] | None = None,
        pfd: "PfdRule | None" = None, m4_rows: list[M4Row] | None = None,
        station_limit: int | None = STATION_SAMPLE, families: set[int] | None = None,
    ):
        self.settings = settings
        self.index = StationIndex(stations)
        self.protected = self.index.stations
        self.total = len(stations)
        self.dataset = dataset or {}
        self.pfd = pfd
        self.m4_rows = m4_rows
        self.station_limit = station_limit  # None lists every station, for GET /cases/{id}/stations
        self.families = families  # None runs every family

    def _assumptions(self) -> list[str]:
        skipped = self.total - len(self.protected)
        return [
            f"{skipped} of {self.total} stations have no usable RX or TX frequency and were skipped, so they are not "
            "protected here.",
            "RX and TX frequencies are both protected, because Traficom said \"every TX is received in Finland\" "
            "(Discord, 2026-11-07): around a broadcast transmitter, or at the far end of a fixed link. matched_on "
            "gives the side each station matched; \"both\" means its RX and TX bands are the same.",
            "A station's band is its frequency +/- half its channel bandwidth, or half its transmission bandwidth "
            "where the channel bandwidth is blank. Where the two differ, the channel bandwidth is used.",
            "The station data is synthetic, per Traficom.",
            "Each station's result comes from the pfd rule's calculation at its coordinates, over the part of the band "
            "a limit mask covers. A part with no mask, or a mask that needs an input the filing lacks, counts as no "
            "calculation, and a slight edge overlap counts.",
            "Beam coverage is not checked: s_beam gives no boresight in this data, and Traficom said beams \"are not "
            "relevant\" and \"the worst case scenario should always be assumed\" (Discord, 2026-11-07), so maximum "
            "notified gain is applied towards every station.",
            "Antenna direction is not checked: the satellite's is not in the data, and the sheet gives a station "
            "direction but few gains, and the receive gain to assume is unanswered (ticket 02 question 14).",
            f"Severity follows the strongest evidence at any station: a calculated exceedance is high; a value within "
            f"3 dB, an upper bound near or above the limit, or no calculation is medium; a calculated value below, or a "
            f"satellite below every station's horizon, is low. {SEVERITY_NOTE}",
        ]

    def _records(self, issue: SpaceIssue, checks: dict[Station, dict[tuple[int, float, float], tuple[ProtectedBand, ...]]], by_id: dict[int, SpaceNotice]) -> list[dict[str, Any]]:
        """Each station's worst record across the frequency ranges it overlaps. A range with no record is no calculation."""
        evidence = self.pfd.station_evidence(issue) if self.pfd else None
        records = []
        for station, ranges in checks.items():
            found = []
            for (ntc_id, low, high), bands in ranges.items():
                notice = by_id[ntc_id]
                record = evidence.for_range(notice.ntc_id, low, high, station.key) if evidence else None
                if record is None and notice.ntc_type == "G" and notice.gso_lon_deg is not None and station.lat_deg is not None \
                        and station.lon_deg is not None and gso_geometry(station.lat_deg, station.lon_deg, notice.gso_lon_deg) is None:
                    record = record_for(station, bands, "not_visible", reason="gso_below_this_station_horizon", ntc_id=notice.ntc_id)
                found.append(record or record_for(station, bands, "no_calculation", reason="no pfd calculation covers this overlap", ntc_id=notice.ntc_id, band={"low_mhz": low, "high_mhz": high}))
            records.append(worst(found))
        return ordered(records)

    def run(self, issue: SpaceIssue) -> Iterable[Hit]:
        satellites = (n for n in issue.notices.values() if n.ntc_type in SATELLITE_NOTICE_TYPES)
        for family_id, notices in _families(satellites).items():
            if self.families is not None and family_id not in self.families:
                continue
            all_hits: dict[tuple[Station, ProtectedBand], set[int]] = defaultdict(set)
            checks: dict[Station, dict[tuple[int, float, float], tuple[ProtectedBand, ...]]] = defaultdict(dict)
            reasons = set()
            for notice in notices:
                visible, why = visible_from_finland(notice, self.settings)
                if not visible:
                    continue
                reasons.add(why)
                for (low, high), groups in _downlinks(notice).items():
                    for station, bands in self.index.overlapping(low, high):
                        checks[station][notice.ntc_id, low, high] = bands
                        for protected in bands:
                            all_hits[station, protected] |= groups
            if not all_hits:
                continue
            records = self._records(issue, checks, {n.ntc_id: n for n in notices})
            linked = [r for r in records if r["status"] != "not_visible"]
            keep = {r["station_id"] for r in linked} or {r["station_id"] for r in records}
            hits = {k: v for k, v in all_hits.items() if k[0].key in keep}
            head = notices[0]
            notice_ids = sorted(n.ntc_id for n in notices)
            stations = {station for station, _ in hits}
            classes = _class_summary(stations)
            matched_on = _matched_on(hits)
            flagged = {flag: n for flag in BAND_FLAGS if (n := sum(1 for s in stations if flag in s.quality_flags))}
            top = worst(records)
            bands = _bands(hits, self.m4_rows, None if self.station_limit is None else BAND_ID_SAMPLE)
            summary = station_summary(records, self.station_limit)
            details: dict[str, Any] = {
                "method": "screening",
                **summary,
                "classes": classes,
                "matched_on": matched_on,
                "bands": bands,
                "station_band_flags": flagged,
                "visibility": sorted(reasons),
                "sections": sorted({n.provision for n in notices if n.provision}),
                "assumptions": self._assumptions(),
                "station_dataset": self.dataset,
                "source": {"domain": "space", "notice_ids": [str(n) for n in notice_ids]},
                "evidence_status": top["status"],
                "primary_allocation": any(b.get("m4_terrestrial_primary") for b in bands),
                "passive_band": any(b.get("passive") for b in bands),
            }
            calculated = [r for r in records if r["status"] in CALCULATED]
            if calculated:
                best = worst(calculated)
                gso = best["basis"] == "calculated_at_station"
                details.update(
                    method="pfd_gso" if gso else "pfd_ngso",
                    margin_basis="gso_station" if gso else "propagated_station",
                    value_db=best["value_db"], limit_db=best["limit_db"], margin_db=best["margin_db"], mask_id=best["mask_id"],
                    input_flagged=best["status"] == "exceeds_flagged",
                    worst_point={"station_id": best["station_id"], "lat": best["lat"], "lon": best["lon"], "angle_deg": best["angle_deg"],
                                 "distance_km": best["distance_km"], "kind": "listed station site"},
                    calc_inputs={k: best.get(k) for k in ("ntc_id", "group_id", "band", "power_in_ref_bw_dbw", "gain_dbi", "minute", "orb_id", "altitude_km") if best.get(k) is not None},
                )
            ranking = score_finding(details, ScoringWeights.from_settings(self.settings))
            details["severity_score"], details["severity_reasons"] = ranking["score"], ranking["reasons"]
            evidence = ""
            if self.pfd:
                count = sum(1 for r in records if r["status"] == "exceeds")
                evidence = TITLE_EVIDENCE[top["status"]].format(n=f"{count} listed station{'' if count == 1 else 's'}")
            yield Hit(
                rule_id=self.id,
                family_id=family_id,
                severity=severity_of(top["status"]) if self.pfd else "medium",
                title=(
                    f"{head.name or head.ntc_id} ({head.adm}) transmits on a band of {len(stations)} protected "
                    f"station(s): " + ", ".join(f"{name} {count}" for name, count in classes.items())
                    + evidence + ("; TX side only" if set(matched_on) == {SIDE_TX} else "")
                ),
                adm=head.adm,
                network=head.name,
                notice_ids=notice_ids,
                details=details,
                comment_deadline=_deadline(notices, self.settings.comment_window_months),
            )


def station_overlap_rule(
    settings: Settings, path: Path = STATIONS_PATH, pfd: "PfdRule | None" = None, stations: list[Station] | None = None,
) -> StationOverlapRule:
    if stations is None:
        from .stations import protected_stations

        stations = protected_stations(path)
    with path.open("rb") as stream:
        sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    earth = sum(1 for s in stations if s.site)
    dataset = {"file": path.name, "sha256": sha256, "records": len(stations) - earth}
    if earth:
        dataset["earth_stations"] = {"file": EARTH_STATIONS_PATH.name, "records": earth}
    return StationOverlapRule(settings, stations, dataset, pfd, load_m4_rows(settings.m4_filter_path))
