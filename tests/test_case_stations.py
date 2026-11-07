import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ific_guard.config import get_settings
from ific_guard.db import session_scope
from ific_guard.models import Artifact, Case
from ific_guard.screening import case_stations
from ific_guard.screening.app import app
from ific_guard.screening.engine import save_hits
from ific_guard.screening.rule_stations import StationOverlapRule
from ific_guard.screening.space import SpaceIssue
from ific_guard.screening.station_links import STATION_SAMPLE
from tests.test_screening import FakeReader, freq, notice
from tests.test_stations import gso, station

TOTAL = STATION_SAMPLE + 40


@pytest.fixture
def screened(tmp_path, monkeypatch):
    """One case whose band overlaps more stations than a case keeps, saved as screening would save it."""
    stations = [station(row=i, number=50_000 + i, cls="FX" if i % 3 else "MVV") for i in range(TOTAL)]
    issue = SpaceIssue(FakeReader(notice=[notice(1)], geo=gso(1), freq=[freq(1, 2230, 2250)]))
    path = tmp_path / "3083.mdb"
    path.write_bytes(b"test")
    with session_scope() as s:
        artifact = Artifact(domain="space", issue_no=3083, source_url="u", sha256="a" * 64, size_bytes=4, mdb_path=str(path))
        s.add(artifact)
        s.flush()
        artifact_id = artifact.id
    rule = StationOverlapRule(get_settings(), stations, {"file": "register.xlsx", "sha256": "reg-1", "records": TOTAL})
    save_hits(artifact_id, list(rule.run(issue)))
    case_stations._compute.cache_clear()
    monkeypatch.setattr(case_stations, "stored_issue", lambda *_: issue)
    monkeypatch.setattr(case_stations, "load_stations_cached", lambda *_: stations)
    monkeypatch.setattr(case_stations, "_digest", lambda *_: "reg-1")
    with session_scope() as s:
        return s.scalars(select(Case.id)).one()


def test_case_stores_a_sample_and_the_endpoint_lists_every_station(screened):
    with session_scope() as s:
        details = s.get(Case, screened).details
    assert details["station_count"] == TOTAL and len(details["stations_overlapping"]) == STATION_SAMPLE
    client = TestClient(app)
    first = client.get(f"/cases/{screened}/stations", params={"limit": 50}).json()
    assert (first["total"], first["matching"], len(first["rows"]), first["dataset_changed"]) == (TOTAL, TOTAL, 50, False)
    rest = client.get(f"/cases/{screened}/stations", params={"offset": 100, "limit": 1000}).json()
    assert len(rest["rows"]) == TOTAL - 100
    ids = {r["station_id"] for r in first["rows"]} | {r["station_id"] for r in rest["rows"]}
    assert len(ids) == 50 + TOTAL - 100
    mvv = client.get(f"/cases/{screened}/stations", params={"licence": "MVV"}).json()
    assert mvv["matching"] == first["counts"]["licence"]["MVV"] and all(r["licence_class"] == "MVV" for r in mvv["rows"])


def test_csv_download_has_every_station(screened):
    text = TestClient(app).get(f"/cases/{screened}/stations.csv").text
    lines = text.strip().splitlines()
    assert lines[0].startswith("station_id,licence_class,status") and len(lines) == TOTAL + 1


def test_a_changed_register_is_reported(screened, monkeypatch):
    monkeypatch.setattr(case_stations, "_digest", lambda *_: "reg-2")
    assert TestClient(app).get(f"/cases/{screened}/stations").json()["dataset_changed"] is True


def test_cases_without_stations_say_so():
    with session_scope() as s:
        s.add(Case(fingerprint="x", domain="space", rule_id="fin-named-by-br", severity="high", title="T", adm="USA",
                   network="S", notice_ids=["1"], details={}, material_hash="m", first_issue=1, last_issue=1,
                   changed_artifact_id=1, source_sha256="f" * 64))
    response = TestClient(app).get("/cases/1/stations")
    assert response.status_code == 404 and "no station list" in response.json()["detail"]
