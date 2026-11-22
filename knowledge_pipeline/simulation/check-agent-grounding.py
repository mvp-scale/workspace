"""check-agent-grounding (T158 who-did-it fix round 1): automatic, no human labels, no model. For each reinforced edge (strength >= 2) of a staged area knowledge.json, and for each supporting fragment sentence, test that the stored subject's surface form (or an alias the identity store holds for it) appears in the sentence's SUBJECT SPAN: the text before the verb (the claim's pred_surface), back to the clause start ('. ', '# ', ';', ' that ', ' said ', ' says ', ' say ', ' told '). A subject that is only a modifier of the object, or an earlier-sentence name a pronoun was resolved to, is NOT grounded.
Edge fragment <-> store evidence: the area's g4/store.jsonl asr 'key' (subj | pred | obj) with the same article id; the verb surface is the evidence attrs.pred_surface. Fragments whose verb surface is not in the sentence text are 'unmeasurable' and left out of the rate.
Wrong-agent statements = auto-answer statements (knowledge.json answer.statements) whose refs include an edge with an ungrounded fragment.
Run: python check-agent-grounding.py [--json]   Import: score(area_key) -> dict"""
import json, re, sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent; SL = HERE.parent.parent / "demo" / "mockups" / "structure-live"
CLAUSE = re.compile(r"(?:\. |# |; |\* | said | says | say | told | and said )")   # ' that ' is not a cut: 'a hat that had fallen' keeps its head noun
PRON = re.compile(r"(?<!\w)(he|she|it|they|who|which)\s+(?:\w+\s+){0,2}$")
def dd(x): return dict(x["__d"]) if isinstance(x, dict) and "__d" in x else x
def aliases(store_dir, ids):
    al = {i: set() for i in ids}
    for l in open(store_dir / "store.jsonl", encoding="utf-8"):
        r = json.loads(l)
        for k, v in r.get("alias", []):
            if v in al: al[v].add(str(k["__t"][1]).lower())
    for i in ids: al[i].add(i.split(":", 1)[-1].replace("-", " ").lower())
    return al
def evidence(store_dir):
    ev = {}
    for l in open(store_dir / "store.jsonl", encoding="utf-8"):
        r = json.loads(l)
        for a, d in r.get("asr", []):
            d = dd(d)
            for e in d.get("evid", []):
                e = dd(e); at = dd(e.get("attrs") or {}); ev.setdefault((d["subj"], d["pred"], d["obj"]), []).append((e["art"], e["sent"], at.get("verb_text") or at.get("pred_surface")))
    return ev
def grounded(sent, verb, names):
    low = sent.lower(); v = (verb or "").lower(); i = low.find(v) if v else -1
    if i < 0: return None
    pre = low[:i]; cut = [m.end() for m in CLAUSE.finditer(pre)]; span = pre[cut[-1]:] if cut else pre
    if any(re.search(r"(?<!\w)%s(?:e?s)?(?!\w)" % re.escape(n), span) for n in names if n): return True
    return "pronoun" if PRON.search(span) else False
def score(key):
    base = SL / ("area-" + key) / "trace"; k = json.load(open(base / "slow_consolidate" / "knowledge.json")); sd = base / "g4"
    edges = {i: e for i, e in k["edges"].items() if (e.get("strength") or 0) >= 2}; al = aliases(sd, {e["subject"] for e in edges.values()}); ev = evidence(sd)
    n = ok = unm = pron = 0; bad = []; bad_edges = set()
    for i, e in edges.items():
        for art, sent, vb in ev.get((e["subject"], e["predicate"], e["object"]), []):
            g = grounded(sent, vb, al[e["subject"]])
            if g is None: unm += 1; continue
            n += 1; ok += (g is True); pron += (g == "pronoun")
            if g is not True: bad_edges.add(i); bad.append({"edge": i, "key": "%s | %s | %s" % (e["subject"], e["predicate"], e["object"]), "sent": sent[:160]})
    wrong = [s["text"][:100] for s in (k.get("answer") or {}).get("statements", []) if set(s.get("refs") or []) & bad_edges]
    return {"area": key, "reinforced_edges": len(edges), "fragments_tested": n, "grounded": ok, "unmeasurable": unm, "pronoun_subject": pron, "rate_ex_pronoun": round(ok / (n - pron), 4) if n - pron else None, "rate": round(ok / n, 4) if n else None, "ungrounded_edges": len(bad_edges), "wrong_agent_statements": len(wrong), "wrong_statements": wrong, "ungrounded": bad}
if __name__ == "__main__":
    out = {a: score(a) for a in ("c1", "mix")}
    if "--json" in sys.argv: print(json.dumps(out, indent=1))
    else:
        for a, r in out.items(): print("%s: grounded %s/%s = %s (pronoun-subject fragments %s, rate without them %s; unmeasurable %s), ungrounded edges %s, wrong-agent statements %s" % (a, r["grounded"], r["fragments_tested"], r["rate"], r["pronoun_subject"], r["rate_ex_pronoun"], r["unmeasurable"], r["ungrounded_edges"], r["wrong_agent_statements"])); [print("   BAD", b["key"], "|", b["sent"][:110]) for b in r["ungrounded"][:12]]
