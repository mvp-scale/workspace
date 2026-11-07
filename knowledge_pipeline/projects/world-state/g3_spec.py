"""G3 rebuild to playbook 00 (pre-registered L942, extended with the owner's lens-linkage idea). Feature sets on one grouped split (train / calibration half / test half):
  A  learned-vocabulary word 1-2gram TF-IDF (what gates_v2.py used)
  B  playbook spec: hashed word 1-2gram + character 3-5gram (2**20 features), TF-IDF, logistic regression
  C  B + G1 spot-class counts + G2 fragment tokens (predicate, factuality, subject and object heads)  [playbook section 7: sparse features plus fragments]
  D  B + lens-linkage features (title, lead, snapshot, whole: cosine and topical density)            [owner idea]
Heads: story type, 16 condition kinds, topic (A and B only). Calibrated (isotonic) on the calibration half, accept threshold at precision 0.85 there, metrics on the test half.
Also: sparse-first vs encoder-on-every-item (accuracy and single-thread speed), and per-article observation records for the mock-up. fastText is not installed: skipped.
    /workspace/models/embed-zs/.venv/bin/python g3_spec.py   (from projects/world-state)"""
import sys, json, re, time, pickle, os, numpy as np, scipy.sparse as sp, onnxruntime as ort
from tokenizers import Tokenizer
from sklearn.feature_extraction.text import TfidfVectorizer, HashingVectorizer, TfidfTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import GroupShuffleSplit
from joblib import Parallel, delayed
from threadpoolctl import threadpool_limits
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
while not os.path.exists("runs/pulse/lens_features.npz"): time.sleep(10)
time.sleep(3); DATA = "/workspace/demo/mockups/gates/data.json"; D = json.load(open(DATA)); KINDS = [l["kind"] for l in D["ladder"]]; PREC = 0.85
S = {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] == "sonnet" and r["version"] == "ws-v2-frozen": S[r["item_id"]] = r
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
ids = sorted(i for i in S if i in pool); T = [re.sub(r"\s+", " ", pool[i])[:600] for i in ids]; N = len(ids)
E1 = np.load("runs/pulse/kind_cascade_emb.npz")["E1"]; LZ = np.load("runs/pulse/lens_features.npz"); assert list(LZ["ids"]) == ids; LF = LZ["F"]; GZ = pickle.load(open("runs/pulse/g2_tokens.pkl", "rb")); assert GZ["ids"] == ids
Y = np.array([[int(k in S[i]["kinds"]) for k in KINDS] for i in ids]); ST = [S[i]["story_type"] for i in ids]; TP = [S[i]["topic"] for i in ids]
grp = {}; gid = np.array([grp.setdefault(re.sub(r"\W+", "", t.lower())[:60], len(grp)) for t in T])
tr, va = next(GroupShuffleSplit(1, test_size=0.2, random_state=0).split(T, groups=gid)); rs = np.random.RandomState(1); va = rs.permutation(va); cal, te = va[: len(va) // 2], va[len(va) // 2:]
# ---------------------------------------------------------------- features
t0 = time.time(); vecA = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True).fit([T[i] for i in tr]); XA = vecA.transform(T).tocsr()
hw = HashingVectorizer(analyzer="word", ngram_range=(1, 2), n_features=2 ** 19, alternate_sign=False, norm=None); hc = HashingVectorizer(analyzer="char_wb", ngram_range=(3, 5), n_features=2 ** 19, alternate_sign=False, norm=None)
H = sp.hstack([hw.transform(T), hc.transform(T)]).tocsr(); tfB = TfidfTransformer(sublinear_tf=True).fit(H[tr]); XB = tfB.transform(H).tocsr()
hg = HashingVectorizer(analyzer=lambda s: s.split(), n_features=2 ** 16, alternate_sign=False, binary=True, norm="l2"); G2B = hg.transform(GZ["tokens"]); G1B = sp.csr_matrix(np.log1p(GZ["counts"]) / 3.0)
XC = sp.hstack([XB, G2B, G1B]).tocsr(); mu, sd = LF[tr].mean(0), LF[tr].std(0) + 1e-6; LS = sp.csr_matrix((LF - mu) / sd * 0.3); XD = sp.hstack([XB, LS]).tocsr()
SETS = {"A": XA, "B": XB, "C": XC, "D": XD}; print("features", {k: v.shape for k, v in SETS.items()}, round(time.time() - t0), "s", flush=True)
# ---------------------------------------------------------------- calibration helpers
def thr_yes(p, y):
    best = None
    for t in np.unique(np.round(p, 4))[::-1]:
        m = p >= t
        if m.sum() >= 5 and y[m].mean() >= PREC: best = float(t)
        elif best is not None and m.sum() >= 5 and y[m].mean() < PREC - 0.05: break
    return best
