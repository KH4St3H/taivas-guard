# Space IFIC 3074 verification — 2026-11-07

## Result and reproduction

106 possible concerns across 59 filings: 8 high from `fin-named-by-br`, 2 high
and 45 medium from `m4-no-space-to-earth`, and 51 medium from
`station-rx-overlap`. A filing can appear under more than one rule. These are
screening results, not a measured interference assessment or an expert accuracy
evaluation.

The earlier two-rule export had 51 cases. All 51 remain. The M4 table from
Traficom's API adds 4 and the station overlap rule adds 51. The station rule
checks frequency only, with no beam, power or geometry check.

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

The files were regenerated on macOS from a clean commit, using Space 3074 downloaded
directly from ITU, and took 35.35 seconds. The current three-rule export took 35.28
seconds, from the same verified file. Earlier measured export times were 70.53
and 54.73 seconds on a Windows machine.
An observed process peak working set during the first export was 774,938,624
bytes (739 MiB); this was sampled during execution, not a final peak measurement.
The second run used streaming MDB hashing and adds per-source-file code hashes
to the manifest. These provenance improvements did not change either case file.

## Five source-row checks

These five checks predate the M4 table and station rule. All five filings are
still in the export. They have not been repeated, and the new rule's cases were
spot-checked on Space 3083, not 3074.

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
The known 3.4–3.8 GHz M4 gap, missing station overlap and missing pfd
calculations remain tracked separately; all are also stated in the manifest.

The operational pipeline separately returned `status: done`, `opened: 51`,
`changed: 0` for artifact 1. Final regression suite: **392 passed** on macOS,
with one dependency deprecation warning. No notifications were delivered.
