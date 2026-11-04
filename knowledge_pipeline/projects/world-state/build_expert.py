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
VER = "expert1_v1"; BAND = 0.025; JOB = "build-expert1"
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
def note(text): subprocess.run(["node", "cp.mjs", "note", "T10", text, "--who", "S?"], cwd=H0.parents[1] / ".ledger", capture_output=True)
hb.beat(JOB, where="[CPU]", task="T10", state="running", why="Build the expert 1 artefact with an unknown rule per field and measure its real read speed", success="Answered items agree 0.77+ per field on the held half; under 5 ms per item", next="Refresh mockup, close T10", need="Nothing", progress="training", spent=0.0, cap=0.0)
t0 = time.time()
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

import pickle, os, time
from threadpoolctl import threadpool_limits
rng = np.random.RandomState(3); perm = rng.permutation(len(vt)); A_ = perm[:len(vt) // 2]; B_ = perm[len(vt) // 2:]
conf_story = Ps.max(1); ok_story = story.classes_[Ps.argmax(1)] == ys_story
conf_t2 = np.sort(Pt, 1)[:, -2:].sum(1); ok_t2 = np.array([ys_topic[i] in set(tc[t2[i]]) for i in range(len(vt))])
conf_pres = np.maximum(pres, 1 - pres); ok_pres = ((pres > .5).astype(int) == sy[vt])
def cut(conf, ok, target=0.8):                                                   # lowest confidence cut-off whose running agreement on A stays >= target
    o = np.argsort(-conf); run = np.cumsum(ok[o]) / np.arange(1, len(o) + 1); idx = np.where(run >= target)[0]
    return float(conf[o][idx.max()]) if len(idx) else 1.01
fields = {"story_type": (conf_story, ok_story), "topic_top2": (conf_t2, ok_t2), "condition_present": (conf_pres, ok_pres)}
cuts = {k: cut(c[A_], o[A_]) for k, (c, o) in fields.items()}; report = {}
for k, (c, o) in fields.items():
    a = c[B_] >= cuts[k]; report[k] = {"cutoff": round(cuts[k], 3), "answered_share_B": round(float(a.mean()), 3), "agreement_on_answered_B": round(float(o[B_][a].mean()), 3) if a.any() else None, "agreement_if_forced_B": round(float(o[B_].mean()), 3)}
art = {"vw": vw, "vc": vc, "vt": vtp, "ss": ss, "story": story, "ph": ph, "ps": ps, "topic": topic, "cuts": cuts, "static": "minishlab/potion-base-8M", "trained_items": int(len(tr)), "contract": "specs/expert_contract_v1.md"}
pkl = H0 / "runs/expert1/expert1_v1.pkl"; pickle.dump(art, open(pkl, "wb")); size_mb = round(os.path.getsize(pkl) / 1e6, 1)
def read(text, M=art, sm=m):
    t = re.sub(r"\s+", " ", text); h = re.split(r"(?<=[.!?])\s", t, 1)[0]; e = np.hstack([sm.encode([t]), sm.encode([h])])
    xwc = sp.hstack([M["vw"].transform([t]), M["vc"].transform([t])]).tocsr(); xt = sp.hstack([M["vt"].transform([t]), sp.csr_matrix(M["ss"].transform(e) * 0.1)]).tocsr()
    ps_ = M["story"].predict_proba(xwc)[0]; pt_ = M["topic"].predict_proba(xt)[0]; pr = 1 / (1 + np.exp(-(lg(M["ph"].predict_proba(xwc)[:, 1]) + lg(M["ps"].predict_proba(xwc)[:, 1])) / 2))[0]
    o2 = np.argsort(-pt_)[:2]; out = {}
    out["story_type"] = {"answer": str(M["story"].classes_[ps_.argmax()]), "confidence": float(ps_.max()), "status": "answered" if ps_.max() >= M["cuts"]["story_type"] else "unknown"}
    out["topic_top2"] = {"answer": [str(M["topic"].classes_[k]) for k in o2], "confidence": float(pt_[o2].sum()), "status": "answered" if pt_[o2].sum() >= M["cuts"]["topic_top2"] else "unknown"}
    cp_ = max(pr, 1 - pr); out["condition_present"] = {"answer": bool(pr > .5), "confidence": float(cp_), "status": "answered" if cp_ >= M["cuts"]["condition_present"] else "unknown"}
    return out
sample = [pool[ids[i]]["text"] for i in te[:400]]
with threadpool_limits(limits=1):
    read(sample[0]); t1 = time.perf_counter(); outs = [read(t) for t in sample]; ms = (time.perf_counter() - t1) / len(sample) * 1000
sh = {k: round(float(np.mean([o[k]["status"] == "answered" for o in outs])), 3) for k in ("story_type", "topic_top2", "condition_present")}
res = {"trained_items": int(len(tr)), "test_voted_n": int(len(vt)), "per_field_B": report, "artefact_mb": size_mb, "read_ms_per_item_one_thread_from_raw_text": round(ms, 2), "answered_share_on_400_unseen_items": sh, "example": outs[0]}
json.dump(res, open(H0 / "runs/expert1/expert1_v1_report.json", "w"), indent=1); print(json.dumps(res, indent=1))
note(f"SCORE T17 expert 1 v1 artefact (runs/expert1/expert1_v1.pkl {size_mb} MB, report runs/expert1/expert1_v1_report.json): trained on {len(tr)} items. Cut-offs set on half A of {len(vt)} voted test items for 80% running agreement with Sonnet, scored on half B: " + "; ".join(f"{k} answered {v['answered_share_B']}, agreement on answered {v['agreement_on_answered_B']} (forced {v['agreement_if_forced_B']})" for k, v in report.items()) + f". Read time {round(ms,2)} ms per item on one thread from raw text. Answered share on 400 unseen items: {sh}.")
hb.finish(JOB, "done", last=f"read {round(ms,2)} ms; answered {sh}", progress=f"{size_mb} MB artefact", next="Refresh mockup, close T10 for review")
subprocess.run([sys.executable, str(H0 / "gates_auto.py")])   # keep the Quality page in step with the data
