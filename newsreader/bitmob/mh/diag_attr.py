"""Per-attribute learnability: which of the 159 conditions the reader can learn at all. Usage: diag_attr.py MODEL_DIR OUT.json
Per attribute: test triggers, Clef wording consistency on triggers, share of triggers that are strong (>=0.85), caught at the tune-chosen cut (0.05% cell false alarms), AUC."""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(16)
import classify as C
from mh_common import load, predict
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"; MD, OUT = sys.argv[1:3]
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]
tt = json.load(open(f"{TUNE}/texts.json")); Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
model, tok, K = load(MD); model.cond_cuts = None; model.reading_cuts = None; A = [k.split("|") for k in K["cond"]]
ck = lambda P: np.array([(P[f"a|{d}|{dr}|{i}|0"] + P[f"a|{d}|{dr}|{i}|1"]) / 2 for d, dr, i in A]); trig = lambda Y: Y >= C.ATTR_MIN
YT = Z["cond"][keep]; YS = np.stack([ck(r["P"]) for r in T])
w0 = np.array([[r["P"][f"a|{d}|{dr}|{i}|0"] for d, dr, i in A] for r in T]); w1 = np.array([[r["P"][f"a|{d}|{dr}|{i}|1"] for d, dr, i in A] for r in T])
HT = np.asarray(predict(model, tok, [tt[i] for i in keep])["cond"]); HS = np.asarray(predict(model, tok, [r["state_text"] for r in T])["cond"])
neg = np.sort(HT[~trig(YT)])[::-1]; c = neg[max(int(0.0005 * len(neg)), 1) - 1]
def auc(s, y):
    if y.sum() == 0 or y.sum() == len(y): return None
    r = s.argsort().argsort() + 1; return float((r[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum()))
rows = []
for j, k in enumerate(K["cond"]):
    t = trig(YS[:, j]); n = int(t.sum())
    rows.append({"key": k, "triggers": n, "strong_share": float((YS[t, j] >= .85).mean()) if n else None, "wording_consistent": float(((w0[:, j] >= .5) & (w1[:, j] >= .5))[t].mean()) if n else None,
                 "caught": float((HS[t, j] >= c).mean()) if n else None, "auc": auc(HS[:, j], t), "tune_triggers": int(trig(YT[:, j]).sum())})
json.dump({"cut": float(c), "rows": rows}, open(OUT, "w"), indent=1)
R = [r for r in rows if r["triggers"] >= 5]; print("attributes with >=5 test triggers:", len(R), "of", len(rows), "; with 0 triggers:", sum(r["triggers"] == 0 for r in rows))
print("trigger-weighted caught", sum(r["caught"] * r["triggers"] for r in R) / sum(r["triggers"] for r in R))
for q in (0, 10, 25, 50): print(f"caught >= {q}%: {sum(r['caught'] * 100 >= q for r in R)} attributes holding {sum(r['triggers'] for r in R if r['caught'] * 100 >= q)} triggers")
print("low strong-share (<0.2) attributes:", sum(r["strong_share"] < .2 for r in R), "of", len(R), "; their triggers", sum(r["triggers"] for r in R if r["strong_share"] < .2))
