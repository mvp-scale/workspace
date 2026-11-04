import json, glob, sys, numpy as np, pathlib
sys.path.insert(0, "."); from expert1_runtime import Expert
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
e = Expert("runs/expert1/expert1_v2.pkl"); pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; old = {}; sn = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
oi = sorted(old); dt = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]; test = [oi[k] for k in np.array_split(o, 5)[4]]; vt = [i for i in test if i in sn]
hneg_total = sum(1 for i in test if not old[i]["conditions"]); hneg_voted = sum(1 for i in vt if not old[i]["conditions"]); hpos_total = sum(1 for i in test if old[i]["conditions"]); hpos_voted = sum(1 for i in vt if old[i]["conditions"])
w = np.array([1.0 * hpos_total / hpos_voted if old[i]["conditions"] else hneg_total / hneg_voted for i in vt])
R = [e.read(pool[i]["text"]) for i in vt]; sp_ = np.array([1 if sn[i]["conditions"] else 0 for i in vt]); cp = np.array([r["condition_present"] for r in R], dtype=object)
ans = np.array([c["status"] == "answered" for c in cp]); pred = np.array([bool(c["answer"]) if c["answer"] is not None else False for c in cp]); conf = np.array([c.get("confidence", 0) for c in cp])
W = lambda m: float(w[m].sum())
res = {"test_fifth_items": len(test), "voted": len(vt), "haiku_neg_weight": round(hneg_total / hneg_voted, 2), "voted_haiku_positive_share": round(hpos_voted / len(vt), 3), "natural_haiku_positive_share": round(hpos_total / len(test), 3)}
res["unweighted"] = {"answered_share": round(float(ans.mean()), 3), "agree_on_answered": round(float((pred == sp_)[ans].mean()), 3)}
res["weighted"] = {"answered_share": round(W(ans) / W(np.ones(len(vt), bool)), 3), "agree_on_answered": round(W(ans & (pred == sp_)) / W(ans), 3), "forced_agreement": round(W(pred == sp_) / W(np.ones(len(vt), bool)), 3)}
cm = ans & pred
res["present_commits"] = {"unweighted_n": int(cm.sum()), "unweighted_precision_sonnet_positive": round(float(sp_[cm].mean()), 3), "weighted_precision_sonnet_positive": round(W(cm & (sp_ == 1)) / W(cm), 3), "weighted_false_alarm_share": round(W(cm & (sp_ == 0)) / W(cm), 3), "weighted_recall_of_sonnet_positives": round(W(cm & (sp_ == 1)) / W(sp_ == 1), 3)}
scan = []
for t in (0.5, 0.6, 0.7, 0.747, 0.8, 0.85, 0.9, 0.95):
    m = pred & (np.maximum(conf, 0) >= t) if t > 0.5 else pred
    m = pred & (conf >= t); scan.append({"min_conf": t, "n": int(m.sum()), "weighted_precision": round(W(m & (sp_ == 1)) / W(m), 3) if m.any() else None, "weighted_recall": round(W(m & (sp_ == 1)) / W(sp_ == 1), 3)})
res["present_threshold_scan_ignoring_unknown_cut"] = scan
json.dump(res, open("runs/expert1/natural_rescore.json", "w"), indent=1); print(json.dumps(res, indent=1))
