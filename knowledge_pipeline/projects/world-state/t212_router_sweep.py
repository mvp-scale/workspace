"""T212 (step 19, sweep after T148-M): same replay and heads as t211 (T211 text follows), but the heads' scores are kept and the answer lines are swept: false-positive quota and miss quota, both-answers mode and no-only mode (the CPU answers only a sure NO and defers every possible yes to Clef). For each setting: answered share of cells, false and missed fires per story, share of engine outputs within the Step 1 noise band. Summary: the largest answered share among settings with at least half of the outputs within the band. Prediction in card T148-N. (T211 text:): engine-level replay of the per-key ROUTER. Reuses the T35 harness (probes/world-engine/sensitivity.py: engine feed arithmetic, the Step 1 noise band from repeated noisy replays of Clef's own readings). Stories: the 8,545 Clef-labelled state-text stories (t209); heads trained on the oldest 70% by day, replay on up to R of the newest 30% (held out). Router per story and key: the CPU answers when its score is past the line fitted at false-positive quota 0.0010 (yes sets the key's reading to its median positive value, no sets it to 0), otherwise Clef's own reading is kept. The 328 attribute readings then go through the engine's own presence rule (sensitivity.presence) and the replay. Compared with the all-Clef replay of the same stories: share of the engine's outputs within the noise band (ratio of absolute difference to the band at most 1), median and max ratio. Also an all-CPU variant (no Clef fallback) for contrast. Prediction in the ledger before the run.
Run (from projects/world-state): R=800 OUT=runs/pulse/t212 /workspace/kev/.venv/bin/python -u t212_router_sweep.py   (needs sklearn: this uses the kev venv for the engine; see the fallback note in the script)"""
import os, sys, json, time, pathlib, itertools, numpy as np
os.environ.setdefault("WORLD_GPU", "0"); os.environ.setdefault("WE_RULES", "rules_v2")
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t211")); OUT.mkdir(parents=True, exist_ok=True); R = int(os.environ.get("R", 800)); T0 = time.time(); FPQ = 0.0010
sys.path.insert(0, "/workspace/probes/world-engine"); import sensitivity as SN
rows = []; seen = set()
for f in ("test", "r3", "r5", "c1", "r1_local", "r1b"):
    for l in open("/workspace/data/clef-labels/" + f + ".jsonl"):
        try: r = json.loads(l)
        except Exception: continue
        if "P" in r and len(r["P"]) == 328 and r["id"] not in seen: seen.add(r["id"]); rows.append(r)
keys = list(rows[0]["P"]); n = len(rows); Pm = np.array([[r["P"][k] for k in keys] for r in rows], dtype=np.float32); Y = (Pm >= 0.5).astype(int); grp = np.array([r["id"] for r in rows]); pub = [r.get("day") or "" for r in rows]
X = np.load("runs/pulse/t209/t209_embeddings.npy"); assert len(X) == n
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
X = PCA(256, random_state=0).fit_transform(X - X.mean(0)).astype(np.float32); X /= X.std(0) + 1e-6
order = np.argsort(pub); te = np.zeros(n, bool); te[order[int(0.7 * n):]] = True; tr = ~te
def fitline(s, yy, fp=FPQ, fn=0.05):
    neg = np.sort(s[yy == 0])[::-1]; hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); lo = pos[int(np.floor(fn * len(pos)))]; return lo, hi
use = [j for j in range(len(keys)) if Y[tr, j].sum() >= 10]; use = use[:int(os.environ["N"])] if os.environ.get("N") else use; OOF = {}; HT = {}; Xt, gt = X[tr], grp[tr]
for jn, j in enumerate(use):
    yt = Y[tr, j]; oof = np.zeros(len(yt))
    for a, b in GroupKFold(5).split(Xt, yt, gt): oof[b] = LogisticRegression(C=0.3, max_iter=300).fit(Xt[a], yt[a]).predict_proba(Xt[b])[:, 1]
    OOF[j] = oof; HT[j] = LogisticRegression(C=0.3, max_iter=300).fit(Xt, yt).predict_proba(X[te])[:, 1]
    if jn % 60 == 0: print("heads", jn, len(use), round(time.time() - T0), flush=True)
