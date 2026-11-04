import json, glob, numpy as np
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
spec = json.load(open("specs/world_state_v2_frozen_haiku.json")); sch = spec["output_schema"]["properties"]; TOP = np.array(sch["topic"]["enum"]); CON = np.array(sch["conditions"]["items"]["properties"]["condition"]["enum"]); ST = np.array(["fact", "forecast", "opinion", "unclear"])
D = np.load("runs/d1_label_probs.npz", allow_pickle=True); ids = list(D["ids"]); hk = {}; sn = {}
for f in glob.glob("runs/p7/*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
H = lambda k: np.array([hk[i][k] for i in ids]); S = lambda k: np.array([sn[i][k] for i in ids]); res = {"n": len(ids)}
for name, probs, cls, key in (("topic", D["topic"], TOP, "topic"), ("story_type", D["story"], ST, "story_type")):
    d1 = cls[probs.argmax(1)]; h, s = H(key), S(key); sp = h != s
    res[name] = {"d1_vs_sonnet": round(float((d1 == s).mean()), 3), "d1_vs_haiku": round(float((d1 == h).mean()), 3), "haiku_vs_sonnet": round(float((h == s).mean()), 3), "n_teacher_disagreements": int(sp.sum()),
                 "on_disagreements": {"d1_sides_sonnet": round(float((d1[sp] == s[sp]).mean()), 3), "d1_sides_haiku": round(float((d1[sp] == h[sp]).mean()), 3), "d1_neither": round(float(((d1[sp] != s[sp]) & (d1[sp] != h[sp])).mean()), 3)}}
# which condition where both teachers name one but their sets differ
both = [k for k, i in enumerate(ids) if hk[i]["conditions"] and sn[i]["conditions"]]; d1c = CON[D["cond"].argmax(1)]; dis = [k for k in both if {c["condition"] for c in hk[ids[k]]["conditions"]}.isdisjoint({c["condition"] for c in sn[ids[k]]["conditions"]})]
res["condition_both_name_one"] = {"n_both": len(both), "d1_top1_in_haiku_set": round(float(np.mean([d1c[k] in {c["condition"] for c in hk[ids[k]]["conditions"]} for k in both])), 3), "d1_top1_in_sonnet_set": round(float(np.mean([d1c[k] in {c["condition"] for c in sn[ids[k]]["conditions"]} for k in both])), 3), "n_disjoint_teacher_sets": len(dis),
    "on_disjoint": {"d1_in_sonnet_set": round(float(np.mean([d1c[k] in {c["condition"] for c in sn[ids[k]]["conditions"]} for k in dis])), 3) if dis else None, "d1_in_haiku_set": round(float(np.mean([d1c[k] in {c["condition"] for c in hk[ids[k]]["conditions"]} for k in dis])), 3) if dis else None}}
json.dump(res, open("runs/snapshots/d1_vs_haiku.json", "w"), indent=1); print(json.dumps(res, indent=1))
