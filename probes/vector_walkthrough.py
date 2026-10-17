"""Data for the vector walkthrough mock-up (demo/mockups/vector-walkthrough.html): every step from text to answer, on real items.

Featured: two test sentences that are both exactly "Yes." with opposite human labels for the 'agree' question
(20180826-011431_343_live#5255 agree-donation, 20180826-204907_535_live#7470 positive-to-inquiry), from data/state-depth/items.jsonl.
Encoders: static potion-base-8M (256 numbers per token, fixed per word) and e5-small int8 (384, the CPU engine's exact runtime).
Heads: LogisticRegression(C=1, balanced) for 'agree' on the 248 training items, the CPU engine's settings.
Writes demo/mockups/vector-walkthrough.json.  Run with models/embed-zs/.venv/bin/python (HF_HOME=/workspace/data/hf).
"""
import json, sys, pathlib
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).parent)); import state_depth as sd
from sklearn.linear_model import LogisticRegression
from sklearn.decomposition import PCA

OUT = pathlib.Path("/workspace/demo/mockups/vector-walkthrough.json")
FEAT = ["20180826-011431_343_live#5255", "20180826-204907_535_live#7470"]
Q = "agree"
r3 = lambda a: [round(float(x), 3) for x in a]

items = [json.loads(l) for l in open(sd.OUT / "items.jsonl")]
tr = [i for i in items if i["split"] == "train"]; by = {i["id"]: i for i in items}; feat = [by[f] for f in FEAT]

# ---- the two encoders, token by token (vectors BEFORE averaging) ----
from model2vec import StaticModel
SM = StaticModel.from_pretrained("minishlab/potion-base-8M")
import onnxruntime as ort
from tokenizers import Tokenizer
from huggingface_hub import hf_hub_download
TOK = Tokenizer.from_file(hf_hub_download("intfloat/e5-small-v2", "tokenizer.json")); TOK.enable_truncation(512)
SESS = ort.InferenceSession("/workspace/data/embed-zs/engine/e5.int8.onnx", providers=["CPUExecutionProvider"])


def tokens(enc, text):
    """(token strings, token vectors) exactly as the encoder averages them."""
    if enc == "static":
        ids = SM.tokenize([text])[0]
        return [SM.tokenizer.id_to_token(t) for t in ids], SM.embedding[ids].astype(np.float32)
    e = TOK.encode("query: " + text); ids = np.array([e.ids], np.int64); m = np.array([e.attention_mask], np.int64)
    h = SESS.run(None, {"input_ids": ids, "attention_mask": m, "token_type_ids": np.zeros_like(ids)})[0][0]
    return e.tokens, h


def pooled(enc, text):
    t, H = tokens(enc, text); v = H.mean(0); return v / np.linalg.norm(v)


Z = np.load(sd.OUT / "vectors.npz", allow_pickle=True)
V = {e: dict(zip(Z[f"{e}_texts"], Z[f"{e}_vecs"])) for e in ("static", "e5")}
for e in ("static", "e5"):   # the walkthrough's own pooling must equal the vectors the grid used
    for i in feat:
        assert float(pooled(e, i["S3"]) @ V[e][i["S3"]]) > 0.9999, (e, i["id"])

STATES = {"S1": lambda i: i["S1"], "S1+instr+crit": lambda i: sd.compose(i["S1"], Q, "deep", 3), "S2": lambda i: i["S2"], "S3": lambda i: i["S3"]}
out = {"question": sd.QW[Q]["deep"], "featured": [{"id": i["id"], "label": i["label"], "truth": i["y"][Q], "S1": i["S1"], "S2": i["S2"], "S3": i["S3"],
                                                    "S1+instr+crit": STATES["S1+instr+crit"](i)} for i in feat], "enc": {}}
grid = json.load(open(sd.OUT / "grid.json"))

