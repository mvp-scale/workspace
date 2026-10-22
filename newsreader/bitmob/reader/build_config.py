"""D-0037 step 1 scoring + serving config. Reads the frozen-test probabilities (e5-base from Kaggle runs, refit e5-small+tf-idf), chooses blend weights, per-key condition cuts
(night1 held-out FPR <= 0.0025, as F-0097), scores country as 100-country accuracy and as before, scores the new heads; writes data/bitmob-integration/reader_config.json + step1_scores.json.
  models/embed-zs/.venv/bin/python newsreader/bitmob/reader/build_config.py"""
import os, json, numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, average_precision_score
W = "/workspace/data"; I = f"{W}/bitmob-integration"; L = lambda f: [json.loads(l) for l in open(f)]; ld = lambda p: np.load(p, allow_pickle=True)
night = L(f"{W}/trainset/night1.jsonl"); _, te_i = train_test_split(np.arange(len(night)), test_size=0.2, random_state=0); test = [night[i] for i in te_i] + L(f"{W}/trainset/testA.jsonl"); nn = len(te_i)
K8 = json.load(open(f"{W}/kaggle/ds_r8/keys.json")); K5 = json.load(open(f"{W}/kaggle/ds_r5/keys.json")); import csv
ENGINE100 = {r["id"] for r in csv.DictReader(open("/workspace/probes/world-engine/data/countries_world100.csv"))}
out = {}; cfg = {"e5base": {"topic": "data/kaggle/run7/e5b_ep3_lr3e-5/topic", "country": "data/kaggle/run8/e5-base-v2/country", "conditions": "data/kaggle/run4/e5-base-v2/conditions", "type": "data/kaggle/run4/e5-base-v2/type", "heads": "data/kaggle/run8/e5-base-v2/heads"}, "w_tfidf": {}}
tf = {a: ld(f"{I}/tfidf_test_{a}.npz")["P"] for a in ("topic", "country", "conditions", "heads")}
# ---- country
ck = K8["country_keys"]; raw = np.array([r["country"] for r in test]); mapped = np.array([r["country"] if r["country"] in ck else "other" for r in test]); pe = ld(f"{W}/suite_kaggle8/e5-base-v2/country.npz")["P"]
def cacc(P, keys=ck):
    pr = np.array(keys)[P.argmax(1)]; in100 = np.array([c in ENGINE100 or c == "global" for c in raw])
    return {"mapped_acc": round(float((pr == mapped).mean()), 4), "strict_100country_acc": round(float((pr == raw).mean()), 4), "acc_when_true_country_in_engine_100": round(float((pr == raw)[in100].mean()), 4), "n_in_engine_100_or_global": int(in100.sum()),
            "share_true_country_outside_model_classes": round(float((mapped == "other").mean()), 4), "pred_other_share": round(float((pr == "other").mean()), 4)}
cands = {"e5b": pe, "tfidf": tf["country"], "blend": (pe + tf["country"]) / 2}; out["country_new"] = {k: cacc(v) for k, v in cands.items()}
cfg["w_tfidf"]["country"] = 0.5 if out["country_new"]["blend"]["mapped_acc"] >= out["country_new"]["e5b"]["mapped_acc"] else 0.0
old = ld(f"{W}/suite_final/blend_country/test-probs.npz"); ok_ = list(old["keys"]); P_old = old["P"]; prb = np.array(ok_)[P_old.argmax(1)]; in100 = np.array([c in ENGINE100 or c == "global" for c in raw])
out["country_old_top15"] = {"mapped_acc(top15+other)": round(float((prb == np.array([r["country"] if r["country"] in ok_ else "other" for r in test])).mean()), 4), "strict_100country_acc": round(float((prb == raw).mean()), 4), "acc_when_true_country_in_engine_100": round(float((prb == raw)[in100].mean()), 4), "classes": len(ok_)}
# ---- heads
hk = K8["head_keys"]; Yh = np.array([[int(r["P"].get(f, 0) >= 0.5) for f in ("x|recent", "s|national", "s|local", "s|new")] for r in test]); ph = ld(f"{W}/suite_kaggle8/e5-base-v2/heads.npz")["P"]
def hscore(P): return {k: {"AUC": round(float(roc_auc_score(Yh[:, i], P[:, i])), 4), "AP": round(float(average_precision_score(Yh[:, i], P[:, i])), 4), "base_rate": round(float(Yh[:, i].mean()), 4), "acc@0.5": round(float(((P[:, i] >= 0.5) == Yh[:, i]).mean()), 4),
                       "majority_acc": round(float(max(Yh[:, i].mean(), 1 - Yh[:, i].mean())), 4)} for i, k in enumerate(hk)}
