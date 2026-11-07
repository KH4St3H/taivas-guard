# 31 Shrink stored station lists without resetting reviews

Status: resolved
Owner: Person C (Claude, with mehr)
Type: task
Size: S
Blocked by: none
Owns: a one-off command in `ific_guard/cli.py`

## Why

Cases stored before the station-list cap still hold every station. Screening those issues again rewrites them, but because the stored shape changed, every station and pfd case counts as changed and its review goes back to pending. A database with real review decisions shouldn't lose them for a storage change.

## Do

1. Add `python -m ific_guard.cli compact-stations`: for each case with a full list, rewrite `details` with `station_summary` and the band sample, and recompute `material_hash` so the next screening sees no change. Do the same for case occurrences.
2. Print counts and bytes before and after; support `--dry-run`.

## Acceptance

- After running it and screening again, no review status changes on a database with decisions.
- A test covers a case stored in the old shape.

## Comments

2026-11-07, done:

- **Command:** `python -m ific_guard.cli compact-stations [--dry-run]` (`ific_guard/screening/compact.py`). It applies the rules' own summary to station and pfd cases (worst 100 stations, counts, per-side and per-flag counts, 20 ids per band) and recomputes `material_hash` as the engine does. Terrestrial cases get `station_count`; one with more than 100 ids is left for screening, because the rule's order of its first 100 isn't stored. Case occurrences are compacted too. Running it twice changes nothing.
- **Test:** an old-shape case rebuilt from an uncapped rule run compacts to exactly what the rule stores now; an accepted case stays accepted through compaction and a fresh `save_hits`, which reports `(0, 0)`.
- **Live database, dry run:** 178 cases and 178 occurrences, 34.1 MB to 28.8 MB. Not applied: it drops stored station lists (they can be recomputed on request), so the owner of that database runs it.
