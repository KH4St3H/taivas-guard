"""Where over Finland a case's satellite can reach, computed on request for the finding's map.

There is no beam footprint in the IFIC data (s_beam gives no boresight), and Traficom said to assume the
worst case, so this maps reach, not coverage:

- visibility: the angle of arrival at each cell. GSO from the orbital position; non-GSO from the same
  one-day two-body flight the pfd rule uses, giving the highest angle and the minutes in view;
- worst-case pfd: maximum notified gain towards every cell, so only distance changes across Finland.
  Where an RR Table 21-4 mask covers the band, the margin against it as well;
- stations: Traficom's listed stations whose RX or TX band overlaps the case's bands.

Nothing here is stored on the case, so reviewing a case is not affected by it.
"""
import json
import math
import threading
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ..config import get_settings
from ..engines.pfd import MASK_DIR, GroundPoint, LimitMask, _inside, gso_geometry, spreading_loss_db
from ..engines.pfd_ngso import _positions_over, _region, _seen_from, _unit, reach_latitude_deg
from .issue_cache import CaseSource, case_source, load_issue
from .rule_pfd import _best_join, _emission_for_mask, _orbit_shapes, _power_in_ref_bw, _select
from .rules import visible_from_finland
from .space import SATELLITE_NOTICE_TYPES, SpaceIssue, SpaceNotice
from .stations import STATIONS_PATH, StationIndex, load_earth_stations, load_stations_cached

LAT_STEP = 0.2  # about 22 km
LON_STEP = 0.45  # about 21 km at 64 N, so cells are roughly square on the ground
DEFAULT_REF_BW_HZ = 1e6  # where no mask gives a reference bandwidth
MAX_SHAPES = 4  # non-GSO orbit shapes flown per case; more are listed as not flown
STATION_POINTS_MAX = 3000  # above this, stations are counted per map cell instead of drawn one by one
_lock = threading.Lock()


def accepts(source: CaseSource) -> bool:
    return bool(source.details.get("bands")) and not source.rule_id.startswith("pfd-")


@lru_cache(maxsize=1)
def boundary() -> list[list[list[float]]]:
    with (MASK_DIR / "finland_boundary.json").open(encoding="utf-8") as f:
        return json.load(f)["rings"]


@lru_cache(maxsize=1)
def cells() -> tuple[GroundPoint, ...]:
    """Centres of the cells that touch Finland. Coarser than the pfd rule's grid plus boundary: this is for drawing.

    A cell counts when its centre or a corner is inside, so the coast and border have no gaps; the map clips
    cells to the boundary, and an edge cell's values are those at its centre.
    """
    rings = boundary()
    lons = [c[0] for r in rings for c in r]
    lats = [c[1] for r in rings for c in r]
    out = []
    lat = min(lats) + LAT_STEP / 2
    while lat < max(lats):
        lon = min(lons) + LON_STEP / 2
        while lon < max(lons):
            probes = [(lon, lat)] + [(lon + dx * LON_STEP / 2, lat + dy * LAT_STEP / 2) for dx in (-1, 1) for dy in (-1, 1)]
            if any(_inside(x, y, ring) for x, y in probes for ring in rings):
                out.append(GroundPoint(round(lat, 4), round(lon, 4), "cell"))
            lon += LON_STEP
        lat += LAT_STEP
    return tuple(out)


@dataclass
class Cell:
    angle_deg: float | None = None  # highest angle of arrival; None if never above the horizon
    minutes: int | None = None  # non-GSO: minutes in view during the day flown
    pfd_db: float | None = None
    margin_db: float | None = None

    def raise_to(self, angle: float | None = None, minutes: int | None = None, pfd: float | None = None, margin: float | None = None):
        if angle is not None and (self.angle_deg is None or angle > self.angle_deg):
            self.angle_deg = angle
        if minutes is not None:
            self.minutes = max(self.minutes or 0, minutes)
        if pfd is not None and (self.pfd_db is None or pfd > self.pfd_db):
            self.pfd_db = pfd
        if margin is not None and (self.margin_db is None or margin > self.margin_db):
            self.margin_db = margin


@dataclass(frozen=True)
class Emission:
    """The strongest transmission in the case's bands: what the pfd layer assumes."""
    ntc_id: int
    group_id: int
    f_low_mhz: float
    f_high_mhz: float
    power_in_ref_bw_dbw: float
    gain_dbi: float
    ref_bw_hz: float
    mask: LimitMask | None

    @property
    def eirp_db(self) -> float:
        return self.power_in_ref_bw_dbw + self.gain_dbi


def _in_case_bands(a: dict[str, Any], bands: list[dict[str, Any]]) -> bool:
    low, high = float(a["freq_min"]), float(a["freq_max"])
    return any(low < float(b["high_mhz"]) and high > float(b["low_mhz"]) for b in bands)


