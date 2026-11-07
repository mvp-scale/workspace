"""Production-shaped G1 to G3a for the gates mock-up (pre-registered L940). Reads demo/mockups/gates/data.json (articles with their NormalizedItem contract), replaces the per-article gate outputs, writes it back.
G1 scan: ONE regex alternation pass over the body (leftmost-first, so spans cannot overlap) -> spot map [start, end, class]; sentence offsets; checks (sorted, in range, text identity); measured MB/s.
G2 solver: spaCy dependency parse -> fragments {subject, predicate, object spans, factuality, polarity, evidence sentence}; checks (every span inside its evidence sentence).
G3a sparse: word 1-2gram TF-IDF + logistic heads for story type (4), topic (49) and the 16 condition kinds; calibrated (isotonic) on a grouped split, accept threshold at precision 0.85 on a calibration half, scored on a separate test half; unresolved heads escalate to the encoder heads (G3b) with the same recipe.
    /workspace/models/embed-zs/.venv/bin/python gates_v2.py   (from projects/world-state)"""
import json, re, time, collections, numpy as np, onnxruntime as ort, spacy
from tokenizers import Tokenizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import GroupShuffleSplit
import size_quantity as SQ
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
DATA = "/workspace/demo/mockups/gates/data.json"; D = json.load(open(DATA)); KINDS = [l["kind"] for l in D["ladder"]]
# ------------------------------------------------------------------ G1 scanner
NUM = r"\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?"; MAG = r"(?:\s?(?:thousand|million|billion|trillion|bn)\b)?"
UNITS = "|".join(u for c, u in SQ.UNITS if c != "percent")
MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
EVENT = r"(?:kill|arrest|detain|announc|sign|ban|clos|open|rais|surg|plung|jump|drop|declin|increas|strik|struck|block|suspend|cancel|resign|elect|vot|approv|reject|launch|attack|protest|march|rall|clash|fir|stol|hack|breach|flood|burn|destroy|damag|collaps|evacuat|displac|infect|confirm|declar|warn|demand|condemn|shrink|grow|slash|hik|freez|seiz|storm|cut|hit|fell|rose|fall|rise)(?:e|ed|es|ing|s|d)?"
PAT = [("quote", r"[“\"][^”\"]{12,300}[”\"]"), ("money", r"(?:US\$|\$|€|£)\s?(?:%s)%s|(?:%s)%s\s?(?:dollars|euros|pounds|yuan|rupees|yen)\b" % (NUM, MAG, NUM, MAG)), ("percent", r"(?:%s)\s?(?:%%|per ?cent\b|percent\b)" % NUM),
       ("quantity", r"(?:%s)%s(?:%s)" % (NUM, MAG, UNITS)), ("date", r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|yesterday|today|tomorrow|(?:last|this|next) (?:week|month|year))\b|\b%s\s+\d{1,2}(?:st|nd|rd|th)?\b(?!,?\s*\d{4})|\b%s\s+\d{4}\b" % (MONTH, MONTH)),
       ("attribution", r"\b(?:said|says|told|according to|reported|warned|claimed|stated|added|noted)\b"), ("negation", r"\b(?:not|no|never|denied|without|despite|fail(?:ed|s)?)\b|n’t|n't"),
       ("modal", r"\b(?:could|may|might|will|would|expected to|plans? to|set to|likely|vow(?:ed|s)? to)\b"), ("change", r"\b(?:rise|rising|rose|fall|falling|fell|surge[sd]?|soar(?:ed|ing)?|plunge[sd]?|drop(?:ped|s)?|jump(?:ed|s)?|increase[sd]?|decline[sd]?|record|worst|highest|lowest)\b"),
       ("event", r"\b" + EVENT + r"\b"), ("entity", r"[A-Z][\w’'-]+(?:\s+(?:of|the|de|and|for|al|bin)\s+[A-Z][\w’'-]+|\s+[A-Z][\w’'-]+)*")]
