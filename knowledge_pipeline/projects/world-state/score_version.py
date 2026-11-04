"""Build-and-score harness: ONE command scores a saved BitMob Expert 1 version and (with --record) puts it on the ledger so the Engine tab grows.
    /workspace/models/embed-zs/.venv/bin/python score_version.py <version> [--record] [--skip-footprint] [--skip-gap]      CPU only, no hosted calls
Add a new build to engine_versions.json first (version, path, class, what, ms_note), then run this. Default is a DRY RUN: nothing is written to the ledger without --record, and a version already on the ledger is refused (append-only: never record twice).
Same items, same definitions every time: the last fifth by date of the Haiku pool that Sonnet also labelled (as score_natural.py); agreement with Sonnet, never accuracy; presence weighted to the natural stream; Wilson 95% intervals; Q26 = against the last earlier version that has the field.
Also measures, in fresh one-thread processes (3 runs, median and spread): memory, load time, p50, p95, stalls; and the train-versus-unseen gap (1,200 items per period against the Haiku label the model trained on).
Result: runs/snapshots/engine_history.json (all versions) and runs/snapshots/score_<version>.json."""
import json, glob, sys, math, os, subprocess, pathlib, statistics, numpy as np
sys.path.insert(0, "."); from expert1_runtime import Expert, Expert3
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
args = [a for a in sys.argv[1:] if not a.startswith("--")]; flag = lambda f: f in sys.argv
if not args: sys.exit(__doc__)
REG = json.load(open("engine_versions.json")); names = [r["version"] for r in REG]; ver = args[0]
if ver not in names: sys.exit(f"unknown version {ver}; add it to engine_versions.json (known: {names})")
reg = REG[names.index(ver)]; LV = ["minor", "notable", "major", "severe", "extreme"]
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
CLS = {"V1": V1, "Expert": Expert, "Expert3": Expert3}
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; old = {}; sn = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
oi = sorted(old); dt = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]; parts = np.array_split(o, 5); test = [oi[k] for k in parts[4]]; vt = [i for i in test if i in sn]; n = len(vt)
hn_t = sum(1 for i in test if not old[i]["conditions"]); hn_v = sum(1 for i in vt if not old[i]["conditions"]); hp_t = len(test) - hn_t; hp_v = n - hn_v
w = np.array([hp_t / hp_v if old[i]["conditions"] else hn_t / hn_v for i in vt]); W = lambda m: float(w[m].sum()); sp_ = np.array([1 if sn[i]["conditions"] else 0 for i in vt])
def wilson(k, m, z=1.96):
    if m == 0: return (None, None)
    p = k / m; d = 1 + z * z / m; c = (p + z * z / (2 * m)) / d; s = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d; return (round(c - s, 3), round(c + s, 3))
prev = json.load(open("runs/snapshots/engine_history.json")) if os.path.exists("runs/snapshots/engine_history.json") else {"items": n, "teacher": "claude-sonnet-5-5 (ws-v2-frozen)", "versions": []}
out_v = {"version": ver, "artefact": reg["path"], "what": reg["what"], "read_ms_mean_one_thread": reg["ms_note"], "fields": {}}; F = out_v["fields"]
def put(k, hit, m, answered=None): lo, hi = wilson(int(hit), m); F[k] = {"n": int(m), "agree": round(float(hit) / m, 3) if m else None, "lo": lo, "hi": hi, "answered_share": answered}
e = None
try: e = CLS[reg["class"]](reg["path"])
except ValueError as err:  # an artefact that does not record its encoder length cannot be re-read faithfully (the runtime refuses to guess): use its saved report
    rep = json.load(open(reg["path"].replace(".pkl", "_report.json")))
    for k, a, m in (("topic_top2", rep["topic"]["top2_all_voted"], n), ("which_condition", rep["condition_given_present_answered"]["top1_among_answered"], rep["condition_given_present_answered"]["answered_with_cut"])):
        lo, hi = wilson(round(a * m), m); F[k] = {"n": int(m), "agree": a, "lo": lo, "hi": hi, "answered_share": rep["topic"]["answered_share"] if k == "topic_top2" else None}
    out_v["not_rescored"] = "from its saved report (" + str(err)[:70] + ")"
