"""T161 (queued round card T148-B): topic head learning curve over the number of Sonnet-labelled rows alone (9,000, 18,000, all), no Jev rows; same held-out queue stories as T160. Derived from t160_topic_curve.py (T160, card T148-A).
"""
"""T160 (queued round card T148-A): topic head learning curve over the number of Jev topic rows added to the Sonnet-labelled rows (0, 400, 1600, all), scored by the topic abstain share (top-two mass < 0.70) on 1,000 held-out queue stories (same pool and seed as T144, none of them in training). CPU only.
    SMALL=1 for a smoke run. OUT=<folder> /workspace/models/embed-zs/.venv/bin/python -u t160_topic_curve.py -> <OUT>/t161_sonnet_curve.json"""
import os, json, glob, random, pathlib, sqlite3, time, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
SMALL = os.environ.get("SMALL") == "1"; OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t161")); OUT.mkdir(parents=True, exist_ok=True); LB = "/workspace/data/newsreader/labels/"; T0 = time.time()
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
for f in glob.glob("runs/**/items*.jsonl", recursive=True):
    try:
        for r in J(f):
            if r.get("id") and r.get("text"): txt.setdefault(r["id"], r["text"])
    except Exception: pass
jt = {}
for f in (LB + "clef-q4km.jsonl", LB + "clef-q4km-ext.jsonl"):
    for r in J(f): jt.setdefault(r["id"], (r["title"] + ". " + r["text"])[:6000])
for r in J(LB + "t135_ls_sample.jsonl"): jt[r["id"]] = (r["title"] + ". " + r["body"])[:6000]
ids144 = J(LB + "t144_ids.jsonl")
for r in ids144: jt[r["id"]] = (r["title"] + ". " + r["body"])[:6000]
fr = {r["id"] for r in J(LB + "full-read-100.jsonl")}; S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(S)
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; bt = {}; ls_ids = set()
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]; ls_ids.add(i.replace("nr:", ""))
    if r["family"] != "sonnet" or i not in txt or i in sealed or i in fr: continue
    rk = RANK.get(r["version"], 2)
    if r.get("topic") and (i not in bt or rk < bt[i][0]): bt[i] = (rk, r["topic"])
jev = {}
for r in J("runs/label_store/labels_jev_t137.jsonl"):
    if r["item_id"] in jt and r["item_id"] not in fr and r["item_id"] not in sealed and r.get("topic"): jev[r["item_id"]] = (jt[r["item_id"]], r["topic"])
for r in J(LB + "t144_read.jsonl"):
    if "error" not in r and r["id"] in jt and r["id"] not in fr and r["id"] not in sealed: jev.setdefault(r["id"], (jt[r["id"]], r["answers_call1"]["area_main"]["choice"]))
taken = set(json.loads(l)["id"] for l in open(LB + "clef-q4km.jsonl")) | ls_ids | {x["id"] for x in ids144}
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); qpool = []
for i, t, b, p in db.execute("select id,title,body,published from items where body is not null"):
    if i in taken or len(b.split()) < 80: continue
    qpool.append((t + ". " + " ".join(b.split()[:1200]))[:6000])
random.Random(145).shuffle(qpool); qheld = qpool[:200 if SMALL else 1000]
def fit(y, texts):
    v = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True); A = v.fit_transform(texts)
    return v, SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=7).fit(A, y)
ids_t = sorted(bt); JX = list(jev.values()); random.Random(160).shuffle(JX); sizes = [9000, 18000, len(ids_t)] if not SMALL else [9000, len(ids_t)]; curve = []; random.Random(161).shuffle(ids_t)
for n in sizes:
    X = [txt[i] for i in ids_t[:n]]; y = [bt[i][1] for i in ids_t[:n]]; v, m = fit(np.array(y), X)
    pt = np.sort(m.predict_proba(v.transform(qheld)), 1)[:, ::-1][:, :2].sum(1); curve.append({"sonnet_rows": n, "train_rows": len(y), "topic_abstain": round(float((pt < 0.7).mean()), 4), "seconds": round(time.time() - T0)}); print(curve[-1], flush=True)
res = {"queue_held_out_stories": len(qheld), "curve": curve, "topic_abstain_at_9000": curve[0]["topic_abstain"], "topic_abstain_at_all_rows": curve[-1]["topic_abstain"], "note": "Held-out queue stories are not in training or in the Jev rows; abstain share is a coverage measure, not accuracy."}
json.dump(res, open(OUT / "t161_sonnet_curve.json", "w"), indent=1); print(json.dumps(res))
