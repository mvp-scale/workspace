"""K1 / R-0184 (1-3-1 attempt 2): do the nearest Clef-labelled training stories' condition answers help BitMob alone catch Clef's conditions?
Protocol fixed before scoring: bank = Clef-labelled rows (the six train files) minus test ids minus tune ids; embeddings = cached e5-small-v2 (unit-normalised, cosine);
retrieval R = similarity-weighted mean of the neighbours' attribute answers; blend S = a*H + (1-a)*R; k, temperature, a and the cut are chosen on the TUNE rows only (cell level), then applied unchanged to the frozen test.
Baseline = BitMob alone (a = 1) under the same cut rule. Scored as the engine does: classify.read readings (dial, direction), conditions caught / false alarms per negative slot (78 slots/story).
  CUDA_VISIBLE_DEVICES= WE_RULES=rules_v2 WORLD_GPU=0 /workspace/kev/.venv/bin/python newsreader/bitmob/mh/retrieval_test.py OUT.txt"""
import os, sys, json, itertools, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(8)
import classify as C
from mh_common import load, predict
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"; OUT = sys.argv[1]; lines = []
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
def emb(texts, bs=64):      # frozen e5-small-v2, 'query: ' prefix, mean pooling, unit length (fixed choice, made before scoring)
    out = []
    with torch.no_grad():
        for i in range(0, len(texts), bs):
            b = _tk(["query: " + x for x in texts[i:i + bs]], truncation=True, max_length=128, padding=True, return_tensors="pt"); h = _m(**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1).float()
            z = (h * m).sum(1) / m.sum(1); out.append(torch.nn.functional.normalize(z, dim=-1).numpy())
    return np.concatenate(out)
bids = list(bank); XB = emb([bank[i]["state_text"] for i in bids]); YB = np.stack([ck(bank[i]["P"]) for i in bids])
tids = [tune_ids[i] for i in keep]; XT = emb([tt[i] for i in keep]); YT = Z["cond"][keep]
XS = emb([r["state_text"] for r in T]); YS = np.stack([ck(r["P"]) for r in T])
log(f"bank {len(bids)} stories; tune {len(tids)}; test {len(T)}; attribute cells {len(A)}; trigger cutoff ATTR_MIN {C.ATTR_MIN}")
HT = np.asarray(predict(model, tok, [tt[i] for i in keep])["cond"]); HS = np.asarray(predict(model, tok, [r["state_text"] for r in T])["cond"])
def retrieve(X, k, tau):
    S = X @ XB.T; idx = np.argpartition(-S, k, axis=1)[:, :k]; s = np.take_along_axis(S, idx, 1); w = np.exp((s - s.max(1, keepdims=True)) / tau); w /= w.sum(1, keepdims=True)
    return np.einsum("nk,nkc->nc", w, YB[idx])
trig = lambda Y: Y >= C.ATTR_MIN
def cut_for(S, Y, fpr):                      # global cut on tune: highest score threshold keeping the false-alarm rate over negative cells <= fpr
    neg = np.sort(S[~trig(Y)])[::-1]; return neg[max(int(fpr * len(neg)), 1) - 1]
best = None
for k, tau, a in itertools.product((5, 10, 25), (0.02, 0.05), (1.0, 0.75, 0.5, 0.25, 0.0)):
    R = retrieve(XT, k, tau) if a < 1 else 0; S = a * HT + (1 - a) * R; t = cut_for(S, YT, 0.0005); caught = ((S >= t) & trig(YT)).sum() / trig(YT).sum()
    if best is None or caught > best[0] + 1e-9: best = (caught, k, tau, a, t)
    if a in (1.0, 0.5): log(f"tune k={k} tau={tau} a={a}: cells caught {caught:.1%} at cell false-alarm rate 0.05%")
caught, k, tau, a, t = best; log(f"CHOSEN ON TUNE: k={k} tau={tau} a={a} cut={t:.4f} (tune cells caught {caught:.1%})")
base_t = cut_for(HT, YT, 0.0005)
keys = lambda rd: {(x["dial"], x["direction"]) for x in rd["readings"] if x["direction"] != "conflict"}
def score(S, cut, name):
    tp = fp = pos = neg = 0
    for n, r in enumerate(T):
        P = dict(r["P"])
        for j, (d, dr, i) in enumerate(A): P[f"a|{d}|{dr}|{i}|0"] = P[f"a|{d}|{dr}|{i}|1"] = float(S[n, j] - cut + C.ATTR_MIN)
        m = keys(C.read(P)); b = keys(r["read"]); tp += len(m & b); fp += len(m - b); pos += len(b); neg += 78 - len(b)
    log(f"TEST {name}: conditions caught {tp/pos:.1%} ({tp}/{pos}), false alarms {fp/neg:.4%} ({fp} extra readings)"); return tp / pos, fp / neg
b = score(HS, base_t, "BitMob alone (same cut rule)"); R = retrieve(XS, k, tau); score(R, cut_for(retrieve(XT, k, tau), YT, 0.0005), "retrieval alone"); s = score(a * HS + (1 - a) * R, t, "blend")
log(f"gain over BitMob alone: {100*(s[0]-b[0]):+.1f} points caught; false alarms {s[1]:.4%} vs {b[1]:.4%}. Bar: caught >= 90% at false alarms <= 0.1%; prediction R-0184: >= 45% (no gain if < +5 points).")
open(OUT, "w").write("\n".join(lines) + "\n")
