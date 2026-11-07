# 30 Trends in the app, terrestrial and space

Status: resolved
Owner: Person C (Claude, with mehr)
Type: task
Size: M
Blocked by: none
Owns: a trends endpoint and page, `ific_guard/terrestrial/trends.py` reuse, a new `ific_guard/screening/trends.py`

## Why

The side quest asks to "surface a small number of trends or anomalies in neighbouring countries administrations' notices", and the guiding question asks for "trends and planned usage of new satellites systems". Terrestrial trends exist only as `outputs/neighbour-trends.md`; there are no space trends (README, "Things not evaluated").

## Do

1. Serve the existing terrestrial report from the API and show it on a Trends page.
2. Add space counts across stored issues: new API/A and CR/C filings by administration, by band (M4 band) and by orbit type, and flag a jump against the previous issues.
3. Keep it to counts and plain flags; each figure links to the findings it counts where possible.

## Acceptance

- The page shows both, for at least 3074-3083.
- A test checks one count against a hand-made fixture.

## Comments

2026-11-07, done:

- **Storage:** `issue_summary` holds one issue's counts, written when the issue is screened (`engine._store_trend_summary`, which never fails screening) and filled in on the first request for issues screened earlier. `SUMMARY_VERSION` makes stored summaries recompute after a change.
- **Space** (`ific_guard/screening/trends.py`): API/A and CR/C satellite notices per issue, by administration, downlink band (IEEE letters), orbit and stage, and how many are visible from Finland; plus the largest non-GSO systems by planned satellites, each network once.
- **Terrestrial:** the counts from `terrestrial/trends.py` for each issue, so the page and `outputs/neighbour-trends.md` agree.
- **Flags:** the latest issue's count is at least twice its earlier average and at least 5. The page states the rule; flagged cells carry a marker and text, not colour alone. Administration flags link to that issue's findings.
- **API and page:** `GET /trends?domain=space|terrestrial`, and a Trends page in the sidebar.
- **Live data:** this installation holds Space 3074, 3082 and 3083 and Terrestrial 3083 only. Space flags Japan (12, from 2) and Saudi Arabia (12, from 0), and V and W band; the largest new system is INDSAT-NGSO-LEO-1 (IND), 1,600 satellites. Terrestrial says it needs two stored issues. The first request took 12 s (space) and 5 s (terrestrial); later ones read the stored summaries.
- **Tests:** `tests/test_trends_api.py`: counts on a hand-made issue, the flag rule, merging and filling in summaries, a twin notice listed once, and an unreadable issue reported, not fatal.
