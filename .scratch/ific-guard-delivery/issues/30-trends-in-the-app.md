# 30 Trends in the app, terrestrial and space

Status: claimed
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
