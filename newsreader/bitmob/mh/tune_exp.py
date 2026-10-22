"""Expected-impact operating point (D-0038 round 4, F-0107 diagnosis). The model's e|dial|up/down outputs rank well against Clef's raw answers (mean AUC .86) but sit below the engine's EXPECT_MIN .5, so the
engine's expected() returns an empty set for 21% of stories where Clef has some. One cut per key, tuned on the TUNE rows (never the frozen test) to maximise F1 of (output >= cut) against (target >= .5) over rows where
that key was asked; mh_common.predict then maps cut -> .5. Merges "exp_cuts" into MODEL_DIR/cuts.json (keeps cond_cuts).
  CUDA_VISIBLE_DEVICES= models/embed-zs/.venv/bin/python newsreader/bitmob/mh/tune_exp.py MODEL_DIR TUNE_DIR [--min_pos 8]"""
import os, sys, json, argparse
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", os.path.dirname(os.path.abspath(__file__))]
import numpy as np, torch
from mh_common import load, predict
ap = argparse.ArgumentParser(); ap.add_argument("model"); ap.add_argument("tune"); ap.add_argument("--min_pos", type=int, default=8); ap.add_argument("--threads", type=int, default=8); a = ap.parse_args()
torch.set_num_threads(a.threads); K = json.load(open(f"{a.tune}/keys.json")); texts = json.load(open(f"{a.tune}/texts.json")); Z = np.load(f"{a.tune}/targets.npz"); T, M = Z["expected"], Z["expected_mask"]
model, tok, _ = load(a.model); model.exp_cuts = None; p = predict(model, tok, texts)["expected"]; cuts = np.full(T.shape[1], 0.5, np.float32); rep = {}
for j, k in enumerate(K["expected"]):
    m = M[:, j] > 0; y = T[m, j] >= .5; s = p[m, j]
    if y.sum() < a.min_pos: continue
    best = (0.0, 0.5)
    for c in np.linspace(0.05, 0.9, 86):
        f = s >= c; tp = (f & y).sum(); f1 = 2 * tp / max(f.sum() + y.sum(), 1)
        if f1 > best[0]: best = (float(f1), float(c))
    cuts[j] = best[1]; rep[k] = {"n": int(m.sum()), "pos": int(y.sum()), "cut": round(best[1], 3), "f1": round(best[0], 3)}
# exact-set criterion (what P-0020 scores): one global cut swept, predicted set = engine rule on calibrated outputs vs target set from the raw targets, on rows where both wordings of the dial were asked
ex = K["expected"]; ups = [j for j, k in enumerate(ex) if k.endswith("|up")]; dn = {j: ex.index(ex[j][:-2] + "down") for j in ups}
def setmatch(cutvec):
    ok = 0; rows = np.where((M[:, ups] > 0).any(1))[0]
    for n in rows:
        pr, tr = [], []
        for j in ups:
            if M[n, j] <= 0: continue
            q = dn[j]; c = cutvec
            pu = p[n, j] / (2 * c[j]) if p[n, j] <= c[j] else .5 + .5 * (p[n, j] - c[j]) / (1 - c[j]); pd = p[n, q] / (2 * c[q]) if p[n, q] <= c[q] else .5 + .5 * (p[n, q] - c[q]) / (1 - c[q])
            if max(pu, pd) >= .5 and abs(pu - pd) > .05: pr.append((abs(pu - pd), ex[j], pu > pd))
            tu, td = T[n, j], T[n, q]
            if max(tu, td) >= .5 and abs(tu - td) > .05: tr.append((abs(tu - td), ex[j], tu > td))
        pr = {(k[:-3], u) for _, k, u in sorted(pr, reverse=True)[:4]}; tr = {(k[:-3], u) for _, k, u in sorted(tr, reverse=True)[:4]}; ok += pr == tr
    return ok / max(len(rows), 1)
grid = [(g, setmatch(np.full(T.shape[1], g, np.float32))) for g in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7)]; gbest = max(grid, key=lambda x: x[1]); print("global cut sweep (set match on tune rows)", [(g, round(v, 4)) for g, v in grid], flush=True)
if gbest[0] != 0.5 or True: cuts = np.full(T.shape[1], gbest[0], np.float32); rep["_global"] = {"cut": gbest[0], "set_match_tune": round(gbest[1], 4)}
cp = f"{a.model}/cuts.json"; cj = json.load(open(cp)) if os.path.exists(cp) else {}; cj["exp_cuts"] = [round(float(x), 4) for x in cuts]; cj["exp_cuts_report"] = {"keys_tuned": len(rep), "median_cut": round(float(np.median([v["cut"] for v in rep.values()])), 3), "tune_rows": len(texts)}
json.dump(cj, open(cp, "w"), indent=1); print(json.dumps(cj["exp_cuts_report"]))
