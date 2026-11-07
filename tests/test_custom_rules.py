import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from ific_guard.config import get_settings
from ific_guard.db import session_scope
from ific_guard.llm.template import CaseView, explain_case
from ific_guard.models import Artifact, Case, Event
from ific_guard.screening.app import app
from ific_guard.screening.custom_rules import DeclarativeRule, RuleDefinition, RuleSpec, describe
from ific_guard.screening.engine import save_hits
from ific_guard.screening.m4 import load_m4_rows
from ific_guard.screening.space import SpaceIssue
from tests.test_screening import FakeReader, freq, notice

KEY = {"X-API-Key": "test-key"}


def issue(*assignments, adm="USA", ntc_type="G", lon=25.0):
    return SpaceIssue(FakeReader(
        notice=[notice(1, adm=adm, ntc_type=ntc_type)],
        geo=[dict(ntc_id=1, sat_name="SAT", long_nom=lon)] if ntc_type == "G" else [],
        non_geo=[dict(ntc_id=1, sat_name="SAT", ref_body="T")] if ntc_type == "N" else [],
        freq=list(assignments),
    ))


def run(spec_or_definition, space_issue):
    spec = spec_or_definition if isinstance(spec_or_definition, RuleSpec) else RuleSpec(
        name="Test", severity="medium", definition=spec_or_definition)
    settings = get_settings()
    return list(DeclarativeRule(settings, 7, 3, spec, load_m4_rows(settings.m4_filter_path)).run(space_issue))


def test_transmit_rule_with_an_m4_condition_matches_the_band_and_names_its_version():
    hits = run(RuleDefinition(m4={"space_to_earth": "no", "primary_services_any": ["MOBILE AND FIXED"]}),
               issue(freq(1, 3480, 3520)))
    assert len(hits) == 1
    hit = hits[0]
    assert hit.rule_id == "custom-7" and hit.severity == "medium"
    assert hit.title == "SAT (USA) matches Test"
    assert [(b["low_mhz"], b["high_mhz"]) for b in hit.details["bands"]] == [(3400, 3800)]
    assert hit.details["custom_rule"] == {"id": 7, "name": "Test", "version": 3}
    assert hit.details["matched_assignments"] == [{"group_id": 1, "freq_min_mhz": 3480.0, "freq_max_mhz": 3520.0, "direction": "transmit"}]


def test_direction_decides_which_assignments_count():
    uplink = issue(freq(1, 14100, 14200, emi="R"))
    assert run(RuleDefinition(), uplink) == []  # transmit is the default
    hits = run(RuleDefinition(direction="receive", m4={"earth_to_space": "yes"}), uplink)
    assert [b["m4_primary_services"] for b in hits[0].details["bands"]] == ["FIXED SATELLITE (EARTH-TO-SPACE)"]
    assert run(RuleDefinition(direction="either", m4={"earth_to_space": "no"}), uplink) == []


def test_frequency_ranges_clip_the_assignment_before_m4_is_checked():
    wide = issue(freq(1, 3700, 3900))
    assert run(RuleDefinition(frequency_ranges=[{"low_mhz": 3850, "high_mhz": 3950}], m4={"space_to_earth": "no"}), wide) == []
    bands = run(RuleDefinition(frequency_ranges=[{"low_mhz": 3850, "high_mhz": 3950}]), wide)[0].details["bands"]
    assert [(b["low_mhz"], b["high_mhz"]) for b in bands] == [(3800, 4200)]
    assert run(RuleDefinition(frequency_ranges=[{"low_mhz": 100, "high_mhz": 200}]), wide) == []


def test_filing_conditions():
    tx = freq(1, 3480, 3520)
    assert run(RuleDefinition(adm_in=["fra"]), issue(tx)) == []
    assert len(run(RuleDefinition(adm_in=["usa"]), issue(tx))) == 1
    assert run(RuleDefinition(adm_not_in=["USA"]), issue(tx)) == []
    assert run(RuleDefinition(orbit="ngso"), issue(tx)) == []
    assert run(RuleDefinition(provision_in=["9.1A"]), issue(tx)) == []
    assert run(RuleDefinition(), issue(tx, lon=-120)) == []  # outside the arc seen from Finland
    assert len(run(RuleDefinition(visible_from_finland=False), issue(tx, lon=-120))) == 1


def test_definitions_are_checked_before_they_are_saved():
    with pytest.raises(ValidationError, match="Unknown title field"):
        RuleSpec(name="x", severity="low", title_template="{network.__class__}")
    with pytest.raises(ValidationError, match="no formatting"):
        RuleSpec(name="x", severity="low", title_template="{bands:{network}}")
    with pytest.raises(ValidationError, match="end above"):
        RuleDefinition(frequency_ranges=[{"low_mhz": 20, "high_mhz": 10}])
    with pytest.raises(ValidationError, match="three letters"):
        RuleDefinition(adm_in=["UNITED"])
    with pytest.raises(ValidationError):
        RuleSpec(name="x", severity="critical")


@pytest.mark.parametrize("filter_visibility", [True, False])
def test_non_earth_filing_is_not_screened_even_without_the_visibility_filter(filter_visibility):
    lunar = SpaceIssue(FakeReader(
        notice=[notice(1, ntc_type="N")], non_geo=[dict(ntc_id=1, ref_body="L")],
        freq=[freq(1, 3480, 3520)],
    ))
    assert run(RuleDefinition(visible_from_finland=filter_visibility), lunar) == []


