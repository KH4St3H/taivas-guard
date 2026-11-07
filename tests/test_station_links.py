"""Ticket 19: pfd results at special-interest stations, and station cases ranked by that evidence.

Expected GSO numbers come from the closed forms, worked separately from the rule:
  cos psi = cos(lat) cos(dlon);  d = sqrt(Re^2 + Rs^2 - 2 Re Rs cos psi);  angle = atan2(cos psi - Re/Rs, sin psi)
  pfd     = min(P + 10 log10(B_ref), pep) + G - 10 log10(4 pi (1000 d)^2)
"""
import math
from dataclasses import replace

import pytest

from ific_guard.config import get_settings
from ific_guard.engines.pfd import load_masks
from ific_guard.screening.m4 import load_m4_rows
from ific_guard.screening.rule_pfd import PfdRule
from ific_guard.screening.rule_stations import StationOverlapRule
from ific_guard.screening.space import SpaceIssue
from ific_guard.screening.station_links import severity_of
from ific_guard.screening.stations import OUTSIDE_FINLAND, SITE_NOT_RECEIVER
from tests.test_rule_pfd import gso_reader, ngso_reader
from tests.test_stations import station

RE, RS = 6378.0, 42164.0
POLAR = {"perig_km": 1000, "apog_km": 1000, "inclin_ang": 90, "perig_arg": 0, "long_asc": 25.0}
PHASE = [{"ntc_id": 1, "orb_id": 1, "orb_sat_id": 1, "phase_ang": 65.0}]


def at(row, lat, lon, **kw):
    return replace(station(row=row, **kw), lat_deg=lat, lon_deg=lon)


def both(reader, stations):
    """The pfd hits and the station hits for one issue, with the station rule reading the pfd rule."""
    settings = get_settings()
    pfd = PfdRule(settings, stations)
    issue = SpaceIssue(reader)
    station_rule = StationOverlapRule(settings, stations, pfd=pfd, m4_rows=load_m4_rows(settings.m4_filter_path))
    return list(pfd.run(issue)), list(station_rule.run(issue))


def records(hit):
    return {r["station_id"]: r for r in hit.details["stations_overlapping"]}


def gso_margin(lat, lon, gso_lon, power, pep, gain, mask):
    cos_psi = math.cos(math.radians(lat)) * math.cos(math.radians(gso_lon - lon))
    d = math.sqrt(RE**2 + RS**2 - 2 * RE * RS * cos_psi)
    angle = math.degrees(math.atan2(cos_psi - RE / RS, math.sqrt(1 - cos_psi**2)))
    pfd = min(power + 10 * math.log10(mask.ref_bw_hz), pep) + gain - 10 * math.log10(4 * math.pi * (1000 * d) ** 2)
    return pfd - mask.limit_db(angle), angle


def test_gso_value_at_a_station_is_calculated_at_its_coordinates():
    rx = at(100, 62.0, 25.0, rx=8030.0, bw=5.0)
    pfd_hits, station_hits = both(gso_reader(lon=25.0), [rx])
    hit = next(h for h in pfd_hits if h.rule_id == "pfd-gso-art21")
    record = records(hit)["1000@R100"]
    mask = load_masks().by_id(record["mask_id"])
    margin, angle = gso_margin(62.0, 25.0, 25.0, -60.0, 20.0, 30.0, mask)
    assert record["basis"] == "calculated_at_station"
    assert record["margin_db"] == pytest.approx(margin, abs=1e-9) and record["angle_deg"] == pytest.approx(angle, abs=1e-9)
    assert hit.details["station_ids"] == ["1000@R100"] and hit.details["special_interest"] is True
    assert any("special-interest" in reason for reason in hit.details["severity_reasons"])
    assert "1 listed station in band" in hit.title
    # The grid's worst point over Finland is at least as bad as any station inside it.
    assert hit.details["margin_db"] >= record["margin_db"]
    assert station_hits[0].details["stations_overlapping"][0]["margin_db"] == pytest.approx(margin, abs=1e-9)


