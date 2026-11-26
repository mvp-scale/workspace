#!/usr/bin/env python3
"""export-bundle.py: write an entity-flow bundle (schema: entity-flow.schema.json) for one staged area by calling the running bench (read-only GETs).
    python3 export-bundle.py <area key: c1|mix|...> [--base http://127.0.0.1:18770] [--out sample-<area>.json] [--max-bytes 2000000]
Endpoints used: /api/raw/areas, /api/raw/knowledge, /api/raw/concepts, /api/raw/sample (one call per article, id=), /api/raw/deep (one call per non-resource concept).
Also reads projects/world-state/publisher-owners.json (static file). No hosted calls, no writes except --out. Stdlib only."""
import sys, json, re, time, statistics, collections, urllib.request, urllib.parse, os
HERE = os.path.dirname(os.path.abspath(__file__))
OWNERS = os.path.join(HERE, "../../../projects/world-state/publisher-owners.json")
SCHEMA_VERSION = "entity-flow-0.1"
MAX_FRAG_PER_ART = 25      # cap on fragments (claim records) per article
MAX_TL_PER_CONCEPT = 60    # cap on timeline lines per concept

def get(base, path, **q):
    url = base + path + ("?" + urllib.parse.urlencode(q) if q else "")
    return json.load(urllib.request.urlopen(url, timeout=600))

def pct(n, d): return None if not d else round(100.0 * n / d, 1)
def filled(rows, f):
    ok = [r for r in rows if r.get(f) not in (None, "", [], {})]
    return {"n": len(ok), "of": len(rows), "pct": pct(len(ok), len(rows))}

STAGES = [
 # id, name, clock, status, module, inputs, outputs, ms_source
 ("s0", "source_intake", "fast", "built", "newsreader queue (queue.sqlite items) read by live_trace.select_sql / ALLOW columns id,url,source,title,teaser,body,published,ready_at", ["feed item"], ["publisher", "article"]),
 ("s1", "article_read_and_windows", "fast", "built", "live_trace.Chain.trace stages windows (+ queue read depth full|teaser and reason)", ["article"], ["article (read depth, windows)"]),
 ("s2", "sentences_and_spans", "fast", "built", "scan_gate.scan, live_trace stages scan_dates, span_rules, facts (facts_lib)", ["article"], ["sentence", "span", "stated fact (date, amount, name)"]),
 ("s3", "fragments_claims", "fast+slow", "partial", "fast: raw_core.claims_v0 + fewnerd_typing (ner_fewnerd); slow: claims_units.extract_claims -> claims_v1.extract (deferred in the chain, run by slow_clock.py)", ["sentence"], ["fragment (claim: subject, predicate, object, spans)"]),
 ("s4", "classification", "fast", "partial", "live_trace stages area_function, domain_rollup, topic_landing, condition, place_student, capability_list, decider; function/factuality heads run in slow_clock (attach_heads); novelty, time not attached", ["article", "sentence"], ["article labels (area, story type, IPTC node, place, condition)", "decider verdict"]),
 ("s5", "identity_entities", "slow(per article)", "partial", "g4_align.align (Store, identity, aliases, IPTC placement), raw_core.merge_units, run by slow_clock.py", ["fragment"], ["entity (G4 identity)", "assertion (G4)", "G4 edge"]),
 ("s6", "contradiction_edges", "slow(per article)", "partial", "g4_align.contradict_edges, g4_align.report_contradictions (window 7 days / report window)", ["assertion (G4)"], ["contradiction edge"]),
 ("s7", "journal_and_story_roots", "fast", "built", "journal.story_keys / classify (first|copy|republished), journal.Durable append, consolidate.story_roots", ["article"], ["story root", "article.story_kind"]),
 ("s8", "fact_join_independence", "slow(batch)", "built (PROVISIONAL)", "consolidate.syndication_groups, independence (publisher-owners.json), anchors, slot_merge with fact_join.Scorer (e5-small-v2, threshold 0.53)", ["assertion (G4)", "fragment evidence"], ["fact (edge, slots)", "independent owner count"]),
 ("s9", "consolidation_slow_clock", "slow(batch)", "built (PROVISIONAL)", "consolidate.consolidate, slow_consolidate.knowledge (counters new/reinforced/contested/bridging, growth, yield, capabilities, contested_pairs, answer via educate.auto_answer)", ["fact"], ["fact flags", "contest", "capability", "pulse inputs (counters, growth, yield)", "answer statements"]),
 ("s10", "concepts_links_triage", "slow(batch)", "partial (PROVISIONAL v0)", "concepts_v0.build (cards, typed links, states, certainty words, per-article triage replay)", ["fact", "contest", "entity (G4)"], ["entity/concept (card)", "link (typed)", "change (triage verdict)"]),
 ("s11", "deep_timeline", "slow(on demand)", "partial (PROVISIONAL)", "concepts_v0 deep pass, GET /api/raw/deep (time box 120 s; own data and local caches only)", ["entity/concept"], ["timeline item", "open question", "history (other windows)"]),
 ("s12", "outputs_macro_pulse", "slow(batch)", "missing/partial", "playbook section 10 contract (what it is / what is changing / why / known / uncertain / adjacent). Code: knowledge.answer statements, counters, growth, yield. No Pulse(a,t)=(V,dV,N,C,U) tuple function exists in slow_consolidate / concepts_v0 / server", ["fact", "entity", "link", "contest", "change"], ["answer statement", "pulse inputs"]),
]

