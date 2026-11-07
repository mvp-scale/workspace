"""T42 (pre-registered L1027): do the tools extract enough to train the BitMobs; how many classes per model; Domain and Area one model or two.
Data: MN-DS (human labels, 10917 articles, 17 first-level, 109 second-level categories, 215 publishers) and the Claude-labelled short stories (story type, 16 kinds).
    /workspace/models/embed-zs/.venv/bin/python tools_to_training.py   (from projects/world-state)  ->  runs/pulse/tools_to_training.json, tools_to_training_flat.json"""
import sys, json, re, time, random, collections, numpy as np
sys.path.insert(0, ".")
from multiprocessing import Pool
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC
OUT = "runs/pulse/"; SEED = 20261107; CAP = 12000
SPOTS = ["quote", "money", "percent", "quantity", "date", "attribution", "negation", "modal", "change", "event", "entity"]
FK = [(k, s) for k in ("amount", "date", "name", "triple") for s in ("stated", "unbound", "invalid")]
def init():
    global G, FL; import scan_gate as G, facts_lib as FL
def feats(job):
    text, anchor = job; t = re.sub(r"\s+", " ", text)[:CAP]; t0 = time.perf_counter(); sp, sents = G.scan(t, anchor); t1 = time.perf_counter()
    f = FL.facts_for(t, anchor)[0]; t2 = time.perf_counter(); n = max(len(t), 1) / 1000; c = collections.Counter(s[2] for s in sp); fc = collections.Counter((x["kind"], x["status"]) for x in f)
    v = [c[k] / n for k in SPOTS] + [fc[k] / n for k in FK] + [np.log1p(len(t)), len(sents) / n]
    return v, (t1 - t0) * 1000, (t2 - t1) * 1000
def run_tools(jobs):
    t0 = time.time()
    with Pool(16, initializer=init) as p: R = p.map(feats, jobs, chunksize=25)
    return np.array([r[0] for r in R], dtype=np.float32), np.array([r[1] for r in R]), np.array([r[2] for r in R]), time.time() - t0
def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); a = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return [round((c - a) / d, 4), round((c + a) / d, 4)]
def acc(S, y, classes):
    o = np.argsort(-S, 1)[:, :2]; t1 = (o[:, 0] == y); t2 = t1 | (o[:, 1] == y); return {"top1": round(float(t1.mean()), 4), "top1_range": wilson(int(t1.sum()), len(y)), "top2": round(float(t2.mean()), 4), "top2_range": wilson(int(t2.sum()), len(y))}
res = {}; flat = {}
# ---------------------------------------------------------------- MN-DS
rows = [json.loads(l) for l in open("/workspace/data/anchors/mn_ds/train.jsonl")]
rows = [r for r in rows if (r.get("title") or "").strip() and (r.get("content") or "").strip() and r.get("category_level_1") and r.get("category_level_2")]
print("articles", len(rows), flush=True)
txt = [r["title"] + ". " + r["content"] for r in rows]; l1 = [r["category_level_1"] for r in rows]; l2 = [r["category_level_1"] + " / " + r["category_level_2"] for r in rows]
C1 = sorted(set(l1)); C2 = sorted(set(l2)); y1 = np.array([C1.index(x) for x in l1]); y2 = np.array([C2.index(x) for x in l2]); par = np.array([C1.index(c.split(" / ")[0]) for c in C2])
X, tsc, tfa, wall = run_tools([(t, r["date"] + "T00:00:00Z") for t, r in zip(txt, rows)])
res["A_speed"] = {"articles": len(rows), "scan_ms_median": round(float(np.median(tsc)), 2), "scan_ms_p95": round(float(np.percentile(tsc, 95)), 2), "facts_ms_median": round(float(np.median(tfa)), 1), "facts_ms_p95": round(float(np.percentile(tfa, 95)), 1), "pass_seconds_16_workers": round(wall, 1)}
print(res["A_speed"], flush=True); np.save(OUT + "tools_features_mnds.npy", X)
src = collections.Counter(r["source"] for r in rows); pubs = sorted(src); rng = random.Random(SEED); rng.shuffle(pubs); test_pubs = set(); n = 0
for p in pubs:
    if n >= 0.2 * len(rows): break
    test_pubs.add(p); n += src[p]
