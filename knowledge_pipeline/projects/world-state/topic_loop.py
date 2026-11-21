"""topic_loop (self-improvement loop, round 1; design docs/research/2026-11-20-self-improvement-loop.md, owner decision L2751, licence L2753).
Round 1 trains ONE small re-ranker (logistic regression on the landing's 1,059 card scores) on MN-DS `train` publishers and judges it on a clean `confirm` half.
Steps (each one CPU/GPU job < 1 h):  split | cache | gpu | score        run:  /workspace/models/embed-zs/.venv/bin/python topic_loop.py <step>
 split  -> specs/topic_loop_split_v1.json   (dedup by title60 + body200, publisher split ~70/30, test-clean -> select/confirm by publisher, hashed; leakage assertion in assert_no_leak)
 cache  -> runs/pulse/topic_loop/r1/cache_cpu.npz  (landing card scores by bge-small for every MN-DS item and every runs-v6 queue article, bge vectors, TF-IDF fit on queue texts only)
 gpu    -> runs/pulse/topic_loop/r1/cache_gpu.npz  (secondary b: Qwen3-Embedding-4B already on disk, cards + texts)
 score  -> runs/pulse/topic_loop/r1/results.json + primary_reranker.pkl   (pre-registration file prereg.json must exist and is hashed into the results)
Nothing here is wired into live_trace or the decider."""
import sys, os, json, re, hashlib, collections, pathlib, pickle, time
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent; MN = "/workspace/data/anchors/mn_ds/"; OUT = HERE / "runs/pulse/topic_loop/r1"; SPLIT = HERE / "specs/topic_loop_split_v1.json"
TRACE = "/workspace/demo/mockups/structure-live/runs-v6/trace"; SEED = "topic_loop_split_v1"; TRAIN_FRAC = 0.70
SETS = [("T28", "items_T28.jsonl", "gold_T28_clean.json"), ("T28b", "items_T28b.jsonl", "gold_T28b.json"), ("fresh", "items_fresh.jsonl", "gold_fresh.json"), ("fresh2", "items_fresh2.jsonl", "gold_fresh2.json")]
norm = lambda s: re.sub(r"\s+", " ", (s or "").lower()).strip()
def title60(t): return norm(t.split(". ")[0])[:60]
def body200(t):
    i = t.find(". "); b = norm(t[i + 2:])[:200] if i >= 0 else ""; return b if len(b) >= 150 else None
