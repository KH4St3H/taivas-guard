import pandas as pd,numpy as np,re,sys
pd.set_option('display.width',240,'display.max_columns',40,'display.max_rows',80,'display.max_colwidth',40)
T='/tmp/sinceai.LRfUUn';R=lambda n:pd.read_pickle(f'{T}/p74/{n}.pkl')
ce,no,ps,sb,gr,em,sc,sa,pv,ob,ng,ge,cp=[R(n) for n in 'com_el notice pub_ssn s_beam grp emiss srv_cls srv_area provn orbit non_geo geo c_pfd'.split()]
print('ntc_type',ce.ntc_type.value_counts().to_dict(),'prov',ce.prov.value_counts().to_dict(),'ids',sorted(set(ce.ntc_id.astype(int)))[:3])
print('ssn',ps.ssn_ref.value_counts().to_dict())
print('adm top',ce.adm.value_counts().head(15).to_dict())
for c in 'freq_min freq_max bdwdth pfd_pk_7g'.split(): print(c,pd.to_numeric(gr[c],errors='coerce').describe()[['count','min','50%','max']].round(3).to_dict())
# --- BR-listed Finland
fin=pv[pv.adm=='FIN'].merge(gr[['grp_id','ntc_id','freq_min','freq_max','emi_rcp']],on='grp_id').merge(no[['ntc_id','adm','prov','ntc_type','wic_part']].rename(columns={'adm':'filer'}),on='ntc_id').merge(ce[['ntc_id','sat_name']],on='ntc_id',how='left')
print('FIN provn',len(fin),'ntc',fin.ntc_id.nunique());
print(fin.groupby(['sat_name','filer','ntc_type','coord_prov','agree_st','emi_rcp'],dropna=False).agg(n=('grp_id','nunique'),fmin=('freq_min','min'),fmax=('freq_max','max'),ids=('ntc_id',lambda s:sorted(set(s))[:2])))
ssn=ps.groupby('ntc_id').ssn_ref.apply(lambda s:','.join(sorted(set(map(str,s)))))
print(ssn[ssn.index.isin(fin.ntc_id)])
print('srv_area FIN',sa[sa.ctry=='FIN'].merge(gr[['grp_id','ntc_id']],on='grp_id').merge(ce[['ntc_id','sat_name','adm','ntc_type','prov']],on='ntc_id').drop_duplicates('ntc_id')[['sat_name','adm','ntc_type','prov','f_excl_api']])
# --- screen
raw=pd.read_excel('/workspaces/codespaces-blank/docs/challenge/Traficom_SinceAI_Frequencies_of_interest_v05112026.xlsx',header=None)
x=raw.iloc[12:].dropna(how='all').copy();x.columns=raw.iloc[10].astype(str)
def hz(v):
    m=re.match(r'\s*([\d.,]+)\s*(kHz|MHz|GHz|Hz)',str(v));return float(m[1])*{'Hz':1,'kHz':1e3,'MHz':1e6,'GHz':1e9}[m[2]]/1e6 if m else np.nan
