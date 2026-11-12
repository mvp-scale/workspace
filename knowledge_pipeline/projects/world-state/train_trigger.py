"""T37 step 4, pieces 1 and 2: train the event trigger tagger on the full MAVEN-FACT validation file, save it, and apply it to every labelled item text (headline + teaser).
Same features and threshold (0.4) as event_trigger_cv.py, whose 5-fold score (F1 0.76) is the only measure of the tagger; this script reports no new score.
Texts are news, not Wikipedia, and are split into sentences and words by simple rules, so the tagger runs on a different kind of text than it was scored on.
    /workspace/kev/.venv/bin/python -I train_trigger.py -> runs/expert1/event_trigger.pkl, runs/pulse/event_triggers_by_item.json"""
import json, re, pickle, time, collections
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
exec(open("event_trigger_cv.py").read().split("X, Y, G, S = [], [], [], []")[0].split("docs = [json.loads(l) for l in open(P)]")[1])  # shape() and feats()
docs = [json.loads(l) for l in open("/workspace/data/anchors/maven_fact/valid.jsonl")]
X, Y = [], []
for d in docs:
    trig = {(m["sent_id"], m["offset"][0]) for e in d["events"] for m in e["mention"]}
    for si, sent in enumerate(d["tokens"]):
        for ti, f in enumerate(feats(sent)): X.append(f); Y.append(int((si, ti) in trig))
dv = DictVectorizer(); clf = LogisticRegression(max_iter=300, C=2.0).fit(dv.fit_transform(X), np.array(Y))
pickle.dump({"dv": dv, "clf": clf, "threshold": 0.4, "trained_on": "maven_fact valid.jsonl, all 710 documents", "built": time.strftime("%Y-%m-%d")}, open("runs/expert1/event_trigger.pkl", "wb"))
print("trained on", len(Y), "tokens,", int(sum(Y)), "triggers")
SENT = re.compile(r"(?<=[.!?])\s+"); TOK = re.compile(r"\w+(?:[-']\w+)*|[^\w\s]")
txt = {}
for p in ("data/pool.jsonl", "runs/pulse/queue_texts.jsonl"):
    for l in open(p, encoding="utf-8"): r = json.loads(l); txt[r["id"]] = r["text"]
ids = sorted({json.loads(l)["item_id"] for l in open("runs/label_store/labels.jsonl")} | {json.loads(l)["item_id"] for l in open("runs/pulse/sealed/labels.jsonl")}); ids = [i for i in ids if i in txt]
out = {}; t0 = time.time()
for i in ids:
    sents = [TOK.findall(s) for s in SENT.split(txt[i]) if s.strip()]; found = []
    for sent in sents:
        if not sent: continue
        p = clf.predict_proba(dv.transform(feats(sent)))[:, 1]
        found += [sent[k].lower() for k in range(len(sent)) if p[k] >= 0.4]
    out[i] = found
json.dump(out, open("runs/pulse/event_triggers_by_item.json", "w"))
n = np.array([len(v) for v in out.values()]); print("items", len(out), "mean triggers per item", round(float(n.mean()), 2), "share with at least one", round(float((n > 0).mean()), 3), f"{time.time() - t0:.0f}s")
