# Traficom IFIC challenge: problem, evidence and what to build

*Research as of 6 Nov 2026. Evidence, schema, limit tables and full source links are in the companion file, [`itu-primary-sources.md`](itu-primary-sources.md). Tags such as `[RR1]` resolve to its source list. Throwaway analysis scripts are in [`spike/`](spike/).*

**How much to trust each part**

| Label | Meaning |
|---|---|
| **Ran** | We ran this on the real IFIC 3074 or 3076 files, or on the Traficom data |
| **Source** | Read from a primary document |
| **Judgement** | Our recommendation or inference |

---

## 1. The short version

**The real problem is triage, not violation-catching.** Every two weeks ITU publishes thousands of records describing radio systems that countries *plan* to operate. Traficom has a limited window, normally four months, to answer one question: *"Could any of this harm Finnish radio use, and if so, what do we formally say, to whom, and by when?"* If Finland stays silent, it can lose the right to complain later. **Source:** RR 9.48, 9.49, 9.52C `[RR1]`.

**What to build:** an auditable screening pipeline with five stages:

1. Ingest a new IFIC issue.
2. Run deterministic checks against Finnish data and the Radio Regulations.
3. Rank the findings.
4. Show the evidence behind each finding.
5. Draft a letter for a human expert to sign.

**The calculations stay deterministic.** The LLM explains and drafts, but never decides a number. The brief says technical correctness, traceability and reviewability matter more than the choice of model `[BRIEF]`.

**Five things that change our plan**

1. **MDB files can't be avoided, but they're easy to handle.** Both mandatory free downloads are Access `.mdb` files. We read them on Linux with a pure-Python library, with no ITU software or Access. **Ran.**
2. **Don't auto-send email.** The brief asks for "expert-reviewable draft correspondence". A formal letter between governments has to be signed off by a person.
3. **The terrestrial side quest is not optional if we want to win.** Criterion B, 25% of the score, covers extensibility and the side quest.
4. **Calculating pfd is easy; being right about Finland is hard.** Our first screen flagged 27 of the 70 networks it could test, and many are obviously false alarms. The free file has no antenna pointing data, so reducing false alarms is the main engineering problem. **Ran.**
5. **The AP30 data seems to be missing.** The brief names AP30/30A/30B, but the free 3074 file contains none of them. Ask Traficom first (section 12).

---

## 2. Where our understanding needs correcting

| What we thought | What's true | Why it matters |
|---|---|---|
| Countries are "violating" Finnish law | Filings are **plans**, mostly not yet in use. Finnish law doesn't bind a foreign satellite; the shared treaty is the ITU Radio Regulations. M4 tells us what Finland *uses*. **Limits come from the RR** | Never write "violation". Use "potential concern" or "calculated value exceeds X" |
| Other countries' signals can't enter Finnish airspace | Satellite signals do land on Finland and that's normal. The RR limits **how strong** they are (pfd), on shared bands | The question is one of level, not presence |
| Traficom "sends a notice" to violators | Finland sends a **comment** or **disagreement** under a specific provision, to the filing administration, with a copy to the Radiocommunication Bureau (BR) | The letter must cite the provision, the deadline and the Finnish assignments relied on |
| Finland requests coordination | The **filer** requests it. Finland agrees or disagrees | Wrong wording would look amateur to the judges |
| We must not use MDB files or ITU tools | ITU tools are optional. MDB is the format of the free data | Convert MDB to SQLite on ingest, then forget about it |
| ITU has an MDB-to-SQLite converter | **None found.** The *full terrestrial* database is SQLite, which probably started the rumour `[TDB]` | Write our own conversion step |
| Letters: G = geospatial, N, S | `ntc_type`: **G** geostationary, **N** non-geostationary, **S** specific earth station, **T** typical earth station, **R** radio astronomy `[P p.96]` | |
| "Missions" hold the power data | No such field. Power is in `emiss`, gain in `s_beam`, service in `srv_cls` | See section 5 |
| Inclination = how far the satellite is from Finland | Inclination is the orbit's tilt, and it sets the **highest latitude** the satellite reaches. Distance comes from altitude plus geometry | Geometry matters a lot at 60–70°N |
| ITU sends letters on "SNS" | SNS is ITU's space database format. The biweekly publication is the **BR IFIC** | |

---

## 3. Radio basics you need

**Frequency.** Where a signal sits on the spectrum, in Hz. Two signals only interfere if they overlap in frequency, or sit close enough that one leaks into the other.

