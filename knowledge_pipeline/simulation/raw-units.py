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

def run_one(ch, row, g=None):
    g = g or G   # g: the window graph when the record comes from a pipeline window (trace loader below); default the page's live graph
    line, text, full = ch.trace(row)
    try:   # read depth from the news reader: full text, or the feed teaser and why (robots.txt, paywall, short extract)
        _db = sqlite3.connect("file:%s?mode=ro" % LT.QUEUE, uri=True); _dr = _db.execute("select depth, reason, words from items where id = ?", (row[0],)).fetchone() or (None, None, None)
    except Exception: _dr = (None, None, None)
    rec0 = {"read": {"depth": _dr[0], "reason": _dr[1], "words": _dr[2]}}
    rec = {**rec0, "text": text, "title_len": len(line["title"]), "id": row[0], "publisher": row[2], "title": line["title"], "url": line["url"], "published": row[6], "state": line["state"], "skip_reason": line.get("skip_reason"), "total_ms": line.get("total_ms")}
    if line["state"] != "traced": rec.update(units=[], codes={}, p={}, decider={}, stages=[]); return rec
    d = JR.classify(g.jidx, line["journal"]["story_key"], line["source"], g.seq); seq = g.seq; g.seq += 1; line["journal"].update(dup={"kind": d["kind"], "of_seq": d["of_seq"]}, publishers=d["publishers"])
    of = g.seqmap.get(d["of_seq"]); g.seqmap[seq] = {"id": row[0], "title": line["title"], "publisher": row[2]}
    rec["story"] = {"kind": d["kind"], "publishers": d["publishers"], "of": of, "seq": seq}
    evs = g.ledger.add(line); rows = g.ledger.rows(); rm = {x["resource"]: x for x in rows}
    rec["world"] = {"counted": evs is not None, "events": [{"resource": r, "name": g.rnames[r][0], "group": g.rnames[r][1], "talk": round(t, 3), "signed": round(sg, 3)} for r, t, sg in (evs or [])],
                    "resources": [{"id": x["resource"], "name": x["name"], "group": x["group"], "items": x["items"], "state": x["state"]} for x in rows], "decision": ((st0 := {s_["name"]: s_ for s_ in line["stages"]}).get("topic_landing") or {}).get("out", {}).get("decision")}
    rec["stage_out"] = {s_["name"]: {"state": s_["state"], "n": s_["n"], "why": s_["why"], "out": s_["out"]} for s_ in line["stages"]}
    return RC.build_rec(ch, line, text, full, rec)   # units, typing, claims, sentences, items, codes: raw_core.build_rec (shared with the live-trace chain)
def sample(n=5, window="any", pick="articles", aid=None, src=None):
    if src and src != "queue": return sample_trace(n, pick, aid, src)   # pipeline window (trace loader): src="window" (newest) or "trace:<window dir>"; anything else = the live queue as before
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
# ---- pipeline window loader (flow fix, defect 2, T158): the page reads what chain_windows.py wrote, not only the live queue ----
# sample(src="window") = the newest runs-e2e-* (else runs-*) dir with traced > 0 under demo/mockups/structure-live; sample(src="trace:<window dir>") = that window (the dir holding trace/, or the trace dir itself).
# Per article the record is built by the SAME code as a queue article: run_one(...) with the stored chain line, the text from a/<seq>.json and its stages_full as the chain trace (no model re-run for the stages), raw_core.build_rec, merge rule, G4.align,
# against a graph of its own (never the live queue graph; nothing durable is written). New fields: slow (the 7 slow-clock parts of slow.jsonl), decider_change {proposed, outcome, provisional}, consolidated {counts, observation, assertions, capabilities}, window {name, traced, ...}.
STRUCT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "demo", "mockups", "structure-live"))
WIN = {}; WIN_LOCK = threading.Lock()
def _inner(x):
    """one chain.jsonl row -> the chain line dict (rows are {seq, prev, sha, line: <json string>}; older runs keep the line itself)"""
    ln = x.get("line") if isinstance(x, dict) else None
    if isinstance(ln, str):
        try: ln = json.loads(ln)
        except Exception: ln = None
    if not isinstance(ln, dict): ln = x if isinstance(x, dict) and "stages" in x else None
    return ln
