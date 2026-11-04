"""T20: paired comparison of two engine versions on the clean holdout DEVQ2 (1,593 natural items), plus 'given a real condition' (no gate) pooled over devq, old, devq2, hf334. Same items, same labels, paired bootstrap (400). CPU, local. Registers heartbeat t20-paired.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python paired_engine.py v5-leaf v6-student"""
import json, glob, re, sys, os, numpy as np, scipy.sparse as sp
sys.path.insert(0, "."); sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from expert1_runtime import Expert, Expert3, ExpertS
hb.beat("t20-paired", pid=os.getpid(), where="[CPU]", task="T20", state="running", progress="paired comparison v5-leaf vs v6-student on DEVQ2", why="Is the challenger's gain real on a holdout it never saw? (ledger L474 rule)", success="Paired intervals for story, topic, found, all-right; which given a real condition pooled", next="Footprint (whole-engine p95), then report the challenger on the page", need="Nothing", cap=3600)
V1, V2 = sys.argv[1], sys.argv[2]; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; LV = ["minor", "notable", "major", "severe", "extreme"]
reg = {r["version"]: r for r in json.load(open("engine_versions.json"))}; cls = {"Expert3": Expert3, "ExpertS": ExpertS}; E = {v: cls[reg[v]["class"]](reg[v]["path"]) for v in (V1, V2)}
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
for r in J("runs/pulse/more/devq2_items.jsonl"): pool[r["id"]] = r["text"]
S2 = {r["item_id"]: r["label"] for r in J("runs/pulse/more/devq2/labels.jsonl")}; ids = sorted(i for i in S2 if i in pool); rng = np.random.RandomState(0)
def per_item(e):
    R = [e.read(pool[i]) for i in ids]; st = np.array([r["story_type"]["answer"] == S2[i]["story_type"] for r, i in zip(R, ids)]); t1 = np.array([bool(r["topic_top2"]["answer"]) and r["topic_top2"]["answer"][0] == S2[i]["topic"] for r, i in zip(R, ids)]); t2 = np.array([S2[i]["topic"] in (r["topic_top2"]["answer"] or []) for r, i in zip(R, ids)])
    pos = np.array([bool(S2[i]["conditions"]) for i in ids]); found = np.array([r["condition_present"]["status"] == "answered" and bool(r["condition_present"]["answer"]) for r in R]) & pos; allr = np.zeros(len(ids), bool)
    for k, (r, i) in enumerate(zip(R, ids)):
        c = r.get("condition")
        if found[k] and c and c.get("status") == "answered":
            x = next((x for x in S2[i]["conditions"] if x["condition"] == c["answer"][0]), None)
            if x: allr[k] = c.get("direction") == x["direction"] and abs(LV.index(c["size"]) - LV.index(x["level"])) <= 1
    ans = np.array([r["condition_present"]["status"] == "answered" for r in R]); ok = np.array([r["condition_present"]["status"] == "answered" and bool(r["condition_present"]["answer"]) == bool(S2[i]["conditions"]) for r, i in zip(R, ids)])
    return {"story": st, "topic1": t1, "topic2": t2, "found": found[pos], "allright": allr[pos], "answered": ans, "pres_ok_answered": ok}, pos
A, pos = per_item(E[V1]); B, _ = per_item(E[V2]); out = {"n": len(ids), "real": int(pos.sum()), "fields": {}}
for k in ("story", "topic1", "topic2", "found", "allright", "answered"):
    a, b = A[k].astype(float), B[k].astype(float); n = len(a); d = [b[ix].mean() - a[ix].mean() for ix in (rng.randint(0, n, n) for _ in range(400))]
    out["fields"][k] = {V1: round(float(a.mean()), 3), V2: round(float(b.mean()), 3), "diff": round(float(b.mean() - a.mean()), 3), "diff_ci95": [round(float(np.percentile(d, 2.5)), 3), round(float(np.percentile(d, 97.5)), 3)]}
    print(k, out["fields"][k], flush=True)
# which given a real condition, pooled
def sets():
    o = {}; o["devq"] = {r["item_id"]: r["label"] for r in J("runs/pulse/devq/labels.jsonl")}; sn = {}
    for f in glob.glob("runs/p7b/*/labels.jsonl"):
        for r in J(f): sn[r["item_id"]] = r["label"]
    hk = {}; old = {}
    for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
        for r in J(f): hk[r["item_id"]] = r["label"]; old[r["item_id"]] = r["label"]
    P = {r["id"]: r for r in J("data/pool_train.jsonl")}; oi = sorted(old); dt = np.array([P[i]["date"] or "" for i in oi]); od = np.argsort(dt, kind="stable"); od = od[dt[od] != ""]; test = [oi[k] for k in np.array_split(od, 5)[4]]
    o["old"] = {i: sn[i] for i in test if i in sn}; o["devq2"] = S2; o["hf334"] = {r["item_id"]: r["label"] for r in J("runs/pulse/more/hf334/labels.jsonl")}; return o
for r in J("runs/pulse/more/hf334_items.jsonl"): pool[r["id"]] = r["text"]
def top1(e, v, text):
    if isinstance(e, ExpertS): S = e.S; lo = e.student(text) @ S["c_W"].T + S["c_b"]; return S["cond_cl"][int(lo.argmax())]
    t = re.sub(r"\s+", " ", text); M = e.M; H = e.H["cond"]; xwc = sp.hstack([M["vw"].transform([t]), M["vc"].transform([t])]).tocsr(); P = e._soft(np.asarray(xwc[:, M["keepc"]] @ H["W"]).ravel() + e.embed(text) @ H["V"] + H["b"]); return str(H["classes"][int(P.argmax())])
hits = {V1: [], V2: []}
for name, lab in sets().items():
    for i, l in lab.items():
        if l["conditions"] and i in pool:
            names = [x["condition"] for x in l["conditions"]]
            for v in (V1, V2): hits[v].append(top1(E[v], v, pool[i]) in names)
a, b = np.array(hits[V1], float), np.array(hits[V2], float); n = len(a); d = [b[ix].mean() - a[ix].mean() for ix in (rng.randint(0, n, n) for _ in range(400))]
out["which_given_real_pooled"] = {"n": n, V1: round(float(a.mean()), 3), V2: round(float(b.mean()), 3), "diff": round(float(b.mean() - a.mean()), 3), "diff_ci95": [round(float(np.percentile(d, 2.5)), 3), round(float(np.percentile(d, 97.5)), 3)]}; print("which|real pooled", out["which_given_real_pooled"], flush=True)
json.dump(out, open(f"runs/pulse/paired_{V1}_{V2}.json", "w"), indent=1); hb.finish("t20-paired", "done", last=f"story {out['fields']['story']['diff']}, topic1 {out['fields']['topic1']['diff']}, found {out['fields']['found']['diff']}, which {out['which_given_real_pooled']['diff']}")
