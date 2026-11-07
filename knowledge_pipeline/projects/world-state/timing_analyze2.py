"""Saves the analyze2 timings (200 golden articles) to runs/pulse/timing_analyze2.json.
    /workspace/models/embed-zs/.venv/bin/python timing_analyze2.py   (from projects/world-state)"""
import json, sys, numpy as np
sys.path.insert(0, "."); import analyze2 as A2
from expert1_runtime import ExpertS
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); FT = json.load(open("runs/pulse/field_table.json")); G = [json.loads(l) for l in open("runs/pulse/golden/articles.jsonl")]
out = {"articles": len(G)}
for name, kw in (("t8", dict(threads=8, fit_headline=True)), ("t1", dict(threads=1, fit_headline=True))):
    X = A2.Analyzer(e.S, FT, **kw)
    for g in G[:3]: X.analyze(g["title"], g["body"], g["date"])
    R = [X.analyze(g["title"], g["body"], g["date"])["ms"] for g in G]
    for k in ("total_ms", "reader_ms", "solver_ms", "decider_ms"):
        v = [r[k] for r in R]; out[f"{name}_{k[:-3]}_median"] = round(float(np.median(v)), 3); out[f"{name}_{k[:-3]}_p95"] = round(float(np.percentile(v, 95)), 3)
json.dump(out, open("runs/pulse/timing_analyze2.json", "w"), indent=1); print(out)