def h(s): return int(hashlib.sha256((SEED + "|" + s).encode()).hexdigest(), 16)
def sha_file(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def load_items():
    """-> list of dict(id, text, set, l1 code) in a fixed order, de-duplicated (id, title60, body200), with a publisher from train.jsonl (title match); items without one unique publisher are dropped and counted."""
    from mnds_codes import gold_codes
    tr = [json.loads(l) for l in open(MN + "train.jsonl")]; idx = collections.defaultdict(list)
    for r in tr: idx[norm(r["title"])[:25]].append(r)
    seen_id = set(); seen_t = set(); seen_b = set(); items = []; drop = collections.Counter()
    for name, f, g in SETS:
        G = json.load(open(MN + g))
        for l in open(MN + f):
            x = json.loads(l); i = x["id"]
            if i not in G or i in seen_id: drop["no gold or repeated id"] += 1; continue
            c1 = gold_codes(G[i])[0]
            if not c1: drop["gold l1 not an IPTC code"] += 1; continue
            seen_id.add(i); t = x["text"]; k1 = title60(t); k2 = body200(t)
            if k1 in seen_t or (k2 and k2 in seen_b): drop["duplicate (title60 or body200)"] += 1; continue
            seen_t.add(k1); k2 and seen_b.add(k2)
            nt = norm(t); m = [r for r in idx.get(nt[:25], []) if nt.startswith(norm(r["title"]))]; pubs = {r["source"] for r in m}
            if len(pubs) != 1: drop["no unique publisher in train.jsonl" if not pubs else "title in several publishers"] += 1; continue
            items.append({"id": i, "text": t, "set": name, "l1": c1, "pub": next(iter(pubs))})
    return items, dict(drop)
def make_split():
    items, drop = load_items(); n = len(items); pc = collections.Counter(x["pub"] for x in items)
    order = sorted(pc, key=lambda p: h("pub|" + p)); train_pubs = []; acc = 0
    for p in order:
        if acc >= TRAIN_FRAC * n: break
        train_pubs.append(p); acc += pc[p]
    test_pubs = [p for p in order if p not in set(train_pubs)]
    tp = sorted(test_pubs, key=lambda p: h("half|" + p)); sel = []; a = 0; tot = sum(pc[p] for p in tp)
    for p in tp:
        if a >= tot / 2: break
        sel.append(p); a += pc[p]
    conf = [p for p in tp if p not in set(sel)]
    part = {**{p: "train" for p in train_pubs}, **{p: "select" for p in sel}, **{p: "confirm" for p in conf}}
    ids = {k: sorted(x["id"] for x in items if part[x["pub"]] == k) for k in ("train", "select", "confirm")}
    cl = {k: dict(collections.Counter(x["l1"] for x in items if part[x["pub"]] == k)) for k in ids}
    spec = {"version": "topic_loop_split_v1", "seed": SEED, "rule": "de-duplicate (id, title60, body200 prefix) over T28 (clean gold) + T28b + fresh + fresh2; publisher from data/anchors/mn_ds/train.jsonl by title match (items without exactly one publisher dropped); publishers ordered by sha256(seed|pub), first publishers up to 70% of items -> train, the rest test-clean; test-clean publishers ordered by sha256(seed|half|pub), first half of items -> select, rest -> confirm. Split is by publisher, so no publisher is in two parts.",
            "counts": {"items_kept": n, "dropped": drop, "publishers": len(pc), "train": len(ids["train"]), "select": len(ids["select"]), "confirm": len(ids["confirm"]),
                       "publishers_train": len(train_pubs), "publishers_select": len(sel), "publishers_confirm": len(conf)}, "class_counts": cl, "publishers": part, "ids": ids}
    spec["content_sha256"] = hashlib.sha256(json.dumps({k: spec[k] for k in ("seed", "ids", "publishers")}, sort_keys=True).encode()).hexdigest(); json.dump(spec, open(SPLIT, "w"), indent=1); return spec, items
def assert_no_leak(spec, train_ids, train_pubs=None, items=None):
    """Leakage assertion: no test-clean (select/confirm) id, and no test-clean publisher, in any training input."""
    test_ids = set(spec["ids"]["select"]) | set(spec["ids"]["confirm"]); test_pubs = {p for p, k in spec["publishers"].items() if k != "train"}
    assert not (set(train_ids) & test_ids), "test-clean id in training input"
    assert not (set(spec["ids"]["train"]) & test_ids), "id in train and test-clean"
    if items is not None: assert not ({x["pub"] for x in items if x["id"] in set(train_ids)} & test_pubs), "test-clean publisher in training input"
    assert not ({p for p, k in spec["publishers"].items() if k == "train"} & test_pubs); return True
def load_queue():
    rows = []
    for f in sorted(os.listdir(TRACE + "/a"), key=lambda s: int(s.split(".")[0])):
        a = json.load(open(TRACE + "/a/" + f)); al = a["article_line"]
        if al.get("state") != "traced": continue
        rows.append({"seq": int(f.split(".")[0]), "id": al["id"], "text": a["text"], "source": al.get("source"), "landing_l1_traced": (((al.get("journal") or {}).get("ids") or {}).get("topic") or {}).get("l1")})
    return rows
def land_setup():
    os.environ.setdefault("OMP_NUM_THREADS", "8"); os.environ["CUDA_VISIBLE_DEVICES"] = ""; sys.path.insert(0, str(HERE)); os.chdir(HERE)
    import spacy; from structure_pack import Pack; from pack_view import Landing
    P = Pack(spacy.blank("en")); L = Landing(P, alias=False); return P, L
def step_split():
    spec, items = make_split(); print(json.dumps(spec["counts"], indent=1)); print({k: len(v) for k, v in spec["class_counts"].items()}, "min class count in select/confirm:", {k: min(spec["class_counts"][k].values()) for k in ("select", "confirm")})
    assert_no_leak(spec, spec["ids"]["train"], items=items); print("leakage assertion on the split: OK", spec["content_sha256"][:16])
def step_cache():
    from sklearn.feature_extraction.text import TfidfVectorizer
    spec = json.load(open(SPLIT)); items, _ = load_items(); byid = {x["id"]: x for x in items}; order = spec["ids"]["train"] + spec["ids"]["select"] + spec["ids"]["confirm"]; assert all(i in byid for i in order)
    P, L = land_setup(); t0 = time.time(); Q = load_queue(); T = [byid[i]["text"][:2000] for i in order]; TQ = [r["text"][:2000] for r in Q]
    enc = lambda tx: L.emb.encode(tx, batch_size=64, normalize_embeddings=True, convert_to_numpy=True)
    Vm = enc(T).astype(np.float32); Vq = enc(TQ).astype(np.float32); Sm = (Vm @ L.E.T).astype(np.float32); Sq = (Vq @ L.E.T).astype(np.float32)
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True).fit([r["text"] for r in Q])   # queue texts only
    pickle.dump(vec, open(OUT / "tfidf_queue_only.pkl", "wb"))
    np.savez_compressed(OUT / "cache_cpu.npz", order=np.array(order), q_id=np.array([r["id"] for r in Q]), Sm=Sm, Sq=Sq, Vm=Vm, Vq=Vq, card_ids=np.array(L.ids), cards_sha=np.array(L.cards_sha))
    print("cache_cpu: mnds", Sm.shape, "queue", Sq.shape, "tfidf vocab", len(vec.vocabulary_), "seconds", round(time.time() - t0))
