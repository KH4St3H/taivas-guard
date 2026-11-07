"""Streaming fallback for the primary exporter's Invalid string length limit."""
import ast
import datetime as dt
import json
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.dimensions import ColumnDimension

root = Path('tools/synthetic-data')
out = Path('outputs/finland-synthetic-20261107/finland_synthetic_stations_100000.xlsx')
records = json.loads((root / 'records.json').read_text(encoding='utf-8'))
headers = json.loads((root / 'headers.json').read_text(encoding='utf-8'))
builder = (root / 'build.mjs').read_text(encoding='utf-8')
notes_text = re.search(r'const notes=(\[.*?\n \]);', builder, re.S).group(1)
notes = ast.literal_eval(notes_text)
categories = list(dict.fromkeys(r[22] for r in records))
assert len(records) == 100000 and len(categories) == 8

wb = Workbook(write_only=True)
overview = wb.create_sheet('Overview')
data = wb.create_sheet('Frequencies of interest')
method = wb.create_sheet('Method and fields')
body_font = Font(name='Arial', size=10)
header_font = Font(name='Arial', size=10, bold=True, color='FFFFFF')
header_fill = PatternFill('solid', fgColor='244A73')
title_font = Font(name='Arial', size=14, bold=True, color='193B5F')

def cell(sheet, value, fmt='General', header=False, wrap=False):
    c = WriteOnlyCell(sheet, value=value)
    c.font = header_font if header else body_font
    c.number_format = fmt
    c.alignment = Alignment(vertical='center', horizontal='center' if header else None, wrap_text=wrap)
    if header:
        c.fill = header_fill
    return c

for sheet in (overview, data, method):
    sheet.sheet_view.showGridLines = False
    sheet.sheet_properties.tabColor = '244A73'

for k, width in {'A':34,'B':16,'C':66}.items():
    overview.column_dimensions[k].width = width
summary = {
    2:['Finland synthetic station inventory'],
    4:['Station records','=B18'],
    5:['Generation date',dt.datetime(2026,11,7)],
    6:['Random seed',20261107],
    7:['Record definition','One station with one representative assignment'],
    9:['Service category','Records','Count basis'],
    18:['Total records','=SUM(B10:B17)'],
    20:['Size interpretation'],
    21:['100,000 is the requested scenario size. It is not an estimate of today’s total operational stations.'],
    23:['Scope'],
    24:['40,000 fixed-link endpoints form 20,000 reciprocal links. Mobile rows do not expand every sector and band.'],
    26:['Source context'],
    27:['The challenge sample has 874 records; its note describes tens of millions of real assignment rows, a different counting unit.'],
    29:['All station identifiers, locations and technical values are fabricated. No operator ownership or regulatory compliance is asserted.'],
}
for i, category in enumerate(categories,10):
    summary[i] = [category,f'=COUNTIF(\'Frequencies of interest\'!$W$13:$W$100012,A{i})', 'Scenario: 2 × 24,000 historical LTE benchmark' if i==10 else 'Synthetic scenario assumption']
for rownum in range(1,31):
    overview.row_dimensions[rownum].height = 23
    values = summary.get(rownum, [])
    cells = [cell(overview,v,'yyyy-mm-dd' if rownum==5 and j==1 else '#,##0' if j==1 and (rownum==4 or 10<=rownum<=18) else 'General',header=rownum==9) for j,v in enumerate(values)]
    if rownum==2:
        cells[0].font=title_font
    if rownum==18:
        for c in cells:
            c.font=Font(name='Arial',size=10,bold=True)
            c.fill=PatternFill('solid',fgColor='E7EEF5')
    overview.append(cells)

from openpyxl.utils import get_column_letter
for i in range(1,27):
    data.column_dimensions[get_column_letter(i)].width = {1:23,8:23,9:23,10:23,23:31,25:23}.get(i,19)
