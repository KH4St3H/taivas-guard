"""Rechecks a sample of exported cases from the raw ITU tables, without the rules' own joins.

Inputs are read with the parser directly and the pfd and distance formulas are written out here.
Three things still come from the project and are named in the output: limit masks and the M4 band
list (data the rules also use), and the terrestrial filter under test.

    uv run python tools/hand_check.py --shared data/shared --outputs outputs
"""
import argparse
import collections
import json
import math
import random
from pathlib import Path

from access_parser import AccessParser
from openpyxl import load_workbook

from ific_guard.engines.pfd import MASK_DIR, load_masks
from ific_guard.screening.m4 import load_m4_conflict_bands
from ific_guard.screening.space import MdbReader
from ific_guard.terrestrial.adapter import TerrestrialIssue, filter_near_finland
from ific_guard.config import get_settings

RE, RS = 6378.0, 42164.0
FINLAND_CENTRE = (64.5, 26.0)
SEED = 3074


def rows(db, name):
    columns = db.parse_table(name)
    names = list(columns)
    return [dict(zip(names, values)) for values in zip(*columns.values())]


def spread(distance_km):
    return 10 * math.log10(4 * math.pi * (distance_km * 1000) ** 2)


def central_deg(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    value = math.sin(a) * math.sin(b) + math.cos(a) * math.cos(b) * math.cos(math.radians(lon1 - lon2))
    return math.degrees(math.acos(max(-1.0, min(1.0, value))))


def haversine_km(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    h = math.sin((b - a) / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def load_cases(path):
    data = json.loads(Path(path).read_text())
    return data if isinstance(data, list) else data["cases"]


class Space:
    def __init__(self, path):
        db = AccessParser(str(path))
        self.notice = {int(r["ntc_id"]): r for r in rows(db, "notice")}
        self.freq = rows(db, "freq")
        self.grp = {int(r["grp_id"]): r for r in rows(db, "grp")}
        self.provn = rows(db, "provn")
        self.tr_provn = rows(db, "tr_provn")
        self.emiss = collections.defaultdict(list)
        for row in rows(db, "emiss"):
            self.emiss[int(row["grp_id"])].append(row)
        self.beams = rows(db, "s_beam")
        self.geo = {int(r["ntc_id"]): r for r in rows(db, "geo")}
        self.orbit = collections.defaultdict(list)
        for row in rows(db, "orbit"):
            self.orbit[int(row["ntc_id"])].append(row)
        self.ref_body = {int(r["ntc_id"]): r["ref_body"] for r in rows(db, "non_geo")}
        self.phase = rows(db, "phase")
        self.freq_by_group = collections.defaultdict(list)
        for row in self.freq:
            if row["grp_id"] is not None:
                self.freq_by_group[int(row["grp_id"])].append(row)

    def beam(self, ntc_id, name):
        return [b for b in self.beams if int(b["ntc_id"]) == ntc_id and b["emi_rcp"] == "E" and b["beam_name"] == name]


def check_finland_named(space, cases, out):
    named_cases = [c for c in cases if c["rule_id"] == "fin-named-by-br"]
    in_cases = {int(n) for c in named_cases for n in c["notice_ids"]}
    raw = {int(space.grp[int(r["grp_id"])]["ntc_id"]) for r in space.provn if r["adm"] == "FIN" and int(r["grp_id"]) in space.grp}
    raw |= {int(r["ntc_id"]) for r in space.tr_provn if r["adm"] == "FIN"}
    in_issue = raw & set(space.notice)
    out.append("\n## fin-named-by-br\n")
    out.append(f"Whole-rule sweep of `provn` and `tr_provn`: {len(raw)} notices name FIN, {len(in_issue)} of them are in this issue's `notice` table.")
    out.append(f"- Cases: {len(named_cases)}, covering {len(in_cases)} notices.")
    out.append(f"- In a case but no FIN row (false positives): {sorted(in_cases - raw)}")
    missed = in_issue - in_cases
    reasons = collections.Counter((space.notice[n]["ntc_type"], space.notice[n]["ntf_rsn"]) for n in missed)
    out.append(f"- FIN row but no case (possible misses): {sorted(missed)}; by notice type and reason: {dict(reasons)}")


def check_m4(space, cases, sample, out):
    bands = load_m4_conflict_bands(get_settings().m4_filter_path)
    cases = [c for c in cases if c["rule_id"] == "m4-no-space-to-earth"]
    out.append("\n## m4-no-space-to-earth\n")
    in_cases = {int(n) for c in cases for n in c["notice_ids"]}
    transmit = collections.defaultdict(list)
    for row in space.freq:
        if row["emi_rcp"] == "E" and row["freq_min"] is not None and row["freq_max"] is not None:
            transmit[int(row["ntc_id"])].append(row)
    overlapping = {
        n for n, notice in space.notice.items() if notice["ntc_type"] in ("G", "N")
        and any(float(r["freq_min"]) < b.high_mhz and float(r["freq_max"]) > b.low_mhz for r in transmit.get(n, []) for b in bands)
    }
    missed = overlapping - in_cases
    out.append(f"Sweep with the project's M4 band list: {len(overlapping)} satellite notices transmit in one, {len(in_cases & overlapping)} are in a case, {len(missed)} are not.")
    settings = get_settings()
    unexplained = []
    for n in missed:
        if n in space.geo and space.geo[n]["long_nom"] is not None:
            longitude = float(space.geo[n]["long_nom"])
            if not settings.gso_visible_west_deg <= longitude <= settings.gso_visible_east_deg:
                continue
        elif space.orbit.get(n):
            reach = max(min(float(o["inclin_ang"]), 180 - float(o["inclin_ang"])) for o in space.orbit[n] if o["inclin_ang"] is not None)
            if reach < settings.ngso_min_inclination_deg:
                continue
        unexplained.append(n)
    stages = collections.Counter(space.notice[n]["ntf_rsn"] for n in unexplained)
    out.append(f"- Not in a case and not explained by the visibility screen: {len(unexplained)}; by notice reason (the rules screen A and C only): {dict(stages)}")
    out.append(f"- In scope and still not in a case: {sorted(n for n in unexplained if space.notice[n]['ntf_rsn'] in ('A', 'C'))}")
    out.append(f"- False positives cannot be counted: none of the {len(cases)} cases checks beam coverage, so the rule over-flags by design.")
    for case in sample.sample(cases, min(3, len(cases))):
        band = case["details"]["bands"][0]
        group = band["group_ids"][0]
        row = next(r for r in space.freq_by_group[group] if r["emi_rcp"] == "E")
        csv_band = next(b for b in bands if b.low_mhz == band["low_mhz"] and b.high_mhz == band["high_mhz"])
        overlap = float(row["freq_min"]) < csv_band.high_mhz and float(row["freq_max"]) > csv_band.low_mhz
        out.append(
            f"- {case['title'][:70]}: group {group} raw E row {row['freq_min']:g}-{row['freq_max']:g} MHz, band {band['low_mhz']:g}-{band['high_mhz']:g} MHz "
            f"({band['m4_primary_services'][:50]}), overlap {overlap}."
        )


def check_stations(space, cases, sample, xlsx, out):
    cases = [c for c in cases if c["rule_id"] == "station-rx-overlap"]
    sheet = load_workbook(xlsx, read_only=True).worksheets[0]
    table = list(sheet.iter_rows(values_only=True))
    header_index = next(i for i, row in enumerate(table) if row and "RX frequency" in row)
    header = table[header_index]
    out.append("\n## station-rx-overlap\n")
    out.append(f"{len(cases)} cases. Sample read from the spreadsheet row and the raw `freq` row:")
    for case in sample.sample(cases, min(3, len(cases))):
        band = case["details"]["bands"][0]
        key = band["station_ids"][0]
        row = table[int(key.split("@R")[1]) - 1]
        cells = dict(zip(header, row))
        rows_in_group = [r for g in band["group_ids"] for r in space.freq_by_group[g] if r["emi_rcp"] == "E"]
        rx = cells["RX frequency"]
        bw = cells["Channel bandwidth"]
        hit = next((r for r in rows_in_group if float(r["freq_min"]) <= band["high_mhz"] and float(r["freq_max"]) >= band["low_mhz"]), None)
        out.append(
            f"- {case['title'][:60]}: station {key}, sheet RX {rx}, TX {cells['TX frequency']}, channel {bw}; joined band {band['low_mhz']:g}-{band['high_mhz']:g} MHz; "
            f"raw E row {hit and (hit['freq_min'], hit['freq_max'])}."
        )


def power_in_ref(row, ref):
    density = float(row["pwr_ds_max"])
    peak = None if row["pep_max"] is None else float(row["pep_max"])
    return min(density + 10 * math.log10(ref), peak) if peak is not None else density + 10 * math.log10(ref)


def check_pfd(space, cases, sample, out):
    masks = load_masks()
    out.append("\n## pfd rules\n")
    out.append("Power, gain and orbit read from raw rows; pfd and geometry from the closed forms; limits from `limit_masks.json`.\n")
    worst_delta = 0.0
    for rule in ("pfd-gso-art21", "pfd-gso-app5", "pfd-ngso-art21", "pfd-ngso-app5"):
        calcs = [(c, k) for c in cases if c["rule_id"] == rule for k in c["details"]["calculations"]]
        kinds = sorted({k["result"] for _, k in calcs})
        for kind in kinds:
            case, calc = sample.choice([x for x in calcs if x[1]["result"] == kind])
            inputs = calc["calc_inputs"]
            ntc, group = int(calc["ntc_id"]), int(inputs["group_id"])
            ref = masks.by_id(calc["mask_id"]).ref_bw_hz
            usable = [r for r in space.emiss[group] if r["pwr_ds_max"] is not None and not (r["pep_max"] is not None and r["pwr_ds_max"] > r["pep_max"])]
            power = max(power_in_ref(r, ref) for r in usable)
            gain = max(float(b["gain"]) for b in space.beam(ntc, inputs["beam_name"]) if b["gain"] is not None)
            point = calc["worst_point"]
            mask = masks.by_id(calc["mask_id"])
            if rule.startswith("pfd-gso"):
                longitude = float(space.geo[ntc]["long_nom"])
                cos_psi = math.cos(math.radians(point["lat"])) * math.cos(math.radians(longitude - point["lon"]))
                distance = math.sqrt(RE**2 + RS**2 - 2 * RE * RS * cos_psi)
                angle = math.degrees(math.atan2(cos_psi - RE / RS, math.sqrt(1 - cos_psi**2)))
            else:
                altitude, angle = point["altitude_km"], point["angle_deg"]
                radius = RE + altitude
                a = math.radians(angle)
                distance = math.sqrt(radius**2 - (RE * math.cos(a)) ** 2) - RE * math.sin(a)
            limit = mask.limit_db(angle)
            margin = power + gain - spread(distance) - limit
            delta = margin - calc["margin_db"]
            worst_delta = max(worst_delta, abs(delta))
            out.append(
                f"- {rule} `{kind}`: {case['network']} ntc {ntc} group {group} {inputs['f_low_mhz']:g}-{inputs['f_high_mhz']:g} MHz: "
                f"P in {ref:g} Hz {power:.2f} dBW, G {gain:g} dBi, d {distance:.0f} km, angle {angle:.2f} deg, limit {limit:.1f}. "
                f"Hand margin {margin:+.3f}, reported {calc['margin_db']:+.3f}, difference {delta:+.4f} dB."
            )
    out.append(f"\nLargest difference across the sample: {worst_delta:.4f} dB.\n")

    high = [c for c in cases if c["rule_id"].startswith("pfd") and c["severity"] == "high"]
    with_boresight = sum(b["bore_lat"] is not None and b["bore_long"] is not None for b in space.beams)
    out.append(f"`s_beam` rows with a boresight position in this issue: {with_boresight} of {len(space.beams)}.\n")
    tally = collections.Counter()
    lines = []
    for case in high:
        calc = case["details"]["calculations"]
        worst = max((k for k in calc if k["result"] == "exceeds"), key=lambda k: k["margin_db"])
        beams = space.beam(int(worst["ntc_id"]), worst["calc_inputs"]["beam_name"])
        located = [b for b in beams if b["bore_lat"] is not None and b["bore_long"] is not None]
        if not located:
            tally["no boresight notified"] += 1
            verdict = "no boresight notified"
        else:
            beam = located[0]
            sep = central_deg(float(beam["bore_lat"]), float(beam["bore_long"]), *FINLAND_CENTRE)
            verdict = f"boresight {float(beam['bore_lat']):.1f},{float(beam['bore_long']):.1f}, {sep:.0f} deg from central Finland"
            tally["boresight over 20 deg of arc away" if sep > 20 else "boresight within 20 deg of arc"] += 1
        lines.append(f"- {case['rule_id']} {case['network']} ({case['adm']}): margin {worst['margin_db']:+.1f} dB, {verdict}.")
    out.append(f"Beam pointing of the {len(high)} high pfd cases, which apply maximum gain towards Finland: {dict(tally)}.\n")
    out.extend(lines)


MU, EARTH_TURN_DEG_PER_MIN = 398600.4418, 360.98564736629 / 1440


def sheet_point(table, header, key):
    """A station's coordinates read from its sheet row, with the sheet's decimal commas."""
    cells = dict(zip(header, table[int(key.split("@R")[1]) - 1]))
    return float(str(cells["Latitude"]).replace(",", ".")), float(str(cells["Longitude"]).replace(",", "."))


def unit(lat, lon):
    a, b = math.radians(lat), math.radians(lon)
    return math.cos(a) * math.cos(b), math.cos(a) * math.sin(b), math.sin(a)


def satellite_at(orbit, phase_deg, minute):
    """Two-body position (unit vector, radius) at a minute, from raw orbit elements, as in the rule's stated assumptions."""
    rp, ra = RE + float(orbit["perig_km"]), RE + float(orbit["apog_km"])
    a, e = (rp + ra) / 2, (ra - rp) / (ra + rp)
    omega = float(orbit["perig_arg"] or 0.0)
    nu0 = math.radians(phase_deg - omega)
    e0 = 2 * math.atan2(math.sqrt(1 - e) * math.sin(nu0 / 2), math.sqrt(1 + e) * math.cos(nu0 / 2))
    mean = e0 - e * math.sin(e0) + math.sqrt(MU / a**3) * 60 * minute
    ecc = mean
    for _ in range(50):
        ecc -= (ecc - e * math.sin(ecc) - mean) / (1 - e * math.cos(ecc))
    nu = 2 * math.atan2(math.sqrt(1 + e) * math.sin(ecc / 2), math.sqrt(1 - e) * math.cos(ecc / 2))
    u = math.radians(omega) + nu
    node = float(orbit["long_asc"] if orbit["long_asc"] is not None else orbit["right_asc"])
    t = math.radians(node - EARTH_TURN_DEG_PER_MIN * minute)
    i = math.radians(float(orbit["inclin_ang"]))
    x = math.cos(t) * math.cos(u) - math.sin(t) * math.sin(u) * math.cos(i)
    y = math.sin(t) * math.cos(u) + math.cos(t) * math.sin(u) * math.cos(i)
    return (x, y, math.sin(u) * math.sin(i)), a * (1 - e * math.cos(ecc))


def check_station_margins(space, cases, xlsx, out):
    """Recomputes station margins from raw rows and the sheet's coordinates, not from the case's own geometry."""
    masks = load_masks()
    sheet = list(load_workbook(xlsx, read_only=True).worksheets[0].iter_rows(values_only=True))
    header = sheet[next(i for i, row in enumerate(sheet) if row and "RX frequency" in row)]
    out.append("\n## pfd at listed stations\n")
    pfd = [c for c in cases if c["rule_id"].startswith("pfd")]
    linked = [c for c in pfd if c["details"].get("station_ids")]
    out.append(f"{len(linked)} of {len(pfd)} pfd cases name a station. Coordinates from the sheet; power, gain, orbit and phase from raw rows.\n")
    worst_delta = 0.0
    for rule, basis in (("pfd-gso", "calculated_at_station"), ("pfd-ngso", "propagated_sample_at_station")):
        records = [(c, r) for c in linked if c["rule_id"].startswith(rule) for r in c["details"]["stations_overlapping"] if r.get("basis") == basis]
        for case, record in sorted(records, key=lambda x: -x[1]["margin_db"])[:2]:
            ntc, group = int(record["ntc_id"]), int(record["group_id"])
            mask = masks.by_id(record["mask_id"])
            usable = [r for r in space.emiss[group] if r["pwr_ds_max"] is not None and not (r["pep_max"] is not None and r["pwr_ds_max"] > r["pep_max"])]
            power = max(power_in_ref(r, mask.ref_bw_hz) for r in usable)
            beam = space.grp[group]["beam_name"]
            gain = max(float(b["gain"]) for b in space.beam(ntc, beam) if b["gain"] is not None)
            lat, lon = sheet_point(sheet, header, record["station_id"])
            px, py, pz = unit(lat, lon)
            if rule == "pfd-gso":
                longitude = float(space.geo[ntc]["long_nom"])
                cos_psi = math.cos(math.radians(lat)) * math.cos(math.radians(longitude - lon))
                distance = math.sqrt(RE**2 + RS**2 - 2 * RE * RS * cos_psi)
                angle = math.degrees(math.atan2(cos_psi - RE / RS, math.sqrt(1 - cos_psi**2)))
                where = f"GSO {longitude:g} E"
            else:
                orbit = next(o for o in space.orbit[ntc] if int(o["orb_id"]) == int(record["orb_id"]))
                phases = [p for p in space.phase if int(p["ntc_id"]) == ntc and int(p["orb_id"]) == int(record["orb_id"]) and p["phase_ang"] is not None]
                phase = float(min(phases, key=lambda p: int(p["orb_sat_id"]))["phase_ang"])
                (sx, sy, sz), radius = satellite_at(orbit, phase, int(record["minute"]))
                cos_psi = sx * px + sy * py + sz * pz
                distance = math.sqrt(radius**2 + RE**2 - 2 * radius * RE * cos_psi)
                angle = math.degrees(math.asin((radius * cos_psi - RE) / distance))
                where = f"orbit {record['orb_id']}, minute {record['minute']}"
            margin = power + gain - spread(distance) - mask.limit_db(angle)
            delta = margin - record["margin_db"]
            worst_delta = max(worst_delta, abs(delta))
            out.append(
                f"- {case['rule_id']} {case['network']} ntc {ntc} group {group}, station {record['station_id']} at {lat:.4f},{lon:.4f} "
                f"({where}): P {power:.2f} dBW, G {gain:g} dBi, d {distance:.1f} km, angle {angle:.3f} deg. "
                f"Hand margin {margin:+.4f}, reported {record['margin_db']:+.4f}, difference {delta:+.6f} dB."
            )
    out.append(f"\nLargest difference across the station sample: {worst_delta:.6f} dB.")
    above_grid = []
    for case in linked:
        for record in case["details"]["stations_overlapping"]:
            if record["status"] not in ("exceeds", "exceeds_flagged"):
                continue
            grid = [k for k in case["details"]["calculations"] if k["ntc_id"] == record["ntc_id"] and k["mask_id"] == record["mask_id"] and k["band"] == record["band"]]
            if not any(k["result"] == "exceeds" for k in grid):
                above_grid.append((case["network"], record["station_id"]))
    out.append(f"Station exceedances whose own calculation does not also exceed over Finland: {above_grid or 'none'}.")


def check_non_earth(space, cases, out):
    out.append("\n## Filings that do not orbit the Earth\n")
    tally = collections.Counter()
    names = collections.defaultdict(set)
    for case in cases:
        bodies = {space.ref_body.get(int(n)) for n in case["notice_ids"]} - {None, "T"}
        if bodies:
            tally[case["rule_id"]] += 1
            names[case["rule_id"]].add(f"{case['network']} ({','.join(sorted(bodies))})")
    out.append(f"Cases whose notices have `non_geo.ref_body` other than T: {dict(tally)}")
    for rule, values in sorted(names.items()):
        out.append(f"- {rule}: {', '.join(sorted(values))}")


def check_terrestrial(cases, sample, shared, out):
    out.append("\n## terrestrial rules\n")
    boundary = json.loads((MASK_DIR / "finland_boundary.json").read_text())["rings"]
    points = [(p[1], p[0]) for ring in boundary for p in ring[::4]]
    issue = TerrestrialIssue(MdbReader(shared / "brific3076.mdb"))
    settings = get_settings()
    kept = {str(i.notice.terrakey) for i in filter_near_finland(issue.notices, neighbour_adms=settings.neighbour_adms, distance_limits_km=settings.terrestrial_distance_limits_km)}
    neighbours = [n for n in issue.notices.values() if n.adm in settings.neighbour_adms and n.latitude_deg is not None]
    near = {}
    for notice in neighbours:
        near[str(notice.terrakey)] = min(haversine_km(notice.latitude_deg, notice.longitude_deg, *p) for p in points)
    within = {k for k, d in near.items() if d <= 300}
    in_cases = {str(n) for c in cases for n in c["notice_ids"]}
    out.append(f"Sweep: {len(neighbours)} positioned notices from the five neighbours, of which {len(within)} are within 300 km of the Natural Earth boundary ; {len(kept)} pass the filter; {len(in_cases)} are in cases.")
    dropped = sorted((round(near[k], 1), k) for k in within - kept)
    out.append(f"- Within 300 km on Natural Earth but dropped by the filter (possible misses): {dropped}")
    out.append(f"- Kept by the filter but over 300 km on Natural Earth: {sorted((k, round(near[k], 1)) for k in kept - within)}")
    calculated = [c for c in cases if c["rule_id"] == "terrestrial-p1546"]
    bad = []
    for case in calculated:
        d = case["details"]
        inputs = d["calc_inputs"]
        length = sum(s["length_km"] for s in inputs["segments"])
        free_space = 106.9 - 20 * math.log10(length) + 10 * math.log10(inputs["erp_kw"])
        if d["value_db"] > free_space + 0.01:
            bad.append((case["notice_ids"][0], d["value_db"], round(free_space, 2)))
    out.append(f"- {len(calculated)} calculated cases against the free-space ceiling 106.9 - 20 log d + 10 log P(kW): above it: {bad}.")
    for case in sample.sample(calculated, min(3, len(calculated))):
        d = case["details"]
        notice = issue.notices[str(case["notice_ids"][0])]
        point = d["worst_point"]
        hand = haversine_km(notice.latitude_deg, notice.longitude_deg, point["lat"], point["lon"])
        path = sum(s["length_km"] for s in d["calc_inputs"]["segments"])
        out.append(
            f"- {case['title'][:95]}: raw {notice.latitude_deg:.4f},{notice.longitude_deg:.4f}, {notice.frequency_mhz:g} MHz; path in case {path:.2f} km, hand distance "
            f"{hand:.2f} km; value {d['value_db']:.2f}, threshold {d.get('limit_db')}."
        )
    for case in [c for c in cases if c["rule_id"] == "terrestrial-not-calculated"][:3]:
        out.append(f"- not calculated: {case['title'][:120]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared", type=Path, required=True)
    parser.add_argument("--outputs", type=Path, required=True)
    parser.add_argument("--xlsx", type=Path, default=Path("docs/challenge/Traficom_SinceAI_Frequencies_of_interest_v05112026.xlsx"))
    args = parser.parse_args()
    sample = random.Random(SEED)
    out = ["# Hand check of exported cases", "", f"Generated by `tools/hand_check.py`, seed {SEED}."]
    space_cases = load_cases(args.outputs / "ific_3074" / "cases.json")
    space = Space(args.shared / "ific3074.mdb")
    check_finland_named(space, space_cases, out)
    check_m4(space, space_cases, sample, out)
    check_stations(space, space_cases, sample, args.xlsx, out)
    check_pfd(space, space_cases, sample, out)
    check_station_margins(space, space_cases, args.xlsx, out)
    check_non_earth(space, space_cases, out)
    check_terrestrial(load_cases(args.outputs / "ific_3076" / "cases.json"), sample, args.shared, out)
    print("\n".join(out))


if __name__ == "__main__":
    main()
