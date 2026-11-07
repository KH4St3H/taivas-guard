"""PFD rules for notified space filings.

The rule deliberately reports missing joined values instead of dropping a group.  A calculated
exceedance is still worded as an exceedance under worst-case assumptions: GIMS contours are not
available, so notified maximum gain is applied towards every Finnish point.
"""
import math
from collections.abc import Iterable
from typing import Any

from ..config import Settings
from ..engines.pfd import GroundPoint, LimitMask, evaluate_gso, finland_points, load_masks, pfd_db
from .rules import Hit, Rule, _deadline, _families
from .scoring import score_finding
from .space import SATELLITE_NOTICE_TYPES, SpaceIssue, SpaceNotice


def _number(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    return float(value) if value is not None and value != "" else None


def _masks_for(low: float, high: float, orbit_type: str, kind: str) -> list[LimitMask]:
    return load_masks().select(low, high, kind, orbit_type)


def _best_join(issue: SpaceIssue, assignment: dict[str, Any]) -> tuple[float | None, float | None, dict[str, Any]]:
    group_id = int(assignment["grp_id"])
    group = issue.groups.get(group_id, {})
    powers = [_number(row, "pwr_ds_max") for row in issue.emissions.get(group_id, [])]
    powers = [p for p in powers if p is not None]
    beam_key = (
        int(assignment["ntc_id"]),
        assignment.get("emi_rcp") or group.get("emi_rcp"),
        assignment.get("beam_name") or group.get("beam_name"),
    )
    gains = [_number(row, "gain") for row in issue.beams.get(beam_key, [])]
    gains = [g for g in gains if g is not None]
    return (
        max(powers) if powers else None,
        max(gains) if gains else None,
        {"group_id": group_id, "beam_name": assignment.get("beam_name") or group.get("beam_name"), "group": group},
    )


def _citation(mask: LimitMask) -> dict[str, Any]:
    return {"doc": mask.citation.get("doc", "RR"), **mask.citation}


POWER_DENSITY_CITATION = {
    "doc": "ITU Space Preface, IFIC 3074 schema, inspected source table description",
    "clause": "emiss table, pwr_ds_max",
    "page_or_url": "docs/research-discarded/itu-primary-sources.md, p. 85",
}


def _calculation(
    notice: SpaceNotice,
    issue: SpaceIssue,
    assignment: dict[str, Any],
    mask: LimitMask,
    points: tuple[GroundPoint, ...],
) -> dict[str, Any] | None:
    power, gain, join = _best_join(issue, assignment)
    if power is None or gain is None or notice.gso_lon_deg is None:
        return None
    result = evaluate_gso(notice.gso_lon_deg, power, gain, mask, points)
    if result.worst is None:
        return None
    return {
        "method": "pfd_gso",
        "calc_inputs": {
            **result.calc_inputs,
            "f_low_mhz": float(assignment["freq_min"]),
            "f_high_mhz": float(assignment["freq_max"]),
            "bandwidth_hz": _number(assignment, "bdwdth"),
            **join,
        },
        "assumptions": [
            *result.assumptions,
            "pwr_ds_max is notified power density in dBW/Hz (Space Preface, p. 85).",
            "Maximum gain and power density are used for the whole assignment.",
        ],
        "worst_point": {
            "lat": result.worst.lat_deg,
            "lon": result.worst.lon_deg,
            "angle_deg": result.worst.angle_deg,
        },
        "value_db": result.worst.value_db,
        "limit_db": result.worst.limit_db,
        "margin_db": result.worst.margin_db,
        "mask_id": result.mask_id,
        "citations": [_citation(mask), POWER_DENSITY_CITATION],
        "band": {"low_mhz": float(assignment["freq_min"]), "high_mhz": float(assignment["freq_max"])},
    }


def _ngso_calculation(
    notice: SpaceNotice,
    orbit: dict[str, Any],
    issue: SpaceIssue,
    assignment: dict[str, Any],
    mask: LimitMask,
    points: tuple[GroundPoint, ...],
) -> dict[str, Any] | None:
    power, gain, join = _best_join(issue, assignment)
    apogee, perigee, inclination = (_number(orbit, key) for key in ("apog_km", "perig_km", "inclin_ang"))
    if power is None or gain is None or None in (apogee, perigee, inclination):
        return None
    radius = 6378.0 + (apogee + perigee) / 2
    period_s = 2 * math.pi * (radius**3 / 398600.4418) ** 0.5
    rate = 2 * math.pi / period_s
    earth_rate = 7.2921159e-5
    worst: tuple[float, GroundPoint, float, float, float] | None = None
    for minute in range(1440):
        argument = rate * minute * 60
        x = radius * math.cos(argument)
        y = radius * math.sin(argument) * math.cos(math.radians(inclination))
        z = radius * math.sin(argument) * math.sin(math.radians(inclination))
        for point in points:
            lon = math.radians(point.lon_deg) + earth_rate * minute * 60
            lat = math.radians(point.lat_deg)
            ux, uy, uz = math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)
            cos_psi = (x * ux + y * uy + z * uz) / radius
            if cos_psi < 6378.0 / radius:
                continue
            distance = (radius**2 + 6378.0**2 - 2 * radius * 6378.0 * cos_psi) ** 0.5
            sin_psi = max(1e-12, (1 - cos_psi**2) ** 0.5)
            angle = math.degrees(math.atan2(cos_psi - 6378.0 / radius, sin_psi))
            value = pfd_db(power, mask.ref_bw_hz, gain, distance)
            limit = mask.limit_db(angle)
            margin = value - limit
            if worst is None or margin > worst[0]:
                worst = (margin, point, angle, value, limit)
    if worst is None:
        return None
    margin, point, angle, value, limit = worst
    return {
        "method": "pfd_ngso",
        "calc_inputs": {
            "f_low_mhz": float(assignment["freq_min"]),
            "f_high_mhz": float(assignment["freq_max"]),
            "p_density_dbw_hz": power,
            "gain_dbi": gain,
            "inclination_deg": inclination,
            "apogee_km": apogee,
            "perigee_km": perigee,
            "propagation_minutes": 1440,
            **join,
        },
        "assumptions": [
            "One-minute propagation over 24 hours uses a circular orbit at the mean notified altitude.",
            "The notified orbital phase and ascending-node longitude are unknown; phase zero is used.",
            "Free-space propagation and maximum gain apply at every Finnish point.",
        ],
        "worst_point": {"lat": point.lat_deg, "lon": point.lon_deg, "angle_deg": angle},
        "value_db": value,
        "limit_db": limit,
        "margin_db": margin,
        "mask_id": mask.mask_id,
        "citations": [_citation(mask)],
    }


