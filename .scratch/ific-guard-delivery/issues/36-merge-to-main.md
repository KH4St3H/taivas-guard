# 36 Merge develop to main for submission

Status: ready-for-human
Type: task
Size: S
Blocked by: 28, 29
Owns: `main`

## Why

Brief 07: "Code repository of the solution". `main` is 11 commits behind `develop` as of 2026-11-07, so a judge opening the default branch sees none of the work since 10:23 that day.

## Do

With the user's approval: open a PR from `develop` to `main`, check CI or run both test suites, merge, and confirm `outputs/` and the README on `main` are the re-exported ones.
