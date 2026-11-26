"""slow_consolidate: the consolidation half of the slow clock (plan 1d, owner directive L2901: every part RUNS end to end; weak quality is never a blocker, output is PROVISIONAL). One pass over a finished window, offline, CPU only, no model, no hosted call, no download. Read-only on every input.
    python3 slow_consolidate.py [--trace <trace folder>] [--out <folder>] [--g4 <store.jsonl> ...] [--slow <slow.jsonl>] [--prev <evolved.json>] [--cap-min 60]
Inputs: the window's trace folder (chain.jsonl; default = the newest runs-*/trace under demo/mockups/structure-live), the slow clock's slow.jsonl when it is there (<trace>/slow.jsonl; accepted, not required), and the G4 stores (default runs/g4/store.jsonl + archive, plus <trace>/g4/store.jsonl, <trace parent>/g4/store.jsonl and $LT_V4_G4_DIR/store.jsonl when they exist). Missing inputs are skipped and listed.
Outputs (default folder <trace>/slow_consolidate/), each sealed with a sha256 of its body (no clock inside), manifest = slow_consolidate_run.json:
  consolidated.json   consolidate.py (merge_assertions, independent publishers, IsA) with the three layers of playbook 00 section 8 kept as three separate top-level keys:
                      observations = immutable pointers (journal refs: item id, publisher, day, journal kind, story root, chain seq, slow stages present), no merging; plus per observation `decider_change` {proposed, outcome, provisional} resolved from the slow clock's change proposal (the chain line itself says "not run, pending slow clock" and stays as it is; decider.py is not touched; a proposal that is not validated gives outcome ABSTAIN with the proposal shown; null when the item has no slow record) and `capabilities` [ids] from the chain's capability_list stage
                      edges        = assertions (merged by G4 key, independent publishers `strength`, `fragments_n`, plus a `decay` field per edge: weight 0.5^(age_days / half-life), half-life one 7-day window, PROVISIONAL)
                      concepts     = IPTC nodes the assertions sit on (each assertion edge carries its `iptc` placement and its `capabilities` ids), the capability graph Domain > Area > Capability (concepts.capabilities, PROVISIONAL, nothing promoted), WordNet known-term filter counts, ours: candidates (consolidate.py), the evolve.py RESIDUAL / PROVISIONAL nodes (summary; full file evolved.json)
  evolved.json        evolve.py over the same inputs (residual clusters, gates, versioned labels); nothing above PROVISIONAL
  resource_state.json ledger_split.py ResourceState (V, dV, N, C, U per resource, country, day) from the chain, ticks in ticks.jsonl
  truth.json          resource_truth.py snapshot + event-peak and identity scores against saved public snapshots. Reported, never gating: nothing reads a pass or fail from it to stop or start another stage
  educate_index.json  educate.py: the names educate.answer resolves, plus sample answers (templates, pointers) over consolidated.json + resource_state.json
Every output is PROVISIONAL. The pass has a hard cap (--cap-min, default 60): SIGALRM stops it and the manifest says so; the pid is in the manifest and in <out>/slow_consolidate.pid so the runner can verify it before a stop.
Deterministic: two passes over the same inputs give the same sha256 per file (the manifest holds the wall clock and is not compared)."""
import os, sys, re, json, glob, hashlib, datetime, subprocess, tempfile, signal, time, shutil, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(os.path.dirname(HERE)); LIVE = "/workspace/demo/mockups/structure-live"
PYNP = "/workspace/models/embed-zs/.venv/bin/python"; VERSION = "slow-consolidate-v0"; HALF_LIFE_DAYS = 7; STATUS = "PROVISIONAL"
SLOW_META = {"id", "seq", "ts", "state", "version", "run_id", "prev", "sha", "line", "title", "source", "published"}   # slow.jsonl keys that name the record, not a stage output
def sha_file(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def seal(body):
    import consolidate as C
    b = {k: v for k, v in body.items() if k != "sha256"}; return {**b, "sha256": hashlib.sha256(C.canon(b).encode()).hexdigest()}
def write(p, o):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True); open(p, "w", encoding="utf-8").write(json.dumps(o, sort_keys=True, ensure_ascii=False, indent=1) + "\n"); return {"file": p, "sha256": o.get("sha256") or sha_file(p), "bytes": os.path.getsize(p)}
def newest_trace():
    c = [p for p in glob.glob(LIVE + "/runs-*/trace/chain.jsonl") if os.path.getsize(p)]; return os.path.dirname(max(c, key=os.path.getmtime)) if c else None
