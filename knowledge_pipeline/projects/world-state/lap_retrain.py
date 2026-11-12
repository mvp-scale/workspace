"""First-lap step 4 on CPU: retrain the two sparse heads with the new weak gist labels attached to the FULL text of those articles, and score against the same outside judges as before (paired with the same recipe without the new rows).
Topic: MN-DS fresh 1,600 human labels, two guesses (round1_cascade.py recipe). Story type: sealed set, agreement with Sonnet (round2_story_cascade.py recipe). MN-DS and the sealed ids are never in the training rows.
Writes runs/pulse/lap_retrain.json.   /workspace/models/embed-zs/.venv/bin/python -u lap_retrain.py   (from projects/world-state)"""
import json, glob, math, time, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
for f in glob.glob("runs/**/items*.jsonl", recursive=True):
    try:
        for r in J(f):
            if r.get("id") and r.get("text"): txt.setdefault(r["id"], r["text"])
    except Exception: pass
S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(S); sid = sorted(i for i in S if i in txt)
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; bt = {}; bs = {}
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]
    if r["family"] != "sonnet" or i not in txt or i in sealed: continue
    rk = RANK.get(r["version"], 2)
    if r.get("topic") and (i not in bt or rk < bt[i][0]): bt[i] = (rk, r["topic"])
    if r.get("story_type") and (i not in bs or rk < bs[i][0]): bs[i] = (rk, r["story_type"])
full = {}
for l in open("runs/harvest/sample.jsonl"):
    r = json.loads(l); full["cc:" + (r.get("url") or "")] = ((r.get("title") or "") + ". " + (r.get("text") or ""))[:6000]
new = J("runs/label_store/labels_ws_gist_v1.jsonl"); new = [r for r in new if r["item_id"] in full and r["item_id"] not in sealed]
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json"))
mn = {x["id"]: x["text"] for x in J("/workspace/data/anchors/mn_ds/items_T28b.jsonl")}; mids = [i for i in mn if i in G]
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
def fit(ids, y, texts):
    v = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True); A = v.fit_transform(texts)
    return v, SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=7).fit(A, y)
res = {"new_rows": len(new), "judge_topic": "MN-DS human labels, 1,600 fresh, two guesses", "judge_story": "agreement with Sonnet, sealed set", "variants": {}}
for name, add in (("without_new_rows", False), ("with_new_rows", True)):
    tt = sorted(bt); Xt = [txt[i] for i in tt]; yt = [bt[i][1] for i in tt]; ts = sorted(bs); Xs = [txt[i] for i in ts]; ys = [bs[i][1] for i in ts]
    if add: Xt += [full[r["item_id"]] for r in new]; yt += [r["topic"] for r in new]; Xs += [full[r["item_id"]] for r in new]; ys += [r["story_type"] for r in new]
    t0 = time.time(); vt, mt = fit(None, np.array(yt), Xt); vs, ms = fit(None, np.array(ys), Xs); fit_s = round(time.time() - t0)
    Pt = mt.predict_proba(vt.transform([mn[i] for i in mids])); ct = np.array(mt.classes_); o = np.argsort(-Pt, 1)[:, :2]
    hit = sum(any(G[i]["l1"] in M.get(t, []) for t in ct[o[k]]) for k, i in enumerate(mids))
    Ps = ms.predict_proba(vs.transform([txt[i] for i in sid])); pr = np.array(ms.classes_)[Ps.argmax(1)]; sh = int(sum(pr[k] == S[i]["story_type"] for k, i in enumerate(sid)))
    res["variants"][name] = {"train_topic": len(yt), "train_story": len(ys), "fit_seconds": fit_s, "topic_two_guess_mnds": {"rate": round(hit / len(mids), 4), "ci95": wil(hit, len(mids))}, "story_agree_sealed": {"rate": round(sh / len(sid), 4), "ci95": wil(sh, len(sid))}}
    print(name, res["variants"][name], flush=True)
json.dump(res, open("runs/pulse/lap_retrain.json", "w"), indent=1)
