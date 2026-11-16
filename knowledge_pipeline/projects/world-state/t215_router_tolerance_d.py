"""T215 (next_steps 21, START HERE in GO.md): re-score the per-key router against the RECORDED tolerance (d), the yardstick of D-0004 and F-0020, not the bare noise band used by t211 to t214. Same harness as Step 1 (probes/world-engine/sensitivity.py) and the same arrays: the 880 Clef-read stories (those with a third wording in clef-q4km-w3.jsonl, in file order), data/step1/self3.npz (clean, wordings 0 to 2) and data/step1/noise.npz (band). Tolerance (d) per output = max(median over the three wording pairs of |w_i - w_j|, band) (sensitivity_report.py:150-154); the router passes when the largest ratio |router replay - clean replay| / tolerance over the 180 outputs is at most 1 (engine noise off, one deterministic replay). Router: per-key heads trained on the 8,545 state-text stories of data/clef-labels (t209, no overlap with these 880) read the story's title plus teaser; where a head is sure at its line the CPU answer replaces Clef's reading, otherwise Clef's own full-text reading is kept. Settings: quota 0.0010 with miss quota 0.05 (as t211), 0.0001 with 0.002 (strictest in t212), and no-only 0.0010 with 0.002. Also reports Clef's own wordings 0, 1, 2 against the clean replay under (d) as context. Known mismatch: the reference reading used the article text, the router reads title plus teaser. Prediction in card T148-Q.
Run (from projects/world-state): R=0 OUT=runs/pulse/t215 /workspace/kev/.venv/bin/python -u t215_router_tolerance_d.py"""
import os, sys, json, time, pathlib, sqlite3, numpy as np
os.environ.setdefault("WORLD_GPU", "0"); os.environ.setdefault("WE_RULES", "rules_v2")
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t215")); OUT.mkdir(parents=True, exist_ok=True); T0 = time.time(); N = int(os.environ.get("N", 0))
sys.path.insert(0, "/workspace/probes/world-engine"); sys.path.insert(0, "."); import sensitivity as SN
LAB = "/workspace/data/newsreader/labels/clef-q4km.jsonl"; w3ids = {json.loads(l)["id"] for l in open(LAB.replace(".jsonl", "-w3.jsonl"))}
all_rows = [json.loads(l) for l in open(LAB)]; keep = [i for i, r in enumerate(all_rows) if r["id"] in w3ids]; assert len(keep) == 880, len(keep)
stories_all = SN.load_stories(); stories = [stories_all[i] for i in keep]; rows = [all_rows[i] for i in keep]; assert [s["id"] for s in stories] == [r["id"] for r in rows]
SN.G["stories"] = stories; SN.G["med"] = SN.medians(stories); SN.build()
clean = SN.replay(SN.clean_readings(stories)); z = np.load("/workspace/data/step1/self3.npz"); band = np.load("/workspace/data/step1/noise.npz")["band"]
res = {"stories": len(stories), "clean_replay_max_abs_diff_vs_saved_self3": float(np.abs(clean - z["clean"]).max())}; print("clean check", res["clean_replay_max_abs_diff_vs_saved_self3"], round(time.time() - T0), flush=True)
ws = [z["w0"], z["w1"], z["w2"]]; pairs = [np.abs(ws[i] - ws[j]) for i, j in ((0, 1), (0, 2), (1, 2))]; told = np.maximum(np.median(pairs, axis=0), band)
res["tolerance_d_points_quantiles_5_50_95"] = [round(float(np.percentile(told, q)), 4) for q in (5, 50, 95)]; res["band_median_points"] = round(float(np.median(band)), 4)
ratio_d = lambda o: np.abs(o - clean) / told
res["clef_wordings_vs_clean_under_d"] = {f"w{k}": {"ratio_max": round(float(ratio_d(ws[k]).max()), 3), "share_outputs_within": round(float((ratio_d(ws[k]) <= 1).mean()), 3)} for k in range(3)}
# heads from the 8,545 state-text stories
rows8 = []; seen = set()
for f in ("test", "r3", "r5", "c1", "r1_local", "r1b"):
    for l in open("/workspace/data/clef-labels/" + f + ".jsonl"):
        try: r = json.loads(l)
        except Exception: continue
        if "P" in r and len(r["P"]) == 328 and r["id"] not in seen: seen.add(r["id"]); rows8.append(r)
