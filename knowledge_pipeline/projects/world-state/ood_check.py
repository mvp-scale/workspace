import json, re, glob, pickle, pathlib, random, numpy as np, scipy.sparse as sp, warnings
warnings.filterwarnings("ignore")
from model2vec import StaticModel
H0 = pathlib.Path(".").resolve(); art = pickle.load(open(H0 / "runs/expert1/expert1_v1.pkl", "rb")); sm = StaticModel.from_pretrained(art["static"]); lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
def paras(paths):
    out = []
    for f in paths:
        for b in re.split(r"\n\s*\n", open(f, encoding="utf-8", errors="ignore").read()):
            b = re.sub(r"\s+", " ", re.sub(r"[`*#|>_-]+", " ", b)).strip()
            if 120 <= len(b) <= 600: out.append(b)
    return out
docs = paras(glob.glob("../../playbook/*.md") + glob.glob("../../*.md") + glob.glob("specs/*.md") + glob.glob("../../../docs/research/*.md")[:6]); random.Random(1).shuffle(docs); docs = docs[:500]
led = [json.loads(l).get("text", "") for l in open("../../.ledger/ledger.jsonl")]; led = [re.sub(r"\s+", " ", t)[:500] for t in led if len(t) > 120]; random.Random(2).shuffle(led); led = led[:200]
def run(texts):
    h = [re.split(r"(?<=[.!?])\s", t, 1)[0] for t in texts]; E = np.hstack([sm.encode(texts), sm.encode(h)])
    xwc = sp.hstack([art["vw"].transform(texts), art["vc"].transform(texts)]).tocsr(); xt = sp.hstack([art["vt"].transform(texts), sp.csr_matrix(art["ss"].transform(E) * 0.1)]).tocsr()
    ps = art["story"].predict_proba(xwc).max(1); pt = np.sort(art["topic"].predict_proba(xt), 1)[:, -2:].sum(1); pr = 1 / (1 + np.exp(-(lg(art["ph"].predict_proba(xwc)[:, 1]) + lg(art["ps"].predict_proba(xwc)[:, 1])) / 2)); cp = np.maximum(pr, 1 - pr)
    return {"story_answered": round(float((ps >= art["cuts"]["story_type"]).mean()), 3), "topic_answered": round(float((pt >= art["cuts"]["topic_top2"]).mean()), 3), "condition_answered": round(float((cp >= art["cuts"]["condition_present"]).mean()), 3), "mean_conf": [round(float(ps.mean()), 3), round(float(pt.mean()), 3)]}
pool = [json.loads(l) for l in open("data/pool_train.jsonl")]; random.Random(3).shuffle(pool); news = [re.sub(r"\s+", " ", r["text"]) for r in pool[:500]]
res = {"n_docs": len(docs), "n_ledger": len(led), "project_docs": run(docs), "ledger_notes": run(led), "news_reference_500": run(news)}
# domain gate: news vs not-news on the same sparse features
from sklearn.linear_model import LogisticRegression; from sklearn.model_selection import cross_val_predict; from sklearn.metrics import roc_auc_score
T = news + docs + led; y = np.r_[np.ones(len(news)), np.zeros(len(docs) + len(led))]; X = sp.hstack([art["vw"].transform(T), art["vc"].transform(T)]).tocsr()
p = cross_val_predict(LogisticRegression(max_iter=500, C=3), X, y, cv=5, method="predict_proba")[:, 1]; res["domain_gate_news_vs_other_auc_cv"] = round(float(roc_auc_score(y, p)), 4)
json.dump(res, open(H0 / "runs/snapshots/ood_check.json", "w"), indent=1); print(json.dumps(res, indent=1))
