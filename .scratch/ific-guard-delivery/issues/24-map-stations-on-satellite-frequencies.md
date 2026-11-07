# 24 Map station layer: only stations on the satellite's own frequencies

Status: ready-for-agent
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
