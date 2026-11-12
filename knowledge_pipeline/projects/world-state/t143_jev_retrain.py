"""T143 (CPU): the closing step of the loop, adapted from lap_retrain.py. Sparse topic and story-type heads trained on (A) a random Sonnet-labelled sample of the same size as the Jev rows, (B) the Jev teacher rows only, (C) all Sonnet rows, (D) all Sonnet rows plus the Jev rows; scored on the same outside judges as lap_retrain: topic against MN-DS human labels (two guesses through the topic-to-IPTC map, T28b set), story type against the sealed set (agreement with Sonnet). MN-DS and sealed ids are never in the training rows.
    JEV=<labels_jev_*.jsonl,...> /workspace/models/embed-zs/.venv/bin/python -u t143_jev_retrain.py (from projects/world-state) -> runs/pulse/t143/t143_jev_retrain.json"""
import json, glob, math, time, os, random, pathlib, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
OUT = pathlib.Path("runs/pulse/t143"); OUT.mkdir(parents=True, exist_ok=True)
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
for f in glob.glob("runs/**/items*.jsonl", recursive=True):
    try:
        for r in J(f):
            if r.get("id") and r.get("text"): txt.setdefault(r["id"], r["text"])
    except Exception: pass
jt = {}
for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl"): r = json.loads(l); jt[r["id"]] = (r["title"] + ". " + r["text"])[:6000]
for l in open("/workspace/data/newsreader/labels/t135_ls_sample.jsonl"): r = json.loads(l); jt[r["id"]] = (r["title"] + ". " + r["body"])[:6000]
S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(S); sid = sorted(i for i in S if i in txt)
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; bt = {}; bs = {}
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]
    if r["family"] != "sonnet" or i not in txt or i in sealed: continue
    rk = RANK.get(r["version"], 2)
    if r.get("topic") and (i not in bt or rk < bt[i][0]): bt[i] = (rk, r["topic"])
    if r.get("story_type") and (i not in bs or rk < bs[i][0]): bs[i] = (rk, r["story_type"])
jev = []
for p in os.environ.get("JEV", "runs/label_store/labels_jev_t135.jsonl").split(","):
    for r in J(p):
        if r["item_id"] in jt and r["item_id"] not in sealed and r.get("topic") and r.get("story_type"): jev.append(r)
seen = set(); jev = [r for r in jev if not (r["item_id"] in seen or seen.add(r["item_id"]))]
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json"))
mn = {x["id"]: x["text"] for x in J("/workspace/data/anchors/mn_ds/items_T28b.jsonl")}; mids = [i for i in mn if i in G]
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
def fit(y, texts):
    v = TfidfVectorizer(ngram_range=(1, 2), min_df=3 if len(texts) > 2000 else 2, max_features=150000, sublinear_tf=True); A = v.fit_transform(texts)
    return v, SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=7).fit(A, y)
res = {"jev_rows": len(jev), "judge_topic": "MN-DS human labels (T28b set), two guesses through the topic-to-IPTC map", "judge_story": "agreement with Sonnet on the sealed set (a teacher judge, not outside truth)", "variants": {}}
rng = random.Random(143); ids_t = sorted(bt); ids_s = sorted(bs)
T100 = []   # held-out stories no variant trained on: the MN-DS fresh2 set (scoring only), first 600
for l in open("/workspace/data/anchors/mn_ds/items_fresh2.jsonl"):
    r = json.loads(l); T100.append(r["text"][:6000])
    if len(T100) >= 600: break
def variant(name, Xt, yt, Xs, ys):
    t0 = time.time(); vt, mt = fit(np.array(yt), Xt); vs, ms = fit(np.array(ys), Xs)
    Pt = mt.predict_proba(vt.transform([mn[i] for i in mids])); ct = np.array(mt.classes_); o = np.argsort(-Pt, 1)[:, :2]; hit = sum(any(G[i]["l1"] in M.get(t, []) for t in ct[o[k]]) for k, i in enumerate(mids))
    pt100 = np.sort(mt.predict_proba(vt.transform(T100)), 1)[:, ::-1][:, :2].sum(1); ps100 = ms.predict_proba(vs.transform(T100)).max(1); ab = {"topic_abstain_share": round(float((pt100 < 0.7).mean()), 3), "story_type_abstain_share": round(float((ps100 < 0.7).mean()), 3), "either": round(float(((pt100 < 0.7) | (ps100 < 0.7)).mean()), 3), "stories": len(T100), "set": "MN-DS fresh2, held out"}
    Ps = ms.predict_proba(vs.transform([txt[i] for i in sid])); pr = np.array(ms.classes_)[Ps.argmax(1)]; sh = int(sum(pr[k] == S[i]["story_type"] for k, i in enumerate(sid)))
    res["variants"][name] = {"abstain_on_100": ab, "train_topic": len(yt), "train_story": len(ys), "fit_seconds": round(time.time() - t0), "topic_two_guess_mnds": {"rate": round(hit / len(mids), 4), "ci95": wil(hit, len(mids))}, "story_agree_sealed": {"rate": round(sh / len(sid), 4), "ci95": wil(sh, len(sid))}}; print(name, res["variants"][name], flush=True)
n = len(jev); JX = [jt[r["item_id"]] for r in jev]
for seed in (1, 2, 3):   # equal-size Sonnet samples
    rr = random.Random(seed); st_ = rr.sample(ids_t, min(n, len(ids_t))); ss_ = rr.sample(ids_s, min(n, len(ids_s)))
    variant(f"A_sonnet_equal_size_seed{seed}", [txt[i] for i in st_], [bt[i][1] for i in st_], [txt[i] for i in ss_], [bs[i][1] for i in ss_])
variant("B_jev_only", JX, [r["topic"] for r in jev], JX, [r["story_type"] for r in jev])
variant("C_sonnet_all", [txt[i] for i in ids_t], [bt[i][1] for i in ids_t], [txt[i] for i in ids_s], [bs[i][1] for i in ids_s])
variant("D_sonnet_all_plus_jev", [txt[i] for i in ids_t] + JX, [bt[i][1] for i in ids_t] + [r["topic"] for r in jev], [txt[i] for i in ids_s] + JX, [bs[i][1] for i in ids_s] + [r["story_type"] for r in jev])
# paired test: the same stories labelled by Sonnet and by Jev, same text, same size
snt = {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] == "sonnet" and r["item_id"].startswith("nr:") and r.get("topic") and r.get("story_type"): snt.setdefault(r["item_id"][3:], r)
both = [r for r in jev if r["item_id"] in snt and r["item_id"] in jt]; BX = [jt[r["item_id"]] for r in both]; res["paired_stories_labelled_by_both"] = len(both)
variant("E1_same_stories_sonnet_labels", BX, [snt[r["item_id"]]["topic"] for r in both], BX, [snt[r["item_id"]]["story_type"] for r in both])
variant("E2_same_stories_jev_labels", BX, [r["topic"] for r in both], BX, [r["story_type"] for r in both])
res["topic_label_agreement_jev_vs_sonnet_on_these"] = round(sum(r["topic"] == snt[r["item_id"]]["topic"] for r in both) / max(len(both), 1), 4); res["story_type_label_agreement_jev_vs_sonnet_on_these"] = round(sum(r["story_type"] == snt[r["item_id"]]["story_type"] for r in both) / max(len(both), 1), 4)
json.dump(res, open(OUT / "t143_jev_retrain.json", "w"), indent=1)
