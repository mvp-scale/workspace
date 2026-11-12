"""Head-to-head: tool A (facts_lib.facts_for 'triple' facts) vs tool B (spo_chains.extract) on MAVEN-FACT valid.jsonl (scoring only, never trained on or copied).
    /workspace/models/embed-zs/.venv/bin/python toolchain_measure.py [N docs] -> runs/harvest/toolchain_measure/toolchain_measure.json
Reading/matching reused exactly from maven_trigger.py: same 250 docs (Random(11) shuffle of valid.jsonl, first N); each event mention m has sent_id and token offset [a,b).
 B: sentences parsed as pre-tokenised spaCy Docs; verb hit = a triple in that sentence with v_i in [a,b); arg hit = triple s_i or o_i in [a,b).
 A: facts_for needs raw text, so each document is the tokens joined by single spaces (sentences joined by a space) and the mention becomes a character range [start of token a, end of token b-1).
    verb hit = a kind=='triple' fact whose verb token starts inside that range; arg hit = the subject or object head (same nsubj/nsubjpass and dobj/attr/oprd rule facts_lib uses) starts inside the range.
 Precision proxy = share of triples whose verb token lies inside any marked mention of the document (B: appositive triples count with their v_i). Time = parse + extraction per article (A: nlp+scan inside facts_for; B: per-sentence parse + extract).
 Bootstrap: 2000 paired resamples of documents on the recall difference B-A. CPU only."""
import sys, json, random, time, statistics, warnings; warnings.filterwarnings("ignore")
import numpy as np, spacy
from spacy.tokens import Doc
import spo_chains as S, facts_lib as F
N = int(sys.argv[1]) if len(sys.argv) > 1 else 250
nlp = spacy.load("en_core_web_sm"); docs = [json.loads(l) for l in open("/workspace/data/anchors/maven_fact/valid.jsonl")]; random.Random(11).shuffle(docs); docs = docs[:N]
def parsed(tokens):
    d = Doc(nlp.vocab, words=tokens)
    for _, proc in nlp.pipeline: d = proc(d)
    return d
per = []; t0 = time.time()
for D in docs:
    mentions = [(m["sent_id"], m["offset"][0], m["offset"][1]) for ev in D["events"] for m in ev["mention"]]
    # B
    tb = time.perf_counter(); sd = [parsed(t) for t in D["tokens"]]; T = S.extract(nlp, sd); tb = (time.perf_counter() - tb) * 1000
    bys = {}
    for t in T: bys.setdefault(t["sent"], []).append(t)
    bv = ba = 0; 
    for si, a, b in mentions:
        ts = bys.get(si, []); v = any(a <= t["v_i"] < b for t in ts); g = any((t["s_i"] is not None and a <= t["s_i"] < b) or (t["o_i"] is not None and a <= t["o_i"] < b) for t in ts)
        bv += v; ba += (v or g)
    bprec = sum(1 for t in T if any(si == t["sent"] and a <= t["v_i"] < b for si, a, b in mentions))
    # A
    text = ""; spans = {}
    for si, toks in enumerate(D["tokens"]):
        for ti, w in enumerate(toks):
            if text: text += " "
            spans[(si, ti)] = (len(text), len(text) + len(w)); text += w
    ta = time.perf_counter(); facts, _, doc = F.facts_for(text, "2026-01-01T00:00:00Z"); ta = (time.perf_counter() - ta) * 1000
    tr = [f for f in facts if f["kind"] == "triple"]; vstart = [f["s"] for f in tr]; astart = []
    for f in tr:
        tok = doc.char_span(f["s"], f["e"], alignment_mode="expand")[0]
        subj = next((c for c in tok.children if c.dep_ in ("nsubj", "nsubjpass")), None); obj = next((c for c in tok.children if c.dep_ in ("dobj", "attr", "oprd")), None)
        if obj is None:
            pp = next((c for c in tok.children if c.dep_ == "prep"), None); obj = next((c for c in pp.children if c.dep_ == "pobj"), None) if pp else None
        astart.append([x.idx for x in (subj, obj) if x is not None])
    av = aa = 0; rng = []
    for si, a, b in mentions:
        lo, hi = spans[(si, a)][0], spans[(si, b - 1)][1]; rng.append((lo, hi))
        v = any(lo <= s < hi for s in vstart); g = any(lo <= x < hi for xs in astart for x in xs); av += v; aa += (v or g)
    aprec = sum(1 for s in vstart if any(lo <= s < hi for lo, hi in rng))
    per.append(dict(n=len(mentions), bv=bv, ba=ba, av=av, aa=aa, bt=len(T), at=len(tr), bp=bprec, ap=aprec, tb=tb, ta=ta))
    if time.time() - t0 > 1500: print("time cap hit"); break
n = len(per); tot = sum(p["n"] for p in per)
def rec(k): return sum(p[k] for p in per) / tot
rng = np.random.default_rng(5); arr = {k: np.array([p[k] for p in per], float) for k in per[0]}; cnt = arr["n"]; boots = {"verb": [], "verb_or_arg": []}
for _ in range(2000):
    ix = rng.integers(0, n, n); d = cnt[ix].sum()
    boots["verb"].append((arr["bv"][ix].sum() - arr["av"][ix].sum()) / d); boots["verb_or_arg"].append((arr["ba"][ix].sum() - arr["aa"][ix].sum()) / d)
ci = lambda x: [round(float(np.percentile(x, 2.5)), 3), round(float(np.percentile(x, 97.5)), 3)]
res = {"v": "toolchain-measure-v1", "documents": n, "event_mentions": tot,
 "A_facts_lib_triples": {"trigger_recall_verb_of_a_triple": round(rec("av"), 3), "trigger_recall_verb_or_argument_head": round(rec("aa"), 3), "triples_per_article": round(sum(p["at"] for p in per) / n, 2), "precision_proxy_verb_is_trigger": round(sum(p["ap"] for p in per) / max(sum(p["at"] for p in per), 1), 3), "median_ms_per_article": round(statistics.median(p["ta"] for p in per), 1), "share_articles_no_triple": round(sum(1 for p in per if p["at"] == 0) / n, 3)},
 "B_spo_chains_triples": {"trigger_recall_verb_of_a_triple": round(rec("bv"), 3), "trigger_recall_verb_or_argument_head": round(rec("ba"), 3), "triples_per_article": round(sum(p["bt"] for p in per) / n, 2), "precision_proxy_verb_is_trigger": round(sum(p["bp"] for p in per) / max(sum(p["bt"] for p in per), 1), 3), "median_ms_per_article": round(statistics.median(p["tb"] for p in per), 1), "share_articles_no_triple": round(sum(1 for p in per if p["bt"] == 0) / n, 3)},
 "recall_difference_B_minus_A": {"verb_of_a_triple": {"diff": round(rec("bv") - rec("av"), 3), "ci95": ci(boots["verb"])}, "verb_or_argument_head": {"diff": round(rec("ba") - rec("aa"), 3), "ci95": ci(boots["verb_or_arg"])}}}
json.dump(res, open("runs/harvest/toolchain_measure/toolchain_measure.json", "w"), indent=1); print(json.dumps(res, indent=1))
