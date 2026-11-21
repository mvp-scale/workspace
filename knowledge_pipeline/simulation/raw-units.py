"""Raw mode: random real queue articles -> live_trace.Chain.trace (the real per-article pipeline, CPU) -> knowledge units -> merge rule v0 (unmeasured).
Add-only: nothing in live_trace / analyze2 / facts_lib is edited. live_trace's `full` output keeps only counts for triples (no s/v/o), so the facts
are re-read here with the same call the stage makes (FL.facts_for + FL.quarantine on the same text) to get the triple values; sentence spans come from scan_gate.scan.
Loaded by server.py via importlib (kebab-case file name). No hosted calls.
Since T172 (owner yes L2870) the record builder lives in shared importable modules in projects/world-state/, so the page and the live-trace chain (live_trace_v4.py) run the same code: raw_core.py (units, lg typing, claims v0, pronoun resolver, merge rule, build_rec),
fewnerd_typing.py (Few-NERD entity types), claims_units.py + claims_v1.py (claims v1), g4_align.py (G4 alignment, identity, contradictions), journal.py (durable journal). This file keeps what only the page needs: the graph, the chain loader, the pickers, run_one, sample, reset, ticker.
Every name it used to define is still importable from here (check-durable.py, claims-round.py and server.py use them), and RAW_HEADS=1 still switches the saved heads on."""
import os, re, sys, json, time, sqlite3, bisect, threading, collections, unicodedata
os.environ["PYTHONHASHSEED"] = "0"   # live_trace re-execs the process unless this is "0"; set before the import so the server is not re-executed
import live_trace as LT
import journal as JR
import random
import ledger_split as LS
import raw_core as RC
import g4_align as G4   # G4/G5 v1, unmeasured (G4.align below); was loaded from g4-align.py by importlib
globals().update({k: v for k, v in vars(RC).items() if not k.startswith("__") and k not in ("merge_units", "identity", "G4", "JR", "LS")})   # every helper the page used to define (norm, filter_v0, Graph, units_for, lg_ents, apply_lg, claims_v0, triple_spans, claims_v1, apply_fewnerd, sentence_table, heads, extras, ...)
G = RC.Graph(); CH = None; CH_LOCK = threading.Lock()
def chain():
    global CH
    with CH_LOCK:
        if CH is None: CH = LT.Chain()
    return CH
def pick_rows(n, window, exclude):
    db = sqlite3.connect("file:%s?mode=ro" % LT.QUEUE, uri=True); cond = "body is not null and length(body) >= 200 and ready_at is not null"; args = []
    if window == "24h": cond += " and ready_at > ?"; args.append(time.time() - 86400)
    ids = [r[0] for r in db.execute("select id from items where " + cond + " order by random() limit ?", args + [n + len(exclude) + 5])]
    ids = [i for i in ids if i not in exclude][:n]; rows = []
    for i in ids: rows.append(db.execute(LT.select_sql("id = ?"), (i,)).fetchone())
    return rows
def pick_story(n, window, exclude):
    """random story with >= 2 distinct publishers in the window. Story = journal.py key group (title key or 300-char body-prefix key, MIRROR_RULE on), root = first item.
    Items classified republished (same publisher again) are dropped; one article per distinct publisher is kept (earliest), capped at n. Returns (rows, info) or (None, info)."""
    assert JR.MIRROR_RULE is True
    db = sqlite3.connect("file:%s?mode=ro" % LT.QUEUE, uri=True); cond = "body is not null and length(body) >= 100 and ready_at is not null"; args = []
    if window == "24h": cond += " and ready_at > ?"; args.append(time.time() - 86400)
    items = db.execute("select id, source, title, substr(body, 1, 2000), ready_at from items where " + cond + " order by ready_at, id", args).fetchall()
    idx = JR.new_index(); groups = {}; kinds = collections.Counter()
    for seq, (iid, src, ti, bo, ra) in enumerate(items):
        d = JR.classify(idx, JR.story_keys(ti, bo), src, seq); kinds[d["kind"]] += 1; root = d["of_seq"] if d["of_seq"] is not None else seq
        groups.setdefault(root, []).append((seq, iid, src, d["kind"], d["keys"]))
    cand = []
    for root, m in groups.items():
        m = [x for x in m if x[1] not in exclude]; first_by_src = {}
        for x in m:
            if x[3] != "republished" and x[2] not in first_by_src: first_by_src[x[2]] = x
        if len(first_by_src) >= 2: cand.append((root, list(first_by_src.values())))
    info = {"items_in_window": len(items), "kinds": dict(kinds), "stories_ge2_publishers": len(cand), "mirror_rule": True}
    if not cand: return None, info
    root, mem = random.choice(cand); mem = sorted(mem)[:n]; keys = mem[0][4]; ti = items[root][2]
    info.update(story_root_title=ti, story_key={"title": (keys.get("title") or "")[:12] or None, "prefix": (keys.get("prefix") or "")[:12] or None}, independent_publishers=sorted({x[2] for x in mem}), story_publishers_total=len({x[2] for x in groups[root]}))
    return [db.execute(LT.select_sql("id = ?"), (x[1],)).fetchone() for x in mem], info
