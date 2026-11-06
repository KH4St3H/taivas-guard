import pandas as pd,numpy as np
pd.set_option('display.width',220,'display.max_columns',30,'display.max_rows',60)
T='/tmp/sinceai.LRfUUn';R=lambda n:pd.read_pickle(f'{T}/p76/{n}.pkl')
t,a,g,x,c=[R(n) for n in 'fxm_terra fxm_ant fxm_geo fxm_tx ref_stn_cls'.split()]
print(c.to_dict('records')[:28])
print(t.adm.value_counts().head(20).to_dict());print(pd.crosstab(t.adm[t.adm.isin(['RUS','FIN','POL','LTU','LVA','EST','S','NOR','DNK','BLR'])],t.intent))
lm=t[t.stn_cls.isin(['FB','ML','FP','FL','FX'])].merge(g[['geo_key','long_dec','lat_dec','ctry','site_name','radius']],on='geo_key',how='left')
for c_ in 'long_dec lat_dec freq_assgn'.split(): lm[c_]=pd.to_numeric(lm[c_],errors='coerce')
# great circle to approx FI border anchors
B=np.array([[60.0,27.8],[61.0,28.9],[62.0,30.9],[63.5,31.5],[65.0,29.8],[67.0,29.5],[68.8,28.5],[69.8,29.0],[70.05,27.5],[69.0,20.5],[66.0,23.7],[60.0,20.0],[59.9,23.0],[59.9,25.5]])
def dist(la,lo):
    a=np.radians(la);b=np.radians(B[:,0]);dl=np.radians(lo-B[:,1]);return (6371*np.arccos(np.clip(np.sin(a)*np.sin(b)+np.cos(a)*np.cos(b)*np.cos(dl),-1,1))).min()
lm['dkm']=[dist(a_,b_) if pd.notna(a_) else np.nan for a_,b_ in zip(lm.lat_dec,lm.long_dec)]
print(lm.stn_cls.value_counts().to_dict());l2=lm[lm.stn_cls.isin(['FB','ML','FP','FL'])&lm.adm.ne('FIN')]
print(pd.crosstab(l2.adm,pd.cut(l2.dkm,[0,50,100,300,1000,5e4])))
n=l2[l2.dkm<=300].merge(a[a.tx_rx.eq('T')|a.tx_rx.isna()][['terrakey','pwr_dbw','pwr_ant','gain_max','hgt_agl','eff_hgtmax','azm_max_e','ant_dir','pwr_eiv']],on='terrakey',how='left').sort_values('dkm')
print(len(n));print(n[['terrakey','adm','stn_cls','freq_assgn','bdwdth','intent','notice_typ','lat_dec','long_dec','site_name','dkm','pwr_dbw','gain_max','eff_hgtmax','hgt_agl','pwr_eiv']].head(25).to_string())
print(n.drop_duplicates('terrakey').groupby(['adm','stn_cls','intent']).size());n.to_pickle(T+'/near.pkl')
