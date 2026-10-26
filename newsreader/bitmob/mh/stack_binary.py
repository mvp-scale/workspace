"""R-0185: stack of (a) fine-tuned-feature binary logistic heads, (b) frozen e5-small binary logistic heads, (c) neighbour votes (k=5, tau .02, trigger indicators of the bank stories), blend weights chosen on TUNE only (cell level), then applied to the frozen test.
Scored at cell level (caught at the tune-chosen cell false-alarm rate 0.05%) and as the engine reads it (classify.read readings, dial+direction; 78 slots/story), beside the shipped reader and the part scores.
Features come from the caches written by diag_ft_binary.py and diag_objective.py (same bank / tune / test order).
  CUDA_VISIBLE_DEVICES= WE_RULES=rules_v2 WORLD_GPU=0 /workspace/kev/.venv/bin/python /workspace/newsreader/bitmob/mh/stack_binary.py /workspace/data/diag/stack_binary_2026-10-23.txt"""
import os, sys, json, itertools, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import classify as C
from mh_common import load, predict
from sklearn.linear_model import LogisticRegression
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"; SP = "/tmp/claude-0/-workspace/92c93ae1-7649-4528-80f3-1f86df44d2d8/scratchpad"; lines = []
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
bids = list(bank); YB = np.stack([ck(bank[i]["P"]) for i in bids]); YT = Z["cond"][keep]; YS = np.stack([ck(r["P"]) for r in T]); trig = lambda Y: Y >= C.ATTR_MIN; Yb = trig(YB)
F = np.load(f"{SP}/ft_feat.npz"); E = np.load(f"{SP}/obj_emb.npz"); assert len(F["XB"]) == len(bids) == len(E["XB"])
mu, sd = F["XB"].mean(0), F["XB"].std(0) + 1e-6
def heads(XB, XT, XS, Cc, norm=None):
    n = (lambda x: (x - norm[0]) / norm[1]) if norm else (lambda x: x); PT = np.full((len(XT), len(A)), -9.0); PS = np.full((len(XS), len(A)), -9.0)
    for j in range(len(A)):
        if Yb[:, j].sum() < 3: continue
        m = LogisticRegression(C=Cc, max_iter=3000).fit(n(XB), Yb[:, j]); PT[:, j] = m.decision_function(n(XT)); PS[:, j] = m.decision_function(n(XS))
    return PT, PS
a_T, a_S = heads(F["XB"], F["XT"], F["XS"], 0.01, (mu, sd)); b_T, b_S = heads(E["XB"], E["XT"], E["XS"], 10)
def nn(X, k=5, tau=0.02):
    S = X @ E["XB"].T; idx = np.argpartition(-S, k, axis=1)[:, :k]; s = np.take_along_axis(S, idx, 1); w = np.exp((s - s.max(1, keepdims=True)) / tau); w /= w.sum(1, keepdims=True); return np.einsum("nk,nkc->nc", w, Yb[idx].astype(float))
c_T, c_S = nn(E["XT"]), nn(E["XS"])
def z(T_, S_): m, s = T_.mean(), T_.std() + 1e-9; return (T_ - m) / s, (S_ - m) / s
(a_T, a_S), (b_T, b_S), (c_T, c_S) = z(a_T, a_S), z(b_T, b_S), z(c_T, c_S)
def cut_for(S, Y, fpr): neg = np.sort(S[~trig(Y)])[::-1]; return neg[max(int(fpr * len(neg)), 1) - 1]
def cell(PT, PS): c = cut_for(PT, YT, 0.0005); return ((PS >= c) & trig(YS)).sum() / trig(YS).sum(), ((PT >= c) & trig(YT)).sum() / trig(YT).sum(), c
best = None
for wa, wb, wc in itertools.product((0, 1, 2, 3), (0, 1, 2), (0, 0.5, 1, 2)):
    if wa + wb + wc == 0: continue
    r = cell(wa * a_T + wb * b_T + wc * c_T, wa * a_S + wb * b_S + wc * c_S)
    if best is None or r[1] > best[0][1] + 1e-9: best = (r, (wa, wb, wc))
for nm, (PT, PS) in (("fine-tuned-feature binary heads", (a_T, a_S)), ("frozen binary heads", (b_T, b_S)), ("neighbour votes", (c_T, c_S))): r = cell(PT, PS); log(f"part {nm}: test caught {r[0]:.1%} (tune {r[1]:.1%})")
(r, w) = best; log(f"STACK weights (a,b,c) {w} chosen on tune: test caught {r[0]:.1%} (tune {r[1]:.1%}); prediction R-0185 >= 40%")
model, tok, K = load(f"{W}/kaggle/mh_r6c1/out/mh"); model.cond_cuts = None
keys = lambda rd: {(x["dial"], x["direction"]) for x in rd["readings"] if x["direction"] != "conflict"}
def engine(S, cut, name):
    tp = fp = pos = neg = 0
    for n, rr in enumerate(T):
        P = dict(rr["P"])
        for j, (d, dr, i) in enumerate(A): P[f"a|{d}|{dr}|{i}|0"] = P[f"a|{d}|{dr}|{i}|1"] = float(S[n, j] - cut + C.ATTR_MIN)
        m = keys(C.read(P)); b = keys(rr["read"]); tp += len(m & b); fp += len(m - b); pos += len(b); neg += 78 - len(b)
    log(f"ENGINE READINGS {name}: conditions caught {tp/pos:.1%} ({tp}/{pos}), false alarms {fp/neg:.4%} ({fp} extra)")
HT = np.asarray(predict(model, tok, [tt[i] for i in keep])["cond"]); HS = np.asarray(predict(model, tok, [rr["state_text"] for rr in T])["cond"])
engine(HS, cut_for(HT, YT, 0.0005), "shipped reader (same cut rule)"); engine(a_S, cell(a_T, a_S)[2], "fine-tuned binary heads"); wa, wb, wc = w; engine(wa * a_S + wb * b_S + wc * c_S, r[2], "STACK")
log("bar: caught >= 90% at false alarms <= 0.1%")
open(sys.argv[1], "w").write("\n".join(lines) + "\n")
