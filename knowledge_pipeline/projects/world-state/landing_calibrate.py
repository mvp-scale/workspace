"""landing_calibrate (build spec step 4, landing v1): fits the calibrated probability p that the landing's level-1 code is right, on MN-DS T28 (1,676 items), scores it on MN-DS fresh2 (1,352; a source split, never the same items),
and writes specs/landing_calibration_v1.json (features, scaler, coefficients, hub-damping shares, the abstain line, the fit set and date). live_trace.py imports load / features / prob from here, so the fit and the trace use one code path.
Landing = pack_view.Landing (alias off, text[:2000] for the article, one vote per sentence of 40+ characters from the same spaCy parse the trace uses). Gold by code through mnds_codes (plan v2 step 1); no label strings compared.
Features (all computed from one Landing.assemble result): best raw cosine; margin (damped best minus damped second); how many of the 3 best cards share the best card's level-1 code (1-3); log length of text[:2000]; hub flag (best card is one of the 10 most-landed cards on T28);
  vote_l1 (share of landed sentences whose level-1 code is the article's); vote_top (1 when 3+ sentences landed and the top vote is the article's level-1 code); log(1 + sentences landed).
Hub damping (pre-registered in c2, not tuned): cards ranked by cosine - 0.5 x (card's share of T28 landings); shares come from T28 only.
The line (permille, integer): sort the T28 items by floor(1000 p); the line is the p of the last item (30 or more items in) whose running accuracy is still >= 0.80 (the c2 rule). The decision uses the same integer: ANSWER_L1 iff floor(1000 p) >= line.
PREDICTION (written before the first run, 2026-11-19; build spec section 4 M1, A1):
  fresh2: level-1 top1 with damping and vote features 0.565 to 0.585 (v0 0.562); level 2 on current-status items 0.29 to 0.33; calibrator AUROC 0.74 to 0.78; accuracy at coverage 0.50 = 0.74 to 0.78 (FAIL the 0.80 bar);
  coverage with running accuracy >= 0.80 on fresh2 = 0.15 to 0.25 (c2 v0 features: 0.138); the line lands near p 0.70 (0.66 to 0.74); on fresh2 the accuracy at that line is 0.76 to 0.82 (the line is chosen in-sample on T28, so it may dip under 0.80) at coverage 0.12 to 0.25.
  The vote features add 0.00 to 0.03 AUROC over the five c2 features. Stop rule: two flat rounds (under +0.5 point).
ROUND 3 (2026-11-19, owner choice ledger L2744): the gate is OFF by default (code kept behind --gate): the vote counts on every article, so `voted` = 1 whenever a sentence has 40 characters. Round-1 numbers for comparison: fresh2 AUROC 0.740, line about 0.757, coverage 12.1% at accuracy 0.823.
ROUND 2 (2026-11-19, the build spec's latency remedy, section 4 L1): the vote runs only when the 3 best cards disagree on the level-1 code (agree3 < 3). New feature `voted` (1 when it ran); vote_l1 and vote_top are 0 when it did not; log_n_sent still counts the 40+ character sentences (no embedding needed). One rule in features() for the fit and the trace.
  The decision and the stored p use one integer, permille = floor(1000 p) (the trace stores p = permille / 1000), so a page never shows p at or above the line with ABSTAIN.
PREDICTION round 2 (written before the fit; the fit reuses the round-1 encodes, so it needs no embedding): fresh2 AUROC 0.72 to 0.74 (round 1: 0.740); coverage at the line on fresh2 0.09 to 0.14 (round 1: 0.121) at accuracy 0.78 to 0.84; accuracy at coverage 0.50 = 0.73 to 0.75 (FAIL the 0.80 bar again); share of articles with the vote running 45 to 65% (T28 mean agree3 was 2.13).
  Landing stage p50 in the trace: 35 to 70 ms (the median article is on the voted side when over half vote); the build spec's 15 to 25 ms needs under half voting. If the 20 ms bar is still missed, say so; do not tune the gate to the bar.
Run (one CPU embedding job, under 10 min):
  cd /workspace/knowledge_pipeline/projects/world-state && /workspace/models/embed-zs/.venv/bin/python landing_calibrate.py --write specs/landing_calibration_v1.json --metrics <out.json> [--cache <enc.pkl>]
  landing_calibrate.py --selftest   (no models: checks features/prob/decision on a synthetic landing)"""
