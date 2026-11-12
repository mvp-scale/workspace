"""Domain from several signals, scored on MN-DS as a ruler only (pre-registered L1045). S2 = BitMob Domain (v6b) topic mapped to the 17 classes; S3 = hashed word model trained only on URL-labelled CC-News articles. Agreement = tool-gold.
    /workspace/models/embed-zs/.venv/bin/python domain_signals.py   -> runs/harvest/domain_signals.json"""
import json, re, sys, time, numpy as np, collections
sys.path.insert(0, "."); import analyze2 as A2
from expert1_runtime import ExpertS
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.svm import LinearSVC
M = [json.loads(l) for l in open("/workspace/data/anchors/mn_ds/train.jsonl")]; M = [m for m in M if m.get("category_level_1") and m.get("content")]; y = np.array([m["category_level_1"] for m in M])
MAP = json.load(open("specs/topic_to_iptc_v1.json"))["map"]
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); S = e.S; X = A2.Analyzer(S, json.load(open("runs/pulse/field_table.json")), threads=8); t0 = time.time(); P = []
for m in M: pt, ps, nw = X.reader.read(m["title"] or "", m["content"][:12000]); P.append(pt)
P = np.array(P); print("reader", round(time.time() - t0), "s", flush=True); np.save("runs/harvest/domain_mnds_topic_probs.npy", P.astype(np.float16))
cl = S["topic_cl"]; prim = np.array([(MAP.get(cl[int(k)]) or [None])[0] for k in P.argmax(1)], dtype=object)
two = [set(c for k in np.argsort(-p)[:2] for c in MAP.get(cl[int(k)], [])) for p in P]
sm = {r["row"]: r for r in map(json.loads, open("runs/harvest/sample100k.jsonl"))}; hl = [json.loads(l) for l in open("runs/harvest/labels100k.jsonl")]; hl = [h for h in hl if "domain_label" in h]
hv = HashingVectorizer(n_features=2**20, ngram_range=(1, 2), alternate_sign=False, norm="l2"); txt = lambda t, b: ((t or "") + ". " + (b or ""))[:3000]
clf = LinearSVC(C=0.5).fit(hv.transform([txt(sm[h["row"]]["title"], sm[h["row"]]["text"]) for h in hl]), [h["domain_label"]["label"] for h in hl])
XT = hv.transform([txt(m["title"], m["content"]) for m in M]); d = clf.decision_function(XT); s3 = clf.classes_[d.argmax(1)]; srt = np.sort(d, axis=1); marg = srt[:, -1] - srt[:, -2]
valid = np.array([p is not None for p in prim]); s2ok = prim == y; s3ok = s3 == y; ag = valid & (prim == s3); res = {"articles": len(M), "train_labels_S3": len(hl)}
res["S2_reader_primary"] = {"covered": int(valid.sum()), "top1": round(float(s2ok.mean()), 4), "precision_when_covered": round(float(s2ok[valid].mean()), 4)}
res["S2_reader_top2_any"] = {"within": round(float(np.mean([y[i] in two[i] for i in range(len(M))])), 4)}
res["S3_url_trained_words"] = {"top1": round(float(s3ok.mean()), 4), "classes": int(len(clf.classes_))}
res["agree_S2_S3"] = {"coverage": round(float(ag.mean()), 4), "precision": round(float(s2ok[ag].mean()), 4), "articles": int(ag.sum())}
res["agree_by_class"] = {c: [int((ag & (prim == c)).sum()), round(float(s2ok[ag & (prim == c)].mean()), 3)] for c in sorted(set(prim[ag])) if (ag & (prim == c)).sum() >= 20}
# agreement plus S3 margin: sweep
sw = []
for q in (0, 50, 75):
    thr = np.percentile(marg[ag], q) if ag.any() else 0; a2 = ag & (marg >= thr); sw.append({"margin_percentile": q, "coverage": round(float(a2.mean()), 4), "precision": round(float(s2ok[a2].mean()), 4)})
res["agree_with_margin"] = sw
json.dump(res, open("runs/harvest/domain_signals.json", "w"), indent=1); print(json.dumps(res, indent=1))