te = np.array([r["source"] in test_pubs for r in rows]); tr = ~te; print("train", int(tr.sum()), "test", int(te.sum()), "test publishers", len(test_pubs), flush=True)
res["split"] = {"train": int(tr.sum()), "test": int(te.sum()), "test_publishers": len(test_pubs), "classes_l1": len(C1), "classes_l2": len(C2), "test_l2_classes_present": int(len(set(y2[te])))}
vec = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=300000, sublinear_tf=True); W = vec.fit_transform([t[:CAP] for t in txt]) if False else None
t0 = time.time(); vec.fit([txt[i][:CAP] for i in np.where(tr)[0]]); W = vec.transform([t[:CAP] for t in txt]); print("tfidf", W.shape, round(time.time() - t0), "s", flush=True)
sc = StandardScaler().fit(X[tr]); Xs = sc.transform(X).astype(np.float32); WT = hstack([W, csr_matrix(Xs)]).tocsr()
def svm(M, y, C=0.5): return LinearSVC(C=C).fit(M[tr], y[tr])
B = {}
for lev, y, CL in (("l1", y1, C1), ("l2", y2, C2)):
    maj = np.bincount(y[tr]).argmax(); majacc = float((y[te] == maj).mean())
    lr = LogisticRegression(max_iter=600, C=1.0).fit(Xs[tr], y[tr]); S_t = lr.predict_proba(Xs[te]) if False else None
    St = np.full((te.sum(), len(CL)), -1e9); St[:, lr.classes_] = lr.decision_function(Xs[te]) if len(lr.classes_) > 2 else 0
    m_w = svm(W, y); Sw = np.full((te.sum(), len(CL)), -1e9); Sw[:, m_w.classes_] = m_w.decision_function(W[te])
    m_wt = svm(WT, y); Swt = np.full((te.sum(), len(CL)), -1e9); Swt[:, m_wt.classes_] = m_wt.decision_function(WT[te])
    B[lev] = {"S_w": Sw}
    res["B_" + lev] = {"commonest_answer_top1": round(majacc, 4), "tools_only": acc(St, y[te], CL), "words": acc(Sw, y[te], CL), "words_plus_tools": acc(Swt, y[te], CL)}
    print(lev, json.dumps(res["B_" + lev]), flush=True)
# ---------------------------------------------------------------- C grouping
S1 = B["l1"]["S_w"]; S2 = B["l2"]["S_w"]; yt1 = y1[te]; yt2 = y2[te]
direct_l2 = acc(S2, yt2, C2); via = par[S2.argmax(1)]; l1_via_l2 = float((via == yt1).mean())
pred1 = S1.argmax(1); M = np.where(par[None, :] == pred1[:, None], S2, -1e9); hier = acc(M, yt2, C2)
res["C_group"] = {"l2_direct": direct_l2, "l2_inside_predicted_l1": hier, "l1_direct_top1": res["B_l1"]["words"]["top1"], "l1_derived_from_l2_top1": round(l1_via_l2, 4), "l1_derived_range": wilson(int((via == yt1).sum()), len(yt1))}
print("C_group", json.dumps(res["C_group"]), flush=True)
# class-count curve
curve = {}; idx_tr = np.where(tr)[0]; idx_te = np.where(te)[0]
for k in (5, 10, 20, 40, 80, 109):
    accs = []
    for d in range(3):
        rr = random.Random(SEED + 100 * k + d); cls = rr.sample(range(len(C2)), k); a = idx_tr[np.isin(y2[idx_tr], cls)]; b = idx_te[np.isin(y2[idx_te], cls)]
        if len(b) < 30: continue
        m = LinearSVC(C=0.5).fit(W[a], y2[a]); accs.append(float((m.predict(W[b]) == y2[b]).mean()))
    curve[str(k)] = {"top1_mean": round(float(np.mean(accs)), 4), "draws": len(accs), "chance": round(1 / k, 4)}; print("classes", k, curve[str(k)], flush=True)
res["C_class_count"] = curve
ex = {}
for nper in (10, 20, 40, 60, 0):
    rr = random.Random(SEED + nper); a = []
    for c in range(len(C2)):
        ii = [i for i in idx_tr if y2[i] == c]; rr.shuffle(ii); a += ii if nper == 0 else ii[:nper]
    a = np.array(a); m = LinearSVC(C=0.5).fit(W[a], y2[a]); Sx = np.full((len(idx_te), len(C2)), -1e9); Sx[:, m.classes_] = m.decision_function(W[idx_te])
    ex[str(nper or "full")] = {"train_articles": int(len(a)), "l2_top1": acc(Sx, yt2, C2)["top1"], "l1_top1_via_l2": round(float((par[Sx.argmax(1)] == yt1).mean()), 4)}; print("per class", nper, ex[str(nper or "full")], flush=True)
