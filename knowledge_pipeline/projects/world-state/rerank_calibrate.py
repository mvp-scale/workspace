"""rerank_calibrate: the abstain line for the round-1 topic re-ranker (ledger L2756 item 1; method of landing_calibrate.py: calibrated p that the level-1 answer is right, line = lowest p whose set of 30+ items still has accuracy >= 0.80).
Fit set: MN-DS train publishers only (specs/topic_loop_split_v1.json), never select or confirm. The saved model was fitted on those same items, so its own train predictions are over-confident (round 1: train 0.84, select 0.74);
the calibrator therefore sees publisher-held-out out-of-fold predictions (GroupKFold by publisher, 5 folds, the model's own recipe: StandardScaler, C from prereg (0.01), balanced multinomial LR, same prior correction).
Features: log q1, margin q1-q2 (corrected posterior), and whether the landing's own damped level-1 code agrees. dev info: the same numbers on `select` (the final model, never used to fit anything here). `confirm` is not read.
Run: /workspace/models/embed-zs/.venv/bin/python rerank_calibrate.py --write specs/rerank_calibration_v1.json [--metrics out.json]   (CPU, a few minutes);  --selftest"""
import sys, os, json, math, time, pickle, hashlib, pathlib, argparse
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE)); OUT = HERE / "runs/pulse/topic_loop/r1"
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--write"); ap.add_argument("--metrics"); a = ap.parse_args(); os.chdir(HERE); t0 = time.time()
    import topic_loop as TL, reranker as RR, landing_calibrate as LC
    from sklearn.linear_model import LogisticRegression; from sklearn.preprocessing import StandardScaler; from sklearn.model_selection import GroupKFold; from sklearn.metrics import roc_auc_score; from joblib import Parallel, delayed; from threadpoolctl import threadpool_limits
    z = np.load(OUT / "cache_cpu.npz", allow_pickle=False); spec = json.load(open(TL.SPLIT)); items, _ = TL.load_items(); byid = {x["id"]: x for x in items}; order = [str(i) for i in z["order"]]; Sm = z["Sm"].astype(np.float64); m = pickle.load(open(OUT / "primary_reranker.pkl", "rb"))
    codes = list(m["classes"]); ci = {c: k for k, c in enumerate(codes)}; K = len(codes); live = np.array(m["live_mix"]); card_ids = [str(c) for c in z["card_ids"]]; assert card_ids == list(m["card_ids"]) and str(z["cards_sha"]) == m["cards_sha"]
    trs = set(spec["ids"]["train"]); tr = np.array([k for k, i in enumerate(order) if i in trs]); se = np.array([k for k, i in enumerate(order) if i in set(spec["ids"]["select"])]); TL.assert_no_leak(spec, [order[k] for k in tr], items=items)
    y = np.array([ci[byid[i]["l1"]] for i in order]); pub = np.array([byid[i]["pub"] for i in order]); cal0 = json.load(open(HERE / "specs/landing_calibration_v1.json")); share = np.array([cal0["share"].get(q, 0.0) for q in card_ids])
    class_of_card = None
    from structure_pack import Pack; import spacy; P = Pack(spacy.blank("en")); l1c = np.array([P.chain(q)[0] for q in card_ids])
    D = Sm - 0.5 * share; land_l1 = np.array([l1c[j] for j in D.argmax(1)]); C = float(m["C"]); folds = list(GroupKFold(n_splits=5).split(tr, y[tr], pub[tr]))
    def fit_fold(a_, b_):
        with threadpool_limits(limits=1):
            sc = StandardScaler().fit(Sm[tr][a_]); clf = LogisticRegression(C=C, class_weight="balanced", max_iter=400).fit(sc.transform(Sm[tr][a_]), y[tr][a_]); p = np.zeros((len(b_), K)); p[:, clf.classes_] = clf.predict_proba(sc.transform(Sm[tr][b_])); return b_, p
    for a_, b_ in folds: TL.assert_no_leak(spec, [order[tr[i]] for i in a_])
    res = Parallel(n_jobs=5)(delayed(fit_fold)(a_, b_) for a_, b_ in folds); P_oof = np.zeros((len(tr), K))
    for b_, p in res: P_oof[b_] = p
    def corrected(Pr): q = Pr * live; return q / q.sum(1, keepdims=True)
    q_oof = corrected(P_oof); pred = q_oof.argmax(1); right = pred == y[tr]; F = [RR.cal_features(q, codes[int(k)] == land_l1[tr[i]]) for i, (q, k) in enumerate(zip(q_oof, pred))]
    X = np.array([[f[k] for k in RR.FEATS] for f in F]); sc = StandardScaler().fit(X); clf = LogisticRegression(max_iter=1000).fit(sc.transform(X), right.astype(int)); p_oof = clf.predict_proba(sc.transform(X))[:, 1]; pm = (p_oof * 1000).astype(int); line = LC.find_line(pm, right)
    cal = {"version": "rerank_calibration_v1", "written": time.strftime("%Y-%m-%d"), "method": "StandardScaler + LogisticRegression(C=1) on whether the corrected level-1 answer equals the MN-DS gold level-1 code; fitted on publisher-held-out out-of-fold predictions of MN-DS train only", "features": RR.FEATS, "scaler_mean": [float(x) for x in sc.mean_], "scaler_scale": [float(x) for x in sc.scale_],
           "coef": [float(x) for x in clf.coef_[0]], "intercept": float(clf.intercept_[0]), "model_sha16": RR.sha_file(str(OUT / "primary_reranker.pkl"))[:16], "cards_sha": m["cards_sha"], "split_sha256": spec["content_sha256"], "fit_items": int(len(tr)), "fit_set": "MN-DS train publishers only (%d items, %d publishers), 5 publisher folds" % (len(tr), len(set(pub[tr]))), "line_permille": line,
           "line_rule": "same as landing_calibrate.find_line: lowest floor(1000 p) whose set of 30+ items has accuracy >= 0.80 (on the out-of-fold items); decision ANSWER_L1 iff floor(1000 p) >= line_permille", "oof": {"top1": round(float(right.mean()), 4), "auroc": round(float(roc_auc_score(right, p_oof)), 4), "at_line": LC.at_line(pm, right, line)}}
    # dev info on select with the final model (never fitted on)
    mm = RR.Reranker.__new__(RR.Reranker); mm.mean, mm.scale, mm.W, mm.b, mm.live = np.array(m["scaler_mean"]), np.array(m["scaler_scale"]), np.array(m["coef"]), np.array(m["intercept"]).ravel(), live
    qs = RR.Reranker.posterior(mm, Sm[se]); ps = qs.argmax(1); rs = ps == y[se]; pms = np.array([int(1000 * RR.cal_prob(RR.cal_features(q, codes[int(k)] == land_l1[se[i]]), cal)) for i, (q, k) in enumerate(zip(qs, ps))])
    cal["dev_select"] = {"n": int(len(se)), "top1": round(float(rs.mean()), 4), "landing_top1": round(float((land_l1[se] == np.array([codes[k] for k in y[se]])).mean()), 4), "at_line": LC.at_line(pms, rs, line), "note": "select is the dev half; never used to fit"}
    cal["seconds"] = round(time.time() - t0, 1); print(json.dumps({k: cal[k] for k in ("line_permille", "oof", "dev_select", "seconds")}, indent=1))
    if a.metrics: json.dump(cal, open(a.metrics, "w"), indent=1)
    if a.write: json.dump(cal, open(a.write, "w"), indent=1); print("wrote", a.write)
def selftest():
    import reranker as RR
    q = np.array([0.6, 0.3, 0.1]); f = RR.cal_features(q, True); assert f["margin"] == 0.3 and f["agree_landing"] == 1.0 and abs(f["log_q1"] - math.log(0.6)) < 1e-4, f
    cal = {"features": RR.FEATS, "scaler_mean": [0, 0, 0], "scaler_scale": [1, 1, 1], "coef": [0, 1, 0], "intercept": 0.0}; assert abs(RR.cal_prob(f, cal) - 1 / (1 + math.exp(-0.3))) < 1e-9; print("selftest ok")
if __name__ == "__main__": selftest() if "--selftest" in sys.argv else main()
