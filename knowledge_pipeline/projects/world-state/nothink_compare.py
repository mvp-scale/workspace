"""Thinking-off test (ledger L552, L553): same 400 items, v3 codebook, thinking default vs off. Stdlib only."""
import json, re, os, collections
H = os.path.dirname(os.path.abspath(__file__)); ns = {}
exec("import collections, itertools\n" + re.search(r"def alpha\(.*?\n(?=\ndef status)", open(os.path.join(H, "fitness_screen.py")).read(), re.S).group(0), ns); alpha = ns["alpha"]
LV = ["minor", "notable", "major", "severe", "extreme"]
def load(d):
    rows = [json.loads(l) for l in open(os.path.join(H, f"runs/pulse/{d}/labels.jsonl"))]
    rej = [json.loads(l) for l in open(os.path.join(H, f"runs/pulse/{d}/rejects.jsonl"))] if os.path.exists(os.path.join(H, f"runs/pulse/{d}/rejects.jsonl")) else []
    sp = sum(json.loads(l).get("usd", 0) for l in open(os.path.join(H, f"runs/pulse/{d}/spend.jsonl")))
    o = sorted(r["usage"]["output_tokens"] for r in rows)
    st = {"labels": len(rows), "rejected": len(rej), "reject_reasons": dict(collections.Counter(json.dumps(r["errors"])[:60] for r in rej)), "usd": round(sp, 3),
          "output_tokens_median_p95_max": [o[len(o)//2], o[int(.95*len(o))], o[-1]]}
    return {r["item_id"]: r["label"] for r in rows}, st
D = {k: load(v) for k, v in {"S_def": "selfcons_v3", "H_def": "selfcons_v3_haiku", "S_nt": "selfcons_v3nt", "H_nt": "selfcons_v3nt_haiku"}.items()}
out = {k: v[1] for k, v in D.items()}; L = {k: v[0] for k, v in D.items()}
ids = sorted(set.intersection(*[set(l) for l in L.values()])); out["items_in_all_four"] = len(ids)
def fields(S, Hh):
    A = collections.defaultdict(list)
    for i in ids:
        s, h = S[i], Hh[i]; A["story_type"].append([s["story_type"], h["story_type"]]); A["topic"].append([s["topic"], h["topic"]]); A["condition_present"].append([bool(s["conditions"]), bool(h["conditions"])])
        cs = {c["condition"]: c for c in s["conditions"]}; ch = {c["condition"]: c for c in h["conditions"]}
        for c in set(cs) & set(ch): A["direction_shared"].append([cs[c]["direction"], ch[c]["direction"]]); A["size_shared"].append([LV.index(cs[c]["level"]), LV.index(ch[c]["level"])])
    return {"story_type": alpha(A["story_type"]), "topic": alpha(A["topic"]), "condition_present": alpha(A["condition_present"]), "direction_shared": alpha(A["direction_shared"]), "size_interval": alpha(A["size_shared"], True), "shared_conditions": len(A["size_shared"])}
a_def, a_nt = fields(L["S_def"], L["H_def"]), fields(L["S_nt"], L["H_nt"])
out["alpha_cross_family"] = {"default": a_def, "thinking_off": a_nt, "change": {k: round(a_nt[k] - a_def[k], 3) for k in a_def if k != "shared_conditions"}}
g = {"story_type": lambda l: l["story_type"], "topic": lambda l: l["topic"], "condition_present": lambda l: bool(l["conditions"])}
out["same_model_raw_agreement_default_vs_off"] = {m: {k: round(sum(f(L[m + "_def"][i]) == f(L[m + "_nt"][i]) for i in ids) / len(ids), 3) for k, f in g.items()} for m in ("S", "H")}
json.dump(out, open(os.path.join(H, "runs/pulse/nothink_compare.json"), "w"), indent=1); print(json.dumps(out, indent=1))