for e in ("static", "e5"):
    E = {"dim": None, "tokens": {}, "pool": {}, "map": {}, "head": {}, "acc": {}}
    # step 1-3: tokens, their vectors, the average, for both featured items in S1 and S3
    for k, i in enumerate(feat):
        for s in ("S1", "S3"):
            t, H = tokens(e, i[s]); E["dim"] = H.shape[1]
            v = H.mean(0); n = float(np.linalg.norm(v))
            # which tokens belong to the sentence: the last run of tokens that spells the sentence (state ends with it)
            sent_t, _ = tokens(e, i["S1"])
            core = [x for x in sent_t if x not in ("[CLS]", "[SEP]", "query", ":")]
            ns = len(core)
            end = len(t) - (1 if t[-1] == "[SEP]" else 0) - (1 if s != "S1" else 0)   # S2/S3 end with a closing quote
            is_sent = [1 if (s == "S1" and x not in ("[CLS]", "[SEP]", "query", ":")) or (s != "S1" and end - ns <= j < end) else 0 for j, x in enumerate(t)]
            E["tokens"][f"{k}|{s}"] = {"tok": t, "vec": [r3(h) for h in H], "is_sent": is_sent, "mean": r3(v), "norm": round(n, 4), "unit": r3(v / n)}
    # the word "yes" on its own token vector: does context change it?
    yes = {}
    for k, i in enumerate(feat):
        for s in ("S1", "S3"):
            d = E["tokens"][f"{k}|{s}"]; js = [j for j, (x, f) in enumerate(zip(d["tok"], d["is_sent"])) if f and x.lower().strip("▁ġ") == "yes"]
            yes[f"{k}|{s}"] = np.array(d["vec"][js[-1]]) if js else None
    ref = yes["0|S1"]
    E["yes_token_cos"] = {key: (round(float(v @ ref / np.linalg.norm(v) / np.linalg.norm(ref)), 3) if v is not None else None) for key, v in yes.items()}
    # cosine between the two featured items, per state
    E["pair_cos"] = {s: round(float(V[e][f(feat[0])] @ V[e][f(feat[1])]), 3) for s, f in STATES.items()}
    E["self_cos"] = {s: [round(float(V[e][i["S1"]] @ V[e][f(i)]), 3) for i in feat] for s, f in STATES.items()}
    # step 4: the map. PCA per state on the 248 training vectors; same scale across states so a collapse shows
    y = np.array([i["y"][Q] for i in tr])
    for s, f in STATES.items():
        X = np.array([V[e][f(i)] for i in tr]); p = PCA(2, random_state=0).fit(X)
        P = p.transform(X); F = p.transform(np.array([V[e][f(i)] for i in feat]))
        C = X @ X.T; off = float(C[~np.eye(len(X), dtype=bool)].mean())
        gap = float(np.linalg.norm(X[y == 1].mean(0) - X[y == 0].mean(0))); spread = float(np.sqrt(((X - X.mean(0)) ** 2).sum(1).mean()))
        E["map"][s] = {"pts": [[round(float(a), 4), round(float(b), 4), int(t)] for (a, b), t in zip(P, y)], "feat": [[round(float(a), 4), round(float(b), 4)] for a, b in F],
                       "var": r3(p.explained_variance_ratio_), "avg_cos": round(off, 3), "gap": round(gap, 3), "spread": round(spread, 3)}
    # step 5: the head (weights x numbers + bias -> probability), for the featured items
    for s, f in list(STATES.items()) + [("split", None)]:
        if s == "split":
            X = np.array([np.concatenate([V[e][i["S1"]], V[e][sd.context_of(i, "S3")]]) for i in tr])
            XF = [np.concatenate([V[e][i["S1"]], V[e][sd.context_of(i, "S3")]]) for i in feat]
        else:
            X = np.array([V[e][f(i)] for i in tr]); XF = [V[e][f(i)] for i in feat]
        clf = LogisticRegression(C=1.0, max_iter=5000, class_weight="balanced").fit(X, y)
        w, b = clf.coef_[0], float(clf.intercept_[0])
        E["head"][s] = {"w": r3(w), "b": round(b, 3), "w_norm": round(float(np.linalg.norm(w)), 3),
                        "items": [{"x": r3(x), "contrib": r3(w * x), "score": round(float(w @ x + b), 3), "p": round(float(1 / (1 + np.exp(-(w @ x + b)))), 3)} for x in XF]}
    for s, key in (("S1", "S1 | state only"), ("S1+instr+crit", "S1 | state+instr+criteria | deep"), ("S2", "S2 | state only"), ("S3", "S3 | state only"), ("split", "S3 | split: sentence vector + context vector")):
        E["acc"][s] = {q: round(grid["cells"][f"{e} | {key} | {q}"][-1][0], 3) for q in sd.Q}
    out["enc"][e] = E
    print(e, "dim", E["dim"], "pair_cos", E["pair_cos"], "yes_token_cos", E["yes_token_cos"])
    for s, h in E["head"].items(): print(f"   head {s:14} |w|={h['w_norm']:.2f}  p(agree) for the two 'Yes.' = {[it['p'] for it in h['items']]}  truth {[i['y'][Q] for i in feat]}")
json.dump(out, open(OUT, "w"), separators=(",", ":"))
print("wrote", OUT, f"{OUT.stat().st_size / 1e6:.1f} MB")