def _jsonl(p):
    out = []
    if os.path.exists(p):
        for l in open(p, encoding="utf-8"):
            if l.strip():
                try: out.append(json.loads(l))
                except Exception: pass
    return out
def _jload(p, default=None):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return default
def _has_traced(tdir):
    p = os.path.join(tdir, "chain.jsonl")
    if not os.path.exists(p): return False
    for l in open(p, encoding="utf-8"):
        try: ln = _inner(json.loads(l))
        except Exception: continue
        if ln and ln.get("state") == "traced": return True
    return False
def latest_window():
    """newest window dir with traced > 0: runs-e2e-* first, then any runs-*; None when there is none"""
    if not os.path.isdir(STRUCT): return None
    for pre in ("runs-e2e-", "runs-"):
        ds = [d for d in os.listdir(STRUCT) if d.startswith(pre) and os.path.isdir(os.path.join(STRUCT, d, "trace"))]
        ds.sort(key=lambda d: -os.path.getmtime(os.path.join(STRUCT, d, "window.json") if os.path.exists(os.path.join(STRUCT, d, "window.json")) else os.path.join(STRUCT, d)))
        for d in ds:
            wj = os.path.join(STRUCT, d, "window.json")   # only a completed window ('done', or legacy without window.json); same rule as check-alignment.py
            try: st = json.load(open(wj)).get("state") if os.path.exists(wj) else None
            except Exception: st = "unreadable"
            if st not in (None, "done"): continue
            if _has_traced(os.path.join(STRUCT, d, "trace")): return os.path.join(STRUCT, d)
    return None
def resolve_window(src):
    """src 'window' or 'trace:<path>' -> (window dir, trace dir); raises ValueError with the reason"""
    if src == "window": wd = latest_window()
    elif src.startswith("trace:"):
        wd = src[6:]; wd = wd if os.path.isabs(wd) else os.path.join(STRUCT, wd); wd = os.path.abspath(wd)
    else: raise ValueError("unknown src: " + src)
    if not wd: raise ValueError("no pipeline window with traced > 0 under " + STRUCT)
    if os.path.exists(os.path.join(wd, "chain.jsonl")): td = wd; wd = os.path.dirname(wd) if os.path.basename(wd) == "trace" else wd
    else: td = os.path.join(wd, "trace")
    if not os.path.exists(os.path.join(td, "chain.jsonl")): raise ValueError("no chain.jsonl in " + wd)
    return wd, td
class _Replay:
    """stands in for the chain's trace(): hands back the stored (line, text, full); every other attribute (SG, pack, ...) is the real chain's, which build_rec / merge / G4.align need"""
    def __init__(self, ch, stored): self._ch = ch; self._st = stored
    def trace(self, row): return self._st
    def __getattr__(self, k): return getattr(self._ch, k)
def _cap_ids(full):
    cf = (full or {}).get("capability_list") or {}; out = []
    for tier in ("recurring", "candidate"):
        for pair in cf.get(tier) or []: out.append(" + ".join(str(x) for x in pair) if isinstance(pair, (list, tuple)) else str(pair))
    return out
