"""python3 analyse.py -> metrics.json in the diversity scratch dir. Reads test1.json, test2.json (from compose_runs.js) and the rules CSVs. Seeded, deterministic."""
import json, re, random, math, csv, itertools, collections, statistics
D='/tmp/claude-0/-workspace/cdb40569-0681-424f-99c4-07e70f2075c8/scratchpad/diversity2/'
R='/workspace/probes/persona/rules_v2/'
LEX=list(csv.DictReader(open(R+'sowhat2_lexicon.csv')))+list(csv.DictReader(open(R+'sowhat_lexicon.csv'))); TPL=list(csv.DictReader(open(R+'sowhat2_templates.csv')))+[dict(id=h['id'],template=h['text']) for h in csv.DictReader(open(R+'sowhat2_hooks.csv'))]
tok=lambda s: re.findall(r"[a-z0-9']+(?:-[a-z0-9']+)*", s.lower())
def grams(t,n): return [tuple(t[i:i+n]) for i in range(len(t)-n+1)]
def entropy(c):
    n=sum(c.values()); return -sum(v/n*math.log2(v/n) for v in c.values())
def dist(xs):
    xs=sorted(xs); 
    if not xs: return {}
    h=collections.Counter(xs); return dict(n=len(xs),min=xs[0],median=statistics.median(xs),mean=round(statistics.mean(xs),2),p90=xs[int(.9*(len(xs)-1))],max=xs[-1],hist=dict(sorted(h.items())))
def jac(a,b):
    A,B=set(a),set(b); return len(A&B)/len(A|B) if A|B else 0
def triples(items,key_ok,rng,N=20000,groups=None):
    """items: list of dicts with 'tk' (tokens). returns share of triples where any two share a 5-gram, mean pairwise trigram Jaccard."""
    for it in items:
        it.setdefault('g5',set(grams(it['tk'],5))); it.setdefault('g3',set(grams(it['tk'],3)))
    if groups is None: pools=[(items,1)]
    else: pools=[(g,math.comb(len(g),3)) for g in groups if len(g)>=3]
    if not pools: return None
    hit=0; js=[]; done=0; tries=0
    while done<N and tries<N*50:
        tries+=1
        pool=rng.choices([p[0] for p in pools],weights=[p[1] for p in pools])[0]
        tr=rng.sample(pool,3)
        if key_ok and len({key_ok(x) for x in tr})<3: continue
        done+=1
        if any(a['g5'] & b['g5'] for a,b in itertools.combinations(tr,2)): hit+=1
        js+= [jac(a['g3'],b['g3']) for a,b in itertools.combinations(tr,2)]
    return dict(triples=done,share_any_pair_5gram=round(hit/done,4),mean_pairwise_trigram_jaccard=round(statistics.mean(js),4))
# lexicon/template attribution
def frags_of_templates(): 
    out=[]
    for t in TPL:
        for f in re.split(r'\{\w+\}',t['template']): out.append((tok(f),'template '+t['id']))
    return out
TFR=frags_of_templates()
LEXTOK=[]
for r in LEX:
    for col in ('down','up','down_bare','up_bare','text','text_alt'):  # v1 lexicon columns plus v2 text
        if r.get(col): LEXTOK.append((tok(r[col]),f"lexicon {r['kind']}:{r['id']}.{col}"))
def attribute(g):
    L=list(g); res=[]
    for toks,name in LEXTOK+TFR:
        if any(toks[i:i+len(L)]==L for i in range(len(toks)-len(L)+1)): res.append(name)
    return res
