"""The finding map: reach, worst-case pfd and listed stations, checked against closed forms."""
import math

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ific_guard.config import get_settings
from ific_guard.db import session_scope
from ific_guard.models import Artifact, Case
from ific_guard.screening import coverage
from ific_guard.screening.app import app
from ific_guard.screening.engine import save_hits
from ific_guard.screening.m4 import load_m4_conflict_bands
from ific_guard.screening.rules import M4NoDownlinkRule
from ific_guard.screening.space import SpaceIssue
from tests.test_rule_pfd import gso_reader, ngso_reader
from tests.test_stations import station

RE, RS = 6378.0, 42164.0


def gso_by_hand(lat, lon, sat_lon):
    cos_psi = math.cos(math.radians(lat)) * math.cos(math.radians(sat_lon - lon))
    d = math.sqrt(RE**2 + RS**2 - 2 * RE * RS * cos_psi)
    angle = math.degrees(math.atan2(cos_psi - RE / RS, math.sqrt(1 - cos_psi**2)))
    return d, angle


def spread(d_km):
    return 10 * math.log10(4 * math.pi * (1000 * d_km) ** 2)


def map_for(tmp_path, monkeypatch, reader, stations=()):
    issue = SpaceIssue(reader)
    path = tmp_path / "3083.mdb"
    path.write_bytes(b"test")
    with session_scope() as s:
        artifact = Artifact(domain="space", issue_no=3083, source_url="u", sha256="a" * 64, size_bytes=4, mdb_path=str(path))
        s.add(artifact)
        s.flush()
        artifact_id = artifact.id
    settings = get_settings()
    save_hits(artifact_id, list(M4NoDownlinkRule(settings, load_m4_conflict_bands(settings.m4_filter_path)).run(issue)))
    coverage._compute.cache_clear()
    monkeypatch.setattr(coverage, "load_issue", lambda *_: issue)
    monkeypatch.setattr(coverage, "load_stations_cached", lambda *_: list(stations))
    with session_scope() as s:
        case_id = s.scalars(select(Case.id)).one()
    return TestClient(app).get(f"/cases/{case_id}/coverage").json()


def test_gso_reach_and_pfd_match_the_closed_forms(tmp_path, monkeypatch):
    # 3480-3520 MHz has no space-to-Earth allocation in M4; RR Table 21-4 has a GSO limit there with 4 kHz.
    out = map_for(tmp_path, monkeypatch, gso_reader(lon=25.0, low=3480, high=3520, power=-60.0, pep=20.0))
    assert out["mapped"] and out["orbit"] == "gso" and out["gso_lon_deg"] == 25.0
    assert out["pfd"]["available"] and out["pfd"]["ref_bw_hz"] == 4000.0 and out["pfd"]["mask_id"]
    assert all(c["angle_deg"] is not None for c in out["cells"])  # 25 E is above the horizon all over Finland
    north = max(out["cells"], key=lambda c: c["lat"])
    d, angle = gso_by_hand(north["lat"], north["lon"], 25.0)
    assert north["angle_deg"] == pytest.approx(angle, abs=0.06)
    # P -60 dBW/Hz in 4 kHz is -23.98 dBW, under the 20 dBW peak; gain 30 dBi.
    assert north["pfd_db"] == pytest.approx(-60 + 10 * math.log10(4000) + 30 - spread(d), abs=0.06)
    assert north["margin_db"] is not None
    south = min(out["cells"], key=lambda c: c["lat"])
    assert south["angle_deg"] > north["angle_deg"] and south["pfd_db"] > north["pfd_db"]


def test_a_gso_low_over_the_horizon_reaches_only_part_of_finland(tmp_path, monkeypatch):
    # At 60 W (inside the configured visible arc's west end or not), Finland's east is past the horizon.
    out = map_for(tmp_path, monkeypatch, gso_reader(lon=-40.0, low=3480, high=3520))
    angles = [c["angle_deg"] for c in out["cells"]]
    assert any(a is None for a in angles) or min(a for a in angles if a is not None) < 5


def test_ngso_flight_gives_minutes_and_highest_angle(tmp_path, monkeypatch):
    orbit = {"perig_km": 1000, "apog_km": 1000, "inclin_ang": 90, "perig_arg": 0, "long_asc": 25.0}
    reader = ngso_reader([orbit], low=3480, high=3520, phase=[{"ntc_id": 1, "orb_id": 1, "orb_sat_id": 1, "phase_ang": 65.0}])
    out = map_for(tmp_path, monkeypatch, reader)
    assert out["orbit"] == "ngso"
    seen = [c for c in out["cells"] if c["minutes"]]
    assert seen and all(0 < c["angle_deg"] <= 90 for c in seen)
    overhead = min(seen, key=lambda c: abs(c["lat"] - 65) + abs(c["lon"] - 25))
    assert overhead["angle_deg"] > 80  # at minute 0 it is straight above 65 N, 25 E


def test_listed_stations_in_the_bands_are_drawn(tmp_path, monkeypatch):
    stations = [station(row=1, rx=3500.0, bw=1.0), station(row=2, rx=3500.0, bw=1.0, cls="MVV"), station(row=3, rx=100.0)]
    out = map_for(tmp_path, monkeypatch, gso_reader(low=3480, high=3520), stations)
    assert out["stations"]["total"] == 2 and out["stations"]["by_class"] == {"FX": 1, "MVV": 1}
    assert {p["id"] for p in out["stations"]["points"]} == {"10@R1", "20@R2"}


def test_without_power_or_gain_the_pfd_layer_says_why(tmp_path, monkeypatch):
    reader = gso_reader(low=3480, high=3520)
    reader.tables["s_beam"] = []
    out = map_for(tmp_path, monkeypatch, reader)
    assert out["pfd"] == {"available": False, "reason": "No transmission in these bands notifies both power density and antenna gain (no antenna gain: 1)."}
    assert all(c["pfd_db"] is None for c in out["cells"]) and all(c["angle_deg"] is not None for c in out["cells"])


def test_an_orbit_that_cannot_be_flown_is_unknown_not_out_of_view(tmp_path, monkeypatch):
    out = map_for(tmp_path, monkeypatch, ngso_reader([{"perig_km": 600, "apog_km": 600, "inclin_ang": 97}], low=3480, high=3520))
    assert out["mapped"] is False and "where it passes over Finland is unknown" in out["notes"][0]
