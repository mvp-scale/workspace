"""Per-attribute cuts vs one global cut (cell level). Cuts chosen on the tune rows only. Usage: diag_attrcut.py MODEL_DIR OUT.txt"""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(16)
import classify as C
from mh_common import load, predict
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"; MD, OUT = sys.argv[1:3]; lines = []
def log(s): print(s, flush=True); lines.append(s)
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]; tt = json.load(open(f"{TUNE}/texts.json")); Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
model, tok, K = load(MD); model.cond_cuts = None; model.reading_cuts = None; A = [k.split("|") for k in K["cond"]]
ck = lambda P: np.array([(P[f"a|{d}|{dr}|{i}|0"] + P[f"a|{d}|{dr}|{i}|1"]) / 2 for d, dr, i in A]); trig = lambda Y: Y >= C.ATTR_MIN
YT = Z["cond"][keep]; YS = np.stack([ck(r["P"]) for r in T]); HT = np.asarray(predict(model, tok, [tt[i] for i in keep])["cond"]); HS = np.asarray(predict(model, tok, [r["state_text"] for r in T])["cond"])
np.savez(OUT.replace(".txt", "_scores.npz"), HT=HT, HS=HS, YT=YT, YS=YS)
tS, tT = trig(YS), trig(YT); negS = ~tS
neg = np.sort(HT[~tT])[::-1]; c = neg[max(int(0.0005 * len(neg)), 1) - 1]
log(f"global cut: caught {((HS >= c) & tS).sum()/tS.sum():.1%}, test false alarms {((HS >= c) & negS).sum()/negS.sum():.4%} ({((HS >= c) & negS).sum()} cells)")
for allow in (0, 1, 2):
    cuts = np.array([ (np.sort(HT[~tT[:, j], j])[::-1][min(allow, (~tT[:, j]).sum() - 1)] + 1e-9) for j in range(HT.shape[1])])
    hit = (HS >= cuts) & tS; fa = (HS >= cuts) & negS
    log(f"per-attribute cut allowing {allow} tune false alarm(s): caught {hit.sum()/tS.sum():.1%}, test false alarms {fa.sum()/negS.sum():.4%} ({fa.sum()} cells)")
open(OUT, "w").write("\n".join(lines) + "\n")
