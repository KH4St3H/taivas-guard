from datetime import date

import httpx
import pytest
from sqlalchemy import select

from ific_guard import events
from ific_guard.config import get_settings
from ific_guard.db import session_scope
from ific_guard.models import Artifact, Event, SyncRun
from ific_guard.sync.fetch import BadArtifact, download, store_zip
from ific_guard.sync.runner import run_sync, scheduled_pass
from ific_guard.sync.sources import (
    ListingChanged,
    discover_space,
    parse_space_listing,
    parse_terrestrial_listing,
)

from .conftest import make_zip

# Markup copied from the live ITU pages on 2026-11-07
SPACE_PAGE = """<tr>
    <td align="center"><b>27.10.2026</b></td>
        <td align="center"><b><a href="../ific10/ific3083.zip">3083</a></b></td>
    <td align="center"><a href="//www.itu.int/net/x?sel_ific=3083&amp;ie=y">View</a></td></tr>
<tr>
    <td align="center"><b>13.10.2026</b></td>
        <td align="center"><b><a href="../ific10/ific3082.zip">3082</a></b></td>
</tr>"""
TERR_PAGE = """<tr class="ms-itmhover"><td class="ms-vb2">3083</td><td class="ms-vb2"><nobr>27/10/2026</nobr></td>
<td class="ms-vb2"><a href="/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific3083.zip">IFIC3083</a></td></tr>
<tr class="ms-alternatingstrong"><td class="ms-vb2">3082</td><td class="ms-vb2"><nobr>13/10/2026</nobr></td>
<td class="ms-vb2"><a href="/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific3082.zip">IFIC3082</a></td></tr>"""


def test_parse_space_listing_resolves_urls_and_dates():
    refs = parse_space_listing(SPACE_PAGE, "https://www.itu.int/sns/wic/demowic26.html")
    assert refs[0].issue_no == 3083
    assert refs[0].url == "https://www.itu.int/sns/ific10/ific3083.zip"
    assert refs[0].published_on == date(2026, 10, 27)


def test_parse_terrestrial_listing_pairs_each_issue_with_its_date():
    refs = parse_terrestrial_listing(TERR_PAGE, "https://www.itu.int/en/ITU-R/terrestrial/brific/Pages/default.aspx")
    assert [(r.issue_no, r.published_on) for r in refs] == [(3083, date(2026, 10, 27)), (3082, date(2026, 10, 13))]
    assert refs[0].url == "https://www.itu.int/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific3083.zip"


def test_a_changed_listing_raises_rather_than_looking_like_no_new_issues():
    with pytest.raises(ListingChanged):
        parse_space_listing("<html>Site redesign</html>", "https://www.itu.int/sns/wic/demowic26.html")


def test_a_link_outside_itu_is_refused():
    page = SPACE_PAGE.replace("../ific10/ific3083.zip", "https://evil.example/ific3083.zip")
    with pytest.raises(ListingChanged, match="outside itu.int"):
        parse_space_listing(page, "https://www.itu.int/sns/wic/demowic26.html")


def test_space_discovery_walks_back_a_year_over_a_missing_page():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("demowic27.html"):
            return httpx.Response(404)
        return httpx.Response(200, text=SPACE_PAGE)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        refs = discover_space(client, get_settings(), today=date(2027, 1, 2))
    assert {r.issue_no for r in refs} == {3082, 3083}


