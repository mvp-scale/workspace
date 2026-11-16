"""T233 (plan T148-N1): is a raw neighbour-vote percentage comparable across stories, and does normalising it give a better cutoff?
Reference set = Sonnet topic labels (49 topics, runs/label_store/labels.jsonl, sonnet ws-v2-frozen and ws-v3b-nosize) of items whose text can be found: nr: and nq: ids in /workspace/data/newsreader/queue.sqlite (id without prefix), cc: ids in /workspace/data/ccnews/raw/plain_text (url = id[3:]).
Text seen = first 300 characters (title + teaser, or the opening of the body). Embedding bge-small. Random 70/30 split; queries with a nearest reference neighbour at cosine >= DEDUP are dropped (syndicated copies); both reported.
Scores for 'the top-1 label is right (agrees with Sonnet)': raw vote share, z-score of the top vote against the other labels' votes, density-adjusted share, and a logistic combination (2-fold cross-fit). Metrics: AUROC, coverage at precision PREC (threshold fitted on one half of the queries, scored on the other), and accuracy by density quartile inside a fixed raw-share band.
    LIMIT=<items> K=20 TAU=0.05 DEDUP=0.92 PREC=0.90 OUT=runs/pulse/t233 /workspace/models/embed-zs/.venv/bin/python -u t233_knn_norm.py"""
import os, sys, json, glob, sqlite3, collections, random
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
LIMIT = int(os.environ.get("LIMIT", 10**9)); K = int(os.environ.get("K", 20)); TAU = float(os.environ.get("TAU", 0.05)); DEDUP = float(os.environ.get("DEDUP", 0.92)); PREC = float(os.environ.get("PREC", 0.90))
OUT = os.environ.get("OUT", "runs/pulse/t233"); os.makedirs(OUT, exist_ok=True)
lab = collections.defaultdict(list)
for l in open("runs/label_store/labels.jsonl"):
    r = json.loads(l)
    if r["family"] == "sonnet" and r["version"] in ("ws-v2-frozen", "ws-v3b-nosize") and r.get("topic"): lab[r["item_id"]].append(r["topic"])
eng = {x["id"] for x in json.load(open("/workspace/exports/world-engine-ontology-rules_v2.json"))["topics"]}
lab = {i: collections.Counter(v).most_common(1)[0][0] for i, v in lab.items() if collections.Counter(v).most_common(1)[0][0] in eng}
ids = sorted(lab); random.Random(1).shuffle(ids); ids = ids[:LIMIT]; text = {}
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
for i in ids:
    if i.startswith(("nr:", "nq:")):
        q = db.execute("select title, teaser from items where id=?", (i[3:],)).fetchone()
        if q and ((q[0] or "") + (q[1] or "")).strip(): text[i] = ((q[0] or "") + ". " + (q[1] or "")).strip()[:300]
cc = {i[3:]: i for i in ids if i.startswith("cc:")}
for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet")):
    t = pq.read_table(f, columns=["url", "text"]); mk = pc.is_in(t["url"], value_set=pa.array(list(cc)))
    for u, x in zip(t["url"].filter(mk).to_pylist(), t["text"].filter(mk).to_pylist()):
        if x and x.strip(): text[cc[u]] = x.strip().replace("\n", " ")[:300]
ids = [i for i in ids if i in text]; y = np.array([lab[i] for i in ids]); classes = sorted(set(y)); ci = {c: k for k, c in enumerate(classes)}; yi = np.array([ci[c] for c in y])
print("items with text", len(ids), "classes", len(classes), flush=True)
m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 96
E = m.encode([text[i] for i in ids], batch_size=128, normalize_embeddings=True, convert_to_numpy=True).astype(np.float32); print("embedded", E.shape, flush=True)
np.save(OUT + "/emb.npy", E); json.dump({"ids": ids, "labels": list(y)}, open(OUT + "/items.json", "w"))
n = len(ids); perm = np.random.default_rng(3).permutation(n); ref = perm[: int(0.7 * n)]; qry = perm[int(0.7 * n):]
R = E[ref]; yr = yi[ref]; feats = []; correct = []; keep = []
for s in range(0, len(qry), 1000):
    b = qry[s:s + 1000]; S = E[b] @ R.T; top = np.argpartition(-S, K, axis=1)[:, :K]
    for r_, row in enumerate(top):
        o = row[np.argsort(-S[r_, row])]; sims = S[r_, o]; w = np.exp((sims - sims[0]) / TAU); votes = np.zeros(len(classes)); np.add.at(votes, yr[o], w); votes /= votes.sum()
        order = np.argsort(-votes); p1, p2 = votes[order[0]], votes[order[1]]; z = (p1 - votes.mean()) / (votes.std() + 1e-9)
        dens = float(sims.mean()); feats.append([p1, z, dens, p1 - p2, float(sims[0])]); correct.append(int(order[0] == yi[b[r_]])); keep.append(float(sims[0]))