SCAN = re.compile("|".join(f"(?P<{n}>{p})" for n, p in PAT))
MON = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}; WD = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
def resolve(text, anchor):
    import datetime
    ad = datetime.date.fromisoformat(anchor[:10]); t = text.lower()
    if t in WD: return (ad - datetime.timedelta(days=(ad.weekday() - WD.index(t)) % 7)).isoformat()
    if t in ("yesterday", "today", "tomorrow"): return (ad + datetime.timedelta(days={"yesterday": -1, "today": 0, "tomorrow": 1}[t])).isoformat()
    m = re.match(r"(last|this|next) (week|month|year)", t)
    if m: return f"{m.group(1)} {m.group(2)} relative to {ad.isoformat()}"
    m = re.match(MONTH.lower() + r"\s+(\d{4})$", t)
    if m: return f"{m.group(1)}-{MON[t[:3]]:02d}"
    m = re.match(MONTH.lower() + r"\s+(\d{1,2})", t)
    if m:
        try:
            d = datetime.date(ad.year, MON[t[:3]], int(m.group(1)))
            return (d.replace(year=ad.year - 1) if d > ad + datetime.timedelta(days=30) else d).isoformat()
        except ValueError: return None
    return None
STARTER = set("The A An In On At As But And For With After Before When While If It He She They This That These Those There Here Now Then Our We You His Her Their Its According".split())
def scan(body, anchor):
    spots = []
    for m in SCAN.finditer(body):
        c = m.lastgroup; s, e = m.span()
        if c == "entity":
            single = " " not in m.group(0); first = s == 0 or body[max(0, s - 2):s] in (". ", "! ", "? ") or body[s - 1:s] in ("“", '"')
            if single and first and m.group(0) in STARTER: continue
            if single and m.group(0) in STARTER: continue
        spots.append([s, e, c] + ([resolve(m.group(0), anchor)] if c == "date" and anchor else []))
    sents = [(m.start(), m.end()) for m in re.finditer(r"[^\n]+?(?:(?<=[.!?])(?=\s+[A-Z0-9\"“‘'])|(?<=[.!?][”\"’])(?=\s)|$)", body)]
    return spots, [(a, b) for a, b in sents if body[a:b].strip()]
def scan_checks(body, spots):
    ok_sorted = all(spots[i][0] <= spots[i + 1][0] for i in range(len(spots) - 1)); ok_range = all(0 <= a < b <= len(body) for a, b, *_ in spots)
    ok_overlap = all(spots[i][1] <= spots[i + 1][0] for i in range(len(spots) - 1)); ok_text = all(body[a:b].strip() != "" for a, b, *_ in spots)
    return {"sorted": ok_sorted, "in_range": ok_range, "no_overlap": ok_overlap, "text_identity": ok_text}
