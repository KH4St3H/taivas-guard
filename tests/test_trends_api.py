"""Ticket 30: trends across stored issues, for the Trends page."""
from fastapi.testclient import TestClient

from ific_guard.db import session_scope
from ific_guard.models import Artifact, IssueSummary
from ific_guard.screening import trends as tr
from ific_guard.screening.app import app
from ific_guard.screening.space import SpaceIssue
from tests.test_screening import FakeReader, freq, notice


def _issue():
    return SpaceIssue(FakeReader(
        notice=[notice(1, adm="USA"), notice(2, adm="CHN", ntc_type="N"), notice(3, adm="USA", reason="C")],
        geo=[dict(ntc_id=1, sat_name="GEO-1", long_nom=25.0), dict(ntc_id=3, sat_name="FAR", long_nom=-120.0)],
        non_geo=[dict(ntc_id=2, sat_name="SWARM", ref_body="T")],
        orbit=[dict(ntc_id=2, orb_id=1, inclin_ang=97.0, nbr_sat_pl=600), dict(ntc_id=2, orb_id=2, inclin_ang=53.0, nbr_sat_pl=400)],
        freq=[freq(1, 11_700, 11_800), freq(1, 3_500, 3_600), freq(2, 2_200, 2_210), freq(2, 29_000, 29_100, emi="R"), freq(3, 12_000, 12_050)],
    ))


def test_space_summary_counts_each_filing_once():
    s = tr.summarise_space(_issue())
    assert s["filings"] == 3 and s["visible_from_finland"] == 2  # FAR at 120 W is outside the arc
    assert s["by_adm"] == {"USA": 2, "CHN": 1}
    assert s["by_orbit"] == {"GSO": 2, "Non-GSO": 1}
    # Bands come from space-to-Earth assignments only: the 29 GHz uplink doesn't count.
    assert s["by_band"] == {"Ku, 12-18 GHz": 1, "X, 8-12 GHz": 1, "S, 2-4 GHz": 2}
    assert s["largest_ngso"] == [{"ntc_id": 2, "network": "SWARM", "adm": "CHN", "satellites": 1000, "reason": "CR/C (9.6)"}]


def test_a_network_published_as_two_notices_is_listed_once():
    issue = _issue()
    twin = {**issue.notices[2].__dict__, "ntc_id": 32}
    issue.notices[32] = type(issue.notices[2])(**{**twin, "assignments": []})
    issue.orbits[32] = [dict(ntc_id=32, orb_id=1, inclin_ang=97.0, nbr_sat_pl=600)]
    assert [s["network"] for s in tr.summarise_space(issue)["largest_ngso"]] == ["SWARM"]


def test_jump_rule_needs_both_a_doubling_and_a_minimum():
    issues = [1, 2, 3]
    series = {"steady": {1: 10, 2: 10, 3: 12}, "jump": {1: 2, 2: 4, 3: 9}, "tiny": {1: 1, 2: 1, 3: 4}}
    assert [f["name"] for f in tr.jumps(series, issues)] == ["jump"]
    assert tr.jumps(series, [3]) == []


def _artifact(issue_no, status="done"):
    with session_scope() as s:
        a = Artifact(domain="space", issue_no=issue_no, source_url="u", sha256=f"{issue_no:064d}", size_bytes=1,
                     mdb_path=f"/nowhere/{issue_no}.mdb", screen_status=status)
        s.add(a)
        s.flush()
        return a.id


def test_endpoint_merges_stored_summaries_and_fills_in_missing_ones(monkeypatch):
    for no, usa in ((3081, 2), (3082, 2), (3083, 9)):
        tr.store(_artifact(no), "space", no, {**tr.summarise_space(_issue()), "by_adm": {"USA": usa}})
    missing = _artifact(3080)
    _artifact(3084, status="pending")  # not screened yet: left out
    monkeypatch.setattr(tr, "_load", lambda *_: _issue())
    out = TestClient(app).get("/trends", params={"domain": "space"}).json()
    assert out["issues"] == [3080, 3081, 3082, 3083]
    assert out["series"]["by_adm"]["USA"] == {"3080": 2, "3081": 2, "3082": 2, "3083": 9}
    assert [f["name"] for f in out["flags"]["by_adm"]] == ["USA"]
    assert out["largest_ngso"]["3083"][0]["satellites"] == 1000 and out["problems"] == []
    with session_scope() as s:
        assert s.get(IssueSummary, missing).version == tr.SUMMARY_VERSION  # computed once, then stored


def test_an_unreadable_issue_is_reported_not_fatal(monkeypatch):
    tr.store(_artifact(3082), "space", 3082, tr.summarise_space(_issue()))
    _artifact(3083)
    monkeypatch.setattr(tr, "_load", lambda *_: (_ for _ in ()).throw(FileNotFoundError("file gone")))
    out = TestClient(app).get("/trends").json()
    assert out["issues"] == [3082] and out["problems"] == ["IFIC 3083: file gone"]