def _strongest(issue: SpaceIssue, notices: list[SpaceNotice], bands: list[dict[str, Any]]) -> tuple[Emission | None, Counter]:
    """Compared at 1 MHz so emissions with different masks rank fairly; each is then mapped in its mask's bandwidth."""
    skipped: Counter = Counter()
    best: tuple[float, Emission] | None = None
    for notice in notices:
        orbit_type = "GSO" if notice.ntc_type == "G" else "NGSO"
        inclination = max(notice.inclinations_deg, default=None)
        for a in notice.assignments:
            if a.get("emi_rcp") != "E" or a.get("freq_min") is None or a.get("freq_max") is None or not _in_case_bands(a, bands):
                continue
            power, gain, join, _ = _best_join(issue, {**a, "ntc_id": notice.ntc_id})
            if power is None or gain is None:
                skipped["no power density" if power is None else "no antenna gain"] += 1
                continue
            low, high = float(a["freq_min"]), float(a["freq_max"])
            masks = _select(low, high, "pfd_art21", orbit_type, inclination, None)
            # Several candidate masks, or one needing an input the filing lacks (X, Y): no single margin to show.
            mask = masks[0] if len(masks) == 1 and not masks[0].parameter else None
            if mask is not None:
                density, peak, join = _emission_for_mask(issue, join, mask)
                if density is None:
                    continue
                in_ref = _power_in_ref_bw(density, peak, mask.ref_bw_hz)
            else:
                in_ref = _power_in_ref_bw(power, join.get("pep_max_dbw"), DEFAULT_REF_BW_HZ)
            rank = _power_in_ref_bw(power, join.get("pep_max_dbw"), DEFAULT_REF_BW_HZ) + gain
            emission = Emission(notice.ntc_id, int(a["grp_id"]), low, high, in_ref, gain,
                                mask.ref_bw_hz if mask else DEFAULT_REF_BW_HZ, mask)
            if best is None or rank > best[0]:
                best = (rank, emission)
    return (best[1] if best else None), skipped


def _gso(notice: SpaceNotice, grid: dict[GroundPoint, Cell], emission: Emission | None) -> None:
    for point, cell in grid.items():
        geometry = gso_geometry(point.lat_deg, point.lon_deg, notice.gso_lon_deg)
        if geometry is None:
            continue
        pfd = margin = None
        if emission and emission.ntc_id == notice.ntc_id:
            pfd = emission.eirp_db - spreading_loss_db(geometry.distance_km)
            if emission.mask:
                margin = pfd - emission.mask.limit_db(geometry.angle_deg)
        cell.raise_to(geometry.angle_deg, pfd=pfd, margin=margin)


def _ngso(issue: SpaceIssue, notice: SpaceNotice, grid: dict[GroundPoint, Cell], emission: Emission | None, notes: list[str]) -> bool:
    """True when at least one orbit shape was flown."""
    shapes, _ = _orbit_shapes(issue, notice.ntc_id, issue.orbits.get(notice.ntc_id, []))
    flown = [s for s in shapes if not s.not_flown_reason]
    if len(flown) > MAX_SHAPES:
        notes.append(f"{notice.name or notice.ntc_id}: flew {MAX_SHAPES} of {len(flown)} orbit shapes.")
    if not flown:
        reach = max((reach_latitude_deg(i) for i in notice.inclinations_deg), default=None)
        notes.append(
            f"{notice.name or notice.ntc_id}: no orbit row has all the elements needed to fly it"
            + (f"; its inclination takes it as far as {reach:.0f} deg latitude, but where it passes over Finland is unknown." if reach else ".")
        )
        return False
    units = {point: _unit(point) for point in grid}
    region = _region(list(units.values()))
    mine = emission if emission and emission.ntc_id == notice.ntc_id else None
    for shape in flown[:MAX_SHAPES]:
        elements = (shape.perigee_km, shape.apogee_km, shape.inclination_deg, shape.perigee_arg_deg, shape.node_lon_deg, shape.phase_deg)
        seen: dict[GroundPoint, list[tuple[float, float]]] = {}
        for position in _positions_over(*elements, region):
            for point, unit in units.items():
                if (sample := _seen_from(position, unit)) is not None:
                    seen.setdefault(point, []).append((math.degrees(math.asin(max(-1.0, min(1.0, sample[0])))), sample[1]))
        for point, samples in seen.items():
            pfd = margin = None
            if mine:
                pfd = mine.eirp_db - spreading_loss_db(min(d for _, d in samples))
                if mine.mask:
                    margin = max(mine.eirp_db - spreading_loss_db(d) - mine.mask.limit_db(max(0.0, a)) for a, d in samples)
            grid[point].raise_to(max(a for a, _ in samples), len(samples), pfd, margin)
    return True


