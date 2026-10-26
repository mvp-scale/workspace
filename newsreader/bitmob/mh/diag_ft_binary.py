"""O1a (1-3-1 attempt 3): the round-6 reader's OWN fine-tuned encoder features (frozen), with binary-trigger logistic heads instead of its soft-target heads. Same bank, tune-chosen cut (cell false-alarm rate 0.05%), 159 heads.
 Caveat recorded up front: the encoder was fit on the bank, so bank features are 'seen'; heads are scored on the held-out test only.
  CUDA_VISIBLE_DEVICES= WE_RULES=rules_v2 WORLD_GPU=0 /workspace/kev/.venv/bin/python newsreader/bitmob/mh/diag_ft_binary.py OUT.txt"""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(16)
import classify as C
from mh_common import load, predict, tokenise
from sklearn.linear_model import LogisticRegression
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"; lines = []; EC = "/tmp/claude-0/-workspace/92c93ae1-7649-4528-80f3-1f86df44d2d8/scratchpad/ft_feat.npz"
def log(s): print(s, flush=True); lines.append(s)
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]; test_ids = {r["id"] for r in T}
tune_ids = json.load(open(f"{TUNE}/keys.json"))["ids"]; tt = json.load(open(f"{TUNE}/texts.json")); Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
model, tok, K = load(f"{W}/kaggle/mh_r6c1/out/mh"); model.cond_cuts = None; A = [k.split("|") for k in K["cond"]]
ck = lambda P: np.array([(P[f"a|{d}|{dr}|{i}|0"] + P[f"a|{d}|{dr}|{i}|1"]) / 2 for d, dr, i in A])
bank = {}
for n in ("r1_local", "r1b", "pilots_train", "kaggle_pilot2_train", "r3", "r5"):
    p = f"{W}/clef-labels/{n}.jsonl"
    for l in (open(p) if os.path.exists(p) else []):
        r = json.loads(l)
        if "P" in r and len(r["P"]) >= 300 and r["id"] not in test_ids and r["id"] not in set(tune_ids): bank[r["id"]] = r
bids = list(bank); YB = np.stack([ck(bank[i]["P"]) for i in bids]); YT = Z["cond"][keep]; YS = np.stack([ck(r["P"]) for r in T]); trig = lambda Y: Y >= C.ATTR_MIN
def feats(texts, bs=32):
    out = []; model.eval()
    with torch.inference_mode():
        for s in range(0, len(texts), bs): ids, mask = tokenise(tok, texts[s:s + bs], "cpu"); out.append(model.pooled(ids, mask).numpy())
    return np.concatenate(out)
if os.path.exists(EC): d = np.load(EC); XB, XT, XS = d["XB"], d["XT"], d["XS"]
else: XB = feats([bank[i]["state_text"] for i in bids]); XT = feats([tt[i] for i in keep]); XS = feats([r["state_text"] for r in T]); np.savez(EC, XB=XB, XT=XT, XS=XS)
def cut_for(S, Y, fpr): neg = np.sort(S[~trig(Y)])[::-1]; return neg[max(int(fpr * len(neg)), 1) - 1]
HT = np.asarray(predict(model, tok, [tt[i] for i in keep])["cond"]); HS = np.asarray(predict(model, tok, [r["state_text"] for r in T])["cond"]); c = cut_for(HT, YT, 0.0005)
log(f"round-6 reader as shipped (soft-target heads): test caught {((HS >= c) & trig(YS)).sum()/trig(YS).sum():.1%} at tune cell false-alarm rate 0.05%")
Yb = trig(YB); mu, sd = XB.mean(0), XB.std(0) + 1e-6
for Cc in (0.01, 0.1, 1.0):
    PT = np.full((len(XT), len(A)), -9.0); PS = np.full((len(XS), len(A)), -9.0)
    for j in range(len(A)):
        if Yb[:, j].sum() < 3: continue
        m = LogisticRegression(C=Cc, max_iter=3000).fit((XB - mu) / sd, Yb[:, j]); PT[:, j] = m.decision_function((XT - mu) / sd); PS[:, j] = m.decision_function((XS - mu) / sd)
    c2 = cut_for(PT, YT, 0.0005); log(f"fine-tuned features + binary-trigger logistic heads C={Cc}: test caught {((PS >= c2) & trig(YS)).sum()/trig(YS).sum():.1%} (tune caught {((PT >= c2) & trig(YT)).sum()/trig(YT).sum():.1%})")
open(sys.argv[1], "w").write("\n".join(lines) + "\n")
