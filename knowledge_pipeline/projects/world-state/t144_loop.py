"""T144 (CPU): the targeted loop, adapted from lap_retrain.py and t143. PHASE=select: train the Sonnet-all sparse heads, find the queue stories they abstain on (topic top-two sum or story-type top probability below 0.70, the decider's line), write 800 targeted (abstained) and 800 random queue stories to an ids file for a Jev call-1 read. PHASE=eval: retrain with the Jev rows of each arm and measure the held-out abstain share and outside-truth scores on MN-DS fresh2 (scoring only).
    PHASE=select|eval /workspace/models/embed-zs/.venv/bin/python -u t144_loop.py (from projects/world-state) -> runs/pulse/t144/"""
import json, glob, math, time, os, random, pathlib, sqlite3, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
PH = os.environ.get("PHASE", "select"); OUT = pathlib.Path("runs/pulse/t144"); OUT.mkdir(parents=True, exist_ok=True); IDS = "/workspace/data/newsreader/labels/t144_ids.jsonl"; ROWS = "/workspace/data/newsreader/labels/t144_read.jsonl"
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
for f in glob.glob("runs/**/items*.jsonl", recursive=True):
    try:
        for r in J(f):
            if r.get("id") and r.get("text"): txt.setdefault(r["id"], r["text"])
    except Exception: pass
S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(S); sid = sorted(i for i in S if i in txt)
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; bt = {}; bs = {}; ls_ids = set()
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]; ls_ids.add(i.replace("nr:", ""))
    if r["family"] != "sonnet" or i not in txt or i in sealed: continue
    rk = RANK.get(r["version"], 2)
    if r.get("topic") and (i not in bt or rk < bt[i][0]): bt[i] = (rk, r["topic"])
    if r.get("story_type") and (i not in bs or rk < bs[i][0]): bs[i] = (rk, r["story_type"])
def fit(y, texts):
    v = TfidfVectorizer(ngram_range=(1, 2), min_df=3 if len(texts) > 2000 else 2, max_features=150000, sublinear_tf=True); A = v.fit_transform(texts)
    return v, SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=7).fit(A, y)
def abstain(vt, mt, vs, ms, texts):
    pt = np.sort(mt.predict_proba(vt.transform(texts)), 1)[:, ::-1][:, :2].sum(1); ps = ms.predict_proba(vs.transform(texts)).max(1); return (pt < 0.7) | (ps < 0.7), pt < 0.7, ps < 0.7
ids_t = sorted(bt); ids_s = sorted(bs); rng = random.Random(144)
if PH == "select":
    taken = set(json.loads(l)["id"] for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl")) | ls_ids
    db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); pool = []
    for i, t, b, p in db.execute("select id,title,body,published from items where body is not null"):
        if i in taken or len(b.split()) < 80: continue
        pool.append({"id": i, "title": t, "body": " ".join(b.split()[:1200]), "published": p})
    rng.shuffle(pool); pool = pool[:6000]
    vt, mt = fit(np.array([bt[i][1] for i in ids_t]), [txt[i] for i in ids_t]); vs, ms = fit(np.array([bs[i][1] for i in ids_s]), [txt[i] for i in ids_s])
    ab, abt, abs_ = abstain(vt, mt, vs, ms, [(r["title"] + ". " + r["body"])[:6000] for r in pool])
    tgt = [r for r, a in zip(pool, ab) if a]; rng.shuffle(tgt); tgt = tgt[:800]; used = {r["id"] for r in tgt}; rnd = [r for r in pool if r["id"] not in used]; rng.shuffle(rnd); rnd = rnd[:800]
    open(IDS, "w").write("\n".join(json.dumps({"set": arm, **r}) for arm, L in (("targeted", tgt), ("random", rnd)) for r in L))
    json.dump({"pool": len(pool), "pool_abstain_share_either": round(float(ab.mean()), 3), "pool_topic_abstain": round(float(abt.mean()), 3), "pool_story_abstain": round(float(abs_.mean()), 3), "targeted": len(tgt), "random": len(rnd)}, open(OUT / "t144_select.json", "w"), indent=1); print(open(OUT / "t144_select.json").read())
