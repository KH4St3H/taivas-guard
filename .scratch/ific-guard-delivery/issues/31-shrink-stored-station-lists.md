# 31 Shrink stored station lists without resetting reviews

Status: claimed
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
