# IFIC Guard frontend

The review UI for IFIC Guard: the latest ITU release and its results, on-demand file analysis, run history, and expert review of findings.

```bash
npm install
npm run dev     # http://localhost:5173
npm test        # file checks, pfd maths, severity rules
npm run build   # type-check and production build
```

## Sample mode

There's no pipeline or API yet, so `src/api/mock.ts` serves sample data and a banner says so on every page.

| Part | Status |
|---|---|
| Latest issue, findings and calculations | Real output of a one-off screen of real ITU files (3083, 3074, 3076). Screening flags, not regulatory findings |
| File checks (type, ZIP contents, SHA-256, duplicate detection) | Real, and run in the browser |
| Upload and run progress | **Simulated.** The file isn't uploaded or analysed, and the run ends by saying so |
| ITU monitor | **Not running.** The latest release was checked by hand |
| Review decisions and letter edits | Saved in this browser only |
| Draft letters | Fixed template. No AI yet |

Severity rules are starter values for the demo, listed on the Rules and data page.

To rebuild the sample data from an IFIC file, see `scripts/export_sample.py` (needs `access-parser pandas openpyxl`). The downloads aren't in the repo; get them from ITU using a browser-style User-Agent.

## Connecting the backend

Implement the `Api` interface from `src/api/types.ts` over HTTP, and export it from `src/api/index.ts`. No page imports the mock directly. Suggested endpoints:

| Method and path | `Api` method | Notes |
|---|---|---|
| `GET /issues` | `listIssues` | Issue summaries, including the funnel and known limitations |
| `GET /monitor` | `getMonitor` | Scheduler state and the latest known ITU release |
| `GET /issues/{id}/findings` | `listFindings` | Ranked by the backend |
| `GET /findings/{id}` | `getFinding` | |
| `PATCH /findings/{id}/review` | `updateReview` | `{status?, note?, letter?}`; the server appends the audit history |
| `GET /runs`, `GET /runs/{id}` | `listRuns`, `getRun` | Polled every 500 ms while running |
| `POST /runs` | `createRun` | Multipart: `file`, `sha256`, `domain`, `issue` |
| `GET /files/{sha256}/issue` | `findIssueByHash` | 404 when the file is new |
| `GET /reference/sources`, `GET /reference/limits` | `listReferenceSources`, `listLimits` | |

Types mirror `Finding` in `ARCHITECTURE.md`, with units in field names. The server has to re-check uploaded files, because browser checks are only a convenience. Real auth is needed before this holds real assignments.

## Not built yet

- Backend, scheduler, and notifications when a new issue lands
- Sign-in, roles, and a server-side audit log
- Comparing issues, and neighbour trends for the terrestrial side quest
- Letters as `.docx`, and AI-written explanations with a number and citation check
- Evaluation files in Traficom's format, once they confirm it
