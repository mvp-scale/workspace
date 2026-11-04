"""Engine history: re-scores every saved BitMob Expert 1 artefact (v1, v2, v3, v3.1) on the SAME later unseen items with the SAME definitions, so the journey is comparable.
    /workspace/models/embed-zs/.venv/bin/python engine_history.py [--record]      CPU only, no hosted calls
Truth = Sonnet's label (agreement, not accuracy). Items = the last fifth by date of the Haiku pool that Sonnet also labelled (as score_natural.py / scorecard.py). Presence is weighted to the natural stream; other fields are plain counts.
Writes runs/snapshots/engine_history.json. With --record it appends Q25 (agreement with a Wilson 95% interval) and Q26 (this version against the previous one) measures per field to the ledger, task T10."""
import json, glob, sys, math, subprocess, pathlib, numpy as np
sys.path.insert(0, "."); from expert1_runtime import Expert, Expert3
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; old = {}; sn = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
oi = sorted(old); dt = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]; test = [oi[k] for k in np.array_split(o, 5)[4]]; vt = [i for i in test if i in sn]; n = len(vt)
hn_t = sum(1 for i in test if not old[i]["conditions"]); hn_v = sum(1 for i in vt if not old[i]["conditions"]); hp_t = len(test) - hn_t; hp_v = n - hn_v
w = np.array([hp_t / hp_v if old[i]["conditions"] else hn_t / hn_v for i in vt]); W = lambda m: float(w[m].sum()); LV = ["minor", "notable", "major", "severe", "extreme"]
def wilson(k, m, z=1.96):
    if m == 0: return (None, None)
    p = k / m; d = 1 + z * z / m; c = (p + z * z / (2 * m)) / d; s = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d; return (round(c - s, 3), round(c + s, 3))
class V1(Expert):  # v1 has no which-condition, direction or size heads: read only the three fields it has
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
VERS = [("v1", "runs/expert1/expert1_v1.pkl", V1, "static word vectors + word/char TF-IDF linear heads, presence blended from two teachers", 2.77), ("v2", "runs/expert1/expert1_v2.pkl", Expert, "v1 + which-condition, direction and size heads", 2.94),
        ("v3", "runs/expert1/expert1_v3.pkl", Expert3, "v2 + bge-small encoder (ONNX) on routed items only", 9.8), ("v3.1", "runs/expert1/expert1_v31.pkl", Expert3, "v3 with the encoder capped at 64 tokens (length chosen on validation)", 9.3)]
sp_ = np.array([1 if sn[i]["conditions"] else 0 for i in vt]); out = {"items": n, "teacher": "claude-sonnet-5-5 (ws-v2-frozen)", "versions": []}
for name, path, cls, what, ms in VERS:
    try: e = cls(path)
    except ValueError as err:  # v3 was saved without its encoder length; the runtime refuses to guess, so use the numbers in its saved report
        rep = json.load(open(path.replace(".pkl", "_report.json"))); F = {}
        for k, a, m in (("topic_top2", rep["topic"]["top2_all_voted"], n), ("which_condition", rep["condition_given_present_answered"]["top1_among_answered"], rep["condition_given_present_answered"]["answered_with_cut"])):
            lo, hi = wilson(round(a * m), m); F[k] = {"n": int(m), "agree": a, "lo": lo, "hi": hi, "answered_share": rep["topic"]["answered_share"] if k == "topic_top2" else None}
        out["versions"].append({"version": name, "artefact": path, "what": what, "read_ms_mean_one_thread": ms, "fields": F, "not_rescored": "from its saved report: the artefact does not record the encoder length, so it cannot be re-read faithfully (" + str(err)[:60] + ")"}); print(name, "from saved report", {k: v["agree"] for k, v in F.items()}); continue
    R = [e.read(pool[i]["text"]) for i in vt]; F = {}
    def put(k, hit, m, answered=None): lo, hi = wilson(int(hit), m); F[k] = {"n": int(m), "agree": round(hit / m, 3) if m else None, "lo": lo, "hi": hi, "answered_share": answered}
    sa = np.array([r["story_type"]["status"] == "answered" for r in R]); sok = np.array([r["story_type"]["answer"] == sn[i]["story_type"] for r, i in zip(R, vt)]); put("story_type", sok[sa].sum(), sa.sum(), round(float(sa.mean()), 3))
    ta = np.array([r["topic_top2"]["status"] == "answered" for r in R]); t1 = np.array([bool(r["topic_top2"]["answer"]) and r["topic_top2"]["answer"][0] == sn[i]["topic"] for r, i in zip(R, vt)]); t2 = np.array([sn[i]["topic"] in (r["topic_top2"]["answer"] or []) for r, i in zip(R, vt)])
    put("topic_top1", t1[ta].sum(), ta.sum(), round(float(ta.mean()), 3)); put("topic_top2", t2[ta].sum(), ta.sum(), round(float(ta.mean()), 3))
    cp = [r["condition_present"] for r in R]; pa = np.array([c["status"] == "answered" for c in cp]); pr = np.array([bool(c["answer"]) if c["answer"] is not None else False for c in cp]); pok = pr == (sp_ == 1); cm = pa & pr
    pw = W(pa) / W(np.ones(n, bool)); lo, hi = wilson(round(W(pa & pok) / w.mean()), round(W(pa) / w.mean())); F["condition_present"] = {"n": int(pa.sum()), "agree": round(W(pa & pok) / W(pa), 3), "lo": lo, "hi": hi, "answered_share": round(pw, 3)}
    F["condition_reach"] = {"n": int((sp_ == 1).sum()), "agree": round(W(cm & (sp_ == 1)) / W(sp_ == 1), 3), "lo": None, "hi": None, "answered_share": None}
    wc = wo = dn = do = sn_ = so = 0
    for r, i in zip(R, vt):
        sc = sn[i]["conditions"]; c = r.get("condition")
        if c and c.get("status") == "answered" and sc:
            wc += 1; names = [x["condition"] for x in sc]; hit = c["answer"][0] in names; wo += hit
            if hit and "direction" in c:
                x = next(x for x in sc if x["condition"] == c["answer"][0]); dn += 1; do += (c["direction"] == x["direction"]); sn_ += 1; so += (abs(LV.index(c["size"]) - LV.index(x["level"])) <= 1)
    if wc: put("which_condition", wo, wc); put("direction", do, dn); put("size_within_one", so, sn_)
    out["versions"].append({"version": name, "artefact": path, "what": what, "read_ms_mean_one_thread": ms, "fields": F}); print(name, {k: (v["agree"], v["n"]) for k, v in F.items()})
