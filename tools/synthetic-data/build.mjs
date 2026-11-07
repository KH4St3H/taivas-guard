import fs from 'node:fs/promises';

const out = 'outputs/finland-synthetic-20261107';
const inputs = 'tools/synthetic-data';
const seed = 20261107;
let state = seed;
const random = () => {state = (Math.imul(1664525, state) + 1013904223) >>> 0; return state / 4294967296;};
const between = (a,b) => a + random()*(b-a);
const pick = a => a[Math.floor(random()*a.length)];
const round = (x,n=2) => Number(x.toFixed(n));
const normal = () => Math.sqrt(-2*Math.log(Math.max(random(),1e-12)))*Math.cos(2*Math.PI*random());
const countries = JSON.parse(await fs.readFile(`${inputs}/countries.geojson`,'utf8'));
const fin = countries.features.find(f=>f.properties.ADM0_A3==='FIN');
if(!fin) throw Error('Finland boundary missing');
const polygons = (fin.geometry.type==='MultiPolygon' ? fin.geometry.coordinates : [fin.geometry.coordinates]).map(rings=>({rings,box:[Math.min(...rings[0].map(p=>p[0])),Math.min(...rings[0].map(p=>p[1])),Math.max(...rings[0].map(p=>p[0])),Math.max(...rings[0].map(p=>p[1]))]}));
function ringContains(ring,x,y){let inside=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){const [xi,yi]=ring[i],[xj,yj]=ring[j];if(((yi>y)!==(yj>y)) && x<(xj-xi)*(y-yi)/(yj-yi)+xi) inside=!inside;}return inside;}
function inFin(x,y){return polygons.some(p=>x>=p.box[0]&&x<=p.box[2]&&y>=p.box[1]&&y<=p.box[3]&&ringContains(p.rings[0],x,y)&&!p.rings.slice(1).some(r=>ringContains(r,x,y)));}
// Regional centres are sampling anchors, never actual station locations.
const hubs=[[24.94,60.17],[24.94,60.17],[23.76,61.50],[22.27,60.45],[25.47,65.01],[25.75,62.24],[27.68,62.89],[25.66,60.98],[21.80,61.49],[21.62,63.10],[28.19,61.06],[29.76,62.60],[25.73,66.50],[27.73,64.22],[23.11,63.84],[27.27,61.69],[24.46,60.99],[23.82,67.65],[27.03,69.00]];
function location(coastal=false){for(let tries=0;tries<100000;tries++){let x,y;if(coastal || random()<0.78){const h=pick(coastal?[[24.94,60.17],[22.27,60.45],[21.62,63.10],[25.47,65.01],[23.04,59.97],[19.94,60.10],[27.19,60.47]]:hubs);x=h[0]+normal()*0.22;y=h[1]+normal()*0.10;}else{x=between(19.5,31.6);y=between(59.8,70.1);}x=round(x,5);y=round(y,5);if(inFin(x,y))return [x,y];}throw Error('Location sampling failed');}
function bearing(a,b){const r=Math.PI/180;const dl=(b[0]-a[0])*r;return round((Math.atan2(Math.sin(dl)*Math.cos(b[1]*r),Math.cos(a[1]*r)*Math.sin(b[1]*r)-Math.sin(a[1]*r)*Math.cos(b[1]*r)*Math.cos(dl))/r+360)%360,1);}
function partner(a){for(let j=0;j<10000;j++){let d=between(1,25),v=between(0,2*Math.PI);const b=[round(a[0]+d*Math.cos(v)/(111*Math.cos(a[1]*Math.PI/180)),5),round(a[1]+d*Math.sin(v)/111,5)];if(inFin(...b))return b;}throw Error('No link partner');}
const hz = f => f==null?null:`${f.toFixed(6)} MHz`;
const bwtext = bw => `${bw.toFixed(3)} kHz`;
const rows=[];
const counts={};
function add(service,cls,itu,loc,tx,rx,bw,opts={}){
 const id=`SYN-FI-${String(rows.length+1).padStart(6,'0')}`;
 const ground=Math.round(between(5,loc[1]>66?450:loc[1]>62?230:150));
 const mast=opts.mast??Math.round(between(20,65));
 const ant=opts.ant??Math.max(2,mast-Math.round(between(1,5)));
 const gain=opts.gain??round(between(7,18),1);
 const loss=opts.loss??round(between(0.3,2.0),1);
 const power=opts.power??round(10**between(1.5,3.2),3);
 const az=opts.az??round(between(0,359.9),1);
 rows.push([id,cls,...loc,ground,mast,'KIINTEÄ',bwtext(bw),hz(tx),hz(rx),ant,ground+ant,gain,opts.emission??'G7W',opts.bandwidth??bwtext(bw),opts.directivity==='ND'?null:az,opts.pol??'V',power,opts.basis??'EIRP','W',loss,opts.directivity??'D',service,itu,opts.pair??null,'SYNTHETIC']);
 counts[service]=(counts[service]??0)+1;
 return id;
}
// One representative carrier per station; sector/band expansion is intentionally omitted.
for(let i=0;i<48000;i++){
 const [txlo,rxlo,bw]=pick([[758,703,10000],[791,832,10000],[925,880,5000],[1805,1710,20000],[2110,1920,15000],[2620,2500,20000],[3400,3400,100000]]);
 const offset=txlo===3400?pick([50,150,250,350]):bw/2000;
 const tx=round(txlo+offset,3),rx=round(rxlo+offset,3);
 const roof=random()<0.58,mast=Math.round(roof?between(15,35):between(35,85));
 add('Public mobile base station','MOBILE','FB',location(),tx,rx,bw,{mast,pol:'X',gain:round(between(14,19),1),power:round(10**between(2.7,3.7),3)});
}
// 20,000 duplex links = 40,000 endpoints. Centre frequencies are illustrative, not a channel-plan claim.
const links=[[2025,2110,2200,2290,1000],[6425,6525,6770,6870,14000],[7125,7275,7425,7575,28000],[8025,8150,8275,8400,28000],[17700,18100,18700,19100,28000],[18100,18500,19100,19500,56000],[24500,25000,25500,26000,56000]];
for(let i=0;i<20000;i++){
 const [lo,hi,rlo,rhi,bw]=pick(links),t=between(0.05,0.95);
 const tx=round(lo+bw/2000+t*(hi-lo-bw/1000),3),rx=round(rlo+bw/2000+t*(rhi-rlo-bw/1000),3);
 const a=location(),b=partner(a),ida=`SYN-FI-${String(rows.length+1).padStart(6,'0')}`,idb=`SYN-FI-${String(rows.length+2).padStart(6,'0')}`;
 const gain=round(tx<3000?between(18,27):between(30,43),1),p=round(10**between(0.3,2.8),3),pol=pick(['H','V']);
 add('Fixed radio link','FX','FX',a,tx,rx,bw,{gain,power:p,pol,az:bearing(a,b),pair:idb});
 add('Fixed radio link','FX','FX',b,rx,tx,bw,{gain,power:p,pol,az:bearing(b,a),pair:ida});
}
for(let i=0;i<2400;i++)add('FM broadcasting','BC','BC',location(),Math.max(87.6,round(87.5+Math.floor(random()*205)*0.1,1)),null,200,{mast:Math.round(between(30,320)),gain:round(between(2,12),1),power:round(10**between(1.3,4.8),2),basis:'ERP',pol:pick(['H','V','M']),az:null,directivity:'ND',emission:'F8E'});
for(let i=0;i<1200;i++)add('DVB-T2 broadcasting','BT','BT',location(),474+8*Math.floor(random()*28),null,8000,{mast:Math.round(between(35,320)),gain:round(between(8,16),1),power:round(10**between(2,4.9),2),basis:'ERP',pol:'H',az:null,directivity:'ND'});
for(let i=0;i<5000;i++){
 const [lo,hi,delta]=pick([[146,154.6,4.6],[160,164.5,4.5],[410,420,10],[450,460,10]]);
 const tx=round(lo+0.025+Math.floor(random()*(hi-lo-0.05)/0.0125)*0.0125,4);
 add('Private land mobile','PMR','FB',location(),tx,round(tx+delta,4),12.5,{gain:round(between(2,9),1),power:round(between(5,80),2),basis:'ERP',az:null,directivity:'ND',emission:'F3E'});
}
for(let i=0;i<700;i++)add('Maritime coast station','MARITIME','FC',location(true),pick([156.3,156.5,156.6,156.8,156.9]),pick([156.3,156.5,156.6,156.8,156.9]),25,{gain:round(between(2,7),1),power:round(between(5,50),2),basis:'ERP',az:null,directivity:'ND',emission:'F3E'});
for(let i=0;i<500;i++){const f=round(118+Math.floor(random()*740)*0.025,3);add('Aeronautical ground station','AVIATION','FA',location(),f,f,25,{gain:round(between(0,5),1),power:round(between(5,50),2),basis:'ERP',az:null,directivity:'ND',emission:'A3E'});}
for(let i=0;i<2200;i++){
 const [tx,rx,bw]=random()<0.75?[round(between(14010,14490),3),round(between(11710,12740),3),2000]:[round(between(28050,29450),3),round(between(17750,19650),3),20000];
 add('Satellite earth terminal','EARTH','UC',location(),tx,rx,bw,{mast:Math.round(between(4,18)),gain:round(between(32,46),1),power:round(10**between(3.2,4.8),2),pol:pick(['H','V','RHCP','LHCP'])});
}
if(rows.length!==100000)throw Error(`Wrong size ${rows.length}`);
// Maritime channels are simplex: RX equals TX.
for(const row of rows)if(row[22]==='Maritime coast station')row[9]=row[8];
const byId=new Map(rows.map(r=>[r[0],r]));
for(const r of rows){if(!inFin(r[2],r[3]))throw Error('Coordinate outside Finland');if(r[10]>r[5]||r[11]!==r[4]+r[10]||r[10]<=0)throw Error('Height inconsistency');if(r[17]<=0)throw Error('Power');if(r[24]){const p=byId.get(r[24]);if(!p||p[24]!==r[0]||p[8]!==r[9]||p[9]!==r[8])throw Error('Link mismatch');}}
await fs.writeFile(`${inputs}/records.json`,JSON.stringify(rows));
console.log('Generated and validated',rows.length,counts);
if (process.argv.includes('--records-only')) process.exit(0);