out["heads"] = {"e5b": hscore(ph), "blend": hscore((ph + tf["heads"]) / 2)}
cfg["w_tfidf"]["heads"] = 0.5 if np.mean([v["AUC"] for v in out["heads"]["blend"].values()]) >= np.mean([v["AUC"] for v in out["heads"]["e5b"].values()]) else 0.0
# ---- topic parity (e5b ep3 + refit tfidf) and conditions
tk = K5["topic_keys"]; yt = np.array([tk.index(r["topic"]) for r in test]); pt = ld(f"{W}/suite_kaggle7/e5b_ep3_lr3e-5/topic.npz")["P"]
out["topic"] = {"e5b": round(float((pt.argmax(1) == yt).mean()), 4), "blend_refit_tfidf": round(float((((pt + tf["topic"]) / 2).argmax(1) == yt).mean()), 4), "F-0100 reference": 0.8301}; cfg["w_tfidf"]["topic"] = 0.5
ck5 = K5["cond_keys"]; Yc = np.array([[k in set(r["target_keys"]) for k in ck5] for r in test]); pc = ld(f"{W}/suite_kaggle4/e5-base-v2/conditions.npz")["P"]; assert list(ld(f"{W}/suite_kaggle4/e5-base-v2/conditions.npz")["keys"]) == ck5
Pc = (pc + tf["conditions"]) / 2; cfg["w_tfidf"]["conditions"] = 0.5; cuts = {}; rows = {}
for i, k in enumerate(ck5):
    neg = ~Yc[:nn, i]; th = 1.01
    if Yc[:nn, i].sum() >= 1:
        for t in np.sort(np.unique(Pc[:nn, i])):
            if ((Pc[:nn, i] >= t) & neg).sum() / max(1, neg.sum()) <= 0.0025: th = float(t); break
    cuts[k] = th; pr = Pc[nn:, i] >= th; yy = Yc[nn:, i]
    if yy.sum() >= 3: rows[k] = {"TPR": round(float((pr & yy).sum() / yy.sum()), 3), "FPR": round(float((pr & ~yy).sum() / (~yy).sum()), 5), "n_pos_testA": int(yy.sum())}
cfg["cond_cuts"] = cuts
out["conditions"] = {"keys": len(ck5), "keys_scored": len(rows), "cut_rule": "night1 held-out FPR <= 0.0025 (F-0097), scored on testA", "mean_TPR": round(float(np.mean([v["TPR"] for v in rows.values()])), 3), "mean_FPR": round(float(np.mean([v["FPR"] for v in rows.values()])), 5),
                     "keys_FPR_le_0.0025": int(sum(v["FPR"] <= 0.0025 for v in rows.values())), "keys_TPR_ge_0.8": int(sum(v["TPR"] >= 0.8 for v in rows.values())), "per_key": rows}
tp = ld(f"{W}/suite_kaggle4/e5-base-v2/type.npz"); tY = tp["Y"].astype(bool); out["type"] = {"mean_AP": round(float(np.mean([average_precision_score(tY[:, i], tp["P"][:, i]) for i in range(4)])), 4)}
json.dump(cfg, open(f"{I}/reader_config.json", "w"), indent=1); json.dump(out, open(f"{I}/step1_scores.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "conditions"}, indent=1)); print({k: v for k, v in out["conditions"].items() if k != "per_key"}); print(cfg["w_tfidf"])
