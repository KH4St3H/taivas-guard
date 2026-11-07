# Space IFIC 3074 verification — submission refresh, 2026-11-07

## Current evaluation

175 possible concerns for expert review. Generated from clean Git commit `941282f644cf7f771c5e9a79d284990953f35f8c` with `dirty: false`, using a newly created SQLite database and isolated data directory. The manifests were generated in an ignored staging directory before replacing tracked outputs. The source commit is retained in the submitted history; the later artifact commit contains these files.

The Docker daemon was unavailable on this Windows machine. This refresh uses the application's importer, deterministic exporter and screening handlers directly, not a repeated Compose/cron rehearsal. Earlier Docker verification is preserved below as historical evidence. No real email is sent; the notifier uses the file backend. Custom-rule storage starts empty, so these evaluations contain built-in rules only.

| Rule | Previous tracked export | Refreshed export |
|---|---:|---:|
| `fin-named-by-br` | 8 | 11 |
| `m4-no-space-to-earth` | 47 | 41 |
| `pfd-gso-app5` | 2 | 2 |
| `pfd-gso-art21` | 16 | 16 |
| `pfd-ngso-app5` | 6 | 6 |
| `pfd-ngso-art21` | 52 | 52 |
| `pfd-ngso-cept` | 0 | 1 |
| `station-rx-overlap` | 51 | 46 |

| Severity | Previous | Refreshed |
|---|---:|---:|
| high | 30 | 43 |
| medium | 123 | 94 |
| low | 29 | 38 |

The total changes from 182 to 175:

- Ticket 22 adds three `fin-named-by-br` cases: 125500060, 125500061 and 125500066. All identify the notification stage, retain the source provision, and have a null comment deadline. The BR rule now has 11 cases; technical rules still receive only A/C notices.
- Ticket 23 removes six M4 and six station cases: LUNAR-R1 through LUNAR-R5 and USASAT-MK1. None of those networks appears under either rule now. PFD still records their unevaluated non-Earth geometry; it does not claim they are harmless.
- Previously merged CEPT support adds one high `pfd-ngso-cept` case for CSN-SSO. This is an ECC condition, distinct from RR limits and Appendix 5 triggers.
- Previously merged Finnish earth-station protection adds one low station case for SUNCET. The named receiving site has no coordinates; a sufficiently low filing-wide upper bound supports its status, not a calculated field at that site.
- Previously merged station-specific PFD evidence promotes nine station cases from medium to high (CSN-SSO, CHINASAT-H-60.5E, AST-NG-C-4, CHINASAT-G-33.5E, F-SAT-NG-15_B, USASAT-NGSO-8F, INSAT-COM(71E), ION SCV-025 and ION SCV-026), and moves eight from medium to low (FUNADE, LVI, USASAT-30T-1, KITASATS, STARERA-3, PUXING-1, ARGUS-CHN and JZ-3). These are evidence/ranking changes, not new expert-confirmed interference findings.
- Finnish restrictions and RR footnotes add annotations without a new rule or severity change. Stored station samples are capped at 100, with complete counts and an endpoint for the full list; the cap itself changes no case count. Compact JSON retains every calculation and source row and reduces the file from 31,473,700 to 21,805,392 bytes.

The two independently executed export runs have identical logical case records; the final run uses compact JSON. Both runs find exactly the three added notification cases and zero lunar M4/station cases. All RR PFD rule case counts are unchanged. No expert-labelled accuracy evaluation is claimed.

## Verification

The full backend suite with `IFIC_SHARED_DATA` pointing at the three real fixtures passed: **626 passed, zero skipped**. The frontend suite passed **40 tests**, and TypeScript checking plus the production build passed. A single upstream deprecation warning remains. The earlier Octave and independent hand checks below were not rerun during this refresh.

An additional isolated service check confirmed all three imported artifacts screen to `done`, both requested issues have stored occurrence counts and rule/severity identities matching their exports, and three digest files are produced. Case detail and guarded draft requests returned 200 for every represented rule family, including notification-stage and terrestrial missing-input cases; review acceptance returned 200. This exposed and fixed a terrestrial station-draft formatting bug, covered by a new regression. The fix affects correspondence, not the evaluation calculations recorded at the source commit. Later develop integration adds map/trend/storage features; final integrated test totals are recorded in README and the submission PR.

All output hashes were recomputed and verified:

| File | SHA-256 |
|---|---|
| `cases.csv` | `15df7d67b766648f5d5f0032aa9150df2dd4def8619be167fa33a0acad8f8056` |
| `cases.json` | `268ba11fc66ca21b827b8860a2325820565a6df1a451b9c0d70bff4d6245e872` |