# ---------- inputs ----------
def read_chain_meta(path):
    """chain.jsonl -> {item id: {kind, of_seq, seq, caps}} for the observation layer (journal.classify result the chain recorded, capability_list stage)"""
    import consolidate as C; m = {}
    for ln in open(path, encoding="utf-8"):
        if not ln.strip(): continue
        o = json.loads(ln); l = json.loads(o["line"])
        if l.get("state") != "traced": continue
        d = (l.get("journal") or {}).get("dup") or {}; m[l["id"]] = {"kind": d.get("kind"), "of_seq": d.get("of_seq"), "seq": l.get("seq"), "caps": C.chain_caps(l)}
    return m
def read_slow_changes(path):
    """slow.jsonl -> {item id: the slow clock's `change` record} (the last line of an id wins); {} when the file is missing"""
    out = {}
    if not path or not os.path.exists(path): return out
    for ln in open(path, encoding="utf-8"):
        if not ln.strip(): continue
        try: o = json.loads(ln)
        except ValueError: continue
        if isinstance(o.get("line"), str):
            try: o = json.loads(o["line"])
            except ValueError: continue
        if o.get("id") is not None and isinstance(o.get("change"), dict): out[o["id"]] = o["change"]
    return out
def decider_change(c):
    """the slow clock's change record -> the consolidated record's field {proposed, outcome, provisional}. Only a validated proposal can answer (provisionally); otherwise ABSTAIN with the proposal still shown. None when there is no slow record."""
    if not isinstance(c, dict): return None
    p = c.get("proposed"); d = c.get("decider_outcome")   # copy the Lean-checked decider's own outcome; never decide here (Opus gate, wf_c8fee42c-e95)
    o = d if d else ("ANSWER_PROVISIONAL" if (p and c.get("validated") is True) else "ABSTAIN")
    return {"proposed": p, "outcome": o, "harvest": c.get("decider_harvest"), "provisional": True}
def read_slow(path):
    """slow.jsonl (one JSON object per line, optionally wrapped like chain.jsonl as {"line": "<json>"}) -> ({id: sorted stage names with a non-null output}, {stage: count}, lines)"""
    per = collections.defaultdict(set); n = 0
    if not path or not os.path.exists(path): return {}, {}, 0
    for ln in open(path, encoding="utf-8"):
        if not ln.strip(): continue
        try: o = json.loads(ln)
        except ValueError: continue
        if isinstance(o.get("line"), str):
            try: o = json.loads(o["line"])
            except ValueError: continue
        n += 1; i = o.get("id")
        if i is None: continue
        for k, v in o.items():
            if k not in SLOW_META and v not in (None, "", [], {}): per[i].add(k)
    cnt = collections.Counter(k for ks in per.values() for k in ks)
    return {i: sorted(ks) for i, ks in per.items()}, dict(sorted(cnt.items())), n
def find_g4(a, trace):
    multi = [a[i + 1] for i, x in enumerate(a) if x == "--g4"]
    if multi: c = multi
    else:   # defect 6 (knowledge step): the window's OWN store only, the first that exists. The shared runs/g4 store and its archive mix store generations (111 article ids for 60 observations) and are never read by default; pass them with --g4 on purpose.
        own = [os.path.join(trace, "g4", "store.jsonl"), os.path.join(os.path.dirname(trace), "g4", "store.jsonl")]
        if os.environ.get("LT_V4_G4_DIR"): own.append(os.path.join(os.environ["LT_V4_G4_DIR"], "store.jsonl"))
        c = [p for p in own if os.path.exists(p)][:1] or own[:1]
    seen = set(); ok = []; missing = []
    for p in c:
        r = os.path.realpath(p)
        if r in seen: continue
        seen.add(r); (ok if os.path.exists(p) else missing).append(p)
    return ok, missing
def tick_state(trace, work):
    """ledger_split.py --state --persist (needs numpy: the embed-zs venv) -> (state json path, ticks path, stdout line)"""
    st = os.path.join(work, "state.json"); tk = os.path.join(work, "ticks.jsonl")
    r = subprocess.run([PYNP if os.path.exists(PYNP) else sys.executable, os.path.join(HERE, "ledger_split.py"), trace, "--state", st, "--persist", tk, "--state-only"], capture_output=True, text=True, cwd=HERE)
    if r.returncode: raise SystemExit("ledger_split failed: " + r.stderr[-500:])
    return st, tk, r.stdout.strip()
