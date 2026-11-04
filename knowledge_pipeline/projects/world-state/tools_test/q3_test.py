import json,time,re
from quantulum3 import parser
d=json.load(open('../runs/fusion/demo.json'))['items']
for k,it in enumerate(d,1):
    t=" ".join(it['sentences']) if isinstance(it['sentences'],list) else it['sentences']
    try: q=[(x.surface,x.value,x.unit.name) for x in parser.parse(t)]
    except Exception as e: q=str(e)[:60]
    print(k,q)
rows=[json.loads(l) for l in open('../data/pool_train.jsonl',encoding='utf-8')][:300]
t0=time.time(); n=0
for r in rows:
    try: n+=len(parser.parse(r['text'][:1500]))
    except Exception: pass
print('ms/item',round((time.time()-t0)/300*1000,1),'quantities/item',round(n/300,2))
