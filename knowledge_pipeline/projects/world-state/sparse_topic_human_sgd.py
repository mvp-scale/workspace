import json,random,time,numpy as np,sys
from collections import defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from scipy.sparse import hstack
G=json.load(open('/workspace/data/anchors/mn_ds/gold_T28b.json'));cats=sorted({v['l1'] for v in G.values()});print(len(cats),cats)
rows=[json.loads(l) for l in open('/workspace/data/anchors/mn_ds/train.jsonl')]
U=[r for r in rows if r.get('category_level_1') in cats and (r.get('title') or '').strip() and (r.get('content') or '').strip()]
R=[r for r in U if len(r['content'])>=800];rng=random.Random(20261105);by=defaultdict(list)
for r in R:by[r['category_level_1']].append(r)
S=[]
for c in sorted(by):S+=rng.sample(by[c],100)
ids={id(r) for r in S};T=[r for r in U if id(r) not in ids]
print(len(U),len(R),len(S),len(T))
tx=lambda r:r['title']+'. '+r['content']
Xt=[tx(r) for r in T];yt=[r['category_level_1'] for r in T];Xs=[tx(r) for r in S];ys=np.array([r['category_level_1'] for r in S])
def wilson(k,n,z=1.96):
    p=k/n;d=1+z*z/n;c=p+z*z/(2*n);a=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n));return [round((c-a)/d,4),round((c+a)/d,4)]
out={'n_train':len(T),'n_eval':len(S),'train_median_chars':float(np.median([len(r['content']) for r in T])),'eval_median_chars':float(np.median([len(r['content']) for r in S]))}
def score(name,P,cl):
    o=np.argsort(-P,1)[:,:2];cl=np.array(cl);f=cl[o[:,0]]==ys;t=f|(cl[o[:,1]]==ys)
    out[name+'_first']=round(f.mean(),4);out[name+'_top2']=round(t.mean(),4)
    out[name+'_first_range']=wilson(f.sum(),len(ys));out[name+'_top2_range']=wilson(t.sum(),len(ys))
    rec={c:round(float(f[ys==c].mean()),3) for c in cats};out[name+'_recall']=rec
    out[name+'_weakest3']=sorted(rec.items(),key=lambda x:x[1])[:3];print(name,out[name+'_first'],out[name+'_top2'],out[name+'_weakest3'])
for name,mk in [('word12sgd',lambda:TfidfVectorizer(ngram_range=(1,2),min_df=3,max_features=300000,sublinear_tf=True)),]:
    v=mk();A=v.fit_transform(Xt);m=SGDClassifier(loss='log_loss',alpha=2e-6,max_iter=30,tol=None,random_state=0,n_jobs=4).fit(A,yt)
    score(name,m.predict_proba(v.transform(Xs)),m.classes_)
    ts=[]
    for x in Xs[:400]:
        t0=time.perf_counter();m.predict_proba(v.transform([x]));ts.append((time.perf_counter()-t0)*1e6)
    out[name+'_median_us']=round(float(np.median(ts)),1)
json.dump(out,open('runs/pulse/sparse_topic_human_sgd.json','w'),indent=1)