**Bandwidth.** How wide the signal is. Spreading the same power over more bandwidth lowers its strength per Hz.

**Decibels.** A logarithmic power scale. +3 dB is double, +10 dB is ten times, +20 dB is a hundred times. `dBW` means decibels relative to 1 watt.

**EIRP.** Transmitter power plus antenna gain: the power an ideal all-directions antenna would need to look this strong. Gain is direction-dependent, which is the crux of our false-positive problem.

**Power flux density (pfd).** Power arriving per square metre at the ground, measured in a stated **reference bandwidth**. This is *the* number for satellite-to-ground limits:

```
pfd = EIRP density (dBW/Hz) + 10·log10(B_ref in Hz) − 10·log10(4π·d²)
```

If the signal is narrower than `B_ref`, use total power instead of density. With no reference bandwidth, a pfd figure can't be compared to a limit.

**Angle of arrival (δ).** How high the satellite appears above the horizon. Limits get *stricter* for low angles, because terrestrial antennas point near the horizon. Finland is far north, so a geostationary satellite never rises above about **22°** there. **Derived** `[itu-primary-sources §6]`.

| Term | Meaning |
|---|---|
| GSO | Geostationary: fixed over one equator longitude at about 36,000 km |
| NGSO | Any other orbit, such as LEO; moves across the sky |
| Allocation | Which service may use a band: primary or secondary, per region, plus footnotes |
| Space-to-Earth | Satellite transmitting; can hit Finnish **receivers** directly |
| Earth-to-space | Ground station transmitting; a concern if nearby, or under footnotes such as 5.221 |
| Adjacent band | Neighbouring frequency, not overlapping; the brief includes this ("same or adjacent") |
| EPFD | Combined pfd from a whole constellation, as a time distribution. It protects GSO **networks**, not terrestrial services, and needs simulation |

---

## 4. Who does what, and the actual process

| Actor | Role |
|---|---|
| **ITU Radiocommunication Bureau (BR)** | Examines and publishes filings, and maintains the Master Register. It doesn't enforce anything |
| **Administration** | A country's regulator. It files on behalf of operators, including private ones |
| **Traficom** | Finland's administration; issues M4 and M15 and defends Finnish spectrum use |
| **CEPT/ECC** | European harmonisation; issues T/R 25-08 |

**Lifecycle of a satellite filing** `[RR1]`, `[P]`

```
Filer submits ──▶ BR examines ──▶ published in BR IFIC ──▶ 4-month window ──▶ coordination ──▶ notification
                                       Special Section        Finland acts      bilateral        Master Register
                                       (API/A, CR/C...)       or stays silent
```

**What Traficom does with each section.** **Source:** full table in `itu-primary-sources.md` §5.

| Section | Content | Action | Deadline |
|---|---|---|---|
| **API/A** | Systems not subject to coordination, advance notice | Comment. RR 9.3 names interference to **satellite networks**, not terrestrial stations | 4 months |
| **CR/C** | Coordination requests | Agree or disagree. Silence under 9.11–9.14 and 9.21 means "unaffected" | 4 months |
| **CR/D, CR/E, API/B** | Status updates | Check our listing; no new window | None |
| **AP30/30A Part A** | Broadcasting-satellite plan changes | Comment or ask to be included | 4 months |
| **Part I/II/III-S** | Notifications and findings | Monitor | See `[SCOM]` |

The BR's list of affected countries is **for information only** (9.36.1). Finland can respond even if unlisted, which is why independent screening adds value.

---

## 5. What's in the data

**Access.** Free downloads, HTTP 200 with a browser-style User-Agent. **Ran.** Plain `curl` gets a firewall rejection.

| Issue | Date | Download | Contents |
|---|---|---|---|
| Space IFIC 3074 | 23 Jun 2026 | `sns/ific10/ific3074.zip`, 61 MB | `ific3074.mdb`, 287 MB |
| Terrestrial IFIC 3076 | 21 Jul 2026 | `.../BRIFIC/MDB/brific3076.zip`, 2.4 MB | `brific3076.mdb`, 25 MB |

**Issue 3074 in numbers.** **Ran.** 146 notices in `com_el` (92 N, 42 G, 12 S), 34,365 frequency groups, 216,455 emission rows and 759,644 coordination-requirement rows. Finland filed none of these notices.

**Join path:**

