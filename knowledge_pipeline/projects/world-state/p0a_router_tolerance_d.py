"""P0a (ledger T149): re-score the per-key router and the two Clef-vs-Clef controls against tolerance (d) on the 880 Step 1 stories.
Engine arithmetic = t211 (sensitivity.presence/readings_of/replay, rules_v2, no engine noise). Router = t211: per-key logistic heads on PCA(256) of the v6b-student embedding, fit on the 8,545 state-text stories
(no overlap with the 880); a head's yes (score above the line at false-positive quota FPQ) sets the key to its median positive value, a no (below the line at miss quota 0.05) sets 0, otherwise Clef's own reading is kept; all-CPU variant sets unsure keys to 0.
Text seen: CPU reader = title + teaser of the story (queue.sqlite); Clef reference reading = the article text (clef-q4km.jsonl P, two wordings averaged by the engine presence rule).
Tolerance (d): ONE shared function, copied from probes/world-engine/sensitivity_report.py:150-152.
Run (from projects/world-state): CUDA_VISIBLE_DEVICES= WORLD_GPU=0 WE_RULES=rules_v2 /workspace/models/embed-zs/.venv/bin/python -u p0a_router_tolerance_d.py"""
import os, sys, json, time, pathlib, sqlite3, numpy as np
os.environ.setdefault("WORLD_GPU", "0"); os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["CUDA_VISIBLE_DEVICES"] = ""
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/p0a")); OUT.mkdir(parents=True, exist_ok=True); T0 = time.time(); B = int(os.environ.get("B", 100)); TLIM = float(os.environ.get("TLIM", 1500))
sys.path.insert(0, "/workspace/probes/world-engine"); sys.path.insert(0, "."); import sensitivity as SN
def tolerance_d(s3, band):   # copied exactly from sensitivity_report.py:150-152
    ws = [s3["w0"], s3["w1"], s3["w2"]]; pairs = [np.abs(ws[i] - ws[j]) for i, j in ((0, 1), (0, 2), (1, 2))]
    return np.maximum(np.median(pairs, axis=0), band)
LAB = "/workspace/data/newsreader/labels/clef-q4km.jsonl"; w3ids = {json.loads(l)["id"] for l in open(LAB.replace(".jsonl", "-w3.jsonl"))}
all_rows = [json.loads(l) for l in open(LAB)]; keep = [i for i, r in enumerate(all_rows) if r["id"] in w3ids]; assert len(keep) == 880
stories_all = SN.load_stories(); stories = [stories_all[i] for i in keep]; rows = [all_rows[i] for i in keep]; assert [s["id"] for s in stories] == [r["id"] for r in rows]
SN.G["stories"] = stories; SN.G["med"] = SN.medians(stories); SN.build()
z = np.load("/workspace/data/step1/self3.npz"); band = np.load("/workspace/data/step1/noise.npz")["band"]; told = tolerance_d(z, band)
bj = json.load(open("/workspace/data/step1/budget.json")); print("budget keys", list(bj)[:12])
clean = SN.replay(SN.clean_readings(stories)); res = {"stories": 880, "clean_vs_saved_self3_max_abs": float(np.abs(clean - z["clean"]).max()), "tolerance_d_quantiles_5_50_95": [round(float(np.percentile(told, q)), 4) for q in (5, 50, 95)], "band_median": round(float(np.median(band)), 4), "n_outputs": int(told.size)}; print(res, flush=True)
# heads
rows8 = []; seen = set()
for f in ("test", "r3", "r5", "c1", "r1_local", "r1b"):
    for l in open("/workspace/data/clef-labels/" + f + ".jsonl"):
        try: r = json.loads(l)
        except Exception: continue
        if "P" in r and len(r["P"]) == 328 and r["id"] not in seen: seen.add(r["id"]); rows8.append(r)
assert not (seen & {r["id"] for r in rows}); keys = list(rows8[0]["P"]); Pm = np.array([[r["P"][k] for k in keys] for r in rows8], dtype=np.float32); Y = (Pm >= 0.5).astype(int); grp = np.array([r["id"] for r in rows8])
X8 = np.load("runs/pulse/t209/t209_embeddings.npy"); assert len(X8) == len(rows8)
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); texts = []
for r in rows: q = db.execute("select title, teaser from items where id=?", (r["id"],)).fetchone(); texts.append(((q[0] or "") + ". " + (q[1] or "")).strip())
from expert1_runtime import ExpertS
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); X880 = np.array([e.student(t) for t in texts], dtype=np.float32); print("embedded", round(time.time() - T0), flush=True)
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
mu = X8.mean(0); pca = PCA(256, random_state=0).fit(X8 - mu); Z8 = pca.transform(X8 - mu).astype(np.float32); sd = Z8.std(0) + 1e-6; Z8 /= sd; Z880 = (pca.transform(X880 - mu) / sd).astype(np.float32)
use = [j for j in range(len(keys)) if Y[:, j].sum() >= 10]; OOF = {}; H = {}
for jn, j in enumerate(use):
    y = Y[:, j]; oof = np.zeros(len(y))
    for a, b in GroupKFold(5).split(Z8, y, grp): oof[b] = LogisticRegression(C=0.3, max_iter=300).fit(Z8[a], y[a]).predict_proba(Z8[b])[:, 1]
    OOF[j] = oof; H[j] = LogisticRegression(C=0.3, max_iter=300).fit(Z8, y).predict_proba(Z880)[:, 1]
    if jn % 60 == 0: print("heads", jn, len(use), round(time.time() - T0), flush=True)
