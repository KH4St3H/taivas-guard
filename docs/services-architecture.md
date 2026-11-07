# IFIC Guard: services architecture

How IFIC Guard runs as FastAPI services: keeping IFIC databases up to date, screening each new issue, and emailing experts. This builds on [ARCHITECTURE.md](../ARCHITECTURE.md), which defines the analysis itself (adapters, relevance filter, pfd and P.1546 engines, LLM layer). This document covers how that analysis gets its data, runs, and reaches people.

## 1. Decisions

| Decision | Choice | Why |
|---|---|---|
| Service split | Three services in one repo and one Python package: `sync`, `screening`, `notifier` | They fail and scale differently, but a small team can still change them together |
| How issues arrive | Downloaded from ITU on a cron schedule, or uploaded as an `.mdb` or a `.zip` containing one | Both take the same path afterwards, so screening cannot tell them apart |
| Terrestrial neighbours | Russia, Sweden, Estonia, Norway, Denmark (`RUS`, `S`, `EST`, `NOR`, `DNK`) | Set by the team, and configurable with `IFIC_NEIGHBOUR_ADMS`. Space filings are not limited to these, because a satellite from anywhere can reach Finland |
| Messaging | Outbox table in the operational database | No broker to run. An event commits together with the change it announces, so neither is lost |
| Operational data | Postgres (SQLite for local development) | Several processes must write at once |
| Analytical data | DuckDB as in `schema.sql`, written only by `screening` | DuckDB allows one writing process, so it cannot be the shared store |
| What triggers email | Deterministic rules only | Principle 1 in ARCHITECTURE.md: the LLM never decides relevance |
| Email unit | One digest per issue, not one mail per case | IFIC 3083 alone produces 39 cases |
| Wording | "Possible concern", never "violation" | Screening flags cases. Whether a filing breaks a limit takes the pfd engine and an expert |

**Case and finding.** A *finding* (ARCHITECTURE.md section 5) is the result for one frequency assignment. A *case* is what a person reviews: one rule against one notice family, holding its evidence and review status. A modification and the notice it modifies share a family, so they produce one case.

## 2. System overview

```mermaid
flowchart LR
    ITU[ITU public listings<br/>and zip files] -->|cron schedule| SYNC
    UPLOAD[Uploaded .mdb or .zip] -->|POST /issues/upload| SYNC

    subgraph Services
        SYNC[sync :8001]
        SCREEN[screening :8002]
        NOTIFY[notifier :8003]
    end

    SYNC -->|issue.fetched| OPS[(Operational DB<br/>artifacts, cases, events,<br/>notifications)]
    OPS --> SCREEN
    SCREEN -->|issue.screened| OPS
    OPS --> NOTIFY
    SYNC -.->|ops.alert| OPS

    SYNC --> FILES[/IFIC files<br/>immutable, by SHA-256/]
    FILES --> SCREEN
    SCREEN --> DUCK[(DuckDB<br/>normalised store)]
    NATIONAL[M4, special-interest<br/>stations] --> SCREEN

    NOTIFY -->|SMTP| MAIL[Experts and operators]
    UI[React review UI] -->|REST| SCREEN
```

## 3. Services

| | `sync` | `screening` | `notifier` |
|---|---|---|---|
| Job | Find and store new issues | Turn issues into cases; serve review | Email experts and operators |
| Consumes | ITU listings on a cron schedule, uploaded files | `issue.fetched` | `issue.screened`, `ops.alert` |
| Publishes | `issue.fetched`, `ops.alert` | `issue.screened` | Nothing |
| Writes | `artifact`, `sync_run`, IFIC files | `case_`, DuckDB, `artifact.screen_status` | `notification` |
| Read API | `GET /issues`, `/runs`, `/status` | `GET /cases`, `/cases/{id}` | `GET /notifications` |
| Write API (needs key) | `POST /sync`, `POST /issues/upload` | `PATCH /cases/{id}`, `POST /issues/{id}/screen` | `POST /notifications/test` |

