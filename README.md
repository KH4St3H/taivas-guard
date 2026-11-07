# IFIC Guard

IFIC Guard screens each ITU BR IFIC (space and terrestrial) for items that could matter to Finland, so a spectrum expert sees a short, ranked list with the evidence behind each item. Built for the Traficom challenge at Since AI 2026.

It raises **possible concerns for expert review**. It doesn't decide that a filing breaks a regulation, and it sends nothing to the ITU or to another administration.

## What it does

1. **Fetches issues.** A cron schedule downloads new Space and Terrestrial IFICs from the ITU. You can also upload an `.mdb` or a `.zip` containing one.
2. **Screens them.** Deterministic rules run against the Finnish reference data. The results are the same for the same input, and no language model takes part.
3. **Notifies.** One digest email per issue, listing new or changed cases.
4. **Supports review.** A web UI shows each case with its evidence, a satellite reach map and a paged station list. The expert accepts or rejects it and edits a local draft, which is never sent. The guarded drafting service is available separately through the API; the UI is not yet connected to it (ticket 25).

| Rule | Domain | Raises a case when |
|---|---|---|
| `fin-named-by-br` | Space | The ITU's own data names Finland on a filing |
| `m4-no-space-to-earth` | Space | A satellite that can reach Finland transmits in a band where Regulation M4 gives no space-to-Earth allocation |
| `station-rx-overlap` | Space | A transmission overlaps the RX or TX band of a Traficom special-interest station. Each station gets the pfd result at its coordinates, and severity follows the strongest one |
| `pfd-gso-art21`, `pfd-gso-app5` | Space | Calculated GSO power flux-density against Article 21 limits and Appendix 5 coordination triggers |
| `pfd-ngso-art21`, `pfd-ngso-app5` | Space | The same for non-GSO, as an upper bound and a one-day flight of the notified orbit |
| `pfd-gso-cept`, `pfd-ngso-cept` | Space | ECC Decision (25)02 PFD condition in 862-870 MHz, kept distinct from RR limits and coordination triggers |
| `custom-<id>` | Space | A saved, versioned expert rule matches its frequency, direction, orbit, administration, provision and M4 conditions; severity is configured by its author |
| `terrestrial-p1546` | Terrestrial | ITU-R P.1546-6 field strength on the Finnish boundary, for land-mobile notices from Russia, Sweden, Estonia, Norway and Denmark |
| `terrestrial-not-calculated` | Terrestrial | A nearby notice can't be calculated, for example with no antenna height |

### Severity of station cases

This is the project's choice, not Traficom's. A `station-rx-overlap` case takes the strongest evidence at any of its stations:

| Evidence at a station | Severity |
|---|---|
| pfd calculated at the station's coordinates is above the limit (GSO), or a sample from the one-day flight is (non-GSO) | High |
| The same, but an input or the station's location is flagged | Medium |
| A calculated value within 3 dB below the limit, a non-GSO upper bound within 3 dB of the limit or above it, or no calculation for part of the band | Medium |
| Calculated more than 3 dB below the limit at every station, an upper bound more than 3 dB below, or the satellite below every station's horizon | Low |

A non-GSO upper bound has no location, so it applies to the filing and is never given as a value at a station. For a TX match, the station's coordinates are not where the band is received, and the case says so. pfd cases list the same stations, and `special_interest` adds the configured boost to their score.

## How to run it

You need Docker with Compose. The first full sync with `IFIC_MIN_ISSUE=3074` downloads 20 issues in about 3 minutes, then screens them in about 8 minutes, and uses about 2.3 GB of disk.

```sh
cp .env.example .env     # set IFIC_API_KEY: openssl rand -hex 32
docker compose up --build
```

- Sync API: <http://localhost:8001>
- Screening API: <http://localhost:8002>
- Notifier API: <http://localhost:8003>

A new install syncs at once, then follows `IFIC_SYNC_CRON`. Keep `IFIC_EMAIL_BACKEND` at `console` or `file` unless you mean to send real email. The `file` backend writes to `data/outbox/` in the `ific-data` volume.

To load a file yourself:

```sh
curl -X POST -H "X-API-Key: $IFIC_API_KEY" -F file=@ific3074.zip http://localhost:8001/issues/upload
```