```
com_el / notice (ntc_id)  who filed, which network, type, provision, IFIC, dates
   └─ s_beam (ntc_id, emi_rcp, beam_name)  direction E/R, max gain
        └─ grp (grp_id)  frequency range, bandwidth
             ├─ emiss     pep_max (dBW), pwr_ds_max (dBW/Hz)
             ├─ srv_cls   stn_cls, nat_srv: the real meaning of "mission"
             ├─ srv_area  countries in service area
             └─ provn     which provision applies to which country  ← start here for Finland
geo / non_geo / orbit     longitude, or inclination and altitude
pub_ssn                   Special Section: CR/C, API/A, ...
c_pfd                     pfd limits the filer states it complies with
```

**The three gaps that shape the design**

| Gap | Consequence | Response |
|---|---|---|
| **No antenna pointing.** `bore_long`, `bore_lat` and `maj_axis` are empty for every beam in 3074. Gain contours sit in a separate graphics database `[P p.117]`. **Ran** | We get peak gain only, and can't tell if a beam points at Finland | Treat the peak result as an upper bound, and be explicit about it. Then see section 9 |
| **No AP30/30A/30B filings** in the free file `[IFICN]`. **Ran** | The brief's explicit requirement can't be met from this file | Ask Traficom. Build a section-parser interface so it can be added |
| **`pfd_pk_7g` is almost always empty:** 17 of 34,365 groups. **Ran** | No shortcut; we have to calculate pfd | Compute it, with the formula visible |

---

## 6. What decides a concern

There's no single "violation" rule. A finding comes from stacked tests of **increasing cost and strength**, and each one adds evidence.

| # | Test | Input | Output | Strength |
|---|---|---|---|---|
| 1 | **BR named Finland** | `provn.adm = 'FIN'` | Provision and status | Formal, but "for information only" |
| 2 | **Can it reach Finland?** | GSO longitude, or NGSO inclination and altitude | Visible / not visible | Hard exclusion |
| 3 | **Same band and direction?** | Filing range vs Finnish receivers, with direction | Stations affected | Necessary, not sufficient |
| 4 | **Is the use allowed?** | RR Article 5 plus footnotes; M4 | Allocation status | Regulatory |
| 5 | **Does pfd exceed a limit?** | `emiss`, `s_beam`, geometry; Table 21-4 | Margin in dB | Strong if the assumptions hold |
| 6 | **Is a coordination threshold crossed?** | Appendix 5 Table 5-2 | Trigger | Coordination, not prohibition |
| 7 | **Is the Finnish side protected?** | Real assignment, conforming to the Table | Whether the claim holds | Decides whether a letter is worth sending |

**Limits for bands that matter here.** **Source:** `[RR1]`, RR Table 21-4, dB(W/m²):

| Band | 0–5° | 5–25° | 25–90° | B_ref |
|---|---|---|---|---|
| 1525–1530, **2025–2110, 2200–2300 MHz** | −154 | −154 + 0.5(δ−5) | −144 | 4 kHz |
| 8025–8500 MHz | −150 | −150 + 0.5(δ−5) | −140 | 4 kHz |
| 3.4–4.2 GHz GSO | −152 | −152 + 0.5(δ−5) | −142 | 4 kHz |
| 10.7–11.7 GHz GSO | −150 | −150 + 0.5(δ−5) | −140 | 4 kHz |
| 17.7–19.3 GHz | −115 − X | see table | −105 | 1 MHz |

Table 21-4 has conditions: free-space propagation, and bands shared with equal rights with fixed or mobile services (21.16). The limit X depends on constellation size. Verify any number used in the demo against the PDF, because some of the extracted formulas are garbled.

---

## 7. What the Traficom data tells us

**Workbook.** **Ran.** 874 rows across 872 unique station numbers, covering 1.5 MHz to 27.5 GHz. It's synthetic.

| `Class of licence` | Rows | Likely meaning (*ask*) | Frequency range |
|---|---|---|---|
| FX | 320 | Fixed | 2025–2243 MHz |
| (blank) | 294 | Unknown | 88 MHz–19.5 GHz |
| BC | 117 | Sound broadcasting | 1.5–108 MHz |
| MVV | 63 | Unknown | 454 MHz–27.5 GHz |
| BT | 58 | TV | 482–690 MHz |
| MUUT | 22 | "Other" (Finnish) | 2.3–9.9 GHz |

**Data traps to handle explicitly**

