#!/usr/bin/env python3
"""Ask each yes/no question from several fixed angles (probes/angles.json) and measure what combining them buys.

Per angle a and item: s_a = cos(q_a, o_yes_a) - cos(q_a, o_no_a), sign-flipped for the 'opposite' angle so that
positive always means the original question's yes. Then, step by step:

  bias      contextual calibration (Zhao et al. 2021): subtract the angle's score for content-free states
            ("N/A", "", "[MASK]"); no labels
  scale     divide each angle by its spread over the items (no centring, so no base-rate assumption); no labels
  combine   question+opposite, all five angles averaged (no labels), or weighted by a 5-fold logistic fit (labels)
  agree     answer only when at least 4 of the 5 bias-corrected angles agree; otherwise say unsure

Writes data/embed-zs/latent/<model>/angles_<set>.json for the Latent lab.

    python probes/latent_angles.py --model Qwen/Qwen3-Embedding-4B
"""
import argparse, json
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

PROBES, OUT = Path("/workspace/probes/v2"), Path("/workspace/data/embed-zs/latent")
ANGLES = json.load(open(Path(__file__).with_name("angles.json")))
ORDER = ["original", "opposite", "rephrase1", "rephrase2", "adjacent"]
FREE = ["N/A", "", "[MASK]"]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--model", default="Qwen/Qwen3-Embedding-4B"); a = ap.parse_args()
    m = SentenceTransformer(a.model, device="cuda", model_kwargs={"torch_dtype": torch.bfloat16})
    enc = lambda xs: m.encode(xs, batch_size=16, normalize_embeddings=True).astype(np.float32)
    for s, angles in ANGLES.items():
        if s.startswith("_"): continue
        items = [json.loads(l) for l in open(PROBES / f"{s}.jsonl")]
        y = np.array([i["expected"] == "yes" for i in items]); n = len(items)
        raw, cor = {}, {}
        for name in ORDER:
            instr, yes, no = angles[name]; sign = -1.0 if name == "opposite" else 1.0
            Q = enc([f"Instruct: {instr}\nQuery:{i['state']}" for i in items]); Oy, On = enc([yes, no])
            C = enc([f"Instruct: {instr}\nQuery:{t}" for t in FREE])
            raw[name] = sign * (Q @ Oy - Q @ On)
            cor[name] = raw[name] - sign * float(np.mean(C @ Oy - C @ On))
        z = {k: v / (v.std() or 1) for k, v in cor.items()}
        Z = np.stack([z[k] for k in ORDER], 1)
        acc = lambda pred: float(np.mean(pred == y))
        pair = (z["original"] + z["opposite"]) / 2; allm = Z.mean(1)
        stack = np.zeros(n)
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=0).split(Z, y):
            stack[te] = LogisticRegression(C=1.0).fit(Z[tr], y[tr]).decision_function(Z[te])
        votes = (Z > 0).sum(1); agree = (votes >= 4) | (votes <= 1)
        methods = {
            "one_raw": acc(raw["original"] > 0), "one_bias": acc(cor["original"] > 0), "pair": acc(pair > 0),
            "all5": acc(allm > 0), "stack": acc(stack > 0),
            "agree_coverage": float(agree.mean()), "agree_acc": float(np.mean(((allm > 0) == y)[agree])) if agree.any() else None,
            "opposite_consistency": float(np.mean((cor["original"] > 0) == (cor["opposite"] > 0)))}
        per_angle = {k: {"raw": acc(raw[k] > 0), "bias": acc(cor[k] > 0)} for k in ORDER}
        corr = np.corrcoef(Z.T).round(3).tolist()
        out = {"set": s, "n": n, "angles": {k: {"instruction": angles[k][0], "yes": angles[k][1], "no": angles[k][2]} for k in ORDER},
               "order": ORDER, "methods": methods, "per_angle": per_angle, "corr": corr,
               "items": [{"id": it["id"], "expected": it["expected"], "z": [round(float(v), 3) for v in Z[i]],
                          "raw_original": round(float(raw["original"][i]), 5), "all5": round(float(allm[i]), 3), "stack": round(float(stack[i]), 3)}
                         for i, it in enumerate(items)]}
        d = OUT / a.model.split("/")[-1]; d.mkdir(parents=True, exist_ok=True)
        json.dump(out, open(d / f"angles_{s}.json", "w"), separators=(",", ":"))
        print(f"{s:<24} one {methods['one_raw']:.2f}  +bias {methods['one_bias']:.2f}  +opposite {methods['pair']:.2f}  all5 {methods['all5']:.2f}  "
              f"learned-trust {methods['stack']:.2f}  | agree on {methods['agree_coverage']:.0%}: {methods['agree_acc']:.2f}  | orig/opp agree {methods['opposite_consistency']:.0%}", flush=True)


if __name__ == "__main__":
    main()