For the review UI (the services must be running):

```sh
cd frontend && npm install && npm run dev    # http://localhost:5173
```

To work on the Python code, with Python 3.11 to 3.13:

```sh
uv sync
uv run pytest
IFIC_SHARED_DATA=/path/to/ific-files uv run pytest    # adds tests that read the real issues
```

To export one issue for evaluation, first commit all changes so the checkout is clean. `--allow-dirty` permits exploratory exports and records their actual state; do not use it for submission. Export into an ignored staging directory when generating multiple issues, then copy the finished set into `outputs/` so one export does not dirty the tree before the next:


```sh
python -m ific_guard.cli export --domain space --issue 3074 --out data/evaluation-stage/ific_3074
python -m ific_guard.cli export --domain terrestrial --issue 3076 --out data/evaluation-stage/ific_3076
```

[docs/demo.md](docs/demo.md) is the rehearsed demo script.

### Screening endpoints

- `GET /rules`, `POST /rules`, `PUT /rules/{id}` and `POST /rules/preview`: inspect, author, version and preview custom rules.
- `GET /cases/{id}/stations` and `/cases/{id}/stations.csv`: recompute the complete matching station list with filtering/pagination or CSV; stored cases retain counts and a capped sample.
- `GET /cases/{id}/coverage`: satellite reach geometry and available PFD estimates. This is an approximate reach map, not a beam footprint or a confirmed interference area.
- `GET /cases/{id}/draft`: guarded draft service; optional model rewrite with deterministic fallback. UI drafts currently remain browser-local.

## Inputs

| Input | Source | Where |
|---|---|---|
| Space IFIC `.mdb` | ITU, or upload | Downloaded at run time, not in the repository |
| Terrestrial IFIC `.mdb` | ITU, or upload | Downloaded at run time, not in the repository |
| Frequency allocation table (Regulation M4) | Traficom open-data API | `data/national/` |
| Special-interest stations (synthetic) | Traficom | `docs/challenge/` |
| Finnish restrictions in each band: prohibitions, reserved use, military or government use, RR footnotes cited | Traficom open-data API, `Comment` and `Sub_band_usage` | `data/national/m4_bands.csv` (`restrictions`, `national_use`, `rr_footnotes`) |
| RR Article 5 footnotes naming Finland (16) | ITU Radio Regulations 2024, Volume 1, extracted by `tools/build_rr_footnotes.py` | `data/national/rr_footnotes_finland.json`, with a PDF page per footnote |
| Real Finnish earth stations named in the frequency table | Traficom open-data API | `data/national/fin_earth_stations.csv`; the receiving site at Sodankylä Tähtelä is protected |
| Article 21 and Appendix 5 limit masks | ITU Radio Regulations | `data/masks/limit_masks.json`, with a citation on each row |
| T/R 25-08 indicative thresholds | CEPT | `data/masks/field_strength.json` |
| ECC Decision (25)02 pfd condition, 862-870 MHz | CEPT | `data/masks/cept_masks.json`, with the page cited, and the CEPT values that can't be checked and why |
| Finnish boundary and land mask | Natural Earth | `data/masks/` |

## Outputs

### Regulation M15 scope decision

M15 is excluded from this demonstrator (ticket 34). The brief names it as an optional dataset in section 05. We use M4 for national allocation comparisons and the supplied station bands for special interests. Adding a low-severity note solely because a satellite frequency overlaps a licence-exempt band would add noise without a verified satellite-to-receiver protection criterion. No M15-specific comparison or protection coverage is claimed; future support needs sourced applicability and technical criteria.


| Output | What it is |
|---|---|
| [`outputs/ific_3074/`](outputs/ific_3074) | Space 3074: 175 cases (43 high, 94 medium, 38 low) |
| [`outputs/ific_3076/`](outputs/ific_3076) | Terrestrial 3076: 29 cases (1 high, 22 medium, 6 low) |
| [`outputs/hand-check.md`](outputs/hand-check.md) | Independent recheck of a sample, with the false positives and misses we could measure |
| [`outputs/neighbour-trends.md`](outputs/neighbour-trends.md) | Counts of neighbouring notices across Terrestrial 3074-3083 |
| Review cases | Stored in the database, served by the Screening API and the UI |
| Digest email | One per issue |
| Draft letter | `GET /cases/{id}/draft`; marked as a draft and never sent |

