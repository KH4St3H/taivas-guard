# 24 Map station layer: only stations on the satellite's own frequencies

Status: resolved
Owner: Person C (Claude, with mehr)
Type: task
Size: S
Blocked by: none
Owns: `_stations` in `ific_guard/screening/coverage.py`, `frontend/src/components/FindingMap.tsx`, `tests/test_coverage.py`

## Why

The finding map's station layer shows every listed station whose band lies anywhere in the case's M4 bands, not only those on the frequencies the satellite transmits. Measured on IFIC 3083: ARABSAT-12G-1E shows 32 (26 share its frequencies), VSAR-03 333 (65), TOUTATIS 320 (0). That overstates who is affected (brief 06 C and D).

## Do

1. Build the layer from the family's space-to-Earth assignments that overlap the case's bands, clipped to those bands, using the same overlap test as `station-rx-overlap`.
2. Rename the toggle "Stations on this satellite's frequencies (N)". When N is 0, say no listed station shares its frequencies instead of hiding the control.
3. Keep binning above `STATION_POINTS_MAX`.

## Acceptance

- The three 3083 cases above show 26, 65 and 0.
- A test has a station inside the M4 band but outside the assignment, and it is not drawn.
- `uv run pytest` and `npx vitest run` pass; a screenshot of TOUTATIS is attached to the comments.

## Comments

2026-11-07, done:

- **Code:** `coverage._transmit_segments` takes the family's space-to-Earth assignments that overlap the case's bands, clipped to them, with the station rule's overlap test. `_stations` matches on those segments. The response names them (`stations.segments`) and "How this map is made" lists them.
- **UI:** the toggle reads "Stations on this satellite's frequencies (N)"; with none, the map says "No listed station shares this satellite's frequencies."
- **3083, with the earth station from ticket 21 in the index:** ARABSAT-12G-1E 26 (was 32), VSAR-03 65 (was 333), TOUTATIS 0 (was 320).
- **Tests:** a station inside the M4 band but outside the assignment isn't drawn; an empty layer is reported as empty. `uv run pytest tests/test_coverage.py` and `npx vitest run` pass.
- **Screenshot:** TOUTATIS shows the empty-layer message (dark theme), checked in headless Chrome.
