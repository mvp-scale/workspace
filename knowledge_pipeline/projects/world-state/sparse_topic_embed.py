import json,random,time,sys,os,numpy as np
from collections import defaultdict
sys.path.insert(0,".");from expert1_runtime import ExpertS;from article_reader import ArticleReader
G=json.load(open('/workspace/data/anchors/mn_ds/gold_T28b.json'));cats=sorted({v['l1'] for v in G.values()})
rows=[json.loads(l) for l in open('/workspace/data/anchors/mn_ds/train.jsonl')]
U=[r for r in rows if r.get('category_level_1') in cats and (r.get('title') or '').strip() and (r.get('content') or '').strip()]
R=[r for r in U if len(r['content'])>=800];rng=random.Random(20261105);by=defaultdict(list)
for r in R:by[r['category_level_1']].append(r)
S=[]
for c in sorted(by):S+=rng.sample(by[c],100)
ids={id(r) for r in S};T=[r for r in U if id(r) not in ids]
random.Random(1).shuffle(T);T=T[:6000]
e=ExpertS("runs/expert1/expert1_v6b_student.pkl");A=ArticleReader(e)
LIM=float(sys.argv[2]) if len(sys.argv)>2 else 1e9
def emb(rs,path):
    if os.path.exists(path):return np.load(path)
    t0=time.time();X=[]
    for i,r in enumerate(rs):
        if time.time()-t0>LIM:print('time cap at',i);return None
        X.append(np.mean([e.student(r['title']+". "+w) for w in A.windows(r['content'])],0))
        if i%200==0:print(i,round(time.time()-t0),flush=True)
    X=np.array(X,dtype=np.float32);np.save(path,X);return X
d='runs/pulse/'
emb(S,d+'sparse_emb_eval.npy');emb(T,d+'sparse_emb_train.npy')
