"""Bias/variance check (Karpathy 'overfit first', Ng): does the round-6 reader catch Clef's triggers on its OWN training stories at the same tune-chosen cut as on the frozen test?
  CUDA_VISIBLE_DEVICES= WE_RULES=rules_v2 WORLD_GPU=0 /workspace/kev/.venv/bin/python newsreader/bitmob/mh/diag_trainfit.py OUT.txt"""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(16)
import classify as C
from mh_common import load, predict
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]; test_ids = {r["id"] for r in T}
tune_ids = json.load(open(f"{TUNE}/keys.json"))["ids"]; tt = json.load(open(f"{TUNE}/texts.json")); Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
model, tok, K = load(f"{W}/kaggle/mh_r6c1/out/mh"); model.cond_cuts = None; A = [k.split("|") for k in K["cond"]]
ck = lambda P: np.array([(P[f"a|{d}|{dr}|{i}|0"] + P[f"a|{d}|{dr}|{i}|1"]) / 2 for d, dr, i in A])
bank = {}
for n in ("r3", "r5"):       # Clef-labelled training rows (2,000 + 2,998)
    for l in open(f"{W}/clef-labels/{n}.jsonl"):
        r = json.loads(l)
        if "P" in r and len(r["P"]) >= 300 and r["id"] not in test_ids and r["id"] not in set(tune_ids): bank[r["id"]] = r
ids = list(bank)[:2500]; YB = np.stack([ck(bank[i]["P"]) for i in ids]); HB = np.asarray(predict(model, tok, [bank[i]["state_text"] for i in ids])["cond"])
YT = Z["cond"][keep]; HT = np.asarray(predict(model, tok, [tt[i] for i in keep])["cond"]); trig = lambda Y: Y >= C.ATTR_MIN
neg = np.sort(HT[~trig(YT)])[::-1]; t = neg[max(int(0.0005 * len(neg)), 1) - 1]
out = [f"cut {t:.3f} (tune-chosen, cell false-alarm rate 0.05%)",
       f"TRAIN stories ({len(ids)}, the reader was fit on these): triggers {trig(YB).sum()}, caught {((HB >= t) & trig(YB)).sum()/trig(YB).sum():.1%}; false-alarm rate on train negatives {((HB >= t) & ~trig(YB)).sum()/(~trig(YB)).sum():.4%}",
       f"TUNE stories ({len(keep)}, held out): triggers {trig(YT).sum()}, caught {((HT >= t) & trig(YT)).sum()/trig(YT).sum():.1%}",
       "reading: train caught near 100% and test far lower = generalisation gap (data/variance); train also low = the model cannot fit the concept (approach/capacity)."]
open(sys.argv[1], "w").write("\n".join(out) + "\n"); print("\n".join(out))
