"""The improvement loop as a program. Waits for new labels, retrains the three-output bundle on everything dated before the fixed test batch,
scores the SAME later test items against Sonnet, compares with the last snapshot using a noise band, writes the next snapshot, the job history,
a ledger note and runs/loop_state.json (what changed, what to do next). Run: loop_driver.py [version]   Uses /workspace/models/embed-zs/.venv/bin/python"""
import json, glob, re, pathlib, sys, time, subprocess, warnings
warnings.filterwarnings("ignore")
import numpy as np, scipy.sparse as sp
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from model2vec import StaticModel
H0 = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(H0.parents[1] / "kit/live")); import heartbeat as hb
CH = [int(x) for x in __import__("os").environ.get("CHUNKS", "1,2,3,4").split(",")]
VER = sys.argv[1] if len(sys.argv) > 1 else "v5"; BAND = 0.025; JOB = f"loop-driver-{VER}"
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
def note(text): subprocess.run(["node", "cp.mjs", "note", "T10", text, "--who", "S?"], cwd=H0.parents[1] / ".ledger", capture_output=True)
hb.beat(JOB, where="[CPU]", task="T10", state="running", why="The loop as code: new labels in, retrain, score on the same later items, compare, log", success=f"No output falls beyond the noise band {BAND}; topic top-2 reaches 0.85", next="Write the next lever from the result", need="Nothing", progress="waiting for labels", spent=0.0, cap=0.0)
t0 = time.time()
while time.time() - t0 < 5400 and not all((H0 / f"runs/p7/more{k}/yield.json").exists() for k in CH): time.sleep(30)
hb.beat(JOB, progress="labels ready, loading")
old, hk, sn = set(), {}, {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]; old.add(r["item_id"])
for f in glob.glob(str(H0 / "runs/p7/more*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; ids = sorted(hk); pos = {i: k for k, i in enumerate(ids)}
txt = [re.sub(r"\s+", " ", pool[i]["text"]) for i in ids]; head = [re.split(r"(?<=[.!?])\s", t, 1)[0] for t in txt]; dt = np.array([pool[i]["date"] or "" for i in ids])
m = StaticModel.from_pretrained("minishlab/potion-base-8M"); E = m.encode(txt); EH = m.encode(head)
y = np.array([1 if hk[i]["conditions"] else 0 for i in ids]); voted = np.array([i in sn for i in ids]); sy = np.array([1 if (i in sn and sn[i]["conditions"]) else 0 for i in ids])
o_ids = sorted(old); o_dt = np.array([pool[i]["date"] or "" for i in o_ids]); o_ord = np.argsort(o_dt, kind="stable"); o_ord = o_ord[o_dt[o_ord] != ""]
test_ids = [o_ids[k] for k in np.array_split(o_ord, 5)[4]]; te = np.array([pos[i] for i in test_ids]); start = min(dt[te]); tset = set(test_ids)
tr = np.array([pos[i] for i in ids if i not in tset and dt[pos[i]] != "" and dt[pos[i]] < start]); vt = te[voted[te]]
hb.beat(JOB, progress=f"training on {len(tr)} items, testing on the same {len(vt)} Sonnet-voted later items")
T = [txt[i] for i in tr]
vw = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True).fit(T); vc = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, sublinear_tf=True, max_features=200000).fit(T); vtp = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, max_features=100000).fit(T)
Xwc = sp.hstack([vw.transform(T), vc.transform(T)]).tocsr(); ss = StandardScaler().fit(np.hstack([E[tr], EH[tr]])); Xt = sp.hstack([vtp.transform(T), sp.csr_matrix(ss.transform(np.hstack([E[tr], EH[tr]])) * 0.1)]).tocsr()
story = LogisticRegression(max_iter=300, C=3).fit(Xwc, [hk[ids[i]]["story_type"] for i in tr]); ph = LogisticRegression(max_iter=1000, C=1).fit(Xwc, y[tr])
vv = voted[tr]; ps = LogisticRegression(max_iter=1000, C=1).fit(Xwc[vv], sy[tr][vv]); topic = LogisticRegression(max_iter=300, C=3).fit(Xt, [hk[ids[i]]["topic"] for i in tr])
hb.beat(JOB, progress="scoring")
Tv = [txt[i] for i in vt]; Xv = sp.hstack([vw.transform(Tv), vc.transform(Tv)]).tocsr(); Xtv = sp.hstack([vtp.transform(Tv), sp.csr_matrix(ss.transform(np.hstack([E[vt], EH[vt]])) * 0.1)]).tocsr()
lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6))); pres = 1 / (1 + np.exp(-(lg(ph.predict_proba(Xv)[:, 1]) + lg(ps.predict_proba(Xv)[:, 1])) / 2))
Ps = story.predict_proba(Xv); Pt = topic.predict_proba(Xtv); tc = topic.classes_; t2 = np.argsort(-Pt, 1)[:, :2]
ys_story = np.array([sn[ids[i]]["story_type"] for i in vt]); ys_topic = np.array([sn[ids[i]]["topic"] for i in vt])
def cover(conf, ok):
    o = np.argsort(-conf); run = np.cumsum(ok[o]) / np.arange(1, len(o) + 1); idx = np.where(run >= 0.8)[0]
    return {"agree": round(float(ok.mean()), 3), "share_at_80": round(float((idx.max() + 1) / len(o)) if len(idx) else 0.0, 3)}
