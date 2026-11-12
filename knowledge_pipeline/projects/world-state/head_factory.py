"""Head factory (T49): one head spec in, a trained sparse head and a four-number row out. Spec: specs/heads/<name>.json (name, kind single|presence, label_field, calibration_items, class_weight, judge, contract_confirmed). Sealed ids are always excluded from training; calibration items (random, seeded) set the confidence threshold = median on them. Reads like r6_calibrated_heads.py / lap2_checks.py, which it generalises. Writes runs/expert1/head_<name>.pkl and runs/pulse/head_<name>.json. Judge is named in the spec and repeated on the row.
    /workspace/models/embed-zs/.venv/bin/python -u head_factory.py specs/heads/story_type.json   (from projects/world-state)"""
import json, glob, math, pickle, random, sys, time
import numpy as np
from admit_mirror import stamp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
spec = json.load(open(sys.argv[1])); assert spec["kind"] in ("single", "presence"), spec["kind"]; name = spec["name"]
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
for f in glob.glob("runs/**/items*.jsonl", recursive=True):
    try:
        for r in J(f):
            if r.get("id") and r.get("text"): txt.setdefault(r["id"], r["text"])
    except Exception: pass
S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(S); sid = sorted(i for i in S if i in txt)
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; best = {}
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]
    if r["family"] != "sonnet" or i not in txt or i in sealed: continue
    v = r.get(spec["label_field"]) if spec["kind"] == "single" else (r.get("n_conditions") or 0) > 0
    if spec["kind"] == "single" and not v: continue
    rk = RANK.get(r["version"], 2)
    if i not in best or rk < best[i][0]: best[i] = (rk, v)
ids = sorted(best); rng = random.Random(20261109); rng.shuffle(ids); cal = ids[:spec.get("calibration_items", 0)]; calset = set(cal)
assert not calset & sealed, "calibration overlaps sealed"
tr = sorted(i for i in ids if i not in calset); y = np.array([best[i][1] for i in tr])
vec = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True); A = vec.fit_transform([txt[i] for i in tr])
m = SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=7, class_weight=spec.get("class_weight")).fit(A, y)
def P(X): return m.predict_proba(vec.transform(X))
thr = float(np.median(P([txt[i] for i in cal]).max(1))) if cal else 0.0
if spec["kind"] == "single": gold = np.array([S[i][spec["label_field"]] for i in sid])
else: gold = np.array([bool(S[i]["conditions"]) for i in sid])
pr = P([txt[i] for i in sid]); conf = pr.max(1); pred = np.array(m.classes_)[pr.argmax(1)] if spec["kind"] == "single" else pr[:, 1] >= 0.5
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
n = len(sid); ok = pred == gold; ans = conf >= thr; k = int((ans & ok).sum())
res = {"head": name, "kind": spec["kind"], "judge": spec["judge"], "contract_confirmed": spec["contract_confirmed"], "sealed_n": n, "train_items": len(tr), "calibration_items": len(cal), "threshold": round(thr, 3),
       "agreement_all": {"rate": round(float(ok.mean()), 4), "ci95": wil(int(ok.sum()), n)},
       "four_numbers": {"tools_alone_settle": None, "model_answers": round(float(ans.mean()), 3), "model_right_of_answered": {"rate": round(k / max(int(ans.sum()), 1), 4), "ci95": wil(k, max(int(ans.sum()), 1))}, "base_rate_most_common": round(float(max(np.mean(gold == c) for c in set(gold.tolist()))), 4), "left_for_teacher": round(float(1 - ans.mean()), 3)}}
res["admit"] = stamp(spec["judge_kind"], n, res["agreement_all"]["ci95"][0], res["agreement_all"]["ci95"][1], res["four_numbers"]["base_rate_most_common"], spec["contract_confirmed"])
if spec["kind"] == "presence":
    tp = int((pred & gold).sum()); fp = int((pred & ~gold).sum()); fn = int((~pred & gold).sum()); p_ = tp / max(tp + fp, 1); r_ = tp / max(tp + fn, 1); res["f1_at_half"] = {"precision": round(p_, 4), "recall": round(r_, 4), "f1": round(2 * p_ * r_ / max(p_ + r_, 1e-9), 4), "always_yes_f1": round(float(2 * gold.mean() / (1 + gold.mean())), 4)}
pickle.dump({"vec": vec, "model": m, "thr": thr, "spec": spec, "built": time.strftime("%Y-%m-%d"), "judge_file": f"runs/pulse/head_{name}.json"}, open(f"runs/expert1/head_{name}.pkl", "wb"))
json.dump(res, open(f"runs/pulse/head_{name}.json", "w"), indent=1); print(json.dumps(res))
