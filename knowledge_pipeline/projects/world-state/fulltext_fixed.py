"""T42 (pre-registered L1005): same 1,600 human-labelled full articles as fulltext_topic.py; windows that leave room for the headline versus the old windows.
    /workspace/models/embed-zs/.venv/bin/python fulltext_fixed.py   (from projects/world-state)"""
import json, sys, random, re, math, collections, numpy as np
sys.path.insert(0, "."); import analyze2 as A2; from expert1_runtime import ExpertS
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; gl = {v["l1"] for v in json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json")).values()}
R = [json.loads(l) for l in open("/workspace/data/anchors/mn_ds/train.jsonl")]; R = [r for r in R if r.get("content") and r.get("title") and r["category_level_1"] in gl and len(r["content"]) >= 800]
rng = random.Random(20261105); by = collections.defaultdict(list)
for r in R: by[r["category_level_1"]].append(r)
S = []
for c in sorted(by): S += rng.sample(by[c], 100)
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); cl = e.S["topic_cl"]; out = {}
def wil(k, n):
    p = k / n; z = 1.96; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return [round((c - h) / d, 3), round((c + h) / d, 3)]
res = {}
for name, kw in (("old_windows", dict(fit_headline=False)), ("headline_aware_windows", dict(fit_headline=True))):
    rd = A2.Reader(e.S, threads=6, **kw); hit2, hit1 = [], []
    for r in S:
        pt, _, _ = rd.read(r["title"], r["content"]); o = np.argsort(-pt)[:2]; g = r["category_level_1"]
        hit2.append(int(any(g in M.get(cl[k], []) for k in o))); hit1.append(int(g in M.get(cl[o[0]], [])))
    res[name] = np.array(hit2); out[name + "_within_two"] = round(float(np.mean(hit2)), 4); out[name + "_range_low"] = wil(sum(hit2), len(S))[0]; out[name + "_range_high"] = wil(sum(hit2), len(S))[1]; out[name + "_first_guess"] = round(float(np.mean(hit1)), 4)
d = res["headline_aware_windows"] - res["old_windows"]; rs = np.random.RandomState(1); bs = [float(d[rs.randint(0, len(d), len(d))].mean()) for _ in range(1000)]
out["diff"] = round(float(d.mean()), 4); out["diff_low"] = round(float(np.percentile(bs, 2.5)), 4); out["diff_high"] = round(float(np.percentile(bs, 97.5)), 4)
json.dump(out, open("runs/pulse/fulltext_fixed.json", "w"), indent=1); print(json.dumps(out, indent=1))
