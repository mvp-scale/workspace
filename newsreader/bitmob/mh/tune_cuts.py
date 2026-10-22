"""Conditions operating point (D-0038 round 2). The engine fires a reading when an attribute's two-wordings mean is >= ATTR_MIN (.65). Round 1b: no reading fired (TPR 0), because trained
sigmoid outputs rarely reach .65. This tunes one cut per attribute on the TUNE rows (15% of training stories, not trained on; build_mh_data2.py writes them to TUNE_DIR) so that the model's
output crossing the cut means the same as the engine's .65: mh_common.calibrate_cond maps cut -> .65 (piecewise linear), applied inside predict(), so score_mh.py and engine_reader see it.
  CUDA_VISIBLE_DEVICES= models/embed-zs/.venv/bin/python newsreader/bitmob/mh/tune_cuts.py MODEL_DIR TUNE_DIR [--out MODEL_DIR/cuts.json] [--threads 8] [--max_rows N]
Method: positive attribute = label (Clef, or Jev translated to Clef's scale) mean of the two wordings >= .65. Per attribute the cut is set so at most f x (its negatives) are false fires; f is swept over a grid
and one f is chosen for all attributes. Reading level (what the engine uses, P-0017): a (dial, direction) fires if ANY of its attributes fires; positives/negatives are pooled over the 78 dial|direction keys;
(row, dial) pairs where the label has both directions (a conflict) are left out. F-0020 operating points: TPR >= .95 with FPR <= .0025, or TPR >= .90 with FPR <= .001. Choice rule: among f that reach an F-0020 point
take the lowest FPR; if none does, the highest TPR with FPR <= .001 (and the output says the point was NOT reached). Honesty check: the same selection on one half of the tune rows is scored on the other half (2 folds).
The numbers here are on tune rows (labels partly translated Jev): the contract score is only ever score_mh.py on the Clef-labelled frozen test."""
import os, sys, json, argparse, time
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", os.path.dirname(os.path.abspath(__file__))]
import numpy as np, torch
from mh_common import load, predict, ATTR_MIN

ap = argparse.ArgumentParser(); ap.add_argument("model"); ap.add_argument("tune"); ap.add_argument("--out"); ap.add_argument("--threads", type=int, default=8); ap.add_argument("--max_rows", type=int, default=0)
ap.add_argument("--clef_only", action="store_true", help="tune only on Clef-labelled tune rows (weight>=2)"); ap.add_argument("--raw_npz", help="skip the model: use saved raw predictions (testing)"); a = ap.parse_args()
torch.set_num_threads(a.threads); out = a.out or f"{a.model}/cuts.json"
K = json.load(open(f"{a.tune}/keys.json")); texts = json.load(open(f"{a.tune}/texts.json")); Z = np.load(f"{a.tune}/targets.npz"); Tc = Z["cond"]
if a.clef_only:
    keep = np.where(Z["w"] >= 2)[0]; texts = [texts[i] for i in keep]; Tc = Tc[keep]; print("clef-only tune rows:", len(keep), flush=True)
n = a.max_rows or len(texts); texts, Tc = texts[:n], Tc[:n]
if a.raw_npz: p = np.load(a.raw_npz)["cond"][:n]
else:
    model, tok, _ = load(a.model); model.cond_cuts = None; t0 = time.time(); p = predict(model, tok, texts)["cond"]; print(f"predicted {n} tune rows in {time.time() - t0:.0f}s", flush=True)
    np.savez_compressed(os.path.join(os.path.dirname(out), "tune_raw_cond.npz"), cond=p) if os.path.isdir(os.path.dirname(out)) else None
COND = K["cond"]; grp = {}
for j, k in enumerate(COND): d, dr, i = k.split("|"); grp.setdefault((d, dr), []).append(j)
G = sorted(grp); pos_attr = Tc >= ATTR_MIN
lab = np.stack([pos_attr[:, grp[g]].any(1) for g in G], 1)      # (N, 78) reading label
dials = sorted({g[0] for g in G}); conflict = np.zeros_like(lab)
for d in dials:
    up, dn = G.index((d, "up")), G.index((d, "down")); both = lab[:, up] & lab[:, dn]; conflict[:, up] |= both; conflict[:, dn] |= both
valid = ~conflict


def cuts_for(f, rows):
    c = np.full(len(COND), 0.5, np.float32)
    for j in range(len(COND)):
        neg = np.sort(p[rows][~pos_attr[rows][:, j], j])[::-1]; k = int(np.floor(f * len(neg)))
        c[j] = max(0.05, float(neg[k]) + 1e-4) if k < len(neg) and len(neg) else 0.05
    return np.clip(c, 0.05, 0.99)


def evaluate(c, rows):
    fire = np.stack([(p[rows][:, grp[g]] >= c[grp[g]]).any(1) for g in G], 1); L = lab[rows]; V = valid[rows]
    tp = int((fire & L & V).sum()); fn = int((~fire & L & V).sum()); fp = int((fire & ~L & V).sum()); tn = int((~fire & ~L & V).sum())
    return {"TPR": tp / max(tp + fn, 1), "FPR": fp / max(fp + tn, 1), "tp": tp, "fn": fn, "fp": fp, "tn": tn}


def ok(r): return (r["TPR"] >= .95 and r["FPR"] <= .0025) or (r["TPR"] >= .90 and r["FPR"] <= .001)


def choose(rows):
    best = None
    for f in np.geomspace(1e-5, 0.05, 40):
        c = cuts_for(f, rows); r = evaluate(c, rows); r["f"] = float(f); r["reached"] = ok(r)
        if best is None: best = (c, r)
        cur = best[1]
        if r["reached"] and (not cur["reached"] or r["FPR"] < cur["FPR"] or (r["FPR"] == cur["FPR"] and r["TPR"] > cur["TPR"])): best = (c, r)
        elif not cur["reached"] and not r["reached"] and r["FPR"] <= .001 and (cur["FPR"] > .001 or r["TPR"] > cur["TPR"]): best = (c, r)
    return best


allr = np.arange(len(texts)); c, r = choose(allr)
h = {}
for name, (tr, te) in {"fold_even_to_odd": (allr[0::2], allr[1::2]), "fold_odd_to_even": (allr[1::2], allr[0::2])}.items():
    c2, r2 = choose(tr); e = evaluate(c2, te); h[name] = {"f": r2["f"], "tuned_TPR": round(r2["TPR"], 4), "tuned_FPR": round(r2["FPR"], 5), "heldout_TPR": round(e["TPR"], 4), "heldout_FPR": round(e["FPR"], 5), "heldout_reached_F0020": bool(ok(e))}
res = {"cond_cuts": [round(float(x), 5) for x in c], "attr_min": ATTR_MIN, "n_tune": len(texts), "positives_readings": int((lab & valid).sum()), "chosen_f_per_attribute": r["f"],
       "on_tune": {"TPR": round(r["TPR"], 4), "FPR": round(r["FPR"], 5), "reached_F0020": bool(r["reached"])}, "heldout_halves": h,
       "note": "tuned on tune rows (partly translated-Jev labels); contract numbers come only from score_mh.py on the Clef-labelled frozen test", "made": time.strftime("%FT%T")}
json.dump(res, open(out, "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "cond_cuts"}, indent=1)[:1500])
