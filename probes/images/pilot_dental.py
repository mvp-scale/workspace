import json,zipfile
Z='/workspace/data/sources/image-lab/dentex/test_data.zip'
W={'çürük':'caries','gömülü':'impacted','lezyon':'lesion','kanal':'root_canal','küretaj':'curettage','saglam':'healthy','çekim':'extraction','kırık':'fracture'}
z=zipfile.ZipFile(Z)
items=[json.loads(l) for l in open('pilots/dental.jsonl')]
out=[]
for it in items:
    d=json.loads(z.read(f"disease/label/{it['source_id']}.json"))
    cnt={v:0 for v in W.values()}; teeth=set(); ct=set()
    for s in d['shapes']:
        p=s['label'].split('-'); w=p[1]; t=p[-1] if len(p)>2 else None
        k=W.get(w,'other_'+w); cnt[k]=cnt.get(k,0)+1
        if t: teeth.add(t)
        if k=='caries' and t: ct.add(t[0])
    up=bool(ct&{'1','2'}); lo=bool(ct&{'3','4'})
    m={f'{k}_count':v for k,v in cnt.items()}
    m.update({f'has_{k}':v>0 for k,v in cnt.items()})
    m['n_teeth_annotated']=len(teeth); m['jaw']='both' if up and lo else 'upper' if up else 'lower' if lo else 'none'
    it['meta']=m; out.append(it)
open('pilots/dental.jsonl','w').write(''.join(json.dumps(i,ensure_ascii=False)+'\n' for i in out))
