"""Embedding litmus test. Run after `offline.py collect3`:  /workspace/models/embed-venv/bin/python embed_test.py
Pass lines are in EMBED-PREREG.md (written before this ran)."""
import json, time
import numpy as np
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from model2vec import StaticModel
import offline as O
from personas import gen, TRAITS

D = json.loads(O.OUT.read_text()); n = D["n"]; pers = [gen(s) for s in range(1, n + 1)]
TXT = {**O.PRODUCTS, **O.PRODUCTS2, **O.DIVERSE}
HELD = [k for k in O.DIVERSE] + O.HELD_OUT
IDEAS = [k for k in TXT if k in D["direct"]]
assert len(IDEAS) == len(TXT), "run collect3 first"
DR = {k: np.array(D["direct"][k]) for k in IDEAS}
INC = ["under $30,000", "$30,000 to $60,000", "$60,000 to $100,000", "over $100,000"]

def named(p):
    return [(p["latent"][t] - 1) / 4 for t in TRAITS] + [p["age"] < 30, p["age"] >= 60, p["area"] == "large city", p["area"] in ("rural area", "small town"),
            p["work"] == "retired", INC.index(p["income"]) / 3, p["caregiver"], p["household"] == "lives alone", "children" in p["household"], p["household"] == "lives with housemates"]
NP = np.array([named(p) for p in pers], float)
t = time.time(); m = StaticModel.from_pretrained("minishlab/potion-base-8M")
PE = m.encode([p["profile"] for p in pers]); IE = {k: m.encode([TXT[k]])[0] for k in IDEAS}; print(f"embedded {n} personas + {len(IDEAS)} ideas in {time.time()-t:.2f}s, dim {PE.shape[1]}")
ID_DEM = {k: np.array([D["idea"][k][q] for q in O.IDEA_Q]) for k in IDEAS}

# T1 raw cosine
unit = lambda x: x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-9)
cs = {k: unit(PE) @ unit(IE[k]) for k in IDEAS}
def r(a, b): return float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 1e-9 and np.std(b) > 0.02 else None
w = {k: r(cs[k], DR[k]) for k in IDEAS}; wv = [v for v in w.values() if v is not None]
print(f"T1 raw cosine vs truth: within-idea r mean {np.mean(wv):+.2f}, mean |r| {np.mean(np.abs(wv)):.2f} (over {len(wv)} ideas with spread); pooled r {np.corrcoef(np.concatenate([cs[k] for k in IDEAS]), np.concatenate([DR[k] for k in IDEAS]))[0,1]:+.2f}")

# PCA reductions (unsupervised)
K = 8
PP = PCA(K, random_state=0).fit_transform(PE); PP = (PP - PP.mean(0)) / PP.std(0)
ie = np.array([IE[k] for k in IDEAS]); IP_ = PCA(K, random_state=0).fit_transform(ie); IP_ = (IP_ - IP_.mean(0)) / (IP_.std(0) + 1e-9); IPCA = dict(zip(IDEAS, IP_))
def outer(P, v): return np.hstack([P, np.tile(v, (len(P), 1)), (P[:, :, None] * v[None, None, :]).reshape(len(P), -1)])
FEAT = {
    "A named x demands": lambda P_n, P_e, k: outer(P_n, ID_DEM[k]),
    "B embed x embed": lambda P_n, P_e, k: outer(P_e, IPCA[k]),
    "C named x idea-embed": lambda P_n, P_e, k: outer(P_n, IPCA[k]),
    "D = A + B": lambda P_n, P_e, k: np.hstack([outer(P_n, ID_DEM[k]), outer(P_e, IPCA[k])]),
}
logit = lambda p: np.log(np.clip(p, .02, .98) / (1 - np.clip(p, .02, .98)))

def evaluate(name, shuffle, seed=0):
    g = np.random.default_rng(seed)
    perm = {k: (g.permutation(n) if shuffle else np.arange(n)) for k in IDEAS}  # which persona's features are paired with row i of the truth
    X = {k: FEAT[name](NP[perm[k]], PP[perm[k]], k) for k in IDEAS}
    preds, truth, within = [], [], []
    for h in HELD:
        tr = [k for k in IDEAS if k != h]
        mdl = Ridge(alpha=3.0).fit(np.vstack([X[k] for k in tr]), np.concatenate([logit(DR[k]) for k in tr]))
        pr = 1 / (1 + np.exp(-mdl.predict(X[h]))); preds.append(pr); truth.append(DR[h])
        rr = r(pr, DR[h]); 
        if rr is not None: within.append(rr)
    P, T = np.concatenate(preds), np.concatenate(truth)
    return float(np.corrcoef(P, T)[0, 1]), float(np.mean(within)), len(within), float(np.mean(np.abs(P - T)))

print(f"\nleave-one-idea-out over {len(HELD)} held-out ideas; pooled r | mean within-idea r (n ideas with spread) | mean abs error")
res = {}
for name in FEAT:
    for sh in (False, True):
        pr, wi, nw, mae = evaluate(name, sh); res[(name, sh)] = pr
        print(f"  {name:22s} {'SHUFFLED' if sh else '        '}  pooled r {pr:+.2f} | within {wi:+.2f} ({nw}) | MAE {mae:.3f}")
print("\nT2 (B beats its shuffle by >= 0.20):", "PASS" if res[("B embed x embed", False)] - res[("B embed x embed", True)] >= 0.20 else "FAIL", round(res[("B embed x embed", False)] - res[("B embed x embed", True)], 2))
print("T3 (D beats A by >= 0.05):", "PASS" if res[("D = A + B", False)] - res[("A named x demands", False)] >= 0.05 else "FAIL", round(res[("D = A + B", False)] - res[("A named x demands", False)], 2))
print("T4 (B or C reaches A):", "PASS" if max(res[("B embed x embed", False)], res[("C named x idea-embed", False)]) >= res[("A named x demands", False)] else "FAIL",
      f"B {res[('B embed x embed', False)]:+.2f}, C {res[('C named x idea-embed', False)]:+.2f}, A {res[('A named x demands', False)]:+.2f}")
