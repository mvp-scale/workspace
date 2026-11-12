"""Can triples from spo_chains.py supply event triggers and 'happened' evidence? Outside truth: MAVEN-FACT validation documents (internal scoring only).
    /workspace/models/embed-zs/.venv/bin/python maven_trigger.py [N docs] -> runs/harvest/relations/maven_trigger.json"""
import sys, json, collections, random, warnings; warnings.filterwarnings("ignore")
import spacy
from spacy.tokens import Doc
import spo_chains as S
N = int(sys.argv[1]) if len(sys.argv) > 1 else 250
nlp = spacy.load("en_core_web_sm"); docs = [json.loads(l) for l in open("/workspace/data/anchors/maven_fact/valid.jsonl")]; random.Random(11).shuffle(docs); docs = docs[:N]
def parsed(tokens):
    d = Doc(nlp.vocab, words=tokens)
    for _, proc in nlp.pipeline: d = proc(d)
    return d
rows = []; verb = arg = tot = 0; fact_counts = collections.Counter()
for D in docs:
    sd = [parsed(t) for t in D["tokens"]]
    for si, d in enumerate(sd): pass
    T = S.extract(nlp, sd)
    by_sent = collections.defaultdict(list)
    for t in T: by_sent[t["sent"]].append(t)
    for ev in D["events"]:
        for m in ev["mention"]:
            si = m["sent_id"]; a, b = m["offset"]; tot += 1; fact_counts[m["factuality"]] += 1; ts = by_sent.get(si, [])
            vh = [t for t in ts if a <= t["v_i"] < b]; ah = [t for t in ts if (t["s_i"] is not None and a <= t["s_i"] < b) or (t["o_i"] is not None and a <= t["o_i"] < b)]
            q = sd[si].text.strip().endswith("?")
            pred_yes = None
            if vh or ah:
                use = vh or ah; neg = any(t["neg"] for t in use); mod = any(t["modal"] for t in use); att = any(t["attrib"] or t["said_by"] for t in use)
                pred_yes = not (neg or mod or att or q); variants_ = {"not negated": not neg, "not negated, not modal": not (neg or mod), "not negated, not modal, not a question": not (neg or mod or q), "not negated, not modal, not attributed, not a question (first rule)": not (neg or mod or att or q), "always yes": True}
                notes = {"neg": neg, "modal": mod, "attrib": att}
            else: notes = None
            rows.append({"variants": (variants_ if (vh or ah) else None), "trigger": m["trigger_word"], "factuality": m["factuality"], "verb_hit": bool(vh), "arg_hit": bool(ah), "pred_yes": pred_yes, "notes": notes, "type": ev["type"]})
verb = sum(1 for r in rows if r["verb_hit"]); anyhit = sum(1 for r in rows if r["verb_hit"] or r["arg_hit"])
sc = [r for r in rows if r["pred_yes"] is not None]
def bal(sub):
    tp = sum(1 for r in sub if r["pred_yes"] and r["factuality"] == "CT+"); fn = sum(1 for r in sub if not r["pred_yes"] and r["factuality"] == "CT+"); tn = sum(1 for r in sub if not r["pred_yes"] and r["factuality"] != "CT+"); fp = sum(1 for r in sub if r["pred_yes"] and r["factuality"] != "CT+")
    tpr = tp / max(tp + fn, 1); tnr = tn / max(tn + fp, 1); return {"balanced_accuracy": round((tpr + tnr) / 2, 3), "yes_recall": round(tpr, 3), "no_recall": round(tnr, 3), "tp": tp, "fn": fn, "tn": tn, "fp": fp, "n": len(sub)}
neg_rows = [r for r in sc if r["notes"]["neg"]]; ctm = [r for r in rows if r["factuality"] in ("CT-", "PS-")]
res = {"v": "maven-trigger-v0", "documents": len(docs), "event_mentions": tot, "factuality_counts": dict(fact_counts), "trigger_recall": {"verb_of_a_triple": round(verb / tot, 3), "verb_or_argument_head": round(anyhit / tot, 3), "mentions": tot}, "happened_rule": bal(sc), "base_rate_CT_plus_among_scored": round(sum(1 for r in sc if r["factuality"] == "CT+") / max(len(sc), 1), 3),
       "negation": {"triples_marked_NOT": len(neg_rows), "of_which_gold_CTminus_or_PSminus": sum(1 for r in neg_rows if r["factuality"] in ("CT-", "PS-")), "gold_CTminus_PSminus_mentions": len(ctm), "of_which_flagged_NOT": sum(1 for r in ctm if r["notes"] and r["notes"]["neg"])},
       "by_note": {k: {"scored": sum(1 for r in sc if r["notes"][k]), "gold_CT_plus": sum(1 for r in sc if r["notes"][k] and r["factuality"] == "CT+")} for k in ("neg", "modal", "attrib")}}
def bal_v(name):
    sub = [r for r in rows if r["variants"] is not None]; tp = sum(1 for r in sub if r["variants"][name] and r["factuality"] == "CT+"); fn = sum(1 for r in sub if not r["variants"][name] and r["factuality"] == "CT+"); tn = sum(1 for r in sub if not r["variants"][name] and r["factuality"] != "CT+"); fp = sum(1 for r in sub if r["variants"][name] and r["factuality"] != "CT+")
    return {"balanced_accuracy": round((tp / max(tp + fn, 1) + tn / max(tn + fp, 1)) / 2, 3), "yes_recall": round(tp / max(tp + fn, 1), 3), "no_recall": round(tn / max(tn + fp, 1), 3), "tn": tn, "fp": fp, "fn": fn}
res["rule_variants"] = {n: bal_v(n) for n in ("not negated", "not negated, not modal", "not negated, not modal, not a question", "not negated, not modal, not attributed, not a question (first rule)", "always yes")}
# a balanced view: all non-CT+ events against an equal-size random sample of CT+ events, to compare with the earlier balanced evaluation
rng = random.Random(3); neg_set = [r for r in rows if r["variants"] is not None and r["factuality"] != "CT+"]; pos_set = [r for r in rows if r["variants"] is not None and r["factuality"] == "CT+"]; rng.shuffle(pos_set); bset = neg_set + pos_set[:len(neg_set)]
res["balanced_sample"] = {"events": len(bset), "rules": {n: round(sum(1 for r in bset if r["variants"][n] == (r["factuality"] == "CT+")) / len(bset), 3) for n in res["rule_variants"]}}
json.dump(res, open("runs/harvest/relations/maven_trigger.json", "w"), indent=1); print(json.dumps(res, indent=1))
