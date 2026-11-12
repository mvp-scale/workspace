"""Measure the extract.py factuality tagger (factuality-rules-v1, playbook 15 row 13) against MAVEN-FACT labels.
Truth: /workspace/data/anchors/maven_fact/valid.jsonl (scoring only). Same 250 docs / mentions as maven_trigger.py (shuffle seed 11).
Tagger logic is copied line-for-line from extract.work (same constants imported from extract.py); applied to each gold sentence as one span,
parsed from the dataset tokens. A mention is tied to its sentence by sent_id; untied mentions are counted.
MAPPING (tagger tag -> class): asserted, reported, decision, request -> certain ; denied -> negated ; planned, predicted, question, unknown -> possible.
GOLD: CT+ -> certain ; CT-, PS- -> negated ; PS+, Uu -> possible.
Also binary: certain vs not-certain (CT+ vs rest), as in maven_trigger.json.
Baseline: best constant (always 'certain'). Bootstrap: 1000 resamples of documents (mentions cluster in docs).
Run: /workspace/models/embed-zs/.venv/bin/python factuality_measure.py -> runs/harvest/toolchain_measure/factuality_maven.json"""
import json, random, warnings, collections; warnings.filterwarnings("ignore")
import numpy as np, spacy
from spacy.tokens import Doc
from extract import SPEECH, DECIDE, REQUEST, PLAN, PRED
nlp = spacy.load("en_core_web_sm")
def tag(s):
    toks = list(s); lem = {t.lemma_.lower() for t in toks}; low = s.text.lower(); root = s.root
    rootneg = any(c.dep_ == "neg" for c in root.children); modal = {t.lower_ for t in toks if t.tag_ == "MD"}; past = root.tag_ in ("VBD", "VBN"); subj = any(c.dep_ in ("nsubj", "nsubjpass") for c in root.children)
    if s.text.strip().endswith("?"): return "question"
    elif lem & SPEECH or "according to" in low: return "reported"
    elif rootneg and root.pos_ in ("VERB", "AUX"): return "denied"
    elif root.lemma_.lower() in REQUEST and root.pos_ == "VERB" or "should" in modal or "must" in modal or (root.dep_ == "ROOT" and root.tag_ == "VB" and root.i == s.start and not subj): return "request"
    elif root.lemma_.lower() in DECIDE and past and subj: return "decision"
    elif modal & {"will", "shall", "'ll"} or (lem & PLAN and "to" in low): return "planned"
    elif modal & {"may", "might", "could", "would"} or lem & PRED: return "predicted"
    elif root.pos_ in ("VERB", "AUX"): return "asserted"
    return "unknown"
MAP = {"asserted": "certain", "reported": "certain", "decision": "certain", "request": "certain", "denied": "negated", "planned": "possible", "predicted": "possible", "question": "possible", "unknown": "possible"}
GM = {"CT+": "certain", "CT-": "negated", "PS-": "negated", "PS+": "possible", "Uu": "possible"}
docs = [json.loads(l) for l in open("/workspace/data/anchors/maven_fact/valid.jsonl")]; random.Random(11).shuffle(docs); docs = docs[:250]
rows = []; untied = 0; tot = 0; tagc = collections.Counter()
for di, D in enumerate(docs):
    cache = {}
    for ev in D["events"]:
        for m in ev["mention"]:
            tot += 1; si = m["sent_id"]
            if not (0 <= si < len(D["tokens"])) or not D["tokens"][si]: untied += 1; continue
            if si not in cache:
                d = Doc(nlp.vocab, words=D["tokens"][si])
                for _, p in nlp.pipeline: d = p(d)
                cache[si] = tag(d[:])
            t = cache[si]; tagc[t] += 1; rows.append((di, GM[m["factuality"]], MAP[t], m["factuality"], t))
g = np.array([r[1] for r in rows]); p = np.array([r[2] for r in rows]); did = np.array([r[0] for r in rows]); CL = ["certain", "negated", "possible"]
def stats(idx):
    gg, pp = g[idx], p[idx]; acc = float((gg == pp).mean()); rec = [float((pp[gg == c] == c).mean()) for c in CL if (gg == c).any()]
    gb, pb = gg == "certain", pp == "certain"; recb = [float(pb[gb].mean()), float((~pb[~gb]).mean())] if (~gb).any() else [float(pb[gb].mean())]
    cacc = float((gg == "certain").mean())
    return {"acc3": acc, "bal3": float(np.mean(rec)), "acc2": float((gb == pb).mean()), "bal2": float(np.mean(recb)), "const_acc": cacc, "diff_acc": acc - cacc}
full = stats(np.arange(len(g))); rng = np.random.default_rng(5); byd = collections.defaultdict(list)
for i, d in enumerate(did): byd[d].append(i)
ks = list(byd); bs = []
for _ in range(1000):
    idx = np.concatenate([byd[k] for k in rng.choice(ks, len(ks))]); bs.append(stats(idx))
ci = {k: [round(float(np.percentile([b[k] for b in bs], q)), 4) for q in (2.5, 97.5)] for k in full}
conf = {a: {b: int(((g == a) & (p == b)).sum()) for b in CL} for a in CL}
res = {"v": "factuality-measure-v1", "docs": 250, "mentions_total": tot, "mentions_untied_to_sentence": untied, "mentions_scored": len(rows), "gold_counts": dict(collections.Counter(g.tolist())), "tag_counts": dict(tagc), "pred_counts": dict(collections.Counter(p.tolist())),
       "metrics": {k: round(v, 4) for k, v in full.items()}, "bootstrap95": ci, "best_constant": {"answer": "certain", "acc": round(full["const_acc"], 4), "bal3": round(1 / 3, 4), "bal2": 0.5}, "confusion_gold_by_pred": conf,
       "mapping": MAP, "note": "bal3 = mean recall over the 3 classes; bal2 = certain vs not-certain"}
json.dump(res, open("runs/harvest/toolchain_measure/factuality_maven.json", "w"), indent=1); print(json.dumps(res, indent=1))