const { Workbook, SpreadsheetFile } = await import('@oai/artifact-tool');
const wb=Workbook.create();
const summary=wb.worksheets.add('Overview');
const data=wb.worksheets.add('Frequencies of interest');
const method=wb.worksheets.add('Method and fields');
for(const s of [summary,data,method]){s.showGridLines=false;s.tabColor='#244A73';}
const headers=JSON.parse(await fs.readFile(`${inputs}/headers.json`,'utf8'));
data.getRange('A1').values=[['Finland synthetic station inventory — 100,000 records']];
data.getRange('A3').values=[['Entirely synthetic. One representative assignment per station. Counts are a modelling scenario, not a Finnish station census.']];
data.getRange('A5').values=[['Core columns and bilingual header positions follow the challenge sample. Additional metadata is in W:Z.']];
data.getRange('A7').values=[['Frequencies and bandwidths retain explicit-unit text for sample compatibility. Numeric heights, coordinates, gains and powers are typed values.']];
data.getRange('A10:D10').values=[['',null,'WGS84 longitude','WGS84 latitude']];
data.getRange('A11:Z11').values=[[...headers.english,'Service category','ITU station class','Paired station ID','Data origin']];
data.getRange('A12:Z12').values=[[...headers.finnish,'Palvelu','Asemaluokka','Pariasema','Aineiston alkuperä']];
data.getRangeByIndexes(12,0,rows.length,26).values=rows;
console.log('Wrote all records');
const end=rows.length+12;
data.getRange('A11:Z12').format={fill:'#244A73',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:44,verticalAlignment:'center',horizontalAlignment:'center'};
data.getRange('A1').format.font={name:'Arial',size:14,bold:true,color:'#193B5F'};
data.getRange('A:Z').format.columnWidth=19;
data.getRange('A:A').format.columnWidth=23;
data.getRange('H:J').format.columnWidth=23;
data.getRange('W:W').format.columnWidth=31;
data.getRange('Y:Y').format.columnWidth=23;
data.getRange(`C13:D${end}`).setNumberFormat('0.00000');
data.getRange(`E13:F${end}`).setNumberFormat('0');
data.getRange(`K13:L${end}`).setNumberFormat('0');
data.getRange(`M13:M${end}`).setNumberFormat('0.0');
data.getRange(`P13:P${end}`).setNumberFormat('0.0');
data.getRange(`R13:R${end}`).setNumberFormat('#,##0.000');
console.log('Finished data formats');
data.freezePanes.freezeRows(12);data.freezePanes.freezeColumns(2);
// Preserve the sample's bilingual header positions and row 13 data start.
summary.getRange('A2').values=[['Finland synthetic station inventory']];
summary.getRange('A4:B7').values=[['Station records',100000],['Generation date',new Date('2026-11-07T00:00:00Z')],['Random seed',seed],['Record definition','One station with one representative assignment']];
summary.getRange('B4').formulas=[['=B18']];
summary.getRange('B5').setNumberFormat('yyyy-mm-dd');
summary.getRange('A9:C9').values=[['Service category','Records','Count basis']];
const entries=Object.entries(counts);
summary.getRange('A10:C17').values=entries.map(([s,n])=>[s,n,s==='Public mobile base station'?'Scenario: 2 × 24,000 historical LTE benchmark':'Synthetic scenario assumption']);
summary.getRange('B10:B17').formulas=entries.map(([s])=>[`=COUNTIF('Frequencies of interest'!$W$13:$W$${end},A${10+entries.findIndex(e=>e[0]===s)})`]);
summary.getRange('A18').values=[['Total records']];summary.getRange('B18').formulas=[['=SUM(B10:B17)']];
summary.getRange('A20').values=[['Size interpretation']];
summary.getRange('A21').values=[['100,000 is the requested scenario size. It is not an estimate of today’s total operational stations.']];
summary.getRange('A23').values=[['Scope']];
summary.getRange('A24').values=[['40,000 fixed-link endpoints form 20,000 reciprocal links. Mobile rows do not expand every sector and band.']];
summary.getRange('A26').values=[['Source context']];
summary.getRange('A27').values=[['The challenge sample has 874 records; its note describes tens of millions of real assignment rows, a different counting unit.']];
summary.getRange('A29').values=[['All station identifiers, locations and technical values are fabricated. No operator ownership or regulatory compliance is asserted.']];
const notes=[
 ['Topic','Definition or assumption','Source / evidence'],
 ['Size', '100,000 unique station IDs, as requested. This is a scenario, not a national census.', 'User request, 7 November 2026'],
 ['Historical benchmark','Traficom reports about 24,000 LTE base stations in 2023. The 48,000 mobile rows are a chosen scenario, not a measured 2026 extrapolation.','https://www.traficom.fi/files/media/publication/Mastomarkkinaselvitysraportti%202023.pdf (printed page 7)'],
 ['Reference structure','First 22 columns and English/Finnish header rows 11/12 follow the supplied workbook. Data starts at row 13.','Traficom_SinceAI_Frequencies_of_interest_v05112026.xlsx'],
 ['Assignment unit','One representative TX/RX channel per synthetic station. Real stations may have many bands, sectors and assignments.','ARCHITECTURE.md, design principle 2; challenge workbook note'],
 ['Geography','78% of general draws cluster around regional centres; the rest sample the national boundary. Coastal stations use coastal anchors. Weights are assumptions.','Natural Earth country polygon; centres are geographical anchors, not station sites.'],
 ['Boundary','Coordinates must lie inside the Natural Earth Finland polygon. National footprint only; no cadastral, inland-water, terrain or actual-site verification.','https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_10m_admin_0_countries.geojson'],
 ['Reproducibility','LCG seed 20261107; deterministic generation order. Technical distributions are engineering assumptions.','Generator retained in repository'],
 ['Mobile bands','Representative carriers in 700, 800, 900, 1800, 2100, 2600 and 3500 MHz bands; base-station TX/RX orientation; 3500 MHz TDD.','https://www.traficom.fi/en/radio-licences-and-frequencies/use-radio-frequencies/frequencies-and-license-holders-public-mobile-networks'],
 ['Fixed links','Paired endpoints exchange TX/RX frequencies and point at their partner. Separation sampled at 1–25 km before coordinate rounding.','Illustrative channels guided by M4 band summary in repository; not an approved channel plan.'],
 ['S-band fixed links','Includes 2025–2110 / 2200–2290 MHz examples so screening can exercise the sample’s S-band protection case.','docs/research-discarded/problem-and-solution-brief.md section 7; engineering scenario only'],
 ['Power','Radiation power is numeric watts. Radiation power (ITU) explicitly contains ERP or EIRP; these are labels, not inferred legacy codes.','ERP referenced to dipole; EIRP to isotropic radiator. No conversion between bases is implied.'],
 ['Antenna gain','Gain is synthetic dBi; retained reference header says dB. It is independent metadata and is already included in radiated ERP/EIRP power.','Do not add gain to the radiated power again.'],
 ['Transmission line','Positive feeder loss in dB; radiated power already includes it.','Do not subtract this loss again from the provided radiated power.'],
 ['Heights','ASL = ground ASL + antenna AGL; 0 < antenna AGL <= mast height. Terrain heights are synthetic and not DEM-derived.','Numerical consistency verified for all rows.'],
 ['Bandwidth','Channel and transmission bandwidths use explicit kHz text, matching the reference style. Emission class omits bandwidth because a separate field supplies it.','Synthetic engineering assumptions.'],
 ['Receive frequencies','Broadcast transmitters have blank RX because no protected receiver is represented. Maritime and aviation examples are simplex.','Blank RX means not applicable, never zero.'],
 ['Licence classes','FX / BC / BT retain the sample vocabulary; MOBILE / PMR / MARITIME / AVIATION / EARTH are explicit synthetic categories.','No claim that added labels are Traficom licence codes.'],
 ['Polarisation','H horizontal; V vertical; M mixed; X cross-polarised; RHCP/LHCP circular.','Synthetic metadata, not measured antenna patterns.'],
 ['Directions','Degrees clockwise from true north. Blank for ND omnidirectional stations. Earth-terminal azimuths are illustrative; orbit/elevation are not modelled.','Do not treat terminal azimuth as a validated satellite pointing solution.'],
 ['Limits','No pfd/field-strength limits, compliance labels or harmful-interference verdicts are fabricated.','Apply deterministic propagation and independently sourced rules downstream.'],
 ['Data quality','No deliberate duplicates, negative heights or gigawatt power outliers. All 100,000 records are labelled SYNTHETIC.','Verified: unique IDs, geometry, heights, positive powers and reciprocal pair keys/frequencies.'],
 ['Service counts','All service counts, including 700 coast stations, are deliberately sized scenarios; they are not official station estimates.','National size across all services was not established.']
 ];