def _site(zips: dict[str, bytes], etag: str = '"v1"', fail_terrestrial: bool = False):
    calls = {"downloads": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("demowic26.html"):
            return httpx.Response(200, text=SPACE_PAGE)
        if path.endswith("default.aspx"):
            return httpx.Response(503) if fail_terrestrial else httpx.Response(200, text=TERR_PAGE)
        name = path.rsplit("/", 1)[-1]
        if name in zips:
            if request.method == "GET":
                calls["downloads"] += 1
            return httpx.Response(200, content=zips[name], headers={"etag": etag})
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


ALL_ZIPS = {
    "ific3083.zip": make_zip("ific3083.mdb"),
    "ific3082.zip": make_zip("ific3082.mdb"),
    "brific3083.zip": make_zip("brific3083.mdb"),
    "brific3082.zip": make_zip("brific3082.mdb"),
}


def test_sync_fetches_both_domains_once_and_announces_each_issue():
    client, calls = _site(ALL_ZIPS)
    run_sync("manual", client)
    assert calls["downloads"] == 4
    run_sync("manual", client)  # nothing new
    assert calls["downloads"] == 4
    with session_scope() as s:
        artifacts = list(s.scalars(select(Artifact)))
        topics = [e.topic for e in s.scalars(select(Event))]
        runs = list(s.scalars(select(SyncRun)))
    assert {(a.domain, a.issue_no) for a in artifacts} == {
        ("space", 3083), ("space", 3082), ("terrestrial", 3083), ("terrestrial", 3082),
    }
    assert topics == [events.ISSUE_FETCHED] * 4
    assert [r.status for r in runs] == ["ok", "ok"]


def test_republished_issue_becomes_a_new_revision_and_keeps_the_old_one():
    client, _ = _site(ALL_ZIPS)
    run_sync("manual", client)
    corrected = dict(ALL_ZIPS, **{"ific3083.zip": make_zip("ific3083.mdb", b"\x00\x01\x00\x00Standard Jet DB\x00corrected")})
    client, _ = _site(corrected, etag='"v2"')
    run_sync("manual", client)
    with session_scope() as s:
        revisions = list(s.scalars(select(Artifact).where(Artifact.domain == "space", Artifact.issue_no == 3083)))
    assert len(revisions) == 2
    assert len({r.mdb_path for r in revisions}) == 2


def test_one_source_down_still_syncs_the_other_and_alerts_ops():
    client, _ = _site(ALL_ZIPS, fail_terrestrial=True)
    run_sync("manual", client)
    with session_scope() as s:
        run = s.scalars(select(SyncRun)).one()
        domains = {a.domain for a in s.scalars(select(Artifact))}
        alerts = list(s.scalars(select(Event).where(Event.topic == events.OPS_ALERT)))
    assert run.status == "partial"
    assert domains == {"space"}
    assert len(alerts) == 1 and "terrestrial" in alerts[0].payload["body"]


def test_a_run_with_errors_retries_sooner_than_a_clean_one(monkeypatch):
    settings = get_settings()
    for client, expected in [
        (_site(ALL_ZIPS, fail_terrestrial=True)[0], settings.retry_interval_s),
        (_site(ALL_ZIPS)[0], settings.poll_interval_s),
    ]:
        monkeypatch.setattr("ific_guard.sync.runner.httpx.Client", lambda *a, c=client, **k: c)
        assert scheduled_pass() == expected


def test_download_asks_for_the_uncompressed_file_so_its_length_can_be_checked():
    seen = {}

    def handler(request):
        seen.update(request.headers)
        return httpx.Response(200, content=make_zip())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        download(client, "https://www.itu.int/x/ific1.zip", "space", 1, get_settings())
    assert seen["accept-encoding"] == "identity"


def test_truncated_download_is_rejected_and_leaves_nothing_behind():
    def handler(_request):
        return httpx.Response(200, content=b"PK\x03\x04broken", headers={"content-length": "9"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client, pytest.raises((BadArtifact, httpx.HTTPError)):
        download(client, "https://www.itu.int/x/ific1.zip", "space", 1, get_settings())
    assert not (get_settings().data_dir / "ific").exists() or not any((get_settings().data_dir / "ific").rglob("*.mdb"))


@pytest.mark.parametrize(
    "archive, message",
    [
        (make_zip("notes.txt"), "found 0"),
        (make_zip("ific.mdb", b"this is not an access file at all, just some text"), "not an Access database"),
        (b"not a zip", "Not a valid zip"),
    ],
)
def test_bad_archives_are_rejected(tmp_path, archive, message):
    path = tmp_path / "ific.zip"
    path.write_bytes(archive)
    with pytest.raises(BadArtifact, match=message):
        store_zip(path, "space", 1, get_settings())


def test_a_path_inside_the_zip_cannot_escape_the_issue_folder(tmp_path):
    path = tmp_path / "ific.zip"
    path.write_bytes(make_zip("../../evil.mdb"))
    stored = store_zip(path, "space", 1, get_settings())
    assert stored.mdb_path.name == "evil.mdb"
    assert stored.mdb_path.is_relative_to(get_settings().data_dir / "ific" / "space" / "1")
