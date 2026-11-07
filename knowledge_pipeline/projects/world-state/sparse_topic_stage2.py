import json,random,time,sys,numpy as np
exec(open('sparse_topic_embed.py').read().split("e=ExpertS")[0])
from sklearn.linear_model import LogisticRegression
out=json.load(open('runs/pulse/sparse_topic_human_stage2_tmp.json')) if False else {}
d='runs/pulse/';Xs=np.load(d+'sparse_emb_eval.npy');Xt=np.load(d+'sparse_emb_train.npy')
yt=np.array([r['category_level_1'] for r in T]);ys=np.array([r['category_level_1'] for r in S]);assert len(Xt)==len(yt)
def wilson(k,n,z=1.96):
    p=k/n;dd=1+z*z/n;c=p+z*z/(2*n);a=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n));return [round((c-a)/dd,4),round((c+a)/dd,4)]
mu=Xt.mean(0);sd=Xt.std(0)+1e-6
m=LogisticRegression(C=1,max_iter=500,n_jobs=6).fit((Xt-mu)/sd,yt)
t0=time.perf_counter();P=m.predict_proba((Xs-mu)/sd);ts=(time.perf_counter()-t0)/len(Xs)*1e6
cl=m.classes_;o=np.argsort(-P,1)[:,:2];f=cl[o[:,0]]==ys;t=f|(cl[o[:,1]]==ys)
out['emb_n_train']=len(yt);out['emb_first']=round(f.mean(),4);out['emb_top2']=round(t.mean(),4);out['emb_first_range']=wilson(f.sum(),len(ys));out['emb_top2_range']=wilson(t.sum(),len(ys))
rec={c:round(float(f[ys==c].mean()),3) for c in cats};out['emb_recall']=rec;out['emb_weakest3']=sorted(rec.items(),key=lambda x:x[1])[:3]
out['emb_classifier_only_us_per_article']=round(ts,1);print(out)
json.dump(out,open(d+'sparse_topic_human_stage2.json','w'),indent=1)
