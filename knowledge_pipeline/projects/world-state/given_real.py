"""T20: the condition chain 'given a real condition' (Sonnet found one), no gate: which condition, direction, size on ALL real conditions. Pools the sets that are untouched by training: devq, old (1,466 test), devq2 (fresh queue), hf334 (Haiku-flagged, never trained on). Wilson 95% intervals. Local CPU.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python given_real.py v5-leaf"""
import json, glob, re, sys, math, os, pickle, numpy as np, scipy.sparse as sp
sys.path.insert(0, "."); from expert1_runtime import Expert3
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; LV = ["minor", "notable", "major", "severe", "extreme"]
ver = sys.argv[1]; reg = {r["version"]: r for r in json.load(open("engine_versions.json"))}[ver]; e = Expert3(reg["path"]); M = e.M; Hc = e.H["cond"]
def raw(text):
    t = re.sub(r"\s+", " ", text); xwc = sp.hstack([M["vw"].transform([t]), M["vc"].transform([t])]).tocsr(); v = e.embed(text); xc = xwc[:, M["keepc"]]
    P = e._soft(np.asarray(xc @ Hc["W"]).ravel() + v @ Hc["V"] + Hc["b"]); c2 = np.argsort(-P)[:2]; top = Hc["classes"][c2[0]]
    xd = sp.hstack([xc, sp.csr_matrix(([2.0], ([0], [e.cond_idx[top]])), shape=(1, len(e.cond_idx)))]).tocsr()
    return {"top1": str(top), "top2": str(Hc["classes"][c2[1]]), "cconf": float(P.max()), "dir": str(M["dirm"].predict(xd)[0]), "size": M["LV"][int(M["sizem"].predict(xd)[0])]}
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
for p in ("runs/pulse/more/devq2_items.jsonl",):
    if os.path.exists(p):
        for r in J(p): pool[r["id"]] = r["text"]
def sets():
    out = {}
    out["devq"] = {r["item_id"]: r["label"] for r in J("runs/pulse/devq/labels.jsonl")}
    sn = {}
    for f in glob.glob("runs/p7b/*/labels.jsonl"):
        for r in J(f): sn[r["item_id"]] = r["label"]
    hk = {}; old = {}
    for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
        for r in J(f): hk[r["item_id"]] = r["label"]; old[r["item_id"]] = r["label"]
    p = {r["id"]: r for r in J("data/pool_train.jsonl")}; oi = sorted(old); dt = np.array([p[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]; test = [oi[k] for k in np.array_split(o, 5)[4]]
    out["old"] = {i: sn[i] for i in test if i in sn}
    for name, path in (("devq2", "runs/pulse/more/devq2/labels.jsonl"), ("hf334", "runs/pulse/more/hf334/labels.jsonl")):
        if os.path.exists(path): out[name] = {r["item_id"]: r["label"] for r in J(path)}
    return out
def wil(k, m, z=1.96):
    if m == 0: return [None, None]
    p = k / m; d = 1 + z * z / m; c = (p + z * z / (2 * m)) / d; s = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d; return [round(c - s, 3), round(c + s, 3)]
rate = lambda k, m: {"rate": round(k / m, 3) if m else None, "ci95": wil(k, m), "n": m}
S = sets(); res = {"version": ver, "sets": {}}; tot = {"n": 0, "w1": 0, "w2": 0, "dn": 0, "d": 0, "sn": 0, "s": 0, "all": 0}
for name, lab in S.items():
    cache = f"runs/pulse/given_raw_{ver}_{name}.json"; pos = [i for i, l in lab.items() if l["conditions"] and i in pool]
    R = json.load(open(cache)) if os.path.exists(cache) else {}
    for i in pos:
        if i not in R: R[i] = raw(pool[i])
    json.dump(R, open(cache, "w"))
    c = {"n": len(pos), "w1": 0, "w2": 0, "dn": 0, "d": 0, "sn": 0, "s": 0, "all": 0}
    for i in pos:
        r = R[i]; names = [x["condition"] for x in lab[i]["conditions"]]; c["w1"] += r["top1"] in names; c["w2"] += (r["top1"] in names) or (r["top2"] in names)
        x = next((x for x in lab[i]["conditions"] if x["condition"] == r["top1"]), None)
        if x:
            c["dn"] += 1; dok = r["dir"] == x["direction"]; sok = abs(LV.index(r["size"]) - LV.index(x["level"])) <= 1; c["d"] += dok; c["s"] += sok; c["all"] += dok and sok
    res["sets"][name] = {"real_conditions": c["n"], "which_top1": rate(c["w1"], c["n"]), "which_top2": rate(c["w2"], c["n"]), "direction_given_which": rate(c["d"], c["dn"]), "size_given_which": rate(c["s"], c["dn"]), "all_three_of_real": rate(c["all"], c["n"])}
    for k in tot: tot[k] += c[k] if k in c else 0
    print(name, json.dumps(res["sets"][name]), flush=True)
res["pooled"] = {"real_conditions": tot["n"], "which_top1": rate(tot["w1"], tot["n"]), "which_top2": rate(tot["w2"], tot["n"]), "direction_given_which": rate(tot["d"], tot["dn"]), "size_given_which": rate(tot["s"], tot["dn"]), "all_three_of_real": rate(tot["all"], tot["n"])}
print("POOLED", json.dumps(res["pooled"])); json.dump(res, open(f"runs/pulse/given_real_{ver}.json", "w"), indent=1)
