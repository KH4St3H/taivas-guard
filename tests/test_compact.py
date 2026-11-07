"""Ticket 31: shrinking cases stored before the station-list cap must not send reviewed cases back to pending."""
import copy
import subprocess
import sys

from sqlalchemy import select

from ific_guard.config import get_settings
from ific_guard.db import session_scope
from ific_guard.models import Artifact, Case, CaseOccurrence
from ific_guard.screening.compact import compact_space, compact_stations, compact_terrestrial
from ific_guard.screening.engine import save_hits
from ific_guard.screening.rule_stations import StationOverlapRule
from ific_guard.screening.space import SpaceIssue
from ific_guard.screening.station_links import STATION_SAMPLE
from ific_guard.screening.stations import BW_MISMATCH
from tests.test_screening import FakeReader, freq, notice
from tests.test_stations import gso, station

TOTAL = STATION_SAMPLE + 40


def _issue():
    return SpaceIssue(FakeReader(notice=[notice(1)], geo=gso(1), freq=[freq(1, 2230, 2250)]))


def _stations():
    flagged = (BW_MISMATCH,)
    return [station(row=i, number=70_000 + i, quality_flags=() if i % 4 else flagged) for i in range(TOTAL)]


def _hit(limit):
    rule = StationOverlapRule(get_settings(), _stations(), {"file": "register.xlsx", "sha256": "r"}, station_limit=limit)
    return next(iter(rule.run(_issue())))


def _old_shape(hit):
    """What the rule stored before the cap: every station, ids per side and per flag, no counts."""
    old = copy.deepcopy(hit)
    d = old.details
    for key in ("station_count", "stations_listed", "stations_not_visible_count"):
        d.pop(key)
    d["matched_on"] = {side: [f"id{i}" for i in range(n)] for side, n in d["matched_on"].items()}
    d["station_band_flags"] = {flag: [f"id{i}" for i in range(n)] for flag, n in d["station_band_flags"].items()}
    for band in d["bands"]:
        band.pop("station_count")
    return old


def test_compaction_gives_exactly_what_the_rule_stores_now():
    old = _old_shape(_hit(None))
    assert len(old.details["stations_overlapping"]) == TOTAL and old.details["station_band_flags"]
    assert compact_space(old.details) == _hit(STATION_SAMPLE).details
    assert compact_space(_hit(STATION_SAMPLE).details) is None  # already compact


def test_reviewed_cases_keep_their_decision_through_compaction_and_screening(tmp_path):
    path = tmp_path / "3083.mdb"
    path.write_bytes(b"test")
    with session_scope() as s:
        artifact = Artifact(domain="space", issue_no=3083, source_url="u", sha256="a" * 64, size_bytes=4, mdb_path=str(path))
        s.add(artifact)
        s.flush()
        artifact_id = artifact.id
    save_hits(artifact_id, [_old_shape(_hit(None))])
    with session_scope() as s:
        s.scalars(select(Case)).one().review_status = "accepted"

    dry = compact_stations(dry_run=True)
    assert (dry["cases"], dry["occurrences"]) == (1, 1) and dry["bytes_after"] < dry["bytes_before"]
    with session_scope() as s:
        assert "station_count" not in s.scalars(select(Case)).one().details  # a dry run writes nothing

    assert compact_stations()["cases"] == 1
    assert compact_stations()["cases"] == 0  # running it again changes nothing
    with session_scope() as s:
        assert len(s.scalars(select(CaseOccurrence)).one().hit["details"]["stations_overlapping"]) == STATION_SAMPLE

    assert save_hits(artifact_id, [_hit(STATION_SAMPLE)]) == (0, 0)  # screening again sees no change
    with session_scope() as s:
        assert s.scalars(select(Case)).one().review_status == "accepted"


def test_terrestrial_ids_are_counted_and_long_lists_left_for_screening():
    assert compact_terrestrial({"station_ids": ["a", "b"]}) == {"station_ids": ["a", "b"], "station_count": 2}
    assert compact_terrestrial({"station_ids": [str(i) for i in range(101)]}) is None
    assert compact_terrestrial({"station_ids": [], "station_count": 0}) is None


def test_the_command_is_wired():
    out = subprocess.run([sys.executable, "-m", "ific_guard.cli", "compact-stations", "--help"], capture_output=True, text=True)
    assert out.returncode == 0 and "--dry-run" in out.stdout
