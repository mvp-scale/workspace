"""Selective prediction check (playbook 00 section 4). Cutoff chosen on DEVQ only, applied once to sealed and MN-DS fresh.
    /workspace/models/embed-zs/.venv/bin/python selective_check.py   (from projects/world-state)"""
import json, math, sys, numpy as np
sys.path.insert(0, "."); from expert1_runtime import ExpertS
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); TX = {r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")}
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
def run(labels_path, which):
    out = []
    for r in J(labels_path):
        t = TX.get(r["item_id"]); 
        if not t: continue
        x = e.read(t); L = r["label"]
        s_ok = x["story_type"]["answer"] == L.get("story_type"); s_c = x["story_type"]["confidence"]
        t_ok = L.get("topic") in x["topic_top2"]["answer"]; t_c = x["topic_top2"]["confidence"]
        out.append((s_c, s_ok, t_c, t_ok))
    return np.array(out, dtype=float)
D = run("runs/pulse/devq/labels.jsonl", "devq"); S = run("runs/pulse/sealed/labels.jsonl", "sealed")
def ece(c, ok, bins=10):
    b = np.minimum((c * bins).astype(int), bins - 1); tot = 0.0
    for i in range(bins):
        m = b == i
        if m.any(): tot += m.mean() * abs(ok[m].mean() - c[m].mean())
    return round(float(tot), 3)
def cutoff(c, ok, target=0.95):
    o = np.argsort(-c); cs = c[o]; hit = np.cumsum(ok[o]) / np.arange(1, len(c) + 1); good = np.where(hit >= target)[0]
    if len(good) == 0: return None
    k = good[-1]; return float(cs[k])
res = {}
for name, ci, oi in (("story_type", 0, 1), ("topic_top2", 2, 3)):
    tau = cutoff(D[:, ci], D[:, oi]); r = {"cutoff_from_devq": tau, "ece_devq": ece(D[:, ci], D[:, oi]), "ece_sealed": ece(S[:, ci], S[:, oi]), "unfiltered_devq": round(float(D[:, oi].mean()), 3), "unfiltered_sealed": round(float(S[:, oi].mean()), 3)}
    if tau is not None:
        for tag, A in (("devq", D), ("sealed", S)):
            m = A[:, ci] >= tau; k = int(A[m, oi].sum()); n = int(m.sum()); r[tag] = {"coverage": round(float(m.mean()), 3), "accepted_n": n, "agree": round(k / n, 3), "ci95": wil(k, n)}
    res[name] = r
# MN-DS fresh, topic two guesses vs human labels (mapping v1), cutoff from DEVQ
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json")); tau = res["topic_top2"]["cutoff_from_devq"]; k = n = tot = 0
for l in open("/workspace/data/anchors/mn_ds/items_T28b.jsonl"):
    x = json.loads(l); a = e.read(x["text"])["topic_top2"]; tot += 1
    if tau is not None and a["confidence"] >= tau:
        n += 1; k += any(G[x["id"]]["l1"] in M.get(t, []) for t in a["answer"])
res["mnds_fresh_topic_top2"] = {"cutoff_from_devq": tau, "coverage": round(n / tot, 3), "accepted_n": n, "lenient_agree_with_human": round(k / max(n, 1), 3), "ci95": wil(k, n) if n else None, "unfiltered": 0.799}
json.dump(res, open("runs/pulse/selective_check.json", "w"), indent=1); print(json.dumps(res, indent=1))
