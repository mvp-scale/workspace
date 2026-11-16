"""T223 (Opus plan Wave 0, Place): score the saved Place student (runs/pulse/t200/place_student.pkl) on N queue stories it was not fitted on, against the text-derived place judge (t167: most mentioned country in title+body, decidable when 2+ mentions and 60%+ one country). Judge and student both read country-name cues, so this is a proxy check, not a human one.
    N=1000 OUT=runs/pulse/t223 /workspace/models/embed-zs/.venv/bin/python -u t223_place_fresh.py -> <OUT>/t223_place_fresh.json"""
import os, json, pickle, random, sqlite3, runpy, collections
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np
from sentence_transformers import SentenceTransformer
N = int(os.environ.get("N", 1000)); OUT = os.environ.get("OUT", "runs/pulse/t223"); os.makedirs(OUT, exist_ok=True)
g = runpy.run_path("t167_place_judge.py"); PAT, names, region = g["PAT"], g["names"], g["region"]; trained = {r["id"] for r in g["rows"]}
S = pickle.load(open("runs/pulse/t200/place_student.pkl", "rb")); classes, line = S["classes"], S["line"]
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
ids = [r[0] for r in db.execute("select id from items where body is not null and length(body) > 200")]; ids = [i for i in ids if i not in trained]
random.seed(23); pick = random.sample(ids, min(N, len(ids)))
rows = {i: db.execute("select title, body from items where id=?", (i,)).fetchone() for i in pick}
m = SentenceTransformer("intfloat/e5-small-v2", device="cpu"); m.max_seq_length = 128
X = m.encode(["query: " + ((rows[i][0] or "") + ". " + rows[i][1])[:1500] for i in pick], batch_size=64, normalize_embeddings=True, convert_to_numpy=True)
P = S["model"].predict_proba(X); conf = P.max(1); pred = [classes[k] for k in P.argmax(1)]; ans = conf >= line
truth = []
for i in pick:
    t = (rows[i][0] or "") + ". " + rows[i][1]; cnt = collections.Counter(names[x.lower()] for x in PAT.findall(t)); tot = sum(cnt.values()); tr = None
    if tot >= 2:
        cc, n = cnt.most_common(1)[0]
        if n / tot >= 0.6: tr = region(cc)
    truth.append(tr)
dec = np.array([t is not None for t in truth]); ok = np.array([p == t for p, t in zip(pred, truth)])
rng = np.random.default_rng(1); sel = np.where(dec & ans)[0]; boots = [float(ok[rng.choice(sel, len(sel))].mean()) for _ in range(1000)] if len(sel) else [0]
maj = collections.Counter(t for t in truth if t).most_common(1)[0]
res = {"stories": len(pick), "excluded_trained_ids": len(trained), "line": line, "answered_share": float(ans.mean()), "decidable": int(dec.sum()), "decidable_answered": int((dec & ans).sum()),
       "accuracy_answered_decidable": float(ok[dec & ans].mean()) if (dec & ans).any() else None, "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
       "accuracy_unanswered_decidable": float(ok[dec & ~ans].mean()) if (dec & ~ans).any() else None, "majority_baseline": {"class": maj[0], "accuracy_all_decidable": maj[1] / int(dec.sum())},
       "prior_in_sample_line_result": "0.914 on 499 decidable answered stories (L2396)"}
json.dump(res, open(OUT + "/t223_place_fresh.json", "w"), indent=1); print(json.dumps(res, indent=1))