if e:
    R = [e.read(pool[i]["text"]) for i in vt]
    sa = np.array([r["story_type"]["status"] == "answered" for r in R]); sok = np.array([r["story_type"]["answer"] == sn[i]["story_type"] for r, i in zip(R, vt)]); put("story_type", sok[sa].sum(), sa.sum(), round(float(sa.mean()), 3))
    ta = np.array([r["topic_top2"]["status"] == "answered" for r in R]); t1 = np.array([bool(r["topic_top2"]["answer"]) and r["topic_top2"]["answer"][0] == sn[i]["topic"] for r, i in zip(R, vt)]); t2 = np.array([sn[i]["topic"] in (r["topic_top2"]["answer"] or []) for r, i in zip(R, vt)])
    put("topic_top1", t1[ta].sum(), ta.sum(), round(float(ta.mean()), 3)); put("topic_top2", t2[ta].sum(), ta.sum(), round(float(ta.mean()), 3))
    cp = [r["condition_present"] for r in R]; pa = np.array([c["status"] == "answered" for c in cp]); pr = np.array([bool(c["answer"]) if c["answer"] is not None else False for c in cp]); pok = pr == (sp_ == 1); cm = pa & pr
    lo, hi = wilson(round(W(pa & pok) / w.mean()), round(W(pa) / w.mean())); F["condition_present"] = {"n": int(pa.sum()), "agree": round(W(pa & pok) / W(pa), 3), "lo": lo, "hi": hi, "answered_share": round(W(pa) / W(np.ones(n, bool)), 3)}
    F["condition_reach"] = {"n": int((sp_ == 1).sum()), "agree": round(W(cm & (sp_ == 1)) / W(sp_ == 1), 3), "lo": None, "hi": None, "answered_share": None}
    wc = wo = dn = do = sn_ = so = 0
    for r, i in zip(R, vt):
        sc = sn[i]["conditions"]; c = r.get("condition")
        if c and c.get("status") == "answered" and sc:
            wc += 1; names_ = [x["condition"] for x in sc]; hit = c["answer"][0] in names_; wo += hit
            if hit and "direction" in c:
                x = next(x for x in sc if x["condition"] == c["answer"][0]); dn += 1; do += (c["direction"] == x["direction"]); sn_ += 1; so += (abs(LV.index(c["size"]) - LV.index(x["level"])) <= 1)
    if wc: put("which_condition", wo, wc); put("direction", do, dn); put("size_within_one", so, sn_)
    if not flag("--skip-gap"):
        rng = np.random.RandomState(0); gap = {}
        for nm, idx in (("train", np.concatenate(parts[:4])), ("unseen", parts[4])):
            ids = [oi[k] for k in rng.choice(idx, 1200, replace=False)]; RR = [e.read(pool[i]["text"]) for i in ids]
            gap[nm] = {"story": round(float(np.mean([r["story_type"]["answer"] == old[i]["story_type"] for r, i in zip(RR, ids)])), 3), "topic_top2": round(float(np.mean([old[i]["topic"] in (r["topic_top2"]["answer"] or []) for r, i in zip(RR, ids)])), 3)}
        out_v["gap"] = {**gap, "story_gap": round(gap["train"]["story"] - gap["unseen"]["story"], 3), "topic_gap": round(gap["train"]["topic_top2"] - gap["unseen"]["topic_top2"], 3), "note": "agreement with the Haiku label (the training teacher), 1,200 random items per period, seed 0"}
