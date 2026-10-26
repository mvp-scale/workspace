"""R-0186 scorer: conditions of a trained multi-head model on the frozen 2,000-story test, same rules as stack_binary.py. Cut chosen on TUNE only (cell false-alarm rate 0.05%).
Reports: cell-level caught (test and tune), the engine's own readings (classify.read) caught / false alarms, and the reader's catch on its own training triggers (bias check).
  CUDA_VISIBLE_DEVICES= WE_RULES=rules_v2 WORLD_GPU=0 /workspace/kev/.venv/bin/python /workspace/newsreader/bitmob/mh/score_b1.py MODEL_DIR LABEL OUT.txt"""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(16)
import classify as C
from mh_common import load, predict
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"; MD, LABEL, OUT = sys.argv[1:4]; lines = []
def log(s): print(s, flush=True); lines.append(s)
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]; test_ids = {r["id"] for r in T}
tune_ids = json.load(open(f"{TUNE}/keys.json"))["ids"]; tt = json.load(open(f"{TUNE}/texts.json")); Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
model, tok, K = load(MD); model.cond_cuts = None; model.reading_cuts = None; A = [k.split("|") for k in K["cond"]]
ck = lambda P: np.array([(P[f"a|{d}|{dr}|{i}|0"] + P[f"a|{d}|{dr}|{i}|1"]) / 2 for d, dr, i in A]); trig = lambda Y: Y >= C.ATTR_MIN
YT = Z["cond"][keep]; YS = np.stack([ck(r["P"]) for r in T])
HT = np.asarray(predict(model, tok, [tt[i] for i in keep])["cond"]); HS = np.asarray(predict(model, tok, [r["state_text"] for r in T])["cond"])
def cut_for(S, Y, fpr): neg = np.sort(S[~trig(Y)])[::-1]; return neg[max(int(fpr * len(neg)), 1) - 1]
c = cut_for(HT, YT, 0.0005); log(f"{LABEL}: cell level, cut {c:.4f} chosen on tune: test caught {((HS >= c) & trig(YS)).sum()/trig(YS).sum():.1%} ({trig(YS).sum()} triggers), tune caught {((HT >= c) & trig(YT)).sum()/trig(YT).sum():.1%}")
bank = {}
for n in ("r3", "r5"):
    for l in open(f"{W}/clef-labels/{n}.jsonl"):
        r = json.loads(l)
        if "P" in r and len(r["P"]) >= 300 and r["id"] not in test_ids and r["id"] not in set(tune_ids): bank[r["id"]] = r
ids = list(bank)[:1500]; YB = np.stack([ck(bank[i]["P"]) for i in ids]); HB = np.asarray(predict(model, tok, [bank[i]["state_text"] for i in ids])["cond"])
log(f"{LABEL}: on {len(ids)} of its own training stories the same cut catches {((HB >= c) & trig(YB)).sum()/trig(YB).sum():.1%} of {trig(YB).sum()} triggers")
keys = lambda rd: {(x["dial"], x["direction"]) for x in rd["readings"] if x["direction"] != "conflict"}
tp = fp = pos = neg = 0
for n, rr in enumerate(T):
    P = dict(rr["P"])
    for j, (d, dr, i) in enumerate(A): P[f"a|{d}|{dr}|{i}|0"] = P[f"a|{d}|{dr}|{i}|1"] = float(HS[n, j] - c + C.ATTR_MIN)
    m = keys(C.read(P)); b = keys(rr["read"]); tp += len(m & b); fp += len(m - b); pos += len(b); neg += 78 - len(b)
log(f"{LABEL}: ENGINE READINGS conditions caught {tp/pos:.1%} ({tp}/{pos}), false alarms {fp/neg:.4%} ({fp} extra); bar >= 90% at <= 0.1%")
open(OUT, "a").write("\n".join(lines) + "\n")
