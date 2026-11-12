"""Lap two free checks. (A) Base rates the advisor asked for: on the sealed set, the always-fact agreement and Cohen's kappa for v6b story type against Sonnet; on the 100 held-out articles, always-fact agreement and kappa for gist labels against full-text labels. (B) M3: a condition-presence sparse head (TF-IDF + SGD log loss) trained on Sonnet labels in the store (sealed ids excluded), scored against Sonnet on the sealed set: precision, recall, F1 at 0.5 and the always-yes F1 baseline.
    /workspace/models/embed-zs/.venv/bin/python -u lap2_checks.py   (from projects/world-state)  -> runs/pulse/lap2_checks.json"""
import json, glob, math, sys, collections
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
sys.path.insert(0, "."); from expert1_runtime import ExpertS
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
def kappa(a, b):
    a = list(a); b = list(b); n = len(a); po = sum(x == y for x, y in zip(a, b)) / n; ca = collections.Counter(a); cb = collections.Counter(b); pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n); return (po - pe) / (1 - pe) if pe < 1 else 1.0
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
for f in glob.glob("runs/**/items*.jsonl", recursive=True):
    try:
        for r in J(f):
            if r.get("id") and r.get("text"): txt.setdefault(r["id"], r["text"])
    except Exception: pass
S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sid = sorted(i for i in S if i in txt); res = {}
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); gold = [S[i]["story_type"] for i in sid]
pred = []
for i in sid:
    r = e.read(txt[i])["story_type"]; pred.append(r["answer"] if r["status"] == "answered" else "none")
fact = sum(g == "fact" for g in gold) / len(gold); acc = sum(p == g for p, g in zip(pred, gold)) / len(gold)
res["sealed_story"] = {"n": len(sid), "always_fact_agreement": round(fact, 4), "v6b_agreement": round(acc, 4), "v6b_kappa": round(kappa(pred, gold), 4)}
D = "runs/harvest/trackC_prep/"; full = json.load(open(D + "labels_heldout_full.json")); lab = {}
for k in (1, 2, 3, 4): lab.update(json.load(open(D + f"labels_part{k}.json")))
h = [x["id"] for x in json.load(open(D + "heldout_100_ids.json"))]; a = [lab[i]["story_type"] for i in h]; b = [full[i]["story_type"] for i in h]
res["heldout_story"] = {"n": len(h), "always_fact_agreement": round(sum(x == "fact" for x in b) / len(b), 4), "gist_agreement": round(sum(x == y for x, y in zip(a, b)) / len(b), 4), "gist_kappa": round(kappa(a, b), 4)}
at = [lab[i]["topic"] for i in h]; bt = [full[i]["topic"] for i in h]; mc = collections.Counter(bt).most_common(1)[0]
res["heldout_topic"] = {"commonest_label_share": round(mc[1] / len(bt), 4), "gist_agreement": round(sum(x == y for x, y in zip(at, bt)) / len(bt), 4), "gist_kappa": round(kappa(at, bt), 4)}
# M3
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; best = {}
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]
    if r["family"] != "sonnet" or i not in txt or i in S: continue
    rk = RANK.get(r["version"], 2)
    if i not in best or rk < best[i][0]: best[i] = (rk, (r.get("n_conditions") or 0) > 0)
tr = sorted(best); y = np.array([best[i][1] for i in tr]); v = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True); A = v.fit_transform([txt[i] for i in tr])
m = SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=7, class_weight="balanced").fit(A, y)
yt = np.array([bool(S[i]["conditions"]) for i in sid]); p = m.predict_proba(v.transform([txt[i] for i in sid]))[:, 1] >= 0.5
tp = int((p & yt).sum()); fp = int((p & ~yt).sum()); fn = int((~p & yt).sum()); pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1); f1 = 2 * pr * rc / max(pr + rc, 1e-9)
base = yt.mean(); f1_yes = 2 * base / (1 + base)
rng = np.random.default_rng(7); fs = []
for _ in range(500):
    ix = rng.integers(0, len(sid), len(sid)); t_, f_, n_ = int((p[ix] & yt[ix]).sum()), int((p[ix] & ~yt[ix]).sum()), int((~p[ix] & yt[ix]).sum()); a_, b_ = t_ / max(t_ + f_, 1), t_ / max(t_ + n_, 1); fs.append(2 * a_ * b_ / max(a_ + b_, 1e-9))
res["m3_condition_head"] = {"train_items": len(tr), "train_positive_share": round(float(y.mean()), 4), "sealed_n": len(sid), "sealed_positive_share": round(float(base), 4), "precision": round(pr, 4), "recall": round(rc, 4), "f1": round(f1, 4), "f1_ci95": [round(float(np.percentile(fs, 2.5)), 3), round(float(np.percentile(fs, 97.5)), 3)], "always_yes_f1": round(float(f1_yes), 4), "judge": "agreement with Sonnet, not outside truth"}
json.dump(res, open("runs/pulse/lap2_checks.json", "w"), indent=1); print(json.dumps(res))
