# 12 Review UI

Status: ready-for-agent
Type: task
Size: M
Blocked by: 01
Owns: `app.py`, a `ui` dependency group in `pyproject.toml`, `tests/test_ui_client.py`

## Goal

A Streamlit page where an expert can work through cases, as in ARCHITECTURE.md section 4.9. It talks only to the REST APIs, and never touches the database, so the services stay the single source of truth.

## Do

1. Ranked case list with filters for severity, rule, administration, status and issue.
2. Case detail: why it was raised, notices, bands, stations, comment deadline, then calculation inputs, assumptions, margin and citations where present. Handle `method: "screening"` cases with no numbers.
3. Accept or reject with a note, through `PATCH /cases/{id}`. Read the API key from the environment, and never show it.
4. A status strip from `GET /status` on the sync service: latest issue per domain and whether it is stale.
5. A clear statement that a case is a possible concern for review, unless it carries a calculated exceedance.
6. Build against the `details` contract in `map.md`, with sample data until tickets 07 and 10 merge.

## Acceptance

- Run it against live services loaded with IFIC 3083: list, open, review a case, and confirm via the API that the review was saved.
- An unavailable service shows a readable message, not a stack trace.
- Screenshots in your report.

## Not in scope

Log-in, the trends panel unless ticket 11 has merged, and editing draft letters until ticket 13 merges.
