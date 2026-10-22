"""Gate operating point (round 4): classify.read() gate = (happened>=.5 or announced>=.5) and opinion<.5 and recent>=.3. Per-question cuts for g|happened, g|announced, g|opinion (mapped to .5) and x|recent (mapped to .3),
chosen by coordinate descent on TUNE rows to maximise agreement of the rule's gate with the labels' gate (labels = targets on those rows; Clef-only rows when --clef_only). Never the frozen test. Writes gate_cuts into MODEL_DIR/cuts.json.
  python tune_gate.py MODEL_DIR TUNE_DIR [--clef_only]"""
import os, sys, json, argparse
os.environ["CUDA_VISIBLE_DEVICES"] = ""; sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", os.path.dirname(os.path.abspath(__file__))]
import numpy as np, torch
from mh_common import load, predict
ap = argparse.ArgumentParser(); ap.add_argument("model"); ap.add_argument("tune"); ap.add_argument("--clef_only", action="store_true"); a = ap.parse_args(); torch.set_num_threads(8)
K = json.load(open(f"{a.tune}/keys.json")); texts = json.load(open(f"{a.tune}/texts.json")); Z = np.load(f"{a.tune}/targets.npz"); T = Z["gate"]; G = K["gate"]
rows = np.where(Z["w"] >= 2)[0] if a.clef_only else np.arange(len(texts)); texts = [texts[i] for i in rows]; T = T[rows]
model, tok, _ = load(a.model); model.gate_cuts = None; p = predict(model, tok, texts)["gate"]; ix = {k: i for i, k in enumerate(G)}
def gate(v): return ((v[:, ix["g|happened"]] >= .5) | (v[:, ix["g|announced"]] >= .5)) & (v[:, ix["g|opinion"]] < .5) & (v[:, ix["x|recent"]] >= .3)
def cal(pv, c, pivot): return np.where(pv <= c, pivot * pv / c, pivot + (1 - pivot) * (pv - c) / (1 - c))
y = gate(T); cuts = {"g|happened": .5, "g|announced": .5, "g|opinion": .5, "x|recent": .3}; piv = dict(cuts)
def apply(cs):
    q = p.copy()
    for k, c in cs.items(): q[:, ix[k]] = cal(p[:, ix[k]], c, piv[k])
    return q
best = float((gate(apply(cuts)) == y).mean()); base = best
for it in range(3):
    for k in cuts:
        for c in np.linspace(.05, .9, 35):
            t = dict(cuts); t[k] = float(c); s = float((gate(apply(t)) == y).mean())
            if s > best + 1e-6: best, cuts = s, t
cp = f"{a.model}/cuts.json"; cj = json.load(open(cp)) if os.path.exists(cp) else {}; cj["gate_cuts"] = {k: round(v, 3) for k, v in cuts.items()}; cj["gate_cuts_pivots"] = piv
json.dump(cj, open(cp, "w"), indent=1); print(json.dumps({"rows": len(texts), "agree_before": round(base, 4), "agree_after": round(best, 4), "cuts": cj["gate_cuts"]}))