RC.set_chain(fn=chain)   # raw_core.identity() uses the page's lazy chain when none is passed
def identity(subj, ch=None): return RC.identity(subj, ch or chain())
def merge_units(rec, batch=None): return RC.merge_units(rec, batch, G)

def run_one(ch, row):
    line, text, full = ch.trace(row)
    try:   # read depth from the news reader: full text, or the feed teaser and why (robots.txt, paywall, short extract)
        _db = sqlite3.connect("file:%s?mode=ro" % LT.QUEUE, uri=True); _dr = _db.execute("select depth, reason, words from items where id = ?", (row[0],)).fetchone() or (None, None, None)
    except Exception: _dr = (None, None, None)
    rec0 = {"read": {"depth": _dr[0], "reason": _dr[1], "words": _dr[2]}}
    rec = {**rec0, "text": text, "title_len": len(line["title"]), "id": row[0], "publisher": row[2], "title": line["title"], "url": line["url"], "published": row[6], "state": line["state"], "skip_reason": line.get("skip_reason"), "total_ms": line.get("total_ms")}
    if line["state"] != "traced": rec.update(units=[], codes={}, p={}, decider={}, stages=[]); return rec
    d = JR.classify(G.jidx, line["journal"]["story_key"], line["source"], G.seq); seq = G.seq; G.seq += 1; line["journal"].update(dup={"kind": d["kind"], "of_seq": d["of_seq"]}, publishers=d["publishers"])
    of = G.seqmap.get(d["of_seq"]); G.seqmap[seq] = {"id": row[0], "title": line["title"], "publisher": row[2]}
    rec["story"] = {"kind": d["kind"], "publishers": d["publishers"], "of": of, "seq": seq}
    evs = G.ledger.add(line); rows = G.ledger.rows(); rm = {x["resource"]: x for x in rows}
    rec["world"] = {"counted": evs is not None, "events": [{"resource": r, "name": G.rnames[r][0], "group": G.rnames[r][1], "talk": round(t, 3), "signed": round(sg, 3)} for r, t, sg in (evs or [])],
                    "resources": [{"id": x["resource"], "name": x["name"], "group": x["group"], "items": x["items"], "state": x["state"]} for x in rows], "decision": ((st0 := {s_["name"]: s_ for s_ in line["stages"]}).get("topic_landing") or {}).get("out", {}).get("decision")}
    rec["stage_out"] = {s_["name"]: {"state": s_["state"], "n": s_["n"], "why": s_["why"], "out": s_["out"]} for s_ in line["stages"]}
    return RC.build_rec(ch, line, text, full, rec)   # units, typing, claims, sentences, items, codes: raw_core.build_rec (shared with the live-trace chain)