data.freeze_panes='C13'
data.auto_filter.ref='A12:Z100012'
top = {
 1:['Finland synthetic station inventory — 100,000 records'],
 3:['Entirely synthetic. One representative assignment per station. Counts are a modelling scenario, not a Finnish station census.'],
 5:['Core columns and bilingual header positions follow the challenge sample. Additional metadata is in W:Z.'],
 7:['Frequencies and bandwidths retain explicit-unit text for sample compatibility. Numeric heights, coordinates, gains and powers are typed values.'],
 10:[None,None,'WGS84 longitude','WGS84 latitude'],
 11:headers['english']+['Service category','ITU station class','Paired station ID','Data origin'],
 12:headers['finnish']+['Palvelu','Asemaluokka','Pariasema','Aineiston alkuperä'],
}
for i in range(1,13):
    if i in (11,12):
        data.row_dimensions[i].height=44
    cs=[cell(data,v,header=i in (11,12),wrap=i in (11,12)) for v in top.get(i,[])]
    if i==1: cs[0].font=title_font
    data.append(cs)
formats={2:'0.00000',3:'0.00000',4:'0',5:'0',10:'0',11:'0',12:'0.0',15:'0.0',17:'#,##0.000',20:'0.0'}
for i,row in enumerate(records):
    data.append([cell(data,v,formats.get(j,'General')) for j,v in enumerate(row)])
    if (i+1)%25000==0:
        print(f'Streamed {i+1} rows',flush=True)

for col,width in {'A':27,'B':97,'C':100}.items():
    method.column_dimensions[col].width=width
method.freeze_panes='A2'
fields=[]
for i,h in enumerate(headers['english']):
    meaning = ('Unique synthetic ID' if i==0 else 'Numeric decimal degrees, WGS84' if i in (2,3) else 'Text, explicit MHz; blank RX where not applicable' if i in (8,9) else 'Numeric radiated power in W' if i==17 else 'ERP / EIRP basis label; no legacy-code assumption' if i==18 else 'Numeric dBi' if i==12 else 'Numeric feeder loss in dB' if i==20 else 'Text, explicit kHz' if i in (7,14) else 'See reference header and methodology above')
    fields.append([get_column_letter(i+1),h,meaning])
method_rows=notes+[[],[],['Column','Field','Meaning / units']]+fields+[
 ['W','Service category','Explicit synthetic service family'],
 ['X','ITU station class','FB / FX / BC / BT / FC / FA / UC'],
 ['Y','Paired station ID','Reciprocal reference for fixed radio links; otherwise blank'],
 ['Z','Data origin','Always SYNTHETIC'],
]
for i,row in enumerate(method_rows,1):
    method.row_dimensions[i].height = 24 if i in (1,len(notes)+3) else 45
    method.append([cell(method,v,header=i in (1,len(notes)+3),wrap=True) for v in row])
wb.save(out)

# Preserve the already independently calculated summary values in Excel's formula caches.
# openpyxl writes formulas but does not evaluate them. Their COUNTIF/SUM results were
# calculated by Artifact Tool, inspected above and independently counted from all rows.
import collections
import zipfile
counts=collections.Counter(r[22] for r in records)
cached={'B4':len(records),'B18':len(records),**{f'B{i}':counts[s] for i,s in enumerate(categories,10)}}
temp=out.with_suffix('.tmp')
with zipfile.ZipFile(out) as source, zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as dest:
    for item in source.infolist():
        payload=source.read(item.filename)
        if item.filename=='xl/worksheets/sheet1.xml':
            xml=payload.decode('utf-8')
            for address,value in cached.items():
                pattern=rf'(<c\b[^>]*\br="{address}"[^>]*>)(.*?)(</c>)'
                def replace(match, value=value):
                    inside=match.group(2)
                    inside=re.sub(r'<v(?:\s[^>]*)?>.*?</v>|<v\s*/>', '',inside,flags=re.S)
                    return match.group(1)+inside+f'<v>{value}</v>'+match.group(3)
                xml,n=re.subn(pattern,replace,xml,count=1,flags=re.S)
                assert n==1,address
            payload=xml.encode('utf-8')
        dest.writestr(item,payload)
temp.replace(out)
print('Saved',out,out.stat().st_size,flush=True)