# ---------- the three layers ----------
def iptc_node(x): return x.get("node") if isinstance(x, dict) else x
def decay(e, as_of):
    """PROVISIONAL decay of one assertion: weight 0.5^(age/half-life) from its newest fragment day to the newest day in the inputs. The half-life (one 7-day window) is a guess, not measured."""
    d = {"half_life_days": HALF_LIFE_DAYS, "as_of": as_of, "last_seen": e["days"][-1] if e["days"] else None, "status": STATUS}
    if e["days"] and as_of: age = (datetime.date.fromisoformat(as_of) - datetime.date.fromisoformat(e["days"][-1][:10])).days; d["age_days"] = age; d["weight"] = round(0.5 ** (age / HALF_LIFE_DAYS), 4)
    else: d["age_days"] = None; d["weight"] = None
    return d
def observations(items, meta, ST, slow, changes=None):
    """immutable pointers, one per traced item of the window: nothing merged, nothing scored (decider_change and capabilities are the slow clock's and the chain's own records, copied)"""
    out = []
    for it in sorted({i["id"]: i for i in items}.values(), key=lambda i: (i.get("day") or "", i["id"])):
        m = meta.get(it["id"]) or {}
        out.append({"id": it["id"], "publisher": it["source"], "day": it["day"], "journal": {"kind": m.get("kind"), "of_seq": m.get("of_seq")}, "story": ST.root.get(it["id"], it["id"]), "ref": {"file": os.path.basename(it["file"]), "seq": it.get("seq")}, "slow": slow.get(it["id"], []), "decider_change": decider_change((changes or {}).get(it["id"])), "capabilities": [c["id"] for c in m.get("caps") or []], "status": STATUS})
    return out
def build_layers(items, meta, stores, ticks, slow, iptc, evo, changes=None):
    import consolidate as C
    body = C.consolidate(items, stores, ticks, iptc); ST = C.Stories(list(items), stores)
    days = sorted({d for e in body["edges"] for d in e["days"]} | {i["day"] for i in items if i.get("day")}); as_of = days[-1] if days else None
    for e in body["edges"]: e["decay"] = decay(e, as_of); e["status"] = STATUS
    obs = observations(items, meta, ST, slow, changes); nodes = collections.Counter(n for e in body["edges"] if e["kind"] == "assertion" for n in [iptc_node(e.get("iptc"))] if n)
    for c in body["candidates"]: c.setdefault("status", STATUS)
    body["observations"] = obs
    body["concepts"] = {"status": STATUS, "iptc": {"edges_per_node": dict(sorted(nodes.items())), "nodes_used": len(nodes), "pack": "iptc/medtop.json (read-only)"}, "wordnet": {"known_terms_filtered": body["candidate_counts"].get("known (IPTC or WordNet)", 0), "pack": "wordnet index.noun (read-only)"},
                        "capabilities": body.pop("capabilities"), "ours": body["candidates"], "evolve": {"file": "evolved.json", "sha256": evo["sha256"], "counts": evo["counts"], "nodes": [{k: n[k] for k in ("id", "label", "stage", "status", "gates_failed", "is_a")} for n in evo["nodes"]]}}
    body["layers"] = {"model": "playbook 00 section 8", "observations": {"key": "observations", "n": len(obs), "role": "immutable pointers (journal refs), not merged"}, "assertions": {"key": "edges", "n": len(body["edges"]), "role": "merged by key, independent-publisher count, decay field"},
                      "concepts": {"key": "concepts", "role": "IPTC / WordNet nodes + residual and PROVISIONAL candidates (evolve.py)"}}
    body["decay_rule"] = {"half_life_days": HALF_LIFE_DAYS, "as_of": as_of, "formula": "weight = 0.5 ** (age_days / half_life_days)", "status": STATUS + " (the half-life is a guess; nothing is dropped or ranked by it here)"}
    body["status"] = STATUS; body["version"] = VERSION + "+" + body["version"]
    return body
