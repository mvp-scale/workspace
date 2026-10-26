"""Direction check (user hint, 2026-10-23: conditions = 'a dial going up or down'). Slot level = (dial, direction); dial level = either direction. Round-6 reader, tune-chosen cuts (false-alarm rate 0.05% of negative slots), frozen test.
 (1) caught at slot level vs at dial level (direction ignored)  (2) of the missed slots, how many have the OPPOSITE direction of the same dial scored above the cut  (3) of the false-alarm slots, how many are slots where Clef triggers the opposite direction.
  CUDA_VISIBLE_DEVICES= WE_RULES=rules_v2 WORLD_GPU=0 /workspace/kev/.venv/bin/python newsreader/bitmob/mh/diag_direction.py OUT.txt"""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(10)
import classify as C
from mh_common import load, predict
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"; lines = []
def log(s): print(s, flush=True); lines.append(s)
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]
tt = json.load(open(f"{TUNE}/texts.json")); Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
model, tok, K = load(f"{W}/kaggle/mh_r6c1/out/mh"); model.cond_cuts = None; A = [k.split("|") for k in K["cond"]]
ck = lambda P: np.array([(P[f"a|{d}|{dr}|{i}|0"] + P[f"a|{d}|{dr}|{i}|1"]) / 2 for d, dr, i in A])
YS = np.stack([ck(r["P"]) for r in T]); YT = Z["cond"][keep]; trig = lambda Y: Y >= C.ATTR_MIN
HT = np.asarray(predict(model, tok, [tt[i] for i in keep])["cond"]); HS = np.asarray(predict(model, tok, [r["state_text"] for r in T])["cond"])
slots = sorted({(d, dr) for d, dr, i in A}); dials = sorted({d for d, _ in slots}); col = {s: [j for j, (d, dr, i) in enumerate(A) if (d, dr) == s] for s in slots}
def slot_mat(H, Y, agg): return np.stack([agg(H[:, col[s]], 1) for s in slots], 1), np.stack([agg(trig(Y[:, col[s]]), 1) for s in slots], 1).astype(bool)
sT, tT = slot_mat(HT, YT, np.max); sS, tS = slot_mat(HS, YS, np.max)
def cut_for(S, Yb, fpr): neg = np.sort(S[~Yb])[::-1]; return neg[max(int(fpr * len(neg)), 1) - 1]
c = cut_for(sT, tT, 0.0005); hit = sS >= c; log(f"slot level (dial, direction): {tS.sum()} Clef-trigger slots in 2,000 stories; caught {(hit & tS).sum()/tS.sum():.1%}; false-alarm slots {(hit & ~tS).sum()}")
di = {d: [k for k, s in enumerate(slots) if s[0] == d] for d in dials}
dT = np.stack([sT[:, di[d]].max(1) for d in dials], 1); dtT = np.stack([tT[:, di[d]].any(1) for d in dials], 1); dS = np.stack([sS[:, di[d]].max(1) for d in dials], 1); dtS = np.stack([tS[:, di[d]].any(1) for d in dials], 1)
c2 = cut_for(dT, dtT, 0.0005); h2 = dS >= c2; log(f"dial level (direction ignored): {dtS.sum()} Clef-trigger dials; caught {(h2 & dtS).sum()/dtS.sum():.1%}; false-alarm dials {(h2 & ~dtS).sum()}")
opp = {k: next(k2 for k2 in di[slots[k][0]] if k2 != k) if len(di[slots[k][0]]) == 2 else None for k in range(len(slots))}
miss = tS & ~hit; mo = sum(1 for n, k in zip(*np.where(miss)) if opp[k] is not None and hit[n, opp[k]]); log(f"missed slots {miss.sum()}: opposite direction of the same dial scored above the cut in {mo} ({mo/max(miss.sum(),1):.1%}); dial detected at all (either direction above its cut) in {sum(1 for n, k in zip(*np.where(miss)) if h2[n, dials.index(slots[k][0])])} ({sum(1 for n, k in zip(*np.where(miss)) if h2[n, dials.index(slots[k][0])])/max(miss.sum(),1):.1%})")
fa = hit & ~tS; fo = sum(1 for n, k in zip(*np.where(fa)) if opp[k] is not None and tS[n, opp[k]]); log(f"false-alarm slots {fa.sum()}: Clef triggers the OPPOSITE direction of the same dial in {fo} ({fo/max(fa.sum(),1):.1%})")
both = sum(1 for n in range(len(T)) for d in dials if len(di[d]) == 2 and tS[n, di[d][0]] and tS[n, di[d][1]]); log(f"stories where Clef triggers both directions of one dial: {both}")
open(sys.argv[1], "w").write("\n".join(lines) + "\n")
