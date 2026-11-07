# IFIC Guard delivery: work distribution

Goal: finish the Traficom challenge deliverables with several agents working in parallel, without them colliding.

Read first: `ARCHITECTURE.md` (the analysis), `docs/services-architecture.md` (the services, current status, known gaps), `docs/challenge/` (the brief).

## Notes

### Tickets

Status values come from `docs/agents/triage-labels.md`. Size is a rough relative guide: S, M or L.

| # | Ticket | Owner | Size | Blocked by | Priority |
|---|---|---|---|---|---|
| 01 | Baseline: commit, fix stray text, fetch shared data | Human + coordinator | S | none | Required |
| 02 | Ask Traficom the open questions | Human | S | none | Required |
| 03 | Space 3074 evaluation export | Agent | M | 01 | Required |
| 04 | M4 bands from Traficom's API | Agent | M | 01 | High |
| 05 | Station loader and overlap rule | Agent | M | 01 | High |
| 06 | pfd engine and limit masks | Agent | L | 01 | High |
| 07 | pfd rule on real filings | Agent | M | 06 | High |
| 08 | Terrestrial adapter, diff and filter | Agent | L | 01 | Required |
| 09 | P.1546 engine and T/R 25-08 triggers | Agent | L | 01 | Required |
| 10 | Terrestrial findings and 3076 export | Agent | M | 03, 08, 09 | Required |
| 11 | Neighbour trends and anomalies | Agent | S | 08 | Medium |
| 12 | Review UI | Agent | M | 01 | Medium |
| 13 | Explanations and draft letters | Agent | M | 01 | High |
| 14 | Final run, evaluation files and demo | Coordinator | M | all others | Required |

### Order

```
Wave 0   01  02 (02 runs alongside everything; answers feed later tickets)
Wave 1   03  04  05  06  08  09  12  13   in parallel
Wave 2   07  10  11                       as their blockers finish
Wave 3   14
```

With fewer agents, start in this order: 03, 08, 09, 06, 04, 13, 05, 12. These are the two mandatory evaluated issues first, then the calculation that gives space cases their evidence.

If time runs out, cut in this order: 11, then 12 (the API and exports can carry a demo), then 07's non-GSO part, then 05. Keep 13 at least as deterministic templates, since draft correspondence is in the brief's guiding question.

### How agents work

The coordinator is one agent or person who assigns tickets, merges and updates this file.

1. **One worktree and branch per ticket:** `agent/NN-slug`, from the latest baseline. Commit there. Never commit to `main`, and do not push unless the coordinator says so.
2. **The coordinator assigns tickets.** Worktrees each hold their own copy of `.scratch/`, so self-claiming by editing a status file would not be seen by other agents. Report results in your final message; the coordinator records them here.
3. **Stay inside your ticket's "Owns" list.** If you need a change elsewhere, make the smallest additive change and name it in your report.
4. **Shared data is read-only.** `data/` and `files/` are git-ignored, so a worktree does not contain them. Point to the shared copy from ticket 01 with an absolute path: `/Users/mehrshad/personal/radio/data/shared/`. Do not download from ITU again.
5. **Never send real email.** Keep `IFIC_EMAIL_BACKEND` at `console` or `file`.
6. **Do not use Docker Compose or fixed ports 8001-8003 in parallel work.** Use the test client, or pick an unused port. Ticket 14 runs the full stack.
7. **Do not invent regulatory values.** Limits, trigger values and clause numbers must come from a source you read, and carry a citation. If you cannot get the source, stop and report `needs-info`.

### Definition of done, every ticket

- `uv run pytest` passes, with new tests for the behaviour added.
- The ticket's acceptance checks were actually run, and the report gives their output.
- Assumptions are visible in the output, and in `Case.details` where they affect a result.
- Findings say "possible concern" unless a calculation shows a limit is exceeded.
- The report lists what changed, what was verified, what was not, and any contract changes.

### Contracts between tickets

**Adding a rule.** Implement `Rule` from `ific_guard/screening/rules.py` in a new module, and add one line to `space_rules()`. That one line is the only expected conflict, and the coordinator resolves it at merge.

