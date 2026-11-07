"""Mock-up data (owner request 2026-11-05): run three REAL news articles (newsreader Clef-labelled set, none in any training pool) through gates G0 normalise, G1 scan, G2 semantic (sentence embeddings + HDBSCAN topic groups), G3a sparse classify, G3b encoder, and build the evidence ladder over the 16 condition kinds from runs/pulse/kind_cascade.json. Nothing here is typed in by hand; every figure is computed. Writes /workspace/demo/mockups/gates/data.json.
    /workspace/models/embed-zs/.venv/bin/python gates_mockup_data.py   (from projects/world-state)"""
import json, re, hashlib, unicodedata, collections, urllib.request, numpy as np, onnxruntime as ort
from tokenizers import Tokenizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.cluster import HDBSCAN, KMeans
import size_quantity as SQ, normalize as NZ
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
PICK = json.load(open("runs/pulse/mockup_articles.json"))
KINDS = list(json.load(open("runs/pulse/kind_cascade.json"))["per_kind"])
tk = Tokenizer.from_file("runs/embeds/leaf_tokenizer.json"); tk.enable_truncation(max_length=64); tk.no_padding()
so = ort.SessionOptions(); so.intra_op_num_threads = 4; sess = ort.InferenceSession("runs/embeds/student_v6b-student.onnx", so, providers=["CPUExecutionProvider"])
def emb(t):
    e = tk.encode(re.sub(r"\s+", " ", t)[:1200]); i = np.array([e.ids], dtype=np.int64); return sess.run(None, {"input_ids": i, "attention_mask": np.ones_like(i)})[0][0]
# ---- training data for the two per-kind stages (Sonnet labels, the same items as kind_cascade.py)
S = {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] == "sonnet" and r["version"] == "ws-v2-frozen": S[r["item_id"]] = set(r["kinds"])
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
ids = sorted(i for i in S if i in pool); T = [re.sub(r"\s+", " ", pool[i])[:600] for i in ids]
z = np.load("runs/pulse/kind_cascade_emb.npz"); assert list(z["ids"]) == ids; E1 = z["E1"]
vec = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True, stop_words=None); X = vec.fit_transform(T); names = np.array(vec.get_feature_names_out())
SP, EN = {}, {}
for k in KINDS:
    y = np.array([int(k in S[i]) for i in ids]); SP[k] = LogisticRegression(C=10.0, max_iter=2000, class_weight="balanced").fit(X, y); EN[k] = LogisticRegression(C=3.0, max_iter=2000, class_weight="balanced").fit(E1, y)
print("trained", len(KINDS), "kinds on", len(ids), flush=True)
idf = TfidfVectorizer(ngram_range=(1, 1), min_df=3, stop_words="english").fit([pool[i][:600] for i in ids[:6000]]); IDF = dict(zip(idf.get_feature_names_out(), idf.idf_))
# ---- ladder
casc = json.load(open("runs/pulse/kind_cascade.json"))["per_kind"]; ladder = []
for k in KINDS:
    pc = SP[k].coef_[0]; pos = np.sort(pc[pc > 0])[::-1]; conc = float(pos[:10].sum() / pos.sum())
    c = casc[k]; sp, en = c["sparse"]["f1_vs_sonnet"], c["enc_story"]["f1_vs_sonnet"]; enp = c["enc_story"]["pass_both"]
    sup = "wording" if sp >= 0.70 else ("meaning" if enp else "weak")
    top = [str(names[j]) for j in np.argsort(-pc)[:8]]
    ladder.append({"kind": k, "ceiling": c["labeller_ceiling"], "rules_f1": c["rules"]["f1_vs_sonnet"], "sparse_f1": sp, "encoder_f1": en, "encoder_f1_vs_haiku": c["enc_story"]["f1_vs_haiku"], "encoder_pass_both": enp, "top10_weight_share": round(conc, 3), "top_ngrams": top, "support": sup, "positives": c["positives_sonnet"]})