def educate_index(cons, state_path, seed=None, keep=None):
    import educate as E
    state = json.load(open(state_path)) if state_path and os.path.exists(state_path) else {}; IX = E.Index(cons, state, E.load_seed(seed or E.SEED))
    if keep is not None: keep["IX"] = IX   # the knowledge step answers from the same index
    rc = collections.Counter(e["subj"][9:] for e in cons["edges"] if e["kind"] == "resource"); cc = collections.Counter(e["obj"][8:] for e in cons["edges"] if e["kind"] == "resource")
    ec = collections.Counter(); [ec.update([x]) for e in cons["edges"] if e["kind"] == "assertion" for x in (e["subj"], e["obj"]) if x in IX.labels]
    qs = [r for r, _ in sorted(rc.items(), key=lambda kv: (-kv[1], kv[0]))[:3]] + [c for c, _ in sorted(cc.items(), key=lambda kv: (-kv[1], kv[0]))[:3] if len(c) == 2] + [IX.labels[k] for k, _ in sorted(ec.items(), key=lambda kv: (-kv[1], kv[0]))[:3]] + [n["label"] for n in sorted((cons["concepts"].get("capabilities") or {}).get("nodes", []), key=lambda n: (-n["articles"], n["id"]))[:2]] + ["no such thing in the stores"]
    samples = []
    for q in qs:
        a = E.answer(IX, q); samples.append({"question": q, "resolved": a.get("resolved"), "statements": a["statements"], "abstain": a.get("abstain"), "text": E.as_text(a)[:1500], "refs": sum(len(s["refs"]) for sec in a["sections"].values() for s in sec)})
    return {"version": E.VERSION + "-index", "status": STATUS, "weights": E.WEIGHTS, "consolidated_sha256": cons["sha256"], "state_sha256": state.get("sha256"),
            "resolves": {"resources": IX.res, "countries": IX.countries, "capabilities": sorted(n["label"] for n in IX.caps.values()), "entities_n": len(IX.labels), "entities_top": [IX.labels[k] for k, _ in sorted(ec.items(), key=lambda kv: (-kv[1], kv[0]))[:200]]},
            "edges": {"assertion": sum(e["kind"] == "assertion" for e in cons["edges"]), "resource": sum(e["kind"] == "resource" for e in cons["edges"])}, "samples": samples, "answers_with_statements": sum(1 for s in samples if s["statements"])}
def truth(trace, out_snap):
    """resource_truth snapshot + the two scores. Reported, never gating. Any failure is recorded as unmeasured, not raised."""
    import resource_truth as T
    r = {"status": STATUS, "gating": "never (scores are reported; no stage reads them)", "bars": {"event_peak": T.BAR_EVENT, "identity_conflicts": T.BAR_IDENTITY}}
    snap = T.build_snapshot(trace, out_snap); r["snapshot"] = {"file": os.path.relpath(out_snap, ROOT) if out_snap.startswith(ROOT) else out_snap, "state_sha256": snap["state_sha256"], "chain_sha256": snap["chain_sha256"], "days": len(snap["independent_items_per_day"]), "resources": len(snap["resource_day"])}
    for k, f in (("event_peak", lambda: T.score_events(snap, T.load_events())), ("identity", T.score_identity)):
        try: r[k] = f()
        except Exception as ex: r[k] = {"unmeasured": "%s: %s" % (type(ex).__name__, str(ex)[:300])}
    return r
# ---------- knowledge.json (knowledge step, KNOWLEDGE_SCHEMA.md, owner yes L2936) ----------
SENT_MAX = 400
def load_contradictions(paths):
    """G4 store files -> {canonical key: contradiction edge record}; later lines override earlier ones (the store is append-only). consolidate.load_g4 reads asr/ent/arts only, so the edges section is read here."""
    import consolidate as C; out = {}
    for p in paths:
        if not os.path.exists(p): continue
        for ln in open(p, encoding="utf-8"):
            if not ln.strip(): continue
            for kj, vj in json.loads(ln).get("edges", []):
                v = C._dec(vj)
                if isinstance(v, dict) and v.get("via") == "contradiction": out[C.canon(C._dec(kj))] = v
    return out
def side_day(v, side, ST):
    """a contradiction edge's side ('a' | 'b') -> the earliest known day of its source articles, or None"""
    d = sorted(x for x in (ST.day(s["art"]) for s in (v.get("sources") or {}).get(side, [])) if x); return d[0] if d else None
