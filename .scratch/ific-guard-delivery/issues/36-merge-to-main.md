# 36 Merge develop to main for submission

Status: resolved
Type: task
Size: S
Blocked by: 28, 29
Owns: `main`

## Why

Brief 07: "Code repository of the solution". `main` is 11 commits behind `develop` as of 2026-11-07, so a judge opening the default branch sees none of the work since 10:23 that day.

## Do

With the user's approval: open a PR from `develop` to `main`, check CI or run both test suites, merge, and confirm `outputs/` and the README on `main` are the re-exported ones.

## Delivery evidence ? 2026-11-07

The user explicitly authorized task 36 together with 22/23/28/29/34. Delivery is through the develop-to-main submission PR; its GitHub merge record is the authoritative completion evidence. Use a merge commit so the evaluation source commit `941282f` remains an ancestor of main.

The integrated candidate preserves newly arrived develop tasks 24/30/31 and the updated demo script. Final checks: 637 backend tests passed, zero skipped, with real 3074/3075/3076 fixtures; 40 frontend tests passed; TypeScript and production build passed. Both evaluation manifests have dirty=false, a retained source commit, verified output hashes and counts matching README (175 Space, 29 Terrestrial). The isolated service run verified stored/exported results, guarded drafts, review acceptance and file digests. Docker/cron was not rehearsed again because the daemon was unavailable.

After merging the PR, check out main, fast-forward from origin, and verify the README and evaluation Git blobs match the tested develop candidate. No force push or history rewriting is needed.