Every service also serves `/health`, `/ready` and FastAPI's `/docs`. Each runs as one uvicorn process with its background loops in the app lifespan. **Run one replica of each for now.** The outbox is safe with more, but the sync scheduler's lock is per process.

### Events

Each topic has one consuming service. Delivery is at-least-once, so handlers must be idempotent.

| Topic | Payload | Consumer's idempotency |
|---|---|---|
| `issue.fetched` | `artifact_id` | Cases are upserted by fingerprint |
| `issue.screened` | `artifact_id`, `status`, `opened`, `changed` | Digest `dedupe_key` |
| `ops.alert` | `dedupe_key`, `subject`, `body` | `dedupe_key` |

A worker claims an event with a compare-and-set update and holds a 30-minute lease, so a crashed worker's event is retried. Failures back off exponentially. After 5 attempts an event is marked `dead` and raises an `ops.alert`.

## 4. Sync subsystem

Findings from ITU's live pages on 2026-11-07:

| | Space | Terrestrial |
|---|---|---|
| Listing | `sns/wic/demowic{YY}.html`, one page per year | `en/ITU-R/terrestrial/brific/Pages/default.aspx`, last 10 issues |
| File | `sns/ific10/ific{N}.zip`; the `ific10` part is the data version, so it is read from the page | `.../BRIFIC/MDB/brific{N}.zip` |
| Contents, issue 3083 | One `.mdb`, 19 MB zip, 118 MB database | One `.mdb`, 3.4 MB zip, 33 MB database, different schema |
| Login | None seen | None seen |

Issues appear about every two weeks. Issue 3084's files return 404 for now, which gives a clean "not published yet" signal.

**One pass:**

1. Read each domain's listing. Keep issues at or above `IFIC_MIN_ISSUE`.
2. Fetch any issue not stored yet, oldest first, so diffs run in publication order.
3. Send `HEAD` for the newest issue. A changed ETag means ITU republished it, and the file is stored as a new revision.
4. Verify: byte count, size limits, zip CRC, exactly one database, Access file header.
5. Move it atomically to `data/ific/<domain>/<issue>/<sha12>/`. Files are never overwritten.
6. Commit the `artifact` row and `issue.fetched` together.

**Schedule.** `IFIC_SYNC_CRON` takes a standard cron expression, in UTC. The default, `0 */6 * * *`, runs every 6 hours. The `sync` service runs it in-process, so containers need no system cron. A brand new install syncs at once rather than waiting for the first slot. To use a system crontab instead, call `python -m ific_guard.cli sync`, and do not run the `sync` service's schedule alongside it.

**Upload.** `POST /issues/upload` takes a multipart `file`, either an `.mdb` or `.accdb`, or a `.zip` containing exactly one. ITU-style names identify it (`ific3074` is space, `brific3076` is terrestrial). For any other name, send `domain` and `issue_no` as form fields. The same exact file uploaded twice is stored and screened once, and an uploaded issue is not downloaded again.

```bash
curl -H "X-API-Key: $IFIC_API_KEY" -F file=@ific3074.zip localhost:8001/issues/upload
```

The hash is taken from the file as supplied, so the same issue given as an `.mdb` and as a `.zip` counts as two revisions. Cases are not duplicated if that happens, because they are matched by fingerprint.

**Failing visibly matters most here,** because a broken sync otherwise looks the same as "no new issue":

| Situation | Behaviour |
|---|---|
| Listing loads but no issues can be read (page redesign) | Raises `ListingChanged`; the run is marked failed and ops is alerted |
| One domain is down | The other still syncs; the run is `partial` |
| Any errors in a run | Retry after 15 minutes rather than waiting for the next slot; at most one sync alert per day |
| No issue for over 21 days (normal gap is 14-17) | `GET /status` reports `stale: true`. It does not raise an alert yet |
| Corrupt, truncated or oversized file | Rejected before anything becomes visible |
| Download link outside `itu.int` | Refused |

**Use of ITU's service.** The space page describes this as a free service "on a trial basis until further notice". Polling every 6 hours for files published every two weeks is light. Read ITU's Terms of Use before any use beyond the hackathon, and do not redistribute the files; `files/` and `data/` are git-ignored.

