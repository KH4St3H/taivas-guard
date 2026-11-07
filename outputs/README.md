# Evaluation exports

`ific_3074/` contains provisional Space IFIC 3074 screening results. These are
possible concerns requiring expert review, not confirmed interference. Read
`manifest.json` for the source hash, code hashes, configuration and coverage gaps.

After importing an archive, reproduce with:

```sh
python -m ific_guard.cli export --domain space --issue 3074 --out outputs/ific_3074
```

The command selects the latest imported revision of that issue. Pass
`--sha256 <archive-hash>` to pin a revision. It evaluates the source again without
modifying review decisions or sending notifications. This prevents later issues'
mutable review cases from leaking into historical evaluation files.

- `cases.csv`: ranked, flat results; notice IDs are separated by semicolons.
- `cases.json`: the same results with full evidence and assumptions.
- `manifest.json`: provenance, configuration, executed rules, runtime and output hashes.

Ranking is severity, estimated deadline, rule ID, then notice-family ID.
Case files are deterministic for fixed inputs and code. Manifest generation time
and measured runtime vary. The format remains provisional pending ticket 02.
Terrestrial export explicitly refuses to run until tickets 08-10 add its rules;
it must not produce an empty file that implies no concerns.

Raw ITU archives and databases remain in ignored `data/shared/`, not in these outputs.
