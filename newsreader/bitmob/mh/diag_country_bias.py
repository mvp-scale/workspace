import os, sys, json
os.environ["CUDA_VISIBLE_DEVICES"] = ""; sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import numpy as np, torch, classify as C
from mh_common import load, predict
torch.set_num_threads(8); M, TUNE, TEST = sys.argv[1:4]; model, tok, K = load(M); REG, CTY = K["region"], K["country"]; rows = C._country_rows(); regs = {x["id"]: x["region"] for x in rows}
def run(texts):
    H = predict(model, tok, texts); return H["region"], H["country"]
def acc(Hr, Hc, truth, b):
    ok = 0; gi = REG.index("GLOBAL")
    for n, t in enumerate(truth):
        pr = Hr[n].copy(); pr[gi] *= b; g = REG[int(pr.argmax())]
        if g == "GLOBAL": p = "global"
        else:
            cand = [x["id"] for x in rows if x["region"] == g] + ["other_here"]; pc = dict(zip(CTY, Hc[n])); c = max(cand, key=lambda x: pc[x]); p = "global" if c == "other_here" else c
        ok += p == t
    return ok / len(truth)
Z = np.load(f"{TUNE}/targets.npz"); texts = json.load(open(f"{TUNE}/texts.json")); keep = np.where(Z["w"] >= 2)[0]; ct = [CTY[int(Z["country"][i].argmax())] for i in keep]; ct = ["global" if c in ("global", "other_here") else c for c in ct]
Hr, Hc = run([texts[i] for i in keep]); R = [json.loads(l) for l in open(TEST)]; Tr, Tc = run([r["state_text"] for r in R]); tt = [r["country"] for r in R]
for b in (0.5, 0.7, 1, 1.5, 2, 3): print("global x", b, "clef tune rows", round(acc(Hr, Hc, ct, b), 3), "| test", round(acc(Tr, Tc, tt, b), 4))
