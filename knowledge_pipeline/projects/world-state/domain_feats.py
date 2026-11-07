"""Features for the many-view Domain test (L1047): runs extract.work on 8000 URL-labelled + 8000 unlabelled CC-News pool articles and all 10916 MN-DS articles; Reader topic probabilities for the pool (MN-DS probabilities are cached by domain_signals.py). Writes runs/harvest/domain_feats.pkl.
    /workspace/models/embed-zs/.venv/bin/python domain_feats.py"""
import json, random, pickle, sys, time, numpy as np
from multiprocessing import Pool
import extract as X
sm = {r["row"]: r for r in map(json.loads, open("runs/harvest/sample100k.jsonl"))}; hl = {h["row"]: h for h in map(json.loads, open("runs/harvest/labels100k.jsonl"))}
rng = random.Random(20261107); lab = sorted(k for k, h in hl.items() if "domain_label" in h); unl = sorted(k for k in sm if k not in hl or "domain_label" not in hl[k]); pool = rng.sample(lab, 8000) + rng.sample(unl, 8000)
M = [json.loads(l) for l in open("/workspace/data/anchors/mn_ds/train.jsonl")]; M = [m for m in M if m.get("category_level_1") and m.get("content")]
R = [sm[k] for k in pool] + [{"row": "mnds:%s" % m.get("data_id"), "domain": "mnds:" + str(m.get("source")), "date": m.get("date"), "url": "", "title": m["title"], "text": m["content"], "description": None} for m in M]
t0 = time.time()
with Pool(16, initializer=X.init) as P: recs = P.map(X.work, R, chunksize=10)
print("extract", len(recs), round(time.time() - t0), "s", flush=True)
out = []
for k, rec in zip(pool + [None] * len(M), recs):
    ent = [e[1].lower().replace(" ", "_") + ":" + e[0].lower().replace(" ", "_") for e in rec["entities"]["items"]] + ["c:" + c for c in rec["places"]["countries"]]
    out.append({"row": rec["row"], "title": rec["text"].split(". ", 1)[0], "desc": (rec["source"]["description"] or ""), "text": rec["text"], "ents": ent, "scan": rec["scan"]["counts"], "facts": rec["facts"]["counts"], "func": rec["function"]["counts"], "etypes": rec["entities"]["counts"], "chars": rec["clean"]["chars"],
                "url_label": (hl[k]["domain_label"]["label"] if k in hl and "domain_label" in hl[k] else None) if k else None, "ruler": None})
for o, m in zip(out[len(pool):], M): o["ruler"] = m["category_level_1"]
sys.path.insert(0, "."); import analyze2 as A2; from expert1_runtime import ExpertS
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); S = e.S; Xa = A2.Analyzer(S, json.load(open("runs/pulse/field_table.json")), threads=8); t1 = time.time()
for o, r in zip(out[:len(pool)], R[:len(pool)]): o["reader"] = Xa.reader.read(r["title"] or "", o["text"][len(o["title"]) + 2:])[0].astype(np.float32)
print("reader", round(time.time() - t1), "s", flush=True)
pickle.dump({"pool": out[:len(pool)], "ruler": out[len(pool):], "topic_cl": S["topic_cl"]}, open("runs/harvest/domain_feats.pkl", "wb")); print("saved")
