# Finland synthetic station workbook

The delivered workbook is `outputs/finland-synthetic-20261107/finland_synthetic_stations_100000.xlsx`. Its methodology sheet explains the assumptions and source references. The 100,000 records are a synthetic scenario, not an official inventory.

## Rebuild

Run from the repository root with Node.js and Python with `openpyxl` installed. Download the public Natural Earth boundary file first:

```powershell
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson' -OutFile tools/synthetic-data/countries.geojson
New-Item -ItemType Directory -Force outputs/finland-synthetic-20261107
node tools/synthetic-data/build.mjs --records-only
python tools/synthetic-data/export_streaming.py
python tools/synthetic-data/verify.py
```

`headers.json` preserves the original sample's first 22 bilingual headers. The fixed random seed is 20261107. Reproduction also depends on the downloaded country boundary version.

The streaming exporter handles the full dataset. The Artifact Tool exporter hit an `Invalid string length` limit at this size. The optional preview scripts use Artifact Tool on bounded captures of the saved workbook and require that package in the runtime.

The workbook contains live summary formulas and independently counted initial cached values. Verification reads every saved record back and compares it with the generated input, checks unique IDs, heights, power units and reciprocal links, and reconciles summary totals.