def metrics(items,name,seed=7):
    rng=random.Random(seed)
    for it in items:
        it['full']=(it['headline']+' '+(it['line2'] or '')).strip(); it['tk']=tok(it['full']); it['htk']=tok(it['headline'])
    n=len(items); M=dict(name=name,n=n)
    op=collections.Counter(' '.join(it['headline'].split()[:3]).lower() for it in items)
    M['openers']=dict(distinct=len(op),top1_share=round(op.most_common(1)[0][1]/n,4),top8=op.most_common(8))
    tc=collections.Counter(it['template'] for it in items)
    M['templates']=dict(distinct=len(tc),entropy_bits=round(entropy(tc),3),max_entropy_bits=round(math.log2(len(tc)),3),top1_share=round(tc.most_common(1)[0][1]/n,4),counts=tc.most_common())
    lc=collections.Counter(it['line2'] for it in items)
    M['line2']=dict(distinct=len(lc),empty_share=round(lc.get('',0)/n,4),distinct_nonempty=len(lc)-(1 if '' in lc else 0),top8=lc.most_common(8))
    hc=collections.Counter(it['headline'] for it in items)
    M['headlines']=dict(distinct=len(hc),distinct_share=round(len(hc)/n,4),top3=hc.most_common(3))
    M['length']=dict(headline_words=dist([len(it['headline'].split()) for it in items]),line2_words=dist([len(it['line2'].split()) for it in items if it['line2']]))
    M['numbers']=dict(headlines_with_digit=sum(bool(re.search(r'\d',it['headline'])) for it in items),line2_with_digit=sum(bool(re.search(r'\d',it['line2'] or '')) for it in items),percent_sign=sum('%' in it['full'] for it in items))
    M['elsewhere']=dict(contains_elsewhere=sum('elsewhere' in (it['line2'] or '').lower() for it in items))
    M['banned']=sum(bool(it['banned']) for it in items)
    # triples
    key=(lambda x:x.get('id')) if 'id' in items[0] else None
    M['triples_all']=triples(items,key,rng)
    byf=collections.defaultdict(list)
    for it in items: byf[it['frame']].append(it)
    M['triples_same_frame']=triples(items,key,random.Random(seed+1),groups=list(byf.values()))
    # headline-only
    hi=[dict(tk=it['htk'],id=it.get('id')) for it in items]; hbf=collections.defaultdict(list)
    for h,it in zip(hi,items): hbf[it['frame']].append(h)
    M['triples_all_headline_only']=triples(hi,key,random.Random(seed+2))
    M['triples_same_frame_headline_only']=triples(hi,key,random.Random(seed+3),groups=list(hbf.values()))
    # 4-grams by document frequency
    df=collections.Counter()
    for it in items:
        for g in set(grams(it['tk'],4)): df[g]+=1
    M['top4grams']=[dict(phrase=' '.join(g),outputs=c,share=round(c/n,3),source=attribute(g)[:5]) for g,c in df.most_common(25)]
    # stock tails
    M['line2_forms_top']=lc.most_common(12)
    # per frame
    pf={}
    for f,its in sorted(byf.items(),key=lambda x:-len(x[1])):
        c=collections.Counter(' '.join(i['headline'].split()[:3]).lower() for i in its); tpc=collections.Counter(i['template'] for i in its)
        smp=[]; r2=random.Random(1)
        for _ in range(3000):
            if len(its)<2: break
            a,b=r2.sample(its,2); 
            if key and key(a)==key(b): continue
            smp.append((bool(set(grams(a['tk'],5))&set(grams(b['tk'],5))),jac(set(grams(a['tk'],3)),set(grams(b['tk'],3)))))
        pf[f]=dict(n=len(its),distinct_headlines=len({i['headline'] for i in its}),distinct_openers=len(c),top_opener=c.most_common(1)[0],templates=tpc.most_common(4),pair_5gram_share=round(sum(s[0] for s in smp)/len(smp),3) if smp else None,pair_trigram_jaccard=round(statistics.mean(s[1] for s in smp),3) if smp else None)
    M['per_frame']=pf
    M['by_cert_templates']=None
    return M
T1=json.load(open(D+'test1.json')); T2=json.load(open(D+'test2.json'))
w=[o for o in T1['outputs'] if o['focus']=='world']
out=dict(test1_world=metrics(w,'TEST 1 world focus'),test1_all=metrics(T1['outputs'],'TEST 1 all foci'),test2=metrics([dict(o,id=o['rows_from']+'>'+o['beats_from']) for o in T2['outputs']],'TEST 2 cross-combined'))
out['test1_fails']=T1['fails']; out['test2_null']=T2['null_count']
# quiet share
for k,v in (('test1_world',w),('test1_all',T1['outputs']),('test2',T2['outputs'])):
    out[k]['quiet_share']=round(sum(o['lead']=='quiet' for o in v)/len(v),3)
    out[k]['lead_counts']=collections.Counter(o['lead'] for o in v).most_common()
    out[k]['shrink_share']=round(sum(bool(o['shrink']) for o in v)/len(v),3)
json.dump(out,open(D+'metrics.json','w'),indent=1,default=list)
for k in ('test1_world','test1_all','test2'):
    m=out[k]; print(k,m['n'],'openers',m['openers']['distinct'],m['openers']['top1_share'],'tpl',m['templates']['distinct'],m['templates']['top1_share'],'l2',m['line2']['distinct'],'tri',m['triples_all'],'same',m['triples_same_frame'])