def thr_no(p, y): return float(np.percentile(p[y == 1], 5)) if (y == 1).sum() >= 15 else None
def f1_at(p, y, t): pr = p >= t; return 2 * int((pr & (y == 1)).sum()) / max(int(pr.sum()) + int(y.sum()), 1)
def binary_metrics(pc, pt, yc, yt):
    iso = IsotonicRegression(out_of_bounds="clip").fit(pc, yc); cc, ct = iso.predict(pc), iso.predict(pt); ty, tn = thr_yes(cc, yc), thr_no(cc, yc)
    ym = (ct >= ty) if ty is not None else np.zeros(len(yt), bool); cands = np.unique(np.quantile(cc, np.linspace(0.5, 0.999, 60))); tf1 = max(cands, key=lambda t: f1_at(cc, yc, t)) if len(cands) else 0.5
    return iso, ty, tn, tf1, {"yes_precision": round(float(yt[ym].mean()), 3) if ym.sum() else None, "yes_recall": round(float(yt[ym].sum() / max(yt.sum(), 1)), 3), "f1": round(f1_at(ct, yt, tf1), 3), "positives_test": int(yt.sum())}
def fit_bin(X, j):
    m = LogisticRegression(solver="liblinear", C=10.0, class_weight="balanced").fit(X[tr], Y[tr, j]); return m, m.predict_proba(X[cal])[:, 1], m.predict_proba(X[te])[:, 1]
def multi(X, labels, name):
    cls = sorted(set(labels)); yi = np.array([cls.index(l) for l in labels])
    def one(c): m = LogisticRegression(solver="liblinear", C=10.0).fit(X[tr], (yi[tr] == c).astype(int)); return m, m.predict_proba(X[cal])[:, 1], m.predict_proba(X[te])[:, 1]
    outs = Parallel(n_jobs=16)(delayed(one)(c) for c in range(len(cls))); Pc = np.array([o[1] for o in outs]).T; Pt = np.array([o[2] for o in outs]).T; Pc /= Pc.sum(1, keepdims=True); Pt /= Pt.sum(1, keepdims=True)
    okc = (Pc.argmax(1) == yi[cal]).astype(int); iso = IsotonicRegression(out_of_bounds="clip").fit(Pc.max(1), okc); ty = thr_yes(iso.predict(Pc.max(1)), okc); ct = iso.predict(Pt.max(1)); ans = (ct >= ty) if ty is not None else np.zeros(len(te), bool); okt = (Pt.argmax(1) == yi[te])
    return [o[0] for o in outs], iso, ty, cls, {"coverage": round(float(ans.mean()), 3), "precision_when_answered": round(float(okt[ans].mean()), 3) if ans.sum() else None, "classes": len(cls), "always_majority_precision": round(float(np.bincount(yi[te]).max() / len(te)), 3)}
RES = {"split": {"train": int(len(tr)), "calibration": int(len(cal)), "test": int(len(te))}, "precision_target": PREC, "fasttext": "not installed in the venv: skipped", "sets": {}}; MODELS = {}
for name, X in SETS.items():
    t1 = time.time(); outs = Parallel(n_jobs=16)(delayed(fit_bin)(X, j) for j in range(len(KINDS))); stm = multi(X, ST, "story_type"); kinds = {}; mods = []
    for j, k in enumerate(KINDS):
        m, pc, pt = outs[j]; iso, ty, tn, tf1, met = binary_metrics(pc, pt, Y[cal, j], Y[te, j]); kinds[k] = met; mods.append((m, iso, ty, tn, tf1))
    macro = float(np.mean([v["f1"] for v in kinds.values()])); withyes = sum(1 for v in kinds.values() if v["yes_precision"] is not None); yrec = float(np.mean([v["yes_recall"] for v in kinds.values()]))
    RES["sets"][name] = {"features": int(X.shape[1]), "story_type": stm[4], "kinds": kinds, "kinds_macro_f1": round(macro, 3), "kinds_that_can_say_yes": withyes, "kinds_mean_yes_recall": round(yrec, 3), "model_mb": round((X.shape[1] * (len(KINDS) + len(stm[3]))) * 4 / 1e6, 1), "fit_s": round(time.time() - t1)}
    MODELS[name] = {"kinds": mods, "st": stm}
    if name in ("A", "B"):
        tm = multi(X, TP, "topic"); RES["sets"][name]["topic"] = tm[4]; MODELS[name]["tp"] = tm
    print(name, {k: v for k, v in RES["sets"][name].items() if k not in ("kinds",)}, round(time.time() - t1), "s", flush=True)