- **Header.** Rows 11 and 12 are English and Finnish headers. Data starts at row 13, and the workbook header has the typo "Radioation".
- **Missing values.** 3 rows have no TX frequency, 61 have no RX frequency, and antenna gain is mostly blank. FX and MUUT have **no power** at all.
- **Power outliers.** Some 6–18 GHz stations state up to **9.4 GW** (about 100 dBW). That's implausible for a radio link, so check its meaning with Traficom.
- **Duplicates.** Station 105820 appears twice as identical rows; 626855 appears with different data.
- **Impossible geometry.** One row has a negative antenna height (−28 m), which the sheet warns about.
- **Mixed formats.** `Transmission bandwidth` uses `5000k`, `8M00`, `0,1G`, `7,6k`. Parse carefully.

**The important finding: a likely designed trap.** **Ran.**

- 170 stations receive in **2200–2300 MHz**; 158 receive in 2025–2110 MHz.
- The Finnish table lists 2200–2245 MHz as **FIXED, "Military use"**, with no satellite service.
- A check against M4 alone would conclude "no satellite here" and **miss the stations in that sub-band**. In our check against the table's satellite rows, none of the 320 FX stations matched.
- Table 21-4 sets a −154 limit for space-to-Earth emissions across 2200–2300 MHz, and many 3074 filings transmit in that band, mostly NGSO.

**So:** compare against both the RR and M4. This is probably our single best accuracy lever.

**Frequency table API.** **Ran.** 5,917 rows from one call, with numeric Hz columns and no pfd limits. Service names mix uppercase and lowercase, which carries meaning: uppercase means primary, in the usual table convention (*confirm with Traficom*).

---

## 8. Results from the real files

**These are screening results from a one-off script, not findings about any network.** Don't quote them as concerns.

### Space IFIC 3074

**Funnel.** Peak gain, worst-case geometry, seven Table 21-4 rows.

```
146 notices
 └ 128 with a satellite transmitting
    └ 100 overlapping at least one Finnish receiver (synthetic list)
       └  70 falling in a limit band we implemented
          └  27 exceeding a limit at peak gain
             └  22 of those also overlapping a Finnish receiver
```

**What the BR says.** **Ran.** `provn` has 220 rows with `adm='FIN'`, covering 18 notice IDs, which are 11 networks: 7 appear as paired IDs (12xxx and 32xxx), while STARERA-3 and the 3 Russian networks appear once.

| Network | Filer | Type | Provision | Band, MHz | Status |
|---|---|---|---|---|---|
| **STARERA-3** | CHN | N | 9.14 | 400–1530 | **CR/C only**, no follow-up yet |
| CHINASAT-G-33.5E | CHN | G | 9.14 | 1518–1525 | CR/C, CR/D |
| HISPASAT-5-52.5W | E | G | 9.11 | 17670–17800 | CR/C, CR/E |
| QATARGOV-G1-25.5E | QAT | G | 9.21/C | 235–400 | CR/C, CR/D |
| SECOMSAT-5-78E | E | G | 9.21/C | 235–399 | CR/C, CR/E |
| UVSQ-SAT-NG | F | N | 9.21/C | 148–149.9 | CR/C, CR/D |
| HOL-NGSO2-I-S | HOL | N | 9.21/C | 148.02–148.11 | CR/C, CR/D |
| INSAT-COM(71E) | IND | G | A30A#7.1 | 17700–19700 | CR/C, CR/D |
| RGS-S-45E, RGS-S-35E, RGS-N | RUS | G, G, N | V/11.31.1/C | 7100–7155 | 11.2 notices |

**Overlap against the BR list.** Overlap with space transmitters caught 9 of the 11 networks. The two misses, UVSQ-SAT-NG and HOL-NGSO2-I-S, are **receive-only at 148 MHz**. The screen only looks at space transmitters, while footnote 5.221 protects Finnish services on this band. **Lesson:** direction logic and footnotes need their own rules.

**Worked example.** A calculation we can defend line by line.

```
RLNEUTRON-1 (USA), beam S1ATM, 2200–2290 MHz, 148 kHz emission

  Power density                  −50.2 dBW/Hz
  + 10·log10(4000 Hz)            +36.0 dB       → −14.2 dBW / 4 kHz
  + Antenna gain                  +5.6 dBi
  − Spreading, 160 km altitude   −115.1 dB
  = pfd                         −123.7 dB(W/m²/4 kHz)

  Limit at δ = 90°               −144
  Margin                         +20.3 dB ⚠ screen flag
```

