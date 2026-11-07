# Evaluation exports

`ific_3074/` contains Space IFIC 3074 screening results, and `ific_3076/`
the Terrestrial IFIC 3076 land-mobile results. These are possible concerns requiring
expert review, not confirmed interference. Read `manifest.json` for the source hash,
code hashes, configuration and coverage gaps.

Current refresh: Space 3074 has 175 cases (43 high, 94 medium, 38 low); Terrestrial 3076 has 29 (1 high, 22 medium, 6 low). Both were generated from clean commit `941282f`; per-folder verification notes explain every change.

After importing the inputs into a fresh database, reproduce from a clean Git checkout into an ignored staging directory:

```sh
python -m ific_guard.cli export --domain space --issue 3074 --out data/evaluation-stage/ific_3074
python -m ific_guard.cli export --domain terrestrial --issue 3076 --out data/evaluation-stage/ific_3076
```

Verify both manifests, then copy both staged folders into `outputs/`. The exporter refuses dirty or unidentified code by default; `--allow-dirty` is an explicit exploratory override and records that state. Generating both files in staging prevents the first export from dirtying the checkout before the second.

Import Terrestrial 3075 as well. Without it, the 3076 export still runs and says on
every finding that changes were not checked against the previous issue.

The command selects the latest imported revision of that issue. Pass
`--sha256 <archive-hash>` to pin a revision. It evaluates the source again without
modifying review decisions or sending notifications. This prevents later issues'
mutable review cases from leaking into historical evaluation files.

- `cases.csv`: ranked, flat results; notice IDs are separated by semicolons.
- `cases.json`: compact JSON with the same results and all evidence and assumptions; formatting does not discard calculations.
- `manifest.json`: provenance, configuration, executed rules, runtime and output hashes.
- `funnel.json` (terrestrial): how many notices each filter removed and why, and which
  were not calculated.

Ranking is severity, estimated deadline, severity score, margin, rule ID, then
notice-family ID.
Case files are deterministic for fixed inputs and code. Manifest generation time
and measured runtime vary. Traficom accepts CSV, and any open machine-readable format; JSON is preferred over MDB, and no fields are mandatory (ticket 02).

`hand-check.md` rechecks a sample of each rule from raw rows, and `neighbour-trends.md` counts neighbouring notices across issues 3074-3083.

Raw ITU archives and databases remain in ignored `data/shared/`, not in these outputs.
