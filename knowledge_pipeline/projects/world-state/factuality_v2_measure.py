"""V1 (old tagger, as factuality_measure.py), V2 (certain/negated/possible from the matching spo_chains triple; fallback to V1), V3 (old tagger, 'denied' decided by the triple neg flag in the sentence).
Same 250 docs (seed 11), mentions, sent_id tie, MAP, GM and document bootstrap (1000, rng seed 5) as factuality_measure.py; truth scoring-only.
Triple matching as maven_trigger.py (verb index inside mention offset, else subject/object head inside it).
V2 rule (fixed before scoring): matched triple neg -> negated; else modal or attrib or said_by -> possible; else certain.
V3 rule: if the sentence has any triple: negated iff any triple neg, else the old tagger with its negation branch skipped; if no triple in the sentence: old tag.
Run: /workspace/models/embed-zs/.venv/bin/python factuality_v2_measure.py -> runs/harvest/toolchain_measure/factuality_v2.json"""
import json, random, warnings, collections; warnings.filterwarnings("ignore")
import numpy as np, spacy
from spacy.tokens import Doc
from extract import SPEECH, DECIDE, REQUEST, PLAN, PRED
import spo_chains as S
nlp = spacy.load("en_core_web_sm")
def tag(s, skipneg=False):
    toks = list(s); lem = {t.lemma_.lower() for t in toks}; low = s.text.lower(); root = s.root
    rootneg = any(c.dep_ == "neg" for c in root.children); modal = {t.lower_ for t in toks if t.tag_ == "MD"}; past = root.tag_ in ("VBD", "VBN"); subj = any(c.dep_ in ("nsubj", "nsubjpass") for c in root.children)
    if s.text.strip().endswith("?"): return "question"
    elif lem & SPEECH or "according to" in low: return "reported"
    elif rootneg and root.pos_ in ("VERB", "AUX") and not skipneg: return "denied"
    elif root.lemma_.lower() in REQUEST and root.pos_ == "VERB" or "should" in modal or "must" in modal or (root.dep_ == "ROOT" and root.tag_ == "VB" and root.i == s.start and not subj): return "request"
    elif root.lemma_.lower() in DECIDE and past and subj: return "decision"
    elif modal & {"will", "shall", "'ll"} or (lem & PLAN and "to" in low): return "planned"
    elif modal & {"may", "might", "could", "would"} or lem & PRED: return "predicted"
    elif root.pos_ in ("VERB", "AUX"): return "asserted"
    return "unknown"
MAP = {"asserted": "certain", "reported": "certain", "decision": "certain", "request": "certain", "denied": "negated", "planned": "possible", "predicted": "possible", "question": "possible", "unknown": "possible"}
GM = {"CT+": "certain", "CT-": "negated", "PS-": "negated", "PS+": "possible", "Uu": "possible"}
docs = [json.loads(l) for l in open("/workspace/data/anchors/maven_fact/valid.jsonl")]; random.Random(11).shuffle(docs); docs = docs[:250]
rows = []; untied = 0; tot = 0; matched = 0; v2changed = 0
for di, D in enumerate(docs):
    sd = [None] * len(D["tokens"])
    def parsed(si):
        if sd[si] is None:
            d = Doc(nlp.vocab, words=D["tokens"][si])
            for _, p in nlp.pipeline: d = p(d)
            sd[si] = d
        return sd[si]
    for si in range(len(sd)): parsed(si) if D["tokens"][si] else None
    docs_for_S = [sd[i] if sd[i] is not None else Doc(nlp.vocab, words=[]) for i in range(len(sd))]
    T = S.extract(nlp, docs_for_S); by = collections.defaultdict(list)
    for t in T: by[t["sent"]].append(t)
    cache = {}
    for ev in D["events"]:
        for m in ev["mention"]:
            tot += 1; si = m["sent_id"]
            if not (0 <= si < len(D["tokens"])) or not D["tokens"][si]: untied += 1; continue
            if si not in cache:
                s = sd[si][:]; ts = by.get(si, [])
                t1 = tag(s); t3 = ("negated" if any(t["neg"] for t in ts) else MAP[tag(s, True)]) if ts else MAP[t1]
                cache[si] = (MAP[t1], t3)
            p1, p3 = cache[si]; a, b = m["offset"]; ts = by.get(si, [])
            vh = [t for t in ts if a <= t["v_i"] < b]; ah = [t for t in ts if (t["s_i"] is not None and a <= t["s_i"] < b) or (t["o_i"] is not None and a <= t["o_i"] < b)]; use = vh or ah
            if use:
                matched += 1
                p2 = "negated" if any(t["neg"] for t in use) else ("possible" if any(t["modal"] or t["attrib"] or t["said_by"] for t in use) else "certain")
                if p2 != p1: v2changed += 1
            else: p2 = p1
            rows.append((di, GM[m["factuality"]], p1, p2, p3))
