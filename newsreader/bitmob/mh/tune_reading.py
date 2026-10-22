"""Reading-head operating point (round 5). The 'reading' head (78 dial|direction outputs) is trained directly on reading-level labels; at serving mh_common.apply_reading_floor raises attribute 0 of a key to
calibrate_pivot(reading, cut -> .65) so classify.read() fires it. One cut per key is tuned on the TUNE rows (never the frozen test): per key the cut keeps at most f x (its negatives) false fires, f swept over a grid and one f
chosen for all keys by the F-0020 rule used in tune_cuts.py (lowest FPR reaching TPR>=.95@FPR<=.0025 or TPR>=.9@FPR<=.001, else max TPR with FPR<=.001; the output says if the point was NOT reached). Rows with the key masked
(conflicts) are left out. Reports a 2-fold held-out check, and the COMBINED fire rate (reading head OR the calibrated attribute heads, as served) when cond_cuts exist. Merges 'reading_cuts' into MODEL_DIR/cuts.json (run tune_cuts.py FIRST: it rewrites cuts.json).
  CUDA_VISIBLE_DEVICES= models/embed-zs/.venv/bin/python newsreader/bitmob/mh/tune_reading.py MODEL_DIR TUNE_DIR [--clef_only] [--max_rows N]"""
import os, sys, json, argparse
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", os.path.dirname(os.path.abspath(__file__))]
import numpy as np, torch
from mh_common import load, predict, calibrate_cond, reading_first_attr, ATTR_MIN
ap = argparse.ArgumentParser(); ap.add_argument("model"); ap.add_argument("tune"); ap.add_argument("--clef_only", action="store_true"); ap.add_argument("--max_rows", type=int, default=0); ap.add_argument("--threads", type=int, default=8); a = ap.parse_args()
torch.set_num_threads(a.threads); K = json.load(open(f"{a.tune}/keys.json")); texts = json.load(open(f"{a.tune}/texts.json")); Z = np.load(f"{a.tune}/targets.npz")
assert "reading" in K, "tune set has no reading labels (build with the round-5 build_mh_data2.py)"
rows = np.where(Z["w"] >= 2)[0] if a.clef_only else np.arange(len(texts)); rows = rows[:a.max_rows] if a.max_rows else rows
texts = [texts[i] for i in rows]; Y = Z["reading"][rows] > 0.5; V = Z["reading_mask"][rows] > 0.5; Tc = Z["cond"][rows]
model, tok, _ = load(a.model); model.reading_cuts = None; H = predict(model, tok, texts); assert "reading" in H, "model has no reading head"; p = H["reading"]; RK = K["reading"]; nk = len(RK)
cond_fire = None
if model.cond_cuts is not None:      # attribute heads as served (calibrated, engine bar .65): any attribute of the key >= .65
    grp = {}
    for j, k in enumerate(K["cond"]): d, dr, i = k.split("|"); grp.setdefault(f"{d}|{dr}", []).append(j)
    cond_fire = np.stack([(H["cond"][:, grp[k]] >= ATTR_MIN).any(1) for k in RK], 1)
def cuts_for(f, rs):
    c = np.full(nk, 0.5, np.float32)
    for j in range(nk):
        neg = np.sort(p[rs][~Y[rs][:, j] & V[rs][:, j], j])[::-1]; k = int(np.floor(f * len(neg))); c[j] = max(0.02, float(neg[k]) + 1e-4) if k < len(neg) and len(neg) else 0.5
    return np.clip(c, 0.02, 0.99)
def evaluate(c, rs, with_cond=False):
    fire = p[rs] >= c[None, :]
    if with_cond and cond_fire is not None: fire = fire | cond_fire[rs]
    L, Vv = Y[rs], V[rs]; tp = int((fire & L & Vv).sum()); fn = int((~fire & L & Vv).sum()); fp = int((fire & ~L & Vv).sum()); tn = int((~fire & ~L & Vv).sum()); return {"TPR": tp / max(tp + fn, 1), "FPR": fp / max(fp + tn, 1), "tp": tp, "fn": fn, "fp": fp}
def ok(r): return (r["TPR"] >= .95 and r["FPR"] <= .0025) or (r["TPR"] >= .90 and r["FPR"] <= .001)
def choose(rs):
    best = None
    for f in np.geomspace(1e-5, 0.05, 40):
        c = cuts_for(f, rs); r = evaluate(c, rs); r["f"] = float(f); r["reached"] = ok(r)
        if best is None: best = (c, r); continue
        cur = best[1]
        if r["reached"] and (not cur["reached"] or r["FPR"] < cur["FPR"] or (r["FPR"] == cur["FPR"] and r["TPR"] > cur["TPR"])): best = (c, r)
        elif not cur["reached"] and not r["reached"] and r["FPR"] <= .001 and (cur["FPR"] > .001 or r["TPR"] > cur["TPR"]): best = (c, r)
    return best
allr = np.arange(len(texts)); c, r = choose(allr); h = {}
for name, (tr, te) in {"fold_even_to_odd": (allr[0::2], allr[1::2]), "fold_odd_to_even": (allr[1::2], allr[0::2])}.items():
    c2, r2 = choose(tr); e = evaluate(c2, te); h[name] = {"f": r2["f"], "tuned_TPR": round(r2["TPR"], 4), "tuned_FPR": round(r2["FPR"], 5), "heldout_TPR": round(e["TPR"], 4), "heldout_FPR": round(e["FPR"], 5), "heldout_reached_F0020": bool(ok(e))}
cb = evaluate(c, allr, with_cond=True)
cp = f"{a.model}/cuts.json"; cj = json.load(open(cp)) if os.path.exists(cp) else {}; cj["reading_cuts"] = [round(float(x), 5) for x in c]
cj["reading_cuts_report"] = {"rows": len(texts), "positives": int((Y & V).sum()), "chosen_f": r["f"], "on_tune_reading_only": {"TPR": round(r["TPR"], 4), "FPR": round(r["FPR"], 5), "reached_F0020": bool(r["reached"])},
                            "on_tune_combined_with_attribute_heads": {"TPR": round(cb["TPR"], 4), "FPR": round(cb["FPR"], 5)} if cond_fire is not None else None, "heldout_halves": h,
                            "note": "tuned on tune rows (partly translated-Jev labels); contract numbers come only from score_mh.py on the Clef-labelled frozen test"}
json.dump(cj, open(cp, "w"), indent=1); print(json.dumps(cj["reading_cuts_report"], indent=1))