json.dump(RES, open("runs/pulse/g3_spec.json", "w"), indent=1)
# ---------------------------------------------------------------- sparse-first vs encoder-on-every-item
tk = Tokenizer.from_file("runs/embeds/leaf_tokenizer.json"); tk.enable_truncation(max_length=64); tk.no_padding(); so = ort.SessionOptions(); so.intra_op_num_threads = 1; so.inter_op_num_threads = 1
sess = ort.InferenceSession("runs/embeds/student_v6b-student.onnx", so, providers=["CPUExecutionProvider"])
def emb(t): e = tk.encode(re.sub(r"\s+", " ", t)[:1200]); i = np.array([e.ids], dtype=np.int64); return sess.run(None, {"input_ids": i, "attention_mask": np.ones_like(i)})[0][0]
ENC = [fit_bin(E1, j) for j in range(len(KINDS))]; ENCM = []
for j in range(len(KINDS)): m, pc, pt = ENC[j]; ENCM.append((m,) + binary_metrics(pc, pt, Y[cal, j], Y[te, j])[:4])
sp_mods = MODELS["B"]["kinds"]; z0 = np.zeros(len(te), bool); f1_enc, f1_cas, unresolved_any = [], [], np.zeros(len(te), bool)
for j in range(len(KINDS)):
    m, iso, ty, tn, tf1 = sp_mods[j]; ps = iso.predict(m.predict_proba(XB[te])[:, 1]); me, isoe, tye, tne, tf1e = ENCM[j]; pe = isoe.predict(me.predict_proba(E1[te])[:, 1]); y = Y[te, j]
    syes = (ps >= ty) if ty is not None else z0; sno = (ps < tn) if tn is not None else z0; unk = ~(syes | sno); unresolved_any |= unk
    cas = syes | (unk & (pe >= tf1e)); enc = pe >= tf1e; f = lambda pr: 2 * int((pr & (y == 1)).sum()) / max(int(pr.sum()) + int(y.sum()), 1)
    f1_enc.append(f(enc)); f1_cas.append(f(cas))
sample = [T[i] for i in te[:300]]
with threadpool_limits(1):
    t1 = time.perf_counter()
    for t in sample:
        e = emb(t)[None]
        for j in range(len(KINDS)): ENCM[j][0].predict_proba(e)
    enc_s = time.perf_counter() - t1; t1 = time.perf_counter(); n_enc_calls = 0
    for t in sample:
        xb = tfB.transform(sp.hstack([hw.transform([t]), hc.transform([t])]).tocsr()); unk = False
        for j in range(len(KINDS)):
            m, iso, ty, tn, tf1 = sp_mods[j]; p = float(iso.predict(m.predict_proba(xb)[:, 1])[0])
            if not ((ty is not None and p >= ty) or (tn is not None and p < tn)): unk = True
        if unk:
            n_enc_calls += 1; e = emb(t)[None]
            for j in range(len(KINDS)): ENCM[j][0].predict_proba(e)
    cas_s = time.perf_counter() - t1
RES["cascade_vs_encoder_everywhere"] = {"kinds_macro_f1_encoder_everywhere": round(float(np.mean(f1_enc)), 3), "kinds_macro_f1_sparse_first": round(float(np.mean(f1_cas)), 3), "items_per_s_encoder_everywhere": round(len(sample) / enc_s, 1), "items_per_s_sparse_first": round(len(sample) / cas_s, 1), "share_of_items_with_no_unresolved_head": round(float(1 - unresolved_any.mean()), 3), "single_thread": True, "sample_items": len(sample)}
json.dump(RES, open("runs/pulse/g3_spec.json", "w"), indent=1); print("cascade", RES["cascade_vs_encoder_everywhere"], flush=True)
# ---------------------------------------------------------------- per-article observation records
def predict_all(view):
    xb = tfB.transform(sp.hstack([hw.transform([view]), hc.transform([view])]).tocsr()); e = emb(view)[None]; out = {}
    ms, iso, ty, cls, _ = MODELS["B"]["st"]; P = np.array([m.predict_proba(xb)[0, 1] for m in ms]); Pn = P / P.sum(); j = int(Pn.argmax()); out["story_type"] = (cls[j], float(iso.predict([Pn[j]])[0]), ty, float(P[j]))
    ms, iso, ty, cls, _ = MODELS["B"]["tp"]; P = np.array([m.predict_proba(xb)[0, 1] for m in ms]); Pn = P / P.sum(); j = int(Pn.argmax()); out["topic"] = (cls[j], float(iso.predict([Pn[j]])[0]), ty, float(P[j]))
    kd = []
    for j, k in enumerate(KINDS):
        m, iso, ty, tn, tf1 = sp_mods[j]; praw = float(m.predict_proba(xb)[0, 1]); p = float(iso.predict([praw])[0]); st = "yes" if ty is not None and p >= ty else ("no" if tn is not None and p < tn else "unknown")
        row = {"kind": k, "p": round(p, 3), "raw": praw, "status": st, "stage": "G3a"}
        if st == "unknown":
            me, isoe, tye, tne, tf1e = ENCM[j]; pe = float(isoe.predict(me.predict_proba(e)[:, 1])[0]); row.update({"encoder_p": round(pe, 3), "encoder_status": "yes" if pe >= tf1e else "no", "stage": "G3b"})
        kd.append(row)
    return out, kd