def test_rx_and_tx_matches_say_where_the_margin_applies():
    rx = at(100, 62.0, 25.0, rx=8030.0, bw=5.0)
    tx = at(101, 63.0, 26.0, rx=9000.0, tx_mhz=8030.0, bw=5.0)
    pfd_hits, _ = both(gso_reader(lon=25.0), [rx, tx])
    found = records(next(h for h in pfd_hits if h.rule_id == "pfd-gso-art21"))
    assert [b["side"] for b in found["1000@R100"]["matched_bands"]] == ["rx"] and "field_location" not in found["1000@R100"]
    assert [b["side"] for b in found["1010@R101"]["matched_bands"]] == ["tx"]
    assert found["1010@R101"]["field_location"] == SITE_NOT_RECEIVER


def test_a_station_that_cannot_see_a_gso_satellite_is_a_computed_result():
    # GSO at 96 E: south-east Finland sees it, a station at 69 N 21 E does not (cos 69 cos 75 < Re/Rs).
    hidden = at(100, 69.0, 21.0, rx=8030.0, bw=5.0)
    pfd_hits, station_hits = both(gso_reader(lon=96.0), [hidden])
    hit = next(h for h in pfd_hits if h.rule_id == "pfd-gso-art21")
    assert hit.details["margin_db"] is not None  # Finland as a whole sees it
    assert hit.details["stations_not_visible"] == ["1000@R100"] and hit.details["station_ids"] == []
    assert hit.details["special_interest"] is False
    case = station_hits[0]
    assert case.details["evidence_status"] == "not_visible" and case.severity == "low"
    assert case.details["stations_not_visible"] == ["1000@R100"] and case.details["station_ids"] == []
    assert "below the horizon of every listed station" in case.title


def test_only_the_part_of_a_band_a_mask_covers_is_calculated():
    # 8000-8040 MHz: the masks start at 8025, so a station at 8010 has no calculation behind it.
    inside, outside = at(100, 62.0, 25.0, rx=8030.0, bw=5.0), at(101, 62.0, 25.0, rx=8010.0, bw=5.0)
    pfd_hits, station_hits = both(gso_reader(lon=25.0, low=8000, high=8040), [inside, outside])
    assert set(records(next(h for h in pfd_hits if h.rule_id == "pfd-gso-art21"))) == {"1000@R100"}
    by_station = records(station_hits[0])
    assert by_station["1010@R101"]["status"] == "no_calculation"
    assert by_station["1000@R100"]["basis"] == "calculated_at_station"


def test_station_case_severity_follows_the_evidence():
    near = at(100, 62.0, 25.0, rx=8030.0, bw=5.0)
    _, loud = both(gso_reader(lon=25.0, power=-20.0, pep=60.0), [near])
    _, quiet = both(gso_reader(lon=25.0, power=-120.0, pep=-40.0), [near])
    assert loud[0].details["evidence_status"] == "exceeds" and loud[0].severity == "high"
    assert loud[0].details["method"] == "pfd_gso" and loud[0].details["margin_basis"] == "gso_station"
    assert loud[0].details["worst_point"]["station_id"] == "1000@R100"
    assert "pfd exceeds the limit at 1 listed station under worst-case assumptions" in loud[0].title
    assert quiet[0].details["evidence_status"] == "below" and quiet[0].severity == "low"


def test_a_flagged_location_cannot_make_a_station_case_high():
    odd = replace(at(100, 62.0, 25.0, rx=8030.0, bw=5.0), quality_flags=(OUTSIDE_FINLAND,))
    _, hits = both(gso_reader(lon=25.0, power=-20.0, pep=60.0), [odd])
    assert hits[0].details["evidence_status"] == "exceeds_flagged" and hits[0].severity == "medium"
    assert hits[0].details["stations_overlapping"][0]["location_flagged"] is True