# ---- gates on three articles
STOP = set("the of and to a in is that for it on with as was at by from be this are an or have has had not but they their its were which will would about after more than also can been who said says".split())
CHG = r"\b(?:rose|rise|rising|fell|fall|falling|surge[sd]?|soar(?:ed|ing)?|plunge[sd]?|drop(?:ped|s)?|jump(?:ed|s)?|increase[sd]?|decline[sd]?|slump(?:ed)?|record|worst|highest|lowest|spike[sd]?)\b"
ATTR = r"\b(?:said|says|told|according to|reported|announced|warned|claimed|stated)\b"; MOD = r"\b(?:could|may|might|will|would|expected to|plans? to|set to|likely)\b"; NEG = r"\b(?:not|no|never|denied|without|despite|fail(?:ed|s)?)\b"
def spans(s):
    out = []
    for o in SQ.extract(s):
        j = s.find(o["span"]); 
        if j >= 0: out.append(("quantity", j, j + len(o["span"])))
    for m in re.finditer(r"[A-Z][\w’'-]+(?:\s+(?:of|the|de|and|for)\s+[A-Z][\w’'-]+|\s+[A-Z][\w’'-]+)*", s):
        if m.start() == 0 and " " not in m.group(0): continue
        out.append(("entity", m.start(), m.end()))
    for n, rx in (("change", CHG), ("attribution", ATTR), ("modal", MOD), ("negation", NEG)):
        for m in re.finditer(rx, s, re.I): out.append((n, m.start(), m.end()))
    for m in re.finditer(r"[“\"]([^”\"]{12,200})[”\"]", s): out.append(("quote", m.start(), m.end()))
    return sorted(out, key=lambda x: (x[1], x[2]))