snap = {"train_n": int(len(tr)), "test_voted_n": int(len(vt)), "story": cover(Ps.max(1), story.classes_[Ps.argmax(1)] == ys_story), "topic_top1": cover(Pt.max(1), tc[Pt.argmax(1)] == ys_topic),
        "topic_top2": cover(np.sort(Pt, 1)[:, -2:].sum(1), np.array([ys_topic[i] in set(tc[t2[i]]) for i in range(len(vt))])), "presence": cover(np.maximum(pres, 1 - pres), ((pres > .5).astype(int) == sy[vt]))}
prev = json.load(open(H0 / "runs/snapshots/v4_bundle.json")); verdict = {}
for k in ("story", "topic_top2", "presence"):
    d = snap[k]["agree"] - prev[k]["agree"]; verdict[k] = {"change": round(d, 3), "call": "improved" if d > BAND else ("regressed: rollback flag" if d < -BAND else "same, inside the noise band")}
snap["vs_v4"] = verdict; json.dump(snap, open(H0 / f"runs/snapshots/{VER}_bundle.json", "w"), indent=1)
new_labels = len(tr) - 19818
nxt = "topic gained from more data: keep adding labelled items" if verdict["topic_top2"]["call"] == "improved" else "more data did not lift topic beyond noise: next lever must add new information, not more of the same"
json.dump({"version": VER, "scores": snap, "verdict": verdict, "next": nxt, "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, open(H0 / "runs/loop_state.json", "w"), indent=1)
note(f"SCORE loop driver {VER} (runs/snapshots/{VER}_bundle.json, runs/loop_state.json): trained on {len(tr)} items (v4 had 19,818), same {len(vt)} later Sonnet-voted test items. Agreement vs Sonnet, change from v4 (noise band {BAND}): story {snap['story']['agree']} ({verdict['story']['change']:+}, {verdict['story']['call']}); topic top-2 {snap['topic_top2']['agree']} ({verdict['topic_top2']['change']:+}, {verdict['topic_top2']['call']}), top-1 {snap['topic_top1']['agree']}; presence {snap['presence']['agree']} ({verdict['presence']['change']:+}, {verdict['presence']['call']}). Prediction was topic top-2 0.85 or more, others within 0.01. Next: {nxt}.")
hb.finish(JOB, "done", last=f"topic top-2 {snap['topic_top2']['agree']} ({verdict['topic_top2']['call']}); story {snap['story']['agree']}; presence {snap['presence']['agree']}", progress=f"{len(tr)} training items, {VER} saved", next=nxt)
print(json.dumps(snap, indent=1))
subprocess.run([sys.executable, str(H0 / "gates_auto.py")])   # keep the Quality page in step with the data