x['rx']=x['RX frequency'].map(hz);x['bw']=x['Channel bandwidth'].map(hz);x['lat']=x.Latitude.astype(float);x['lon']=x.Longitude.astype(float);x=x.dropna(subset=['rx'])
x['bw']=x.bw.fillna(0);x['lo']=x.rx-x.bw/2;x['hi']=x.rx+x.bw/2
print('stations usable',len(x))
g=gr.merge(sb[['ntc_id','emi_rcp','beam_name','gain','bore_long','bore_lat']],on=['ntc_id','emi_rcp','beam_name'],how='left')
for c in 'freq_min freq_max bdwdth gain pfd_pk_7g'.split(): g[c]=pd.to_numeric(g[c],errors='coerce')
e=em.copy();e['pwr_ds_max']=pd.to_numeric(e.pwr_ds_max,errors='coerce');e['pep_max']=pd.to_numeric(e.pep_max,errors='coerce')
ea=e.groupby('grp_id').agg(ds=('pwr_ds_max','max'),pep=('pep_max','max'))
g=g.merge(ea,left_on='grp_id',right_index=True,how='left').merge(ce[['ntc_id','adm','sat_name','ntc_type','prov','long_nom']],on='ntc_id')
print('groups in com_el',len(g),'ntc',g.ntc_id.nunique(),' E',(g.emi_rcp=='E').sum())
sp=g[(g.emi_rcp=='E')&g.ntc_type.isin(['G','N'])].copy();print('space tx groups',len(sp),'ntc',sp.ntc_id.nunique(),'missing ds',sp.ds.isna().mean().round(3),'missing gain',sp.gain.isna().mean().round(3))
Re=6378.;rg=42164.
# overlap with Finnish rx
lo,hi=x.lo.values,x.hi.values
sp['nst']=[int(((lo<b)&(hi>a)).sum()) for a,b in zip(sp.freq_min,sp.freq_max)]
print('funnel: notices all',ce.ntc_id.nunique(),'space-tx',sp.ntc_id.nunique(),'overlap any FI rx',sp[sp.nst>0].ntc_id.nunique(),'groups',(sp.nst>0).sum())
# limits (selected verified rows) P,r per Table 21-4: limit(d)=P for d<=5, P+r(d-5), P+20r>=25
L=[(1525,1530,-154,.5,.004,'21-4 1525-1530'),(2025,2110,-154,.5,.004,'21-4 2025-2110'),(2200,2300,-154,.5,.004,'21-4 2200-2300'),(2500,2690,-136,.55,1,'21-4 2500-2690'),(8025,8500,-150,.5,.004,'21-4 8025-8500'),(19300,19700,-115,.5,1,'21-4 19.3-19.7'),(17700,19300,-115,.5,1,'21-4 17.7-19.3 (X=0)')]
def lim(P,r,d): return P+r*np.clip(d-5,0,20)
def sw(b): return None
rows=[]
ng2=ob.copy();ng2['ap']=pd.to_numeric(ng2.apog_km,errors='coerce');ng2['pe']=pd.to_numeric(ng2.perig_km,errors='coerce');ng2['inc']=pd.to_numeric(ng2.inclin_ang,errors='coerce');ng2['h']=ng2.pe.fillna(pd.to_numeric(ng2.op_ht_km,errors='coerce'))
orb=ng2.groupby('ntc_id').agg(hmin=('h','min'),inc=('inc','max'))
sp['ds2']=sp.ds
for _,s in sp.iterrows():
    if pd.isna(s.ds) or pd.isna(s.gain): continue
    for a,b,P,r,bw,name in L:
        if s.freq_min<b and s.freq_max>a:
            # worst case over FI lat 59.8-70.1, lon 19.5-31.5
            best=None
            if s.ntc_type=='G':
                ln=s.long_nom
                if pd.isna(ln):continue
                for lat in [59.8,65,70.1]:
                  for lon in [19.5,25,31.5]:
                    cg=np.cos(np.radians(lat))*np.cos(np.radians(lon-float(ln)))
                    gam=np.arccos(cg);
                    if cg<=Re/rg: continue
                    d=np.sqrt(Re*Re+rg*rg-2*Re*rg*cg);el=np.degrees(np.arctan((cg-Re/rg)/np.sin(gam)))
                    ds=s.ds;val=min(s.ds+10*np.log10(bw*1e6),s.pep if pd.notna(s.pep) else 1e9)+s.gain-10*np.log10(4*np.pi*(d*1e3)**2)
                    m=val-lim(P,r,el)
                    if best is None or m>best[0]: best=(m,val,el,d)
            else:
                if s.ntc_id not in orb.index or pd.isna(orb.hmin[s.ntc_id]):continue
                h=orb.hmin[s.ntc_id]
                for el in [0,5,10,20,25,40,60,90]:
                    d=np.sqrt((Re*np.sin(np.radians(el)))**2+2*Re*h+h*h)-Re*np.sin(np.radians(el))
                    val=min(s.ds+10*np.log10(bw*1e6),s.pep if pd.notna(s.pep) else 1e9)+s.gain-10*np.log10(4*np.pi*(d*1e3)**2);m=val-lim(P,r,el)
                    if best is None or m>best[0]: best=(m,val,el,d)
            if best: rows.append(dict(ntc=s.ntc_id,name=s.sat_name,adm=s.adm,t=s.ntc_type,prov=s.prov_y,band=name,fmin=s.freq_min,fmax=s.freq_max,gain=s.gain,ds=s.ds,pep=s.pep,pfd=round(best[1],1),el=round(best[2],1),d=round(best[3]),margin=round(best[0],1),nst=s.nst,pk7=s.pfd_pk_7g,bl=s.bore_long,bt=s.bore_lat,beam=s.beam_name))
r=pd.DataFrame(rows);print('groups in limit bands',len(r),'ntc',r.ntc.nunique() if len(r) else 0)
if len(r):
    r=r.sort_values('margin',ascending=False)
    a=r.groupby(['name','adm','t','band']).agg(ntc=('ntc','first'),grps=('ntc','size'),maxm=('margin','max'),exc=('margin',lambda s:(s>0).sum()),maxst=('nst','max'),pfd=('pfd','max'),el=('el','first'),gain=('gain','max')).sort_values('maxm',ascending=False);print(a.head(30))
    print(r.head(8).T)
r.to_pickle(f'{T}/screen.pkl')
ov=sp[sp.nst>0].groupby(['sat_name','adm','ntc_type','prov_y']).agg(grps=('grp_id','size'),fmin=('freq_min','min'),fmax=('freq_max','max'),st=('nst','max')).sort_values('st',ascending=False);print(ov.head(40));print('BR FIN nets overlapped by screen?',set(fin.sat_name)&set(sp[sp.nst>0].sat_name),'BR only',set(fin.sat_name)-set(sp[sp.nst>0].sat_name))
print('c_pfd');print(cp.merge(ce[['ntc_id','sat_name','adm']],on='ntc_id').groupby(['sat_name','adm','freq_min','freq_max','bdwdth','pfd','ra_stn_type'],dropna=False).size().head(20))