import sys, os, json, math, hashlib, time, pathlib, collections, argparse, pickle
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent; SPEC = str(HERE / "specs/landing_calibration_v1.json"); MN = "/workspace/data/anchors/mn_ds"
FEATS = ["best", "margin", "agree3", "log_len", "hub", "voted", "vote_l1", "vote_top", "log_n_sent"]; DAMP_K = 0.5; MINN = 30; BAR = 0.80
def features(res, n_chars, hubs, gate=False):
    """res = Landing.assemble/land result (ranked with the shares); n_chars = len(text[:2000]); hubs = set of card qcodes. -> dict of the 9 features.
    gate=False (the owner's choice, ledger L2744: UNGATED): the sentence vote counts on every article that has a sentence (`voted` = 1 whenever n_sent > 0). gate=True (round 2, behind --gate / cal["gate"]): the vote counts only when the 3 best cards disagree (agree3 < 3; spec 2.6), and the two vote features are 0 when it did not run, in the fit and in the trace alike."""
    art = res["article"]; b = art[0]; l1 = b["path_codes"][0]; ns = res["n_sentences"]; va = res.get("vote_all") or {}; vb = res.get("vote_by_code") or []; rk = res["rank_scores"]; a3 = sum(1 for a in art[:3] if a["path_codes"][0] == l1); v = (a3 < 3 or not gate) and ns > 0
    return {"best": b["score"], "margin": round(rk[0] - rk[1], 4), "agree3": a3, "log_len": round(math.log(max(1, n_chars)), 4), "hub": 1.0 if b["qcode"] in hubs else 0.0, "voted": 1.0 if v else 0.0,
            "vote_l1": round(va.get(l1, 0) / ns, 4) if v else 0.0, "vote_top": 1.0 if v and ns >= 3 and vb and vb[0][0] == l1 else 0.0, "log_n_sent": round(math.log1p(ns), 4)}
def prob(f, cal):
    x = (np.array([f[k] for k in cal["features"]], float) - np.array(cal["scaler_mean"])) / np.array(cal["scaler_scale"]); z = float(x @ np.array(cal["coef"]) + cal["intercept"]); return 1 / (1 + math.exp(-z))
def permille(p): return int(1000 * p)   # floor; the one integer the decision, the stored p and the decider's confidence all use
def decide_pm(pm, cal): return "ANSWER_L1" if pm >= cal["line_permille"] else "ABSTAIN"
def decide(p, cal): return decide_pm(permille(p), cal)
def load(cards_sha, path=SPEC):
    """-> (calibration dict or None, why). Missing file, or a card set that differs from the one the fit saw: no calibration, the trace falls back to v0 (EVIDENCE_ONLY, p null) and says why."""
    if not os.path.exists(path): return None, "no calibration file " + os.path.basename(path)
    raw = open(path, "rb").read(); cal = json.loads(raw)
    if cal["cards_sha"] != cards_sha: return None, "calibration was fitted on cards %s, the landing has cards %s" % (cal["cards_sha"][:16], cards_sha[:16])
    cal["sha16"] = hashlib.sha256(raw).hexdigest()[:16]; cal["hubs_set"] = set(cal["hubs"]); return cal, None
def share_array(landing, cal): return np.array([cal["share"].get(q, 0.0) for q in landing.ids])
def _acc_at(prob_, right, cov):
    k = int(cov * len(prob_)); idx = np.argsort(-prob_, kind="stable")[:k]; return round(float(right[idx].mean()), 3), round(float(np.sort(prob_)[::-1][k - 1]), 3)
def _max_cov(prob_, right, bar=BAR):
    o = np.argsort(-prob_, kind="stable"); acc = np.cumsum(right[o]) / np.arange(1, len(o) + 1); ok = np.where(acc >= bar)[0]; return round(float((ok.max() + 1) / len(o)), 3) if len(ok) else 0.0
def find_line(pm, right):
    """c2's rule on integer permille, over the sets the decision really makes: for each distinct p (floor(1000 p)) the items at or above it; the line is the lowest p whose set holds MINN or more T28 items and still has accuracy >= BAR; 1001 (abstain all) when none. Round 1 tried a stricter 'stays above 0.80 at every threshold' rule: it gave line 835 (0.2% coverage on fresh2), so it was dropped."""
    line = 1001
    for t in sorted({int(x) for x in pm}, reverse=True):
        m = pm >= t
        if m.sum() >= MINN and right[m].mean() >= BAR: line = t
    return line
