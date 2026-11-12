"""T145 (CPU): calibrate the decider's confidence line from data. Sonnet-all sparse heads; topic confidence = top-two probability sum, correct = a two-guess hit on MN-DS fresh2 human labels (through the topic-to-IPTC map); story-type confidence = top probability, correct = agreement with Sonnet on the sealed set. For each line, the share answered and the accuracy among the answered. MN-DS is scoring only.
    /workspace/models/embed-zs/.venv/bin/python t145_calibrate_line.py (from projects/world-state) -> runs/pulse/t145/t145_calibrate_line.json"""
import json, glob, pathlib, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
OUT = pathlib.Path("runs/pulse/t145"); OUT.mkdir(parents=True, exist_ok=True); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
for f in glob.glob("runs/**/items*.jsonl", recursive=True):
    try:
        for r in J(f):
            if r.get("id") and r.get("text"): txt.setdefault(r["id"], r["text"])
    except Exception: pass
S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(S); sid = sorted(i for i in S if i in txt); RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; bt = {}; bs = {}
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]
    if r["family"] != "sonnet" or i not in txt or i in sealed: continue
    rk = RANK.get(r["version"], 2)
    if r.get("topic") and (i not in bt or rk < bt[i][0]): bt[i] = (rk, r["topic"])
    if r.get("story_type") and (i not in bs or rk < bs[i][0]): bs[i] = (rk, r["story_type"])
def fit(y, texts):
    v = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True); A = v.fit_transform(texts); return v, SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=7).fit(A, y)
ids_t = sorted(bt); ids_s = sorted(bs); vt, mt = fit(np.array([bt[i][1] for i in ids_t]), [txt[i] for i in ids_t]); vs, ms = fit(np.array([bs[i][1] for i in ids_s]), [txt[i] for i in ids_s])
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open("/workspace/data/anchors/mn_ds/gold_fresh2.json")); items = {r["id"]: r["text"] for r in J("/workspace/data/anchors/mn_ds/items_fresh2.jsonl")}; mids = [i for i in items if i in G]
P = mt.predict_proba(vt.transform([items[i][:6000] for i in mids])); ct = np.array(mt.classes_); o = np.argsort(-P, 1)[:, :2]; conf_t = np.take_along_axis(P, o, 1).sum(1)
ALIAS = {"politics": "politics and government", "religion and belief": "religion"}; norm = lambda x: ALIAS.get(x, x)
hit_t = np.array([any(norm(G[i]["l1"]) in [norm(y) for y in M.get(t, [])] or G[i]["l1"] in M.get(t, []) for t in ct[o[k]]) for k, i in enumerate(mids)])
Ps = ms.predict_proba(vs.transform([txt[i] for i in sid])); conf_s = Ps.max(1); hit_s = np.array(ms.classes_)[Ps.argmax(1)] == np.array([S[i]["story_type"] for i in sid])
def curve(conf, hit): return [{"line": round(float(t), 2), "answered_share": round(float((conf >= t).mean()), 3), "accuracy_among_answered": round(float(hit[conf >= t].mean()), 3) if (conf >= t).any() else None} for t in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)]
def line_for(conf, hit, target):
    for t in np.linspace(0.3, 0.99, 70):
        if (conf >= t).sum() >= 30 and hit[conf >= t].mean() >= target: return round(float(t), 2), round(float((conf >= t).mean()), 3)
    return None
res = {"topic": {"items": len(mids), "judge": "MN-DS fresh2 human labels, two guesses through the topic-to-IPTC map (scoring only)", "all_answered_accuracy": round(float(hit_t.mean()), 3), "curve": curve(conf_t, hit_t), "line_for_accuracy_0.80": line_for(conf_t, hit_t, 0.80), "line_for_accuracy_0.90": line_for(conf_t, hit_t, 0.90)},
       "story_type": {"items": len(sid), "judge": "sealed set, agreement with Sonnet (a teacher judge)", "all_answered_accuracy": round(float(hit_s.mean()), 3), "curve": curve(conf_s, hit_s), "line_for_accuracy_0.90": line_for(conf_s, hit_s, 0.90)}, "decider_line_now": 0.70}
json.dump(res, open(OUT / "t145_calibrate_line.json", "w"), indent=1); print(json.dumps(res, indent=1))
