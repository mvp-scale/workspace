"""Wide net (pre-registered after L944, ledger note 'PRE-REGISTERED before the build (wide_net.py)'): OPEN extraction with no predefined list, then zero-shot grouping onto the engine's own vocabulary.
Open layer per story: TF-IDF keyphrases (corpus IDF), G1 names and event verbs, G2 'predicate + object' phrases. Grouping layer: v6b-student embedding of each open phrase (wrapped as 'This story is about ...') against the 159 engine attribute wordings (definition + 2 statements each, 39 dials) and 49 domain definitions; per-dial z-scores from a background of the calibration half; a story maps to a dial when its best open phrase scores z >= tau.
Evaluated on 1736 Clef-read stories (no training pool) against Clef's dials, and on the Sonnet-labelled test half for the 16 kinds.
    /workspace/models/embed-zs/.venv/bin/python wide_net.py   (from projects/world-state)"""
import sys, json, re, time, collections, numpy as np, onnxruntime as ort, spacy
sys.path.insert(0, "."); import scan_gate as G, normalize as NZ
from tokenizers import Tokenizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import GroupShuffleSplit
from sklearn.cluster import HDBSCAN, KMeans
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
DATA = "/workspace/demo/mockups/gates/data.json"; D = json.load(open(DATA)); KINDS = [l["kind"] for l in D["ladder"]]; V = json.load(open("runs/pulse/wide_vocab.json"))
S = {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] == "sonnet" and r["version"] == "ws-v2-frozen": S[r["item_id"]] = r
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
ids = sorted(i for i in S if i in pool); T = [re.sub(r"\s+", " ", pool[i])[:600] for i in ids]
Y = np.array([[int(k in S[i]["kinds"]) for k in KINDS] for i in ids])
grp = {}; gid = np.array([grp.setdefault(re.sub(r"\W+", "", t.lower())[:60], len(grp)) for t in T])
tr, va = next(GroupShuffleSplit(1, test_size=0.2, random_state=0).split(T, groups=gid)); rs = np.random.RandomState(1); va = rs.permutation(va); cal, te = va[: len(va) // 2], va[len(va) // 2:]
DIALS = sorted({k.split("|")[0] for k in V["attrs"]}); DI = {d: i for i, d in enumerate(DIALS)}; KI = [DI[k] for k in KINDS]
tk = Tokenizer.from_file("runs/embeds/leaf_tokenizer.json"); tk.enable_truncation(max_length=64); tk.no_padding(); so = ort.SessionOptions(); so.intra_op_num_threads = 8
sess = ort.InferenceSession("runs/embeds/student_v6b-student.onnx", so, providers=["CPUExecutionProvider"]); CACHE = {}
def emb(t):
    if t in CACHE: return CACHE[t]
    e = tk.encode(re.sub(r"\s+", " ", t)[:1200]); i = np.array([e.ids], dtype=np.int64); v = sess.run(None, {"input_ids": i, "attention_mask": np.ones_like(i)})[0][0]; CACHE[t] = v / (np.linalg.norm(v) + 1e-9); return CACHE[t]
# ---- vocabulary matrices
vt, vd = [], []
for key, lst in V["attrs"].items():
    d = key.split("|")[0]
    for a in lst:
        for t in (a["attribute"] + ": " + a["definition"], a["q1"], a["q2"]): vt.append(t); vd.append(DI[d])
VM = np.array([emb(t) for t in vt]); vd = np.array(vd); DOM = V["domains"]; DM = np.array([emb(d["name"] + ": " + d["definition"]) for d in DOM]); print("vocab", VM.shape, DM.shape, flush=True)
def sims(vecs):
    """per-dial max cosine and per-domain cosine for an array of phrase vectors"""
    C = vecs @ VM.T; out = np.full((len(vecs), len(DIALS)), -1.0)
    for d in range(len(DIALS)): out[:, d] = C[:, vd == d].max(1)
    return out, vecs @ DM.T
# ---- open layer
tfv = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", min_df=3, sublinear_tf=True).fit(T); FN = np.array(tfv.get_feature_names_out())
nlp = spacy.load("en_core_web_sm", disable=["ner"]); SPEECH = {"say", "tell", "report", "claim", "announce", "warn", "state", "add", "note", "according"}
def keyphrases(view, k=8):
    x = tfv.transform([view]); idx = x.indices[np.argsort(-x.data)]; out = []
    for j in idx:
        w = FN[j]
        if any(w in o.split() or (" " in o and w in o) for o in out if o != w): continue
        out = [o for o in out if not (" " not in o and o in w.split())] + [w]
        if len(out) >= k: break
    return out
def frag_phrases(doc, k=5):
    out = []
    for t in doc:
        if t.pos_ != "VERB" or t.lemma_ in SPEECH or t.lemma_ in ("be", "have", "do"): continue
        obj = next((c for c in t.children if c.dep_ in ("dobj", "attr", "oprd")), None)
        if obj is None:
            pp = next((c for c in t.children if c.dep_ == "prep"), None); obj = next((c for c in pp.children if c.dep_ == "pobj"), None) if pp else None
        if obj is not None: out.append(f"{t.lemma_} {obj.text.lower()}")
    return list(dict.fromkeys(out))[:k]
def open_items(view, doc, kp=8):
    sp, _ = G.scan(view, "2026-01-01T00:00:00Z"); ents = list(dict.fromkeys(view[a:b] for a, b, c, *_ in sp if c == "entity"))[:6]; evs = list(dict.fromkeys(view[a:b].lower() for a, b, c, *_ in sp if c == "event"))[:4]
    return [("keyphrase", p) for p in keyphrases(view, kp)] + [("fragment", p) for p in frag_phrases(doc)], ents, evs
wrap = lambda p: f"This story is about {p}."
def story_items(views):
    docs = list(nlp.pipe(views, batch_size=64)); return [open_items(v, d) for v, d in zip(views, docs)]
t0 = time.time(); KV = [T[i] for i in np.concatenate([cal, te])]; clef = J("/workspace/data/newsreader/labels/clef-q4km.jsonl"); CV = []
for r in clef:
    c = NZ.feed_article(r); CV.append(re.sub(r"\s+", " ", c["title"] + ". " + c["body"])[:600])
ITEMS_K = story_items(KV); ITEMS_C = story_items(CV); print("open items", sum(len(x[0]) for x in ITEMS_K), sum(len(x[0]) for x in ITEMS_C), round(time.time() - t0), "s", flush=True)
def embed_items(ITEMS): return [np.array([emb(wrap(p)) for _, p in it[0]]) if it[0] else np.zeros((0, VM.shape[1])) for it in ITEMS]
EK = embed_items(ITEMS_K); EC = embed_items(ITEMS_C); print("embedded", len(CACHE), round(time.time() - t0), "s", flush=True)
# ---- per-dial z-scores from the calibration half's items (background)
nc = len(cal); allk = np.concatenate([e for e in EK[:nc] if len(e)]); Sd, Sdom = sims(allk); mu, sd = Sd.mean(0), Sd.std(0) + 1e-6; dmu, dsd = Sdom.mean(0), Sdom.std(0) + 1e-6
def story_scores(E):
    """per story: max z over its items for each dial, and for each domain"""
    sdz = np.full((len(E), len(DIALS)), -9.0); sdo = np.full((len(E), len(DOM)), -9.0)
    for n, e in enumerate(E):
        if not len(e): continue
        a, b = sims(e); sdz[n] = ((a - mu) / sd).max(0); sdo[n] = ((b - dmu) / dsd).max(0)
    return sdz, sdo
ZK, ZKd = story_scores(EK); ZC, ZCd = story_scores(EC); TAU_BROAD = 3.5
dom_ids = [d['id'] for d in DOM]; nc0 = len(cal); tp_idx = np.array([dom_ids.index(S[ids[i]]['topic']) for i in np.concatenate([cal, te])]); zt = ZKd[nc0:]; tpt = tp_idx[nc0:]
DOMRES = {'test_stories': int(len(tpt)), 'top1': round(float((zt.argmax(1) == tpt).mean()), 3), 'top3': round(float(np.mean([tpt[n] in np.argsort(-zt[n])[:3] for n in range(len(tpt))])), 3), 'always_majority': round(float(np.bincount(tpt).max() / len(tpt)), 3), 'topics': len(dom_ids)}; print('domain grouping', DOMRES, flush=True)
# ---- tau on the calibration half (macro F1 over the 16 kinds), reported on the test half
yk = Y[np.concatenate([cal, te])]; ycal, yte = yk[:nc], yk[nc:]; zk = ZK[:, KI]
def f1(p, y): return 2 * int((p & (y == 1)).sum()) / max(int(p.sum()) + int(y.sum()), 1)
grid = np.round(np.arange(1.0, 6.01, 0.25), 2); macro = {t: np.mean([f1(zk[:nc, j] >= t, ycal[:, j]) for j in range(len(KINDS))]) for t in grid}; TAU = max(macro, key=macro.get)
kind_res = {k: {"precision": None, "recall": None, "f1": None, "positives_test": int(yte[:, j].sum())} for j, k in enumerate(KINDS)}
for j, k in enumerate(KINDS):
    p = zk[nc:, j] >= TAU; tp = int((p & (yte[:, j] == 1)).sum()); kind_res[k].update({"precision": round(tp / max(int(p.sum()), 1), 3), "recall": round(tp / max(int(yte[:, j].sum()), 1), 3), "f1": round(f1(p, yte[:, j]), 3)})
macro_te = float(np.mean([v["f1"] for v in kind_res.values()])); print("tau", TAU, "kinds macro F1 cal", round(macro[TAU], 3), "test", round(macro_te, 3), flush=True)
# ---- Clef dials (any direction)
Ct = np.zeros((len(clef), len(DIALS)), bool)
for n, r in enumerate(clef):
    for x in r["readings"]:
        if x["direction"] != "conflict" and x["dial"] in DI: Ct[n, DI[x["dial"]]] = True
def sweep(Z, Yb, taus):
    out = []
    for t in taus:
        p = Z >= t; tp = int((p & Yb).sum()); fp = int((p & ~Yb).sum()); out.append({"tau": float(t), "tpr": round(tp / Yb.sum(), 3), "fpr": round(fp / (~Yb).sum(), 5), "dials_reached": int(((p & Yb).sum(0) > 0).sum()), "mapped_per_story": round(float(p.sum(1).mean()), 2)})
    return out
TS = np.round(np.arange(1.0, 8.01, 0.25), 2); sw = sweep(ZC, Ct, TS); at_kinds = next(x for x in sw if x["tau"] == TAU); under = [x for x in sw if x["fpr"] <= 0.002]; at_fpr = max(under, key=lambda x: x["tpr"]) if under else None
zs = np.load("runs/pulse/dial_heads_cv_scores.npz"); keys = [k.split("|") for k in zs["keys"]]; Sup = np.zeros((len(clef), len(DIALS))); 
for j, (d, _) in enumerate(keys):
    if d in DI: Sup[:, DI[d]] = np.maximum(Sup[:, DI[d]], zs["S"][:, j])
assert list(zs["ids"]) == [r["id"] for r in clef]
supsw = sweep(Sup, Ct, np.unique(np.quantile(Sup, np.linspace(0.8, 0.99995, 400)))); supu = [x for x in supsw if x["fpr"] <= 0.002]; sup_at = max(supu, key=lambda x: x["tpr"]) if supu else None; supk = [x for x in supsw if x["fpr"] <= at_kinds["fpr"]]; sup_k = max(supk, key=lambda x: x["tpr"]) if supk else None; at_broad = next(x for x in sw if x["tau"] == TAU_BROAD)
# open item mapping and unmapped share on Clef stories
unm = collections.Counter(); tot = 0; unm_n = 0; mapped_dial_hits = collections.Counter()
for n, e in enumerate(EC):
    if not len(e): continue
    a, b = sims(e); za = ((a - mu) / sd).max(1); zb = ((b - dmu) / dsd).max(1)
    for (typ, p), x, y_ in zip(ITEMS_C[n][0], za, zb):
        tot += 1
        if max(x, y_) < TAU: unm_n += 1; unm[p] += 1
SUITE = {"vocabulary": {"dial_wordings": int(len(vt)), "dials": len(DIALS), "domains": len(DOM)}, "tau_z": TAU, "tau_chosen_on": "macro F1 of the 16 kinds on the Sonnet calibration half", "kinds_macro_f1_cal": round(macro[TAU], 3), "kinds_macro_f1_test": round(macro_te, 3), "kinds": kind_res,
         "clef": {"stories": len(clef), "dials_in_clef": int(Ct.any(0).sum()), "clef_dial_readings": int(Ct.sum()), "wide_at_kinds_tau": at_kinds, "wide_at_fpr_0_002": at_fpr, "wide_at_broad_tau": at_broad, "supervised_dial_level_at_fpr_0_002": sup_at, "supervised_dial_level_at_wide_kinds_fpr": sup_k, "sweep": sw},
         "tau_broad_z": TAU_BROAD, "domain_grouping": DOMRES, "open_items": {"clef_items": tot, "unmapped": unm_n, "unmapped_share": round(unm_n / max(tot, 1), 3), "most_common_unmapped": unm.most_common(25)}}
print(json.dumps({k: v for k, v in SUITE.items() if k not in ("kinds",)}, indent=1)[:2600], flush=True)
D["wide_net_suite"] = SUITE; json.dump(D, open(DATA, "w")); json.dump(SUITE, open("runs/pulse/wide_net.json", "w"), indent=1)
# ---- the three mock-up articles (full body, sentence groups)
bg = [re.split(r"(?<=[.!?])\s+", T[i])[1] if len(re.split(r"(?<=[.!?])\s+", T[i])) > 1 else T[i] for i in cal[:1500]]; Eb = np.array([emb(s) for s in bg]); sb, sdb = sims(Eb); smu, ssd = sb.mean(0), sb.std(0) + 1e-6; dsmu, dssd = sdb.mean(0), sdb.std(0) + 1e-6
for a in D["articles"]:
    c = a["contract"]; body = c["body"]; sents = [(s["start"], s["end"]) for s in a["sentences"]]; items, ents, evs = open_items(re.sub(r"\s+", " ", body), nlp(body), kp=12); E_i = np.array([emb(wrap(p)) for _, p in items]); ai, bi = sims(E_i); zi = (ai - mu) / sd; zdi = (bi - dmu) / dsd
    out_items = []
    for n, (typ, p) in enumerate(items):
        top = [(float(zi[n, d]), "dial", DIALS[d]) for d in np.argsort(-zi[n])[:2]] + [(float(zdi[n, d]), "domain", DOM[d]["name"]) for d in np.argsort(-zdi[n])[:1]]; top.sort(reverse=True)
        out_items.append({"phrase": p, "type": typ, "best": [{"kind": k, "name": nm, "z": round(z, 2)} for z, k, nm in top[:2]], "mapped": bool(top[0][0] >= TAU_BROAD), "strict": bool(top[0][0] >= TAU)})
    Es = np.array([emb(body[s:e]) for s, e in sents]); cl = HDBSCAN(min_cluster_size=2, min_samples=1).fit_predict(Es); meth = "HDBSCAN"
    if len(set(cl) - {-1}) < 2: cl = KMeans(3, n_init=10, random_state=0).fit_predict(Es); meth = "k-means"
    themes = []
    for g in sorted(set(cl) - {-1}):
        m = [i for i in range(len(sents)) if cl[i] == g]; cen = Es[m].mean(0); cen /= np.linalg.norm(cen) + 1e-9; rep = m[int(np.argmin(np.linalg.norm(Es[m] - cen, axis=1)))]; ca, cb = sims(cen[None]); zc = ((ca - smu) / ssd)[0]; zd = ((cb - dsmu) / dssd)[0]
        top = sorted([(float(zc[d]), "dial", DIALS[d]) for d in np.argsort(-zc)[:2]] + [(float(zd[d]), "domain", DOM[d]["name"]) for d in np.argsort(-zd)[:1]], reverse=True)[:3]
        txt = " ".join(body[sents[i][0]:sents[i][1]].lower() for i in m); its = [o["phrase"] for o in out_items if o["type"] == "keyphrase" and all(w in txt for w in o["phrase"].split())][:6]
        themes.append({"id": int(g), "sentences": len(m), "representative": rep, "items": its, "maps": [{"kind": k, "name": nm, "z": round(z, 2)} for z, k, nm in top]})
    mapped = {}
    for o in out_items:
        for b_ in o["best"]:
            if b_["kind"] == "dial" and b_["z"] >= TAU_BROAD: mapped[b_["name"]] = max(mapped.get(b_["name"], -9), b_["z"])
    for th in themes:
        for b_ in th["maps"]:
            if b_["kind"] == "dial" and b_["z"] >= TAU_BROAD: mapped[b_["name"]] = max(mapped.get(b_["name"], -9), b_["z"])
    cd = {x.split()[0] for x in a["clef_dials"]}; a["wide_net"] = {"method": meth, "tau_z": TAU, "themes": themes, "items": out_items, "entities": ents, "events": evs, "tau_broad_z": TAU_BROAD, "mapped_dials": [{"dial": d, "z": round(z, 2), "level": "strict" if z >= TAU else "possible"} for d, z in sorted(mapped.items(), key=lambda kv: -kv[1])], "domains": sorted({(b_["name"], b_["z"]) for o in out_items for b_ in o["best"] if b_["kind"] == "domain" and b_["z"] >= TAU_BROAD} | {(b_["name"], b_["z"]) for th in themes for b_ in th["maps"] if b_["kind"] == "domain" and b_["z"] >= TAU_BROAD}, key=lambda x: -x[1])[:5], "clef_dials": sorted(cd), "recovered": sorted(cd & set(mapped)), "missed": sorted(cd - set(mapped)), "beyond_clef": sorted(set(mapped) - cd)}
    for r in a["agreement_rows"]: r["wide_z"] = round(mapped[r["kind"]], 2) if r["kind"] in mapped else None; r["wide_level"] = ("strict" if mapped[r["kind"]] >= TAU else "possible") if r["kind"] in mapped else None
    have = {r["kind"] for r in a["agreement_rows"]}
    for d, z in mapped.items():
        if d not in have: a["agreement_rows"].append({"kind": d, "cue_rule": None, "sparse_p": None, "sparse_yes": None, "encoder_p": None, "encoder_yes": None, "clef": next((x.split()[1] for x in a["clef_dials"] if x.split()[0] == d), None), "cheap_votes": 0, "wide_z": round(z, 2), "wide_level": "strict" if z >= TAU else "possible", "outside_funnel": d not in KINDS})
    for d in cd:
        if d not in {r["kind"] for r in a["agreement_rows"]}: a["agreement_rows"].append({"kind": d, "cue_rule": None, "sparse_p": None, "sparse_yes": None, "encoder_p": None, "encoder_yes": None, "clef": next((x.split()[1] for x in a["clef_dials"] if x.split()[0] == d), None), "cheap_votes": 0, "wide_z": None, "wide_level": None, "outside_funnel": d not in KINDS})
    print(a["id"], "mapped", list(mapped)[:8], "clef", sorted(cd), "recovered", a["wide_net"]["recovered"], "missed", a["wide_net"]["missed"], flush=True)
json.dump(D, open(DATA, "w")); print("saved", flush=True)