def contested_pairs(cons, stores, g4p, by_id, ST):
    """the store's contradiction edges -> (kept pairs, dropped counts). Fact-join fix (T158 L2954): both sides map to slot edges; a pair is kept only when a != b (a polarity edge joins two readings of ONE fact: dropped as self_pair), both edges sit under the same anchor (cross_anchor otherwise),
    both sides have a day (unordered otherwise), and for kind status the later report reverses the earlier (dead first, alive later; care -> died is a timeline, dropped as timeline). amount / direction / polarity pairs need the time order only. Each kept pair names earlier and later."""
    import consolidate as C; jmap = (cons.get("join") or {}).get("map") or {}; amap = {}
    for S in stores:
        for aid, r in S["asr"].items():
            if r.get("kind") == "claim":
                e = jmap.get(C.h(r["key"]), C.h(r["key"]))
                if e in by_id: amap.setdefault(aid, e)
    keep = {}; drop = collections.Counter()
    for v in load_contradictions(g4p).values():
        a, b = amap.get(re.sub(r"#[+-]$", "", v["a"])), amap.get(re.sub(r"#[+-]$", "", v["b"])); k = v.get("kind")
        if not (a and b): drop["unmapped"] += 1; continue
        if a == b: drop["self_pair"] += 1; continue
        spk_kind = k in ("outcome", "claim_vs_denial")   # attribution contradictions (T158 round 3): the two sides are different SPEAKERS on one TARGET entity, not one anchor; both sides stay, with their speakers
        if spk_kind:
            sa_, sb_ = {x["entity"] for x in (v.get("speakers") or {}).get("a", []) if x["entity"] != "unresolved"}, {x["entity"] for x in (v.get("speakers") or {}).get("b", []) if x["entity"] != "unresolved"}
            if not (sa_ and sb_) or sa_ & sb_: drop["same_or_unknown_speaker"] += 1; continue
            if not v.get("targets"): drop["no_shared_target"] += 1; continue
        elif by_id[a].get("anchor") != by_id[b].get("anchor"): drop["cross_anchor"] += 1; continue
        da, db = side_day(v, "a", ST), side_day(v, "b", ST)
        if not (da and db): drop["unordered"] += 1; continue
        if spk_kind and abs((datetime.date.fromisoformat(da[:10]) - datetime.date.fromisoformat(db[:10])).days) > 2: drop["outside_2_days"] += 1; continue
        (ea, la), (eb, lb) = ((a, da), (b, db)) if (da, a) <= (db, b) else ((b, db), (a, da))
        if k == "status":
            sa = ((by_id[ea].get("attrs") or {}).get("status")); sb = ((by_id[eb].get("attrs") or {}).get("status"))
            if not (sa == "dead" and sb == "alive" and la < lb): drop["timeline"] += 1; continue
        pr = {"a": min(a, b), "b": max(a, b), "kind": k, "earlier": {"edge": ea, "day": la}, "later": {"edge": eb, "day": lb}, "reversal": k == "status", "note": v.get("note"), "status": STATUS}
        if spk_kind:   # both sides with their speakers, outcome class, quote and the shared target entity; sides are keyed by edge id (a < b)
            sd = lambda side, e_: {"edge": e_, "speakers": [{"entity": x["entity"], "text": x.get("text")} for x in (v.get("speakers") or {}).get(side, [])], "said": (v.get("say") or {}).get(side), "outcome": (v.get("classes") or {}).get(side), "quote": (v.get("quotes") or {}).get(side), "day": side_day(v, side, ST)}
            sides = sorted((sd("a", a), sd("b", b)), key=lambda x: x["edge"])
            pr.update({"targets": list(v.get("targets") or []), "sides": {x["edge"]: x for x in sides}, "label": " vs ".join("%s: %s %s" % ("/".join(y["text"] or y["entity"] for y in x["speakers"]), x["said"], x["outcome"]) for x in sides)})
        kk = (min(a, b), max(a, b), str(k))
        if kk in keep: drop["duplicate_pair"] += 1; continue   # two store edges that join-map onto the same two assertions are one pair
        keep[kk] = pr
    return [keep[t] for t in sorted(keep)], dict(sorted(drop.items()))
