# 03 Space 3074 evaluation export

Status: ready-for-agent
Type: task
Size: M
Blocked by: 01
Owns: `ific_guard/export.py`, `outputs/`, one `export` command in `ific_guard/cli.py`, `tests/test_export.py`

## Goal

Process the mandatory Space IFIC 3074 and export its cases as files an evaluator can read, using the existing pipeline. This is required for submission, and it is the first real test on the larger issue (61 MB zip, against 19 MB for 3083, which was the only one run so far).

## Do

1. Import `data/shared/ific3074.zip` with `python -m ific_guard.cli import` into a database under your worktree, then run screening.
2. Record run time and memory. Fix anything that breaks on this issue, including unexpected values in `SpaceIssue`.
3. Add `python -m ific_guard.cli export --domain space --issue 3074 --out outputs/ific_3074/` writing:
   - `cases.csv`: one row per case, flat columns, ranked
   - `cases.json`: full `details`
   - `manifest.json`: source URL, file SHA-256, code version, config values, rule IDs, run time
4. Keep the format in one place, since ticket 02 may change it. Ticket 10 reuses this exporter for 3076.
5. Report what 3074 contains: how many AP30, AP30A and AP30B notices exist, and whether current scope (`ntf_rsn` in A and C) skips them. The brief puts those sections in scope.

## Acceptance

- The export runs twice with identical content apart from timestamps.
- Every case in `cases.csv` traces to notice IDs and the file SHA-256.
- A hand check of 5 cases against the `.mdb`: reported in your final message with the rows you compared.
- AP30 coverage is stated plainly: handled, absent from 3074, or a gap.

## Not in scope

New rules, UI work, and `outputs/` for terrestrial.
