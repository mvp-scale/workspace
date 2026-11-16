"""pool_build: first label pool from the BitMob toolchain (playbook 15 rules 2 and 5). Reuses extract.py (init, work) and adds span-level facts, scan spots.
Strength: amount/date passing all four Validator checks = proved; other tool output = rule (failed-check amounts/dates stay rule with their status). Never weak here, never topic/story type.
    /workspace/models/embed-zs/.venv/bin/python -u pool_build.py [N] [MAXSEC]  -> runs/harvest/pool_v1/pool.jsonl, summary.json"""
import json, sys, time, collections
from multiprocessing import Pool
import extract as E
V = "pool-v1"; OUT = "runs/harvest/pool_v1/"
# Provenance default (T150 P1d), a PROPOSAL awaiting owner confirmation: Observed = cut from a document span (scan, span rules, fact extractors, binder, name finder); Resolved = place-linker alias result; External = imported from a list or ontology (place-linker non-alias hits); Inferred = rule-derived (factuality tagger, change lexicon); Candidate = model output or uncertain (default for an unknown tool).
PROV = {"fact-finder": "Observed", "name-finder": "Observed", "scan_gate": "Observed", "span-rules": "Observed", "factuality-tagger": "Inferred", "change-lexicon": "Inferred", "place-linker": "External"}
def it(tool, ver, kind, s, e, text, strength, **kw):
    # add-only keys: provenance, status ('unchecked' where no Validator check applies; fact items pass their own; 'quarantined' is set by held_back below)
    d = {"tool": tool, "version": ver, "kind": kind, "span": [s, e], "text": text[s:e], "strength": strength, "provenance": PROV.get(tool, "Candidate"), "status": "unchecked"}; d.update(kw); return d
def held_back(items, text):
    """Quarantine: items whose stored text no longer equals text[s:e] of the source text are split off, so no later layer reads them. Returns (kept, held); an unflagged list passes through unchanged."""
    from facts_lib import quarantine
    return quarantine(items, text)
def work(r):
    rec = E.work(r); text = rec["text"]; date = rec["source"]["date"]; anchor = date + "T00:00:00Z" if date else None; items = []
    try: facts = E.FL.facts_for(text, anchor)[0]
    except Exception: facts = []
    facts, held_f = held_back(facts, text)  # it() rebuilds item text from the span, so the check that can fail is on the extractor's own stored text, before it() (T150)
    places, held_p = held_back(rec["places"]["items"], text)
    for f in facts:
        c = f["checks"]; ok = all(c.values()) and f["kind"] in ("amount", "date")
        items.append(it("fact-finder", E.V, f["kind"], f["s"], f["e"], text, "proved" if ok else "rule", value=f["value"] if f["kind"] != "triple" else f["value"], checks=c, status=("stated" if all(c.values()) else "not_validated")))
    try: sp, _ = E.G.scan(text, anchor)
    except Exception: sp = []
    for x in sp[:80]: items.append(it("scan_gate", "scan-v0", x[2], x[0], x[1], text, "rule", value=(x[3] if len(x) > 3 else None)))
    for k, s, e, v in rec["more_spans"]["items"]: items.append(it("span-rules", "span-rules-v0", k, s, e, text, "rule", value=v))
    for s, e, tag in rec["function"]["sentences"]: items.append(it("factuality-tagger", "factuality-rules-v1", "factuality:" + tag, s, e, text, "rule"))
    for p in places: items.append(it("place-linker", "geonames+alias-v0", "place", p["span"][0], p["span"][1], text, "rule", country=p["country"], how=p["how"], provenance="Resolved" if p["how"] == "alias" else "External"))
    for c in rec["conditions"]["items"]: items.append(it("change-lexicon", "change-lexicon-v0", "condition:" + c["condition"], c["span"][0], c["span"][1], text, "rule", direction=c["direction"], thing=c["thing"], negated=c["negated"]))
    for x in items:
        if x["kind"] == "name": x["tool"] = "name-finder"
    items, held = held_back(items, text); held = held_f + held_p + held
    return {"v": V, "item_id": "cc:" + (r["url"] or ""), "row": r["row"], "publisher": r["domain"], "date": date, "text_chars": len(text), "items": items, "ms": rec["ms"], "quarantined": held}
if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000; MAXS = float(sys.argv[2]) if len(sys.argv) > 2 else 2400; t0 = time.time()
    ids = {json.loads(l)["item_id"] for l in open("runs/label_store/labels.jsonl")}
    R = (json.loads(l) for _, l in zip(range(N), open("runs/harvest/sample.jsonl"))); n = ov = anyp = 0; cnt = collections.Counter(); art = collections.Counter()
    with Pool(18, initializer=E.init) as P, open(OUT + "pool.jsonl", "w") as w:
        for rec in P.imap(work, R, chunksize=8):
            w.write(json.dumps(rec) + "\n"); n += 1; ov += rec["item_id"] in ids; hp = False
            for x in rec["items"]:
                k = (x["tool"], x["strength"]); cnt[k] += 1; hp |= x["strength"] == "proved"
            anyp += hp
            if n % 500 == 0: print(n, round(time.time() - t0), flush=True)
            if time.time() - t0 > MAXS: print("time budget reached", flush=True); P.terminate(); break
    wall = time.time() - t0
    s = {"v": V, "articles_done": n, "wall_seconds": round(wall, 1), "seconds_per_article": round(wall / n, 4), "articles_per_minute": round(n / wall * 60, 1),
         "items_per_article_by_tool_strength": {f"{t}|{s_}": round(c / n, 3) for (t, s_), c in sorted(cnt.items())}, "share_articles_with_proved": round(anyp / n, 4),
         "overlap_with_label_store": {"articles_with_cc_id_in_labels": ov, "share": round(ov / n, 4), "note": "ids matched as cc:<url>; nq:/nr:/q: ids in the store cannot be mapped to sample rows"},
         "strength_rule": "proved = amount/date with all four Validator checks; all else rule; name finder and place linker never proved"}
    json.dump(s, open(OUT + "summary.json", "w"), indent=1); print(json.dumps(s))