Each export folder holds `cases.csv`, compact `cases.json` (with the full evidence and assumptions), `manifest.json` (source hash, Git commit and dirty state, code hashes, configuration) and `verification.md`. Terrestrial also has `funnel.json`, which shows how many notices each filter removed. See [`outputs/README.md`](outputs/README.md).

Traficom accepts this: they prefer Xls/csv or doc/pdf for quick evaluation, accept any open machine-readable format, prefer JSON over MDB, and named no mandatory fields.

## What was verified

Earlier integration verification at `ba6f09a` used an empty database with `docker compose up --build`; these are historical checks, not a claim that the current submission was rehearsed again:

- The scheduled first sync finished `ok`, with all 20 issues (Space and Terrestrial 3074-3083) screened and a digest written for each. No real email was sent.
- A second empty database, loaded by upload (`ific3074.zip`, `brific3075.mdb`, `brific3076.mdb`), gave the same cases as the download. The only differences were the source URL, and the hash and size of whichever file was uploaded.
- A demo was rehearsed from a clean start, including a draft for each of the 224 cases in 3083. This ran just before the TX protection was merged, which changes station links but not the steps.

The rehearsals found faults that the unit tests had not, all now fixed:

- every terrestrial issue failed in the container
- one bad date cell lost all of Space 3077
- draft letters crashed on most pfd cases
- letters described an upper bound as an exceedance

The earlier hand check recomputed 13 pfd results from raw rows with no difference above 0.0001 dB. It recomputed four station margins, two GSO and two non-GSO, from raw rows and the sheet's coordinates, with no difference above 0.000001 dB, and found no station exceedance that the calculation over Finland didn't also show. All 21 P.1546 values match the upstream reference code in Octave to within 0.006 dB. Those sweeps predate the notification-stage and non-Earth-orbit fixes and do not establish current recognition accuracy. See [`outputs/hand-check.md`](outputs/hand-check.md).

**Accuracy against expert judgement has not been measured.** No result has been compared with Traficom's own assessment.

## Known limitations

### False positives

- **Worst-case gain.** Every pfd result applies the maximum notified gain towards Finland, as Traficom said to assume (beams "are not relevant", Discord, 2026-11-07). So "exceeds" always means under worst-case assumptions. `s_beam` holds no boresight position for any of the 2,304 rows in 3074, so we can't say how many of the high pfd cases a real beam would reach.
- **Frequency-only M4 rule.** `m4-no-space-to-earth` ignores power, antenna direction and location. A slight edge overlap counts, so it over-flags by design.
- **Station cases where nothing is calculated.** `station-rx-overlap` uses the pfd result at each station, but a band with no limit mask, or one needing X or Y, has no calculation and stays at medium. On 3074 that is the strongest evidence in 17 of 51 station cases, and covers 2,063 of 4,975 station links. Antenna direction isn't used: the satellite's isn't notified, and the sheet has few receive gains (ticket 02 question 14). A slight edge overlap counts.
- **Filings around the Moon are set aside.** In 3074, LUNAR-R1 to R5 and USASAT-MK1 previously generated six M4 and six station cases. They now generate none of those cases: non-Earth reference bodies are excluded from Earth visibility screening, including custom rules. The pfd rule retains explicit unevaluated evidence. A missing reference body is still kept as a precaution.
- **Synthetic stations.** Traficom's station list is synthetic, so station cases show that the rule works, not real interference.

### Things not evaluated