def knowledge(cons, meta, items, stores, g4p, ix, IX, trace):
    """consolidated body -> the knowledge.json body (sealed by the caller). Everything is derived from the window's own observations and its own G4 store: no clock, no random value, sorted everywhere, so the same inputs give the same sha256. Counters: new = assertion edges (fact slots, consolidate.py slot_merge) first seen in the window (the store is the window's own, so all of them); reinforced = strength >= 2 independent publishers (consolidate.independence: one source per story root or near-identical sentence, publisher = the fragment's own); contested = contradiction edges of the store mapped to slot edges and kept by contested_pairs (a != b, same anchor, time-ordered, status only when reversed); bridging = capability nodes used by >= 2 Areas."""
    import consolidate as C
    ST = C.Stories(list(items), stores); obs = cons["observations"]; A = [e for e in cons["edges"] if e["kind"] == "assertion"]; by_id = {e["id"]: e for e in A}
    seq_of = {o["id"]: (meta.get(o["id"]) or {}).get("seq") for o in obs}; seqs = sorted({s for s in seq_of.values() if s is not None}); last = seqs[-1] if seqs else 0
    sq = lambda art: seq_of.get(art) if seq_of.get(art) is not None else last   # an article the chain does not number counts at the end, so the growth totals reconcile
    # edges index: every assertion edge, fragments art/pub/sent only
    edges = {}
    for e in A:
        fr = []; seen = set()
        for f in e["fragments"]:
            k = (f["art"], f.get("sent") or "")
            if k in seen: continue
            seen.add(k); fr.append({"art": f["art"], "pub": f.get("pub") or ST.pub(f["art"]), "sent": (f.get("sent") or "")[:SENT_MAX]})
        ind = e.get("independent") or {}
        edges[e["id"]] = {"subject": e["subj"], "predicate": e["pred"], "object": e["obj"] if e["obj"] is not None else e.get("obj_text"), "kind": e["kind"], "strength": e["strength"], "publishers": list(e["publishers"]), "fragments": fr, "anchor": e.get("anchor"),
                          "independent": {"n": ind.get("n", e["strength"]), "collapsed": ind.get("collapsed", 0), "sources": [{"pub": s["pub"], "arts": s["arts"], "fragments": s["fragments"], "copies": s["copies"], "how": s["how"]} for s in ind.get("sources") or []]},
                          "slot": ({"n": e["slot"]["n"], "merged_how": e["slot"]["merged_how"], "min_pair_prob": e["slot"]["min_pair_prob"], "members": e["slot"]["members"]} if e.get("slot") else None)}
    new = sorted(by_id); reinf = sorted(i for i, e in by_id.items() if e["strength"] >= 2)
    contested, cdrop = contested_pairs(cons, stores, g4p, by_id, ST); cev = sorted({x for c in contested for x in (c["a"], c["b"])})
    # capabilities and bridging (areas_n / bridging come from consolidate.py when it writes them; else len(areas))
    caps = []
    for n in (cons["concepts"].get("capabilities") or {}).get("nodes", []):
        ar = n.get("areas") or {}; areas = sorted(ar.keys() if isinstance(ar, dict) else ar); an = n["areas_n"] if n.get("areas_n") is not None else len(areas)
        caps.append({"id": n["id"], "label": n["label"], "areas": areas, "areas_n": an, "bridging": bool(n["bridging"]) if n.get("bridging") is not None else an >= 2})
    bridg = sorted(c["id"] for c in caps if c["bridging"])
    # growth by chain seq: cumulative assertions / reinforced / contested, one row per chain seq of the window
    first = {}; rseq = {}
    for i, e in by_id.items():   # reinforced at the chain seq where the 2nd independent source publisher arrives (consolidate.independence sources, not story roots)
        fs = sorted(((sq(f["art"]), f["art"], f.get("pub")) for f in e["fragments"]), key=lambda t: (t[0], t[1], str(t[2]))); first[i] = fs[0][0] if fs else last; ps = set()
        for s_, p in sorted((min(sq(a) for a in src["arts"]), src["pub"]) for src in (e.get("independent") or {}).get("sources") or []):
            ps.add(p)
            if len(ps) >= 2: rseq[i] = s_; break
    cseq = []
    for c in contested:
        side = lambda eid: min([sq(f["art"]) for f in by_id[eid]["fragments"]] or [last]); cseq.append(max(side(c["a"]), side(c["b"])))
    growth = [{"seq": s, "assertions": sum(1 for x in first.values() if x <= s), "reinforced": sum(1 for x in rseq.values() if x <= s), "contested": sum(1 for x in cseq if x <= s)} for s in seqs]
    nodes = cons["concepts"]["iptc"]["nodes_used"] + len(cons["concepts"]["ours"])
    J = cons.get("join") or {}
    funnel = {"observations": len(obs), "fragments": sum(e["fragments_n"] for e in A), "sources": sum(len((e.get("independent") or {}).get("sources") or []) for e in A), "facts_raw": J.get("facts_raw", len(A)), "assertions": len(A), "reinforced": len(reinf), "contested": len(cev), "capabilities": len(caps), "bridging": len(bridg), "concepts": nodes}
    join = {k: J.get(k) for k in ("mode", "threshold", "facts_raw", "slots", "merge_rate", "merged_slots", "anchors", "anchor_merges", "gated_pairs", "independence")}
    join.update({"contested_kept": len(contested), "contested_dropped": cdrop, "rule": "slots: one fact per anchor cluster (fact_join scorer, hard gates); reinforced: >= 2 independent sources (story root or near-identical sentence = one source); contested: a != b, same anchor, both dated, status only when the later report reverses (dead -> alive)", "status": STATUS})
    body = {"as_of": cons["decay_rule"]["as_of"], "window": trace, "articles": len(obs), "publishers": len({o["publisher"] for o in obs if o.get("publisher")}),
            "counters": {"new": {"n": len(new), "evidence": new}, "reinforced": {"n": len(reinf), "evidence": reinf}, "contested": {"n": len(cev), "evidence": cev}, "bridging": {"n": len(bridg), "evidence": bridg}},
            "edges": edges, "contested": contested, "capabilities": caps, "funnel": funnel, "growth": growth, "join": join}
    return body
