"""Objective isolation (2026-10-23): same frozen e5-small features, same bank, same tune-chosen cut (cell false-alarm rate 0.05%), 159 condition heads. Vary only the training target / loss:
 binary-trigger logistic (C 1/10/100), soft-target logistic (Clef value as a probability: each row twice, label 1 weight y, label 0 weight 1-y), balanced binary logistic, binary ridge, soft ridge.
  CUDA_VISIBLE_DEVICES= WE_RULES=rules_v2 WORLD_GPU=0 /workspace/kev/.venv/bin/python newsreader/bitmob/mh/diag_objective.py OUT.txt"""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo"]
import torch; torch.set_num_threads(16)
import classify as C
from sklearn.linear_model import Ridge, LogisticRegression
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"; lines = []; EC = "/tmp/claude-0/-workspace/92c93ae1-7649-4528-80f3-1f86df44d2d8/scratchpad/obj_emb.npz"
def log(s): print(s, flush=True); lines.append(s)
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]; test_ids = {r["id"] for r in T}
tune_ids = json.load(open(f"{TUNE}/keys.json"))["ids"]; tt = json.load(open(f"{TUNE}/texts.json")); Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
A = [k.split("|") for k in json.load(open(f"{W}/kaggle/mh_r6c1/out/mh/keys.json"))["cond"]]
ck = lambda P: np.array([(P[f"a|{d}|{dr}|{i}|0"] + P[f"a|{d}|{dr}|{i}|1"]) / 2 for d, dr, i in A])
bank = {}
for n in ("r1_local", "r1b", "pilots_train", "kaggle_pilot2_train", "r3", "r5"):
    p = f"{W}/clef-labels/{n}.jsonl"
    for l in (open(p) if os.path.exists(p) else []):
        r = json.loads(l)
        if "P" in r and len(r["P"]) >= 300 and r["id"] not in test_ids and r["id"] not in set(tune_ids): bank[r["id"]] = r
bids = list(bank); YB = np.stack([ck(bank[i]["P"]) for i in bids]); YT = Z["cond"][keep]; YS = np.stack([ck(r["P"]) for r in T]); trig = lambda Y: Y >= C.ATTR_MIN
if os.path.exists(EC): d = np.load(EC); XB, XT, XS = d["XB"], d["XT"], d["XS"]
else:
    from transformers import AutoModel, AutoTokenizer
    _tk = AutoTokenizer.from_pretrained("intfloat/e5-small-v2"); _m = AutoModel.from_pretrained("intfloat/e5-small-v2").eval()
    def emb(texts, bs=64):
        out = []
        with torch.no_grad():
            for i in range(0, len(texts), bs):
                b = _tk(["query: " + x for x in texts[i:i + bs]], truncation=True, max_length=128, padding=True, return_tensors="pt"); h = _m(**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1).float()
                out.append(torch.nn.functional.normalize((h * m).sum(1) / m.sum(1), dim=-1).numpy())
        return np.concatenate(out)
    XB = emb([bank[i]["state_text"] for i in bids]); XT = emb([tt[i] for i in keep]); XS = emb([r["state_text"] for r in T]); np.savez(EC, XB=XB, XT=XT, XS=XS)
def cut_for(S, Y, fpr): neg = np.sort(S[~trig(Y)])[::-1]; return neg[max(int(fpr * len(neg)), 1) - 1]
Yb = trig(YB); log(f"bank {len(bids)} stories, trigger cells {Yb.sum()}; tune {len(keep)}; test {len(T)} ({trig(YS).sum()} triggers)")
def run(name, fit):
    PT = np.full((len(XT), len(A)), -9.0); PS = np.full((len(XS), len(A)), -9.0)
    for j in range(len(A)):
        if Yb[:, j].sum() < 3: continue
        f = fit(j); PT[:, j] = f(XT); PS[:, j] = f(XS)
    c = cut_for(PT, YT, 0.0005); log(f"{name}: test caught {((PS >= c) & trig(YS)).sum()/trig(YS).sum():.1%} (tune caught {((PT >= c) & trig(YT)).sum()/trig(YT).sum():.1%})")
def lg(Cc, cw=None): return lambda j: LogisticRegression(C=Cc, max_iter=3000, class_weight=cw).fit(XB, Yb[:, j]).decision_function
for Cc in (1, 10, 100): run(f"binary-trigger logistic C={Cc}", lg(Cc))
run("binary-trigger logistic C=10 balanced", lg(10, "balanced"))
def soft(j):
    y = np.clip(YB[:, j], 0, 1); m = LogisticRegression(C=10, max_iter=3000).fit(np.vstack([XB, XB]), np.r_[np.ones(len(XB)), np.zeros(len(XB))], sample_weight=np.r_[y, 1 - y]); return m.decision_function
run("soft-target logistic C=10 (Clef value as probability)", soft)
run("binary ridge (squared loss on 0/1)", lambda j: Ridge(alpha=1.0).fit(XB, Yb[:, j].astype(float)).predict)
run("soft ridge (squared loss on Clef value)", lambda j: Ridge(alpha=1.0).fit(XB, YB[:, j]).predict)
open(sys.argv[1], "w").write("\n".join(lines) + "\n")
