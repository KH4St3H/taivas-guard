"""Read the final workbook independently; no workbook modifications."""
import collections
import json
from pathlib import Path
import openpyxl

path = Path('outputs/finland-synthetic-20261107/finland_synthetic_stations_100000.xlsx')
book = openpyxl.load_workbook(path, read_only=True, data_only=True)
source_records = json.loads(Path('tools/synthetic-data/records.json').read_text(encoding='utf-8'))
sheet = book['Frequencies of interest']
counts = collections.Counter()
ids = set()
pairs = {}
total = 0
for row in sheet.iter_rows(min_row=13, max_col=26, values_only=True):
    if not row[0]:
        continue
    total += 1
    assert list(row) == source_records[total - 1], ('Export changed a value', row[0])
    assert row[0] not in ids, ('Duplicate ID', row[0])
    ids.add(row[0])
    assert isinstance(row[2], (int, float)) and isinstance(row[3], (int, float))
    assert 19 <= row[2] <= 32 and 59 <= row[3] <= 71
    assert 0 < row[10] <= row[5]
    assert row[11] == row[4] + row[10]
    assert row[17] > 0 and row[19] == 'W' and row[18] in ('ERP', 'EIRP')
    assert row[25] == 'SYNTHETIC'
    if row[21] == 'ND':
        assert row[15] is None, ('Omnidirectional antenna has azimuth', row[0])
    bw = float(row[7].split()[0])
    assert bw > 0 and row[7].endswith(' kHz')
    for frequency in row[8:10]:
        if frequency is not None:
            assert frequency.endswith(' MHz')
            assert float(frequency.split()[0]) > bw / 2000
    if row[22] in ('FM broadcasting', 'DVB-T2 broadcasting'):
        assert row[9] is None
    else:
        assert row[9] is not None
    if row[24]:
        pairs[row[0]] = (row[24], row[8], row[9])
    counts[row[22]] += 1
assert total == len(ids) == 100000
assert len(pairs) == 40000
for key, (partner, tx, rx) in pairs.items():
    assert pairs[partner] == (key, rx, tx)
summary = book['Overview']
assert summary['B18'].value == total, ('Cached total', summary['B18'].value)
for r in range(10, 18):
    assert summary.cell(r, 2).value == counts[summary.cell(r, 1).value]
book.close()
print({'records': total, 'unique_ids': len(ids), 'paired_endpoints': len(pairs), 'counts': dict(counts), 'xlsx_bytes': path.stat().st_size})
