import sys,pandas as pd,pickle
from access_parser import AccessParser
db=AccessParser(sys.argv[1]);out=sys.argv[2]
for t in sys.argv[3:]:
    d=db.parse_table(t); df=pd.DataFrame({k:list(v) for k,v in d.items()}); df.to_pickle(f'{out}/{t}.pkl'); print(t,df.shape,list(df.columns)[:40],flush=True)