Then the reviewer asks: *Would a 160 km orbit, one of several filed altitudes, ever produce this over Finland? Does the beam actually have 5.6 dBi at zenith? If the low altitude is a short-lived phase, does it matter?* It's a flag to review, not a conclusion. That is the correct behaviour.

**A clear false alarm.** HISPASAT-5-52.5W is flagged at +8.6 dB at δ = 0.2°. The satellite sits at 52.5°W, and Finland is on the very edge of its visibility. Its beam almost certainly points elsewhere. Without pointing data, peak gain can't rule this out.

### Terrestrial IFIC 3076

**Ran.** 4,057 assignments in `fxm_terra`, and only one neighbour shows up:

| | RUS | POL | FIN | Sweden, Norway, Estonia |
|---|---|---|---|---|
| Rows | 313 | 9 | 4 (fixed) | **0 in this issue** |

**Near the border.** 37 Russian land-mobile records (`FB`, `ML`) lie within 300 km of a rough Finnish border approximation, 28 of them within 100 km. Examples: Ruskeala and Sortavala (793–795 MHz), Lyaskelya, Vyborg and Kostomuksha (about 152–155 MHz), and Kingisepp (414–426 MHz). The file's `intent` column gives ADD, MODIFY, RECORDED or SUPPRESS directly.

