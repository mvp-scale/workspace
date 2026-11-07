"""Judge the gates against OUTSIDE human-labelled anchors (pre-registered L956). No training on the anchors; internal scoring only (licences). 
J1 coverage of gold event triggers (MAVEN-FACT, items_T33b) by G2 fragment predicates and G1 event verbs. J2 agreement of G2 factuality with MAVEN-FACT 'certainly happened'. J3 separation of subjective vs objective sentences (CheckThat) by G1 cues and G2 factuality counts, AUC, no fitting.
    /workspace/models/embed-zs/.venv/bin/python judge_gates.py   (from projects/world-state)"""
import json, re, collections, numpy as np, spacy
from sklearn.metrics import roc_auc_score
import scan_gate as G
nlp = spacy.load("en_core_web_sm", disable=["ner"]); SPEECH = {"say", "tell", "report", "claim", "announce", "warn", "state", "add", "note", "according"}; PLAN = {"plan", "expect", "intend", "vow", "set", "aim", "seek", "threaten", "promise"}
def fragments(doc):
    out = []
    for t in doc:
        if t.pos_ != "VERB" or t.lemma_ in SPEECH or t.lemma_ in ("be", "have", "do"): continue
        subj = next((c for c in t.children if c.dep_ in ("nsubj", "nsubjpass")), None); obj = next((c for c in t.children if c.dep_ in ("dobj", "attr", "oprd")), None)
        if obj is None:
            pp = next((c for c in t.children if c.dep_ == "prep"), None); obj = next((c for c in pp.children if c.dep_ == "pobj"), None) if pp else None
        if subj is None and obj is None: continue
        neg = any(c.dep_ == "neg" for c in t.children); aux = [c.lemma_ for c in t.children if c.dep_ == "aux"]
        fact = "denied" if neg else "reported" if (t.dep_ in ("ccomp", "parataxis") and t.head.lemma_ in SPEECH) else "planned" if (any(a in ("will", "would", "shall") for a in aux) or (t.dep_ == "xcomp" and t.head.lemma_ in PLAN)) else "predicted" if any(a in ("could", "may", "might", "can", "should") for a in aux) else "asserted"
        out.append((t.idx, t.idx + len(t.text), fact))
    return out
ov = lambda a, b, c, d: a < d and c < b
# ---------------- J1 / J2 MAVEN-FACT
gold = json.load(open("/workspace/data/anchors/maven_fact/gold_T33b.json")); items = [json.loads(l) for l in open("/workspace/data/anchors/maven_fact/items_T33b.jsonl")]
texts, trig = [], []
for it in items:
    m = re.search(r"«\s*(.+?)\s*»", it["text"]); raw = it["text"]
    if not m: texts.append(raw); trig.append(None); continue
    clean = raw[:m.start()] + m.group(1) + raw[m.end():]; texts.append(clean); trig.append((m.start(), m.start() + len(m.group(1))))
docs = list(nlp.pipe(texts, batch_size=64)); rows = []
for it, doc, tg, tx in zip(items, docs, trig, texts):
    if tg is None: continue
    fr = fragments(doc); cov_frag = [f for f in fr if ov(f[0], f[1], tg[0], tg[1])]; tok = [t for t in doc if ov(t.idx, t.idx + len(t.text), tg[0], tg[1])]; pos = tok[-1].pos_ if tok else "NONE"
    ev = any(ov(a, b, tg[0], tg[1]) for a, b, c, *_ in G.scan(tx, "2026-01-01T00:00:00Z")[0] if c == "event")
    g = gold[it["id"]]; rows.append({"pos": pos, "frag": bool(cov_frag), "verb_token": pos == "VERB", "g1_event": ev, "fact": cov_frag[0][2] if cov_frag else None, "gold": g["factuality"], "yes": g["yes"]})
n = len(rows); res = {"events": n, "trigger_pos": dict(collections.Counter(r["pos"] for r in rows).most_common(4)), "covered_by_g2_fragment": round(sum(r["frag"] for r in rows) / n, 3), "covered_by_g1_event_verb": round(sum(r["g1_event"] for r in rows) / n, 3), "covered_by_either": round(sum(r["frag"] or r["g1_event"] for r in rows) / n, 3), "triggers_that_are_verbs": round(sum(r["verb_token"] for r in rows) / n, 3)}
cv = [r for r in rows if r["frag"]]; mine = lambda r: r["fact"] in ("asserted", "reported"); acc = float(np.mean([mine(r) == r["yes"] for r in cv])) if cv else None; base = float(np.mean([r["yes"] for r in cv])) if cv else None
res["j2"] = {"covered_events": len(cv), "happened_call_accuracy": round(acc, 3), "always_yes_accuracy": round(max(base, 1 - base), 3), "gold_yes_share": round(base, 3), "mine_vs_gold": {f"{k[0]} | {k[1]}": v for k, v in collections.Counter((r["fact"], r["gold"]) for r in cv).most_common(12)},
             "denied_precision_for_not_happened": round(float(np.mean([not r["yes"] for r in cv if r["fact"] == "denied"])), 3) if any(r["fact"] == "denied" for r in cv) else None, "denied_count": sum(1 for r in cv if r["fact"] == "denied")}
# ---------------- J3 CheckThat
gold3 = json.load(open("/workspace/data/anchors/checkthat_subj/gold_T30.json")); it3 = [json.loads(l) for l in open("/workspace/data/anchors/checkthat_subj/items_T30.jsonl")]; docs3 = list(nlp.pipe([i["text"] for i in it3], batch_size=64))
CL = ["quote", "money", "percent", "quantity", "date", "attribution", "negation", "modal", "change", "event", "entity"]; feats = []; y = np.array([int(gold3[i["id"]] == "SUBJ") for i in it3])
for i, d in zip(it3, docs3):
    c = collections.Counter(s[2] for s in G.scan(i["text"], "2026-01-01T00:00:00Z")[0]); f = collections.Counter(x[2] for x in fragments(d)); feats.append([c.get(k, 0) for k in CL] + [f.get(k, 0) for k in ("asserted", "reported", "planned", "predicted", "denied")] + [len(i["text"].split())])
X = np.array(feats, float); names = ["g1_" + c for c in CL] + ["g2_" + k for k in ("asserted", "reported", "planned", "predicted", "denied")] + ["length_words"]
aucs = {nm: round(float(roc_auc_score(y, X[:, j])), 3) for j, nm in enumerate(names) if X[:, j].std() > 0}; cuesum = X[:, names.index("g1_modal")] + X[:, names.index("g1_negation")] + X[:, names.index("g1_attribution")] + X[:, names.index("g1_quote")]
res["j3"] = {"sentences": len(y), "subjective_share": round(float(y.mean()), 3), "auc_per_cue": aucs, "auc_sum_of_modal_negation_attribution_quote": round(float(roc_auc_score(y, cuesum)), 3), "best_cue": max(aucs, key=lambda k: abs(aucs[k] - 0.5)), "best_cue_auc": aucs[max(aucs, key=lambda k: abs(aucs[k] - 0.5))]}
json.dump(res, open("runs/pulse/judge_gates.json", "w"), indent=1); print(json.dumps(res, indent=1))