def test_conditions_read_as_sentences():
    words = describe(RuleDefinition(direction="receive", adm_in=["RUS"], m4={"terrestrial_primary": "yes", "space_to_earth": "no"}))
    assert words == [
        "The filing is for any satellite whose orbit can be seen from Finland",
        "Notified by RUS",
        "The satellite receives",
        "There, M4 gives no space-to-Earth allocation; primary terrestrial use",
    ]


def _artifact(tmp_path, issue_no=3083):
    path = tmp_path / f"{issue_no}.mdb"
    path.write_bytes(b"test")
    with session_scope() as s:
        a = Artifact(domain="space", issue_no=issue_no, source_url="u", sha256=str(issue_no)[0] * 64, size_bytes=4, mdb_path=str(path))
        s.add(a)
        s.flush()
        return a.id


BODY = {"name": "Uplinks near Finland", "severity": "low", "definition": {"direction": "receive"}, "saved_by": "Expert", "note": "First try"}


def test_rules_are_saved_as_versions_and_need_the_key():
    client = TestClient(app)
    assert client.post("/rules", json=BODY).status_code == 401
    created = client.post("/rules", json=BODY, headers=KEY).json()
    assert (created["rule_id"], created["version"], created["versions"][0]["saved_by"]) == (f"custom-{created['id']}", 1, "Expert")
    url = f"/rules/{created['id']}"
    assert client.put(url, json=BODY, headers=KEY).json()["version"] == 1  # nothing changed
    changed = client.put(url, json={**BODY, "severity": "high", "note": "Raise it"}, headers=KEY).json()
    assert changed["version"] == 2
    assert [(v["version"], v["severity"], v["note"]) for v in client.get(url).json()["versions"]] == [(2, "high", "Raise it"), (1, "low", "First try")]
    assert client.post("/rules", json={**BODY, "title_template": "{oops}"}, headers=KEY).status_code == 422
    assert "MOBILE AND FIXED" in client.get("/rules/options").json()["m4_primary_services"]


def test_preview_runs_a_draft_without_saving_anything(tmp_path, monkeypatch):
    artifact_id = _artifact(tmp_path)
    monkeypatch.setattr("ific_guard.screening.rules_api._issue", lambda *_: issue(freq(1, 3480, 3520)))
    client = TestClient(app)
    out = client.post("/rules/preview", json={"artifact_id": artifact_id, "spec": {"name": "Draft", "severity": "high"}}, headers=KEY).json()
    assert (out["issue_no"], out["total"], out["by_adm"]) == (3083, 1, {"USA": 1})
    assert out["hits"][0]["title"] == "SAT (USA) matches Draft"
    assert client.post("/rules/preview", json={"artifact_id": 999, "spec": {"name": "D", "severity": "low"}}, headers=KEY).status_code == 404
    with session_scope() as s:
        assert s.scalars(select(Case)).all() == []


def test_rescreen_queues_every_space_issue(tmp_path):
    ids = {_artifact(tmp_path, 3074), _artifact(tmp_path, 3083)}
    out = TestClient(app).post("/rules/rescreen", headers=KEY).json()
    assert out["issues"] == [3074, 3083]
    with session_scope() as s:
        queued = {e.payload["artifact_id"] for e in s.scalars(select(Event)) if e.payload.get("artifact_id") is not None}
        assert ids <= queued


def test_case_list_hides_cases_of_a_rule_switched_off_or_no_longer_raised(tmp_path):
    client = TestClient(app)
    rule = client.post("/rules", json=BODY, headers=KEY).json()
    spec = RuleSpec(name=BODY["name"], severity="low", definition=RuleDefinition())
    hits = run(spec, issue(freq(1, 3480, 3520)))
    for h in hits:
        h.rule_id = rule["rule_id"]
    artifact_id = _artifact(tmp_path)
    save_hits(artifact_id, hits)
    listed = lambda: [c["rule_id"] for c in client.get("/cases").json()]  # noqa: E731
    assert listed() == [rule["rule_id"]]
    assert client.get("/rules").json()[0]["case_count"] == 1
    client.put(f"/rules/{rule['id']}", json={**BODY, "enabled": False}, headers=KEY)
    assert listed() == []
    client.put(f"/rules/{rule['id']}", json=BODY, headers=KEY)
    assert listed() == [rule["rule_id"]]
    save_hits(artifact_id, [])  # screened again, and the rule no longer raises it
    assert listed() == []


def test_letter_explanation_describes_the_rule_not_a_missing_allocation():
    hit = run(RuleDefinition(direction="transmit"), issue(freq(1, 3480, 3520)))[0]
    case = CaseView(id=1, domain="space", rule_id=hit.rule_id, severity=hit.severity, title=hit.title, adm=hit.adm,
                    network=hit.network, notice_ids=["1"], details=hit.details, first_issue=3083, last_issue=3083,
                    comment_deadline=None, source_sha256="f" * 64)
    text = explain_case(case)
    assert "user-defined rule “Test” (version 3)" in text
    assert "no space-to-Earth" not in text