res["C_examples_per_class"] = ex
# ---------------------------------------------------------------- D short stories, Claude labels
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
S = {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] == "sonnet" and r["version"] == "ws-v2-frozen": S[r["item_id"]] = r
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
ids = sorted(i for i in S if i in pool); T = [re.sub(r"\s+", " ", pool[i])[:600] for i in ids]
XD, dsc, dfa, dwall = run_tools([(t, None) for t in T]); res["D_speed"] = {"stories": len(ids), "scan_ms_median": round(float(np.median(dsc)), 2), "facts_ms_median": round(float(np.median(dfa)), 1), "pass_seconds_16_workers": round(dwall, 1)}
grp = {}; gid = np.array([grp.setdefault(re.sub(r"\W+", "", t.lower())[:60], len(grp)) for t in T]); a, b = next(GroupShuffleSplit(1, test_size=0.2, random_state=0).split(T, groups=gid))
v2 = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True).fit([T[i] for i in a]); WD = v2.transform(T); sD = StandardScaler().fit(XD[a]); XDs = sD.transform(XD).astype(np.float32); WTD = hstack([WD, csr_matrix(XDs)]).tocsr()
ST = [S[i]["story_type"] for i in ids]; CS = sorted(set(ST)); ys = np.array([CS.index(x) for x in ST])
def accs(M): m = LinearSVC(C=0.5).fit(M[a], ys[a]); return round(float((m.predict(M[b]) == ys[b]).mean()), 4)
lrS = LogisticRegression(max_iter=600).fit(XDs[a], ys[a])
res["D_story_type"] = {"classes": len(CS), "commonest_answer": round(float((ys[b] == np.bincount(ys[a]).argmax()).mean()), 4), "tools_only": round(float(lrS.score(XDs[b], ys[b])), 4), "words": accs(WD), "words_plus_tools": accs(WTD), "test_stories": int(len(b))}
kinds = sorted({k for i in ids for k in S[i]["kinds"]}); apw, apt, per = [], [], {}
for k in kinds:
    y = np.array([int(k in S[i]["kinds"]) for i in ids])
    if y[b].sum() < 15 or y[a].sum() < 15: continue
    m1 = LinearSVC(C=0.5, class_weight="balanced").fit(WD[a], y[a]); m2 = LinearSVC(C=0.5, class_weight="balanced").fit(WTD[a], y[a])
    p1 = average_precision_score(y[b], m1.decision_function(WD[b])); p2 = average_precision_score(y[b], m2.decision_function(WTD[b])); apw.append(p1); apt.append(p2); per[k] = [round(p1, 3), round(p2, 3)]
res["D_kinds"] = {"kinds_scored": len(apw), "mean_ap_words": round(float(np.mean(apw)), 4), "mean_ap_words_plus_tools": round(float(np.mean(apt)), 4), "kinds_improved": int(sum(1 for x, y_ in zip(apw, apt) if y_ > x + 0.005)), "per_kind_ap_words_then_plus_tools": per}
print("D", json.dumps({k: v for k, v in res.items() if k.startswith("D_") and k != "D_kinds"}), res["D_kinds"]["mean_ap_words"], res["D_kinds"]["mean_ap_words_plus_tools"], flush=True)
json.dump(res, open(OUT + "tools_to_training.json", "w"), indent=1)
f = {"scan_ms_median": res["A_speed"]["scan_ms_median"], "facts_ms_median": res["A_speed"]["facts_ms_median"], "pass_seconds": res["A_speed"]["pass_seconds_16_workers"],
     "l1_commonest": res["B_l1"]["commonest_answer_top1"], "l1_tools_top1": res["B_l1"]["tools_only"]["top1"], "l1_words_top1": res["B_l1"]["words"]["top1"], "l1_words_low": res["B_l1"]["words"]["top1_range"][0], "l1_words_tools_top1": res["B_l1"]["words_plus_tools"]["top1"],
     "l2_commonest": res["B_l2"]["commonest_answer_top1"], "l2_tools_top1": res["B_l2"]["tools_only"]["top1"], "l2_words_top1": res["B_l2"]["words"]["top1"], "l2_words_low": res["B_l2"]["words"]["top1_range"][0], "l2_words_tools_top1": res["B_l2"]["words_plus_tools"]["top1"],
     "l2_direct_top1": direct_l2["top1"], "l2_hier_top1": hier["top1"], "l1_derived_top1": res["C_group"]["l1_derived_from_l2_top1"],
     "k5": curve["5"]["top1_mean"], "k20": curve["20"]["top1_mean"], "k109": curve["109"]["top1_mean"], "n40": ex["40"]["l2_top1"], "nfull": ex["full"]["l2_top1"],
     "story_words": res["D_story_type"]["words"], "story_words_tools": res["D_story_type"]["words_plus_tools"], "story_tools": res["D_story_type"]["tools_only"], "story_commonest": res["D_story_type"]["commonest_answer"],
     "kinds_ap_words": res["D_kinds"]["mean_ap_words"], "kinds_ap_words_tools": res["D_kinds"]["mean_ap_words_plus_tools"]}
json.dump(f, open(OUT + "tools_to_training_flat.json", "w")); print("DONE", f)
