"""M6: how much does the STRUCTURE matter? For one model, compare its answers to the old JSON-label request (it writes topic, story_type, claim, conditions) with its answers to the typed questions (bundle B1, variant A, seed 0) on the same items. Alpha between the two structures, population-weighted, bootstrap by stratum. Needs the numpy venv.
    python3-venv: structure_consistency.py <bundle> <rater> <json_labels_dir>"""
import json, sys, numpy as np
sys.path.insert(0, "/workspace/knowledge_pipeline/xtest"); from score import alpha_nominal, boot_alpha
bundle, rater, jd = sys.argv[1:4]; B = json.load(open(f"{bundle}/bundle.json")); d = B["selection"]["design"]; items = [json.loads(l)["id"] for l in open(B["items_file"])]
w = np.array([d["weights"][i] for i in items]); st = np.array([d["strata"][i] for i in items])
J = {}
for l in open(f"{jd}/labels.jsonl"):
    r = json.loads(l); J[r["item_id"]] = r["label"]
T = {}
for l in open(f"{bundle}/runs/{rater}_A_s0/results.jsonl"):
    r = json.loads(l); T[r["task"]] = r
for fld, getj in (("presence", lambda L: "yes" if L["conditions"] else "no"), ("story", lambda L: L["story_type"]), ("topic", lambda L: L["topic"])):
    ok = [k for k, i in enumerate(items) if i in J and T.get(f"{fld}:{i}", {}).get("ok")]; cls = sorted({getj(J[items[k]]) for k in ok} | {T[f"{fld}:{items[k]}"]["label"] for k in ok}); cid = {c: n for n, c in enumerate(cls)}
    M = np.array([[cid[getj(J[items[k]])], cid[T[f"{fld}:{items[k]}"]["label"]]] for k in ok]); ok = np.array(ok); a = alpha_nominal(M, w[ok]); lo, hi = boot_alpha(M, w[ok], st[ok], 500)
    print(f"{rater:7s} {fld:9s} JSON-label vs typed-question: alpha {a:.3f} [{lo:.3f},{hi:.3f}]  raw agree {np.average(M[:,0]==M[:,1], weights=w[ok]):.3f}  n {len(ok)}")
