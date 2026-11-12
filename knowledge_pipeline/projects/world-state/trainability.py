"""Trainability survey (T51): per head, label source and counts, and sealed-set score of a text-only sparse head versus text plus tool-evidence features (runs/harvest/pool_v2/labelled.jsonl), paired on the same items. Judge: agreement with Sonnet, not outside truth. Heads with no labels are listed, not scored. Same split rules as head_factory.py (sealed ids never train).
    /workspace/models/embed-zs/.venv/bin/python -u trainability.py  -> runs/pulse/trainability_matrix.json"""
import json, glob, collections
import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(S)
EV = {}
for r in J("runs/harvest/pool_v2/labelled.jsonl") + J("runs/harvest/pool_v2/sealed_evidence.jsonl"):
    d = collections.Counter()
    for x in r["items"]: d[f'{x["tool"]}|{x["kind"]}|{x["strength"]}'] += 1
    EV[r["item_id"]] = {k: float(np.log1p(v)) for k, v in d.items()}
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; best = {}; fam = collections.defaultdict(dict)
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]; fam[r["family"]].setdefault(i, r)
    if r["family"] != "sonnet" or i not in txt or i in sealed or i not in EV: continue
    rk = RANK.get(r["version"], 2)
    if i not in best or rk < best[i][0]: best[i] = (rk, r)
tr = sorted(best); sid = sorted(i for i in S if i in txt and i in EV)
HEADS = {"topic": (lambda r: r.get("topic"), lambda l: l["topic"]), "story_type": (lambda r: r.get("story_type"), lambda l: l["story_type"]),
         "condition_presence": (lambda r: (r.get("n_conditions") or 0) > 0, lambda l: bool(l["conditions"]))}
vt = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True); At = vt.fit_transform([txt[i] for i in tr]); Bt = vt.transform([txt[i] for i in sid])
dv = DictVectorizer(); Ae = dv.fit_transform([EV[i] for i in tr]); Be = dv.transform([EV[i] for i in sid])
import os; EVS = float(os.environ.get("EVSCALE", "1")); Xa, Xb = hstack([At, Ae * EVS]).tocsr(), hstack([Bt, Be * EVS]).tocsr()
rng = np.random.default_rng(7); out = {"judge": "agreement with Sonnet on the sealed set, not outside truth", "train_items": len(tr), "sealed_items_with_evidence": len(sid), "evidence_features": len(dv.feature_names_), "heads": {}}
def fit(A, y, cw): return SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=7, class_weight=cw).fit(A, y)
for name, (get, gold) in HEADS.items():
    y = np.array([get(best[i][1]) for i in tr]); g = np.array([gold(S[i]) for i in sid]); cw = "balanced" if name == "condition_presence" else None; cnt = collections.Counter(y.tolist())
    res = {}
    for tag, A, B in (("text_only", At, Bt), ("text_plus_evidence", Xa, Xb)):
        m = fit(A, y, cw); p = m.predict(B)
        if name == "topic": pr = m.predict_proba(B); top2 = np.array(m.classes_)[np.argsort(-pr, 1)[:, :2]]; res[tag + "_top2"] = np.array([g[k] in top2[k] for k in range(len(g))])
        res[tag] = p
    ok = lambda p: p == g
    def f1(p, ix):
        tp = (p[ix] & g[ix]).sum(); fp = (p[ix] & ~g[ix]).sum(); fn = (~p[ix] & g[ix]).sum(); pr_ = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1); return 2 * pr_ * rc / max(pr_ + rc, 1e-9)
    n = len(g); B_ = [rng.integers(0, n, n) for _ in range(500)]; row = {"train_items": len(y), "classes": len(cnt), "smallest_class": min(cnt.values()), "largest_class_share": round(max(cnt.values()) / len(y), 4)}
    if name == "condition_presence":
        a, b = res["text_only"], res["text_plus_evidence"]; ix = np.arange(n); row["text_only"] = round(float(f1(a, ix)), 4); row["text_plus_evidence"] = round(float(f1(b, ix)), 4); d = [f1(b, i) - f1(a, i) for i in B_]; metric = "F1"
    else:
        a, b = ok(res["text_only"]), ok(res["text_plus_evidence"]); row["text_only"] = round(float(a.mean()), 4); row["text_plus_evidence"] = round(float(b.mean()), 4); d = [b[i].mean() - a[i].mean() for i in B_]; metric = "agreement"
        if name == "topic": a2, b2 = res["text_only_top2"], res["text_plus_evidence_top2"]; row["top2_text_only"] = round(float(a2.mean()), 4); row["top2_text_plus_evidence"] = round(float(b2.mean()), 4); row["top2_delta_ci95"] = [round(float(np.percentile([b2[i].mean() - a2[i].mean() for i in B_], q)), 4) for q in (2.5, 97.5)]
    row["metric"] = metric; row["delta"] = round(row["text_plus_evidence"] - row["text_only"], 4); row["delta_ci95"] = [round(float(np.percentile(d, 2.5)), 4), round(float(np.percentile(d, 97.5)), 4)]; row["evidence_helps"] = row["delta_ci95"][0] > 0
    sk = fam["haiku"]; both = [i for i in best if i in sk]; row["teacher_haiku_vs_sonnet_agreement"] = round(float(np.mean([get(sk[i]) == get(best[i][1]) for i in both])), 4); row["teacher_overlap_items"] = len(both)
    out["heads"][name] = row
inv = {"kinds_labelled_items": sum(1 for r in fam["sonnet"].values() if r.get("kinds")), "size_level_field": "max_level (Sonnet items with a value: %d)" % sum(1 for r in fam["sonnet"].values() if r.get("max_level") is not None)}
out["other_label_inventory"] = inv
out["untrainable_no_labels"] = {"area": "no Area labels; needs the owner's named Areas (T48 decision 3)", "capability": "no Capability labels; needs the owner's named Capabilities (T48 decision 3)", "novelty": "defined as matching no Area; waits on Areas", "understanding_claims_alignment_trace": "no labels in the store; only triples with CaRB-style scoring exist"}
out["evidence_scale"] = EVS; json.dump(out, open("runs/pulse/trainability_matrix.json" if EVS == 1 else "runs/pulse/trainability_matrix_scale%s.json" % EVS, "w"), indent=1); print(json.dumps(out, indent=1))