def at_line(pm, right, line):
    m = pm >= line; return {"n": int(m.sum()), "coverage": round(float(m.mean()), 3), "accuracy": round(float(right[m].mean()), 3) if m.any() else None}
def reliability(p, right): return {"%.1f-%.1f" % (lo, lo + 0.1): [round(float(right[(p >= lo) & (p < lo + 0.1)].mean()), 3) if ((p >= lo) & (p < lo + 0.1)).any() else None, int(((p >= lo) & (p < lo + 0.1)).sum())] for lo in np.arange(0.2, 1.0, 0.1)}
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--write"); ap.add_argument("--metrics"); ap.add_argument("--cache"); ap.add_argument("--gate", action="store_true", help="round-2 gated vote (agree3 < 3 only); default off = ungated"); a = ap.parse_args()
    os.environ.setdefault("OMP_NUM_THREADS", "4"); os.environ["CUDA_VISIBLE_DEVICES"] = ""; sys.path.insert(0, str(HERE)); os.chdir(HERE)
    import facts_lib as FL; from structure_pack import Pack; from pack_view import Landing; from mnds_codes import gold_codes, table
    from sklearn.linear_model import LogisticRegression; from sklearn.preprocessing import StandardScaler; from sklearn.metrics import roc_auc_score
    t0 = time.time(); P = Pack(FL.nlp); L = Landing(P, alias=False); med = json.load(open("/workspace/data/ontology_src/iptc/medtop.json")).get("dateReleased")
    c1 = np.array([P.chain(q)[0] for q in L.ids]); c2 = np.array([P.chain(q)[1] if len(P.chain(q)) > 1 else "" for q in L.ids])
    cache = pickle.load(open(a.cache, "rb")) if a.cache and os.path.exists(a.cache) else {}
    def load_set(name, items_f, gold_f):
        items = {}
        for l in open(f"{MN}/{items_f}"): x = json.loads(l); items[x["id"]] = x["text"]
        G = json.load(open(f"{MN}/{gold_f}")); ids = [i for i in items if i in G]; gc = [gold_codes(G[i]) for i in ids]; keep = [k for k, g in enumerate(gc) if g[0]]
        T = [items[ids[k]][:12000] for k in keep]; y1 = np.array([gc[k][0] for k in keep]); y2 = np.array([gc[k][1] or "" for k in keep]); cur = np.array([gc[k][2] == "current" for k in keep])
        if name not in cache or cache[name]["cards_sha"] != L.cards_sha or len(cache[name]["enc"]) != len(T):
            enc = [L.encode(d, t) for d, t in zip(FL.nlp.pipe(T, batch_size=32), T)]; cache[name] = {"cards_sha": L.cards_sha, "enc": enc}
            if a.cache: pickle.dump(cache, open(a.cache, "wb"))
        return cache[name]["enc"], T, y1, y2, cur
    A = load_set("T28", "items_T28.jsonl", "gold_T28_clean.json"); B = load_set("fresh2", "items_fresh2.jsonl", "gold_fresh2.json"); enc_s = round(time.time() - t0, 1)
    cnt = collections.Counter(int(np.argmax(e["sc"])) for e in A[0]); hubs_i = [k for k, _ in cnt.most_common(10)]; hubs = {L.ids[k] for k in hubs_i}; share = np.zeros(len(L.ids))
    for k, v in cnt.items(): share[k] = v / len(A[0])
    def run(S, share_):
        enc, T, y1, y2, cur = S; res = [L.assemble(e, share=share_) for e in enc]; F = [features(r, len(t[:2000]), hubs, a.gate) for r, t in zip(res, T)]
        pred = np.array([r["article"][0]["path_codes"][0] for r in res]); p2 = np.array([(r["article"][0]["path_codes"] + [""])[1] for r in res]); return res, F, pred, p2
    out = {}; fits = {}
    for tag, sh in (("v1 (damped)", share), ("undamped", None)):
        ra, Fa, pa, _ = run(A, sh); rb, Fb, pb, p2b = run(B, sh); out[tag] = {"fresh2 l1 top1": round(float((pb == B[2]).mean()), 3), "T28 l1 top1": round(float((pa == A[2]).mean()), 3), "fresh2 l2 top1 on current": round(float((p2b[B[4]] == B[3][B[4]]).mean()), 3), "fresh2 l2 coverage current": round(float(B[4].mean()), 3)}
        fits[tag] = (Fa, pa, Fb, pb, rb)
    Fa, pa, Fb, pb, rb = fits["v1 (damped)"]; ya, yb = A[2], B[2]; right_a = (pa == ya); right_b = (pb == yb)
    def fit(names):
        X = np.array([[f[k] for k in names] for f in Fa]); sc = StandardScaler().fit(X); clf = LogisticRegression(max_iter=1000).fit(sc.transform(X), right_a.astype(int)); return sc, clf
    def score(names, sc, clf, F): return clf.predict_proba(sc.transform(np.array([[f[k] for k in names] for f in F])))[:, 1]
    sc, clf = fit(FEATS); p_a = score(FEATS, sc, clf, Fa); p_b = score(FEATS, sc, clf, Fb); pm_a = (p_a * 1000).astype(int); pm_b = (p_b * 1000).astype(int); line = find_line(pm_a, right_a)
    base = ["best", "margin", "agree3", "log_len", "hub"]; sc0, clf0 = fit(base); p_b0 = score(base, sc0, clf0, Fb)   # the five c2 features, same damped landing, for the vote-feature ablation
    nv_a = round(float(np.mean([f["voted"] for f in Fa])), 3); nv_b = round(float(np.mean([f["voted"] for f in Fb])), 3)   # share of articles on which the gated vote runs
    m = {"encode_s": enc_s, "total_s": round(time.time() - t0, 1), "T28 n": len(ya), "fresh2 n": len(yb), "cards_sha": L.cards_sha, "iptc_release": med, "landing": out,
         "T28 hub cards (10 most landed; share)": [[P.lab(L.ids[k]), round(cnt[k] / len(A[0]), 3)] for k in hubs_i], "features": FEATS, "vote ran (share of articles) T28 / fresh2": [nv_a, nv_b], "coefficients (standardised)": [round(float(c), 3) for c in clf.coef_[0]],
         "fresh2 AUROC (9 features)": round(float(roc_auc_score(right_b, p_b)), 3), "fresh2 AUROC (5 c2 features, same landing)": round(float(roc_auc_score(right_b, p_b0)), 3), "T28 AUROC (in-sample)": round(float(roc_auc_score(right_a, p_a)), 3),
         "line_permille": line, "line_p": round(line / 1000, 3), "fresh2 at the line": at_line(pm_b, right_b, line), "T28 at the line (in-sample)": at_line(pm_a, right_a, line),
         "fresh2 max coverage with running accuracy >= 0.80": _max_cov(p_b, right_b), "fresh2 max coverage (5 c2 features)": _max_cov(p_b0, right_b), "T28 max coverage with running accuracy >= 0.80 (in-sample)": _max_cov(p_a, right_a),
         "reliability fresh2: p bin -> observed accuracy, n": reliability(p_b, right_b), "fresh2 acc and p at coverage": {str(c): _acc_at(p_b, right_b, c) for c in (0.75, 0.5, 0.25)},
         "fresh2 safe-abstain bar (accuracy >= 0.80 at coverage >= 0.50)": {"accuracy at coverage 0.50": _acc_at(p_b, right_b, 0.5)[0], "pass": _acc_at(p_b, right_b, 0.5)[0] >= 0.80}}
    print(json.dumps(m, indent=1))
    if a.metrics: json.dump(m, open(a.metrics, "w"), indent=1)
    if a.write:
        cal = {"version": "landing_calibration_v1", "written": time.strftime("%Y-%m-%d"), "method": "StandardScaler + LogisticRegression(C=1) on whether the landing's level-1 code (by code) equals the MN-DS gold level-1 code", "fit_set": "MN-DS T28 clean (%d items), scored on fresh2 (%d items)" % (len(ya), len(yb)), "features": FEATS, "scaler_mean": [float(x) for x in sc.mean_], "scaler_scale": [float(x) for x in sc.scale_],
               "coef": [float(x) for x in clf.coef_[0]], "intercept": float(clf.intercept_[0]), "damp_k": DAMP_K, "hubs": sorted(hubs), "share": {L.ids[k]: round(float(share[k]), 6) for k in np.nonzero(share)[0]}, "cards_sha": L.cards_sha, "iptc_release": med, "table": table()["version"], "gate": bool(a.gate), "gate_rule": "gate false (ungated, owner choice L2744, round 3): the sentence vote counts on every article with a sentence of 40+ characters; gate true: only when the 3 best cards disagree on the level-1 code (agree3 < 3), voted, vote_l1 and vote_top are 0 otherwise",
               "as_of": {"run_id": "fit-T28-" + time.strftime("%Y-%m-%d"), "seq": len(ya), "label_version": "%s/%s" % (med, L.cards_sha[:8])},   # build spec 2.6: seq = number of fit items (a fit has no article counter)
               "line_permille": line, "line_rule": "T28 items sorted by floor(1000p); line = p of the last item (%d or more items in) whose running accuracy is still >= 0.80; decision = ANSWER_L1 iff floor(1000p) >= line_permille" % MINN,
               "fresh2_check": {"at_the_line": m["fresh2 at the line"], "AUROC": m["fresh2 AUROC (9 features)"], "max_coverage_at_0.80": m["fresh2 max coverage with running accuracy >= 0.80"], "accuracy_at_coverage_0.50": m["fresh2 acc and p at coverage"]["0.5"][0]}, "L1_top1": {"T28": out["v1 (damped)"]["T28 l1 top1"], "fresh2": out["v1 (damped)"]["fresh2 l1 top1"]}}
        json.dump(cal, open(a.write, "w"), indent=1); print("wrote", a.write)