**Inputs exist for P.1546.** `fxm_ant` has power, gain, height and direction fields. **The P.1546 calculation has not been run.** For scale, Vyborg at 153 MHz (12.8 dBW, if that's e.r.p., which is unverified) gives about 59 dB(µV/m) in free space at our rough 34 km distance, against a T/R 25-08 threshold of 12. Free space is only an upper bound, so this shows the case needs the real model; it doesn't show an exceedance.

**Note:** T/R 25-08's main table covers 29.7–470 MHz. The 793 MHz stations need another criterion, possibly its Annex 4.

---

## 9. Existing solutions

**Bottom line: we found no open-source or startup product that does this workflow end to end.** That's based on limited searches, so it's evidence, not proof. The components exist, though, and the commercial tools show what experts expect.

### Directly related

| Name | What it does | Takeaway | Confidence |
|---|---|---|---|
| **ITU SpaceCom, GIBC, BRSIS-Query** | The official comment, pfd and query tools. Windows only `[SW]` | Our calculation benchmark. **If anyone has Windows, validate pfd against GIBC** | Source |
| **ITU Space Explorer** | Web view of the SNS data; export is subscription-based `[RSOFT]` | Don't build on scraping it | Source |
| **Transfinite Visualyse** (EPFD, GSO, Professional) | Commercial simulation; reads SRS orbit data; S.1503 EPFD pass/fail. [Link](https://www.transfinite.com/content/Non_GSO_Satellite_Coordination) | Screening is deliberately conservative. Keep the two-step approach: screen, then detail | Vendor claim |
| **Integrasys VeryFiling** | Web EPFD check with a "regulator mode" showing pass/fail and why. [Link](https://satnews.com/2023/02/22/integrasys-launches-veryfiling-an-itu-filing-tool-for-satellite-operators-and-regulators/) | Good idea for us: explain *why it failed and what would fix it* | Press piece |
| **LS telcom SPECTRAemc** | Spectrum engineering tool; claims BR IFIC integration and automated bilateral and ITU coordination. [Link](https://www.lstelcom.com/en/products/spectrum-management/spectraemc/) | The incumbent type of tool regulators use. We differ on evidence and AI drafting | Search summary, vendor |
| **Satmen Telecom** | Consultancy: processes IFICs to find interfering filings, prepares written comments and SpaceCom files. [Link](http://satmen.com/index.php/itur-itu-br-ific) | **Proof that this workflow is valuable enough to pay for.** Humans do it today | Search snippet only; site's certificate failed, so not opened |

### AI and regulation research

| Name | What it does | Takeaway |
|---|---|---|
| **Radio-RAG** ([arXiv 2509.09651](https://arxiv.org/abs/2509.09651), [code](https://github.com/Zakaria010/Radio-RAG)) | RAG over the Radio Regulations, plus a multiple-choice benchmark. Reports about 97% on its retrieval metric, and notes naive document stuffing adds under 1% for GPT-4o | **Generic RAG isn't enough; structure matters.** Consider its dataset for testing citation lookup. Only 2 stars; it's a research artifact |
| **Ghasemi & Guinand** ([arXiv 2403.17819](https://arxiv.org/html/2403.17819v1)) | Rules-as-code extraction, RAG over about 2,000 regulatory documents, and a licence chatbot, using a locally hosted model | Warns of table loss in PDFs, automation bias and hallucination. Recommends human review. **No quantitative results** |
| **UK SPF AI report** ([techUK](https://www.techuk.org/resource/uk-spf-report-artificial-intelligence-for-spectrum-management.html)) | Regulator-side overview: licensing review, interference prediction, and hybrid AI plus conventional methods | Supports the "hybrid" architecture |

### Hugging Face

**Nothing relevant.** We queried the Hugging Face API directly. "Radio regulations", "spectrum management", "spectrum regulation", "satellite interference" and "ITU filing" each returned **zero** models and datasets. "ITU-R" returned only unrelated name matches.

The only telecom match is [`netop/TeleQnA`](https://huggingface.co/datasets/netop/TeleQnA) and models built on it. It's a general telecom knowledge benchmark, so it doesn't help with filings. **Don't train anything.** There's no labelled data, and a general-purpose LLM handles the text work.

### Open-source building blocks

| Component | Use | Status |
|---|---|---|
| [`access-parser`](https://pypi.org/project/access-parser/) | Read MDB, pure Python | **Tested: read 3074 and 3076.** Old and unpopular, so pin the version |
| [`mdbtools`](https://github.com/mdbtools/mdbtools) | Read MDB, native tools | 1,185 stars, active, GPL-2. Not tested here. Good fallback |
| [`eeveetza/Py1546`](https://github.com/eeveetza/Py1546) | P.1546-6, matches the reference approved by ITU-R WP 3K; includes validation data | README read. **Install blocked in our session; not run.** Licence not machine-detected, so read it |
| [`eeveetza/p1546`](https://github.com/eeveetza/p1546) | MATLAB/Octave reference | Same author; can be a cross-check |
| [`pycraf`](https://github.com/bwinkel/pycraf) | Antenna patterns and compatibility-study functions | GPL-3 per PyPI. Useful for gain envelopes |
| SEAMCAT | CEPT's simulation tool; its P.1546 is simplified `[SEAM]` | Not needed |

---

## 10. Options for what to build

| | **A. Deterministic core + LLM layer** (recommended) | B. LLM agent reads everything | C. Wrap ITU tools | D. Full simulation |
|---|---|---|---|---|
| **Idea** | SQL and Python compute everything; LLM explains, cites and drafts | Agent queries data and reasons freely | Automate SpaceCom and GIBC | Visualyse-style dynamic EPFD and interference |
| **Technical credibility (A, 25%)** | High: same input, same output | Low: hard to reproduce | High | Highest, in theory |
| **Extensibility (B, 25%)** | High: shared pipeline, swap rule packs | Medium | Low: separate tools | Low |
| **Usefulness (C, 20%)** | High | Flashy demo, shaky trust | Medium | Low in the time we have |
| **Accuracy (D, 15%)** | Tunable and measurable | Unpredictable | Good on pfd only | Good, but only if it gets finished |
| **Audit (E, 15%)** | High: every value traces back | Weak | Medium | Medium |
| **48-hour risk** | Low | Medium | **High:** Windows only, and hard to script | **Very high** |

**Recommendation: A.** It matches the brief almost word for word: "rule-based or deterministic calculation components" and "technical correctness... more important than the choice of model". Use GIBC only as a one-off validation if someone can run it. **Judgement.**

**Reducing false positives without pointing data.** In order of value for effort:

1. **Exclude by geometry.** Not visible from Finland means no finding. NGSO inclination plus coverage must reach 60°N.
2. **Use real orbits, not the worst one.** Test each filed orbit and each emission separately rather than taking maximums, and report them all.
3. **Use a beam type and service area.** A narrow beam with `srv_area` elsewhere and very low δ is suspect, so downgrade it.
4. **Report confidence separately from severity.** "+20 dB at peak gain" and "+20 dB toward Finland" are different statements.
5. **Add gain contours later.** If GIMS graphical data can be obtained, the peak-gain assumption goes away. Ask Traficom.

---

## 11. Proposed architecture

```
 ┌─────────────┐   ┌────────────┐   ┌──────────────────────────────────────┐
 │ IFIC watcher│──▶│  Ingest    │──▶│           Normalised SQLite          │
 │ schedule/   │   │ MDB→SQLite │   │  + source file hash, table, row IDs  │
 │ page check  │   │ + checksum │   └───────────────┬──────────────────────┘
 └─────────────┘   └────────────┘                   │
                                                    ▼
 ┌─────────────────────┐        ┌─────────────────────────────────────────┐
 │ Reference data      │───────▶│  Rule packs (deterministic, versioned)  │
 │ M4 API, workbook,   │        │  ┌───────────────┐  ┌────────────────┐  │
 │ RR limits as YAML   │        │  │ Space: reach, │  │ Terrestrial:   │  │
 │ with clause cites   │        │  │ overlap, 21-4,│  │ diff, distance,│  │
 └─────────────────────┘        │  │ AP5, provn    │  │ P.1546, T/R    │  │
                                │  └───────────────┘  └────────────────┘  │
                                └───────────────────┬─────────────────────┘
                                                    ▼
                                ┌─────────────────────────────────────────┐
                                │  Finding (shared schema) + ranking      │
                                └───────────────────┬─────────────────────┘
                                                    ▼
                                ┌─────────────────────────────────────────┐
                                │  LLM layer: explanation, draft letter   │
                                │  Input = finding JSON only. Numbers are │
                                │  checked against the finding afterwards │
                                └───────────────────┬─────────────────────┘
                                                    ▼
                                ┌─────────────────────────────────────────┐
                                │  Expert review UI → accept/reject/edit  │
                                │  → audit log → export. No auto-send.    │
                                └─────────────────────────────────────────┘
```

**The shared `Finding` is the extensibility story.** Space and terrestrial produce the same object, which is what criterion B wants to see:

```jsonc
{
  "id": "3074-125545347-S1ATM-pfd2200",
  "domain": "space",                    // or "terrestrial"
  "ific": 3074, "section": "API/A",
  "counterparty": "USA",
  "subject": {"network": "RLNEUTRON-1", "ntc_id": 125545347},
  "rule": {"id": "RR-T21-4-2200-2300", "clause": "RR 21.16, Table 21-4", "version": "RR 2024"},
  "calculation": {
    "inputs":  {"pwr_ds_max": -50.2, "gain_dbi": 5.6, "d_km": 160, "b_ref_hz": 4000, "delta_deg": 90},
    "formula": "pfd = ds + 10log10(B) + G − 10log10(4πd²)",
    "result": -123.7, "limit": -144, "margin_db": 20.3
  },
  "assumptions": ["peak gain toward Finland", "lowest filed altitude", "free space"],
  "finnish_assets": {"station_count": 170, "source": "Traficom workbook 05-11-2026"},
  "evidence": [{"file_sha256": "…", "table": "emiss", "key": {"grp_id": 125748048}}],
  "severity": "high", "confidence": "low",
  "deadline": "2026-10-23",
  "status": "needs_review"
}
```

**Where AI actually helps**

| Use AI for | Don't use AI for |
|---|---|
| Plain-language explanation of a finding | pfd, field strength, geometry |
| Drafting the letter from a template | Deciding whether a limit is exceeded |
| Extracting footnote conditions into YAML, **with human checking** | Inventing clause citations |
| Trend narrative over computed statistics | Being the only source of a number |
| Answering "why was this flagged?" from the evidence | Sending anything |

**Guardrail worth demoing:** after generation, every number and citation in the LLM's text is checked against the finding JSON. A mismatch blocks the draft. This addresses the hallucination risk flagged by the literature, and it's a small amount of code.

**Stack.** **Judgement.**

| Layer | Choice | Why |
|---|---|---|
| Language | Python | P.1546, parsers, team speed |
| Ingest | `access-parser`; `mdbtools` as fallback | Tested |
| Store | SQLite | Simple and portable, and it matches ITU's terrestrial direction |
| Rules | Python with YAML limit tables; each row carries a clause cite | Auditable, easy to diff |
| Propagation | `Py1546`, after checking licence and running its validation | ITU-WP-approved reference |
| Output | FastAPI or Streamlit; `.docx` or Markdown drafts; JSON and CSV | Fast to demo |
| LLM | Provider-agnostic, structured output, finding-only input | The brief doesn't mandate one |
| Tests | Golden calculations, hand-verified | Direct evidence for criterion A |

**Watcher realism.** ITU's site rejects plain scripted requests, so a watcher must be polite and low-frequency. Bulk reuse terms for the data aren't confirmed. Provide a manual-upload fallback.

---

## 12. Plan for the remaining time

**Saturday 7 Nov, first thing: ask Traficom.** Slots `[BRIEF]`: Space Sat 10–11 and 17–18; Terrestrial Sat 11–12 and 16–17; Q&A stand 9–12 and 14:30–18.

**Must ask**

1. **AP30/30A/30B:** the free 3074 has none. Will you provide `SPS_ALL` and `30B`, or the PDFs? Or is the free file enough?
2. **What does the 3074 and 3076 "accuracy" file expect?** A format? Only BR-listed cases, or calculated concerns too?
3. **Show them the RLNEUTRON-1 worked example.** Would an expert consider this useful or noise? Is peak gain the right first screen?
4. **Terrestrial stations and API/A:** 9.3 names satellite networks. Would Traficom raise a terrestrial concern on an API/A filing, and how?
5. **T/R 25-08 for Russia, and above 470 MHz:** does it apply? Which criterion for the 793 MHz stations? No Sweden, Norway or Estonia rows exist in 3076; is that expected?

**Should ask**

6. Workbook meanings: `MVV`, blank licence class, 9 GW powers, and `E` in the ITU power column (e.r.p.?).
7. Is the comment window on 3074 (23 Oct 2026, by our calculation) relevant, given it has already closed?
8. Do you keep a real sample letter we could use as a template?

**Priorities, in order**

| Priority | Item | Scoring |
|---|---|---|
| **P0** | Ingest to SQLite for both IFICs, with row-level provenance | E, A |
| **P0** | Finding schema; `provn` list; reach and overlap screen for 3074 | D, B |
| **P0** | Table 21-4 engine with hand-verified golden tests | A |
| **P0** | Submission files for **3074 and 3076** | Required |
| **P1** | Terrestrial: diff of two issues, distance filter, P.1546, T/R 25-08 | **B (25%)** |
| **P1** | Review UI with evidence panel and draft letter | C, E |
| **P2** | Appendix 5 thresholds; ranking refinement | D |
| **P2** | LLM number-and-citation guard | C, E |
| **P3** | Trends and anomalies for neighbours | Required by side quest; keep it small |
| **Skip** | EPFD simulation, model training, generic RR chatbot | Low return |

**Evaluating ourselves.** There's no public answer key, and the BR list isn't ground truth. Measure recall against the BR's Finland list as a *floor*, report the funnel, and have an expert review a handful at the Q&A. State the numbers honestly in the submission.

**Pitch in one line:** *"Every IFIC, every Finnish receiver, every limit checked. Each flag traceable to a table row and an RR clause, ready for an expert to sign in minutes."*

---

## 13. Risks

| Risk | Likelihood | Response |
|---|---|---|
| False-positive flood from peak gain | **Already seen** | Separate confidence, geometry exclusions, ranking |
| AP30 data unavailable | High | Ask early; declare the gap |
| RR numbers wrong from bad PDF extraction | Medium | Check every limit used against the PDF; golden tests |
| P.1546 package unusable or licence issue | Medium | Run validation early; Octave reference as fallback |
| `access-parser` fails on another issue | Low–medium | `mdbtools` fallback; run on several issues |
| ITU changes access or blocks scripted downloads | Medium | Manual upload path; cache with hash |
| Misreading regulatory wording | Medium | Use the term table in `itu-primary-sources.md` §8; have Traficom review |
| LLM invents a clause or number | Medium | Finding-only input; automated check |

## 14. What this research does not establish

- **Our screen's results are unvalidated.** They use peak gain, seven Table 21-4 rows, X=0 for NGSO at 17.7–19.3 GHz, and rough border points. No result here should be treated as a real concern.
- **P.1546 was not run.** Package installation was blocked in this session, so it's the first thing to try.
- **Not fully verified:** `agree_st` code meanings, why `ntc_id` values appear in 12xxx/32xxx pairs, AP30B Article 6 periods, No. 11.28.1, Finnish ITU filings (ICEYE, Aalto, Kuva Space), and data reuse terms. Details are in `itu-primary-sources.md`.
- **Absence claims** ("no open-source pipeline", "no ITU converter") reflect what we searched, not a proof.
- **Vendor capabilities** are vendors' own statements. Satmen's site couldn't be opened.

## Reproducing the results

Scripts are in [`spike/`](spike/): `ex.py` (MDB to dataframes), `screen.py` (space funnel), `terr.py` (terrestrial). They are throwaway, with hard-coded temporary paths at the top that need editing. Dependencies: `access-parser pandas openpyxl`. Run them on the zips from section 5, using a browser-style User-Agent to download.
