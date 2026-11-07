import fs from 'node:fs/promises';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
const book=await SpreadsheetFile.importXlsx(await FileBlob.load('tools/synthetic-data/preview-source.tmp'));
for(const [sheetName,range,file] of [['Overview','A1:C30','overview'],['Frequencies of interest','A10:F20','stations'],['Frequencies of interest','H10:V18','technical'],['Frequencies of interest','W10:Z18','metadata'],['Method and fields','A1:C8','method']]){
 const blob=await book.render({sheetName,range,scale:1,format:'png'});
 await fs.writeFile(`outputs/finland-synthetic-20261107/${file}-preview.png`,new Uint8Array(await blob.arrayBuffer()));
 console.log('Verified saved-file preview',file);
}