if e and not flag("--skip-footprint"):
    env = {**os.environ, "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}; runs = []
    for _ in range(3): runs.append(json.loads(subprocess.run([sys.executable, "footprint.py", reg["path"]], capture_output=True, text=True, env=env).stdout.strip().splitlines()[-1]))
    med = lambda k: round(statistics.median(r[k] for r in runs), 1)
    out_v["footprint"] = {"runs": len(runs), "ram_mb_peak": med("ram_mb_peak"), "ram_mb_after_load": med("ram_mb_after_load"), "file_mb": runs[0]["file_mb"], "onnx_mb": runs[0]["onnx_mb"], "load_s": med("load_s"), "ms_p50": med("ms_p50"), "ms_p95": med("ms_p95"), "ms_p95_spread": [min(r["ms_p95"] for r in runs), max(r["ms_p95"] for r in runs)], "ms_max_worst": max(r["ms_max"] for r in runs), "stalled_runs": sum(r["ms_max"] > 500 for r in runs), "threads": 1, "loadavg_max": max(max(r["loadavg_start"], r["loadavg_end"]) for r in runs)}
# Q26: each field against the last earlier version (registry order) that has it
earlier = [v for v in prev["versions"] if v["version"] in names[:names.index(ver)]]; out_v["vs_previous"] = {}
for k, v in F.items():
    p = next((x["fields"][k] for x in reversed(earlier) if k in x["fields"]), None)
    out_v["vs_previous"][k] = "new" if not p else ("not tested" if v["lo"] is None or p["lo"] is None else ("better" if v["lo"] > p["hi"] else ("worse" if v["hi"] < p["lo"] else "no change")))
prev["versions"] = [x for x in prev["versions"] if x["version"] != ver] + [out_v]; prev["versions"].sort(key=lambda x: names.index(x["version"]))
json.dump(out_v, open(f"runs/snapshots/score_{ver}.json", "w"), indent=1)
if flag("--record"): json.dump(prev, open("runs/snapshots/engine_history.json", "w"), indent=1)
print(json.dumps({"version": ver, "fields": {k: [f["agree"], f["n"]] for k, f in F.items()}, "vs_previous": out_v["vs_previous"], "gap": out_v.get("gap"), "footprint": out_v.get("footprint")}, indent=1))
if flag("--record"):
    led = [json.loads(l) for l in open(H0.parents[1] / ".ledger/ledger.jsonl")]
    on = lambda fld: any(m.get("version") == ver and m.get("field") == fld for l in led for m in (l.get("measures") or []))
    if flag("--gap-only"):
        if on("train_vs_unseen_gap"): sys.exit(f"{ver} already has its gap on the ledger")
    elif any(m.get("version") == ver and m.get("gate") == "Q25" for l in led for m in (l.get("measures") or [])): sys.exit(f"{ver} is already on the ledger: refusing to record twice (use --gap-only to add only the gap)")
    M = []
    for k, f in ({} if flag("--gap-only") else F).items():
        if k == "condition_reach": continue
        M.append({"gate": "Q25", "pass": bool(f["lo"] is not None and f["lo"] >= 0.8 * f["agree"]), "field": k, "version": ver, "engine": "BitMob Expert 1", "n_in": f["n"], "agree": f["agree"], "lo": f["lo"], "hi": f["hi"], "answered_share": f["answered_share"], "value": f"BitMob Expert 1 {ver}, {k}: agreement with Sonnet {f['agree']} (95% {f['lo']} to {f['hi']}) on {f['n']} of {n} later unseen items; answered share {f['answered_share']}. Agreement, not accuracy."})
    r = None if flag("--gap-only") else F.get("condition_reach")
    if r: M.append({"gate": "Q25", "pass": False, "field": "condition_reach", "version": ver, "engine": "BitMob Expert 1", "n_in": r["n"], "agree": r["agree"], "value": f"BitMob Expert 1 {ver}: finds {r['agree']} of the {r['n']} stories where Sonnet found a condition (weighted to the natural stream)."})
    for k, s in ({} if flag("--gap-only") else out_v["vs_previous"]).items():
        if s != "not tested": M.append({"gate": "Q26", "pass": s != "worse", "field": k, "version": ver, "engine": "BitMob Expert 1", "value": f"{k}: {ver} against the last earlier version that has it: {s} (non-overlapping 95% intervals, else no change)"})
    if "footprint" in out_v:
        fp = out_v["footprint"]; M.append({"gate": "Q28", "pass": fp["ms_p50"] < 50 and fp["ms_p95"] < 50, "version": ver, "engine": "BitMob Expert 1", **{k: fp[k] for k in ("ram_mb_peak", "ram_mb_after_load", "file_mb", "onnx_mb", "load_s", "ms_p50", "ms_p95", "threads")}, "stalls": f"{fp['stalled_runs']} of {fp['runs']} runs had a single item over 500 ms (worst {fp['ms_max_worst']} ms); p95 ranged {fp['ms_p95_spread'][0]} to {fp['ms_p95_spread'][1]} ms; machine load average up to {fp['loadavg_max']} during the runs (a stall is CPU-bound inside the encoder path, not host steal; cause otherwise unfound)",
                  "value": f"{ver} footprint (score_version.py, {fp['runs']} fresh runs, 400 natural test items, one CPU thread): peak memory {fp['ram_mb_peak']} MB, load {fp['load_s']} s, typical read {fp['ms_p50']} ms, 95% under {fp['ms_p95']} ms; {fp['stalled_runs']} of {fp['runs']} runs had a stalled item over 500 ms."})
    if "gap" in out_v: g = out_v["gap"]; M.append({"gate": "Q25", "pass": g["topic_gap"] <= 0.05, "field": "train_vs_unseen_gap", "version": ver, "engine": "BitMob Expert 1", "story_gap": g["story_gap"], "topic_gap": g["topic_gap"], "value": f"{ver}: agreement with the Haiku label on items it trained on vs later unseen items: story {g['train']['story']} vs {g['unseen']['story']} (gap {g['story_gap']}), topic top-2 {g['train']['topic_top2']} vs {g['unseen']['topic_top2']} (gap {g['topic_gap']}). A big gap means it is memorising."})
    subprocess.run(["node", "cp.mjs", "measure", "T10", "--who", "S?", "--measures", json.dumps(M)], cwd=H0.parents[1] / ".ledger", check=True); print("recorded to ledger:", len(M), "measures")
    print("REMINDER: if this version changes the engine design (trunk, heads, stages, speed or memory story), record a new engine card so the Engine tab says so: node cp.mjs engine T10 --who <code> --card <json> (owner rule 2026-11-01).")
