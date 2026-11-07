# 28 README, Reference page and docs match the code

Status: ready-for-agent
Type: task
Size: S
Blocked by: 29
Owns: `README.md`, `SOURCES` and severity text in `frontend/src/api/http.ts`, `docs/services-architecture.md` status section

## Why

Brief 07 asks for "information on the input/output" and documentation; 06 E for auditability. Several statements are now false:

- The Reference page says RR limits are used by "no screening rule … yet" and that terrestrial rules are "not added yet" (`http.ts`, `SOURCES`).
- The README rule table lacks `pfd-gso-cept`, `pfd-ngso-cept` and custom rules (`custom-<id>`), and doesn't mention the reach map or the paged station list.
- README output counts (182 and 29 cases) predate today's changes.

## Do

1. Rewrite `SOURCES` and the severity rules to match the code, one line per source with its real status.
2. Update the README: rule table, what it does, outputs and counts (from ticket 29), new endpoints (`/rules`, `/cases/{id}/stations`, `/cases/{id}/coverage`).
3. Update `docs/services-architecture.md` current status.

## Acceptance

- Every rule id the code can produce is in the README table.
- No statement on the Reference page contradicts the code.
