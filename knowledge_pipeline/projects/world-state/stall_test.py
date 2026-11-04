"""T20 end-to-end scorer (ledger L435): per Pulse field, the share of ALL items where the engine answers AND agrees with Sonnet, with Wilson 95% intervals; the condition chain is split into reach x which x direction x size on the items where Sonnet found a condition. Agreement with Sonnet, never accuracy. CPU only, local.
    /workspace/models/embed-zs/.venv/bin/python score_end2end.py <version> <set: old|dev2> [--save]
 devq = 2,000 natural random queue items published after all training and test data (weight 1); dev2 = a Haiku-negative stratum check, not natural; old = the 1,466 Sonnet-labelled test items (condition-enriched, re-weighted to the natural stream exactly as score_version.py); dev2 = natural random items (weight 1). SEALED is refused here."""
import json, glob, math, sys, pathlib, numpy as np
sys.path.insert(0, "."); from expert1_runtime import Expert, Expert3, ExpertS
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; LV = ["minor", "notable", "major", "severe", "extreme"]

class V1(Expert):  # v1 has only story type, topic (two guesses) and condition presence (copied from score_version.py)
    def __init__(self, path):
        import pickle; from model2vec import StaticModel
        self.M = pickle.load(open(path, "rb")); self.sm = StaticModel.from_pretrained(self.M["static"])
    def read(self, text):
        import re, scipy.sparse as sp
        M = self.M; t = re.sub(r"\s+", " ", text); h = re.split(r"(?<=[.!?])\s", t, 1)[0]; e = np.hstack([self.sm.encode([t]), self.sm.encode([h])])
        xwc = sp.hstack([M["vw"].transform([t]), M["vc"].transform([t])]).tocsr(); xt = sp.hstack([M["vt"].transform([t]), sp.csr_matrix(M["ss"].transform(e) * 0.1)]).tocsr()
        ps = M["story"].predict_proba(xwc)[0]; pt = M["topic"].predict_proba(xt)[0]; o2 = np.argsort(-pt)[:2]; lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
        pr = float(1 / (1 + np.exp(-(lg(M["ph"].predict_proba(xwc)[:, 1]) + lg(M["ps"].predict_proba(xwc)[:, 1])) / 2))[0]); cp = max(pr, 1 - pr)
        return {"story_type": {"answer": str(M["story"].classes_[ps.argmax()]), "status": "answered" if ps.max() >= M["cuts"]["story_type"] else "unknown"}, "topic_top2": {"answer": [str(M["topic"].classes_[k]) for k in o2], "status": "answered" if pt[o2].sum() >= M["cuts"]["topic_top2"] else "unknown"},
                "condition_present": {"answer": bool(pr > .5), "confidence": cp, "status": "answered" if cp >= M["cuts"]["condition_present"] else "unknown"}}
ver, which = sys.argv[1], sys.argv[2]
if which not in ("devq", "devq2"): sys.exit("stall_test scores devq or devq2 only")
REG = {r["version"]: r for r in json.load(open("engine_versions.json"))}; reg = REG[ver]; e = {"V1": V1, "Expert": Expert, "Expert3": Expert3, "ExpertS": ExpertS}[reg["class"]](reg["path"])
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; hk = {}; sn = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
if which in ("dev2", "devq", "devq2"):
    if which in ("devq", "devq2"):
        for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r
        if which == "devq2":
            for r in J("runs/pulse/more/devq2_items.jsonl"): pool[r["id"]] = r
    for r in J(f"runs/pulse/{which}/labels.jsonl" if which != "devq2" else "runs/pulse/more/devq2/labels.jsonl"): sn[r["item_id"]] = r["label"]
    ids = sorted(i for i in sn if i in pool); w = np.ones(len(ids))
else:
    for f in glob.glob("runs/p7b/*/labels.jsonl"):
        for r in J(f): sn[r["item_id"]] = r["label"]
    oi = sorted(hk); dt = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]; test = [oi[k] for k in np.array_split(o, 5)[4]]; ids = [i for i in test if i in sn]
    hn_t = sum(1 for i in test if not hk[i]["conditions"]); hn_v = sum(1 for i in ids if not hk[i]["conditions"]); hp_t = len(test) - hn_t; hp_v = len(ids) - hn_v
    w = np.array([hp_t / hp_v if hk[i]["conditions"] else hn_t / hn_v for i in ids])
n = len(ids); R = [e.read(pool[i]["text"]) for i in ids]; S = [sn[i] for i in ids]
def wil(k, m, z=1.96):
    if m <= 0: return [None, None]
    p = k / m; d = 1 + z * z / m; c = (p + z * z / (2 * m)) / d; s = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d; return [round(c - s, 3), round(c + s, 3)]
