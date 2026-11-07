"""PFD rules for notified space filings.

The rule deliberately reports missing joined values instead of dropping a group.  A calculated
exceedance is still worded as an exceedance under worst-case assumptions: GIMS contours are not
available, so notified maximum gain is applied towards every Finnish point.
"""
from collections.abc import Iterable
from typing import Any

from ..config import Settings
from ..engines.pfd import GroundPoint, LimitMask, evaluate_gso, finland_points, load_masks, pfd_db
from .rules import Hit, Rule, _deadline, _families
from .scoring import ScoringWeights, score_finding
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
    "doc": "IFIC Space Preface (secondary schema note; primary copy unavailable)",
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
            "pwr_ds_max is treated as dBW/Hz per a secondary schema note; primary Space Preface confirmation is unavailable.",
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
    orbits: list[dict[str, Any]],
    issue: SpaceIssue,
    assignment: dict[str, Any],
    mask: LimitMask,
    points: tuple[GroundPoint, ...],
) -> dict[str, Any] | None:
    power, gain, join = _best_join(issue, assignment)
    complete = [
        row for row in orbits
        if None not in (_number(row, "apog_km"), _number(row, "perig_km"), _number(row, "inclin_ang"))
    ]
    if power is None or gain is None or not complete:
        return None
    perigee = min(_number(row, "perig_km") for row in complete)
    apogee = max(_number(row, "apog_km") for row in complete)
    inclination = max(_number(row, "inclin_ang") for row in complete)
    # Perigee plus the lowest mask value is a conservative upper bound: it does not
    # depend on an assumed node/phase and covers every orbit row in the notice.
    value = pfd_db(power, mask.ref_bw_hz, gain, perigee)
    angle, limit = 0.0, min(mask.limit_db(p) for p, _ in mask.breakpoints)
    margin = value - limit
    point = points[0]
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
            "orbit_rows_considered": len(orbits),
            "perigee_bound_km": perigee,
            "apogee_bound_km": apogee,
            **join,
        },
        "assumptions": [
            "NGSO is bounded conservatively at the smallest notified perigee; eccentricity is not replaced by mean altitude.",
            "The perigee bound and lowest mask value cover unknown node, phase, visibility and Finnish grid geometry.",
            "This is an upper-bound screen, not a time-sampled orbit result; below-limit results remain expert review items.",
            "pwr_ds_max is treated as dBW/Hz per a secondary schema note; primary Space Preface confirmation is unavailable.",
        ],
        "worst_point": {"lat": point.lat_deg, "lon": point.lon_deg, "angle_deg": angle},
        "value_db": value,
        "limit_db": limit,
        "margin_db": margin,
        "mask_id": mask.mask_id,
        "citations": [_citation(mask), POWER_DENSITY_CITATION],
    }


def _hit(
    rule_id: str,
    family_id: int,
    notices: list[SpaceNotice],
    calculations: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    dropped: list[dict[str, Any]],
    settings: Settings,
) -> Hit:
    worst = max(calculations, key=lambda item: item["margin_db"]) if calculations else None
    details: dict[str, Any] = {
        "method": worst["method"] if worst else "screening",
        "calculations": calculations,
        "missing": missing,
        "dropped": dropped,
        "dropped_count": len(dropped),
        "unevaluated_count": len(missing),
        "expert_review": True,
        "assumptions": [
            "Results are possible concerns for expert review; they do not establish compliance.",
            "Groups missing power density or gain are counted for expert review.",
        ],
    }
    if worst:
        details.update({key: worst[key] for key in ("calc_inputs", "worst_point", "value_db", "limit_db", "margin_db", "mask_id", "citations")})
        details["source_rows"] = {"notice_ids": [n.ntc_id for n in notices]}
    ranking = score_finding(details, ScoringWeights.from_settings(settings))
    details["severity_score"] = ranking["score"]
    details["severity_reasons"] = ranking["reasons"]
    severity = "high" if worst and worst["margin_db"] > 0 else "medium"
    head = notices[0]
    label = "Article 21 limit" if "art21" in rule_id else "Appendix 5 coordination trigger"
    orbit_label = "GSO" if rule_id.startswith("pfd-gso-") else "NGSO"
    title = f"{head.name or head.ntc_id} ({head.adm}) {label}"
    title = f"{head.name or head.ntc_id} ({head.adm}) {orbit_label} {label}"
    if not calculations:
        missing_names = sorted(
            {name for row in missing for name in row.get("missing", [])}
            | {row.get("reason", "required inputs") for row in dropped}
        )
        title += f" not evaluated; missing {', '.join(missing_names) or 'required inputs'}"
    elif len(missing):
        title += f"; {len(missing)} assignment(s) not evaluated"
    elif worst and worst["margin_db"] > 0:
        title += " exceeds under worst-case assumptions"
    else:
        title += " is below the screened bound; expert review required"
    return Hit(rule_id, family_id, severity, title, head.adm, head.name, sorted(n.ntc_id for n in notices), details, _deadline(notices, settings.comment_window_months))


class PfdRule:
    id = "pfd"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.points = None

    def run(self, issue: SpaceIssue) -> Iterable[Hit]:
        grouped = _families(n for n in issue.notices.values() if n.ntc_type in SATELLITE_NOTICE_TYPES)
        for family_id, notices in grouped.items():
            for orbit_type, orbit_prefix in (("GSO", "gso"), ("NGSO", "ngso")):
              for kind, kind_prefix in (("pfd_art21", "art21"), ("pfd_app5", "app5")):
                calculations: list[dict[str, Any]] = []
                missing: list[dict[str, Any]] = []
                dropped: list[dict[str, Any]] = []
                seen: set[tuple[int, float, float, float | None, float | None, str]] = set()
                for notice in notices:
                    if (notice.ntc_type == "G") != (orbit_type == "GSO"):
                        continue
                    if notice.ntc_type == "N":
                        if not issue.orbits.get(notice.ntc_id):
                            missing.append({"ntc_id": notice.ntc_id, "missing": ["orbit"], "frequency_screen_only": True})
                            continue
                    elif notice.ntc_type != "G":
                        continue
                    for assignment in notice.assignments:
                        if assignment.get("emi_rcp") != "E" or assignment.get("freq_min") is None or assignment.get("freq_max") is None:
                            continue
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
                                    notice, issue.orbits[notice.ntc_id], issue, assignment, mask, self._ngso_points()
                                )
                            )
                            if calculation:
                                calculations.append(calculation)
                            else:
                                dropped.append({
                                    "ntc_id": notice.ntc_id,
                                    "group_id": int(assignment["grp_id"]),
                                    "mask_id": mask.mask_id,
                                    "reason": "no visible Finnish point or GSO longitude",
                                })
                if calculations or missing or dropped:
                    yield _hit(
                        f"pfd-{orbit_prefix}-{kind_prefix}", family_id, notices, calculations, missing, dropped, self.settings
                    )

    def _points(self) -> tuple[GroundPoint, ...]:
        if self.points is None:
            self.points = finland_points()
        return self.points

    def _ngso_points(self) -> tuple[GroundPoint, ...]:
        # Retained as representative points for the reported bound; the bound itself is
        # independent of grid coverage.
        points = self._points()
        return (points[0], points[len(points) // 4], points[len(points) // 2], points[(3 * len(points)) // 4], points[-1])


def pfd_rule(settings: Settings) -> Rule:
    return PfdRule(settings)
