"""T54 background learner. For topic, story type and condition presence: random search over sparse-head settings on a DEV split of the training labels (sealed set never read during search), then refit the dev-best and the default on all training items and score both on the sealed set ONCE, paired. Text-only plus optional tool-evidence features (scaled). Judge: agreement with Sonnet, not outside truth.
    nohup timeout 3300 /workspace/models/embed-zs/.venv/bin/python -u learn_loop.py MAXSEC [N_CONFIGS_PER_HEAD]  -> runs/pulse/learn_loop.json, log runs/pulse/learn_loop.log"""
import json, sys, time, os, random, collections
import numpy as np
from multiprocessing import Pool
from scipy.sparse import hstack
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
T0 = time.time(); MAXS = float(sys.argv[1]) if len(sys.argv) > 1 else 3000; NC = int(sys.argv[2]) if len(sys.argv) > 2 else 150
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(S); sid = sorted(i for i in S if i in txt)
EV = {}
for p in ("runs/harvest/pool_v2/labelled.jsonl", "runs/harvest/pool_v2/sealed_evidence.jsonl"):
    for r in J(p):
        d = collections.Counter(f'{x["tool"]}|{x["kind"]}|{x["strength"]}' for x in r["items"]); EV[r["item_id"]] = {k: float(np.log1p(v)) for k, v in d.items()}
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; best = {}
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]
    if r["family"] != "sonnet" or i not in txt or i in sealed or not r.get("topic") or not r.get("story_type"): continue
    rk = RANK.get(r["version"], 2)
    if i not in best or rk < best[i][0]: best[i] = (rk, r)
ids = sorted(best); random.Random(20261110).shuffle(ids); nd = int(0.15 * len(ids)); dev, fitids = ids[:nd], ids[nd:]
HEADS = {"topic": lambda r: r["topic"], "story_type": lambda r: r["story_type"], "condition_presence": lambda r: (r.get("n_conditions") or 0) > 0}
GOLD = {"topic": lambda l: l["topic"], "story_type": lambda l: l["story_type"], "condition_presence": lambda l: bool(l["conditions"])}
Y = {h: {i: HEADS[h](best[i][1]) for i in ids} for h in HEADS}
VECS = {"w1_100k": dict(ngram_range=(1, 1), min_df=3, max_features=100000), "w12_150k": dict(ngram_range=(1, 2), min_df=3, max_features=150000), "w12_150k_md2": dict(ngram_range=(1, 2), min_df=2, max_features=150000),
        "w12_400k": dict(ngram_range=(1, 2), min_df=3, max_features=400000), "w13_400k": dict(ngram_range=(1, 3), min_df=3, max_features=400000)}
M = {}
def build(key, trn, others):
    v = TfidfVectorizer(sublinear_tf=True, **VECS[key]); A = v.fit_transform([txt[i] for i in trn]); return v, A, [v.transform([txt[i] for i in o]) for o in others]
def evmat(trn, others):
    dv = DictVectorizer(); A = dv.fit_transform([EV.get(i, {}) for i in trn]); return A, [dv.transform([EV.get(i, {}) for i in o]) for o in others]
for k in VECS: _, M[("fit", k)], (M[("dev", k)],) = build(k, fitids, [dev])
M[("fit", "ev")], (M[("dev", "ev")],) = evmat(fitids, [dev])
DEFAULT = dict(vec="w12_150k", alpha=2e-6, loss="log_loss", cw=None, iters=12, evs=0.0)
def mk(cfg, h): return SGDClassifier(loss=cfg["loss"], alpha=cfg["alpha"], max_iter=cfg["iters"], tol=None, n_jobs=1, random_state=7, class_weight="balanced" if (cfg["cw"] or h == "condition_presence" and cfg.get("cw", 1) == "balanced") else None)
def X(split, cfg): A = M[(split, cfg["vec"])]; return hstack([A, M[(split, "ev")] * cfg["evs"]]).tocsr() if cfg["evs"] else A
def metric(h, p, g):
    if h != "condition_presence": return float((p == g).mean())
    tp = (p & g).sum(); fp = (p & ~g).sum(); fn = (~p & g).sum(); a = tp / max(tp + fp, 1); b = tp / max(tp + fn, 1); return float(2 * a * b / max(a + b, 1e-9))