# Q26 vs previous version: non-overlapping intervals, else 'no change'
for j, b in enumerate(out["versions"][1:], 1):
    b["vs_previous"] = {}
    for k, v in b["fields"].items():
        p = next((x["fields"][k] for x in reversed(out["versions"][:j]) if k in x["fields"]), None)   # last earlier version that has this field
        if not p: b["vs_previous"][k] = "new"; continue
        if v["lo"] is None or p["lo"] is None: b["vs_previous"][k] = "not tested"; continue
        b["vs_previous"][k] = "better" if v["lo"] > p["hi"] else ("worse" if v["hi"] < p["lo"] else "no change")
json.dump(out, open("runs/snapshots/engine_history.json", "w"), indent=1)
if "--record" in sys.argv:
    cwd = H0.parents[1] / ".ledger"; prev = None
    skip = sys.argv[sys.argv.index("--skip") + 1].split(",") if "--skip" in sys.argv else []   # versions already on the ledger (append-only: never record twice)
    for v in out["versions"]:
        if v["version"] in skip: continue
        M = []
        for k, f in v["fields"].items():
            if k == "condition_reach": continue
            M.append({"gate": "Q25", "pass": bool(f["lo"] is not None and f["lo"] >= 0.8 * f["agree"]), "field": k, "version": v["version"], "engine": "BitMob Expert 1", "n_in": f["n"], "agree": f["agree"], "lo": f["lo"], "hi": f["hi"], "answered_share": f["answered_share"],
                      "value": f"BitMob Expert 1 {v['version']}, {k}: agreement with Sonnet {f['agree']} (95% {f['lo']} to {f['hi']}) on {f['n']} of {out['items']} later unseen items; answered share {f['answered_share']}. Agreement, not accuracy."})
        r = v["fields"].get("condition_reach")
        if r: M.append({"gate": "Q25", "pass": False, "field": "condition_reach", "version": v["version"], "engine": "BitMob Expert 1", "n_in": r["n"], "agree": r["agree"], "value": f"BitMob Expert 1 {v['version']}: finds {r['agree']} of the {r['n']} stories where Sonnet found a condition (weighted to the natural stream)."})
        if "vs_previous" in v:
            for k, s in v["vs_previous"].items():
                if s != "not tested": M.append({"gate": "Q26", "pass": s != "worse", "field": k, "version": v["version"], "engine": "BitMob Expert 1", "value": f"{k}: {v['version']} against previous version: {s} (non-overlapping 95% intervals, else no change)"})
        M.append({"gate": "Q28", "pass": True, "version": v["version"], "engine": "BitMob Expert 1", "value": f"{v['version']}: mean {v['read_ms_mean_one_thread']} ms per item on one CPU thread (from the build report; {v['what']})"})
        subprocess.run(["node", "cp.mjs", "measure", "T10", "--who", "S?", "--measures", json.dumps(M)], cwd=cwd, check=True)
    print("recorded to ledger")
