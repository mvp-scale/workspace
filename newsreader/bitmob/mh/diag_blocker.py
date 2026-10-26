"""Blocker diagnosis (2026-10-23): data vs approach vs assumption, on the 2,000-story frozen test with the round-6 reader. Cut chosen on TUNE rows only (cell false-alarm rate 0.05%), as in retrieval_test.py.
 (1) misses by Clef strength: does BitMob miss only borderline triggers, or strong ones too?  (2) caught rate vs number of training positives per attribute (data-limited?)  (3) what BitMob's top false alarms are in Clef's own terms (near-misses under the cut, or clear negatives?)
 (4) learning curve: frozen e5-small + ridge heads on 25/50/100% of the bank, caught at the same cell false-alarm rate.
  CUDA_VISIBLE_DEVICES= WE_RULES=rules_v2 WORLD_GPU=0 /workspace/kev/.venv/bin/python newsreader/bitmob/mh/diag_blocker.py OUT.txt"""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(16)
import classify as C
from mh_common import load, predict
from sklearn.linear_model import Ridge
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"; lines = []
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
XT = emb([tt[i] for i in keep]); YT = Z["cond"][keep]; XS = emb([r["state_text"] for r in T]); YS = np.stack([ck(r["P"]) for r in T])
HT = np.asarray(predict(model, tok, [tt[i] for i in keep])["cond"]); HS = np.asarray(predict(model, tok, [r["state_text"] for r in T])["cond"])
trig = lambda Y: Y >= C.ATTR_MIN
def cut_for(S, Y, fpr): neg = np.sort(S[~trig(Y)])[::-1]; return neg[max(int(fpr * len(neg)), 1) - 1]
t = cut_for(HT, YT, 0.0005); hit = (HS >= t); tr = trig(YS)
log(f"round-6 reader, cut {t:.3f} chosen on tune: triggers {tr.sum()}, caught {(hit & tr).sum()/tr.sum():.1%}")
log("(1) caught by Clef strength: " + "; ".join(f"Clef {lo:.2f}-{hi:.2f}: {(hit & tr & (YS>=lo) & (YS<hi)).sum()}/{(tr & (YS>=lo) & (YS<hi)).sum()} = {(hit & tr & (YS>=lo) & (YS<hi)).sum()/max((tr & (YS>=lo) & (YS<hi)).sum(),1):.0%}" for lo, hi in ((0.65, 0.75), (0.75, 0.85), (0.85, 0.95), (0.95, 1.01))))
npos = trig(YB).sum(0); caught_a = np.array([(hit[:, j] & tr[:, j]).sum() / max(tr[:, j].sum(), 1) for j in range(len(A))]); ntest = tr.sum(0); ok = ntest >= 3
q = np.quantile(npos[ok], [0, .25, .5, .75, 1])
for a, b in zip(q[:-1], q[1:]):
    m = ok & (npos >= a) & (npos <= b); log(f"(2) attributes with {a:.0f}-{b:.0f} training positives (n={m.sum()}): test caught {np.average(caught_a[m], weights=ntest[m]):.1%}")
log(f"(2) correlation (training positives, test caught rate) over {ok.sum()} attributes: {np.corrcoef(npos[ok], caught_a[ok])[0,1]:+.2f}; training positives per attribute: median {np.median(npos):.0f}, min {npos.min()}, max {npos.max()}")
neg_scores = np.where(~tr, HS, -1); top = np.argsort(-neg_scores.ravel())[:200]; yv = YS.ravel()[top]
log(f"(3) BitMob's 200 highest-scoring non-trigger cells, by Clef's own value: <0.10: {(yv<.1).sum()}, 0.10-0.40: {((yv>=.1)&(yv<.4)).sum()}, 0.40-0.55: {((yv>=.4)&(yv<.55)).sum()}, 0.55-0.65: {((yv>=.55)&(yv<.65)).sum()}")
fa = hit & ~tr; yf = YS[fa]; log(f"(3) actual false alarms at the cut: {fa.sum()} cells; Clef value 0.55-0.65 (near-miss): {((yf>=.55)).sum()}, 0.40-0.55: {((yf>=.4)&(yf<.55)).sum()}, <0.40: {(yf<.4).sum()}")
rng = np.random.default_rng(0)
for frac in (0.25, 0.5, 1.0):
    idx = rng.permutation(len(bids))[: int(frac * len(bids))]; R = Ridge(alpha=1.0).fit(XB[idx], YB[idx]); PT = R.predict(XT); PS = R.predict(XS); c = cut_for(PT, YT, 0.0005)
    log(f"(4) learning curve, frozen e5-small + ridge, {len(idx)} training stories ({trig(YB[idx]).sum()} trigger cells): test caught {((PS >= c) & tr).sum()/tr.sum():.1%} at tune cell false-alarm rate 0.05%")
open(sys.argv[1], "w").write("\n".join(lines) + "\n")
