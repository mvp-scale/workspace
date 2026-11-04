"""Revote comparison: alpha per field for the SAME two voters (one Sonnet, one Haiku) on the SAME items, v2 codebook vs v3 codebook. Stdlib only.
v2: Sonnet r2 (runs/pulse/selfcons) + Haiku r2 (runs/pulse/selfcons_haiku). v3: runs/pulse/selfcons_v3 + runs/pulse/selfcons_v3_haiku. Prediction: ledger L537."""
import json, re, os, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ns = {}
src = open(os.path.join(HERE, "fitness_screen.py")).read(); exec("import collections, itertools\n" + re.search(r"def alpha\(.*?\n(?=\ndef status)", src, re.S).group(0), ns); alpha = ns["alpha"]
J = lambda p: {json.loads(l)["item_id"]: json.loads(l)["label"] for l in open(os.path.join(HERE, p), encoding="utf-8")}
LV = ["minor", "notable", "major", "severe", "extreme"]
SETS = {"v2": (J("runs/pulse/selfcons/labels.jsonl"), J("runs/pulse/selfcons_haiku/labels.jsonl"))}
if os.path.exists(os.path.join(HERE, "runs/pulse/selfcons_v3/labels.jsonl")) and os.path.exists(os.path.join(HERE, "runs/pulse/selfcons_v3_haiku/labels.jsonl")):
    SETS["v3"] = (J("runs/pulse/selfcons_v3/labels.jsonl"), J("runs/pulse/selfcons_v3_haiku/labels.jsonl"))
ids = sorted(set.intersection(*[set(a) & set(b) for a, b in SETS.values()]))
def fields(s, h, i):
    out = {"story_type": [s[i]["story_type"], h[i]["story_type"]], "topic": [s[i]["topic"], h[i]["topic"]],
           "condition_present": [bool(s[i]["conditions"]), bool(h[i]["conditions"])]}
    cs = {c["condition"]: c for c in s[i]["conditions"]}; ch = {c["condition"]: c for c in h[i]["conditions"]}
    both = sorted(set(cs) & set(ch))
    out["direction_shared"] = [[cs[c]["direction"], ch[c]["direction"]] for c in both]
    out["size_shared"] = [[LV.index(cs[c]["level"]), LV.index(ch[c]["level"])] for c in both]
    return out
res = {"items": len(ids), "versions": {}}
for v, (s, h) in SETS.items():
    A = collections.defaultdict(list); rate = collections.Counter(); sz = collections.Counter(); ty = collections.Counter()
    for i in ids:
        f = fields(s, h, i)
        for k in ("story_type", "topic", "condition_present"): A[k].append(f[k])
        for k in ("direction_shared", "size_shared"): A[k].extend(f[k])
        for who, lab in (("sonnet", s[i]), ("haiku", h[i])):
            rate[who + "_presence_yes"] += bool(lab["conditions"]); ty[who + "_" + lab["story_type"]] += 1
            for c in lab["conditions"]: sz[who + "_" + c["level"]] += 1
    res["versions"][v] = {"alpha": {"story_type": alpha(A["story_type"]), "topic": alpha(A["topic"]), "condition_present": alpha(A["condition_present"]),
                           "direction_shared": alpha(A["direction_shared"]), "size_shared_interval": alpha(A["size_shared"], True), "size_shared_nominal": alpha(A["size_shared"])},
                          "raw_agree": {k: round(sum(a == b for a, b in A[k]) / len(A[k]), 3) for k in ("story_type", "topic", "condition_present")},
                          "shared_conditions": len(A["size_shared"]), "presence_yes": {k: rate[k] for k in rate}, "story_types": dict(ty), "levels": dict(sz)}
if "v3" in res["versions"]:
    res["delta_alpha"] = {k: round(res["versions"]["v3"]["alpha"][k] - res["versions"]["v2"]["alpha"][k], 3) for k in res["versions"]["v2"]["alpha"] if res["versions"]["v2"]["alpha"][k] is not None and res["versions"]["v3"]["alpha"][k] is not None}
json.dump(res, open(os.path.join(HERE, "runs/pulse/revote_compare.json"), "w"), indent=1); print(json.dumps(res, indent=1))
