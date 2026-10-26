"""Ensemble of conditions readers (mean logit), same rules as score_b1.py. Usage: score_ens.py OUT.txt NAME=DIR[:attn] ..."""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(16)
import classify as C
import mh_common_t1 as M
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"; OUT = sys.argv[1]; specs = sys.argv[2:]; lines = []
def log(s): print(s, flush=True); lines.append(s)
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]; tt = json.load(open(f"{TUNE}/texts.json")); Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
K0 = None; HT, HS = {}, {}
for sp in specs:
    name, d = sp.split("="); attn = d.endswith(":attn"); d = d.replace(":attn", "")
    if attn: model, tok, K = M.load_attn(d)
    else: model, tok, K = M.load(d); model.cond_cuts = None; model.reading_cuts = None
    K0 = K0 or K; lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    HT[name] = lg(np.asarray(M.predict(model, tok, [tt[i] for i in keep])["cond"])); HS[name] = lg(np.asarray(M.predict(model, tok, [r["state_text"] for r in T])["cond"])); print("scored", name, flush=True)
np.savez(OUT.replace(".txt", "_scores.npz"), **{f"T_{k}": v for k, v in HT.items()}, **{f"S_{k}": v for k, v in HS.items()})
A = [k.split("|") for k in K0["cond"]]; ck = lambda P: np.array([(P[f"a|{d}|{dr}|{i}|0"] + P[f"a|{d}|{dr}|{i}|1"]) / 2 for d, dr, i in A]); trig = lambda Y: Y >= C.ATTR_MIN
YT = Z["cond"][keep]; YS = np.stack([ck(r["P"]) for r in T])
def cut_for(S, Y, fpr): neg = np.sort(S[~trig(Y)])[::-1]; return neg[max(int(fpr * len(neg)), 1) - 1]
keys = lambda rd: {(x["dial"], x["direction"]) for x in rd["readings"] if x["direction"] != "conflict"}
def evaluate(label, ST, SS):
    c = cut_for(ST, YT, 0.0005); cell = ((SS >= c) & trig(YS)).sum() / trig(YS).sum(); tp = fp = pos = neg = 0
    for n, rr in enumerate(T):
        P = dict(rr["P"])
        for j, (d, dr, i) in enumerate(A): P[f"a|{d}|{dr}|{i}|0"] = P[f"a|{d}|{dr}|{i}|1"] = float(SS[n, j] - c + C.ATTR_MIN)
        m = keys(C.read(P)); b = keys(rr["read"]); tp += len(m & b); fp += len(m - b); pos += len(b); neg += 78 - len(b)
    log(f"{label}: cell caught {cell:.1%}; ENGINE READINGS caught {tp/pos:.1%} ({tp}/{pos}), false alarms {fp/neg:.4%}")
for k in HT: evaluate(k, HT[k], HS[k])
evaluate("ENSEMBLE mean logit of " + "+".join(HT), np.mean(list(HT.values()), 0), np.mean(list(HS.values()), 0))
open(OUT, "w").write("\n".join(lines) + "\n")