Reproduce from a clean checkout: import Space 3074, Terrestrial 3075 and Terrestrial 3076 into a fresh database; export each requested issue into an ignored staging directory; verify the manifests; then copy both folders to `outputs/`. The default export refuses a dirty or unidentified code version; `--allow-dirty` is for explicit exploratory use. Raw files remain outside Git.

## Historical verification (superseded export)

# Space IFIC 3074 verification — 2026-11-07

## Current export (clean Compose run, code commit ba6f09a)

182 possible concerns: 30 high, 123 medium, 29 low. Exported in the screening container from an empty database after the scheduled first sync, which finished `ok`. The manifest's `code_version` is empty because the image has no Git history, but its 44 code hashes identify the code and match that commit.

| Rule | Cases |
|---|---:|
| `station-rx-overlap` | 51 |
| `m4-no-space-to-earth` | 47 |
| `fin-named-by-br` | 8 |
| `pfd-gso-art21` | 16 |
| `pfd-gso-app5` | 2 |
| `pfd-ngso-art21` | 52 |
| `pfd-ngso-app5` | 6 |

| File | SHA-256 |
|---|---|
| cases.csv | e1811b1b621bbf5a824ae50a7f869d6b1d2a3ced1ff980dc646fd6c7b10cc899 |
| cases.json | 7822f99e5fb14576f561edbd280c2cd59f65373e5ed0bf7d0f006a70a959ddbb |

A second empty database, loaded by uploading `ific3074.zip`, gave the same cases. The only difference was `source_url`. See `../hand-check.md` for the hand check.

Compared with the ticket 16 export (30 high, 124 medium, 28 low), the only change in rule behaviour is the `pep_max` cap on pfd power. In this issue, no record's worst margin rose and 74 of 1,234 fell. GSO Article 21 `exceeds` went from 613 to 605 calculations, and one non-GSO family moved from medium to low.

The sections below describe earlier exports unless they say otherwise.

### Effect of protecting TX frequencies

Traficom said "every TX is received in Finland" (Discord, 2026-11-07), so the station rule now matches RX and TX bands. Before and after were run on the same source, with no other code change:

| Measure | RX only | RX and TX |
|---|---:|---:|
| Cases, all rules | 182 | 182 |
| `station-rx-overlap` cases | 51 | 51 |
| Cases found only through TX | | 0 |
| Severity changes | | 0 |
| Station links across those cases | 2,839 | 4,975 |
| Distinct stations reached | 572 | 604 |
| Cases that gained a station | | 30 of 51 |

No case was added or lost. Of 63 visible families with downlinks, the other 12 have no case. Code separate from the rule, reading the sheet directly, found no RX or TX centre frequency inside their downlink ranges. That check uses centre frequencies, so it would not see a band that only overlaps at its edge; the rule itself does.

No case is TX-only, so these spot-checks use stations that matched only through TX inside an existing case. Each TX frequency is inside a space transmission (`emi_rcp` E) of the notice, and the station's RX frequency is not:

| Network | Notice | Station (sheet row) | TX, MHz | RX, MHz | Width | Group, range in MHz |
|---|---|---|---:|---:|---|---|
| NSL-1 | 117520318 | 628728 (381) | 18930 | 17920 | 110 MHz | 117805664, 18800-19040 |
| AST-NG-C-4 | 117520372 | 985264 (830) | 2509.7 | 2629.7 | 5 MHz | 124818514, 2500-2520 |
| USASAT-NGSO-3X | 123520029 | 614038 (287) | 17755 | 18765 | 55 MHz | 123644931, 17700-17950 |

## Earlier result and reproduction

106 possible concerns across 59 filings: 8 high from `fin-named-by-br`, 2 high
and 45 medium from `m4-no-space-to-earth`, and 51 medium from
`station-rx-overlap`. A filing can appear under more than one rule. These are
screening results, not a measured interference assessment or an expert accuracy
evaluation.

The previous export had 102 cases. All 102 remain. Using the M4 table built from
Traficom's API adds 4: F-SAT-NG-15_B, GD-B, USASAT-NGSO-3X and USASAT-NGSO-8F.

```sh
python -m ific_guard.cli export --domain space --issue 3074 --out outputs/ific_3074
python -m ific_guard.cli export --domain space --issue 3074 --out data/verify_3074
```

Both real-data runs produced byte-identical CSV and JSON files:

| File | SHA-256 |
|---|---|
| cases.csv | 4c0efb29e024431a5d2116910e2d6ea740e9be4590018c75be1305a6e69212e4 |
| cases.json | 96cfafa1d63a18c4bb959d1c476d9f87d104b925ffeca4071c4a75493a3695cf |

These hashes use LF line endings on every platform. Earlier values in this file
covered Windows line endings, so they did not verify after a git checkout; the
case content did not change.

