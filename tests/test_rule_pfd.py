"""PFD rule joins and a hand calculation from a real IFIC filing."""
from pathlib import Path

import pytest

from ific_guard.config import get_settings
import math

from ific_guard.screening.rule_pfd import PfdRule
from ific_guard.screening.space import MdbReader, SpaceIssue
from tests.test_screening import FakeReader, freq, notice


def test_missing_power_and_gain_are_reported():
    reader = FakeReader(
        notice=[notice(1)],
        geo=[{"ntc_id": 1, "long_nom": 25.0}],
        freq=[freq(1, 8025, 8040)],
        grp=[{"grp_id": 1, "ntc_id": 1, "beam_name": "1", "emi_rcp": "E"}],
        emiss=[{"grp_id": 1, "pwr_ds_max": None}],
        s_beam=[{"ntc_id": 1, "emi_rcp": "E", "beam_name": "1", "gain": None}],
    )
    hits = list(PfdRule(get_settings()).run(SpaceIssue(reader)))
    assert hits and hits[0].details["method"] == "screening"
    assert hits[0].details["missing"][0]["missing"] == ["pwr_ds_max", "gain"]


def test_rule_uses_maximum_joined_power_and_gain_and_is_repeatable():
    reader = FakeReader(
        notice=[notice(1)],
        geo=[{"ntc_id": 1, "long_nom": 25.0}],
        freq=[freq(1, 8025, 8040, grp=1)],
        grp=[{"grp_id": 1, "ntc_id": 1, "beam_name": "1", "emi_rcp": "E"}],
        emiss=[{"grp_id": 1, "pwr_ds_max": -50}, {"grp_id": 1, "pwr_ds_max": -40}],
        s_beam=[
            {"ntc_id": 1, "emi_rcp": "E", "beam_name": "1", "gain": 20},
            {"ntc_id": 1, "emi_rcp": "E", "beam_name": "1", "gain": 30},
        ],
    )
    rule = PfdRule(get_settings())
    first, second = list(rule.run(SpaceIssue(reader))), list(rule.run(SpaceIssue(reader)))
    assert first[0].details == second[0].details
    calculated = [c for c in first[0].details["calculations"] if c["mask_id"] == "art21-8025-8500"]
    assert calculated and calculated[0]["calc_inputs"]["p_density_dbw_hz"] == -40
    assert calculated[0]["calc_inputs"]["gain_dbi"] == 30


def test_uncomputed_hit_is_not_presented_as_within_limit():
    reader = FakeReader(
        notice=[notice(1, ntc_type="N")],
        freq=[freq(1, 17700, 17800)],
        orbit=[],
    )
    hit = next(PfdRule(get_settings()).run(SpaceIssue(reader)))
    assert hit.details["method"] == "screening"
    assert hit.details["expert_review"] is True
    assert "not evaluated" in hit.title
    assert "within" not in hit.title


def test_eccentric_ngso_uses_the_smallest_perigee_as_a_conservative_bound():
    reader = FakeReader(
        notice=[notice(1, ntc_type="N")],
        freq=[freq(1, 17700, 17800)],
        grp=[{"grp_id": 1, "ntc_id": 1, "beam_name": "1", "emi_rcp": "E"}],
        emiss=[{"grp_id": 1, "pwr_ds_max": -50}],
        s_beam=[{"ntc_id": 1, "emi_rcp": "E", "beam_name": "1", "gain": 30}],
        orbit=[
            {"ntc_id": 1, "apog_km": 40000, "perig_km": 500, "inclin_ang": 70},
            {"ntc_id": 1, "apog_km": 30000, "perig_km": 800, "inclin_ang": 60},
        ],
    )
    hits = list(PfdRule(get_settings()).run(SpaceIssue(reader)))
    calc = next(c for hit in hits for c in hit.details["calculations"])
    assert calc["method"] == "pfd_ngso"
    assert calc["calc_inputs"]["perigee_bound_km"] == 500
    assert calc["calc_inputs"]["orbit_rows_considered"] == 2
    assert any("perigee" in a for a in calc["assumptions"])
    assert "pfd-ngso-art21" == hits[0].rule_id


@pytest.mark.skipif(not Path("/Users/mehrshad/personal/radio/data/shared/ific3074.mdb").exists(), reason="shared filing unavailable")
def test_real_3074_row_matches_hand_pfd_calculation():
    issue = SpaceIssue(MdbReader("/Users/mehrshad/personal/radio/data/shared/ific3074.mdb"))
    rule = PfdRule(get_settings())
    hits = list(rule.run(issue))
    calculated = next(
        c for hit in hits for c in hit.details["calculations"]
        if c["method"] == "pfd_gso" and c["calc_inputs"]["group_id"] == 124711730
    )
    # These are read directly from the 3074 source rows, not from rule output.
    notice_row = next(r for r in issue._reader.table("geo") if r["ntc_id"] == 124520179)
    freq_row = next(r for r in issue._reader.table("freq") if r["grp_id"] == 124711730)
    emiss_row = next(r for r in issue._reader.table("emiss") if r["grp_id"] == 124711730)
    beam_row = next(r for r in issue._reader.table("s_beam") if r["ntc_id"] == 124520179 and r["beam_name"] == "TB2")
    assert notice_row["long_nom"] == -52.5
    assert (freq_row["freq_min"], freq_row["freq_max"]) == (17670.0, 17710.0)
    assert emiss_row["pwr_ds_max"] == pytest.approx(-48.599998474121094)
    assert beam_row["gain"] == 44.0
    point = calculated["worst_point"]
    lat, lon, sat_lon = point["lat"], point["lon"], notice_row["long_nom"]
    re, rs = 6378.0, 42164.0
    cos_psi = math.cos(math.radians(lat)) * math.cos(math.radians(sat_lon - lon))
    distance = math.sqrt(re**2 + rs**2 - 2 * re * rs * cos_psi)
    hand = emiss_row["pwr_ds_max"] + 10 * math.log10(1_000_000) + beam_row["gain"] - 10 * math.log10(4 * math.pi * (distance * 1000) ** 2)
    assert hand == pytest.approx(calculated["value_db"], abs=1e-9)
