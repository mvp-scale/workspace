"""T150 (CPU; ledger T-0029, runbook R3): topic head from Sonnet-all plus Jev topic rows (t137 label rows, t144 read rows), T135 ids and MN-DS excluded; story head and thresholds from sparse_heads_v2.pkl. Builds runs/expert1/sparse_heads_v3.pkl, scores MN-DS topic (T28b, two guesses through the IPTC map) and the abstain share (topic top-two mass or story prob < 0.70) on the 100 T135 stories.
    /workspace/models/embed-zs/.venv/bin/python -u t150_topic_head.py   (from projects/world-state) -> runs/pulse/t150/t150_topic_head.json"""
import json, glob, math, pickle, pathlib, random, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; OUT = pathlib.Path("runs/pulse/t150"); OUT.mkdir(parents=True, exist_ok=True); LB = "/workspace/data/newsreader/labels/"
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
for r in J(LB + "t144_ids.jsonl"): jt[r["id"]] = (r["title"] + ". " + r["body"])[:6000]
fr = J(LB + "full-read-100.jsonl"); mnf = {r["id"]: r["text"] for r in J("/workspace/data/anchors/mn_ds/items_fresh2.jsonl")}
T135 = {}; 
for r in fr: T135[r["id"]] = mnf[r["id"]][:6000] if r["set"] == "mnds" else jt.get(r["id"])
miss135 = [i for i, t in T135.items() if t is None]; T135 = {i: t for i, t in T135.items() if t}
S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(S)
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; bt = {}
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]
    if r["family"] != "sonnet" or i not in txt or i in sealed or i in T135: continue
    rk = RANK.get(r["version"], 2)
    if r.get("topic") and (i not in bt or rk < bt[i][0]): bt[i] = (rk, r["topic"])
jev = {}; nomatch = 0
for r in J("runs/label_store/labels_jev_t137.jsonl"):
    if r["item_id"] in T135 or r["item_id"] in sealed: continue
    if r["item_id"] in jt and r.get("topic"): jev[r["item_id"]] = (jt[r["item_id"]], r["topic"])
    else: nomatch += 1
for r in J(LB + "t144_read.jsonl"):
    if "error" in r or r["id"] in T135 or r["id"] in sealed or r["id"] not in jt: continue
    jev.setdefault(r["id"], (jt[r["id"]], r["answers_call1"]["area_main"]["choice"]))
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json")); mn = {x["id"]: x["text"] for x in J("/workspace/data/anchors/mn_ds/items_T28b.jsonl")}; mids = [i for i in mn if i in G]
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
def fit(y, texts):
    v = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True); A = v.fit_transform(texts)
    return v, SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=7).fit(A, y)
H2 = pickle.load(open("runs/expert1/sparse_heads_v2.pkl", "rb")); ids_t = sorted(bt); res = {"jev_rows_used": len(jev), "jev_rows_without_text": nomatch, "sonnet_topic_rows": len(ids_t), "t135_texts": len(T135), "t135_without_text": len(miss135), "variants": {}}
tx135 = list(T135.values())
def score(name, vt, mt, vs, ms):
    Pt = mt.predict_proba(vt.transform([mn[i] for i in mids])); ct = np.array(mt.classes_); o = np.argsort(-Pt, 1)[:, :2]; hit = sum(any(G[i]["l1"] in M.get(t, []) for t in ct[o[k]]) for k, i in enumerate(mids))
    pt = np.sort(mt.predict_proba(vt.transform(tx135)), 1)[:, ::-1][:, :2].sum(1); ps = ms.predict_proba(vs.transform(tx135)).max(1)
    res["variants"][name] = {"mnds_topic_two_guess": {"rate": round(hit / len(mids), 4), "n": len(mids), "ci95": wil(hit, len(mids))}, "abstain_t135": {"topic": int((pt < 0.7).sum()), "story": int((ps < 0.7).sum()), "either": int(((pt < 0.7) | (ps < 0.7)).sum()), "of": len(tx135)}}; print(name, res["variants"][name], flush=True)
score("v2_deployed", H2["topic_vec"], H2["topic_model"], H2["story_vec"], H2["story_model"])
vC, mC = fit(np.array([bt[i][1] for i in ids_t]), [txt[i] for i in ids_t]); score("C_sonnet_all_retrained", vC, mC, H2["story_vec"], H2["story_model"])
JX = list(jev.values()); vT, mT = fit(np.array([bt[i][1] for i in ids_t] + [y for _, y in JX]), [txt[i] for i in ids_t] + [t for t, _ in JX]); score("T_sonnet_all_plus_jev_topic", vT, mT, H2["story_vec"], H2["story_model"])
c, t = res["variants"]["C_sonnet_all_retrained"], res["variants"]["T_sonnet_all_plus_jev_topic"]
res["deploy_rule_mnds_not_lower_by_more_than_0_01"] = bool(t["mnds_topic_two_guess"]["rate"] >= c["mnds_topic_two_guess"]["rate"] - 0.01)
if res["deploy_rule_mnds_not_lower_by_more_than_0_01"]:
    H3 = dict(H2); H3.update(topic_vec=vT, topic_model=mT, train_topic=len(ids_t) + len(JX), built="2026-11-11", judge="runs/pulse/t150/t150_topic_head.json", note="topic head = Sonnet-all + Jev topic rows (T-0029); story head and thresholds from v2"); pickle.dump(H3, open("runs/expert1/sparse_heads_v3.pkl", "wb")); res["saved"] = "runs/expert1/sparse_heads_v3.pkl"
json.dump(res, open(OUT / "t150_topic_head.json", "w"), indent=1)