def _stations(bands: list[dict[str, Any]]) -> dict[str, Any]:
    index = StationIndex(load_stations_cached(STATIONS_PATH) + load_earth_stations())
    found = {}
    for b in bands:
        for station, _ in index.overlapping(float(b["low_mhz"]), float(b["high_mhz"])):
            found[station.key] = station
    located = [s for s in found.values() if s.lat_deg is not None and s.lon_deg is not None]
    by_class = Counter(s.licence_class or "no class" for s in found.values())
    out: dict[str, Any] = {"total": len(found), "without_location": len(found) - len(located), "by_class": dict(by_class.most_common())}
    if len(located) <= STATION_POINTS_MAX:
        out["points"] = [{"id": s.key, "lat": s.lat_deg, "lon": s.lon_deg, "licence": s.licence_class} for s in located]
    else:
        bins = Counter((round(math.floor(s.lat_deg / LAT_STEP) * LAT_STEP + LAT_STEP / 2, 4),
                        round(math.floor(s.lon_deg / LON_STEP) * LON_STEP + LON_STEP / 2, 4)) for s in located)
        out["bins"] = [{"lat": la, "lon": lo, "count": n} for (la, lo), n in bins.items()]
    return out


@lru_cache(maxsize=8)
def _compute(source: CaseSource) -> dict[str, Any]:
    settings = get_settings()
    issue = load_issue(source)
    bands = source.details.get("bands", [])
    family = [n for n in issue.notices.values() if n.family_id == source.family_id and n.ntc_type in SATELLITE_NOTICE_TYPES]
    visible = [n for n in family if visible_from_finland(n, settings)[0]]
    grid = {point: Cell() for point in cells()}
    emission, skipped = _strongest(issue, visible, bands)
    notes: list[str] = []
    mapped = False  # False: nothing could be placed, so empty cells mean "unknown", not "never in view"
    for notice in visible:
        if notice.ntc_type == "G" and notice.gso_lon_deg is not None:
            _gso(notice, grid, emission)
            mapped = True
        elif notice.ntc_type == "N":
            mapped = _ngso(issue, notice, grid, emission, notes) or mapped
        else:
            notes.append(f"{notice.name or notice.ntc_id}: no orbital position is notified, so its reach can't be mapped.")
    kinds = {n.ntc_type for n in visible}
    pfd: dict[str, Any] = {"available": emission is not None}
    if emission:
        pfd.update(
            ref_bw_hz=emission.ref_bw_hz, ntc_id=emission.ntc_id, group_id=emission.group_id,
            f_low_mhz=emission.f_low_mhz, f_high_mhz=emission.f_high_mhz,
            power_in_ref_bw_dbw=round(emission.power_in_ref_bw_dbw, 2), gain_dbi=emission.gain_dbi,
            mask_id=emission.mask.mask_id if emission.mask else None,
            limit_kind="RR Table 21-4" if emission.mask else None,
        )
    else:
        pfd["reason"] = (
            "No transmission in these bands notifies both power density and antenna gain"
            + (f" ({', '.join(f'{k}: {n}' for k, n in skipped.items())})" if skipped else "") + "."
        )
    return {
        "issue_no": source.issue_no,
        "mapped": mapped,
        "boundary": boundary(),
        "cell": {"lat_step": LAT_STEP, "lon_step": LON_STEP},
        "orbit": "gso" if kinds == {"G"} else "ngso" if kinds == {"N"} else "mixed" if kinds else "none",
        "gso_lon_deg": next((n.gso_lon_deg for n in visible if n.gso_lon_deg is not None), None),
        "satellites": list(dict.fromkeys(n.name or str(n.ntc_id) for n in visible)),  # paired notices share a name
        "cells": [
            {"lat": p.lat_deg, "lon": p.lon_deg, "angle_deg": _r(c.angle_deg, 1), "minutes": c.minutes,
             "pfd_db": _r(c.pfd_db, 1), "margin_db": _r(c.margin_db, 1)}
            for p, c in grid.items()
        ],
        "pfd": pfd,
        "stations": _stations(bands),
        "notes": notes,
        "assumptions": [
            "No beam footprint is notified, so this shows where the satellite can reach, not where its beam points.",
            "pfd assumes the maximum notified gain towards every cell and free-space spreading, so it varies only with distance.",
            "Non-GSO values come from one day of two-body flight per orbit shape, in one-minute steps; they are samples, not bounds.",
        ],
    }


def _r(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def coverage(case_id: int) -> dict[str, Any]:
    source = case_source(case_id, accepts, "This case has no bands to map.")
    with _lock:
        return _compute(source)
