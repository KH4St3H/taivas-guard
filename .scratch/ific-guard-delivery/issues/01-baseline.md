# 01 Baseline: commit, fix stray text, fetch shared data

Status: resolved
Type: task
Size: S
Blocked by: none

## Why

Everything built so far is uncommitted, and worktrees start from commits, so no agent can see it yet. Every other agent ticket waits on this one.

## Steps

1. A human reviews the uncommitted work and approves committing it.
2. Remove the stray `[118;1:3u` from `schema.sql` (line 121) and `ARCHITECTURE.md` (line 126). Check with a teammate first if it is their file in progress.
3. In `docs/services-architecture.md` section 9, correct the `ARCHITECTURE.md` line reference from 124 to 126, or drop the line number.
4. Commit. Decide whether agents branch from `main` or from an integration branch.
5. Download the issues once, for all agents to share:

```bash
mkdir -p data/shared && cd data/shared
curl -fLO https://www.itu.int/sns/ific10/ific3074.zip
curl -fLO https://www.itu.int/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific3075.zip
curl -fLO https://www.itu.int/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific3076.zip
cp ../../files/ific3083.zip .
for z in *.zip; do unzip -oq "$z"; done
```

## Acceptance

- `git status` is clean apart from ignored files.
- `uv run pytest` passes on a fresh worktree of the baseline.
- `data/shared/` holds `ific3074.mdb`, `ific3083.mdb`, `brific3075.mdb` and `brific3076.mdb`. Confirm the database names, since these come from the zips. Expected zip sizes: 60,837,631, 19,001,626, 3,427,636 and 2,406,450 bytes.

## Answer

Done on 2026-11-07. Baseline is on `services-foundation-v2`. Stray text removed, and `schema.sql` creates all 12 tables in DuckDB. The four issues are in `data/shared/`, with the expected sizes and names.