def _hit(
    rule_id: str,
    family_id: int,
    notices: list[SpaceNotice],
    calculations: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    settings: Settings,
) -> Hit:
    worst = max(calculations, key=lambda item: item["margin_db"]) if calculations else None
    details: dict[str, Any] = {
        "method": worst["method"] if worst else "screening",
        "calculations": calculations,
        "missing": missing,
        "assumptions": [
            "Results say exceeds under worst-case assumptions; boresight gain may over-estimate off-axis pfd.",
            "Groups missing power density or gain are counted for expert review.",
        ],
    }
    if worst:
        details.update({key: worst[key] for key in ("calc_inputs", "worst_point", "value_db", "limit_db", "margin_db", "mask_id", "citations")})
        details["source_rows"] = {"notice_ids": [n.ntc_id for n in notices]}
    ranking = score_finding(details)
    details["severity_score"] = ranking["score"]
    details["severity_reasons"] = ranking["reasons"]
    severity = "high" if worst and worst["margin_db"] > 0 else "medium" if worst and worst["margin_db"] >= -3 else "low"
    head = notices[0]
    label = "Article 21 limit" if "art21" in rule_id else "Appendix 5 coordination trigger"
    title = f"{head.name or head.ntc_id} ({head.adm}) {label}"
    if worst and worst["margin_db"] > 0:
        title += " exceeds under worst-case assumptions"
    else:
        title += " is within the screened limit"
    return Hit(rule_id, family_id, severity, title, head.adm, head.name, sorted(n.ntc_id for n in notices), details, _deadline(notices, settings.comment_window_months))