QWEN_TASK = "Instruct: Given a news article, retrieve the IPTC media topic description it is about\nQuery: "
def step_gpu():
    """Secondary (b): Qwen3-Embedding-4B (already on disk, /workspace/data/hf/hub; the registry's BitMob Domain model was distilled from it). Re-embeds the 1,059 cards (documents, no instruction) and the same texts as step cache (queries, with QWEN_TASK). No download (HF_HUB_OFFLINE)."""
    os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["TRANSFORMERS_OFFLINE"] = "1"; sys.path.insert(0, str(HERE)); os.chdir(HERE)
    import torch; from sentence_transformers import SentenceTransformer
    z = np.load(OUT / "cache_cpu.npz", allow_pickle=False); spec = json.load(open(SPLIT)); items, _ = load_items(); byid = {x["id"]: x for x in items}; order = [str(i) for i in z["order"]]; Q = load_queue(); assert [r["id"] for r in Q] == [str(i) for i in z["q_id"]]
    P, L = land_setup(); cards = L.cards; assert hashlib.sha256("\n".join(cards).encode()).hexdigest() == str(z["cards_sha"])
    t0 = time.time(); m = SentenceTransformer("Qwen/Qwen3-Embedding-4B", device="cuda", model_kwargs={"torch_dtype": torch.bfloat16}); m.max_seq_length = 512
    E = m.encode(cards, batch_size=32, normalize_embeddings=True, convert_to_numpy=True); t1 = time.time()
    enc = lambda tx: m.encode([QWEN_TASK + t for t in tx], batch_size=32, normalize_embeddings=True, convert_to_numpy=True)
    Vm = enc([byid[i]["text"][:2000] for i in order]); Vq = enc([r["text"][:2000] for r in Q]); Sm = (Vm @ E.T).astype(np.float32); Sq = (Vq @ E.T).astype(np.float32)
    np.savez_compressed(OUT / "cache_gpu.npz", Sm=Sm, Sq=Sq, model=np.array("Qwen/Qwen3-Embedding-4B"), seconds=np.array(time.time() - t0), peak_gb=np.array(torch.cuda.max_memory_allocated() / 1e9))
    print("gpu done: cards %.0fs total %.0fs peak GB %.1f" % (t1 - t0, time.time() - t0, torch.cuda.max_memory_allocated() / 1e9))

SEC = {"business": "economy, business and finance", "science": "science and technology", "tech": "science and technology", "health": "health", "entertain": "arts, culture, entertainment and media", "politic": "politics and government", "environment": "environment", "climate": "environment"}   # field_test.py L2721
def holm(ps):
    o = sorted(range(len(ps)), key=lambda i: ps[i]); adj = [None] * len(ps); run = 0.0
    for r, i in enumerate(o): run = max(run, min(1.0, (len(ps) - r) * ps[i])); adj[i] = run
    return adj
