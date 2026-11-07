import csv
import json

import pytest
from sqlalchemy import select

from ific_guard.db import session_scope
from ific_guard.export import export_issue
from ific_guard.models import Artifact, Case, Event
from tests.test_screening import FakeReader, freq, notice


def source(tmp_path, issue=3074, sha="a" * 64):
    path = tmp_path / f"{issue}-{sha[:4]}.mdb"
    path.write_bytes(b"test database")
    with session_scope() as s:
        row = Artifact(domain="space", issue_no=issue, source_url="https://www.itu.int/test.zip",
                       sha256=sha, size_bytes=20, mdb_path=str(path))
        s.add(row)
        s.flush()
        return row.id


@pytest.fixture
def fake_reader(monkeypatch):
    reader = FakeReader(
        notice=[notice(10), notice(20)],
        geo=[dict(ntc_id=10, sat_name="Medium", long_nom=25), dict(ntc_id=20, sat_name="High", long_nom=25)],
        freq=[freq(10, 1410, 1412), freq(20, 1410, 1412)],
        grp=[dict(grp_id=2, ntc_id=20)],
        provn=[dict(grp_id=2, adm="FIN", coord_prov="9.7")],
    )
    monkeypatch.setattr("ific_guard.export.MdbReader", lambda path: reader)
    return reader


def test_export_is_repeatable_ranked_traceable_and_has_no_side_effects(tmp_path, fake_reader, monkeypatch):
    source(tmp_path)
    monkeypatch.setenv("IFIC_API_KEY", "do-not-export-this")
    first, second = tmp_path / "first", tmp_path / "second"
    a = export_issue("space", 3074, first)
    b = export_issue("space", 3074, second)
    for name in ("cases.csv", "cases.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    for key in ("generated_at", "run_time_s"):
        a.pop(key)
        b.pop(key)
    assert a == b
    rows = json.loads((first / "cases.json").read_text(encoding="utf-8"))
    assert rows and all(r["source_sha256"] == "a" * 64 and r["notice_ids"] for r in rows)
    assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
    assert rows[0]["severity"] == "high"
    with (first / "cases.csv").open(encoding="utf-8", newline="") as f:
        assert len(list(csv.DictReader(f))) == len(rows)
    assert "do-not-export-this" not in (first / "manifest.json").read_text()
    with session_scope() as s:
        assert list(s.scalars(select(Case))) == []
        assert list(s.scalars(select(Event))) == []


def test_export_uses_requested_issue_and_revision_not_latest_global_case(tmp_path, fake_reader, monkeypatch):
    source(tmp_path)
    source(tmp_path, sha="b" * 64)
    source(tmp_path, issue=3083, sha="c" * 64)
    paths = []
    monkeypatch.setattr("ific_guard.export.MdbReader", lambda path: paths.append(path) or fake_reader)
    assert export_issue("space", 3074, tmp_path / "latest")["source_sha256"] == "b" * 64
    assert "3074-bbbb" in paths[-1]
    assert export_issue("space", 3074, tmp_path / "old", sha256="a" * 64)["source_sha256"] == "a" * 64
    assert "3074-aaaa" in paths[-1]


def test_missing_or_unsupported_issue_does_not_create_empty_success(tmp_path):
    for domain in ("space", "terrestrial"):
        with pytest.raises(ValueError):
            export_issue(domain, 3074, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_zero_findings_keeps_headers_and_rule_scope(tmp_path, fake_reader):
    source(tmp_path)
    fake_reader.tables.clear()
    manifest = export_issue("space", 3074, tmp_path / "out")
    assert manifest["case_count"] == 0
    assert manifest["rule_ids"] == ["fin-named-by-br", "m4-no-space-to-earth"]
    assert manifest["scope"]["ap30_coverage"] == "not implemented"
    assert (tmp_path / "out/cases.json").read_text().strip() == "[]"
    assert (tmp_path / "out/cases.csv").read_text().startswith("rank,domain,issue_no,")