def knowledge_final(body, cons, ix, IX, man_note):
    """yield (knowledge_yield.py, answerable from the educate index) and the auto answer (educate.py --auto); each falls back to an explicit null with the reason in man_note, never a silent gap"""
    import knowledge_yield as KY, educate as E
    y = KY.yield_block(cons, contested_n=len(body["contested"])); body["yield"] = {k: y[k] for k in ("pct_reinforced", "contested_per_100", "bridging", "answerable")}
    body["yield"]["bridging"] = body["counters"]["bridging"]["n"]   # the same number as the counter (knowledge_yield counts nodes from consolidated.json; the schema counts the capabilities list written here)
    man_note["yield_basis"] = y["basis"]
    try: body["answer"] = E.knowledge_answer(E.auto_answer(IX), IX)
    except Exception as ex: body["answer"] = None; man_note["answer_unmeasured"] = "%s: %s" % (type(ex).__name__, str(ex)[:300])
    body["provisional"] = True; return body
# ---------- the pass ----------
def main(a):
    opt = lambda f: a[a.index(f) + 1] if f in a else None; t0 = time.time(); cap = float(opt("--cap-min") or 60) * 60
    trace = os.path.abspath(opt("--trace")) if opt("--trace") else newest_trace()
    if not trace or not os.path.exists(os.path.join(trace, "chain.jsonl")): raise SystemExit("no trace folder with chain.jsonl")
    out = os.path.abspath(opt("--out") or os.path.join(trace, "slow_consolidate")); os.makedirs(out, exist_ok=True); man = {"version": VERSION, "status": STATUS, "pid": os.getpid(), "cap_s": cap, "trace": trace, "out": out, "started": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "state": "running"}
    open(os.path.join(out, "slow_consolidate.pid"), "w").write(str(os.getpid()) + "\n"); write(os.path.join(out, "slow_consolidate_run.json"), man)
    def stop(sig, fr):
        man.update({"state": "stopped: hard cap %d s reached" % cap, "ended": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}); write(os.path.join(out, "slow_consolidate_run.json"), man); os._exit(3)
    signal.signal(signal.SIGALRM, stop); signal.alarm(int(cap))
    import consolidate as C, evolve as EV
    chain = os.path.join(trace, "chain.jsonl"); items = C.load_trace(chain); meta = read_chain_meta(chain)
    jr = os.path.join(ROOT, "runs", "journal", "journal.jsonl"); jitems = C.load_journal(jr); items_all = items + jitems
    slow_path = opt("--slow") or os.path.join(trace, "slow.jsonl"); slow, scount, slines = read_slow(slow_path); changes = read_slow_changes(slow_path)
    g4p, g4missing = find_g4(a, trace); stores = [C.load_g4(p) for p in g4p]
    with tempfile.TemporaryDirectory(prefix="slow-consolidate-") as work:
        st, tk, stline = tick_state(trace, work); outs = {}; shutil.copyfile(tk, os.path.join(out, "ticks.jsonl"))
        ticks = C.load_ticks(os.path.join(out, "ticks.jsonl")); state = json.load(open(st))   # ticks come from the kept copy: the lineage names that file, not the temp folder (same sha every pass)
        # resource state (ledger_split ResourceState) -> resource_state.json: the file ledger_split wrote, kept as is (its own sha256)
        shutil.copyfile(st, os.path.join(out, "resource_state.json")); outs["resource_state"] = {"file": os.path.join(out, "resource_state.json"), "sha256": state["sha256"], "bytes": os.path.getsize(os.path.join(out, "resource_state.json")), "counts": state["counts"], "ledger_split": stline[:300]}
        iptc = C.load_iptc()
        prev = json.load(open(opt("--prev"))) if opt("--prev") else None
        evo = EV.seal(EV.evolve(items_all, stores, ticks, iptc, prev)); evo["status"] = STATUS; evo = EV.seal(evo); outs["evolved"] = write(os.path.join(out, "evolved.json"), evo); outs["evolved"]["counts"] = evo["counts"]
        cons = seal(build_layers(items_all, meta, stores, ticks, {**slow}, iptc, evo, changes)); outs["consolidated"] = write(os.path.join(out, "consolidated.json"), cons)
        outs["consolidated"]["counts"] = cons["counts"]; outs["consolidated"]["layers"] = {"observations": len(cons["observations"]), "assertions": len(cons["edges"]), "concepts_ours": len(cons["concepts"]["ours"]), "concepts_evolve_nodes": len(cons["concepts"]["evolve"]["nodes"])}
        # truth: snapshot into the output folder (not the shared /workspace/data/anchors/truth file); scores reported only
        tr = seal(truth(trace, os.path.join(out, "resource_snapshot.json"))); outs["truth"] = write(os.path.join(out, "truth.json"), tr)
        e, i = tr.get("event_peak", {}), tr.get("identity", {}); outs["truth"]["summary"] = {"event_peak": {k: e.get(k) for k in ("checkable", "hits", "hit_rate", "bar", "pass", "unmeasured")}, "identity": {k: i.get(k) for k in ("pairs_resolved", "conflicts", "conflict_rate", "pass", "unmeasured")}}
        keep = {}; ix = seal(educate_index(cons, os.path.join(out, "resource_state.json"), keep=keep)); outs["educate_index"] = write(os.path.join(out, "educate_index.json"), ix); outs["educate_index"]["answers_with_statements"] = ix["answers_with_statements"]
        knote = {}; kn = seal(knowledge_final(knowledge(cons, meta, items_all, stores, g4p, ix, keep["IX"], trace), cons, ix, keep["IX"], knote))
        outs["knowledge"] = write(os.path.join(out, "knowledge.json"), kn); outs["knowledge"]["counters"] = {k: v["n"] for k, v in kn["counters"].items()}; outs["knowledge"]["yield"] = kn["yield"]; outs["knowledge"]["notes"] = knote; outs["knowledge"]["join"] = {k: kn["join"].get(k) for k in ("mode", "facts_raw", "slots", "merge_rate", "contested_kept", "contested_dropped")}
    signal.alarm(0)
    man.update({"state": "done", "ended": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "seconds": round(time.time() - t0, 1), "inputs": {"chain": {"file": chain, "sha256": sha_file(chain), "traced_items": len(items)}, "journal_rows": len(jitems), "slow": {"file": slow_path, "present": os.path.exists(slow_path), "lines": slines, "ids": len(slow), "stage_counts": scount}, "g4_stores": [{"file": p, "sha256": sha_file(p), "bytes": os.path.getsize(p)} for p in g4p], "g4_missing": g4missing},
                "outputs": outs, "layers": cons["layers"], "note": "every output PROVISIONAL; truth scores reported, never gating; the half-life of the decay field is a guess"})
    write(os.path.join(out, "slow_consolidate_run.json"), man)
    print(json.dumps({"out": out, "state": man["state"], "seconds": man["seconds"], "slow_present": man["inputs"]["slow"]["present"], "outputs": {k: {"sha256": v["sha256"], **{x: v[x] for x in ("counts", "layers", "summary", "answers_with_statements", "counters") if x in v}} for k, v in outs.items()}}, sort_keys=True, indent=1))
if __name__ == "__main__": main(sys.argv[1:])