def step_score():
    from sklearn.linear_model import LogisticRegression; from sklearn.preprocessing import StandardScaler; from sklearn.model_selection import GroupKFold
    import sqlite3; t00 = time.time(); pre = OUT / "prereg.json"; assert pre.exists(); pre_sha = sha_file(pre)
    z = np.load(OUT / "cache_cpu.npz", allow_pickle=False); zg = np.load(OUT / "cache_gpu.npz", allow_pickle=False) if (OUT / "cache_gpu.npz").exists() else None
    spec = json.load(open(SPLIT)); items, _ = load_items(); byid = {x["id"]: x for x in items}; order = [str(i) for i in z["order"]]; n = len(order)
    P, L = land_setup(); ids = list(L.ids); assert ids == [str(i) for i in z["card_ids"]]; l1c = np.array([P.chain(q)[0] for q in ids]); codes = sorted(set(l1c)); ci = {c: k for k, c in enumerate(codes)}; K = len(codes); lab = {c: P.lab(c) for c in codes}
    part = np.array([("train" if i in set(spec["ids"]["train"]) else "select" if i in set(spec["ids"]["select"]) else "confirm") for i in order]); tr = np.where(part == "train")[0]; se = np.where(part == "select")[0]; co = np.where(part == "confirm")[0]
    y = np.array([ci[byid[i]["l1"]] for i in order]); pub = np.array([byid[i]["pub"] for i in order]); Sm = z["Sm"].astype(np.float64); Sq = z["Sq"].astype(np.float64)
    assert_no_leak(spec, [order[i] for i in tr], items=items)
    cal = json.load(open(HERE / "specs/landing_calibration_v1.json")); share = np.array([cal["share"].get(q, 0.0) for q in ids])
    onehot = np.zeros((len(ids), K)); onehot[np.arange(len(ids)), [ci[c] for c in l1c]] = 1
    def cmax(S, sh):   # per-code best damped card score (n x K)
        D = S - 0.5 * sh; M = np.full((len(S), K), -9.0)
        for k in range(K): M[:, k] = D[:, l1c == codes[k]].max(1)
        return M
    Ml, Mlq = cmax(Sm, share), cmax(Sq, share); res = {"prereg_sha256": pre_sha, "split_sha256": spec["content_sha256"], "split_counts": spec["counts"], "classes": [lab[c] for c in codes]}
    # ---- primary: C by publisher-held-out CV inside train
    Xs = StandardScaler().fit(Sm[tr]); Xtr = Xs.transform(Sm[tr]); gk = GroupKFold(n_splits=5); cv = {}
    def macro(yt, yp): return float(np.mean([(yp[yt == k] == k).mean() for k in np.unique(yt)]))
    FAST = os.environ.get("TL_FAST") == "1"; fitc = OUT / ("primary_fit_cache_dev.pkl" if FAST else "primary_fit_cache.pkl")
    if fitc.exists(): cv, Cbest, clf = pickle.load(open(fitc, "rb")); print("primary fit loaded from cache", flush=True)
    else:
        from joblib import Parallel, delayed
        from threadpoolctl import threadpool_limits
        Cs = (0.03,) if FAST else (0.003, 0.01, 0.03, 0.1, 0.3, 1.0); folds = list(gk.split(Xtr, y[tr], pub[tr]))[:1 if FAST else 5]
        for a, b in folds: assert_no_leak(spec, [order[tr[i]] for i in a])
        def one(C, a, b):
            with threadpool_limits(limits=1):
                m = LogisticRegression(C=C, class_weight="balanced", max_iter=(60 if FAST else 400)).fit(Xtr[a], y[tr][a]); return macro(y[tr][b], m.classes_[m.predict(Xtr[b])])
        out = Parallel(n_jobs=15)(delayed(one)(C, a, b) for C in Cs for a, b in folds)
        for j, C in enumerate(Cs): cv[C] = round(float(np.mean(out[j * len(folds):(j + 1) * len(folds)])), 4); print("CV C", C, cv[C], round(time.time() - t00), "s", flush=True)
        Cbest = max(cv, key=cv.get); clf = LogisticRegression(C=Cbest, class_weight="balanced", max_iter=(60 if FAST else 800)).fit(Xtr, y[tr]); pickle.dump((cv, Cbest, clf), open(fitc, "wb"))
    res["primary_cv_macro_recall_by_C"] = cv; res["primary_C"] = Cbest; assert list(clf.classes_) == list(range(K)); Pm = clf.predict_proba(Xs.transform(Sm)); Pq = clf.predict_proba(Xs.transform(Sq)); print("primary fit done", round(time.time() - t00), flush=True)
    # ---- live mix from the deployed landing on runs-v6 (traced l1)
    Q = load_queue(); assert [r["id"] for r in Q] == [str(i) for i in z["q_id"]]; tl = [r["landing_l1_traced"] for r in Q]; cnt = collections.Counter(t for t in tl if t in ci); live = np.array([cnt.get(c, 0) for c in codes], float); live = np.maximum(live / live.sum(), 1e-3); live /= live.sum()
    res["live_mix_runs_v6"] = {lab[c]: round(float(live[ci[c]]), 4) for c in codes}; res["queue_articles"] = len(Q); res["traced_l1_missing"] = sum(1 for t in tl if t not in ci)
    # ---- options (predictions, top-2, live-corrected predictions)
    def top2(M): return np.argsort(-M, 1)[:, :2]
    opt = {}; opt["landing"] = {"M": Ml, "Mq": Mlq}
    opt["P1"] = {"M": Pm, "Mq": Pq, "Mlive": Pm * live, "Mqlive": Pq * live}
    if zg is not None:
        Sg_ = zg["Sm"].astype(np.float64); shg = np.bincount(Sg_[tr].argmax(1), minlength=len(ids)) / len(tr); Mg, Mgq = cmax(Sg_, shg), cmax(zg["Sq"].astype(np.float64), shg); opt["b"] = {"M": Mg, "Mq": Mgq}
        res["b_model"] = {"model": str(zg["model"]), "seconds": round(float(zg["seconds"])), "peak_gpu_gb": round(float(zg["peak_gb"]), 1)}
    for o in opt.values(): o["pred"] = o["M"].argmax(1); o["t2"] = top2(o["M"]); o["pl"] = (o["Mlive"] if "Mlive" in o else o["M"]).argmax(1)
    for nm in opt: opt[nm]["c1"] = opt[nm]["pred"] == y; opt[nm]["c2"] = (opt[nm]["t2"] == y[:, None]).any(1)
    def share_err(pl, yy, idx):
        yi = yy[idx]; nc = np.bincount(yi, minlength=K); pr = nc > 0; lp = np.where(pr, live, 0.0); lp = lp / lp.sum(); w = lp[yi] / nc[yi]; ps = np.bincount(pl[idx], weights=w, minlength=K); d = np.abs(ps - lp); return d.sum() / K, 0.5 * d.sum()
    def mets(nm, idx):
        o = opt[nm]; yi = y[idx]; rec = [o["pred"][idx][yi == k].__eq__(k).mean() for k in np.unique(yi)]; mae, tv = share_err(o["pl"], y, idx)
        return {"top1": float(o["c1"][idx].mean()), "macro_recall": float(np.mean(rec)), "top2": float(o["c2"][idx].mean()), "share_mae": float(mae), "share_tv": float(tv)}
    rng = np.random.default_rng(20261120); cp = sorted(set(pub[co])); byp = {p: co[pub[co] == p] for p in cp}; B = 2000; boot = {nm: [] for nm in opt}
    for _ in range(B):
        idx = np.concatenate([byp[cp[j]] for j in rng.integers(0, len(cp), len(cp))])
        for nm in opt: boot[nm].append(mets(nm, idx))
    def summarize(nm, keys, base="landing", gain_sign=None):
        out = {}; pt = mets(nm, co); b0 = mets(base, co)
        for k in keys:
            sgn = -1 if k.startswith("share") else 1; d = np.array([sgn * (boot[nm][i][k] - boot[base][i][k]) for i in range(B)]); g = sgn * (pt[k] - b0[k])
            out[k] = {"option": round(pt[k], 4), "landing": round(b0[k], 4), "gain": round(g, 4), "ci95": [round(float(np.percentile(d, 2.5)), 4), round(float(np.percentile(d, 97.5)), 4)], "p_one_sided": round(float((d <= 0).mean()), 4)}
        return out
    K5 = ["top1", "macro_recall", "top2", "share_mae", "share_tv"]; res["confirm"] = {nm: summarize(nm, K5) for nm in opt if nm != "landing"}; res["confirm"]["landing_alone"] = {k: round(v, 4) for k, v in mets("landing", co).items()}; res["confirm_n"] = [int(len(co)), len(cp)]
    res["select"] = {nm: {k: round(v, 4) for k, v in mets_sel.items()} for nm in opt for mets_sel in [ (lambda nm_: (lambda idx: mets(nm_, idx))(se))(nm) ]}
    Vm_ = z["Vm"]; nn = (Vm_[co] @ Vm_[tr].T).max(1); keep_ = co[nn < 0.9]; res["near_duplicate_audit"] = {"confirm_items_with_train_neighbour_cos>0.95": int((nn > 0.95).sum()), ">0.90": int((nn > 0.9).sum()), "confirm_items_kept_below_0.90": int(len(keep_)), "P1_vs_landing_on_kept": {k: [round(mets("P1", keep_)[k], 4), round(mets("landing", keep_)[k], 4)] for k in ("top1", "macro_recall", "top2")}}
    # ---- secondary a: teacher blend, covered items only
    pil = {}
    for l in open(HERE / "runs/pulse/learn/pilot_rows_top2_v1.jsonl"):
        r = json.loads(l)
        if r.get("l1a") in ci: pil[r["id"]] = (ci[r["l1a"]], ci.get(r.get("l1b"), -1))
    pos = {i: k for k, i in enumerate(order)}; cov = np.array([pos[i] for i in pil if i in pos]); ta = np.array([pil[order[k]][0] for k in cov]); tb = np.array([pil[order[k]][1] for k in cov]); lp_ = opt["landing"]["pred"][cov]; bl = np.where((lp_ == ta) | (lp_ == tb), lp_, ta)
    def cov_part(p): return np.array([k for k, c in enumerate(cov) if part[c] == p])
    ablend = {}
    for p in ("confirm", "select", "train"):
        s = cov_part(p); ablend[p] = {"n": int(len(s)), "landing": round(float((lp_[s] == y[cov][s]).mean()), 4), "blend": round(float((bl[s] == y[cov][s]).mean()), 4), "teacher_first": round(float((ta[s] == y[cov][s]).mean()), 4), "P1": round(float(opt["P1"]["c1"][cov][s].mean()), 4) if p != "train" else "in-train, not scored"}
    s = cov_part("confirm"); pc = np.array([pub[c] for c in cov[s]]); up = sorted(set(pc)); d0 = ((bl[s] == y[cov][s]).astype(float) - (lp_[s] == y[cov][s]))
    bd = []
    for _ in range(B):
        idx = np.concatenate([np.where(pc == up[j])[0] for j in rng.integers(0, len(up), len(up))]); bd.append(d0[idx].mean())
    ablend["gain_confirm_top1"] = {"gain": round(float(d0.mean()), 4), "ci95": [round(float(np.percentile(bd, 2.5)), 4), round(float(np.percentile(bd, 97.5)), 4)], "p_one_sided": round(float((np.array(bd) <= 0).mean()), 4), "n_publishers": len(up)}; res["secondary_a_teacher_blend"] = ablend
    # ---- Holm across candidates
    cands = [("P1", res["confirm"]["P1"]["macro_recall"]["p_one_sided"], res["confirm"]["P1"]["macro_recall"]["gain"]), ("a", ablend["gain_confirm_top1"]["p_one_sided"], ablend["gain_confirm_top1"]["gain"])]
    if "b" in opt: cands.append(("b", res["confirm"]["b"]["macro_recall"]["p_one_sided"], res["confirm"]["b"]["macro_recall"]["gain"]))
    adj = holm([c[1] for c in cands]); res["holm"] = {c[0]: {"p_raw": c[1], "p_holm": round(a, 4), "gain_pts": round(100 * c[2], 2), "gate_pass": bool(a < 0.05 and c[2] >= 0.02)} for c, a in zip(cands, adj)}
    # ---- live checks on runs-v6
    db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); feed = dict(db.execute("select id, feed from items where id in (%s)" % ",".join("?" * len(Q)), [r["id"] for r in Q]).fetchall()) if len(Q) < 900 else {}
    if not feed:
        for a in range(0, len(Q), 500): feed.update(dict(db.execute("select id, feed from items where id in (%s)" % ",".join("?" * len(Q[a:a + 500])), [r["id"] for r in Q[a:a + 500]]).fetchall()))
    nm2code = {lab[c].lower(): c for c in codes}; assert all(v in nm2code for v in SEC.values()); sec = np.full(len(Q), -1)
    for j, r in enumerate(Q):
        f = (feed.get(r["id"]) or "").lower(); hit = {v for k, v in SEC.items() if k in f}
        if len(hit) == 1 and "world" not in f: sec[j] = ci[nm2code[next(iter(hit))]]
    sj = np.where(sec >= 0)[0]; qp = {"landing": opt["landing"]["Mq"].argmax(1), "P1": (Pq * live).argmax(1), "P1_uncorrected": Pq.argmax(1)}
    if "b" in opt: qp["b"] = opt["b"]["Mq"].argmax(1)
    src = np.array([r["source"] or "" for r in Q]); us = sorted(set(src[sj])); bsrc = {s: sj[src[sj] == s] for s in us}; live_res = {"section_articles": int(len(sj)), "sections": dict(collections.Counter(lab[codes[sec[j]]] for j in sj)), "agreement": {}}
    ix = [np.concatenate([bsrc[us[j]] for j in rng.integers(0, len(us), len(us))]) for _ in range(B)]
    for nm, p in qp.items():
        ok = (p[sj] == sec[sj]); r_ = {"agree": round(float(ok.mean()), 4), "n": int(len(sj))}
        if nm != "landing":
            dl = [((p[i] == sec[i]).mean() - (qp["landing"][i] == sec[i]).mean()) for i in ix]; r_["change_pts_vs_landing"] = round(100 * float(ok.mean() - (qp["landing"][sj] == sec[sj]).mean()), 2); r_["ci95_pts"] = [round(100 * float(np.percentile(dl, 2.5)), 2), round(100 * float(np.percentile(dl, 97.5)), 2)]
        live_res["agreement"][nm] = r_
    t_lab = {}
    for l in open(HERE / "runs/pulse/learn/labels_learn-r2-top2.jsonl"):
        r = json.loads(l); t_lab[r["id"]] = (ci.get(r.get("l1a"), -1), ci.get(r.get("l1b"), -1))
    qpos = {r["id"]: j for j, r in enumerate(Q)}; tj = np.array([qpos[i] for i in t_lab if i in qpos]); live_res["teacher_labelled_queue_articles"] = int(len(tj))
    if len(tj):
        ta_q = np.array([t_lab[Q[j]["id"]][0] for j in tj]); tb_q = np.array([t_lab[Q[j]["id"]][1] for j in tj]); lq = qp["landing"][tj]; blq = np.where((lq == ta_q) | (lq == tb_q), lq, ta_q)
        live_res["teacher_first_agreement_info_only"] = {nm: round(float((p[tj] == ta_q).mean()), 4) for nm, p in qp.items()} | {"blend_rule_agreement_is_by_construction": round(float((blq == ta_q).mean()), 4)}
    live_res["predicted_queue_mix_tv_vs_live_mix"] = {nm: round(0.5 * float(np.abs(np.bincount(p, minlength=K) / len(p) - live).sum()), 4) for nm, p in qp.items()}; live_res["landing_vs_traced_l1_agreement"] = round(float(np.mean([codes[p] == t for p, t in zip(qp["landing"], tl)])), 4); res["live_checks"] = live_res
    # ---- keep rule for P1 (as pre-registered)
    c = res["confirm"]["P1"]; ag = live_res["agreement"]["P1"]["change_pts_vs_landing"]; shg_ = c["share_mae"]["gain"]
    cond = {"1_macro_recall_gain>=2pts_and_holm_p<0.05": res["holm"]["P1"]["gate_pass"], "2_top2_gain>=0": c["top2"]["gain"] >= 0, "3_top1_guard_gain>=0": c["top1"]["gain"] >= 0, "4a_no_loss_share_error(change<=0)": shg_ >= 0, "4b_no_loss_section_agreement(>=-1pt)": ag >= -1.0, "4c_gain_on_a_live_check(share>=0.0005 or section>=+1pt)": bool(shg_ >= 0.0005 or ag >= 1.0)}
    res["keep_rule_P1"] = {"conditions": cond, "decision": "ADOPT" if all(cond.values()) else "DO NOT ADOPT"}
    if "b" in opt:
        cb = res["confirm"]["b"]; agb = live_res["agreement"]["b"]["change_pts_vs_landing"]; res["keep_rule_b_information"] = {"gate_pass_macro_holm": res["holm"]["b"]["gate_pass"], "top1_gain": cb["top1"]["gain"], "section_change_pts": agb, "never_adopted_in_round_1": True}
    # ---- cause-to-action on select
    Mtr = Ml[tr]; ys = y[se]; pl_ = opt["landing"]["pred"]; goldsh = np.bincount(y[tr], minlength=K) / len(tr); prsh = np.bincount(pl_[tr], minlength=K) / len(tr); over = (prsh >= 1.25 * np.maximum(goldsh, 1e-9)) & (goldsh > 0)
    b = np.zeros(K); best = (9, b.copy())
    for it in range(300):
        pr = np.bincount((Mtr + b).argmax(1), minlength=K) / len(tr); tvv = 0.5 * np.abs(pr - goldsh).sum()
        if tvv < best[0]: best = (tvv, b.copy())
        b += 0.01 * np.clip(np.log(np.maximum(goldsh, 1e-4)) - np.log(np.maximum(pr, 1e-4)), -1, 1)
    bb = best[1]; pbias = (Ml + bb).argmax(1); res["prior_only_bias"] = {"train_tv_after": round(float(best[0]), 4), "train_tv_before": round(float(0.5 * np.abs(prsh - goldsh).sum()), 4), "select_top1": round(float((pbias[se] == ys).mean()), 4), "select_macro": round(macro(ys, pbias[se]), 4), "select_landing_top1": round(float((pl_[se] == ys).mean()), 4)}
    Dsel = Sm[se] - 0.5 * share; rank_gold = np.array([1 + (Dsel[j] > Dsel[j][l1c == codes[ys[j]]].max()).sum() for j in range(len(se))]); err = np.where(pl_[se] != ys)[0]; rows = collections.defaultdict(list)
    for j in err:
        r = "prior error" if over[pl_[se][j]] else ("card vocabulary miss" if rank_gold[j] > 10 else "both wrong / convention"); rows[r].append(j)
    qwen_ok = opt["b"]["c1"][se] if "b" in opt else np.zeros(len(se), bool); p1_ok = opt["P1"]["c1"][se]; bias_ok = pbias[se] == ys; fixer = {"prior error": ("per-code bias correction fitted on train", bias_ok), "card vocabulary miss": ("node-card text (fix share measured with the Qwen landing)", qwen_ok), "both wrong / convention": ("re-ranker data (fix share measured with P1)", p1_ok)}
    table = {}
    for r, js in rows.items():
        a, okv = fixer[r]; fs = float(okv[js].mean()) if len(js) else 0.0; table[r] = {"errors": len(js), "share_of_select_errors": round(len(js) / len(err), 3), "action": a, "fix_share": round(fs, 3), "predicted_top1_gain_pts": round(100 * len(js) / len(se) * fs, 2), "over_predicted_codes": [lab[codes[k]] for k in np.where(over)[0]] if r == "prior error" else None}
    ssel = cov_part("select"); table["teacher right where landing wrong (overlay, covered select items only)"] = {"covered_select_items": int(len(ssel)), "landing_wrong": int((lp_[ssel] != y[cov][ssel]).sum()), "teacher_first_right_of_those": int(((lp_[ssel] != y[cov][ssel]) & (ta[ssel] == y[cov][ssel])).sum()), "action": "routing / teacher labels (hosted spend, needs owner yes)", "blend_gain_pts_if_teacher_everywhere": round(100 * (ablend["select"]["blend"] - ablend["select"]["landing"]), 2)}
    res["cause_to_action_select"] = {"n_select": int(len(se)), "landing_errors": int(len(err)), "rows": table}
    cand_next = {r: v["predicted_top1_gain_pts"] for r, v in table.items() if "predicted_top1_gain_pts" in v and r != "both wrong / convention"}; res["next_primary"] = {"gains_pts": cand_next, "choice": max(cand_next, key=cand_next.get) if cand_next else None, "note": "convention row's action is P1 itself, so it is not a next-round option; its unfixed errors are label-convention noise"}
    json.dump(res, open(OUT / ("results_dev.json" if FAST else "results.json"), "w"), indent=1)
    mdl = {"scaler_mean": Xs.mean_.tolist(), "scaler_scale": Xs.scale_.tolist(), "coef": clf.coef_.tolist(), "intercept": clf.intercept_.tolist(), "classes": codes, "C": Cbest, "card_ids": ids, "cards_sha": L.cards_sha, "live_mix": live.tolist(), "split_sha256": spec["content_sha256"], "trained_on": "MN-DS train publishers only (n=%d)" % len(tr), "prior_correction": "multiply p by live_mix for share/live use; none for top-1/recall/top-2"}
    mp = OUT / ("primary_reranker_dev.pkl" if FAST else "primary_reranker.pkl"); pickle.dump(mdl, open(mp, "wb")); res["model_sha256"] = sha_file(mp); json.dump(res, open(OUT / ("results_dev.json" if FAST else "results.json"), "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("primary_C", "confirm_n", "holm", "keep_rule_P1")}, indent=1), "seconds", round(time.time() - t00))
if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True); {"split": step_split, "cache": step_cache, "gpu": step_gpu, "score": step_score}.get(sys.argv[1], lambda: None)()