## 5. Screening

A rule takes a parsed issue and returns hits:

```python
class Rule(Protocol):
    id: str
    def run(self, issue: SpaceIssue) -> Iterable[Hit]: ...
```

New checks plug in here, including the pfd engine and special-interest station overlap.

| Rule | Fires when | Severity |
|---|---|---|
| `fin-named-by-br` | Tier 1: `FIN` appears in `provn` or `tr_provn` for an in-scope notice | High |
| `m4-no-space-to-earth` | A visible satellite transmits in a band with Finnish terrestrial or passive use and no space-to-Earth allocation in `data/national/m4_bands.csv` (built by `tools/build_m4_bands.py`) | Medium; high for a passive band |

- **Scope:** API/A and CR/C notices, with suppressions skipped.
- **Visibility:** GSO from 47°W to 97°E. Non-GSO reaching at least 55° latitude. Missing orbit data keeps the notice in, following the conservative principle.
- **Re-flagging:** the same content in a later issue updates `last_issue` and stays silent. Changed content reopens the case for review and notifies again.
- **Comment deadline:** IFIC date plus 4 months. It is an estimate, and the email says so.

**Severities are placeholders** until the ranking in ARCHITECTURE.md section 4.7 replaces them.

## 6. Notifications

`notifier` works in two steps, so an SMTP outage never blocks event processing: an event creates a `notification` row, and a separate loop sends what is due.

- **Experts:** one digest per issue, ranked, filtered by `IFIC_NOTIFY_MIN_SEVERITY`, showing notice IDs, deadline, review link, source URL and file SHA-256. No new cases means no email.
- **Operators:** sync failures and dead events.
- **Backends:** `console` (default), `file` and `smtp`. Real mail needs an explicit setting.
- **Retries:** exponential backoff, 6 attempts, then `failed` and visible in `GET /notifications`.
- **Known limit:** a crash between sending and recording can send a duplicate. That is better than losing an alert.

## 7. Security

- Write endpoints require `X-API-Key`, and stay closed if no key is set.
- Compose binds ports to localhost. A shared key is not enough for public exposure: production needs SSO and per-reviewer identity, so that review decisions can be attributed.
- ITU files are untrusted. Zip paths are reduced to a base name and extracted bytes are capped.
- Secrets come from the environment only.

## 8. Running it

```bash
uv sync
cp .env.example .env                 # then set IFIC_API_KEY
uv run python -m ific_guard.cli init-db

uv run uvicorn ific_guard.sync.app:app --port 8001
uv run uvicorn ific_guard.screening.app:app --port 8002
uv run uvicorn ific_guard.notifier.app:app --port 8003

uv run pytest
```

To skip a download, load a local copy with `uv run python -m ific_guard.cli import files/ific3083.zip`, or upload it (section 4). Full stack: `docker compose up --build`.

With the default `IFIC_MIN_ISSUE=3074`, the first sync downloads about 20 zips. The space ones are 20-60 MB each.

## 9. Current status

Per-issue evidence is now retained in the additive `case_occurrence` table.
Each row links an artifact to its cross-issue review case and stores the exact
hit from that artifact's latest successful screening. Re-screening replaces
only that artifact's occurrences, atomically with case updates. Run
`python -m ific_guard.cli init-db` on existing installations to create the table,
then re-screen imported artifacts to backfill it. Exports continue evaluating
the selected source directly without changing review state or notifications.
Processing-order tests cover 3074 alone, before 3083 and after 3083; the 3074
CSV/JSON stays identical. The suite now passes 68 tests.

**Verified**