The files were last regenerated on Linux from clean commit 4fe2874, which added the
station rule, using Space 3074 downloaded directly from ITU, and took 73.26 seconds.
The source hash is the same as in earlier runs. Before that they were regenerated on
macOS in 35.35 seconds. Earlier measured export times were 70.53
and 54.73 seconds on a Windows machine.
An observed process peak working set during the first export was 774,938,624
bytes (739 MiB); this was sampled during execution, not a final peak measurement.
The second run used streaming MDB hashing and adds per-source-file code hashes
to the manifest. These provenance improvements did not change either case file.

## Five source-row checks

Compared the exported fields with rows read directly from `ific3074.mdb`.
For the first three, joined `grp.grp_id` to `provn.grp_id` and confirmed the
notice association and `FIN`. For the final two, compared the transmit
frequency interval and orbit inclination against the exported band and
visibility reason. Representative rows are listed below; the JSON retains
the complete matched group lists.

| Network | Notice | Source rows checked | Conclusion |
|---|---|---|---|
| QATARGOV-G1-25.5E | 124520173 / 324520173 | `notice`: QAT, C, 9.6; `grp`: 124793424 → 124520173; `provn`: group 124793424, FIN, 9.21/C | Named-Finland trigger supported |
| HISPASAT-5-52.5W | 124520179 / 324520179 | `notice`: E, C, 9.6; `grp`: 124711730 → 124520179; `provn`: group 124711730, FIN, 9.11 | Named-Finland trigger supported; tier 1 does not require visibility |
| CHINASAT-G-33.5E | 124520184 / 324520184 | `notice`: CHN, C, 9.6; `grp`: 124793660 → 124520184; `provn`: group 124793660, FIN, 9.14 | Named-Finland trigger supported |
| CSN-SSO | 124545403 | `freq`: group 124747316, E, 116000–122250 MHz; `orbit`: 97.7900009155° | Overlaps current M4 116000–119980 MHz passive band (page 216); latitude reach 82.21° passes screening |
| USASAT-30-3 | 125545390 | `freq`: group 125743475, E, 1646.5–1660.5 MHz; `orbit`: 96.6999969482° | Overlaps current M4 1660–1660.5 MHz radio-astronomy band (page 136); latitude reach 83.30° passes screening |

All sampled notice publication dates are 2026-06-23. The estimated four-month
deadline is 2026-10-23; the historical evaluation should not imply these
deadlines are still open. M4 page references above are inherited from the
existing band CSV, not newly validated against the regulation PDF.

## Station rule checks

Compared three `station-rx-overlap` cases, the smallest, the median and the largest,
with `ific3074.mdb` and the Traficom spreadsheet, using code separate from the rule.
Up to three stations and two bands were sampled per case. Each sampled group is a
space transmission (`emi_rcp` E) overlapping the band, and each sampled station's
number, receive frequency and bandwidth match its sheet row.

| Network | Notice | Stations in case | Sampled group | Sampled stations |
|---|---|---|---|---|
| AST-NG-C-4 | 117520372 / 317520372 | 1 | 117788367, 2170-2200 MHz | 989650 (row 874), RX 2168.2 MHz, 5 MHz wide |
| YG-1 | 126545117 | 20 | 126662627, 8025-8400 MHz; 126662631, 9300-9800 MHz | 402006, 405674, 406317 (rows 188-190) |
| CSN-SSO | 124545403 | 348 | 125749495, 450-470 MHz | 289729, 289742, 289748 (rows 33-35) |

The rule compares frequency only. Location, power and antenna direction are not used,
and a slight edge overlap counts: AST-NG-C-4's single station overlapped by 0.7 MHz in this
earlier RX-only export, when 61 stations with no receive frequency were skipped. Now only 3 are
skipped, those with neither frequency. Traficom's station data is synthetic.

## AP30 coverage

The MDB `notice` table has 196 rows: 76 C / 9.6, 50 A / 9.1/IA,
65 N / 11.2 and 5 U / RS49. No AP30/AP30A/AP30B-labelled provision appears
in that table. The catalog's `ap30b_ref_agg`, `ap30b_ref_se` and
`ap30b_tr_res` tables each contain zero rows.
The `plan_pub` table also contains zero rows.

**AP30/AP30A/AP30B handling remains a gap.** These observations are not proof
that every plan publication associated with the circular is absent from
other ITU files. The exporter states that only API/A and CR/C are screened.

## Remaining limits

The export format is provisional pending Traficom's answer to ticket 02.
No independent MDB parser or expert case-accuracy check was available.
At that earlier export, the pfd engine was not connected to a rule. It now is; see
Current export. The manifest states the remaining limits.

The regression suite at commit ba6f09a: **554 passed** on macOS, including the tests that read real issues, with one
dependency deprecation warning. The frontend's 32 tests also pass. No real mail was sent.
