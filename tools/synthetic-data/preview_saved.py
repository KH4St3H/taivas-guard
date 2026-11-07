"""Capture bounded ranges from the saved workbook for final visual QA."""
from copy import copy
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
import openpyxl
from openpyxl.utils import get_column_letter

source=Path('outputs/finland-synthetic-20261107/finland_synthetic_stations_100000.xlsx')
read=openpyxl.load_workbook(source,read_only=True,data_only=True)
small=openpyxl.Workbook()
small.remove(small.active)
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(source) as archive:
    for idx,(name,lastrow,lastcol) in enumerate([('Overview',30,3),('Frequencies of interest',20,26),('Method and fields',8,3)],1):
        sheet=small.create_sheet(name)
        sheet.sheet_view.showGridLines=False
        with archive.open(f'xl/worksheets/sheet{idx}.xml') as stream:
            prefix=stream.read(100000).decode('utf-8',errors='ignore')
        head=ET.fromstring(prefix.split('<sheetData>')[0]+'</worksheet>')
        for col in head.findall('s:cols/s:col',ns):
            for colidx in range(int(col.attrib['min']),int(col.attrib['max'])+1):
                sheet.column_dimensions[get_column_letter(colidx)].width=float(col.attrib['width'])
        for row in read[name].iter_rows(max_row=lastrow,max_col=lastcol):
            for source_cell in row:
                if source_cell.value is None:
                    continue
                target=sheet.cell(source_cell.row,source_cell.column,source_cell.value)
                target.font=copy(source_cell.font)
                target.fill=copy(source_cell.fill)
                target.border=copy(source_cell.border)
                target.alignment=copy(source_cell.alignment)
                target.number_format=source_cell.number_format
        with archive.open(f'xl/worksheets/sheet{idx}.xml') as stream:
            for event,element in ET.iterparse(stream,events=['end']):
                if element.tag.endswith('}row'):
                    rownum=int(element.attrib['r'])
                    if rownum>lastrow:
                        break
                    if 'ht' in element.attrib:
                        sheet.row_dimensions[rownum].height=float(element.attrib['ht'])
                    element.clear()
read.close()
small.save('tools/synthetic-data/preview-source.tmp')
print('Captured final workbook ranges')