class PfdRule:
    id = "pfd"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.points = None

    def run(self, issue: SpaceIssue) -> Iterable[Hit]:
        grouped = _families(n for n in issue.notices.values() if n.ntc_type in SATELLITE_NOTICE_TYPES)
        for family_id, notices in grouped.items():
            for kind, prefix in (("pfd_art21", "pfd-gso-art21"), ("pfd_app5", "pfd-gso-app5")):
                calculations: list[dict[str, Any]] = []
                missing: list[dict[str, Any]] = []
                seen: set[tuple[int, float, float, float | None, float | None, str]] = set()
                for notice in notices:
                    if notice.ntc_type == "N":
                        if not issue.orbits.get(notice.ntc_id):
                            missing.append({"ntc_id": notice.ntc_id, "missing": ["orbit"], "frequency_screen_only": True})
                            continue
                    elif notice.ntc_type != "G":
                        continue
                    for assignment in notice.assignments:
                        if assignment.get("emi_rcp") != "E" or assignment.get("freq_min") is None or assignment.get("freq_max") is None:
                            continue
                        orbit_type = "GSO" if notice.ntc_type == "G" else "NGSO"
                        masks = _masks_for(float(assignment["freq_min"]), float(assignment["freq_max"]), orbit_type, kind)
                        if not masks:
                            continue
                        power, gain, join = _best_join(issue, assignment)
                        if power is None or gain is None:
                            missing.append({
                                **join,
                                "ntc_id": notice.ntc_id,
                                "missing": [name for name, value in (("pwr_ds_max", power), ("gain", gain)) if value is None],
                                "freq_min": float(assignment["freq_min"]),
                                "freq_max": float(assignment["freq_max"]),
                            })
                            continue
                        for mask in masks:
                            if notice.ntc_type == "N" and mask.parameter is not None:
                                missing.append({
                                    "ntc_id": notice.ntc_id,
                                    "group_id": int(assignment["grp_id"]),
                                    "missing": [mask.parameter["name"]],
                                    "mask_id": mask.mask_id,
                                    "frequency_screen_only": True,
                                })
                                continue
                            power, gain, _ = _best_join(issue, assignment)
                            key = (
                                notice.ntc_id,
                                float(assignment["freq_min"]),
                                float(assignment["freq_max"]),
                                power,
                                gain,
                                mask.mask_id,
                            )
                            if key in seen:
                                continue
                            seen.add(key)
                            calculation = (
                                _calculation(notice, issue, assignment, mask, self._points())
                                if notice.ntc_type == "G"
                                else _ngso_calculation(
                                    notice, issue.orbits[notice.ntc_id][0], issue, assignment, mask, self._ngso_points()
                                )
                            )
                            if calculation:
                                calculations.append(calculation)
                if calculations or missing:
                    yield _hit(prefix, family_id, notices, calculations, missing, self.settings)

    def _points(self) -> tuple[GroundPoint, ...]:
        if self.points is None:
            self.points = finland_points()
        return self.points

    def _ngso_points(self) -> tuple[GroundPoint, ...]:
        # The one-minute propagation remains intact; this deterministic subset keeps a full
        # real filing tractable until a vectorised orbit library is introduced.
        points = self._points()
        return (points[0], points[len(points) // 4], points[len(points) // 2], points[(3 * len(points)) // 4], points[-1])


def pfd_rule(settings: Settings) -> Rule:
    return PfdRule(settings)