else:
    M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json")); mn = {x["id"]: x["text"] for x in J("/workspace/data/anchors/mn_ds/items_T28b.jsonl")}; mids = [i for i in mn if i in G]
    held = [r["text"][:6000] for r in J("/workspace/data/anchors/mn_ds/items_fresh2.jsonl")[:600]]
    rows = J(ROWS); arms = {}
    for r in rows:
        if "error" in r: continue
        a = r["answers_call1"]; po, pp = a["function_opinion"]["noul"], a["function_prediction"]["noul"]; st = "opinion" if po >= 0.5 and po >= pp else "forecast" if pp >= 0.5 else "fact"
        arms.setdefault(r["set"], []).append({"text": (r["title"] + ". " + r.get("body", ""))[:6000] if r.get("body") else None, "id": r["id"], "topic": a["area_main"]["choice"], "story_type": st})
    body = {x["id"]: (x["title"] + ". " + x["body"])[:6000] for x in J(IDS)}
    for k in arms:
        for x in arms[k]: x["text"] = body[x["id"]]
    taken_ = set(json.loads(l)["id"] for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl")) | ls_ids | {x["id"] for x in J(IDS)}
    _db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); qpool = []
    for i, t, b, p in _db.execute("select id,title,body,published from items where body is not null"):
        if i in taken_ or len(b.split()) < 80: continue
        qpool.append((t + ". " + " ".join(b.split()[:1200]))[:6000])
    random.Random(145).shuffle(qpool); qheld = qpool[:1000]
    res = {"queue_held_out_stories": len(qheld), "rows": {k: len(v) for k, v in arms.items()}, "held_out": "MN-DS fresh2 first 600, scoring only", "variants": {}}
    def wil(k, n, z=1.96):
        p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
    for name, add in (("C_sonnet_all", []), ("C_plus_targeted_jev", arms.get("targeted", [])), ("C_plus_random_jev", arms.get("random", [])), ("C_plus_targeted_jev_topic_only", arms.get("targeted", [])), ("C_plus_random_jev_topic_only", arms.get("random", [])), ("C_plus_both_jev_topic_only", arms.get("targeted", []) + arms.get("random", []))):
        Xt = [txt[i] for i in ids_t] + [x["text"] for x in add]; yt = [bt[i][1] for i in ids_t] + [x["topic"] for x in add]; sadd = [] if name.endswith("topic_only") else add; Xs = [txt[i] for i in ids_s] + [x["text"] for x in sadd]; ys = [bs[i][1] for i in ids_s] + [x["story_type"] for x in sadd]
        vt, mt = fit(np.array(yt), Xt); vs, ms = fit(np.array(ys), Xs); ab, abt, abs_ = abstain(vt, mt, vs, ms, held)
        Pt = mt.predict_proba(vt.transform([mn[i] for i in mids])); ct = np.array(mt.classes_); o = np.argsort(-Pt, 1)[:, :2]; hit = sum(any(G[i]["l1"] in M.get(t, []) for t in ct[o[k]]) for k, i in enumerate(mids))
        Ps = ms.predict_proba(vs.transform([txt[i] for i in sid])); pr = np.array(ms.classes_)[Ps.argmax(1)]; sh = int(sum(pr[k] == S[i]["story_type"] for k, i in enumerate(sid)))
        res["variants"][name] = {"train_rows": len(yt), "added": len(add), "held_out_abstain_either": round(float(ab.mean()), 4), "queue_held_out_abstain_either": round(float(abstain(vt, mt, vs, ms, qheld)[0].mean()), 4), "queue_held_out_topic_abstain": round(float(abstain(vt, mt, vs, ms, qheld)[1].mean()), 4), "queue_held_out_story_abstain": round(float(abstain(vt, mt, vs, ms, qheld)[2].mean()), 4), "held_out_topic_abstain": round(float(abt.mean()), 4), "held_out_story_abstain": round(float(abs_.mean()), 4), "topic_two_guess_mnds": {"rate": round(hit / len(mids), 4), "ci95": wil(hit, len(mids))}, "story_agree_sealed": {"rate": round(sh / len(sid), 4), "ci95": wil(sh, len(sid))}}; print(name, res["variants"][name], flush=True)
    json.dump(res, open(OUT / "t144_eval.json", "w"), indent=1)