MON = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
WD = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
def resolve_times(body, anchor):
    """G1 time mentions resolved against the record anchor (TIMEX-style, small): weekday names, yesterday/today/tomorrow, 'Month D', 'Month YYYY'."""
    import datetime
    ad = datetime.date.fromisoformat(anchor[:10]); out = []
    for m in re.finditer(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b", body):
        d = ad - datetime.timedelta(days=(ad.weekday() - WD.index(m.group(1).lower())) % 7); out.append((m.start(), m.end(), d.isoformat(), "most recent " + m.group(1) + " on or before the anchor"))
    for m in re.finditer(r"\b(yesterday|today|tomorrow)\b", body, re.I):
        d = ad + datetime.timedelta(days={"yesterday": -1, "today": 0, "tomorrow": 1}[m.group(1).lower()]); out.append((m.start(), m.end(), d.isoformat(), m.group(1).lower() + " relative to the anchor"))
    for m in re.finditer(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?!,?\s*\d{4})", body):
        try:
            d = datetime.date(ad.year, MON[m.group(1).lower()], int(m.group(2)))
            if d > ad + datetime.timedelta(days=30): d = d.replace(year=ad.year - 1)
            out.append((m.start(), m.end(), d.isoformat(), "month and day, year taken from the anchor"))
        except ValueError: pass
    for m in re.finditer(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{4})\b", body): out.append((m.start(), m.end(), f"{m.group(2)}-{MON[m.group(1).lower()]:02d}", "month and year as written"))
    return [{"text": body[a:b], "start": a, "end": b, "resolved": r, "rule": ru} for a, b, r, ru in sorted(out)]
def pulse(text):
    req = urllib.request.Request("http://127.0.0.1:8023/v1/pulse", data=json.dumps({"text": text}).encode(), headers={"content-type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=10))["result"]; return r["story_type"]["answer"], r["topic_top2"]["answer"]
rows = {r["id"][:8]: r for r in J("/workspace/data/newsreader/labels/clef-q4km.jsonl") if r["id"][:8] in PICK}; arts = []
for pid in PICK:
    r = rows[pid]; raw = r["text"]
    import sqlite3
    _c = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); _c.row_factory = sqlite3.Row
    _row = _c.execute("select url, published, found_at, lang, country, teaser from items where source=? and title=? limit 1", (r["source"], r["title"])).fetchone()
    contract = NZ.feed_article(r, dict(_row) if _row else None); t = contract["body"]; paras = [t]
    sents = []
    for pi, p in enumerate(paras):
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“‘'])", p):
            if len(s) > 20: sents.append({"para": pi, "text": s})
    sents = sents[:40]; Em = np.array([emb(s["text"]) for s in sents], dtype=np.float32); En = Em / np.linalg.norm(Em, axis=1, keepdims=True)
    cl = HDBSCAN(min_cluster_size=2, min_samples=1).fit_predict(En); method = "HDBSCAN"
    if len(set(cl) - {-1}) < 2: cl = KMeans(3, n_init=10, random_state=0).fit_predict(En); method = "k-means (k=3; HDBSCAN found fewer than 2 stable groups)"
    for i, s in enumerate(sents):
        s["spans"] = [{"cls": c, "a": a, "b": b} for c, a, b in spans(s["text"])]; s["story_type"], s["topic"] = pulse(s["text"]); s["cluster"] = int(cl[i])
    cur = 0
    for s in sents:
        i = t.find(s["text"], cur); s["start"] = i if i >= 0 else None; s["end"] = (i + len(s["text"])) if i >= 0 else None
        if i >= 0: cur = i + len(s["text"])
    times = resolve_times(t, contract["time"]["anchor"]) if contract["time"]["anchor"] else []
    groups = []
    for g in sorted(set(cl) - {-1}):
        m = [i for i in range(len(sents)) if cl[i] == g]; cen = En[m].mean(0); rep = m[int(np.argmin(np.linalg.norm(En[m] - cen, axis=1)))]
        cnt = collections.Counter(w for i in m for w in re.findall(r"[a-z][a-z']{2,}", sents[i]["text"].lower()) if w not in STOP); terms = sorted(cnt, key=lambda w: -(cnt[w] * IDF.get(w, 3.0)))[:8]
        tc = collections.Counter(sents[i]["topic"][0] for i in m); groups.append({"id": int(g), "size": len(m), "members": m, "representative": rep, "terms": terms, "topic_vote": tc.most_common(2)})
    noise = [i for i in range(len(sents)) if cl[i] == -1]
    head = re.sub(r"\s+", " ", t)[:600]; xa = vec.transform([head]); ea = emb(head); kinds = []
    for k in KINDS:
        ps = float(SP[k].predict_proba(xa)[0, 1]); pe = float(EN[k].predict_proba(ea[None])[0, 1]); xs = vec.transform([s["text"] for s in sents]); sp_s = SP[k].predict_proba(xs)[:, 1]; en_s = EN[k].predict_proba(Em)[:, 1]
        contrib = np.asarray(xa.multiply(SP[k].coef_[0]).todense()).ravel(); top = [(str(names[j]), round(float(contrib[j]), 3)) for j in np.argsort(-contrib)[:5] if contrib[j] > 0]
        kinds.append({"kind": k, "sparse_p": round(ps, 3), "encoder_p": round(pe, 3), "sparse_evidence": [sents[int(np.argmax(sp_s))]["start"], sents[int(np.argmax(sp_s))]["end"]], "encoder_evidence": [sents[int(np.argmax(en_s))]["start"], sents[int(np.argmax(en_s))]["end"]], "sparse_sentence": int(np.argmax(sp_s)), "sparse_sentence_p": round(float(sp_s.max()), 3), "encoder_sentence": int(np.argmax(en_s)), "encoder_sentence_p": round(float(en_s.max()), 3), "top_ngrams": top})
    arts.append({"id": r["id"][:8], "source": r["source"], "title": r["title"], "clef_dials": [f'{x["dial"]} {x["direction"]}' for x in r["readings"] if x["direction"] != "conflict"],
                 "contract": contract, "times": times, "trained_window_chars": 600,
                 "sentences": sents, "g2": {"method": method, "groups": groups, "noise": noise}, "kinds": kinds}); print(pid, len(sents), method, len(groups), flush=True)
ex = []
for l in J("data/pool_train.jsonl")[:4000:800]: ex.append(NZ.cc_headline(l))
doc = NZ.markdown_document(open("/workspace/knowledge_pipeline/playbook/00-knowledge-pipeline-v1.md", encoding="utf-8").read(), "Knowledge Pipeline v1 (playbook 00)", "knowledge_pipeline/playbook/00-knowledge-pipeline-v1.md")
json.dump({"document_example": doc, "adapter_design": NZ.ADAPTER_DESIGN, "contract_examples": ex[:2], "built_by": "projects/world-state/gates_mockup_data.py", "ladder": ladder, "ladder_rule": "wording = sparse n-gram F1 vs Sonnet at least 0.70; meaning = encoder passes both labellers (L933) but sparse under 0.70; weak = encoder does not pass", "articles": arts}, open("/workspace/demo/mockups/gates/data.json", "w"))
print("saved", {k: sum(1 for l in ladder if l["support"] == k) for k in ("wording", "meaning", "weak")})