neff = w.sum() ** 2 / (w ** 2).sum()   # effective sample size under the weights
def rate(mask, base=None):
    base = np.ones(n, bool) if base is None else base; num = w[mask & base].sum(); den = w[base].sum(); p = num / den if den else float("nan"); ne = den ** 2 / (w[base] ** 2).sum() if den else 0
    return {"rate": round(float(p), 3), "ci95": wil(p * ne, ne), "n_items": int(base.sum()), "n_effective": round(float(ne), 1)}
ans = lambda r, k: r.get(k, {}).get("status") == "answered"
st_a = np.array([ans(r, "story_type") for r in R]); st_ok = np.array([r["story_type"]["answer"] == s["story_type"] for r, s in zip(R, S)])
tp_a = np.array([ans(r, "topic_top2") for r in R]); t1 = np.array([bool(r["topic_top2"]["answer"]) and r["topic_top2"]["answer"][0] == s["topic"] for r, s in zip(R, S)]); t2 = np.array([s["topic"] in (r["topic_top2"]["answer"] or []) for r, s in zip(R, S)])
pos = np.array([bool(s["conditions"]) for s in S]); cp_a = np.array([ans(r, "condition_present") for r in R]); cp_yes = np.array([bool(r["condition_present"].get("answer")) for r in R]); cp_ok = cp_yes == pos
found = cp_a & cp_yes & pos; cq = [r.get("condition") for r in R]
wh = np.zeros(n, bool); di = np.zeros(n, bool); sz = np.zeros(n, bool); ca = np.zeros(n, bool)
for k, (c, s) in enumerate(zip(cq, S)):
    if not (found[k] and c and c.get("status") == "answered"): continue
    ca[k] = True; names = [x["condition"] for x in s["conditions"]]
    if c["answer"][0] in names:
        wh[k] = True; x = next(x for x in s["conditions"] if x["condition"] == c["answer"][0])
        di[k] = c.get("direction") == x["direction"]; sz[k] = ("size" in c) and abs(LV.index(c["size"]) - LV.index(x["level"])) <= 1

import collections
from scipy.stats import spearmanr
p7b = {}
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): p7b[r["item_id"]] = r["label"]
cnt_h = collections.Counter(c["condition"] for l in hk.values() for c in l.get("conditions", []))
cnt_s = collections.Counter(c["condition"] for l in p7b.values() for c in l.get("conditions", []))
# four-vote sample counts: condition named by 3 of 4 voters
def lo(pats):
    d = {}
    for p in pats:
        for f in glob.glob(p):
            for r in J(f): d[r["item_id"]] = r["label"]
    return d
V4 = [lo(["runs/p7b/*/labels.jsonl"]), lo(["runs/pulse/selfcons/labels.jsonl"]), lo(["runs/p7/*/labels.jsonl"]), lo(["runs/pulse/selfcons_haiku/labels.jsonl"])]
ids4 = [i for i in json.load(open("runs/pulse/selfcons/ids.json")) if all(i in v for v in V4)]
cnt_4 = collections.Counter()
for i in ids4:
    named = collections.Counter(c["condition"] for v in V4 for c in v[i].get("conditions", []))
    for c, k in named.items():
        if k >= 3: cnt_4[c] += 1
pos_n = collections.Counter(); hit = collections.Counter()
for k, (r, s) in enumerate(zip(R, S)):
    c = r.get("condition"); top = c["answer"][0] if (found[k] and c and c.get("status") == "answered") else None
    for x in s["conditions"]:
        pos_n[x["condition"]] += 1; hit[x["condition"]] += (top == x["condition"])
rows = [{"condition": c, "positives": pos_n[c], "recall": round(hit[c] / pos_n[c], 3), "cases_395_sample": cnt_4[c], "train_sonnet": cnt_s[c], "train_haiku": cnt_h[c]} for c in pos_n if pos_n[c] >= 5]
out = {"version": ver, "n_conditions": len(rows), "rows": sorted(rows, key=lambda r: -r["recall"])}
for key in ("cases_395_sample", "train_sonnet", "train_haiku"):
    rho, pv = spearmanr([r[key] for r in rows], [r["recall"] for r in rows]) if len(rows) > 3 else (float("nan"), float("nan"))
    out["rho_" + key] = [round(float(rho), 3), round(float(pv), 3)]
few = [r["recall"] for r in rows if r["train_sonnet"] < 30]; many = [r["recall"] for r in rows if r["train_sonnet"] >= 30]
out["mean_recall_under30_train_sonnet"] = [round(float(np.mean(few)), 3) if few else None, len(few)]; out["mean_recall_30plus_train_sonnet"] = [round(float(np.mean(many)), 3) if many else None, len(many)]
json.dump(out, open(f"runs/pulse/stall_test_{ver}_{which}.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "rows"})); [print(r) for r in out["rows"]]
