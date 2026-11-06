# ITU / Traficom primary-source findings (checked 2026-11-06)

**How to read this.** Tags such as `[P p.95]` resolve to URLs in [Sources](#sources) (page numbers are PDF pages). `[Inspected]` means read directly from the downloaded file: `[Z3074]` or `[Z3076]` opened with the pure-Python `access-parser` package on Linux, `[API]` from the live endpoint. Downloads were not kept, so re-run these checks. The `com_el`, `provn`, `pub_ssn` and `fxm_terra` counts were re-derived independently from fresh downloads and matched. `Derived` means my calculation or inference from cited text. `UNVERIFIED` means I could not confirm it.

## Key corrections for the team

| Team belief / brief | Finding | Source |
|---|---|---|
| Avoid MDB files | **Not possible for the public files.** Both mandatory public downloads are Access `.mdb` inside a zip. They can be read without Access or ITU software. | `[Inspected]` [Z3074], [Z3076] |
| ITU has an mdb-to-SQLite tool | **None found.** The likely source of the rumour: the full *terrestrial* database is natively SQLite, and BR ships a converter from the new SQLite structure back to the legacy structure. It does not touch space MDB files. | [TDB], [CR516], [TLEG] |
| Avoid ITU software | Allowed. The brief says "or direct database logic" and "or direct calculation logic". The v10 BR suite is Windows 10/11 only. | [BRIEF], [SW] |
| IFIC is "bi-monthly" | Every two weeks. | [BRIFIC], [SCHED] |
| G/N/S meanings | Nearly right: S is **specific** earth station, and T and R also exist. | [P p.96, p.112] |
| "Missions in the data" | No such schema term. Use class of station and nature of service (section 3). | [P p.106, p.176–178] |
| "Violation" | Wrong for most cases (section 8). | [RR1], [GSO] |
| Free files cover AP30 | **The free `ific3074.mdb` has no AP30/30A/30B filings.** Those are in other, subscription databases. | [IFICN], `[Inspected]` [Z3074], [CR511] |

## 1. IFIC mechanics

### Space BR IFIC

| Item | Finding | Source |
|---|---|---|
| Cadence | Every two weeks, under RR Nos. 20.2–20.6 and 20.15 | [BRIFIC] |
| Issue 3074 | Published **23.06.2026**; `[Inspected]` `notice.d_wic` agrees | [SCHED], [D26], [Z3074] |
| Free download | **Yes**, HTTP 200 without login: `ific3074.zip`, 60.8 MB, containing one `ific3074.mdb`, 286.7 MB | `[Inspected]` [Z3074] |
| Listing page | Year pages `demowicYY.html`; 2026 links `../ific10/ificNNNN.zip`, which resolves to `/sns/ific10/` | [DEMO], [D26] |
| Schema version | SNS v10 since 7 Jan 2025 (IFIC 3037); `[Inspected]` `srs_ooak.version_no=10` | [D26], [CR511] |
| Paid channel | The BR IFIC is "a paying service"; full issue via online app, ISO or DVD | [UG], [ISO] |
| Paid content | PDF Special Sections plus technical data: TSUM, AP8 results, EPFD input/results, MSPACEg, GIBC PFD results | [UG p.3] |
| Paid databases | `SRSXXXX.MDB` (non-plan), `IFICXXXX.mdb`, `SPS_ALL_IFICXXXX.MDB` (AP30/30A), `30B_XXXX.MDB` (AP30B) | [P p.77] |
| Free zip scope | Part I-S, II-S, III-S, API/A, CR/C, RES49, plus updated CR/C data if CR/D or CR/E is published | [IFICN] (2016 note) |
| Missing from zip | The cumulative SRS baseline. Use Space Explorer or a subscription. | [EXPL], Derived |

**Automated access.** The first plain `curl` to `demowic.html` got a "Request Rejected" page; a browser-style User-Agent worked. `[Inspected]`

**Parts and Special Sections** (all from [P p.10–22]):

| Name | Content |
|---|---|
| Part I-S | Notifications received; acknowledgement of receipt |
| Part II-S | Assignments to be recorded in the Master Register, with findings |
| Part III-S | Assignments returned, generally unfavourable findings |
| API/A | Advance publication, No. 9.2B |
| API/B | Commenting administrations under 9.3, report under 9.4 |
| API/C | Derived from 9.30 under 9.1A/9.2C. Both provisions are now `SUP - WRC-23` [RR1], so treat as legacy. |
| CR/C | Coordination requests, Nos. 9.7–9.14 and 9.21, published under 9.38; also Article 7 of AP30/30A |
| CR/D | Status of coordination under 9.11–9.14 and 9.21 (No. 9.53A) |
| CR/E | Inclusion requests under No. 9.41 |
| AP30/E, AP30A/E | Regions 1 and 3 List. Part A proposals (§4.1.5), Part B (§4.1.15), Part C cancellations |
| AP30-30A/E | Region 2 Plan modifications, Parts A–D |
| AP30-30A/F | Article 2A guard-band space operation functions |
| AP30B/A6A, /A6B, /A7 | AP30B Article 6 and Article 7 |
| AP30/P, AP30A/P, AP30B/P | Plan entries by WRC decision |
| RES49 | Administrative due diligence |
| RES4, RES8, RES35, RES42, RES148, RES170/A6A, RES552 | Other resolution-specific sections |

**Observed in 3074** `[Inspected]` [Z3074]:

- `pub_ssn`: CR/C 64, CR/C rev M 12, CR/D 58, API/A 41, API/A rev M 7, API/A rev S 2, API/B 22, CR/E 14, RES49 5.
- `com_el.prov`: 11.2 = 51, 9.1/IA = 50, 9.6 = 40, RS49 = 5. No AP30 notices.
- `com_el.ntc_type`: N 92, G 42, S 12.
- `notice` has 196 rows; `prov` 9.6 = 76, 11.2 = 65, 9.1/IA = 50, RS49 = 5.
- Finland is the notifying administration of no entry in `com_el`.

### Terrestrial BR IFIC

| Item | Finding | Source |
|---|---|---|
| Issue 3076 | 21.07.2026 | [TBR] |
| Free extract | **Yes**: `brific3076.zip`, 2.4 MB, containing `brific3076.mdb`, 25.1 MB | `[Inspected]` [Z3076] |
| Also free for 3076 | `Article11-Index/ific3076.pdf`, `GE84_365.pdf`, `GE06L_167.pdf`, `RR921C1116.pdf`, `ReadMe_3076.pdf` | [TBR] |
| Full edition | ISO with TerRaQ, TerRaNotices, and SQLite `BRIFIC_nnnn.db3` plus `GLAD.db` | [TBR], [TDB] |
| 3076 counts | Article 11: Part I 2415, Part II 1051, Part III 44, total 3510; GE06L/167 16; GE84/365 472 | [RM3076] |

## 2. Database schema

**Space.** The authoritative dictionary is **Preface Section III Chapter 1, October 2026 edition** [P p.77–125]. The `sns_dbv91.pdf` still linked from [BRIFIC] is the older v9.1 schema. Formats use `X` alphanumeric and `9` digit [P p.78]. Each notice is relational. Some names in the request do not exist: there is no `mask` or `pfd` table.

Join path `[Inspected]`: `notice(ntc_id)` → `s_beam(ntc_id, emi_rcp, beam_name)` → `grp(grp_id, ntc_id, emi_rcp, beam_name)` → `freq`, `emiss`, `srv_cls`, `srv_area`, `provn`, `e_as_stn` by `grp_id`.

| Table (3074 rows, `[Inspected]`) | Key fields | Meaning and units [P page] |
|---|---|---|
| `com_el` (146) | `ntc_id, adm, ntwk_org, sat_name, long_nom, ntc_type, prov, ntf_rsn, st_cur, wic_no, wic_part, act_code, d_rcv, stn_name, ctry` | Summary per notice. `long_nom` is degrees, West negative [p.112] |
| `notice` (196) | `ntc_id, prov, adm, ntwk_org, ntf_occurs, ntf_rsn, st_cur, act_code, d_rcv, wic_no, d_wic, ntc_type` | General notice information. Has no `sat_name`. [p.95–96] |
| `pub_ssn` (225) | `ntc_id, ssn_ref, ssn_no, ssn_rev` | Special Section reference [p.109] |
| `s_beam` (2304) | `gain, gain_x, freq_min, freq_max, emi_rcp, beam_name, pwr_max_4k, pwr_max_1m, bore_long, bore_lat` | `gain` dB isotropic; `emi_rcp` E or R; `pwr_max_*` peak e.i.r.p. if 9.11A applies [p.103–104] |
| `grp` (34365) | `grp_id, ntc_id, noise_t, bdwdth, freq_min, freq_max, d_prot_eff, d_reg_limit, pfd_pk_7g, elev_min, prov, adm_resp` | `bdwdth` kHz; `pfd_pk_7g` calculated peak pfd [p.87–89] |
| `freq` (95865) | `ntc_id, grp_id, freq_assgn, freq_sym, freq_mhz, freq_min, freq_max, bdwdth, emi_rcp, beam_name, ntc_type` | Derived data; `freq_min/max` observed in MHz [p.113] |
| `assgn` (96624) | `grp_id, seq_no, freq_sym, freq_assgn, freq_mhz` | k/m/g symbol sets the unit of `freq_assgn` [p.80] |
| `emiss` (216455) | `pep_max, pwr_ds_max, pep_min, pwr_ds_min, c_to_n, pwr_ds_nbw, design_emi` | `pep_*` dBW; `pwr_ds_*` dBW/Hz [p.85] |
| `srv_cls` (60529) | `grp_id, seq_no, stn_cls, nat_srv` | C.4.a and C.4.b [p.106] |
| `srv_area` (930) | `grp_id, ctry, f_excl_api` | C.11.a service-area country; check the exclusion flag [p.106] |
| `provn` (759644) | `grp_id, coord_prov, agree_st, coord_st, adm, ntwk_org, ctry` | Coordination requirements [p.100]. **Key table for Finland.** |
| `tr_aff_ntw` (95499), `all_aff_ntw` (15882) | `aff_ntc_id, sat_name, coord_prov, agree_st, adm` | Affected networks |
| `geo` (72), `non_geo` (112), `orbit` (11221) | `long_nom, tol_east, tol_west`; `nbr_sat_nh, x_zone`; `inclin_ang, apog_km, perig_km, nbr_sat_pl, op_ht_km` | Orbit data; angle in degrees, altitude in km [p.97] |
| `e_stn` (12) | `long_dec, lat_dec, ant_alt, elev_min, stn_name` | Specific earth stations; decimal degrees [p.112] |
| `c_pfd` (119) | `freq_min, freq_max, pfd, bdwdth, ra_stn_type` | A.17 compliance; `pfd` dB(W/m²), `bdwdth` kHz [p.80] |
| `mask_info`, `mask_lnk1–3`, `epfd_param`, `epfd_freq` | `mask_id, freq_min, freq_max, f_mask`; `scen_id` | Masks and EPFD scenarios [p.91–92] |
| `res49_sel`, `plan_pub`, `sps_results`, `ap30b_tr_res` | | All 0 rows in 3074, although RES49 notices exist |

No gain-contour table is present, and graphical data travels in a GIMS-format MDB [P p.117]. So **peak gain, not gain toward Finland, is what the free file gives** (Derived). Treat it as a conservative screen.

**Terrestrial.** TerRaBase domains are `fmtv_terra`, `fxm_terra`, `lfmf_terra`, with `GLAD.db` separate [TDB]. The documentation has table-level text and diagrams, not per-column units [TFXM]. BR warns third-party readers about the structure change from IFIC 3042 (18 March 2025) [CR516].

`[Inspected]` [Z3076] tables relevant to the side quest:

| Table (rows) | Fields |
|---|---|
| `fxm_terra` (4057) | `terrakey, adm, freq_assgn, freq_min, freq_max, bdwdth, stn_cls, emi_cls, notice_typ, intent, stage, prov, geo_key, d_inuse` |
| `fxm_ant` (5197) | `terrakey, ant_key, pwr_ant, pwr_dbw, azm_max_e, gain_max, bmwdth, hgt_agl, eff_hgtmax, pwr_xyz, pwr_eiv, ant_dir, polar, tx_rx` |
| `fxm_geo` | `geo_key, long_dec, lat_dec, site_alt, radius, ctry, site_name` |
| `fxm_tx` (871), `fxm_rx` (4317), `fxm_coord` (5209), `fxm_fdg` (1963) | Links, coordination status, findings |
| `ref_notice_typ`, `ref_stn_cls`, `ref_nat_srv`, `ref_adm` | Code lists with descriptions |

- `intent`: ADD 2905, RECORDED 576, SUPPRESS 413, MODIFY 163. Usable directly for new/modified/withdrawn alongside diffing consecutive issues (Derived).
- `notice_typ`: T11 2162, T12 978, T13 871, G12 32, T14 9, 1A1 5.
- Land-mobile rows (`stn_cls` FB or ML): SVN 1127, KAZ 412, CHN 194, **RUS 125**, POL 9, F 2.
- `adm` has **no S, NOR or EST rows in 3076**; RUS 313 and FIN 4 (all FX).

## 3. Letters, filing type, and "mission"

| Field | Values | Source |
|---|---|---|
| `ntc_type` | G geostationary satellite; N non-geostationary satellite; S **specific** earth station; T typical earth station; R radio astronomy station | [P p.96, p.112] |
| `ntf_rsn` | A = No. 9.1; C = 9.6, 9.7A, 9.21; D = 9.17; N = 11.2, 11.12, AP30/30A Art 5, AP30B Art 8; B = AP30/30A Arts 2A and 4; P = AP30B Arts 6, 7; U = Res 49; X = Res 35; T = Res 8 | [P p.95] |
| `act_code` | Part I-S: A new, M modification, N non-basic change, R resubmitted, S suppress, W withdrawn | [P p.11] |

**"Mission" is not a schema or RR filing term.** In the Preface it appears in the relevant sense only for a "short duration mission" under Resolution 32 [P]. Map a team "mission" to:

- `srv_cls.stn_cls`: e.g. EC FSS, EI MSS, EV BSS TV, EN RNSS, E3 EESS active, ER telemetry, ED telecommand, EK tracking, ET space operation [P p.176]. Earth station codes such as UC are also in Table 3.
- `srv_cls.nat_srv`: CO, CP, CR, CV, FS, OT, describing correspondence type [P p.178].
- Beams and groups: `emi_rcp` gives direction, `beam_name` the beam, `grp` the group.

Appendix 4 item references are the "Items in AP4" column of the dictionary [P p.80+]; WRC-23 revised Appendix 4, effective 1 Jan 2025 [CR511].

## 4. ITU tools

| Tool | Purpose | Source |
|---|---|---|
| BR Space Applications v10 | Suite, build 10.0.0.72, **Windows 10/11 only** | [SW] |
| SpaceCom | Comments on CR/C, API/A, AP30-30A/E Part A, AP30-30A/F/C, AP30B ESIM, Part I-S | [SCOM] |
| GIBC | PFD/EIRP GSO, NGSO, Earth Station; Appendix 8 with coordination arc; AP30B Annex 4; AP7; AP30/30A PFD conformity; Power Control | [GIBC] |
| SPS (MSPACEg) | AP30/30A coordination requirements | [SW] |
| SpaceCap, GIMS | Filing and graphical capture | [SW] |
| BRSIS-Validation | Validates SpaceCap notices | [SW] |
| BRSIS-Query (SpaceQry) | Standard, IFIC, overlap and "Sql Adhoc" queries; export | [SQ] |
| BRSIS-SRSConvert | **SNS version upgrade only**, e.g. 9.1 to 10.0 | [SRSC], [CR511] |
| Space Explorer | Previously SNS Online. Web app, updated each IFIC, network dashboards. Consulting and exporting filing characteristics is a subscription service, free to TIES users. | [EXPL], [RSOFT] |
| SNL query pages | Declared obsolete; redirects users to Space Explorer | [SNLQ] |
| Notex query, As Received, BIU, Suspension list | Public web pages | [HUB] |
| e-Submission | Filings and SpaceCom files; mandatory since 1 Aug 2018 | [RRS] |
| e-Communications | Administrative correspondence | [ECOM] |
| TerRaQ / TerRaNotices | Terrestrial query and notice tools | [TBR] |

**SQLite.** Only terrestrial is documented as SQLite [TDB], [CR516]. No ITU space-services page I read mentions SQLite, and the Preface and CR/511 specify MDB [P p.77], [CR511]. The Preface says BR accepts notices only as an Access file [P p.78].

**The converter that exists:** "BR IFIC TerRaBase Format Converter", launched from TerRaQ, converts the current database to "TerRaBase 2019" [TLEG]. It runs *from* SQLite, not from MDB.

**Practical route (Derived):** convert MDB to SQLite yourselves. `access-parser` parsed all 3074 tables, including `grp_aff_rec` at 3.1 million rows. `mdbtools` was not tested.

**Public API:** none documented on the pages read. Export from Space Explorer is described as subscription-based [RSOFT], so do not build the demo on scraping it.

## 5. Process and legal

All from [RR1] unless tagged.

| Provision | Rule |
|---|---|
| 9.1, 9.2B | API published within two months of complete receipt |
| Sub-Section IA | API applies to systems **not subject to coordination under Section II**. Confirmed; 9.1A and 9.2C are `SUP - WRC-23`. |
| 9.3 | Comments within four months, copy to BR. Silence: BR "may assume" no objections. |
| 9.5A | The sub-section is mainly for informing administrations |
| 9.30, 9.35, 9.36, 9.38 | CR received, examined, affected administrations identified, published within four months |
| 9.36.1 | BR's list under 9.11–9.14 and 9.21 is **for information only** |
| 9.41 | Within four months, ask to be added or removed |
| 9.50 | Examine interference to own assignments, identified under Appendix 5 |
| 9.51 | Under 9.7–9.7B, agree or disagree within four months |
| 9.52 | Disagreement within four months, **with information on own assignments** and suggestions; copy to BR |
| 9.52A | Under 9.14, may ask BR to apply AP5 criteria; this counts as disagreement pending results |
| 9.52C | Under 9.11–9.14 and 9.21, silence means **unaffected**; for 9.11–9.14, 9.48 and 9.49 apply |
| 9.48, 9.49 | No complaint of harmful interference to own assignments, and own use must not cause any |
| 9.52.1 | Comments in non-coordinated cases are **not by themselves a disagreement** |
| 5.474A | Exception: silence on 9.2–9.3 and 9.9–10.4 GHz EESS active counts as **not agreed**. Also noted on the CR/D cover [P p.45]. |
| 11.2 | Notification |
| 11.31, 11.32, 11.32A, 11.33 | Examination: allocations and limits; coordination; probability of harmful interference |
| 11.41, 11.42 | Recording after unfavourable finding; notifier must eliminate actual interference upon report |
| 4.4 | Derogation use: no interference, no protection |
| 15.21–15.43 | Infringement and harmful-interference procedure; BR via 15.41–15.42 |

**Action by Special Section**

| Section | What Finland does | Deadline | Source |
|---|---|---|---|
| API/A | Comment if unacceptable interference to its satellite networks. **Terrestrial stations are not named in 9.3.** | 4 months from IFIC | [RR1], [P p.39] |
| CR/C (9.7, 9.7A, 9.7B) | Agree or disagree; may use 9.41 | 4 months | [P p.42] |
| CR/C (9.11–9.14, 9.21) | Disagree under 9.52, whether listed or not | 4 months | [P p.42] |
| CR/D, CR/E, API/B | Status information. Check your own listing; no new window. | None | [P p.40, 45, 47], Derived |
| AP30/AP30A/AP30-30A Article 4 Part A | Agree or comment; ask to be included under §4.1.7 or §4.2.10 | 4 months | [RR2 §4.1.7, 4.1.10, 4.2.10, 4.2.14] |
| AP30-30A/F/C | Silence means **agreed** to the AP30#4.2.3D form | Stated date | [P p.53] |
| AP30B/A6A etc. | UNVERIFIED: AP30B Article 6 periods not extracted | | [P p.20] |
| Part I-S | SpaceCom handles comments "subject to No. 11.28.1"; text not read | UNVERIFIED | [SCOM] |
| RES49 | Due diligence information; no response duty found | UNVERIFIED | [P p.22] |

So 3074 CR/C comments fall due **23 Oct 2026** (Derived: 23 Jun 2026 plus four months). The real-world window has passed, but the printed deadline is still the correct output field. Each CR/C cover prints an expiry date [P p.42]; prefer that when you have the PDF.

**Plans.** AP30 covers BSS at 11.7–12.5 GHz in Region 1, 12.2–12.7 in Region 2, 11.7–12.2 in Region 3. AP30A covers feeder links, 14.5–14.8 and 17.3–18.1 GHz in Regions 1 and 3, 17.3–17.8 in Region 2 [RR1 fn A.9.3]. Structure: Regions 1 and 3 Plan plus **List** (§4.1); Region 2 Plan (§4.2) [RR2]. AP30B is an FSS allotment plan; see A6A, A6B, A7 [P p.20]. AP30B band list: UNVERIFIED here.

**How submissions flow.** Comments go to the responsible administration, and the BR copy goes as a SpaceCom MDB through e-Submission [COM]. Only administration users can submit [RRS].

**Finland in 3074** `[Inspected]` [Z3074]: `provn` has 220 rows with `adm='FIN'`, duplicated in 12xxx and 32xxx `ntc_id` pairs (reason UNVERIFIED). One of each pair:

| Network | ADM | Type | Provision | Rows | Band range, MHz | Latest section |
|---|---|---|---|---|---|---|
| **STARERA-3** | CHN | N | 9.14 | 2 | 400.15–1530 | **CR/C 6498, no CR/D yet** |
| CHINASAT-G-33.5E | CHN | G | 9.14 | 16 | 1518–1525 | CR/D 5379 |
| QATARGOV-G1-25.5E | QAT | G | 9.21/C | 40 | 235–399.9 | CR/D 5375 |
| SECOMSAT-5-78E | E | G | 9.21/C | 11 | 235–399.4 | CR/E 2875 |
| HISPASAT-5-52.5W | E | G | 9.11 | 36 | 17670–17800 | CR/E 2869 |
| UVSQ-SAT-NG | F | N | 9.21/C | 1 | 148–149.9 | CR/D 5386 |
| HOL-NGSO2-I-S | HOL | N | 9.21/C | 1 | 148.02–148.11 | CR/D 5367 |
| INSAT-COM(71E) | IND | G | A30A#7.1 | 1 | 17700–19700 | CR/D 5372 |
| RGS-S-45E, RGS-S-35E, RGS-N | RUS | G, G, N | V/11.31.1/C | 2 each | 7100–7155 | 11.2 notices |

Band ranges are min/max over groups, not per-row assignments. Inference: STARERA-3 is the one item above with a live CR/C window; confirm against the PDF. Also, `srv_area` names FIN for SOLAR SENTRY (D, API, 9.1/IA, N), and `tr_aff_ntw` shows Finnish plan entries `FIN10300` and `FIN10400` at 22.8°E affected by INSAT-COM(71E).

Evaluators' reference answers are not known, so do not treat this table as ground truth. It is BR's list and "for information only" (9.36.1).

## 6. Power limits

**Rule.** No. 21.16: pfd at Earth's surface, for all conditions and modulation, shall not exceed Table 21-4. It assumes **free-space** propagation and applies where bands are shared with equal rights with fixed or mobile services, unless stated otherwise [RR1]. No. 21.17 allows exceedance on the territory of a consenting country [RR1].

**Formula.** BR: `PFD = Pt + Gt(θ) − 10log(4πR²)` [GSO slide ~44]. Derived for a reference bandwidth `B_ref`:

```
pfd_ref = EIRP_density(dBW/Hz) + 10log10(B_ref_Hz) − 10log10(4πd²)
```

The commonly written form `pfd = EIRP − 10log(4πd²) − 10log(BW)` gives a **per-Hz** value, not the limit's unit. Add back `10log(B_ref)`. Use `emiss.pwr_ds_max` (dBW/Hz) + `s_beam.gain` (dB). If the emission is narrower than `B_ref`, use total power instead of density (Derived; carrier spectrum shape assumed flat). At d = 38,000 km, the spreading term is 162.6 dB (Derived).

**Table 21-4 (Rev.WRC-23)** [RR1 p.298–302], δ is angle of arrival. dB(W/m²):

| Band | Service | 0–5° | 5–25° | 25–90° | B_ref |
|---|---|---|---|---|---|
| 1525–1530 MHz (R1, R3), 1670–1710 MHz (see table), **2025–2110, 2200–2300 MHz** | Met-sat, SR, SO, EESS row | −154 | −154+0.5(δ−5) | −144 | 4 kHz |
| 2500–2690 MHz | FSS, BSS, RDSS, MSS | −136 | −136+(11/20)(δ−5) | −125 | 1 MHz |
| 3.4–4.2 GHz GSO | FSS | −152 | −152+0.5(δ−5) | −142 | 4 kHz |
| 3.4–4.2 GHz NGSO | FSS | −138−Y | −138−Y+(12+Y)(δ−5)/20 | −126 | 1 MHz |
| 8025–8500 MHz | EESS, SR | −150 | −150+0.5(δ−5) | −140 | 4 kHz |
| 10.7–11.7 GHz GSO | FSS | −150 | −150+0.5(δ−5) | −140 | 4 kHz |
| 10.7–11.7 GHz NGSO (fn 25) | FSS | −126 | −126+0.5(δ−5) | −116 | 1 MHz |
| 10.7–12.75 NGSO (fn 24, regional set) | FSS | −129 | −129+0.75(δ−5) | −114 | 1 MHz |
| 17.7–19.3 GHz | FSS, ISS, Met-sat | −115 or −115−X | −115+0.5(δ−5) or −115−X+((10+X)/20)(δ−5) | −105 | 1 MHz |
| 19.3–19.7 GHz | FSS, ISS | −115 | −115+0.5(δ−5) | −105 | 1 MHz |
| 37.5–40 GHz GSO | FSS, MSS | −127 | 5–20°: −127+(4/3)(δ−5); 20–25°: −107+0.4(δ−20) | −105 | 1 MHz |
| 37.5–40 GHz NGSO | FSS, MSS | −120 | −120+0.75(δ−5) | −105 | 1 MHz |
| 40–40.5 GHz | FSS, MSS | −115 | −115+0.5(δ−5) | −105 | 1 MHz |
| 40.5–42 GHz GSO | FSS, BSS | −120 | 5–15°: −120+(δ−5); 15–25°: −110+0.5(δ−15) | −105 | 1 MHz |
| 40.5–42 GHz NGSO | FSS, BSS | −115 | −115+0.5(δ−5) | −105 | 1 MHz |
| 42–42.5 GHz GSO / NGSO | FSS, BSS | −127 / −120 | as 37.5–40 GSO / NGSO | −105 | 1 MHz |
| 9.9–10.4 GHz | EESS active | 0–5.7°: −113 | 5.7–53°: −109+25log(δ−5) | 53–90°: −66.6 (mean, fn 18) | 1 MHz |

Notes:

- The 1518–1525 MHz rows in Table 21-4 apply only to United States territory, so they do not bind over Finland.
- **X** (fn 13, 21.16.6): function of constellation size N. Printed: X=0 for N≤50; `max{20.3; 10log Nv}` for 1000≤N≤6000; `10log Nv + 1` for N>6000. The 50<N≤999 formulas were garbled by PDF extraction, so **read them from the PDF**.
- **Y** (fn 22, 21.16.15): Y=0 for max(NN,NS)≤2, otherwise 5·log(max(NN,NS)).
- 17.7–19.3 has a second row for highly inclined orbits: 0–3° −120; 3–12° −120+(8/9)(δ−3); 12–25° −112+(7/13)(δ−12); 25–90° −105 (fn 16). A similar row covers 19.3–19.7.
- 12.5–12.75 GHz GSO row (−148/−138) applies to Region 1 countries in 5.494 and 5.496. Finland is not in 5.494 as read; 5.496 not fully checked.
- Table 21-4 has no row for 9.3–9.9 GHz (as read), so the common SAR band has no such pfd limit here.

**Appendix 5 Table 5-2 (Rev.WRC-19), pfd coordination thresholds** [RR2 p.178–179], the trigger for No. 9.14. Formula (NOTE 2): P for δ≤5°; P+r(δ−5) for 5–25°; P+20r for 25–90°.

| MHz | Case | GSO P | NGSO P | r |
|---|---|---|---|---|
| 1518–1525, 1525–1530 | Analogue FS telephony | −146 in 4 kHz **and** −128 in 1 MHz | same | 0.5 |
| | All other cases | −128 in 1 MHz | −128 in 1 MHz (FDP 25%) | 0.5 |
| 2160–2200 | Analogue FS telephony | −146 / −128 | −141 / −123 | 0.5 |
| | All other cases | −128 | −123 (FDP 25%) | 0.5 |
| 2483.5–2500 | MSS, all cases | −146 / −128 | −144 / −126 | 0.5 / 0.65 |
| 2483.5–2500 | RDSS | −152 / −128 | −153 / −129 | – |

Note 9 gives other values for a list of countries (full list not checked for Finland). 4 kHz and 1 MHz values are as printed.

**EPFD.** No. 22.5C protects GSO networks, not terrestrial services. Example Table 22-1A, 10.7–11.7 GHz: −175.4 at 0%, −174 at 90%, −170.8 at 99%, −165.3 at 99.73%, −160.4 at 99.991%, −160 at 99.997% and 100%; 40 kHz, 60 cm, S.1428-1 [RR1]. Requires a time simulation, so out of scope for a simple demo (Derived). BR publishes results to subscribers [UG].

**AP30 Annex 1 (Rev.WRC-19)** [RR2 p.566–568]. New List assignment: max −103.6 dB(W/(m²·27 MHz)). Affected if orbital spacing is under 9° unless, at test points, pfd is within: −147 for θ<0.23°; −135.7+17.74logθ to 2.0°; −136.7+1.66θ² to 3.59°; −129.2+25logθ beyond (upper limit not captured in extraction); or the equivalent protection margin falls no more than 0.45 dB. **This needs AP30 test-point and plan data not in the free file** (Derived).

**Geometry, GSO seen from Finland** (Derived, spherical Earth): `el = atan((cosγ − Re/r)/sinγ)`, `cosγ = cos(lat)·cos(Δlon)`, Re=6378 km, r=42164 km.

| Lat | Δlon 0° | 30° | 60° |
|---|---|---|---|
| 60°N | 21.9° (39,364 km) | 17.4° | 5.8° (41,037 km) |
| 65°N | 16.7° | 13.0° | 3.5° |
| 70°N | 11.5° (40,429 km) | 8.6° | 1.1° (41,551 km) |

So **GSO limits over Finland fall in the 0–25° segments**, and the −142 style upper values do not apply. Visibility limit is 81.3° central angle. For NGSO, compute δ from `orbit.inclin_ang`, `apog_km`, `perig_km`; near-zenith passes need inclination close to or above site latitude (Derived). Use worst δ per limit.

**Allocations naming Finland** (Article 5, heuristic search of [RR1], may be incomplete): 5.96, 5.161B, 5.162A, 5.164, 5.166A, 5.206 (137–138 MHz AM(OR) primary), 5.211 (138–144 MHz maritime and land mobile), **5.221** (148–149.9 MHz MSS must not interfere with listed countries' fixed and mobile services), 5.235, 5.275, 5.296, 5.331, 5.536B and 5.536C (25.5–27 GHz earth stations, no protection claim). 5.221 is directly relevant to UVSQ-SAT-NG and HOL-NGSO2.

**What "protect" requires** (from [RR1]):

1. A real assignment. 9.52 requires "information concerning its own assignments", and for terrestrial or opposite-direction stations in a coordination area only existing ones, or within three months (terrestrial) or three years (earth stations), count as notifications.
2. Silence loses it: 9.48, 9.49, 9.52C.
3. Conformity with the Table: 4.4 stations get no protection.
4. Some footnotes cap it: e.g. stations in parts of 3.4–3.6 GHz "shall not claim more protection from space stations than" Table 21-4.

## 7. Finland and CEPT

**M4.** Radio Frequency Regulation **4 AG/2026M**, Reg. no TRAFICOM/265115/03.04.05.00/2025. Issued 26.3.2026, in force **31.3.2026**, repeals 4 AF/2025M. Covers 100 Hz–400 GHz. The annex is the Frequency Allocation Table, 258 pp. in English; legal basis Act 917/2014 ss. 96(1), 97(2) [M4EN]. Its notes say the table takes the ITU RR into account (Decree 12/2000), and Regulations 4 and 15 are updated simultaneously [M4N]. So **the M15 link in the brief, dated 27.3.2025 [M15], may be superseded** (UNVERIFIED). Traficom-site PDFs from search returned 404; use Finlex [M4FI].

**Open data `[Inspected]` [API], [META]:** OData v13, one call returns 5917 rows, no `nextLink`, 8.3 kHz–400 GHz.

| Field | Type | Note |
|---|---|---|
| `ID` | Int32 | |
| `Frequency_band_lower_limit`, `_upper_limit` | String | "8.3 kHz" |
| `Sub_band_lower_limit__Hz_`, `Sub_band_upper_limit__Hz_` | **Int64** | Use these |
| `Services_in_Finland`, `Additional_information`, `Sub_band_usage` | String | Fixed satellite 341, Mobile satellite 312 |
| `Class_of_station` | String | "Mobile (ML)", "Earth station (TC)" |
| `Direction` | String | TX, RX, TXRX, empty |
| `Radiated_power` | String | "25 W"; empty in 5372 |
| `Transmitter_power` | Int32 | 0 in 5909, treat as missing (Derived) |
| `Mode_of_traffic`, `Channel_spacing`, `Bandwidth`, `Duplex_separation`, `Duplex_band_lower_limit`, `Duplex_band_upper_limit`, `Class_of_emission`, `Standard_type`, `Comment` | String | Mostly free text |

It holds no pfd limits, so limits must come from the RR (Derived).

**T/R 25-08, current edition 6 June 2025** [TR], 29.7–470 MHz. Indicative thresholds: co-channel, 50% locations, 10% time, 10 m receiving height, 25 kHz, **at the border line**.

| MHz | dB(µV/m) |
|---|---|
| 29.7–47 | 0 |
| 47–108 | 6 |
| 108–380 | 12 |
| 380–400 | 18 |
| 400–470 | 20 |

- Wider channels: add `BC = 10·log10(channel spacing / 25 kHz)` dB, if spectrally uniform.
- Digital systems may need the 1% time curves in certain situations (fn 2).
- Annex 3 (410–430, 450–470 MHz, narrowband vs >1 MHz): e.g. 20 dBµV/m/25 kHz at 40 or 50 km for preferential regimes, 41 or 48 at 0 km.
- Annex 4 (LTE/NR, CDMA >1 MHz): 55 dBµV/m/5 MHz at 0 km and 37 at 10 km, 3 m height. FIN is listed as "Type country 1" for code plans.

**The 2008 edition's 29.7–921 MHz scope is superseded** [TR]. Its recommendation is that CEPT administrations make agreements with neighbours, and HCM may be a basis [TR].

**P.1546-6** (08/2019, in force) [P1546R]. 30–4000 MHz, land, sea or mixed paths up to 1000 km; curves at 1 kW e.r.p.; 100, 600, 2000 MHz nominal [P1546]. Inputs: frequency, time %, distance, effective `h1`, `h2`, path type and sea fraction, location variability. Map to `fxm_ant.pwr_dbw`, `gain_max`, `hgt_agl`, `eff_hgtmax`, `fxm_geo.long_dec`, `lat_dec`. `pwr_xyz` and `pwr_eiv` semantics are UNVERIFIED, so check them before converting to e.r.p.

Implementations: `eeveetza/p1546` MATLAB/Octave reference with validation data [ZEN]; SEAMCAT, documented as simplified (flat, land only) [SEAM]; MathWorks calculator without mixed paths [MW]. A Python port exists: `eeveetza/Py1546`, whose README says it corresponds to the WP 3K reference (https://github.com/eeveetza/Py1546). README read; code not run.

**HCM.** The BNetzA page lists 17 parties and **not Finland** [HCM]; the list may be dated. A 2021 draft Sweden–Finland–Norway 5G land-mobile agreement exists on Nkom's site; status UNVERIFIED [NKOM]. Agreements with Estonia and Russia: UNVERIFIED.

**CEPT.** Implementation overview offers CSV exports and links to EFIS [DOC]. ERC Report 25 is cited as the European common allocation table in [TR]; I did not fetch it.

**Finnish space use.**

- ICEYE and the Finnish Defence Forces signed a SAR satellite contract on 8 Sept 2025 [ICE]. Whether it is under a Finnish ITU filing: UNVERIFIED.
- 9.6 GHz for ICEYE: UNVERIFIED. RR: EESS (active) at 9.3–9.9 GHz, with 9.2–9.3 and 9.9–10.4 under 5.474A [RR1].
- Aalto, Reaktor Hello World, Kuva Space filings: UNVERIFIED. Query Space Explorer by administration.
- Radio astronomy: M4 shows 1400–1427 MHz "all emissions prohibited", plus 1660–1668.4 MHz and 13.36–13.41 MHz [M4EN]. A Metsähovi ITU entry: UNVERIFIED.
- GNSS: 3074 has CHN COMPASS `c_pfd` rows at 1164–1215 MHz, −131 `[Inspected]`. Finnish GNSS protection terms: UNVERIFIED.

**WRC-23.** Final Acts [WRC]; Appendix 4 revised, new Resolutions 8 and 35 sections [CR511], [P p.21]; Table 21-4 amended [RR1]. Item-by-item impact on Finland not assessed.

## 8. Terminology and correspondence

| Term | Meaning | Use when |
|---|---|---|
| Violation / breach | Not an RR filing term. RR 15.21 has "infringement" for stations. | Avoid. A filing is a plan. |
| Excess of hard limit | Exceeds Table 21-4 or similar | Calculated pfd above limit under stated assumptions |
| Unfavourable finding | **BR's** result under 9.35 or 11.31 [GSO] | Only when BR has made it (Part III-S) |
| Coordination trigger | Threshold showing coordination is needed (AP5, T/R 25-08) | Not a prohibition |
| Comment | API 9.3, or 9.52.1 | Not itself a disagreement |
| Disagreement | 9.52, CR/C | With own-assignment data, in four months |
| "Objection" | Used in 9.3 ("no objections") | Prefer the provision's term |
| Coordination request | **Sent by the filer** (9.30) | Finland usually receives one, so do not write that it "requests coordination" unless it is the filer (Derived) |
| Permissible, accepted, harmful interference | RR 1.167, 1.168, 1.169; harmful means endangers safety services or seriously degrades, obstructs or repeatedly interrupts | "Harmful" is for actual cases, or risk phrased as potential |

Suggested wording (Derived): "calculated pfd of X dB(W/m²/ref BW) at δ=Y° exceeds the Z threshold by N dB under free-space assumptions; potential unacceptable interference to assignments [IDs]."

**Direct letters.** Yes. Comments go directly to the responsible administration with a copy to BR [RR1 9.3, 9.52], [P p.39, 42]. e-Communications covers correspondence between administrations and with BR, without email or fax [ECOM]. Per the e-Submission page, from 1 Sept 2026 "Others" uploads move to e-Communications [ESUB]. No prescribed letter template was found (UNVERIFIED).

**Suggested draft fields (Derived from [RR1], [P p.42]):** responsible administration, network, ID number, IFIC and date, Special Section, provision, expiry date, Finnish assignments relied on, calculation with assumptions, suggestions for resolution, copy to BR, human-reviewer status.

## Open questions / could not verify

Ask Traficom at Q&A (Saturday slots in [BRIEF]):

1. **AP30/30A/30B for 3074.** The brief requires them, but the free zip has none. Will they provide `SPS_ALL` and `30B`, or Special Section PDFs? Is anything public (`SpaceCom draft database`, [UG])?
2. **What does the 3074 accuracy file expect?** Finland-listed items only, or calculated concerns too?
3. Whether the comment-deadline passage matters for scoring.
4. Is the `.mdb` extract enough for terrestrial? It is the only free source named.

Other gaps:

- Meaning of `agree_st` values Q, F, V, T, P and symbol `V/11.31.1/C`: see Preface Tables 11A–11C, 13 [P p.197–208, 370+]; not fully read.
- `ntc_id` pairs 12xxx and 32xxx: reason not established.
- `res49_sel` is empty though RES49 notices exist; `com_el` is smaller than `notice` (146 vs 196) because of those pairs, presumably.
- `freq_min/max` units are observed, not confirmed from the dictionary.
- Why STARERA-3's range spans 400.15–1530 MHz, and which footnote triggers each 9.21/C case.
- AP30 Annex 1 terrestrial sections, AP30B Article 6, No. 11.28.1, not read.
- Terms of reuse for bulk ITU data, including the free zips.
- `demowic` public availability is as tested 6 Nov 2026; ITU may change it.
- M4 Annex change list, and the `v13` API's sync date with 4 AG/2026M.
- Radio Regulations 2024 PDF text extraction is imperfect in tables. **Verify any number used in the demo against the PDF.**
- Traficom's synthetic frequencies `.xlsx` is analysed in `problem-and-solution-brief.md` §7, not here.

## Sources

- **[BRIEF]** `docs/challenge/Since_AI_Traficom_Challenge_Brief_FINAL_04112026.pdf`
- **[BRIFIC]** https://www.itu.int/en/ITU-R/space/brific/Pages/default.aspx
- **[SCHED]** https://www.itu.int/en/ITU-R/space/brific/Pages/brificSchedule.aspx
- **[DEMO]** https://www.itu.int/sns/wic/demowic.html
- **[D26]** https://www.itu.int/sns/wic/demowic26.html
- **[Z3074]** https://www.itu.int/sns/ific10/ific3074.zip
- **[TBR]** https://www.itu.int/en/ITU-R/terrestrial/brific/Pages/default.aspx
- **[Z3076]** https://www.itu.int/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific3076.zip
- **[RM3076]** https://www.itu.int/en/ITU-R/terrestrial/brific/BRIFIC/ReadMe/ReadMe_3076.pdf
- **[P]** Preface, Oct 2026: https://www.itu.int/en/ITU-R/space/Preface/preface_e.pdf
- **[IFICN]** https://www.itu.int/en/ITU-R/space/Documents/ificmdb_E.pdf
- **[UG]** https://www.itu.int/en/ITU-R/space/Documents/brificSpaceServicesOnlineUserGuide.pdf
- **[ISO]** https://www.itu.int/en/ITU-R/space/Documents/BR-IFIC-(Space)-ISO-image_2021.pdf
- **[CR511]** https://www.itu.int/dms_pub/itu-r/md/00/cr/cir/R00-CR-CIR-0511!!PDF-E.pdf
- **[CR516]** https://www.itu.int/dms_pub/itu-r/md/00/cr/cir/R00-CR-CIR-0516!!PDF-E.pdf
- **[TDB]** https://www.itu.int/ITU-R/terrasys/docs/db/structure
- **[TFXM]** https://www.itu.int/ITU-R/terrasys/docs/db/fxm
- **[TLEG]** https://www.itu.int/ITU-R/terrasys/docs/db-changes/generate-legacy
- **[SW]** https://www.itu.int/en/ITU-R/software/Pages/space-network-software.aspx
- **[SCOM]** https://www.itu.int/en/ITU-R/software/Pages/spacecom.aspx
- **[GIBC]** https://www.itu.int/en/ITU-R/software/Pages/gibc.aspx
- **[SQ]** https://www.itu.int/en/ITU-R/software/Pages/brsisquery.aspx
- **[SRSC]** https://www.itu.int/en/ITU-R/software/Pages/srsconvert.aspx
- **[EXPL]** https://www.itu.int/en/ITU-R/space/ITUSpaceExplorer/Pages/default.aspx
- **[RSOFT]** https://www.itu.int/pub/r-soft
- **[SNLQ]** https://www.itu.int/net/ITU-R/space/snl/bresult/radvance.asp?sel_ific=3074&ie=y
- **[HUB]** https://www.itu.int/en/ITU-R/space/snl/Pages/default.aspx
- **[ESUB]** https://www.itu.int/en/ITU-R/space/e-submission/Pages/default.aspx
- **[ECOM]** https://www.itu.int/en/ITU-R/space/WRS20space/30%20e-Communication.pdf
- **[COM]** https://www.itu.int/en/ITU-R/space/WRS20space/36%20Commenting%20on%20CRC%20Special%20Sections.pdf
- **[RRS]** https://www.itu.int/en/ITU-R/seminars/rrs/RRS-22-Asia-Pacific/Presentations/4.%20Space%20Services%20Friday%2016%20Dec/RRS-22%20Asia%20Pacific%20Online%20tools%20(e-Sub,e-Comms,SIRRS).pdf
- **[GSO]** https://www.itu.int/en/ITU-R/seminars/wrs/Documents/2024/Space-Workshops/GSO-Regulatory%20and%20Technical%20Examination.pdf
- **[RR1]** RR 2024 Vol 1: https://search.itu.int/history/HistoryDigitalCollectionDocLibrary/1.49.48.en.101.pdf
- **[RR2]** RR 2024 Vol 2: https://search.itu.int/history/HistoryDigitalCollectionDocLibrary/1.49.48.en.102.pdf
- **[WRC]** https://www.itu.int/dms_pub/itu-r/opb/act/R-ACT-WRC.16-2024-PDF-E.pdf
- **[M4FI]** https://www.finlex.fi/fi/viranomaiset/maarayskokoelmat/traficom-viestinta/2026/3
- **[M4EN]** https://www.finlex.fi/api/media/authority-regulation/1070976/mainPdf/main.pdf?typeDiscriminator=traficom-communications
- **[M4N]** https://www.finlex.fi/api/media/authority-regulation/1070976/media/Explanatory%20notes%20Radio%20Frequency%20Regulation%204AG2026M.pdf?typeDiscriminator=traficom-communications
- **[M15]** https://www.finlex.fi/fi/viranomaiset/maarayskokoelmat/traficom-viestinta/2025/51209
- **[API]** https://opendata.traficom.fi/api/v13/Taajuusjakotaulukko
- **[META]** https://opendata.traficom.fi/api/v13/$metadata
- **[TR]** T/R 25-08 (6 June 2025): https://docdb.cept.org/download/4789 (record: https://docdb.cept.org/document/909)
- **[DOC]** https://docdb.cept.org/implementation/overview
- **[P1546R]** https://www.itu.int/rec/R-REC-P.1546/en
- **[P1546]** https://www.itu.int/dms_pubrec/itu-r/rec/p/R-REC-P.1546-6-201908-I!!PDF-E.pdf
- **[ZEN]** https://zenodo.org/records/6206015
- **[SEAM]** https://ecowiki.atlassian.net/wiki/x/9KUH
- **[MW]** https://www.mathworks.com/matlabcentral/fileexchange/25099-itu-r-p-1546-calculator
- **[HCM]** https://hcm.bundesnetzagentur.de/http/englisch/europakarte/europakarte.htm
- **[NKOM]** https://wWw.nkom.no/hoeringer/horing-av-5g-koordineringsavtale-mellom-norge-sverige-og-finland/_/attachment/download/5f5909af-cd11-4ce1-b84d-b464ed054f94:5c0559f80c9312b624b4f47c387d2125b6a61126/Coordination_Agreement_5G_Land_Mobile_draft_Swe_Fin_NOR%20mars%202021.pdf
- **[ICE]** https://www.iceye.com/newsroom/press-releases/iceye-signs-satellite-acquisition-agreement-with-the-finnish-defence-forces