def scan_speed(body):
    big = (body + " ") * max(1, 3_000_000 // len(body)); t0 = time.perf_counter(); n = sum(1 for _ in SCAN.finditer(big)); dt = time.perf_counter() - t0
    return round(len(big) / 1e6 / dt, 2)
# ------------------------------------------------------------------ G2 solver
nlp = spacy.load("en_core_web_sm", disable=["ner"]); SPEECH = {"say", "tell", "report", "claim", "announce", "warn", "state", "add", "note", "according"}; PLAN = {"plan", "expect", "intend", "vow", "set", "aim", "seek", "threaten", "promise"}
def np_span(t): return [t.left_edge.idx, t.idx + len(t.text)]
def solve(body):
    t0 = time.perf_counter(); doc = nlp(body); dt = time.perf_counter() - t0; frs = []
    for t in doc:
        if t.pos_ != "VERB" or t.lemma_ in SPEECH or t.lemma_ in ("be", "have", "do"): continue
        subj = next((c for c in t.children if c.dep_ in ("nsubj", "nsubjpass")), None); obj = next((c for c in t.children if c.dep_ in ("dobj", "attr", "oprd")), None)
        if obj is None:
            pp = next((c for c in t.children if c.dep_ == "prep"), None); obj = next((c for c in pp.children if c.dep_ == "pobj"), None) if pp else None
        if subj is None and obj is None: continue
        neg = any(c.dep_ == "neg" for c in t.children); aux = [c.lemma_ for c in t.children if c.dep_ == "aux"]
        if neg: fact, pol = "denied", -1
        elif t.dep_ in ("ccomp", "parataxis") and t.head.lemma_ in SPEECH: fact, pol = "reported", 1
        elif any(a in ("will", "would", "shall") for a in aux) or (t.dep_ == "xcomp" and t.head.lemma_ in PLAN): fact, pol = "planned", 1
        elif any(a in ("could", "may", "might", "can", "should") for a in aux): fact, pol = "predicted", 1
        elif t.sent.text.lower().startswith("according to"): fact, pol = "reported", 1
        else: fact, pol = "asserted", 1
        frs.append({"subject": np_span(subj) if subj else None, "predicate": [t.idx, t.idx + len(t.text)], "object": np_span(obj) if obj else None, "factuality": fact, "polarity": pol, "evidence": [t.sent.start_char, t.sent.end_char]})
    return frs, round(dt / len(body) * 1000 * 1000, 1)
def solve_checks(frs, n):
    inside = lambda sp, ev: sp is None or (ev[0] <= sp[0] < sp[1] <= ev[1]); fields = all(f["predicate"] and f["factuality"] and f["polarity"] in (1, -1) and f["evidence"] for f in frs)
    return {"fields_present": fields, "spans_inside_evidence": all(inside(f["subject"], f["evidence"]) and inside(f["predicate"], f["evidence"]) and inside(f["object"], f["evidence"]) for f in frs), "evidence_in_body": all(0 <= f["evidence"][0] < f["evidence"][1] <= n for f in frs)}
# ------------------------------------------------------------------ G3a / G3b heads
S = {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] == "sonnet" and r["version"] == "ws-v2-frozen": S[r["item_id"]] = r
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
ids = sorted(i for i in S if i in pool); T = [re.sub(r"\s+", " ", pool[i])[:600] for i in ids]
z = np.load("runs/pulse/kind_cascade_emb.npz"); assert list(z["ids"]) == ids; E1 = z["E1"]
grp = {}; gid = np.array([grp.setdefault(re.sub(r"\W+", "", t.lower())[:60], len(grp)) for t in T])
tr, va = next(GroupShuffleSplit(1, test_size=0.2, random_state=0).split(T, groups=gid)); rs = np.random.RandomState(1); va = rs.permutation(va); cal, te = va[: len(va) // 2], va[len(va) // 2:]
vec = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True).fit([T[i] for i in tr]); X = vec.transform(T); names = np.array(vec.get_feature_names_out()); print("vectorised", X.shape, flush=True)
PREC = 0.85
def thr_yes(p, y):
    best = None
    for t in np.unique(np.round(p, 4))[::-1]:
        m = p >= t
        if m.sum() >= 5 and y[m].mean() >= PREC: best = float(t)
        elif best is not None and m.sum() >= 5 and y[m].mean() < PREC - 0.05: break
    return best
def thr_no(p, y):
    """a 'no' answer is allowed only below the 5th percentile of the positives, so it loses at most 5 percent of them (needs 15 positives to trust)"""
    return float(np.percentile(p[y == 1], 5)) if (y == 1).sum() >= 15 else None
def fit_binary(M, y):
    m = LogisticRegression(C=10.0 if M is X else 3.0, max_iter=2000, class_weight="balanced").fit(M[tr], y[tr]); pc = m.predict_proba(M[cal])[:, 1]; pt = m.predict_proba(M[te])[:, 1]
    iso = IsotonicRegression(out_of_bounds="clip").fit(pc, y[cal]); cc, ct = iso.predict(pc), iso.predict(pt); ty, tn = thr_yes(cc, y[cal]), thr_no(cc, y[cal])
    ym = (ct >= ty) if ty is not None else np.zeros(len(te), bool); nm = (ct < tn) if tn is not None else np.zeros(len(te), bool); yt = y[te]
    met = {"threshold_yes": ty, "threshold_no": tn, "test_positives": int(yt.sum()), "yes_precision": round(float(yt[ym].mean()), 3) if ym.sum() else None, "yes_recall": round(float(yt[ym].sum() / max(yt.sum(), 1)), 3), "no_positives_lost": round(float(yt[nm].sum() / max(yt.sum(), 1)), 3) if nm.sum() else None, "no_coverage": round(float(nm[yt == 0].sum() / max((yt == 0).sum(), 1)), 3)}
    return m, iso, ty, tn, met
KH = {}
for k in KINDS:
    y = np.array([int(k in S[i]["kinds"]) for i in ids]); sp = fit_binary(X, y); en = fit_binary(E1, y); KH[k] = {"sparse": sp, "encoder": en}; print(k, sp[4]["yes_precision"], sp[4]["yes_recall"], "|enc", en[4]["yes_precision"], en[4]["yes_recall"], flush=True)
def fit_multi(labels):
    cls = sorted(set(labels)); yi = np.array([cls.index(l) for l in labels]); m = LogisticRegression(C=10.0, max_iter=300).fit(X[tr], yi[tr])
    def conf(idx):
        P = m.predict_proba(X[idx]); return P.argmax(1), P.max(1)
    pc, cc_ = conf(cal); ok = (pc == yi[cal]).astype(int); iso = IsotonicRegression(out_of_bounds="clip").fit(cc_, ok); cal_c = iso.predict(cc_); ty = thr_yes(cal_c, ok)
    pt, ct_ = conf(te); ct = iso.predict(ct_); ans = (ct >= ty) if ty is not None else np.zeros(len(te), bool); okt = (pt == yi[te])
    return m, iso, ty, cls, {"threshold": ty, "test_items": int(len(te)), "coverage": round(float(ans.mean()), 3), "precision_when_answered": round(float(okt[ans].mean()), 3) if ans.sum() else None, "classes": len(cls)}
ST = fit_multi([S[i]["story_type"] for i in ids]); TP = fit_multi([S[i]["topic"] for i in ids]); print("story type", ST[4], "topic", TP[4], flush=True)
# latency and size
t0 = time.perf_counter(); sample = [T[i] for i in te[:200]]; Xs = vec.transform(sample)
for k in KINDS: KH[k]["sparse"][0].predict_proba(Xs)
ST[0].predict_proba(Xs); TP[0].predict_proba(Xs); lat = round((time.perf_counter() - t0) / len(sample) * 1000, 3)
size = (sum(KH[k]["sparse"][0].coef_.size for k in KINDS) + ST[0].coef_.size + TP[0].coef_.size) * 4 / 1e6
tk = Tokenizer.from_file("runs/embeds/leaf_tokenizer.json"); tk.enable_truncation(max_length=64); tk.no_padding(); so = ort.SessionOptions(); so.intra_op_num_threads = 4; sess = ort.InferenceSession("runs/embeds/student_v6b-student.onnx", so, providers=["CPUExecutionProvider"])
def emb(t):
    e = tk.encode(re.sub(r"\s+", " ", t)[:1200]); i = np.array([e.ids], dtype=np.int64); return sess.run(None, {"input_ids": i, "attention_mask": np.ones_like(i)})[0][0]
def find_all(body, ng):
    return [[m.start(), m.end()] for m in re.finditer(r"\b" + re.escape(ng).replace(r"\ ", r"\s+") + r"\b", body, re.I)]
casc = {}
for k in KINDS:
    (m, iso, ty, tn, _), (me, isoe, tye, tne, _) = KH[k]["sparse"], KH[k]["encoder"]; y = np.array([int(k in S[i]["kinds"]) for i in ids])[te]
    ps = iso.predict(m.predict_proba(X[te])[:, 1]); pe = isoe.predict(me.predict_proba(E1[te])[:, 1]); z0 = np.zeros(len(te), bool)
    sy = (ps >= ty) if ty is not None else z0; sn = (ps < tn) if tn is not None else z0; unk = ~(sy | sn); ey = (pe >= tye) if tye is not None else z0; en_ = (pe < tne) if tne is not None else z0
    casc[k] = {"escalated_share": round(float(unk.mean()), 3), "encoder_yes": int((unk & ey).sum()), "encoder_yes_precision": round(float(y[unk & ey].mean()), 3) if (unk & ey).sum() else None, "encoder_no": int((unk & en_).sum()), "still_unknown_share": round(float((unk & ~ey & ~en_).mean()), 3)}
CASC = {"per_kind": casc, "mean_escalated_share": round(float(np.mean([v["escalated_share"] for v in casc.values()])), 3), "mean_still_unknown_share": round(float(np.mean([v["still_unknown_share"] for v in casc.values()])), 3)}; print("cascade", CASC["mean_escalated_share"], CASC["mean_still_unknown_share"], flush=True)
# ------------------------------------------------------------------ per article
D["g3a_suite"] = {"cascade": CASC, "precision_target": PREC, "calibration": "isotonic on a grouped calibration half; thresholds set on that half; metrics on a separate test half", "train_items": int(len(tr)), "calibration_items": int(len(cal)), "test_items": int(len(te)), "latency_ms_per_item_single_thread": lat, "model_mb": round(size, 1), "vocabulary": int(len(names)),
                  "story_type": ST[4], "topic": TP[4], "kinds": {k: {"sparse": KH[k]["sparse"][4], "encoder": KH[k]["encoder"][4]} for k in KINDS}}
for a in D["articles"]:
    c = a["contract"]; body = c["body"]; anchor = c["time"]["anchor"]; spots, sents = scan(body, anchor); chk = scan_checks(body, spots)
    cnt = collections.Counter(s[2] for s in spots); frs, ms = solve(body)
    a["sentences"] = [{"start": s, "end": e} for s, e in sents]
    a["scan"] = {"spots": spots, "counts": dict(cnt), "per_1k_chars": round(len(spots) / len(body) * 1000, 1), "mb_per_s": scan_speed(body), "checks": chk, "sentences": len(sents)}
    a["solver"] = {"fragments": frs, "n": len(frs), "with_subject": sum(1 for f in frs if f["subject"]), "with_object": sum(1 for f in frs if f["object"]), "factuality": dict(collections.Counter(f["factuality"] for f in frs)), "ms_per_1k_chars": ms, "checks": solve_checks(frs, len(body))}
    view = c["title"] + ". " + body; view = re.sub(r"\s+", " ", view)[:600]; shift = len(c["title"]) + 2; xa = vec.transform([view]); ea = emb(view)
    def multi(M):
        m, iso, ty, cls, met = M; P = m.predict_proba(xa)[0]; j = int(P.argmax()); cc = float(iso.predict([P[j]])[0]); return {"answer": cls[j], "confidence": round(cc, 3), "status": "answered" if (ty is not None and cc >= ty) else "unknown", "second": cls[int(np.argsort(-P)[1])]}, m.coef_[j]
    st, stc = multi(ST); tp, tpc = multi(TP); heads = []; esc = []; ev = []
    def evidence(head, coef):
        xv = np.asarray(xa.multiply(coef).todense()).ravel(); out = []
        for j in np.argsort(-xv)[:4]:
            if xv[j] <= 0: break
            sp = find_all(body, str(names[j]))
            if sp: out.append({"head": head, "ngram": str(names[j]), "spans": sp})
        return out
    ev += evidence("story_type=" + st["answer"], stc) if st["status"] == "answered" else []; ev += evidence("topic=" + tp["answer"], tpc) if tp["status"] == "answered" else []
    for k in KINDS:
        (m, iso, ty, tn, met), (me, isoe, tye, tne, mete) = KH[k]["sparse"], KH[k]["encoder"]; p = float(iso.predict(m.predict_proba(xa)[:, 1])[0]); status = "yes" if ty is not None and p >= ty else ("no" if tn is not None and p < tn else "unknown")
        row = {"kind": k, "p": round(p, 3), "status": status, "stage": "G3a"}
        if status == "unknown":
            pe = float(isoe.predict(me.predict_proba(ea[None])[:, 1])[0]); se = "yes" if tye is not None and pe >= tye else ("no" if tne is not None and pe < tne else "unknown"); row.update({"encoder_p": round(pe, 3), "encoder_status": se}); esc.append(k)
        if status == "yes":
            xv = np.asarray(xa.multiply(m.coef_[0]).todense()).ravel(); 
            for j in np.argsort(-xv)[:3]:
                sp = find_all(body, str(names[j])) if xv[j] > 0 else []
                if sp: ev.append({"head": k, "ngram": str(names[j]), "spans": sp})
        heads.append(row)
    a["sparse"] = {"story_type": st, "topic": tp, "kinds": heads, "escalated": esc, "evidence": ev}
    print(a["id"], "spots", len(spots), dict(cnt), chk, "| frags", len(frs), a["solver"]["checks"], "| st", st["answer"], st["status"], "| topic", tp["answer"], tp["status"], "| yes", [h["kind"] for h in heads if h["status"] == "yes"], "esc", len(esc), flush=True)
D.pop("articles_note", None); json.dump(D, open(DATA, "w")); print("saved; latency ms", lat, "model MB", round(size, 1))
