"""T7: improvement loop with snapshots. Batches by date; train on <=k, score unseen k+1. Run with /workspace/models/embed-zs/.venv/bin/python loop.py"""
import json, glob, re, pathlib, warnings, urllib.parse
warnings.filterwarnings("ignore")
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score, brier_score_loss
from model2vec import StaticModel
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hk, sn = {}, {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; ids = sorted(hk)
F = np.load(H0 / "runs/structure/feat_all.npz", allow_pickle=True)["F"]
txt = [re.sub(r"\s+", " ", pool[i]["text"]) for i in ids]
head = [re.split(r"(?<=[.!?])\s", t, 1)[0] for t in txt]                       # headline = first sentence, any sentence end (fixes the emoji split flaw)
def src(i):
    if i.startswith("cc:"): return urllib.parse.urlparse(i[3:]).netloc.replace("www.", "")
    if i.startswith("nq:"): return (pool[i].get("from") or "").split(":", 1)[-1]
    return "nr"
S = np.array([src(i) for i in ids]); dt = np.array([pool[i]["date"] or "" for i in ids]); keep = dt != ""
m = StaticModel.from_pretrained("minishlab/potion-base-8M"); E = m.encode(txt); EH = m.encode(head)
y = np.array([1 if hk[i]["conditions"] else 0 for i in ids]); sy = np.array([1 if (i in sn and sn[i]["conditions"]) else 0 for i in ids]); voted = np.array([i in sn for i in ids])
order = np.argsort(dt, kind="stable"); order = order[keep[order]]; B = np.array_split(order, 5)
def src_rate(tr, idx, mm=20):                                                    # smoothed per-outlet positive rate learned on train only
    g = y[tr].mean(); d = {}
    for s in np.unique(S[tr]): k = tr[S[tr] == s]; d[s] = (y[k].sum() + mm * g) / (len(k) + mm)
    r = np.array([d.get(s, g) for s in S[idx]]); return np.log(r / (1 - r))[:, None]
def fit(tr, te, kind):
    parts = {"base": lambda idx, tr_: np.hstack([F[idx], E[idx]]), "head": lambda idx, tr_: np.hstack([F[idx], EH[idx]]), "srcprior": lambda idx, tr_: np.hstack([F[idx], E[idx], src_rate(tr_, idx)]), "both": lambda idx, tr_: np.hstack([F[idx], E[idx], EH[idx]])}
    mdl = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, C=0.1)).fit(parts[kind](tr, tr), y[tr]); p = mdl.predict_proba(parts[kind](te, tr))[:, 1]; return p
def sel_agree(te, p):                                                            # student vs Sonnet on the voted slice, all vs the more confident half
    v = te[voted[te]]
    if len(v) < 50: return None
    pv = p[np.isin(te, v)]; c = np.maximum(pv, 1 - pv); o = np.argsort(-c); a = ((pv > .5).astype(int) == sy[v])[o]
    return {"all": round(float(a.mean()), 3), "top_half": round(float(a[:len(a) // 2].mean()), 3), "n": int(len(v))}
res = {"batches": [len(b) for b in B], "date_edges": [[dt[b[0]], dt[b[-1]]] for b in B], "curve": {}, "levers_k4": {}, "window": {}}
for k in range(1, 5):
    tr = np.concatenate(B[:k]); te = B[k]; p = fit(tr, te, "base")
    res["curve"][f"v{k}"] = {"train_n": int(len(tr)), "auc": round(float(roc_auc_score(y[te], p)), 4), "brier": round(float(brier_score_loss(y[te], p)), 4), "sonnet": sel_agree(te, p)}
    json.dump(res["curve"][f"v{k}"], open(H0 / f"runs/snapshots/v{k}.json", "w"), indent=1)
tr = np.concatenate(B[:4]); te = B[4]
for kind in ("base", "head", "srcprior", "both"):
    p = fit(tr, te, kind); res["levers_k4"][kind] = {"auc": round(float(roc_auc_score(y[te], p)), 4), "brier": round(float(brier_score_loss(y[te], p)), 4)}
    if kind == "head":                                                           # headline-first gate: skip share at 95% recall of positives
        o = np.argsort(-p); cum = np.cumsum(y[te][o]) / y[te].sum(); res["levers_k4"][kind]["skip_share_at_95_recall"] = round(float(1 - (np.argmax(cum >= .95) + 1) / len(te)), 3)
    if kind == "base":
        o = np.argsort(-p); cum = np.cumsum(y[te][o]) / y[te].sum(); res["levers_k4"][kind]["skip_share_at_95_recall"] = round(float(1 - (np.argmax(cum >= .95) + 1) / len(te)), 3)
for name, trw in (("all_prior", np.concatenate(B[:4])), ("latest_two", np.concatenate(B[2:4])), ("latest_one", B[3])):
    p = fit(trw, te, "base"); res["window"][name] = {"train_n": int(len(trw)), "auc": round(float(roc_auc_score(y[te], p)), 4)}
json.dump(res, open(H0 / "runs/snapshots/loop_results.json", "w"), indent=1); print(json.dumps(res, indent=1), flush=True)