def main():
    a = sys.argv[1:]
    if not a or a[0].startswith("-"): print(__doc__); return 2
    area = a[0]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    base = opt("--base", "http://127.0.0.1:18770"); out = opt("--out", os.path.join(HERE, "sample-%s.json" % area)); maxb = int(opt("--max-bytes", "2000000"))
    src = "area:" + area; t0 = time.time(); calls = collections.Counter(); dropped = {}
    areas = {x["key"]: x for x in get(base, "/api/raw/areas")}; calls["areas"] += 1
    if area not in areas: print("unknown area", area, list(areas)); return 2
    K = get(base, "/api/raw/knowledge", src=src); C = get(base, "/api/raw/concepts", src=src); calls["knowledge"] += 1; calls["concepts"] += 1
    kn = K["knowledge"]; arts = K["articles"]
    # ---- per-article records (sample, id=) ----
    recs = {}; ms_stage = collections.defaultdict(list); ms_slow = collections.defaultdict(list); tot = []
    for aid in sorted(arts, key=lambda i: arts[i]["seq"]):
        r = get(base, "/api/raw/sample", src=src, id=aid, n=1)["articles"][0]; calls["sample"] += 1; recs[aid] = r
        for s in r.get("stages", []):
            if s["state"] in ("ran", "abstain", "empty") and s.get("ms") is not None: ms_stage[s["name"]].append(s["ms"])
        for k2, v in ((r.get("slow") or {}).get("ms") or {}).items(): ms_slow[k2].append(v)
        if r.get("total_ms") is not None: tot.append(r["total_ms"])
    # ---- publishers ----
    own = {p["publisher"]: p for p in json.load(open(OWNERS))["publishers"]}
    pubn = collections.Counter(v["publisher"] for v in arts.values())
    publishers = [{"id": p, "owner": (own.get(p) or {}).get("owner", p), "owner_listed": p in own, "cite": (own.get(p) or {}).get("cite"), "articles": n} for p, n in sorted(pubn.items())]
    # ---- articles + fragments ----
    articles = []; fragments = []; sent_index = collections.defaultdict(list)
    for aid, v in sorted(arts.items(), key=lambda x: x[1]["seq"]):
        r = recs[aid]; rd = r.get("read") or {}; st = r.get("story") or {}; p = r.get("p") or {}; cd = r.get("codes") or {}; dec = r.get("decider") or {}
        resev = [{"resource": e["resource"], "group": e.get("group"), "talk": e.get("talk"), "signed": e.get("signed")} for e in ((r.get("world") or {}).get("events") or [])]
        articles.append({"id": aid, "seq": v["seq"], "publisher": v["publisher"], "title": v["title"], "url": v.get("url"), "published": v.get("published"),
            "read_depth": rd.get("depth"), "read_reason": rd.get("reason"), "words": rd.get("words"),
            "story_kind": st.get("kind"), "story_root": st.get("of"), "story_publishers": st.get("publishers"),
            "area_top": [{"name": n, "p": q} for n, q in (p.get("area_top") or [])[:3]], "story_type_top": [{"name": n, "p": q} for n, q in (p.get("story_type_top") or [])[:3]],
            "iptc_l1": cd.get("l1_label"), "iptc_node": cd.get("node"), "iptc_node_label": cd.get("node_label"),
            "place_top": [{"name": n, "p": q} for n, q in (p.get("place_student_top") or [])[:2]], "condition_present": p.get("condition_present"),
            "decider": {k2: (x or {}).get("outcome") for k2, x in dec.items()}, "resource_events": resev,
            "sentences": len(r.get("sentences") or []), "claims_n": len(r.get("claims") or []), "claims_v1_n": ((r.get("slow") or {}).get("claims") or {}).get("claims"),
            "ms_fast": r.get("total_ms"), "ms_slow": ((r.get("slow") or {}).get("ms") or {}).get("total"), "gaps": r.get("gaps")})
        sents = {s["i"]: s for s in (r.get("sentences") or [])}
        cl = r.get("claims") or []; dropped_n = max(0, len(cl) - MAX_FRAG_PER_ART)
        cl = sorted(cl, key=lambda c: (c.get("type") != "triple", c.get("sentence") or 0))[:MAX_FRAG_PER_ART]
        if dropped_n: dropped.setdefault("fragments", 0); dropped["fragments"] += dropped_n
        for i, c in enumerate(cl):
            s = sents.get(c.get("sentence")) or {}; sp = {x["role"]: [x["s"], x["e"]] for x in (c.get("spans") or []) if "role" in x}
            f = {"id": "%s:%d" % (aid[:12], i), "article_id": aid, "sentence_index": c.get("sentence"), "sentence": c.get("sent_text"), "type": c.get("type"),
                 "subject": c.get("subject"), "predicate": c.get("predicate"), "object": c.get("value"), "missing": c.get("missing"), "spans": sp, "fate": c.get("fate"),
                 "factuality": s.get("factuality"), "negated": s.get("negated"), "modal": s.get("modal"), "resolved_from": c.get("resolved_from")}
            fragments.append(f); sent_index[aid].append(f)
    # ---- facts ----
    new = set((kn["counters"]["new"] or {}).get("evidence") or []); rein = set((kn["counters"]["reinforced"] or {}).get("evidence") or []); cont = set()
    for c in kn.get("contested") or []: cont.update([c["a"], c["b"]])
    day = lambda aid: ((arts.get(aid) or {}).get("published") or "")[:10] or None
    facts = []; matched = 0; evn = 0
    for eid, e in kn["edges"].items():
        ev = []
        for fr in e["fragments"]:
            fid = None; txt = re.sub(r"\s+", " ", fr["sent"]).strip()[:60]
            for g in sent_index.get(fr["art"], []):
                if g["sentence"] and txt and txt[:40] in re.sub(r"\s+", " ", g["sentence"]): fid = g["id"]; break
            evn += 1; matched += fid is not None
            ev.append({"article_id": fr["art"], "publisher": fr["pub"], "sentence": fr["sent"], "day": day(fr["art"]), "fragment_id": fid})
        days = sorted({x["day"] for x in ev if x["day"]}); ind = e["independent"]
        facts.append({"id": eid, "subject": e["subject"], "predicate": e["predicate"], "object": e["object"], "kind": e["kind"], "anchor": e["anchor"],
            "strength": e["strength"], "independent_owners": ind["n"], "collapsed_copies": ind["collapsed"],
            "independent_sources": [{"owner_or_publisher": s["pub"], "articles": s["arts"], "fragments": s["fragments"], "copies": s["copies"], "how": s["how"]} for s in ind["sources"]],
            "publishers": e["publishers"], "evidence": ev, "first_day": days[0] if days else None, "last_day": days[-1] if days else None, "days": days,
            "slot": e["slot"], "is_new": eid in new, "is_reinforced": eid in rein, "in_contest": eid in cont})
    # ---- entities, links, changes ----
    g4 = {}
    for r in recs.values():
        for x in (r.get("g4") or {}).get("entities", []): g4[x["id"]] = x
    capsrc = {c["id"]: c for c in kn.get("capabilities") or []}
    entities = []; res_def = {}
    for c in C["concepts"]:
        card = c.get("card") or {}; g = g4.get(c["id"]) or {}
        entities.append({"id": c["id"], "label": c["label"], "kind": c["kind"], "depth": c["depth"], "state": c["state"], "certainty": c["certainty"], "certainty_word": c.get("certainty_word"),
            "direction": c.get("direction"), "owners": c["owners"], "facts": c["facts"], "first_seq": c["first_seq"], "last_seq": c["last_seq"], "in_graph_from_seq": c.get("in_graph_from_seq"),
            "what_it_is": card.get("what_it_is"), "slot_fill": c.get("slot_fill"), "edge_ids": c["edge_ids"], "conflicts": c.get("conflicts") or [],
            "did": card.get("did") or [], "drivers": card.get("drivers") or [], "resources": card.get("resources") or [], "related": card.get("related") or [],
            "allies": card.get("allies") or [], "opponents": card.get("opponents") or [], "disputed": card.get("disputed") or [], "gaps": card.get("gaps") or [],
            "g4": ({"type": g.get("type"), "canon": g.get("canon"), "aliases": g.get("aliases"), "iptc_path": (g.get("iptc") or {}).get("path"), "iptc_how": (g.get("iptc") or {}).get("how"), "geo": g.get("geo")} if g else None)})
    for cid, cp in capsrc.items():
        entities.append({"id": cid, "label": cp["label"], "kind": "capability", "areas": cp["areas"], "bridging": cp["bridging"]})
    links = [{"a": l["a"], "b": l["b"], "rel": l["rel"], "direction": l.get("direction"), "certainty": l["certainty"], "owners": l["owners"], "n": l["n"], "edge_ids": l["edge_ids"], "note": l.get("note")} for l in C["links"]]
    changes = []
    for t in C["triage"]:
        cc = [{"concept": k2, "kind": v2.get("kind"), "text": v2.get("text"), "publisher": v2.get("pub"), "edge_ids": v2.get("edge_ids")} for k2, v2 in (t.get("concept_changes") or {}).items()]
        changes.append({"seq": t["seq"], "article_id": t["art"], "publisher": t.get("pub"), "verdict": t["verdict"], "concept": t.get("concept"), "detail": t.get("detail"), "counts": t.get("counts"),
            "facts": t.get("facts"), "unmapped": t.get("unmapped"), "graph_before": t.get("graph_before"), "change_kind": t.get("change_kind"), "change_text": t.get("change_text"),
            "change_concept": t.get("change_concept"), "change_edge_ids": t.get("change_edge_ids"), "touched": t.get("touched"), "concept_changes": cc, "edge_ids": t.get("edge_ids")})
    # ---- contests ----
    contests = []
    for i, c in enumerate(kn.get("contested") or []):
        sides = [{"edge_id": k2, "day": v2.get("day"), "said": v2.get("said"), "outcome": v2.get("outcome"), "quote": v2.get("quote"), "speakers": v2.get("speakers")} for k2, v2 in (c.get("sides") or {}).items()]
        contests.append({"id": "c%d" % i, "a": c["a"], "b": c["b"], "kind": c["kind"], "label": c.get("label"), "status": c.get("status"), "reversal": c.get("reversal"), "note": c.get("note"),
            "earlier": c.get("earlier"), "later": c.get("later"), "targets": c.get("targets"), "sides": sides})
    # ---- timeline (deep) ----
    timeline = []; deep_ms = []; deep_state = collections.Counter()
    for c in C["concepts"]:
        if c["kind"] == "resource": continue
        d = get(base, "/api/raw/deep", src=src, concept=c["id"]); calls["deep"] += 1; deep_ms.append(d.get("ms") or 0); deep_state["cut" if d.get("time_boxed_cut") else "ok"] += 1
        tl = d.get("timeline") or []
        if len(tl) > MAX_TL_PER_CONCEPT: dropped["timeline"] = dropped.get("timeline", 0) + len(tl) - MAX_TL_PER_CONCEPT; tl = tl[:MAX_TL_PER_CONCEPT]
        for j, x in enumerate(tl): timeline.append({"concept": c["id"], "seq": x.get("seq"), "day": x.get("day"), "text": x.get("text"), "edge_id": x.get("edge_id"), "publishers": x.get("pubs")})
    # ---- meta ----
    q = lambda xs, p: None if not xs else round(sorted(xs)[min(len(xs) - 1, int(p * len(xs)))], 1)
    timing = {"fast_chain_ms_per_article": {"p50": q(tot, .5), "p90": q(tot, .9), "n": len(tot)},
              "fast_stage_ms_p50": {k2: q(v2, .5) for k2, v2 in ms_stage.items()},
              "slow_clock_ms_p50": {k2: q(v2, .5) for k2, v2 in ms_slow.items()},
              "deep_ms": {"p50": q(deep_ms, .5), "max": max(deep_ms) if deep_ms else None, "states": dict(deep_state)}}
    stages = []
    for sid, name, clock, status, mod, i_, o_ in STAGES:
        stages.append({"id": sid, "name": name, "clock": clock, "status": status, "module": mod, "input_types": i_, "output_types": o_})
    cov = {"articles": {f: filled(articles, f) for f in ["read_depth", "story_kind", "iptc_node", "place_top", "area_top", "story_type_top"]},
           "fragments": {f: filled(fragments, f) for f in ["subject", "predicate", "object", "spans", "factuality"]},
           "facts": {"evidence_to_fragment_link": {"n": matched, "of": evn, "pct": pct(matched, evn)}, "with_slot": filled(facts, "slot"), "independent_owners_ge2": {"n": sum(f["independent_owners"] >= 2 for f in facts), "of": len(facts), "pct": pct(sum(f["independent_owners"] >= 2 for f in facts), len(facts))}, "in_contest": {"n": len(cont), "of": len(facts), "pct": pct(len(cont), len(facts))}, "dated": filled(facts, "first_day")},
           "entities": {f: filled([e for e in entities if e["kind"] != "capability"], f) for f in ["what_it_is", "did", "drivers", "related", "resources", "opponents", "disputed", "g4", "certainty_word"]},
           "links": {"owners_ge2": {"n": sum(l["owners"] >= 2 for l in links), "of": len(links), "pct": pct(sum(l["owners"] >= 2 for l in links), len(links))}},
           "timeline": {"concepts_with_timeline": {"n": len({t["concept"] for t in timeline}), "of": sum(1 for c in C["concepts"] if c["kind"] != "resource"), "pct": pct(len({t["concept"] for t in timeline}), sum(1 for c in C["concepts"] if c["kind"] != "resource"))}},
           "changes": {"verdicts": dict(collections.Counter(c["verdict"] for c in changes)), "articles_covered": {"n": len(changes), "of": len(articles)}}}
    ent_kinds = dict(collections.Counter(e["kind"] for e in entities))
    meta = {"schema_version": SCHEMA_VERSION, "area": area, "area_label": areas[area]["label"], "as_of": kn["as_of"], "provisional": True, "source": base, "endpoint_calls": dict(calls),
        "generated_seconds": round(time.time() - t0, 1), "dropped": dropped, "caps": {"fragments_per_article": MAX_FRAG_PER_ART, "timeline_per_concept": MAX_TL_PER_CONCEPT},
        "counts": {"publishers": len(publishers), "articles": len(articles), "fragments": len(fragments), "facts": len(facts), "entities": len(entities), "entity_kinds": ent_kinds, "links": len(links), "contests": len(contests), "timeline": len(timeline), "changes": len(changes)},
        "funnel": kn["funnel"], "yield": kn["yield"], "counters": {k2: v2["n"] for k2, v2 in kn["counters"].items()}, "growth": kn["growth"], "join": {k2: kn["join"][k2] for k2 in ("mode", "threshold", "status", "merge_rate", "merged_slots", "slots", "facts_raw")},
        "answer": kn.get("answer"), "timing": timing, "coverage": cov, "rules": C.get("rules"), "sha256_knowledge": kn.get("sha256")}
    bundle = {"meta": meta, "stages": stages, "publishers": publishers, "articles": articles, "fragments": fragments, "facts": facts, "entities": entities, "links": links, "contests": contests, "timeline": timeline, "changes": changes}
    s = json.dumps(bundle, ensure_ascii=False)
    if len(s.encode()) > maxb:   # shrink: drop fragments' sentence text first, then evidence sentences beyond 2 per fact; log it
        for f in bundle["fragments"]: f["sentence"] = (f["sentence"] or "")[:160]
        for f in bundle["facts"]:
            if len(f["evidence"]) > 3: dropped["evidence_rows"] = dropped.get("evidence_rows", 0) + len(f["evidence"]) - 3; f["evidence"] = f["evidence"][:3]
        meta["dropped"] = dropped; s = json.dumps(bundle, ensure_ascii=False)
    open(out, "w").write(s)
    print(out, len(s.encode()), "bytes", meta["counts"], "dropped", dropped)
    return 0
if __name__ == "__main__": sys.exit(main())
