import json, random, statistics as st
from collections import Counter, defaultdict
rows=[json.loads(l) for l in open("/workspace/data/persona-lab/pilot.jsonl")]
by=defaultdict(dict)
for r in rows: by[r["product"]][r["persona"]]=r
def tp(r): return r["answers"]["try"]["noul"]
def boot(a,b,n=2000,seed=1):
    g=random.Random(seed); d=[]
    for _ in range(n):
        d.append(st.mean(g.choices(a,k=len(a)))-st.mean(g.choices(b,k=len(b))))
    d.sort(); return st.mean(a)-st.mean(b), d[int(.025*n)], d[int(.975*n)]
print("blind (no persona) P(try):",{p:round(tp(by[p][-1]),2) for p in by})
for p in by:
    v=[tp(by[p][i]) for i in range(100)]
    c=Counter(by[p][i]["answers"]["take"]["choice"] for i in range(100))
    print(f"{p:11s} mean P(try)={st.mean(v):.2f} sd={st.pstdev(v):.2f} first-take={dict(c)}")
A=lambda i:by["splitly"][i]["attrs"]
young=[i for i in range(100) if A(i)["age"]<35]; old=[i for i in range(100) if A(i)["age"]>=55]; mid=[i for i in range(100) if 35<=A(i)["age"]<55]
cg=[i for i in range(100) if A(i)["cares_for_older_relative"]]
print("n young/mid/old/caregivers",len(young),len(mid),len(old),len(cg))
def d(p,x,y): return boot([tp(by[p][i]) for i in x],[tp(by[p][i]) for i in y])
print("H1 universal-bad (paired mean diff)", round(st.mean(tp(by['universal'][i])-tp(by['bad'][i]) for i in range(100)),2))
print("H2 splitly young-old  diff,lo,hi:",[round(x,2) for x in d("splitly",young,old)])
print("H3 carecircle old-young:",[round(x,2) for x in d("carecircle",old,young)])
nc=[i for i in range(100) if i not in cg]
print("   carecircle caregivers-noncaregivers:",[round(x,2) for x in d("carecircle",cg,nc)])
# yes-sayer check: correlation of persona scores across products
def corr(a,b):
    ma,mb=st.mean(a),st.mean(b); 
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/ (len(a)*st.pstdev(a)*st.pstdev(b)) if st.pstdev(a)*st.pstdev(b)>0 else float('nan')
ps=list(by); 
for i,a in enumerate(ps):
    for b in ps[i+1:]: print(f"corr persona P(try) {a}~{b}: {corr([tp(by[a][k]) for k in range(100)],[tp(by[b][k]) for k in range(100)]):.2f}")
# age gradient, tech, household for splitly/carecircle
for p in ("splitly","carecircle"):
    for key,groups in (("tech",["uses new apps easily","uses a few familiar apps","avoids new technology"]),("household",None)):
        gs=groups or sorted({by[p][i]["attrs"][key] for i in range(100)})
        print(p,key,{g:(round(st.mean(tp(by[p][i]) for i in range(100) if by[p][i]["attrs"][key]==g),2),sum(1 for i in range(100) if by[p][i]["attrs"][key]==g)) for g in gs})
# frustration linkage: splitly
for p in ("splitly","carecircle","bad"):
    f=Counter(by[p][i]["answers"]["frustration"]["choice"] for i in range(100)); dl=Counter(by[p][i]["answers"]["delight"]["choice"] for i in range(100))
    print(p,"frustration",dict(f),"delight",dict(dl))
fr_old=Counter(by["splitly"][i]["answers"]["frustration"]["choice"] for i in old); fr_y=Counter(by["splitly"][i]["answers"]["frustration"]["choice"] for i in young)
print("splitly frustration old",dict(fr_old),"young",dict(fr_y))
# consistency: take vs try
inc=sum(1 for r in rows if r["persona"]>=0 and ((r["answers"]["try"]["noul"]>.5)!=(r["answers"]["take"]["choice"]=="try_it")) )
print("try>.5 disagrees with take==try_it in",inc,"of 400")