- Automated tests pass, using fake servers and no real mail.
- All three services as separate processes on SQLite, against live ITU: both 3083 files fetched in 45 s, 39 cases opened (9 high, 30 medium), one digest written to a file, in 64 s overall. The downloaded space zip's SHA-256 matches `files/ific3083.zip`.
- On Postgres through Compose, against live ITU: sync run `ok`, the same 39 cases as SQLite, one digest written to a file. Re-screening the issue added no cases and no email.
- Uploads with the real files, on SQLite: `brific3076.mdb` and `ific3074.zip` were accepted, a repeat upload was recognised, and a request with no key got 401. Space 3074 screened in under a minute at about 700 MB peak memory.
- Cron, on SQLite with an every-minute schedule: runs started on the minute with no errors.
- Discovery finds Space and Terrestrial 3074-3083 with `IFIC_MIN_ISSUE=3074`, and downloading Space 3074 and Terrestrial 3076 directly gave the same hashes as the shared copies.

- Merged code at `integration/wave-2`, with the export, M4 table, station rule, pfd engine, P.1546 engine, draft letters and frontend: 446 Python and 31 frontend tests pass, and the Docker image builds with all rules, services and data files. Real services took Space 3074 and Terrestrial 3076 by upload through to a digest with no errors. Space 3074 gives 106 cases. The full Compose stack has not been run on it, and the pfd and P.1546 engines are not yet connected to any rule.

**Open or not yet verified**

| Item | Detail |
|---|---|
| **One unexplained download failure under Compose** | One of two runs ended `partial` with `could not fetch space issue 3083`; the error text was lost, and the next run was clean. It may have been a network problem, but that is unconfirmed. The failure alert fired and the other domain still synced. If it recurs, read `errors` from `GET localhost:8001/runs` |
| Real SMTP | Tested with a mocked client only |
| A full first sync | With `IFIC_MIN_ISSUE=3074` this fetches about 20 zips. Each path was tested, but not that whole run |
| Cron and upload on Postgres | Tested on SQLite only so far |
| Case accuracy | The 39 cases have not been checked by an expert or compared with Traficom's results |

**Known gaps**

| Gap | Effect | Fix |
|---|---|---|
| Terrestrial has no rules | Files sync, but report `no_rules`, deliberately not "no concerns" | Land-mobile adapter and P.1546 engine |
| Cases span issues | A case seen in two issues counts once, so a digest or count for one issue can omit it. **Export per issue, not from "new" cases** | Ticket 03 |
| Older issues untested | The brief says all existing issues must be evaluable. Space discovery looks back 3 years, and older databases may differ | Ticket 15. Upload works as a way in meanwhile |
| No beam coverage or pfd check | `m4-no-space-to-earth` over-flags and cannot confirm an exceedance | pfd engine, then GIMS contours |
| AP30, AP30A, AP30B not screened | The brief puts them in scope; issue 3083's plan tables are empty, so this is untested | Add notice handling using an issue that contains them |
| DuckDB store not connected | Rules read the `.mdb` directly | Load `schema.sql` tables inside `screening` |
| Tables made with `create_all` | Schema changes need manual work | Alembic |
| `access-parser` is a young library | Parsing errors could go unnoticed | Compare row counts against `mdbtools` on 3074 and 3076 |

## 10. Next steps, in order

The full breakdown is in `.scratch/ific-guard-delivery/map.md`.

1. Process Space 3074, which is evaluated separately, and export its cases.
2. Add a special-interest station overlap rule.
3. Add the pfd engine as a rule, which is what allows a case to say a limit is exceeded.
4. Add the terrestrial land-mobile adapter, the diff between issues, and P.1546 for Terrestrial 3076.
5. Add LLM explanations and draft letters to the case detail. The review UI in `frontend/` already uses the services.

After the hackathon: Alembic, SSO, staleness alerts, a stuck-event view and metrics.

## 11. Questions for Traficom

Added to ARCHITECTURE.md section 9:

1. Who should receive the email, and would they want a digest or also immediate alerts for high-severity cases?
2. Would ITU's terms allow automated downloads and retention of these files in production?
3. Is the 4-month comment window right for every section in scope, including API/A?
4. Do you provide a template for the 3074 and 3076 results? The brief says "separate file(s) to be provided".
5. Terrestrial 3075, 3076 and 3083 hold fixed and mobile notices from Russia and Estonia only among the five neighbours. Is coordination data (`fxm_coord`), which also names Sweden and Norway, what matters for those countries?
