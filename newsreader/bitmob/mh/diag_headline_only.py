"""Does the conditions signal live in the headline? Q15 reader, same tune cut as the full-text run, test stories cut to headline only (text before the first '. ')."""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(16)
import classify as C, mh_common_t1 as M
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]; Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
model, tok, K = M.load_attn(f"{W}/kaggle/mh_t1lg24/out/mh"); A = [k.split("|") for k in K["cond"]]
ck = lambda P: np.array([(P[f"a|{d}|{dr}|{i}|0"] + P[f"a|{d}|{dr}|{i}|1"]) / 2 for d, dr, i in A])
YT = Z["cond"][keep]; YS = np.stack([ck(r["P"]) for r in T]); trig = lambda Y: Y >= C.ATTR_MIN
S = np.load(f"{W}/diag/ens3_2026-10-24_scores.npz"); ST, SSfull = S["T_Q15"], S["S_Q15"]
neg = np.sort(ST[~trig(YT)])[::-1]; cut = neg[max(int(0.0005 * len(neg)), 1) - 1]
head = lambda t: t.split(". ", 1)[0]
lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
SSh = lg(np.asarray(M.predict(model, tok, [head(r["state_text"]) for r in T])["cond"]))
nh = sum(1 for r in T if ". " in r["state_text"]); print("stories with a second sentence:", nh, "of", len(T))
for lab, SS in (("headline+description", SSfull), ("headline only", SSh)):
    P = SS >= cut; print(f"{lab}: cell catch {(P & trig(YS)).sum() / trig(YS).sum():.1%}, false alarms {(P & ~trig(YS)).sum() / (~trig(YS)).sum():.3%}")