F = np.array(feats); c = np.array(correct); top1 = F[:, 4]
def cov_at(score, c, prec, fit_idx, test_idx):
    o = fit_idx[np.argsort(-score[fit_idx])]; run = np.cumsum(c[o]) / np.arange(1, len(o) + 1); ok = np.where(run >= prec)[0]
    if len(ok) == 0: return 0.0, None, None
    thr = score[o[ok[-1]]]; sel = test_idx[score[test_idx] >= thr]; return float(len(sel) / len(test_idx)), (float(c[sel].mean()) if len(sel) else None), float(thr)
def evaluate(mask, tag):
    idx = np.where(mask)[0]; rng = np.random.default_rng(5); rng.shuffle(idx); h = len(idx) // 2; A, B = idx[:h], idx[h:]
    p1, z, dens, mar = F[:, 0], F[:, 1], F[:, 2], F[:, 3]; adj = p1 - (dens - dens[idx].mean()) * 0.0
    lr_scores = np.zeros(len(F))
    for tr, te in ((A, B), (B, A)): lr_scores[te] = LogisticRegression(max_iter=2000).fit(F[tr][:, :4], c[tr]).predict_proba(F[te][:, :4])[:, 1]
    sc = {"raw_share": p1, "z_score": z, "density_only": dens, "margin": mar, "logistic_combo": lr_scores}
    out = {"queries": int(len(idx)), "top1_agreement_with_sonnet": float(c[idx].mean()), "auroc": {k: float(roc_auc_score(c[idx], v[idx])) for k, v in sc.items()}, "coverage_at_precision": {}}
    for k, v in sc.items():
        if k == "logistic_combo": cv, pr, _ = cov_at(v, c, PREC, idx, idx)
        else:
            c1 = cov_at(v, c, PREC, A, B); c2 = cov_at(v, c, PREC, B, A); cv = (c1[0] + c2[0]) / 2; pr = np.mean([x for x in (c1[1], c2[1]) if x is not None]) if (c1[1] is not None or c2[1] is not None) else None
        out["coverage_at_precision"][k] = {"coverage": cv, "precision": None if pr is None else float(pr)}
    band = idx[(p1[idx] >= 0.60) & (p1[idx] < 0.70)]
    if len(band) >= 40:
        qs = np.quantile(dens[band], [0.25, 0.5, 0.75]); gq = np.digitize(dens[band], qs); out["raw_share_band_0.60_0.70"] = {"n": int(len(band)), "accuracy_by_density_quartile": [float(c[band][gq == g].mean()) for g in range(4)], "n_by_quartile": [int((gq == g).sum()) for g in range(4)]}
        out["raw_share_band_0.60_0.70"]["spread"] = max(out["raw_share_band_0.60_0.70"]["accuracy_by_density_quartile"]) - min(out["raw_share_band_0.60_0.70"]["accuracy_by_density_quartile"])
        lb = band[(lr_scores[band] >= np.quantile(lr_scores[idx], 0.45)) & (lr_scores[band] <= np.quantile(lr_scores[idx], 0.65))]
    bins = np.quantile(lr_scores[idx], [0.45, 0.65]); sub = idx[(lr_scores[idx] >= bins[0]) & (lr_scores[idx] <= bins[1])]
    if len(sub) >= 40:
        qs = np.quantile(dens[sub], [0.25, 0.5, 0.75]); gq = np.digitize(dens[sub], qs); acc = [float(c[sub][gq == g].mean()) for g in range(4)]
        out["calibrated_score_middle_band"] = {"n": int(len(sub)), "accuracy_by_density_quartile": acc, "spread": max(acc) - min(acc)}
    return out
res = {"items": n, "reference": int(len(ref)), "queries": int(len(qry)), "k": K, "tau": TAU, "text_seen": "first 300 characters", "label": "Sonnet topic (system label)"}
res["all_queries"] = evaluate(np.ones(len(F), bool), "all"); res[f"dedup_below_{DEDUP}"] = evaluate(top1 < DEDUP, "dedup")
json.dump(res, open(OUT + "/t233_knn_norm.json", "w"), indent=1); print(json.dumps(res, indent=1))
