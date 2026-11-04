"""Owner's method: a cosine library. Every item (headline, each sentence, whole text) is scored against hundreds of generated probe sentences with a static
embedding, z-scored per probe, the inverse gap is tested, HDBSCAN looks for areas. CPU only. Run with /workspace/models/embed-zs/.venv/bin/python."""
import json, os, re, glob, pathlib, random, yaml
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.decomposition import PCA
from sklearn.cluster import HDBSCAN
from model2vec import StaticModel
H0 = pathlib.Path(__file__).resolve().parent; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
m = StaticModel.from_pretrained("minishlab/potion-base-8M"); lib = yaml.safe_load(open(H0 / ("specs/" + os.environ.get("LIB", "probe_library.yaml"))))["conditions"]; C = sorted(lib)
probes, ptype = [], []
for c in C:
    for k in ("up", "down", "inverse_up", "inverse_down", "none"):
        for t in lib[c][k]: probes.append(t); ptype.append((c, k))
unit = lambda a: a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9)
idx = {(c, k): [j for j, pt in enumerate(ptype) if pt == (c, k)] for c in C for k in ("up", "down", "inverse_up", "inverse_down", "none")}
H = {}; S = {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): H[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): S[r["item_id"]] = r["label"]
pool = {r["id"]: r["text"] for r in J(H0 / "data/pool_train.jsonl")}; ids = sorted(i for i in S if i in H)
ref_ids = random.Random(3).sample([i for i in pool if i not in set(ids)], 2000)
def units(t):
    t = re.sub(r"\s+", " ", t).strip(); ss = [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'])", t) if len(s.split()) >= 3] or [t]
    return t, ss[0], ss
PE0 = m.encode(probes)
def embed(idl):
    U, off = [], []                                                                           # unit rows: [whole, headline, sentence1..n]
    for i in idl: w, hd, ss = units(pool[i]); a = len(U); U += [w, hd] + ss; off.append((a, len(U)))
    return m.encode(U), off
Rn, Ro = embed(ref_ids); mu = Rn.mean(0); cen = lambda x: unit(x - mu); PE = cen(PE0)
def sims(E, off):                                                                              # -> per item: whole, headline, best-sentence rows over all probes
    Sm = cen(E) @ PE.T; W = np.stack([Sm[a] for a, b in off]); Hd = np.stack([Sm[a + 1] for a, b in off]); Ss = np.stack([Sm[a + 2:b].max(0) for a, b in off]); return {"all": W, "head": Hd, "sent": Ss}
R = sims(Rn, Ro); stats = {g: (R[g].mean(0), R[g].std(0) + 1e-9) for g in R}
En, Eo = embed(ids); Z = {g: (v - stats[g][0]) / stats[g][1] for g, v in sims(En, Eo).items()}
mx = lambda M, j: M[:, j].max(1)
def feats(g):
    z = Z[g]; F = {}
    for c in C:
        up, dn, iu, idn, no = (mx(z, idx[(c, k)]) for k in ("up", "down", "inverse_up", "inverse_down", "none"))
        F[c] = {"pres": np.maximum(up, dn), "pres_gap": np.maximum(up, dn) - no, "dir": up - dn, "dir_gap": (up - iu) - (dn - idn)}
    return F
cs = lambda L: {x["condition"]: x["direction"] for x in L["conditions"]}
A = {i: (cs(H[i]), cs(S[i])) for i in ids}
res = {"items": len(ids), "probes": len(probes)}; Fg = {g: feats(g) for g in Z}
for g in Z:
    for kind in ("pres", "pres_gap"):
        aucs = {}
        for c in C:
            y = np.array([1 if (c in A[i][0] and c in A[i][1]) else 0 if (c not in A[i][0] and c not in A[i][1]) else -1 for i in ids]); k = y >= 0
            if y[k].sum() >= 15: aucs[c] = float(roc_auc_score(y[k], Fg[g][c][kind][k]))
        res[f"auc_{g}_{kind}"] = {"mean": round(float(np.mean(list(aucs.values()))), 3), "n_cond": len(aucs), "ge_0.75": sum(v >= 0.75 for v in aucs.values())}
    for kind in ("dir", "dir_gap"):
        ok = n = 0
        for c in C:
            for t, i in enumerate(ids):
                if c in A[i][0] and c in A[i][1] and A[i][0][c] == A[i][1][c]: n += 1; ok += ((Fg[g][c][kind][t] > 0) == (A[i][0][c] == "up"))
        res[f"acc_{g}_{kind}"] = round(ok / max(n, 1), 3); res["direction_n"] = n
up_share = np.mean([A[i][0][c] == "up" for i in ids for c in C if c in A[i][0] and c in A[i][1] and A[i][0][c] == A[i][1][c]]); res["direction_majority_baseline_up"] = round(float(up_share), 3)
# weak answers: exactly one model names the condition. Where does the probe score fall between absent (neither) and present (both)?
g = "all"; zs = {"both": [], "neither": [], "haiku_only": [], "sonnet_only": []}
for c in C:
    for t, i in enumerate(ids):
        h, s = c in A[i][0], c in A[i][1]; zs["both" if h and s else "neither" if not h and not s else "haiku_only" if h else "sonnet_only"].append(Fg[g][c]["pres"][t])
mb, mn = np.mean(zs["both"]), np.mean(zs["neither"]); mid = (mb + mn) / 2
res["weak_answers"] = {k: {"n": len(v), "mean_z": round(float(np.mean(v)), 2), "share_above_midpoint": round(float(np.mean(np.array(v) > mid)), 3)} for k, v in zs.items()}
# HDBSCAN on presence scores of all conditions
X = np.stack([Fg["all"][c]["pres"] for c in C], 1); Xp = PCA(n_components=15, random_state=0).fit_transform((X - X.mean(0)) / (X.std(0) + 1e-9))
best = None
for mcs in (12, 25, 50):
    for ncomp in (6, 15):
        Xq = PCA(n_components=ncomp, random_state=0).fit_transform((X - X.mean(0)) / (X.std(0) + 1e-9)); lab = HDBSCAN(min_cluster_size=mcs, min_samples=5, copy=True).fit_predict(Xq); cl = []
        for k in sorted(set(lab) - {-1}):
            mem = np.where(lab == k)[0]; top = C[int(np.argmax(X[mem].mean(0)))]; pur = float(np.mean([(top in A[ids[t]][0] and top in A[ids[t]][1]) for t in mem]))
            cl.append({"cluster": int(k), "size": int(len(mem)), "top_condition": top, "share_both_models_name_it": round(pur, 3)})
        row = {"min_cluster_size": mcs, "pca": ncomp, "clusters": len(cl), "noise_share": round(float(np.mean(lab == -1)), 3), "top": sorted(cl, key=lambda r: -r["share_both_models_name_it"])[:6]}
        if best is None or (len(cl) >= 3 and row["noise_share"] < best["noise_share"]) or (best["clusters"] < 3 and len(cl) > best["clusters"]): best = row
res["hdbscan"] = best
(H0 / "runs/cosinelib").mkdir(exist_ok=True); json.dump(res, open(H0 / ("runs/cosinelib/" + os.environ.get("OUT", "yield.json")), "w"), indent=1); print(json.dumps(res, indent=1))