assert not (seen & {r["id"] for r in rows}), "overlap with the 880"
keys = list(rows8[0]["P"]); Pm = np.array([[r["P"][k] for k in keys] for r in rows8], dtype=np.float32); Y = (Pm >= 0.5).astype(int); grp = np.array([r["id"] for r in rows8])
X8 = np.load("runs/pulse/t209/t209_embeddings.npy"); assert len(X8) == len(rows8)
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); texts = []
for r in rows:
    q = db.execute("select title, teaser from items where id=?", (r["id"],)).fetchone(); texts.append(((q[0] or "") + ". " + (q[1] or "")).strip())
from expert1_runtime import ExpertS
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); X880 = np.array([e.student(t) for t in texts], dtype=np.float32); print("embedded 880", round(time.time() - T0), flush=True)
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
mu = X8.mean(0); pca = PCA(256, random_state=0).fit(X8 - mu); Z8 = pca.transform(X8 - mu).astype(np.float32); sd = Z8.std(0) + 1e-6; Z8 /= sd; Z880 = (pca.transform(X880 - mu) / sd).astype(np.float32)
use = [j for j in range(len(keys)) if Y[:, j].sum() >= 10]; use = use[:N] if N else use; OOF = {}; H = {}
for jn, j in enumerate(use):
    y = Y[:, j]; oof = np.zeros(len(y))
    for a, b in GroupKFold(5).split(Z8, y, grp): oof[b] = LogisticRegression(C=0.3, max_iter=300).fit(Z8[a], y[a]).predict_proba(Z8[b])[:, 1]
    OOF[j] = oof; H[j] = LogisticRegression(C=0.3, max_iter=300).fit(Z8, y).predict_proba(Z880)[:, 1]
    if jn % 60 == 0: print("heads", jn, len(use), round(time.time() - T0), flush=True)
def fitline(s, yy, fp, fn):
    neg = np.sort(s[yy == 0])[::-1]; hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); lo = pos[int(np.floor(fn * len(pos)))]; return lo, hi
medpos = np.array([float(np.median(Pm[Y[:, j] == 1, j])) if Y[:, j].sum() else 0.9 for j in range(len(keys))], dtype=np.float32); akeys = [j for j, k in enumerate(keys) if k.startswith("a|")]
res["router"] = []
for mode, fp, fn in (("both", 0.0010, 0.05), ("both", 0.0001, 0.002), ("no_only", 0.0010, 0.002)):
    yes_ = np.zeros((len(rows), len(keys)), bool); no_ = np.zeros((len(rows), len(keys)), bool)
    for j in use:
        lo, hi = fitline(OOF[j], Y[:, j], fp, fn); no_[:, j] = H[j] < lo
        if mode == "both": yes_[:, j] = H[j] > hi
    rs = []
    for i, r in enumerate(rows):
        P = dict(r["P"])
        for j in akeys:
            if yes_[i, j]: P[keys[j]] = float(medpos[j])
            elif no_[i, j]: P[keys[j]] = 0.0
        rs.append((SN.readings_of(SN.presence(P)), stories[i]["w"]))
    o = SN.replay(rs); d = ratio_d(o); b_ = np.abs(o - clean) / band
    res["router"].append({"mode": mode, "fp_quota": fp, "miss_quota": fn, "answered_cell_share": round(float((yes_ | no_)[:, akeys].sum() / (len(rows) * len(keys))), 3), "ratio_d_max": round(float(d.max()), 3), "ratio_d_median": round(float(np.median(d)), 4), "share_outputs_within_d": round(float((d <= 1).mean()), 3), "passes_d": bool(d.max() <= 1), "bare_band_ratio_median": round(float(np.median(b_)), 3), "bare_band_share_within": round(float((b_ <= 1).mean()), 3)}); print(res["router"][-1], round(time.time() - T0), flush=True)
res["ratio_d_max_baseline_setting"] = res["router"][0]["ratio_d_max"]; res["seconds"] = round(time.time() - T0)
json.dump(res, open(OUT / ("t215_smoke.json" if N else "t215_router_tolerance_d.json"), "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "router"}))