def _load_window(wd, td):
    k = os.path.abspath(td); w = WIN.get(k)
    if w is not None: return w
    lines = [ln for ln in (_inner(x) for x in _jsonl(os.path.join(td, "chain.jsonl"))) if ln]
    traced = [ln for ln in lines if ln.get("state") == "traced"]
    slow = {r.get("id"): r for r in _jsonl(os.path.join(td, "slow.jsonl"))}
    cons = _jload(os.path.join(td, "slow_consolidate", "consolidated.json"), {}) or {}
    obs = {}
    for o in cons.get("observations") or []:
        if o.get("id") is not None: obs[o["id"]] = o
    ids = {ln.get("id") for ln in lines}; by_art = collections.defaultdict(list)
    for e in cons.get("edges") or []:
        for f in e.get("fragments") or []:
            if f.get("art") in ids: by_art[f["art"]].append(e)
    wj = _jload(os.path.join(wd, "window.json"), {}) or {}; sr = _jload(os.path.join(td, "slow_run.json"), {}) or {}
    iptc = ((cons.get("concepts") or {}).get("iptc") or {}); ours = (cons.get("concepts") or {}).get("ours") or []
    cap_total = sum(len(o.get("capabilities") or []) for o in obs.values())
    tgt = sr.get("target_ids")
    w = {"dir": wd, "trace": td, "name": os.path.basename(wd.rstrip("/")), "lines": lines, "traced": traced, "slow": slow, "cons": cons, "obs": obs, "by_art": by_art, "pos": 0, "g": None, "served": set(),
         "info": {"name": os.path.basename(wd.rstrip("/")), "window_state": wj.get("state"), "chain_lines": len(lines), "traced": len(traced), "slow_lines": len(slow), "slow_target": tgt, "slow_state": sr.get("state"),
                  "slow_partial": bool(tgt is not None and tgt < len(traced)), "consolidated": bool(cons),
                  "counts": {"observations": len(obs), "assertions": (cons.get("counts") or {}).get("assertion_edges"), "assertions_all_edges": ((cons.get("layers") or {}).get("assertions") or {}).get("n"),
                             "concepts": (iptc.get("nodes_used") or 0) + len(ours), "concepts_iptc_nodes_used": iptc.get("nodes_used"), "concepts_ours": len(ours), "candidates": (cons.get("counts") or {}).get("candidates"), "capabilities": cap_total}}}
    WIN[k] = w; return w
def window_info(src="window"):
    """cheap: what the page header needs (no model load). {exists: False, why} when there is no window"""
    try: wd, td = resolve_window(src)
    except ValueError as e: return {"exists": False, "why": str(e)}
    return {"exists": True, **_load_window(wd, td)["info"]}
def _decider_change(w, ln, slow_row):
    o = w["obs"].get(ln.get("id")) or {}; dc = o.get("decider_change")
    if isinstance(dc, dict): return {**dc, "source": "consolidated observation"}
    ch_ = ((ln.get("decider") or {}).get("change") or {}); sc = (slow_row or {}).get("change") or {}
    if sc: return {"proposed": sc.get("proposed"), "outcome": sc.get("chain_outcome") or ch_.get("outcome"), "provisional": sc.get("provisional") in (True, "PROVISIONAL") or bool(ch_.get("provisional")), "state": sc.get("state"), "validated": sc.get("validated"), "why": sc.get("why"), "source": "slow.jsonl (the consolidated record has no decider_change for this article)"}
    return {"proposed": None, "outcome": ch_.get("outcome"), "provisional": bool(ch_.get("provisional")), "why": ch_.get("reason"), "source": "chain line (no slow output for this article)"}
def _edge_row(e):
    return {"id": e.get("id"), "key": e.get("key"), "kind": e.get("kind"), "pred": e.get("pred"), "subj": e.get("subj"), "obj": e.get("obj"), "publishers": e.get("publishers"), "fragments_n": e.get("fragments_n"), "weight": (e.get("decay") or {}).get("weight"), "status": e.get("status")}
def _enrich(w, rec, ln, full):
    iid = ln.get("id"); sr = w["slow"].get(iid); o = w["obs"].get(iid)
    caps = (o or {}).get("capabilities"); caps = list(caps) if isinstance(caps, list) else _cap_ids(full)
    edges = w["by_art"].get(iid, [])
    rec["window"] = {"name": w["name"], "dir": w["dir"], "seq": ln.get("seq"), "traced": w["info"]["traced"], "chain_lines": w["info"]["chain_lines"], "slow_lines": w["info"]["slow_lines"], "slow_partial": w["info"]["slow_partial"]}
    keys = ("claims", "direction", "change", "function_p", "factuality_p", "identity_g4", "contradictions")
    rec["slow"] = ({k: sr[k] for k in keys + ("ms",) if k in sr} if sr else None)
    rec["slow_state"] = ({k: (sr[k].get("state") if isinstance(sr.get(k), dict) else None) for k in keys} if sr else None)
    rec["decider_change"] = _decider_change(w, ln, sr)
    rec["consolidated"] = {"counts": w["info"]["counts"], "observation": ({k: o[k] for k in o if k != "slow"} | {"slow_parts": o.get("slow")}) if o else None, "assertions": [_edge_row(e) for e in edges[:40]], "assertions_n": len(edges), "capabilities": caps, "status": (w["cons"] or {}).get("status")}
