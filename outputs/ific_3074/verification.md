# Space IFIC 3074 verification — 2026-11-07

## Result and reproduction

102 possible concerns: 8 high from `fin-named-by-br`, 2 high and 41 medium
from `m4-no-space-to-earth`, and 51 medium from `station-rx-overlap`. These are screening results, not a measured
interference assessment or an expert accuracy evaluation.

```sh
python -m ific_guard.cli export --domain space --issue 3074 --out outputs/ific_3074
python -m ific_guard.cli export --domain space --issue 3074 --out data/verify_3074
```

Both real-data runs produced byte-identical CSV and JSON files:

| File | SHA-256 |
|---|---|
| cases.csv | aa5e72ad7e225a765704e3ccad1199c250cadd5d8df6d893a570fd635d3bbb02 |
| cases.json | d2fed838893f6a0b684d478915452794cc1bcd3f057af1e2f9941d1bbf45f88f |

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
and a slight edge overlap counts: AST-NG-C-4's single station overlaps by 0.7 MHz. 61
stations with no receive frequency are skipped. Traficom's station data is synthetic.

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
The known 3.4–3.8 GHz M4 gap and missing pfd calculations remain tracked
separately; all are also stated in the manifest.

The regression suite at commit 4fe2874: **185 passed** on Linux, with two
dependency deprecation warnings. No notifications were delivered.