def find_all(body, w): return [[m.start(), m.end()] for m in re.finditer(r"\b" + re.escape(w) + r"\b", body, re.I)]
def occlusion(view, score_fn, body, top=4):
    base = score_fn(view); words = sorted(set(w.lower() for w in re.findall(r"[A-Za-z]{4,}", view))); res = []
    for w in words:
        d = base - score_fn(re.sub(r"\b" + re.escape(w) + r"\b", "", view, flags=re.I))
        if d > 0: res.append((d, w))
    res.sort(reverse=True); return [{"word": w, "delta": round(d, 3), "spans": find_all(body, w)} for d, w in res[:top] if find_all(body, w)]
def head_score(kind_or_head, view):
    xb = tfB.transform(sp.hstack([hw.transform([view]), hc.transform([view])]).tocsr())
    if kind_or_head in KINDS: return float(sp_mods[KINDS.index(kind_or_head)][0].predict_proba(xb)[0, 1])
    which, cls_name = kind_or_head.split("=", 1); ms, iso, ty, cls, _ = MODELS["B"]["st" if which == "story_type" else "tp"]; return float(ms[cls.index(cls_name)].predict_proba(xb)[0, 1])
tkn = Tokenizer.from_file("runs/embeds/leaf_tokenizer.json")
for a in D["articles"]:
    c = a["contract"]; body = c["body"]; view = re.sub(r"\s+", " ", c["title"] + ". " + body)[:600]; pa, kd = predict_all(view); evidence = []
    for head, (ans, conf, thr, raw) in pa.items():
        status = "answered" if thr is not None and conf >= thr else "unknown"; pa[head] = {"answer": ans, "confidence": round(conf, 3), "status": status}
        if status == "answered" and not (head == "story_type" and ans == "fact"): evidence.append({"head": f"{head}={ans}", "words": occlusion(view, lambda v, h=f"{head}={ans}": head_score(h, v), body)})
    for r in kd:
        if r["status"] == "yes" or r.get("encoder_status") == "yes":
            if r["status"] == "yes": evidence.append({"head": r["kind"], "words": occlusion(view, lambda v, h=r["kind"]: head_score(h, v), body)})
    # lens linkage on the full body
    sents = [(s["start"], s["end"]) for s in a["sentences"]]; en = lambda t: (lambda v: v / (np.linalg.norm(v) + 1e-9))(emb(t)); et = en(c["title"]); ed = en(c["description"]); esn = en(c["snapshot"]); es = [en(body[s:e]) for s, e in sents]; ew = np.mean(es, 0); ew /= np.linalg.norm(ew) + 1e-9
    L = ["title", "description", "snapshot", "whole body"]; Em = [et, ed, esn, ew]; mat = [[round(float(x @ y), 3) for y in Em] for x in Em]; sims = [round(float(et @ v), 3) for v in es]
    a["lens"] = {"names": L, "matrix": mat, "sentence_sims": sims, "density_close_to_title": round(float(np.mean([s >= 0.6 for s in sims])), 3), "threshold": 0.6}
    a["observation"] = {"tenant_id": "default", "document_id": c["id"], "fragments": a["solver"]["fragments"], "domains": pa["topic"], "content_function": pa["story_type"], "conditions": [{k: v for k, v in r.items() if k != "raw"} for r in kd],
                        "areas": {"items": [], "reason": "needs a seeded ontology"}, "capabilities": {"items": [], "reason": "needs a seeded ontology"}, "novelty": {"status": "not built"}, "evidence": evidence, "model_version": "g3_spec v1", "ontology_version": "none"}
    print(a["id"], pa, [r["kind"] for r in kd if r["status"] == "yes"], [(e["head"], [w["word"] for w in e["words"]]) for e in evidence], "density", a["lens"]["density_close_to_title"], flush=True)
D["g3_spec"] = RES; json.dump(D, open(DATA, "w")); print("saved data.json", flush=True)