def sample_trace(n=5, pick="articles", aid=None, src="window"):
    n = max(1, min(int(n), 20)); wd, td = resolve_window(src); w = _load_window(wd, td); ch = chain(); t0 = time.time()
    with WIN_LOCK:
        if w["g"] is None: w["g"] = RC.Graph(dur_dir=None, durable=False)   # its own graph: not the live queue's, nothing written to disk
        g = w["g"]; rest = [ln for ln in w["traced"] if ln.get("id") not in w["served"]]
        if aid: sel = [ln for ln in w["traced"] if ln.get("id") == aid][:1]
        elif pick == "story":
            grp = collections.defaultdict(list)
            for ln in rest:
                sk = ((ln.get("journal") or {}).get("story_key") or {}); grp[sk.get("title") or sk.get("prefix") or ln.get("id")].append(ln)
            cand = [m for m in grp.values() if len({x.get("source") for x in m}) >= 2]
            if not cand: return {"articles": [], "tally": {"pick": "story", "window": w["name"], "error": "no story with >= 2 distinct publishers in this window (%d traced)" % len(w["traced"])}, "merge_rule": MERGE_LABEL, "source": window_info(src)}
            m = cand[0]; seen = set(); sel = []
            for x in m:
                if x.get("source") not in seen: seen.add(x.get("source")); sel.append(x)
            sel = sel[:n]
        else: sel = rest[:n]
        if not sel: return {"articles": [], "tally": {"pick": pick, "window": w["name"], "error": ("no article %s in window %s" % (aid, w["name"])) if aid else "end of window %s: %d of %d traced articles read; press reset to read it again" % (w["name"], len(w["served"]), len(w["traced"]))}, "merge_rule": MERGE_LABEL, "source": window_info(src)}
        batch = {ln["id"] for ln in sel}; recs = []
        for ln in sel:
            a = _jload(os.path.join(td, "a", "%s.json" % ln.get("seq")))
            if not a:
                recs.append({"id": ln.get("id"), "title": ln.get("title"), "publisher": ln.get("source"), "published": ln.get("published"), "state": "skipped", "skip_reason": "no a/%s.json in %s (the window stored no text for this article)" % (ln.get("seq"), w["name"]), "units": [], "codes": {}, "p": {}, "decider": ln.get("decider") or {}, "stages": []}); continue
            line = a.get("article_line") or ln; text = a.get("text") or ""; full = a.get("stages_full") or {}
            row = (line["id"], line.get("url"), line.get("source"), line.get("title"), None, None, line.get("published"), line.get("ready_at"))
            r = run_one(_Replay(ch, (line, text, full)), row, g)
            rd = (line.get("input") or {}).get("read")
            if rd: r["read"] = {"depth": rd.get("depth"), "reason": rd.get("reason"), "words": rd.get("words")}
            if r.get("state") == "traced":
                RC.merge_units(r, batch, g)
                try: G4.align(r, g, ch)
                except Exception as e: r["g4_error"] = repr(e)
            _enrich(w, r, ln, full); w["served"].add(ln["id"]); recs.append(r)
        g.batches += 1
    tr = [r for r in recs if r["state"] == "traced"]; us = [u for r in tr for u in r["units"]]
    tally = {"pick": pick, "articles": len(recs), "traced": len(tr), "skipped": len(recs) - len(tr), "units": len(us), "units_kept": sum(1 for u in us if u["filter"]["kept"]), "merge_rule": MERGE_LABEL, "window": w["name"], "src": "pipeline window", "seconds": round(time.time() - t0, 1), "read_so_far": len(w["served"]), "window_traced": len(w["traced"])}
    return {"articles": recs, "tally": tally, "merge_rule": MERGE_LABEL, "source": window_info(src)}
def reset_trace():
    """a reset starts every loaded window over: cursor to the first article, a fresh graph (the window files are not touched)"""
    with WIN_LOCK:
        for w in WIN.values(): w["pos"] = 0; w["g"] = None; w["served"] = set()
def reset():
    reset_trace()
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
