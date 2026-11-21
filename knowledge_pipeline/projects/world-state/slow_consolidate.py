"""slow_consolidate: the consolidation half of the slow clock (plan 1d, owner directive L2901: every part RUNS end to end; weak quality is never a blocker, output is PROVISIONAL). One pass over a finished window, offline, CPU only, no model, no hosted call, no download. Read-only on every input.
    python3 slow_consolidate.py [--trace <trace folder>] [--out <folder>] [--g4 <store.jsonl> ...] [--slow <slow.jsonl>] [--prev <evolved.json>] [--cap-min 60]
Inputs: the window's trace folder (chain.jsonl; default = the newest runs-*/trace under demo/mockups/structure-live), the slow clock's slow.jsonl when it is there (<trace>/slow.jsonl; accepted, not required), and the G4 stores (default runs/g4/store.jsonl + archive, plus <trace>/g4/store.jsonl, <trace parent>/g4/store.jsonl and $LT_V4_G4_DIR/store.jsonl when they exist). Missing inputs are skipped and listed.
Outputs (default folder <trace>/slow_consolidate/), each sealed with a sha256 of its body (no clock inside), manifest = slow_consolidate_run.json:
  consolidated.json   consolidate.py (merge_assertions, independent publishers, IsA) with the three layers of playbook 00 section 8 kept as three separate top-level keys:
                      observations = immutable pointers (journal refs: item id, publisher, day, journal kind, story root, chain seq, slow stages present), no merging
                      edges        = assertions (merged by G4 key, independent publishers `strength`, `fragments_n`, plus a `decay` field per edge: weight 0.5^(age_days / half-life), half-life one 7-day window, PROVISIONAL)
                      concepts     = IPTC nodes the assertions sit on, WordNet known-term filter counts, ours: candidates (consolidate.py), the evolve.py RESIDUAL / PROVISIONAL nodes (summary; full file evolved.json)
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
    """chain.jsonl -> {item id: {kind, of_seq, seq}} for the observation layer (journal.classify result the chain recorded)"""
    m = {}
    for ln in open(path, encoding="utf-8"):
        if not ln.strip(): continue
        o = json.loads(ln); l = json.loads(o["line"])
        if l.get("state") != "traced": continue
        d = (l.get("journal") or {}).get("dup") or {}; m[l["id"]] = {"kind": d.get("kind"), "of_seq": d.get("of_seq"), "seq": l.get("seq")}
    return m
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
    else:
        c = [os.path.join(ROOT, "runs", "g4", "store.jsonl")] + sorted(glob.glob(os.path.join(ROOT, "runs", "g4", "archive", "store.jsonl-*")))
        c += [os.path.join(trace, "g4", "store.jsonl"), os.path.join(os.path.dirname(trace), "g4", "store.jsonl")]
        if os.environ.get("LT_V4_G4_DIR"): c.append(os.path.join(os.environ["LT_V4_G4_DIR"], "store.jsonl"))
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
def observations(items, meta, ST, slow):
    """immutable pointers, one per traced item of the window: nothing merged, nothing scored"""
    out = []
    for it in sorted({i["id"]: i for i in items}.values(), key=lambda i: (i.get("day") or "", i["id"])):
        m = meta.get(it["id"]) or {}
        out.append({"id": it["id"], "publisher": it["source"], "day": it["day"], "journal": {"kind": m.get("kind"), "of_seq": m.get("of_seq")}, "story": ST.root.get(it["id"], it["id"]), "ref": {"file": os.path.basename(it["file"]), "seq": it.get("seq")}, "slow": slow.get(it["id"], []), "status": STATUS})
    return out
def build_layers(items, meta, stores, ticks, slow, iptc, evo):
    import consolidate as C
    body = C.consolidate(items, stores, ticks, iptc); ST = C.Stories(list(items), stores)
    days = sorted({d for e in body["edges"] for d in e["days"]} | {i["day"] for i in items if i.get("day")}); as_of = days[-1] if days else None
    for e in body["edges"]: e["decay"] = decay(e, as_of); e["status"] = STATUS
    obs = observations(items, meta, ST, slow); nodes = collections.Counter(n for e in body["edges"] if e["kind"] == "assertion" for n in [iptc_node(e.get("iptc"))] if n)
    for c in body["candidates"]: c.setdefault("status", STATUS)
    body["observations"] = obs
    body["concepts"] = {"status": STATUS, "iptc": {"edges_per_node": dict(sorted(nodes.items())), "nodes_used": len(nodes), "pack": "iptc/medtop.json (read-only)"}, "wordnet": {"known_terms_filtered": body["candidate_counts"].get("known (IPTC or WordNet)", 0), "pack": "wordnet index.noun (read-only)"},
                        "ours": body["candidates"], "evolve": {"file": "evolved.json", "sha256": evo["sha256"], "counts": evo["counts"], "nodes": [{k: n[k] for k in ("id", "label", "stage", "status", "gates_failed", "is_a")} for n in evo["nodes"]]}}
    body["layers"] = {"model": "playbook 00 section 8", "observations": {"key": "observations", "n": len(obs), "role": "immutable pointers (journal refs), not merged"}, "assertions": {"key": "edges", "n": len(body["edges"]), "role": "merged by key, independent-publisher count, decay field"},
                      "concepts": {"key": "concepts", "role": "IPTC / WordNet nodes + residual and PROVISIONAL candidates (evolve.py)"}}
    body["decay_rule"] = {"half_life_days": HALF_LIFE_DAYS, "as_of": as_of, "formula": "weight = 0.5 ** (age_days / half_life_days)", "status": STATUS + " (the half-life is a guess; nothing is dropped or ranked by it here)"}
    body["status"] = STATUS; body["version"] = VERSION + "+" + body["version"]
    return body
def educate_index(cons, state_path, seed=None):
    import educate as E
    state = json.load(open(state_path)) if state_path and os.path.exists(state_path) else {}; IX = E.Index(cons, state, E.load_seed(seed or E.SEED))
    rc = collections.Counter(e["subj"][9:] for e in cons["edges"] if e["kind"] == "resource"); cc = collections.Counter(e["obj"][8:] for e in cons["edges"] if e["kind"] == "resource")
    ec = collections.Counter(); [ec.update([x]) for e in cons["edges"] if e["kind"] == "assertion" for x in (e["subj"], e["obj"]) if x in IX.labels]
    qs = [r for r, _ in sorted(rc.items(), key=lambda kv: (-kv[1], kv[0]))[:3]] + [c for c, _ in sorted(cc.items(), key=lambda kv: (-kv[1], kv[0]))[:3] if len(c) == 2] + [IX.labels[k] for k, _ in sorted(ec.items(), key=lambda kv: (-kv[1], kv[0]))[:3]] + ["no such thing in the stores"]
    samples = []
    for q in qs:
        a = E.answer(IX, q); samples.append({"question": q, "resolved": a.get("resolved"), "statements": a["statements"], "abstain": a.get("abstain"), "text": E.as_text(a)[:1500], "refs": sum(len(s["refs"]) for sec in a["sections"].values() for s in sec)})
    return {"version": E.VERSION + "-index", "status": STATUS, "weights": E.WEIGHTS, "consolidated_sha256": cons["sha256"], "state_sha256": state.get("sha256"),
            "resolves": {"resources": IX.res, "countries": IX.countries, "entities_n": len(IX.labels), "entities_top": [IX.labels[k] for k, _ in sorted(ec.items(), key=lambda kv: (-kv[1], kv[0]))[:200]]},
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
    slow_path = opt("--slow") or os.path.join(trace, "slow.jsonl"); slow, scount, slines = read_slow(slow_path)
    g4p, g4missing = find_g4(a, trace); stores = [C.load_g4(p) for p in g4p]
    with tempfile.TemporaryDirectory(prefix="slow-consolidate-") as work:
        st, tk, stline = tick_state(trace, work); outs = {}; shutil.copyfile(tk, os.path.join(out, "ticks.jsonl"))
        ticks = C.load_ticks(os.path.join(out, "ticks.jsonl")); state = json.load(open(st))   # ticks come from the kept copy: the lineage names that file, not the temp folder (same sha every pass)
        # resource state (ledger_split ResourceState) -> resource_state.json: the file ledger_split wrote, kept as is (its own sha256)
        shutil.copyfile(st, os.path.join(out, "resource_state.json")); outs["resource_state"] = {"file": os.path.join(out, "resource_state.json"), "sha256": state["sha256"], "bytes": os.path.getsize(os.path.join(out, "resource_state.json")), "counts": state["counts"], "ledger_split": stline[:300]}
        iptc = C.load_iptc()
        prev = json.load(open(opt("--prev"))) if opt("--prev") else None
        evo = EV.seal(EV.evolve(items_all, stores, ticks, iptc, prev)); evo["status"] = STATUS; evo = EV.seal(evo); outs["evolved"] = write(os.path.join(out, "evolved.json"), evo); outs["evolved"]["counts"] = evo["counts"]
        cons = seal(build_layers(items_all, meta, stores, ticks, {**slow}, iptc, evo)); outs["consolidated"] = write(os.path.join(out, "consolidated.json"), cons)
        outs["consolidated"]["counts"] = cons["counts"]; outs["consolidated"]["layers"] = {"observations": len(cons["observations"]), "assertions": len(cons["edges"]), "concepts_ours": len(cons["concepts"]["ours"]), "concepts_evolve_nodes": len(cons["concepts"]["evolve"]["nodes"])}
        # truth: snapshot into the output folder (not the shared /workspace/data/anchors/truth file); scores reported only
        tr = seal(truth(trace, os.path.join(out, "resource_snapshot.json"))); outs["truth"] = write(os.path.join(out, "truth.json"), tr)
        e, i = tr.get("event_peak", {}), tr.get("identity", {}); outs["truth"]["summary"] = {"event_peak": {k: e.get(k) for k in ("checkable", "hits", "hit_rate", "bar", "pass", "unmeasured")}, "identity": {k: i.get(k) for k in ("pairs_resolved", "conflicts", "conflict_rate", "pass", "unmeasured")}}
        ix = seal(educate_index(cons, os.path.join(out, "resource_state.json"))); outs["educate_index"] = write(os.path.join(out, "educate_index.json"), ix); outs["educate_index"]["answers_with_statements"] = ix["answers_with_statements"]
    signal.alarm(0)
    man.update({"state": "done", "ended": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "seconds": round(time.time() - t0, 1), "inputs": {"chain": {"file": chain, "sha256": sha_file(chain), "traced_items": len(items)}, "journal_rows": len(jitems), "slow": {"file": slow_path, "present": os.path.exists(slow_path), "lines": slines, "ids": len(slow), "stage_counts": scount}, "g4_stores": [{"file": p, "sha256": sha_file(p), "bytes": os.path.getsize(p)} for p in g4p], "g4_missing": g4missing},
                "outputs": outs, "layers": cons["layers"], "note": "every output PROVISIONAL; truth scores reported, never gating; the half-life of the decay field is a guess"})
    write(os.path.join(out, "slow_consolidate_run.json"), man)
    print(json.dumps({"out": out, "state": man["state"], "seconds": man["seconds"], "slow_present": man["inputs"]["slow"]["present"], "outputs": {k: {"sha256": v["sha256"], **{x: v[x] for x in ("counts", "layers", "summary", "answers_with_statements") if x in v}} for k, v in outs.items()}}, sort_keys=True, indent=1))
if __name__ == "__main__": main(sys.argv[1:])