def test_non_gso_value_at_a_station_is_a_sample_from_the_same_flight():
    under = at(100, 65.0, 25.0, rx=8030.0, bw=5.0)
    pfd_hits, station_hits = both(ngso_reader([POLAR], phase=PHASE), [under])
    hit = next(h for h in pfd_hits if h.rule_id == "pfd-ngso-art21")
    record = records(hit)["1000@R100"]
    calc = hit.details["calculations"][0]
    assert record["basis"] == "propagated_sample_at_station" and record["status"] == "exceeds"
    assert {"minute", "angle_deg", "distance_km", "altitude_km", "orb_id"} <= set(record)
    assert 0 < record["margin_db"] <= calc["envelope"]["margin_db"] + 1e-9
    assert record["filing_upper_bound"] == {"margin_db": calc["envelope"]["margin_db"], "applies_to": "the filing, not this station"}
    assert station_hits[0].severity == "high" and station_hits[0].details["margin_basis"] == "propagated_station"


def test_an_upper_bound_stays_a_bound_at_a_station():
    station_ = at(100, 62.0, 25.0, rx=8030.0, bw=5.0)
    pfd_hits, station_hits = both(ngso_reader([{"perig_km": 500, "apog_km": 40000, "inclin_ang": 70}]), [station_])
    record = records(next(h for h in pfd_hits if h.rule_id == "pfd-ngso-art21"))["1000@R100"]
    assert record["status"] == "bound_above" and record["basis"] == "no_sample_at_station"
    assert not {"value_db", "limit_db", "margin_db"} & set(record)
    case = station_hits[0]
    assert case.severity == "medium" and case.details["method"] == "screening" and "margin_db" not in case.details
    assert "only the filing's upper bound is near or above the limit" in case.title and "exceeds" not in case.title


def test_station_bands_carry_the_m4_allocation():
    _, hits = both(gso_reader(lon=25.0), [at(100, 62.0, 25.0, rx=8030.0, bw=5.0)])
    band = hits[0].details["bands"][0]
    assert band["m4_space_to_earth"] in {"allocated", "partly allocated", "not allocated"}
    assert band["m4_primary_services"] and band["m4_table_pages"]


def test_the_station_rule_reuses_the_pfd_rules_calculation():
    settings = get_settings()
    stations = [at(100, 62.0, 25.0, rx=8030.0, bw=5.0)]
    pfd = PfdRule(settings, stations)
    issue = SpaceIssue(gso_reader(lon=25.0))
    list(StationOverlapRule(settings, stations, pfd=pfd).run(issue))
    evidence = pfd.station_evidence(issue)
    assert pfd.run(issue) is pfd.run(issue) and pfd.station_evidence(issue) is evidence


@pytest.mark.parametrize("status, severity", [
    ("exceeds", "high"), ("exceeds_flagged", "medium"), ("within_3db", "medium"), ("bound_above", "medium"),
    ("no_calculation", "medium"), ("below", "low"), ("bound_below", "low"), ("not_visible", "low"),
])
def test_severity_of_each_status(status, severity):
    assert severity_of(status) == severity


def _draft_of(hit):
    from ific_guard.llm import draft
    from tests.test_llm import make_case

    return draft(make_case(hit.rule_id, **hit.details)).letter


def test_station_draft_quotes_values_at_stations_and_not_a_missing_allocation():
    _, hits = both(gso_reader(lon=25.0, power=-20.0, pep=60.0), [at(100, 62.0, 25.0, rx=8030.0, bw=5.0)])
    letter = _draft_of(hits[0])
    margin = round(hits[0].details["stations_overlapping"][0]["margin_db"], 2)
    assert "Station 1000@R100 (RX): calculated above the limit" in letter and f"margin {margin} dB" in letter
    assert "receive or transmit frequencies of Finnish stations" in letter
    assert "gives no space-to-Earth allocation" not in letter


def test_station_draft_with_only_a_bound_makes_no_finding():
    _, hits = both(ngso_reader([{"perig_km": 500, "apog_km": 40000, "inclin_ang": 70}]), [at(100, 62.0, 25.0, rx=8030.0, bw=5.0)])
    letter = _draft_of(hits[0])
    assert "No power flux-density value has been calculated at any of these stations" in letter
    assert "exceeds the limit" not in letter
