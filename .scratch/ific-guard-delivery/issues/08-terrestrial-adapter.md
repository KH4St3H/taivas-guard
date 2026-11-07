# 08 Terrestrial adapter, diff and filter

Status: ready-for-agent
Type: task
Size: L
Blocked by: 01
Owns: `ific_guard/terrestrial/adapter.py`, `ific_guard/terrestrial/diff.py`, `tests/test_terrestrial_adapter.py`

## Goal

The first half of the side quest: read terrestrial land-mobile notices, identify what is new, modified or withdrawn between consecutive issues, and filter foreign assignments that may be relevant to Finland.

## Inputs

`data/shared/brific3075.mdb` and `brific3076.mdb`. The schema differs from space. Tables as seen in Terrestrial 3083, so confirm them on 3076:

- `fxm_terra`: 7,371 rows, including `terrakey`, `freq_assgn`, `freq_min`, `freq_max`, `bdwdth`, `geo_key`, `adm`. Print the full column list.
- `fxm_geo`: `geo_key`, `long_dec`, `lat_dec`, `site_alt`, `ctry`, `site_name`
- `fxm_ant`: `terrakey`, `pwr_dbw`, `gain_max`, `hgt_agl`, `eff_hgtmax`, `azm_max_e`, `polar`, `tx_rx`
- `fxm_ant_hgt`: effective height by azimuth
- `fxm_nat_serv`: `nat_srv`; `ref_nat_srv` and `ref_stn_cls` give meanings
- `fxm_target`: `terrakey`, `target`, `action`; `fxm_coord`: `adm`, `coord_prov`

Read `ReadMe_3076.pdf` (`.../BRIFIC/ReadMe/ReadMe_3076.pdf`) for structure. Note the zip holds one `.mdb`, despite ARCHITECTURE.md section 4.1 mentioning a converter to SQLite. `MdbReader` in `screening/space.py` reads it directly.

## Do

1. Define land mobile using service and station-class codes from the reference tables. State the exact codes and why.
2. Produce a typed `TerrestrialIssue`, keeping `terrakey` verbatim plus raw source rows.
3. Diff two issues using the data's own `action` and `target` fields if they mean what they appear to, otherwise by comparing rows. Check this: an IFIC is an update, so absence from the next issue may not mean withdrawn. Report what you conclude and why.
4. Filter to foreign stations near Finland: by administration (neighbours, per ticket 02), and by distance to the Finnish border, with a band-dependent limit in configuration.
5. Add land/sea path information, or a clear interface for ticket 09 to compute it.

## Acceptance

- Counts for 3075 to 3076: new, modified and withdrawn, by administration, and how many pass the filter. Reconcile them against the issue's published totals (`pub_totals`, Article 11 index) where possible.
- Hand check of 5 notices, including one of each change type if present.
- `MdbReader` handles the schema on 3076 without error, with row counts compared to `mdbtools` if available.

## Not in scope

Field strength (ticket 09), cases and export (ticket 10), and trends (ticket 11).
