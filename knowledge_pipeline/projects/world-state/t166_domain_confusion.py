"""Domain confusion table from saved T149 held-out predictions (wording A) vs MN-DS gold_fresh2 (scoring only, no new reads).
Run: python3 -I t166_domain_confusion.py (from projects/world-state) -> runs/pulse/t149/t166_confusion.json"""
import json, collections
r = json.load(open("runs/pulse/t149/t149_domain_wording.json")); g = json.load(open("/workspace/data/anchors/mn_ds/gold_fresh2.json"))
ALIAS = {"politics": "politics and government", "religion and belief": "religion"}
n = ok = 0; pairs = collections.Counter(); gold_n = collections.Counter(); gold_ok = collections.Counter()
for i, p in r["held_pred"]["A"].items():
    if i not in g: continue
    t = ALIAS.get(g[i]["l1"], g[i]["l1"]); n += 1; gold_n[t] += 1
    if p == t: ok += 1; gold_ok[t] += 1
    else: pairs[(t, p)] += 1
err = n - ok; top = pairs.most_common(8)
res = {"n": n, "acc": round(ok / n, 3), "errors": err, "top3_share_of_errors": round(sum(c for _, c in top[:3]) / err, 3), "top5_share": round(sum(c for _, c in top[:5]) / err, 3),
       "top_pairs": [{"gold": a, "predicted": b, "count": c} for (a, b), c in top],
       "per_gold_recall": {k: [gold_ok[k], gold_n[k]] for k in sorted(gold_n)}}
json.dump(res, open("runs/pulse/t149/t166_confusion.json", "w"), indent=1); print(json.dumps(res, indent=1)[:1800])