g = np.array([r[1] for r in rows]); P = {"V1": np.array([r[2] for r in rows]), "V2": np.array([r[3] for r in rows]), "V3": np.array([r[4] for r in rows])}; did = np.array([r[0] for r in rows]); CL = ["certain", "negated", "possible"]
def stats(idx, p):
    gg, pp = g[idx], p[idx]; rec = [float((pp[gg == c] == c).mean()) for c in CL if (gg == c).any()]
    return {"acc3": float((gg == pp).mean()), "bal3": float(np.mean(rec)), "neg_recall": int(((gg == "negated") & (pp == "negated")).sum()), "certain_as_possible": int(((gg == "certain") & (pp == "possible")).sum()), "const_acc": float((gg == "certain").mean())}
full = {k: stats(np.arange(len(g)), p) for k, p in P.items()}
rng = np.random.default_rng(5); byd = collections.defaultdict(list)
for i, d in enumerate(did): byd[d].append(i)
ks = list(byd); bs = {k: [] for k in P}
for _ in range(1000):
    idx = np.concatenate([byd[k] for k in rng.choice(ks, len(ks))])
    for k, p in P.items(): bs[k].append(stats(idx, p))
pc = lambda a: [round(float(np.percentile(a, q)), 4) for q in (2.5, 97.5)]
ci = {k: {m: pc([b[m] for b in bs[k]]) for m in ("acc3", "bal3", "neg_recall", "certain_as_possible")} for k in P}
paired = {k: {"bal3_minus_V1": pc([a["bal3"] - b["bal3"] for a, b in zip(bs[k], bs["V1"])]), "acc3_minus_V1": pc([a["acc3"] - b["acc3"] for a, b in zip(bs[k], bs["V1"])]), "acc3_minus_const": pc([a["acc3"] - a["const_acc"] for a in bs[k]])} for k in ("V2", "V3")}
paired["V1"] = {"acc3_minus_const": pc([a["acc3"] - a["const_acc"] for a in bs["V1"]])}
res = {"v": "factuality-v2-measure-v1", "docs": 250, "mentions_total": tot, "untied": untied, "scored": len(rows), "mentions_matched_to_triple": matched, "v2_differs_from_v1": v2changed, "gold_counts": dict(collections.Counter(g.tolist())),
       "variants_tried": 2, "note": "V2 and V3 each run once on the same mentions; no tuning", "full": {k: {m: round(v, 4) if isinstance(v, float) else v for m, v in d.items()} for k, d in full.items()}, "bootstrap95": ci, "paired95": paired, "best_constant": {"answer": "certain", "acc3": round(full["V1"]["const_acc"], 4), "bal3": 0.3333},
       "confusion_gold_by_pred": {k: {a: {b: int(((g == a) & (p == b)).sum()) for b in CL} for a in CL} for k, p in P.items()}}
json.dump(res, open("runs/harvest/toolchain_measure/factuality_v2.json", "w"), indent=1); print(json.dumps(res, indent=1))