def selftest():
    cal = {"features": FEATS, "scaler_mean": [0] * 9, "scaler_scale": [1] * 9, "coef": [1] + [0] * 8, "intercept": 0.0, "line_permille": 600}
    art = [{"path_codes": ["medtop:11000000", "medtop:11006000"], "qcode": "medtop:11006000", "score": 0.7}, {"path_codes": ["medtop:11000000"], "qcode": "x", "score": 0.6}, {"path_codes": ["medtop:04000000"], "qcode": "y", "score": 0.5}]
    res = {"article": art, "n_sentences": 4, "vote_all": {"medtop:11000000": 3, "medtop:04000000": 1}, "vote_by_code": [("medtop:11000000", 3), ("medtop:04000000", 1)], "rank_scores": [0.7, 0.6]}
    f = features(res, 1500, {"y"}); assert f["agree3"] == 2 and f["voted"] == 1.0 and f["vote_l1"] == 0.75 and f["vote_top"] == 1.0 and f["hub"] == 0.0 and f["margin"] == 0.1, f
    art3 = [{"path_codes": ["medtop:11000000"], "qcode": q, "score": 0.7} for q in "abc"]; u = features({**res, "article": art3}, 1500, set()); assert u["voted"] == 1.0 and u["vote_l1"] == 0.75, u   # ungated (default): the vote counts even when the 3 best cards agree
    g = features({**res, "article": art3}, 1500, set(), True); assert g["agree3"] == 3 and g["voted"] == 0.0 and g["vote_l1"] == 0.0 and g["vote_top"] == 0.0 and g["log_n_sent"] == round(math.log1p(4), 4), g   # agree3 3: the vote is not used, even if it was computed
    assert permille(0.7569996) == 756 and decide_pm(756, {"line_permille": 757}) == "ABSTAIN" and decide_pm(757, {"line_permille": 757}) == "ANSWER_L1" and decide(0.7569996, {"line_permille": 757}) == "ABSTAIN"
    p = prob(f, cal); assert abs(p - 1 / (1 + math.exp(-0.7))) < 1e-9 and decide(p, cal) == "ANSWER_L1" and decide(0.59, cal) == "ABSTAIN" and decide(0.6, cal) == "ANSWER_L1"
    pm = np.array([900] * 40 + [800] * 40 + [700] * 40 + [600] * 40); r = np.array([1] * 40 + [1] * 36 + [0] * 4 + [1] * 24 + [0] * 16 + [0] * 40, bool); assert find_line(pm, r) == 700, find_line(pm, r)
    print("selftest ok")
if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