def job(a):
    h, cfg = a
    if time.time() - T0 > MAXS: return h, cfg, None, 0.0
    t = time.time(); y = np.array([Y[h][i] for i in fitids]); g = np.array([Y[h][i] for i in dev]); m = mk(cfg, h).fit(X("fit", cfg), y); return h, cfg, metric(h, m.predict(X("dev", cfg)), g), time.time() - t
rng = random.Random(7); tasks = []
for h in HEADS:
    tasks.append((h, dict(DEFAULT, cw="balanced" if h == "condition_presence" else None)))
    for _ in range(NC): tasks.append((h, dict(vec=rng.choice(list(VECS)), alpha=10 ** rng.uniform(-7, -4), loss=rng.choice(["log_loss", "modified_huber"]), cw=rng.choice([None, "balanced"]), iters=rng.choice([5, 10, 20, 30]), evs=rng.choice([0.0, 0.1, 0.3]))))
rng.shuffle(tasks); print(f"data ready {time.time() - T0:.0f}s, fit {len(fitids)} dev {len(dev)} sealed {len(sid)}, {len(tasks)} fits", flush=True)
res = collections.defaultdict(list); n = 0
with Pool(18) as P:
    for h, cfg, sc, dt in P.imap_unordered(job, tasks, chunksize=1):
        n += 1
        if sc is not None: res[h].append((sc, cfg, dt))
        if n % 25 == 0: print(n, f"{time.time() - T0:.0f}s", {k: round(max(x[0] for x in v), 4) for k, v in res.items()}, flush=True)
out = {"judge": "agreement with Sonnet on the sealed set, not outside truth", "dev_items": len(dev), "fit_items": len(fitids), "sealed_n": len(sid), "fits_done": sum(len(v) for v in res.values()), "wall_search_s": round(time.time() - T0, 1), "sealed_touches_per_head": 1, "heads": {}}
trn = sorted(ids); gB = {h: np.array([GOLD[h](S[i]) for i in sid]) for h in HEADS}; rg = np.random.default_rng(7)
Ba = vec_all = None
allv = {}
for h in HEADS:
    if not res[h]: continue
    top = sorted(res[h], key=lambda x: -x[0]); dflt = next(x for x in res[h] if x[1] == dict(DEFAULT, cw="balanced" if h == "condition_presence" else None)); bsc, bcfg, _ = top[0]
    preds = {}
    for tag, cfg in (("default", dflt[1]), ("tuned", bcfg)):
        v = TfidfVectorizer(sublinear_tf=True, **VECS[cfg["vec"]]); A = v.fit_transform([txt[i] for i in trn]); B = v.transform([txt[i] for i in sid])
        if cfg["evs"]: dv = DictVectorizer(); A = hstack([A, dv.fit_transform([EV.get(i, {}) for i in trn]) * cfg["evs"]]).tocsr(); B = hstack([B, dv.transform([EV.get(i, {}) for i in sid]) * cfg["evs"]]).tocsr()
        m = mk(cfg, h).fit(A, np.array([Y[h][i] for i in trn])); preds[tag] = m.predict(B)
    g = gB[h]; n_ = len(g); ixs = [rg.integers(0, n_, n_) for _ in range(500)]
    sc = lambda p, ix: metric(h, p[ix], g[ix]); a, b = sc(preds["default"], np.arange(n_)), sc(preds["tuned"], np.arange(n_)); d = [sc(preds["tuned"], i) - sc(preds["default"], i) for i in ixs]
    ci = [round(float(np.percentile(d, 2.5)), 4), round(float(np.percentile(d, 97.5)), 4)]
    out["heads"][h] = {"metric": "F1" if h == "condition_presence" else "agreement", "default_dev": round(dflt[0], 4), "tuned_dev": round(bsc, 4), "tuned_config": bcfg, "sealed_default": round(a, 4), "sealed_tuned": round(b, 4), "delta": round(b - a, 4), "delta_ci95": ci, "gain": ci[0] > 0, "fits_for_head": len(res[h]), "top5_dev": [round(x[0], 4) for x in top[:5]]}
    print(h, json.dumps(out["heads"][h]), flush=True)
out["wall_total_s"] = round(time.time() - T0, 1); json.dump(out, open("runs/pulse/learn_loop.json", "w"), indent=1); print("DONE", out["wall_total_s"], flush=True)
