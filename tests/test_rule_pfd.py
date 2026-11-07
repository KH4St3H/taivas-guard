"""PFD rule joins and a hand calculation from a real IFIC filing."""
from pathlib import Path

import pytest

from ific_guard.config import get_settings
from ific_guard.engines.pfd import GroundPoint, load_masks, pfd_db
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


@pytest.mark.skipif(not Path("/Users/mehrshad/personal/radio/data/shared/ific3074.mdb").exists(), reason="shared filing unavailable")
def test_real_3074_row_matches_hand_pfd_calculation():
    issue = SpaceIssue(MdbReader("/Users/mehrshad/personal/radio/data/shared/ific3074.mdb"))
    rule = PfdRule(get_settings())
    hits = list(rule.run(issue))
    calculated = next(
        c for hit in hits for c in hit.details["calculations"]
        if c["mask_id"].startswith("art21-") and c["method"] == "pfd_gso"
    )
    inputs = calculated["calc_inputs"]
    point = GroundPoint(calculated["worst_point"]["lat"], calculated["worst_point"]["lon"])
    mask = load_masks().by_id(calculated["mask_id"])
    from ific_guard.engines.pfd import gso_geometry
    geometry = gso_geometry(point.lat_deg, point.lon_deg, inputs["gso_lon_deg"])
    assert geometry is not None
    hand = pfd_db(inputs["p_density_dbw_hz"], mask.ref_bw_hz, inputs["gain_dbi"], geometry.distance_km)
    assert hand == pytest.approx(calculated["value_db"], abs=1e-9)