medpos = np.array([float(np.median(Pm[Y[:, j] == 1, j])) if Y[:, j].sum() else 0.9 for j in range(len(keys))], dtype=np.float32)
rng = np.random.RandomState(5); idx = np.where(te)[0]; idx = np.sort(rng.choice(idx, min(R, len(idx)), replace=False)); print("replay stories", len(idx), flush=True)
import classify as C
def story_of(i, P): rd = C.read(P); w_, _, _ = C.type_weight(rd["gate"]["happened"], rd["gate"]["announced"], rd["gate"]["opinion"], P["g|forecast"]); return w_
stories = [{"id": rows[i]["id"], "w": story_of(i, rows[i]["P"]), "keys": SN.presence(rows[i]["P"])} for i in idx]
SN.G["stories"] = stories; SN.G["med"] = SN.medians(stories); SN.build()
clean = SN.replay(SN.clean_readings(stories)); cr = SN.clean_readings(stories); outs = np.array([SN.replay(cr, seed=s, noise=True) for s in range(10)])
pair = np.array([np.abs(outs[i] - outs[j]) for i, j in itertools.combinations(range(10), 2)]); band = np.percentile(pair, 95, axis=0); print("band median", float(np.median(band)), round(time.time() - T0), flush=True)
te_idx = np.where(te)[0]; pos_in_te = {int(i): p for p, i in enumerate(te_idx)}; idx_te = np.array([pos_in_te[int(i)] for i in idx])
def lines_for(fp, fn, no_only):
    yes_ = np.zeros((n, len(keys)), bool); no_ = np.zeros((n, len(keys)), bool)
    for j in use:
        yt = Y[tr, j]; oof = OOF[j]; lo, hi = fitline(oof, yt, fp=fp, fn=fn); h = HT[j]
        no_[te_idx, j] = h < lo
        if not no_only: yes_[te_idx, j] = h > hi
    return yes_, no_
def build_P(i, yes_, no_):
    P = dict(rows[i]["P"])
    for j, k in enumerate(keys):
        if not k.startswith("a|"): continue
        if yes_[i, j]: P[k] = float(medpos[j])
        elif no_[i, j]: P[k] = 0.0
    return P
def run(yes_, no_):
    rs = [(SN.readings_of(SN.presence(build_P(i, yes_, no_))), stories[s]["w"]) for s, i in enumerate(idx)]; o = SN.replay(rs); d = np.abs(o - clean) / band
    return {"ratio_max": round(float(d.max()), 3), "ratio_median": round(float(np.median(d)), 3), "share_outputs_within_band": round(float((d <= 1).mean()), 3)}
akeys = [j for j, k in enumerate(keys) if k.startswith("a|")]
SET = [("both", 0.0010, 0.05), ("both", 0.0010, 0.02), ("both", 0.0010, 0.01), ("both", 0.0003, 0.01), ("both", 0.0003, 0.005), ("both", 0.0001, 0.002), ("no_only", 0.0010, 0.02), ("no_only", 0.0010, 0.01), ("no_only", 0.0010, 0.005), ("no_only", 0.0010, 0.002)]
res = {"stories_replayed": len(idx), "keys_with_heads": len(use), "band_median_points": round(float(np.median(band)), 4), "clef_fired_attribute_keys_per_story": round(float(Y[idx][:, akeys].sum() / len(idx)), 3), "settings": []}
for mode, fp, fn in SET:
    yes_, no_ = lines_for(fp, fn, mode == "no_only"); r_ = run(yes_, no_)
    yerr = int((yes_[idx] & (Y[idx] == 0)).sum()); nerr = int((no_[idx] & (Y[idx] == 1)).sum()); ans = int((yes_[idx] | no_[idx])[:, akeys].sum())
    row = {"mode": mode, "fp_quota": fp, "miss_quota": fn, "answered_cell_share": round(ans / (len(idx) * len(keys)), 3), "false_fires_per_story": round(yerr / len(idx), 3), "missed_fires_per_story": round(nerr / len(idx), 3), **r_}; res["settings"].append(row); print(row, round(time.time() - T0), flush=True)
good = [r for r in res["settings"] if r["share_outputs_within_band"] >= 0.5]
res["best_answered_share_at_band_ge_0_5"] = max([r["answered_cell_share"] for r in good], default=0.0); res["best_band_share"] = max(r["share_outputs_within_band"] for r in res["settings"]); res["answered_share_at_best_band"] = [r["answered_cell_share"] for r in res["settings"] if r["share_outputs_within_band"] == res["best_band_share"]][0]; res["seconds"] = round(time.time() - T0)
json.dump(res, open(OUT / "t212_router_sweep.json", "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "settings"}))