def fitline(s, yy, fp, fn):
    neg = np.sort(s[yy == 0])[::-1]; hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); lo = pos[int(np.floor(fn * len(pos)))]; return lo, hi
medpos = np.array([float(np.median(Pm[Y[:, j] == 1, j])) if Y[:, j].sum() else 0.9 for j in range(len(keys))], dtype=np.float32); akeys = [j for j, k in enumerate(keys) if k.startswith("a|")]
FPQ = 0.0010; yes_ = np.zeros((880, len(keys)), bool); no_ = np.zeros((880, len(keys)), bool)
for j in use:
    lo, hi = fitline(OOF[j], Y[:, j], FPQ, 0.05); no_[:, j] = H[j] < lo; yes_[:, j] = H[j] > hi
def build_P(i, mode):
    P = dict(rows[i]["P"])
    for j in akeys:
        k = keys[j]
        if yes_[i, j]: P[k] = float(medpos[j])
        elif no_[i, j]: P[k] = 0.0
        elif mode == "cpu_only": P[k] = 0.0
    return P
# per-story readings for each variant (so bootstrap can resample stories)
V = {"router": [SN.readings_of(SN.presence(build_P(i, "router"))) for i in range(880)], "cpu_only": [SN.readings_of(SN.presence(build_P(i, "cpu_only"))) for i in range(880)],
     "clef_w0": [SN.readings_of(SN.presence(rows[i]["P"], wording=0)) for i in range(880)], "clef_w1": [SN.readings_of(SN.presence(rows[i]["P"], wording=1)) for i in range(880)], "clean": SN.clean_readings(stories) and [SN.readings_of(s["keys"]) for s in stories]}
W = [s["w"] for s in stories]
rep = lambda name, idx: SN.replay([(V[name][i], W[i]) for i in idx])
full = np.arange(880); O = {n: rep(n, full) for n in V}; print("replays done", round(time.time() - T0), "clean check", float(np.abs(O["clean"] - clean).max()), flush=True)
comp = {"router_vs_clean": ("router", "clean"), "cpu_only_vs_clean": ("cpu_only", "clean"), "clef_w0_vs_w1": ("clef_w0", "clef_w1"), "clef_w0_vs_clean_twowording": ("clef_w0", "clean"), "clef_w1_vs_clean_twowording": ("clef_w1", "clean")}
stat = lambda a, b: (lambda d: (float((d <= 1).mean()), float(np.median(d)), float(d.max())))(np.abs(a - b) / told)
res["answered_cell_share_router"] = round(float((yes_ | no_)[:, akeys].sum() / (880 * len(keys))), 3); res["fired_attr_keys_per_story_clef"] = round(sum(len(s["keys"]) for s in stories) / 880, 3)
for c, (a, b) in comp.items(): s = stat(O[a], O[b]); res[c] = {"share_inside_d": round(s[0], 4), "median_ratio_to_d": round(s[1], 4), "max_ratio": round(s[2], 3), "share_inside_bare_band_for_reference": round(float((np.abs(O[a] - O[b]) / band <= 1).mean()), 4)}
print(json.dumps(res, indent=1), flush=True); json.dump(res, open(OUT / "p0a_point.json", "w"), indent=1)
# bootstrap over stories: resample stories (sorted order kept), replay all variants on the resample, same fixed tolerance (d)
rng = np.random.RandomState(21); boots = {c: [] for c in comp}; nb = 0; tb = time.time()
for b in range(B):
    if b == 1: per = time.time() - tb; print("one bootstrap sample took", round(per), "s", flush=True)
    if b >= 1 and (time.time() - T0) + per > TLIM: print("time guard, stopping at", b); break
    idx = np.sort(rng.randint(0, 880, 880)); Ob = {n: rep(n, idx) for n in V}
    for c, (a, bb) in comp.items(): boots[c].append(stat(Ob[a], Ob[bb])[:2])
    nb += 1
    if nb % 10 == 0: print("boot", nb, round(time.time() - T0), flush=True)
res["bootstrap_samples"] = nb
for c in comp:
    arr = np.array(boots[c]); res[c]["share_inside_d_ci95"] = [round(float(np.percentile(arr[:, 0], 2.5)), 4), round(float(np.percentile(arr[:, 0], 97.5)), 4)]; res[c]["median_ratio_ci95"] = [round(float(np.percentile(arr[:, 1], 2.5)), 4), round(float(np.percentile(arr[:, 1], 97.5)), 4)]
res["seconds"] = round(time.time() - T0); json.dump(res, open(OUT / "p0a_router_tolerance_d.json", "w"), indent=1); print(json.dumps(res, indent=1))