**`Hit` and `Case`.** Do not add database columns. Put results in `details`, so that UI and LLM work is not blocked by schema changes.

**Keys in `Case.details`** for anything calculated. This follows the Finding record in ARCHITECTURE.md section 5. Tickets 07, 10, 12, 13 and 14 all depend on it:

```json
{
  "method": "pfd_gso | pfd_ngso | p1546 | screening",
  "calc_inputs": {},
  "assumptions": ["..."],
  "worst_point": {"lat": 0.0, "lon": 0.0, "angle_deg": 0.0},
  "value_db": 0.0,
  "limit_db": 0.0,
  "margin_db": 0.0,
  "mask_id": "...",
  "station_ids": ["..."],
  "citations": [{"doc": "RR", "clause": "Art. 21, Table 21-4", "page_or_url": "..."}],
  "source": {"domain": "space", "issue_no": 3074, "notice_ids": ["..."], "sha256": "..."}
}
```

Screening rules without a calculation use `method: "screening"` and leave the numeric keys out.

**Severity.** Tickets keep using `high`, `medium` and `low`. Scoring per ARCHITECTURE.md section 4.7 belongs to ticket 07, in one function that ticket 10 reuses.

### Who owns which code

| Path | Owner |
|---|---|
| `ific_guard/sync/`, `ific_guard/notifier/`, `ific_guard/service.py`, `ific_guard/events.py` | Stable. Change only to fix a bug |
| `ific_guard/screening/space.py` | 07, and 05 for additive reads |
| `ific_guard/screening/engine.py` | 10 (terrestrial routing) |
| `ific_guard/screening/m4.py` (new), `tools/`, `data/national/` | 04 |
| `ific_guard/screening/stations.py`, `rule_stations.py` (new) | 05 |
| `ific_guard/engines/pfd.py`, `data/masks/` (new) | 06 |
| `ific_guard/screening/rule_pfd.py`, `scoring.py` (new) | 07 |
| `ific_guard/terrestrial/` (new) | 08, 10, 11 in separate modules |
| `ific_guard/engines/p1546.py` (new) | 09 |
| `ific_guard/export.py`, `outputs/` (new) | 03 |
| `app.py` (new) | 12 |
| `ific_guard/llm/`, `data/refdocs/` (new) | 13 |

## Decisions so far

- **DuckDB is deferred.** Rules keep reading the `.mdb` through adapters until after submission, because no ticket needs the store to meet a deliverable. This departs from ARCHITECTURE.md section 4.2; ticket 14 records it there.
- **The evaluated issues are Space 3074 and Terrestrial 3076.** 3083 is for development only.
- **The terrestrial diff uses 3075 to 3076**, since the brief asks for consecutive issues.
- **Deterministic code decides.** The LLM only explains and drafts (ARCHITECTURE.md section 2).
- **Baseline verified (2026-11-07):** services and stray-text fix were already committed at `bc9c594`; 41 baseline tests pass. All four verified archives and MDBs are in this checkout's ignored `data/shared/`. See [ticket 01](issues/01-baseline.md). The old macOS shared-data path does not apply here.
- **Sequential implementation:** the user requested issues one by one. Work continues in the existing `services-foundation-v2` checkout without parallel agents, commits or pushes. Ticket 02 remains a human question list; ticket 03 uses a clearly provisional export format.
- **Space 3074 export complete:** [ticket 03](issues/03-space-3074-export.md) produced 51 possible concerns (10 high, 41 medium), identical CSV/JSON across two runs, five source-row checks, and 45 passing tests. Export re-evaluates the source artifact so mutable cross-issue review state cannot contaminate historical results. AP30-family coverage remains a declared gap.

## Fog

- **Submission deadline.** The event runs 6-8 Nov 2026, and the exact time is not in the brief. It decides how much of this plan is realistic.
- **Evaluation file format** for 3074 and 3076 (ticket 02). Ticket 03 builds a provisional format.
- **Whether teammates are already building** the pfd engine, P.1546 or the UI. If so, remove those tickets rather than duplicating.
- **Whether Octave is acceptable** for P.1546 in the demo environment (ticket 09).
