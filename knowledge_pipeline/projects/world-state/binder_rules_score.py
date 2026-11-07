"""Score binder_rules.py against spaCy (stated_facts.facts_for) on the 200 golden articles. Run from projects/world-state:
   /workspace/models/embed-zs/.venv/bin/python binder_rules_score.py   -> runs/pulse/binder_rules.json"""
import sys, re, json, time, statistics, collections, random
sys.path.insert(0, "."); import binder_rules as B
exec(open("stated_facts.py").read().split("# ---------------- 4102 stories")[0], globals())
arts = [json.loads(l) for l in open("runs/pulse/golden/articles.jsonl")]
M = {k: collections.Counter() for k in ("amount", "date")}; noun = collections.Counter(); rows = []; t_rule = []; t_spacy = []
for i, a in enumerate(arts):
    text = re.sub(r"\s+", " ", a["title"] + ". " + a["body"])[:12000]
    t0 = time.perf_counter(); f, _, _ = facts_for(text, a["date"] + "T00:00:00Z"); t_spacy.append((time.perf_counter() - t0) * 1000)
    f = [x for x in f if x["kind"] in ("amount", "date")]
    t0 = time.perf_counter(); res = [B.bind(text, x["s"], x["e"], x["kind"], None) for x in f]; t_rule.append((time.perf_counter() - t0) * 1000)   # sentence split inside each call (worst case); see batch timing below
    sents = None
    t0 = time.perf_counter(); sents = B.split_sentences(text); res = [B.bind(text, x["s"], x["e"], x["kind"], sents) for x in f]; t_rule[-1] = (time.perf_counter() - t0) * 1000
    for x, b in zip(f, res):
        st = B.status(b["bound"], b["one_sentence"]); M[x["kind"]][(x["status"], st)] += 1
        if x["kind"] == "amount" and x["checks"]["bound"] and b["bound"] and x["noun"] and b["noun"]: noun[x["noun"].lower() == b["noun"].lower()] += 1
        if x["status"] != st: rows.append((i, x["kind"], x["status"], st, text[max(0, x["s"] - 70):x["s"]] + "[[" + x["text"] + "]]" + text[x["e"]:x["e"] + 40], x["noun"], x["verb"], b["noun"], b["verb"]))
out = {}
for k, c in M.items():
    tot = sum(c.values()); out[f"{k}_facts"] = tot; out[f"{k}_agree"] = round(sum(v for (a, b), v in c.items() if a == b) / tot, 4)
    out[f"{k}_false_stated"] = round(c[("unbound", "stated")] / tot, 4); out[f"{k}_baseline_all_stated_agree"] = round(sum(v for (a, b), v in c.items() if a == "stated") / tot, 4)
    out[f"{k}_spacy_unbound"] = sum(v for (a, b), v in c.items() if a == "unbound"); out[f"{k}_unbound_caught"] = c[("unbound", "unbound")]
    out[f"{k}_matrix_spacy_rule"] = {f"{a}->{b}": v for (a, b), v in sorted(c.items())}
n_ = sum(noun.values()); out["amount_noun_pairs_both_bound"] = n_; out["amount_noun_agree"] = round(noun[True] / n_, 4)
out["rule_ms_median"] = round(statistics.median(t_rule), 3); out["rule_ms_p95"] = round(sorted(t_rule)[int(0.95 * len(t_rule))], 3)
out["spacy_ms_median"] = round(statistics.median(t_spacy), 2); out["spacy_ms_p95"] = round(sorted(t_spacy)[int(0.95 * len(t_spacy))], 2)
out["articles"] = len(arts); random.seed(7)
out["note"] = "agreement with spaCy status, not truth; spaCy reference is noisy; always-stated baseline shown. Dev tuned on articles 0-99, frozen, checked on 100-199 (amount agree 0.848, date 0.881 on that half)."
out["disagreements"] = [dict(zip(("article", "kind", "spacy", "rule", "context", "spacy_noun", "spacy_verb", "rule_noun", "rule_verb"), r)) for r in random.sample(rows, 10)]
json.dump(out, open("runs/pulse/binder_rules.json", "w"), indent=1, ensure_ascii=False)
print({k: v for k, v in out.items() if k != "disagreements"})
for d in out["disagreements"]: print(d)
