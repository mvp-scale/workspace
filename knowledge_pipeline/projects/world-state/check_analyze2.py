"""Proves analyze2 against the reference set (runs/pulse/golden/articles.jsonl) and Lean's cases, section by section, then times it.
    /workspace/models/embed-zs/.venv/bin/python check_analyze2.py   (from projects/world-state)"""
import json, sys, time, numpy as np
sys.path.insert(0, "."); import decider as D, facts_lib as FL, analyze2 as A2
from expert1_runtime import ExpertS
print("decider vs Lean:", D.check_against_lean(), "cases identical")
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); FT = json.load(open("runs/pulse/field_table.json")); G = [json.loads(l) for l in open("runs/pulse/golden/articles.jsonl")]
leg = A2.Reader(e.S, threads=1, fit_headline=False); worst = 0; top_same = 0
for g in G:
    pt, ps, nw = leg.read(g["title"], g["body"]); worst = max(worst, float(np.abs(pt - np.array(g["topic_probs"])).max(), ) , float(np.abs(ps - np.array(g["story_probs"])).max())); top_same += [e.S["topic_cl"][k] for k in np.argsort(-pt)[:2]] == g["topic_top2"]
print("legacy-window reader vs reference: largest probability difference %.2e, same two guesses on %d of %d" % (worst, top_same, len(G)))
bad = 0; skipped = 0
for g in G:
    text = FL.re.sub(r"\s+", " ", g["title"] + ". " + g["body"])[:12000]; anchor = (g["date"] + "T00:00:00Z") if g["date"] else None
    new = {(f["kind"], f["s"], f["e"], f["status"]) for f in (FL.facts_for(text, anchor)[0] if A2.NUM_OR_DATE.search(text) else []) if f["kind"] in ("amount", "date")}
    ref = {(f["kind"], f["s"], f["e"], f["status"]) for f in g["facts"] if f["kind"] in ("amount", "date")}; bad += new != ref; skipped += not A2.NUM_OR_DATE.search(text)
print("amount and date facts vs reference: %d of %d articles differ; parse skipped on %d articles (no number or date word)" % (bad, len(G), skipped))
for name, kw in (("legacy windows, 1 thread", dict(threads=1, fit_headline=False)), ("headline-aware windows, 8 threads", dict(threads=8, fit_headline=True)), ("headline-aware windows, 1 thread", dict(threads=1, fit_headline=True))):
    X = A2.Analyzer(e.S, FT, **kw)
    for g in G[:3]: X.analyze(g["title"], g["body"], g["date"])
    R = [X.analyze(g["title"], g["body"], g["date"])["ms"] for g in G]; q = lambda k, p: sorted(r[k] for r in R)[int(p * len(R)) - 1]
    print("%-36s total median %6.1f ms, p95 %6.1f ms | reader median %6.1f | solver median %5.1f" % (name, q("total_ms", .5), q("total_ms", .95), q("reader_ms", .5), q("solver_ms", .5)))
