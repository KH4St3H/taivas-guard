# 21 Finnish band restrictions, RR footnotes naming Finland, and real earth stations

Status: resolved
Type: task
Size: L
Blocked by: none
Priority: Next. One feature: what Finland restricts or protects in a band, shown on the cases that touch it.
Owns: `ific_guard/screening/m4.py`, `tools/build_m4_bands.py`, `data/national/` (new files and regenerated band table), the band sections of `rules.py` and `rule_stations.py`, a new loader for earth stations, `tools/build_rr_footnotes.py`, the band table on the case page, tests

## Why

Finland's own restrictions are in data we already download, but only three phrases survive into `m4_bands.csv` (`notes`, 21 bands) and no rule reads them. Traficom's frequency table API (`data/national/taajuusjakotaulukko_2026-11-07.json`, 5,917 rows) also holds:

| Field | What it says | Rows |
|---|---|---:|
| `Comment` | "All emissions prohibited (RR 5.340)" | 34 |
| `Comment` | "Restrictions on use (RR 5.113)" and similar | 52 |
| `Comment` | "reserved", "not allowed", "not in use", "shall not" | about 30 |
| `Comment` | A citation of an RR footnote (44 distinct, 5.340, 5.150, 5.287, 5.353A, ...) | many |
| `Sub_band_usage` | "Military use" | 83 |
| `Sub_band_usage` | "Government" | 29 |
| `Comment` | Real Finnish earth stations: a receiving station at Sodankylä Tähtelä (7700-8500 MHz), transmitting stations at Sodankylä Tähtelä (2025-2070 MHz) and Kirkkonummi (2036.25 MHz) | 9 |

The ITU's own exceptions for Finland are separate: at least 14 RR Article 5 footnotes name Finland (additional, alternative or different-category allocations), found by a text search of RR Volume 1 (2024 edition, the copy `data/masks/limit_masks.json` cites, sha256 `040907a3...`).

## Do

1. **Keep every restriction in the band table.** `build_band_table` adds three columns, verbatim and without interpretation: `restrictions` (comments that restrict, prohibit, reserve or exclude), `rr_footnotes` (RR 5.x numbers the comments cite) and `national_use` (military or government `Sub_band_usage`). Regenerate `m4_bands.csv` from the saved snapshot, with no network. No existing column may change.
2. **Show them on cases.** Bands on `m4-no-space-to-earth` and `station-rx-overlap` cases carry the restrictions, RR footnote numbers and national use that overlap them. Severity does not change: Traficom has not said how these should weigh.
3. **RR footnotes naming Finland.** `tools/build_rr_footnotes.py` extracts, from RR Volume 1, every Article 5 footnote whose text names Finland: its number, kind (the words before the colon), the frequency ranges its text states, the text and the PDF page. It writes `data/national/rr_footnotes_finland.json` with the PDF's sha256. Bands on cases carry the footnotes that overlap them. Text extraction keeps PDF spacing artefacts, so the file says each entry must be checked against the page.
4. **Real earth stations.** `data/national/fin_earth_stations.csv` lists each site from the API comments, with its direction, band and API row. Receiving sites join the special-interest stations, so the station rule and the pfd rule evaluate them as real receivers. Transmitting sites are listed but not protected: a satellite downlink in their band does not reach a receiver there.

## Acceptance

- `m4_bands.csv` keeps every existing column and value; only the three new columns differ.
- On 3074, report: cases whose bands carry a restriction, an RR footnote naming Finland, or military or government use; and station cases that include the Sodankylä receiving station.
- Every RR footnote entry gives a PDF page, and the frequency ranges parsed from its text are covered by a test on at least two real footnotes.
- `uv run pytest` and the frontend tests pass.

## Open

- **Earth station coordinates.** The API gives none and the IFICs contain no Finnish earth station filings. ITU Space Explorer lists earth stations, but a programmatic query was blocked in this session, so someone needs to look the sites up there (or Traficom gives them). Until then the sites have no coordinates: they are linked by frequency and count as no calculation, never as a result.
- **CEPT implementation status** (`docdb.cept.org/implementation`) is a possible later addition, not in this ticket.

## Answer

Done on `agent/21-finnish-restrictions`.

- **Band table:** `restrictions`, `rr_footnotes` and `national_use` added; all 479 rows and every existing value unchanged. 69 bands carry a restriction, 107 cite an RR footnote and 38 have military or government use.
- **RR footnotes:** `tools/build_rr_footnotes.py` found 16 Article 5 footnotes naming Finland, two more than the first text search (5.295A, 5.512), each with its PDF page and the ranges its text states.
- **Earth stations:** the receiving site at Sodankylä Tähtelä (7700-8500 MHz, API rows 4332-4360) is protected; Sodankylä's and Kirkkonummi's transmitting sites are listed but not. Coordinates are still missing (see Open).
- **On 3074** (183 cases, 39 high, 106 medium, 38 low): 25 cases carry a restriction, 61 national use, 34 a cited RR footnote and 14 a footnote naming Finland (5.536B and 5.536C on 27 bands, 5.295A and 5.296 on 5). Sodankylä appears in 19 station cases. One case is new: SUNCET, where Sodankylä is the only station in band and the non-GSO bound is more than 3 dB below the limit, so it is low.
- **Verified:** 612 Python tests (4 skipped) and 40 frontend tests pass. The committed exports were not regenerated; that is pending with ticket 19's.
