"""Ticket 21: Finland's restrictions, RR footnotes naming Finland, and real earth stations."""
import csv
import json

from ific_guard.config import get_settings
from ific_guard.screening.m4 import (
    BAND_COLUMNS,
    RR_FINLAND_PATH,
    build_band_table,
    finnish_notes,
    load_m4_rows,
    load_rr_footnotes_finland,
)
from ific_guard.screening.rule_stations import StationOverlapRule
from ific_guard.screening.rules import M4NoDownlinkRule
from ific_guard.screening.space import SpaceIssue
from ific_guard.screening.stations import EARTH_STATIONS_PATH, NO_COORDINATES, StationIndex, load_earth_stations
from tests.test_screening import FakeReader, freq, notice
from tests.test_stations import gso
from tools.build_rr_footnotes import footnotes, ranges_mhz

M4_BANDS = "data/national/m4_bands.csv"


def api_row(row_id, low_hz, high_hz, service="FIXED", comment="", usage=""):
    return {
        "ID": row_id, "Frequency_band_lower_limit": "1 GHz", "Frequency_band_upper_limit": "2 GHz",
        "Services_in_Finland": service, "Additional_information": "", "Sub_band_lower_limit__Hz_": low_hz,
        "Sub_band_upper_limit__Hz_": high_hz, "Sub_band_usage": usage, "Class_of_station": "", "Direction": "", "Comment": comment,
    }


def test_band_table_keeps_restrictions_footnotes_and_national_use_verbatim():
    rows = [
        api_row(1, 1_000_000_000, 1_500_000_000, comment="Restrictions on use (RR 5.113).", usage="Military use"),
        api_row(2, 1_000_000_000, 1_500_000_000, comment="Digital fixed radiolinks.", usage="Fixed links"),
    ]
    bands, _ = build_band_table(rows)
    assert {"restrictions", "rr_footnotes", "national_use"} <= set(BAND_COLUMNS)
    band = bands[0]
    assert band["restrictions"] == "Restrictions on use (RR 5.113)."
    assert band["rr_footnotes"] == "5.113" and band["national_use"] == "Military use"


def test_saved_band_table_carries_the_new_columns():
    with open(M4_BANDS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_low = {(r["band_low_mhz"], r["band_high_mhz"]): r for r in rows}
    assert "5.340" in by_low["1400", "1427"]["rr_footnotes"]
    assert "All emissions prohibited (RR 5.340)." in by_low["1400", "1427"]["restrictions"]
    assert sum(1 for r in rows if r["national_use"]) > 10


def test_footnote_ranges_are_read_from_their_text():
    assert ranges_mhz("the frequency bands 430-432 MHz and 438-440 MHz are also allocated") == [[430.0, 432.0], [438.0, 440.0]]
    assert ranges_mhz("in the band 1 610-1 626.5 MHz") == [[1610.0, 1626.5]]
    assert ranges_mhz("the band 1 715-1 800 kHz") == [[1.715, 1.8]]


def test_footnotes_are_split_and_kept_only_when_they_name_finland():
    pages = [(104, "RADIOLOCATION 5.275 5.276 5.275 Additional allocation: in Croatia, Estonia, Finl and, Libya, the "
                   "frequency bands 430-432 MHz and 438-440 MHz are also allocated. 5.276 Additional allocation: in Algeria, "
                   "the band 430-440 MHz is also allocated.")]
    found = footnotes(pages)
    assert [f["footnote"] for f in found] == ["5.275"]
    assert found[0]["kind"] == "Additional allocation" and found[0]["pdf_page"] == 104
    assert found[0]["bands_mhz"] == [[430.0, 432.0], [438.0, 440.0]]


def test_saved_footnotes_cite_the_edition_and_a_page_each():
    data = json.loads(RR_FINLAND_PATH.read_text(encoding="utf-8"))
    limits = json.loads(open("data/masks/limit_masks.json", encoding="utf-8").read())
    assert data["source"]["sha256"] == limits["sources"]["RR"][0]["sha256"]
    by_number = {f["footnote"]: f for f in data["footnotes"]}
    assert by_number["5.275"]["bands_mhz"] == [[430.0, 432.0], [438.0, 440.0]]
    assert by_number["5.221"]["bands_mhz"] == [[148.0, 149.9]]
    assert all(isinstance(f["pdf_page"], int) and "Finland" in f["text"].replace(" ", "") for f in data["footnotes"])


def test_notes_on_a_band_are_only_those_that_overlap_it():
    rows = load_m4_rows(get_settings().m4_filter_path)
    notes = finnish_notes(430.0, 431.0, rows, load_rr_footnotes_finland())
    assert [f["footnote"] for f in notes["rr_footnotes_naming_finland"]] == ["5.275"]
    assert finnish_notes(433.0, 434.0, [], load_rr_footnotes_finland()) == {}


def test_m4_case_bands_show_finnish_restrictions():
    bands = [b for b in __import__("ific_guard.screening.m4", fromlist=["x"]).load_m4_conflict_bands(get_settings().m4_filter_path)
             if b.low_mhz == 1400.0]
    hits = list(M4NoDownlinkRule(get_settings(), bands).run(
        SpaceIssue(FakeReader(notice=[notice(1)], geo=gso(1), freq=[freq(1, 1410, 1420)]))))
    band = hits[0].details["bands"][0]
    assert "All emissions prohibited (RR 5.340)." in band["m4_restrictions"] and "5.340" in band["m4_rr_footnotes"]


def test_receiving_earth_station_is_protected_and_transmitting_sites_are_not():
    with open(EARTH_STATIONS_PATH, newline="", encoding="utf-8") as f:
        listed = list(csv.DictReader(f))
    assert {(r["site"], r["direction"]) for r in listed} == {("Sodankylä Tähtelä", "rx"), ("Sodankylä Tähtelä", "tx"), ("Kirkkonummi", "tx")}
    stations = load_earth_stations()
    assert [s.key for s in stations] == ["ES:Sodankylä Tähtelä"]
    sodankyla = stations[0]
    assert sodankyla.rx_band_mhz == (7700.0, 8500.0) and sodankyla.licence_class == "Earth station (RX)"
    assert NO_COORDINATES in sodankyla.quality_flags and sodankyla.lat_deg is None
    assert [s.key for s, _ in StationIndex(stations).overlapping(8025.0, 8400.0)] == ["ES:Sodankylä Tähtelä"]


def test_an_earth_station_without_coordinates_is_linked_but_never_a_result():
    stations = load_earth_stations()
    rule = StationOverlapRule(get_settings(), stations)
    hits = list(rule.run(SpaceIssue(FakeReader(notice=[notice(1)], geo=gso(1), freq=[freq(1, 8025, 8400)]))))
    record = hits[0].details["stations_overlapping"][0]
    assert record["station_id"] == "ES:Sodankylä Tähtelä" and record["status"] == "no_calculation"
    assert hits[0].details["classes"] == {"Earth station (RX)": 1}


def test_drafts_quote_finnish_restrictions_for_a_band():
    from ific_guard.llm import draft
    from tests.test_llm import make_case

    band = {"low_mhz": 1400.0, "high_mhz": 1427.0, "m4_primary_services": "RADIO ASTRONOMY", "passive": True, "m4_table_pages": "120",
            "group_ids": [1], "m4_restrictions": ["All emissions prohibited (RR 5.340)."]}
    letter = draft(make_case("m4-no-space-to-earth", method="screening", bands=[band])).letter
    assert "Finnish restriction: All emissions prohibited (RR 5.340)." in letter
