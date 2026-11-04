"""T20 round 2 (ledger L455): train story type and topic on Haiku vs Sonnet vs both labels; score on DEVQ. Local, CPU, no hosted calls.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python round2_story_topic.py"""
import json, glob, re, sys, math, time, pickle, numpy as np, scipy.sparse as sp, warnings
warnings.filterwarnings("ignore"); sys.path.insert(0, ".")
from expert1_runtime import Expert3
from sklearn.linear_model import LogisticRegression
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; art = pickle.load(open("runs/expert1/expert1_v5_leaf.pkl", "rb")); reg = {r["version"]: r for r in json.load(open("engine_versions.json"))}["v5-leaf"]; e = Expert3(reg["path"])
eid = {i: k for k, i in enumerate(json.load(open("runs/embeds/bge_small_ids.json")))}; LEAF = np.load("runs/embeds/leaf_64_fp32.npy")
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; hk = {}; old = {}; sn = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]; old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7/more*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
oi = sorted(old); dt = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]; test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test)
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start and i in eid]; strn = [i for i in trn if i in sn]; pos = {i: k for k, i in enumerate(trn)}
qt = {r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")}; dsn = {r["item_id"]: r["label"] for r in J("runs/pulse/devq/labels.jsonl")}; dq = sorted(i for i in dsn if i in qt)
clean = lambda t: re.sub(r"\s+", " ", t); XS = lambda texts: sp.hstack([art["vw"].transform([clean(t) for t in texts]), art["vc"].transform([clean(t) for t in texts])]).tocsr()
Xtr = sp.hstack([XS([pool[i]["text"] for i in trn]), sp.csr_matrix(LEAF[[eid[i] for i in trn]] * 1.5)]).tocsr(); Xdq = sp.hstack([XS([qt[i] for i in dq]), sp.csr_matrix(np.array([e.embed(qt[i]) for i in dq]))]).tocsr(); print("features ready", len(trn), len(strn), len(dq), flush=True)
def wil(k, m, z=1.96):
    p = k / m; d = 1 + z * z / m; c = (p + z * z / (2 * m)) / d; s = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d; return [round(c - s, 3), round(c + s, 3)]
import os
QUICK = "--sonnet-only" in sys.argv
res = json.load(open("runs/pulse/round2_topic.json")) if QUICK and os.path.exists("runs/pulse/round2_topic.json") else {}
if QUICK:
    sys.path.insert(0, "../../kit/live"); import heartbeat as hb
    hb.beat("t20-r2-topic-sonnet-rows", pid=os.getpid(), where="[CPU]", task="T20", state="running", progress="topic: Sonnet-trained 6,000 and learning curve (Haiku control done: top-1 0.765)", why="Does training topic on Sonnet labels beat the Haiku-trained control (L455)? Lighter rerun after the 1-hour cap.", success="Sonnet-trained beats the control by 0.02 on top-1 with non-overlapping intervals", next="Record WIN or NO GAIN; decide on buying more Sonnet labels (L4)", need="Nothing", cap=3600)
def run(field, name, ix, y, w=None, C=1.0):
    t0 = time.time(); clf = LogisticRegression(C=C, max_iter=120).fit(Xtr[ix], y, sample_weight=w); P = clf.predict_proba(Xdq); cl = clf.classes_; truth = [dsn[i][field] for i in dq]
    t1 = np.array([cl[P[k].argmax()] == truth[k] for k in range(len(dq))]); r = {"top1": round(float(t1.mean()), 3), "top1_ci95": wil(int(t1.sum()), len(dq))}
    if field == "topic": t2 = np.array([truth[k] in [cl[j] for j in np.argsort(-P[k])[:2]] for k in range(len(dq))]); r["top2"] = round(float(t2.mean()), 3); r["top2_ci95"] = wil(int(t2.sum()), len(dq))
    r["fit_s"] = round(time.time() - t0); res[f"{field}: {name}"] = r; print(field, name, json.dumps(r), flush=True); json.dump(res, open(f"runs/pulse/round2_{field}.json", "w"), indent=1)
FIELDS = [a for a in sys.argv[1:] if a in ("story_type", "topic")] or ["story_type", "topic"]
for field in FIELDS:
    yH = np.array([hk[i][field] for i in trn]); sx = [pos[i] for i in strn]; yS = np.array([sn[i][field] for i in strn])
    if not QUICK: run(field, "Haiku-trained (36,070) [control]", np.arange(len(trn)), yH)
    run(field, "Sonnet-trained (6,000)", sx, yS)
    if not QUICK: run(field, "Haiku + Sonnet x5", np.r_[np.arange(len(trn)), sx], np.r_[yH, yS], np.r_[np.ones(len(trn)), 5 * np.ones(len(sx))])
    for n in (1500, 3000):
        ix = np.random.RandomState(0).choice(len(sx), n, replace=False); run(field, f"Sonnet-trained curve n={n}", [sx[k] for k in ix], yS[ix])
if QUICK: hb.finish("t20-r2-topic-sonnet-rows", "done", last="topic Sonnet-trained rows done: see runs/pulse/round2_topic.json")