method.getRange(`A1:C${notes.length}`).values=notes;
const fields=headers.english.map((h,i)=>[String.fromCharCode(65+i),h, i===0?'Unique synthetic ID':i===2||i===3?'Numeric decimal degrees, WGS84':i===8||i===9?'Text, explicit MHz; blank RX where not applicable':i===17?'Numeric radiated power in W':i===18?'ERP / EIRP basis label; no legacy-code assumption':i===12?'Numeric dBi':i===20?'Numeric feeder loss in dB':i===7||i===14?'Text, explicit kHz':'See reference header and methodology above']);
method.getRange(`A${notes.length+3}:C${notes.length+3}`).values=[['Column','Field','Meaning / units']];
method.getRange(`A${notes.length+4}:C${notes.length+25}`).values=fields;
method.getRange(`A${notes.length+26}:C${notes.length+29}`).values=[['W','Service category','Explicit synthetic service family'],['X','ITU station class','FB / FX / BC / BT / FC / FA / UC'],['Y','Paired station ID','Reciprocal reference for fixed radio links; otherwise blank'],['Z','Data origin','Always SYNTHETIC']];
for(const s of [summary,method]){s.getUsedRange().format.font={name:'Arial',size:10};s.getUsedRange().format.verticalAlignment='center';s.getUsedRange().format.rowHeight=23;}
summary.getRange('A:A').format.columnWidth=34;summary.getRange('B:B').format.columnWidth=16;summary.getRange('C:C').format.columnWidth=66;
summary.getRange('B4:B4').setNumberFormat('#,##0');summary.getRange('B10:B18').setNumberFormat('#,##0');
summary.getRange('A2').format.font={name:'Arial',size:14,bold:true};
summary.getRange('A9:C9').format={fill:'#244A73',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:25};
summary.getRange('A18:C18').format={fill:'#E7EEF5',font:{name:'Arial',size:10,bold:true}};
method.getRange('A:A').format.columnWidth=27;method.getRange('B:B').format.columnWidth=97;method.getRange('C:C').format.columnWidth=100;
method.getUsedRange().format.wrapText=true;method.getUsedRange().format.rowHeight=45;
method.getRange('A1:C1').format={fill:'#244A73',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:24};
method.freezePanes.freezeRows(1);
console.log('Calculating summary');
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'Overview!A9:C18',include:'values,formulas',tableMaxRows:10,tableMaxCols:3,maxChars:2200})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:10},maxChars:1000})).ndjson);
for(const [s,range,file] of [[summary,'A1:C30','overview'],[data,'A10:F20','stations'],[data,'H10:V18','technical'],[data,'W10:Z18','metadata'],[method,'A1:C8','method']]){
 try{const png=await wb.render({sheetName:s.name,range,scale:1,format:'png'});await fs.writeFile(`${out}/${file}-preview.png`,new Uint8Array(await png.arrayBuffer()));console.log('Rendered',file);}catch(e){console.log('Render unavailable:',e.message);}
}
console.log('Exporting workbook');
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(`${out}/finland_synthetic_stations_100000.xlsx`);
await fs.writeFile(`${inputs}/validation.json`,JSON.stringify({count:rows.length,uniqueIds:byId.size,serviceCounts:counts,seed,geometry:'Natural Earth FIN',pairedEndpoints:40000,checks:['country containment','height consistency','positive power','unique IDs','reciprocal pairs and frequencies']},null,2));
console.log('Saved workbook');
