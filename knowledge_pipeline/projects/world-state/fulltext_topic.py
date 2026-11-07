"""T42 (pre-registered L995): does the trained reader do better when it sees the whole article? MN-DS full articles, human categories.
    /workspace/models/embed-zs/.venv/bin/python fulltext_topic.py   (from projects/world-state)"""
import json, sys, random, re, math, collections, numpy as np
sys.path.insert(0, "."); from expert1_runtime import ExpertS
from tokenizers import Tokenizer
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; gl = {v["l1"] for v in json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json")).values()}
R = [json.loads(l) for l in open("/workspace/data/anchors/mn_ds/train.jsonl")]
R = [r for r in R if r.get("content") and r.get("title") and r["category_level_1"] in gl and len(r["content"]) >= 800]
rng = random.Random(20261105); by = collections.defaultdict(list)
for r in R: by[r["category_level_1"]].append(r)
S = []
for c in sorted(by): S += rng.sample(by[c], 100)
print("sample", len(S), "median content chars", sorted(len(r["content"]) for r in S)[len(S) // 2], flush=True)
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); W = e.S["t_W"]; b = e.S["t_b"]; cl = e.S["topic_cl"]
tk = Tokenizer.from_file(e.S["tok_path"]); tk.no_truncation()
def soft(z): z = z - z.max(); p = np.exp(z); return p / p.sum()
def probs(text): return soft(e.student(text) @ W.T + b)
def chunks(text, k=64, cap=12):
    enc = tk.encode(re.sub(r"\s+", " ", text)); off = [o for o in enc.offsets if o[1] > o[0]]; out = []
    for i in range(0, len(off), k):
        seg = off[i:i + k]; out.append(re.sub(r"\s+", " ", text)[seg[0][0]:seg[-1][1]])
        if len(out) >= cap: break
    return out
def judged(p, gold):
    o = np.argsort(-p)[:2]; g = [cl[k] for k in o]
    return int(any(gold in M.get(x, []) for x in g)), int(gold in M.get(g[0], []))
res = {"title_only": [], "title_teaser": [], "whole_article": []}; nch = []
for n, r in enumerate(S):
    t, c, gold = r["title"], re.sub(r"\s+", " ", r["content"]), r["category_level_1"]
    res["title_only"].append(judged(probs(t), gold)); res["title_teaser"].append(judged(probs(t + ". " + c[:300]), gold))
    ch = chunks(c); nch.append(len(ch)); P = np.mean([probs(t + ". " + x) for x in ch], axis=0); res["whole_article"].append(judged(P, gold))
    if n % 200 == 0: print(n, flush=True)
def wil(k, n):
    p = k / n; z = 1.96; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return round((c - h) / d, 3), round((c + h) / d, 3)
out = {"n": len(S), "median_chunks": sorted(nch)[len(nch) // 2], "systems": {}}
for k, v in res.items():
    a = np.array(v); out["systems"][k] = {"within_two": round(a[:, 0].mean(), 4), "range": wil(int(a[:, 0].sum()), len(a)), "first_guess": round(a[:, 1].mean(), 4)}
A = np.array(res["title_teaser"])[:, 0]; B = np.array(res["whole_article"])[:, 0]; d = B - A; rs = np.random.RandomState(1)
bs = [float(d[rs.randint(0, len(d), len(d))].mean()) for _ in range(1000)]
out["whole_minus_teaser"] = {"diff": round(float(d.mean()), 4), "range": [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]}
json.dump(out, open("runs/pulse/fulltext_topic.json", "w"), indent=1); print(json.dumps(out, indent=1))
