"""Source analysis (T-0025): train / test / pool split by outlet and source country, and per-outlet score of the best available reader per area on the frozen test.
  THREADS=1 models/embed-zs/.venv/bin/python newsreader/bitmob/source_analysis.py [type=ensemble topic=e5tfidf country=e5 conditions=e5tfidf]  -> data/suite/source_analysis.json"""
import os, sys, json, collections, numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import average_precision_score
W = "/workspace/data"; TAG = os.environ.get("SUITE_TAG", ""); L = lambda f: [json.loads(l) for l in open(f)]
readers = dict(a.split("=") for a in sys.argv[1:]) or {"type": "ensemble", "topic": "e5tfidf", "country": "e5", "conditions": "e5tfidf"}
sc = json.load(open("/workspace/newsreader/bitmob/source_country.json"))["sources"]
src = lambda r: r.get("outlet") or str(r.get("feed"))   # pool records name feeds in "outlet"
night = L(f"{W}/trainset/night1.jsonl"); tr_i, te_i = train_test_split(np.arange(len(night)), test_size=0.2, random_state=0)
train = [night[i] for i in tr_i] + L(f"{W}/trainset/round1.jsonl") + L(f"{W}/trainset/round2.jsonl") + [r for n in filter(None, os.environ.get("EXTRA_TRAIN", "").split(",")) for r in L(f"{W}/trainset/{n}.jsonl")]; test = [night[i] for i in te_i] + L(f"{W}/trainset/testA.jsonl")
pool = L(f"{W}/round1/pool.jsonl")
ctry = lambda o: sc.get(o, "unmapped")
out = {"counts": {}, "readers": readers, "per_outlet": {}}
for name, rows in (("train", train), ("test", test), ("pool", pool)):
    c = collections.Counter(src(r) for r in rows); cc = collections.Counter(ctry(src(r)) for r in rows)
    out["counts"][name] = {"stories": len(rows), "outlets": len(c), "by_outlet": dict(c.most_common()), "by_source_country": dict(cc.most_common())}
ot = np.array([src(r) for r in test]); res = collections.defaultdict(dict); overall = {}
for area, m in readers.items():
    z = np.load(f"{W}/suite{TAG}/{m}/{area}.npz", allow_pickle=True); P, Y = z["P"], z["Y"].astype(bool); assert len(P) == len(test)
    if area == "type": s = ((P >= 0.5) == Y).mean(1); lab = "hamming accuracy at 0.5"
    elif area in ("topic", "country"): s = (P.argmax(1) == Y.argmax(1)).astype(float); lab = "accuracy"
    else: s = None; lab = "micro AP (all key x story pairs)"
    overall[area] = {"reader": m, "metric": lab}
    for o in sorted(set(ot)):
        ix = np.where(ot == o)[0]
        if len(ix) < 60: continue
        if s is not None: v = float(s[ix].mean())
        else: v = float(average_precision_score(Y[ix].ravel(), P[ix].ravel())) if Y[ix].sum() >= 5 else None
        res[o][area] = None if v is None else round(v, 4); res[o]["n_test"] = int(len(ix))
    overall[area]["all"] = round(float(s.mean()), 4) if s is not None else round(float(average_precision_score(Y.ravel(), P.ravel())), 4)
out["overall"] = overall; out["per_outlet"] = res
json.dump(out, open(f"{W}/suite{TAG}/source_analysis.json", "w"), indent=1)
print(overall)
for area in readers:
    v = sorted(((d[area], o, d["n_test"]) for o, d in res.items() if d.get(area) is not None)); print(area, "worst5", v[:5], "best3", v[-3:], "n outlets", len(v))