def sample(n=5, window="any", pick="articles", aid=None):
    n = max(1, min(int(n), 20)); window = "24h" if window == "24h" else "any"; pick = "story" if pick == "story" else "articles"; ch = chain(); t0 = time.time(); sinfo = None
    with G.lock:
        if pick == "story":
            rows, sinfo = pick_story(n, window, G.pulled)
            if rows is None: return {"articles": [], "tally": {"pick": "story", "window": window, "error": "no story with >= 2 distinct publishers in this window", **sinfo}, "merge_rule": MERGE_LABEL}
        elif aid:   # one named article (?id=), so a specific story can be replayed
            db = sqlite3.connect("file:%s?mode=ro" % LT.QUEUE, uri=True); r0 = db.execute(LT.select_sql("id = ?"), (aid,)).fetchone(); rows = [r0] if r0 else []
        else: rows = pick_rows(n, window, G.pulled)
        batch = {r[0] for r in rows}; recs = []
        for row in rows:
            G.pulled.add(row[0]); r = run_one(ch, row); merge_units(r, batch)
            try: G4.align(r, G, ch)   # G4/G5 v1 hook
            except Exception as e: r["g4_error"] = repr(e)
            recs.append(r)
        G.batches += 1
    tr = [r for r in recs if r["state"] == "traced"]; us = [u for r in tr for u in r["units"]]; kept = [u for u in us if u["filter"]["kept"]]; keyed = [u for u in kept if u["merge"]["result"] != "NO KEY"]
    hits = [u for u in keyed if u["merge"]["result"] == "+EVIDENCE"]; hs = [u for u in hits if u["merge"]["scope"] == "same story"]; ho = len(hits) - len(hs); nm = len(tr) or 1
    ncap = lambda r: sum(1 for u in r["units"] if u["type"] == "capability"); rate = lambda a: round(a / len(keyed), 3) if keyed else None
    tally = {"pick": pick, "articles": len(recs), "traced": len(tr), "skipped": len(recs) - len(tr), "units": len(us), "units_per_article": round(len(us) / nm, 2), "share_articles_ge1_unit": round(sum(1 for r in tr if r["units"]) / nm, 3),
             "filter": FILTER_LABEL, "units_kept": len(kept), "units_dropped": len(us) - len(kept), "drop_reasons": dict(collections.Counter(u["filter"]["reason"] for u in us if not u["filter"]["kept"])), "units_addressed": sum(1 for r in tr if r["p"].get("topic_decision") != "ABSTAIN" for u in r["units"] if u["filter"]["kept"]), "units_merged": sum(1 for r in tr if r["p"].get("topic_decision") != "ABSTAIN" for u in r["units"] if u["filter"]["kept"] and u["merge"]["result"] in ("NEW", "+EVIDENCE")), "units_with_span": sum(1 for u in us if u["spans"]), "units_keyed": len(keyed), "units_no_key": len(kept) - len(keyed), "merge_hits": len(hits), "merge_hit_rate": rate(len(hits)), "hits_same_story": len(hs), "merge_hit_rate_same_story": rate(len(hs)), "hits_other": ho, "merge_hit_rate_other": rate(ho),
             "share_zero_capability_candidates": round(sum(1 for r in tr if ncap(r) == 0) / nm, 3), "graph_nodes": len(G.nodes), "graph_articles": len(G.pulled), "by_type": dict(collections.Counter(u["type"] for u in us)), "merge_rule": MERGE_LABEL, "window": window, "seconds": round(time.time() - t0, 1)}
    if sinfo: tally.update(story=sinfo)
    return {"articles": recs, "tally": tally, "merge_rule": MERGE_LABEL}
def reset():
    with G.lock:
        G.reset()
        for p in (_node_log(), (_node_log() or "").replace("raw-units-nodes", "store")):   # a reset starts from nothing: the durable logs are moved aside (not deleted) so a restart does not bring the graph back
            if p and os.path.exists(p): os.makedirs(os.path.dirname(p) + "/archive", exist_ok=True); os.replace(p, os.path.dirname(p) + "/archive/%s-%d" % (os.path.basename(p), int(time.time())))
    return {"graph_nodes": 0, "graph_articles": 0}
def ticker(hours=24, limit=40):
    """the queue as it arrives: newest headlines (title, publisher, ready_at) and the count per hour over the last `hours`. Read-only."""
    hours = max(1, min(int(hours), 72)); now = time.time(); db = sqlite3.connect("file:%s?mode=ro" % LT.QUEUE, uri=True)
    items = [{"title": t, "source": s, "ready_at": r} for t, s, r in db.execute("select title, source, ready_at from items where ready_at is not null and ready_at > ? and title is not null order by ready_at desc limit ?", (now - hours * 3600, limit))]
    per = [0] * hours
    for (r,) in db.execute("select ready_at from items where ready_at is not null and ready_at > ?", (now - hours * 3600,)):
        per[min(hours - 1, int((now - r) // 3600))] += 1
    return {"items": items, "per_hour": per[::-1], "total": sum(per), "hours": hours, "now": now}
