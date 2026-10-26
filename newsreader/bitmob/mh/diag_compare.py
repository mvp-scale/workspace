"""Layered check (user, 2026-10-23: 'it's not just the data'). (A) OBJECTIVE/INTENT: same frozen e5-small features, same bank and cut rule, binary-trigger logistic heads vs soft-value ridge heads -> caught at the tune cell false-alarm rate 0.05%.
(B) ANOTHER TARGET, SAME SYSTEM: topics (48 yes/no heads, same reader, stories and teacher): test F1 and AUC per topic against the number of training positives, beside the conditions' caught-rate-by-positives from diag_blocker.
  CUDA_VISIBLE_DEVICES= WE_RULES=rules_v2 WORLD_GPU=0 /workspace/kev/.venv/bin/python newsreader/bitmob/mh/diag_compare.py OUT.txt"""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(16)
import classify as C
from mh_common import load, predict
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.metrics import roc_auc_score, f1_score
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"; lines = []
def log(s): print(s, flush=True); lines.append(s)
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]; test_ids = {r["id"] for r in T}
tune_ids = json.load(open(f"{TUNE}/keys.json"))["ids"]; tt = json.load(open(f"{TUNE}/texts.json")); Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
model, tok, K = load(f"{W}/kaggle/mh_r6c1/out/mh"); model.cond_cuts = None; A = [k.split("|") for k in K["cond"]]; TOP = K["topic_y"]
ck = lambda P: np.array([(P[f"a|{d}|{dr}|{i}|0"] + P[f"a|{d}|{dr}|{i}|1"]) / 2 for d, dr, i in A])
tp = lambda r: np.array([any(x["id"] == t and x["tagged"] for x in r["place"]) for t in TOP])
bank = {}
for n in ("r1_local", "r1b", "pilots_train", "kaggle_pilot2_train", "r3", "r5"):
    p = f"{W}/clef-labels/{n}.jsonl"
    for l in (open(p) if os.path.exists(p) else []):
        r = json.loads(l)
        if "P" in r and len(r["P"]) >= 300 and r["id"] not in test_ids and r["id"] not in set(tune_ids): bank[r["id"]] = r
from transformers import AutoModel, AutoTokenizer
_tk = AutoTokenizer.from_pretrained("intfloat/e5-small-v2"); _m = AutoModel.from_pretrained("intfloat/e5-small-v2").eval()
def emb(texts, bs=64):
    out = []
    with torch.no_grad():
        for i in range(0, len(texts), bs):
            b = _tk(["query: " + x for x in texts[i:i + bs]], truncation=True, max_length=128, padding=True, return_tensors="pt"); h = _m(**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1).float()
            out.append(torch.nn.functional.normalize((h * m).sum(1) / m.sum(1), dim=-1).numpy())
    return np.concatenate(out)
bids = list(bank); YB = np.stack([ck(bank[i]["P"]) for i in bids]); XB = emb([bank[i]["state_text"] for i in bids])
XT = emb([tt[i] for i in keep]); YT = Z["cond"][keep]; XS = emb([r["state_text"] for r in T]); YS = np.stack([ck(r["P"]) for r in T]); trig = lambda Y: Y >= C.ATTR_MIN
def cut_for(S, Y, fpr): neg = np.sort(S[~trig(Y)])[::-1]; return neg[max(int(fpr * len(neg)), 1) - 1]
R = Ridge(alpha=1.0).fit(XB, YB); PT, PS = R.predict(XT), R.predict(XS); c = cut_for(PT, YT, 0.0005)
log(f"(A) frozen e5-small, soft-value ridge heads: test caught {((PS >= c) & trig(YS)).sum()/trig(YS).sum():.1%} at tune cell false-alarm rate 0.05%")
PTl = np.zeros_like(PT); PSl = np.zeros_like(PS); Yb = trig(YB)
for j in range(len(A)):
    if Yb[:, j].sum() < 3: PTl[:, j] = PSl[:, j] = -9; continue
    m = LogisticRegression(C=10, max_iter=2000).fit(XB, Yb[:, j]); PTl[:, j] = m.decision_function(XT); PSl[:, j] = m.decision_function(XS)
c = cut_for(PTl, YT, 0.0005); log(f"(A) frozen e5-small, binary-trigger logistic heads (C=10): test caught {((PSl >= c) & trig(YS)).sum()/trig(YS).sum():.1%} at the same rule")
c = cut_for(PTl, YT, 0.0005)
HS = np.asarray(predict(model, tok, [r["state_text"] for r in T])["topic_y"]); YTop = np.stack([tp(r) for r in T]); npos = np.array([sum(tp(bank[i])[j] for i in bids) for j in range(len(TOP))])
f1 = np.array([f1_score(YTop[:, j], HS[:, j] >= 0.5, zero_division=0) for j in range(len(TOP))]); ok = YTop.sum(0) >= 5
auc = np.array([roc_auc_score(YTop[:, j], HS[:, j]) if 0 < YTop[:, j].sum() < len(T) else np.nan for j in range(len(TOP))])
log(f"(B) topics (48 heads, same reader): training positives per topic median {np.median(npos):.0f}, min {npos.min()}, max {npos.max()}; test topics with >=5 positives: {ok.sum()}")
q = np.quantile(npos[ok], [0, .25, .5, .75, 1])
for a, b in zip(q[:-1], q[1:]):
    m = ok & (npos >= a) & (npos <= b); log(f"(B) topics with {a:.0f}-{b:.0f} training positives (n={m.sum()}): mean test F1 {f1[m].mean():.2f}, mean AUC {np.nanmean(auc[m]):.3f}")
log(f"(B) correlation (training positives, test F1) over {ok.sum()} topics: {np.corrcoef(npos[ok], f1[ok])[0,1]:+.2f}")
open(sys.argv[1], "w").write("\n".join(lines) + "\n")