- **5,429 non-GSO records in 3074 have no calculation** because their masks need parameters X or Y, which the IFIC data can't supply (5,398 and 31). They are counted, and shown for expert review.
- **Technical space rules screen API/A and CR/C.** The BR-names-Finland rule also screens notification-stage (`N`) filings naming FIN, including 3074 notices 125500060, 125500061 and 125500066. These require expert review of the cited provisions; no response deadline is assumed. AP30, AP30A and AP30B remain unsupported.
- **Only Space database version 10 screens.** Issues in versions 8, 7 and 5 are rejected with a clear error, so "all existing issues" isn't met for older issues. Space discovery walks back to 1998, and 3074-3083 are all version 10.
- **Terrestrial covers land mobile only.** Other services and terrain (`pathinfo = 1`) aren't calculated.
- **Article 22 epfd isn't calculated.** Neither is the sum of several satellites at one point.
- **Finnish restrictions are shown, not weighed.** Bands on M4 and station cases list Finland's restrictions, military or government use and the RR footnotes naming Finland, verbatim. Severity doesn't change, because Traficom hasn't said how they should count. The fields retain the source text and citations; they do not independently establish regulatory applicability.
- **The Sodankylä earth station has no coordinates.** Neither Traficom's table nor the IFICs give them, so it is matched by frequency only. It appears in 19 station cases on 3074, as no calculation unless a non-GSO bound below the limit applies everywhere (one case, SUNCET). The two transmitting sites are listed but not protected.
- **The RR footnote file is extracted from the PDF text.** Spacing artefacts are kept, and each entry should be checked against its page before a letter relies on it.
- **Finnish satellites aren't protected.** The brief also asks about systems that could interfere with Finnish satellites, and no rule does this yet.
- **No space-side trends.** `outputs/neighbour-trends.md` covers terrestrial only.

### Assumptions an expert should check

- **`pwr_ds_max` in dBW/Hz** rests on a secondary note. The primary ITU Space Preface could not be retrieved. Each pfd case states this.
- **`pep_max` caps power in the reference bandwidth**, treated as dBW. In 3074 it lowers the worst margin of 74 of 1,234 records and raises none.
- **Inferred field meanings.** `orbit_lnk`, `long_asc`, `phase_ang`, `fxm_coord`, `action`, `target`, `pwr_eiv` and `pwr_xyz` are inferred from the data, because the ITU ReadMe could not be read.
- **Non-GSO flights** are two-body with no J2, over one day, for one satellite per orbit shape from an assumed start. They can miss the worst case. The upper bound covers the notified altitudes for any node, phase or epoch, but it may describe a state the satellite never occupies.
- **T/R 25-08 thresholds are indicative, and all 21 comparisons in 3076 are provisional.** The document doesn't say whether they apply on the Russian border, and no bilateral agreement was checked. Above 470 MHz, where T/R 25-08 stops, the 400-470 MHz Annex 1 threshold is applied up to 4000 MHz, as Traficom said. Its bandwidth conversion lifts the threshold by up to about 26 dB for wide channels. Annexes 3 and 4 aren't used.
- **The 300 km terrestrial screen and the Finnish border polyline are engineering approximations.** On 3076 the polyline dropped nothing within 300 km of the Natural Earth boundary and kept 7 notices at about 306 km.
- **Draft letters say "limit" for every comparison**, including Appendix 5 triggers and T/R 25-08 thresholds. An expert should correct the term when editing a draft.
- **API/A and CR/C comment deadlines are estimates**: publication date plus four months. Notification-stage Finland-named cases have no assumed response window.

### Data and operations

- **Article 11 totals don't reconcile with notice rows**: 106 unreconciled in 3075 and 29 in 3076.
- **Invalid dates read as null.** Space 3077 has 22 such cells in `grp`; each logs a warning.
- **Severity scoring.** Station-linked PFD evidence can activate the configured special-interest boost. The 3 dB watch band and scoring weights are project choices, not regulatory criteria; each scored case lists its reasons.
- **The MDB parser `access-parser` is a young library**, and row counts haven't been compared with `mdbtools`.
- **A first sync sends one digest per issue**, so a low `IFIC_MIN_ISSUE` sends a burst of them.
- **Not tested:** real SMTP (mocked only), the language-model path with a real model, and ITU's own PFD software as a cross-check.
- **Security is minimal.** The API key is a basic guard and the ports bind to localhost, so this isn't ready to face the internet.
- **Schema changes** use `create_all`, with no migrations.
- **The normalised DuckDB store was deferred.** Rules read the `.mdb` directly. See [ARCHITECTURE.md](ARCHITECTURE.md) section 4.2.

## More documentation

- [ARCHITECTURE.md](ARCHITECTURE.md): pipeline, engines and principles
- [docs/services-architecture.md](docs/services-architecture.md): services, data flow and current status
- [docs/demo.md](docs/demo.md): demo script
- [frontend/README.md](frontend/README.md): the review UI
