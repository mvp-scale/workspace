"""T42 sparse selective test (pre-registered L1011). Same split and model as sparse_topic_human.py; adds abstain line and per-category right-within-two.
    python3 sparse_selective.py   (from projects/world-state)"""
import re,json
src=open('sparse_topic_human.py').read().split("for name,mk in")[0]
exec(src)
v=TfidfVectorizer(ngram_range=(1,2),min_df=3,max_features=300000,sublinear_tf=True);A=v.fit_transform(Xt);m=LogisticRegression(C=20,max_iter=300,n_jobs=6).fit(A,yt)
P=m.predict_proba(v.transform(Xs));cl=np.array(m.classes_);o=np.argsort(-P,1)[:,:2]
top2=(cl[o[:,0]]==ys)|(cl[o[:,1]]==ys);first=cl[o[:,0]]==ys;mass=P[np.arange(len(P))[:,None],o].sum(1)
res={'n':len(ys),'top2_all':round(float(top2.mean()),4),'per_category_top2':{c:round(float(top2[ys==c].mean()),3) for c in cats}}
res['categories_under_080']=[c for c,x in res['per_category_top2'].items() if x<0.80]
lines={}
for t in (0.5,0.6,0.7,0.8,0.9,0.95):
    a=mass>=t;k=int((top2&a).sum());n=int(a.sum());lines[str(t)]={'answered':n,'share':round(n/len(ys),4),'top2_right':round(k/max(n,1),4),'range':wilson(k,n) if n else None,'first_right':round(float((first&a).sum()/max(n,1)),4)}
res['by_line']=lines
a=mass>=0.7;res['abstained_by_category_at_070']={c:int(((~a)&(ys==c)).sum()) for c in cats}
res['abstained_top2_right_at_070']=round(float(top2[~a].mean()),4) if (~a).sum() else None
json.dump(res,open('runs/pulse/sparse_selective.json','w'),indent=1)
print(json.dumps({k:res[k] for k in ('top2_all','categories_under_080','by_line','abstained_top2_right_at_070')},indent=0))
print(res['per_category_top2'])
