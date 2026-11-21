"""check-durable: structural done-check for plan step 1 (durable journal, G4 store, resource ledger) and step 3 (resource state v1). Touches nothing of the running bench: every
store goes to a temp folder (G4_DURABLE_DIR / --tmp), the G4 parts run in separate child processes that load raw-units.py themselves. CPU only, no hosted calls.
    /workspace/models/embed-zs/.venv/bin/python simulation/check-durable.py [--trace <trace folder>] [--no-g4]
Checks (each prints PASS or FAIL):
  journal : save, reload in a fresh Durable -> same rows and day table; two replays of one input -> same sha256 of the log; a syndicated copy adds no story (counted once)
  ledger  : resource state replay is idempotent (second pass over the same lines adds 0 ticks and gives the same sha256); a fresh process reloading the tick log gives equal Ledger rows;
            100 percent of state rows carry >= 1 evidence pointer; per-day shares are written and sum to 1 per (country, day)
  g4      : 4 articles (a story root, its syndicated copy, 2 others) into two empty stores give the same digest (two replays, same sha256); a fresh process reloading the file gives equal
            entity / assertion / edge / node counts and digest; the copy does not raise any assertion's independent-publisher count; the raw-units merge index reloads with the same node count."""
import sys, os, json, hashlib, subprocess, tempfile, sqlite3, collections
HERE = os.path.dirname(os.path.abspath(__file__)); WS = os.path.join(os.path.dirname(HERE), "projects", "world-state"); PY = sys.executable
TRACE = sys.argv[sys.argv.index("--trace") + 1] if "--trace" in sys.argv else "/workspace/demo/mockups/structure-live/runs-v7/trace"
bad = []
def ck(name, ok, detail=""):
    print("%s %s %s" % ("PASS" if ok else "FAIL", name, detail)); bad.extend([] if ok else [name])
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def traced(trace):
    for ln in open(trace + "/chain.jsonl"):
        l = json.loads(json.loads(ln)["line"])
        if l.get("state") == "traced": yield l
if len(sys.argv) > 2 and sys.argv[1] == "--g4-child":   # child: python check-durable.py --g4-child <dir> <mode: build|load> <id,id,...>
    d, mode, ids = sys.argv[2], sys.argv[3], sys.argv[4].split(",")
    os.environ["G4_DURABLE_DIR"] = d; os.environ["G4_DURABLE"] = "1"; os.chdir(WS); sys.path.insert(0, WS)
    import importlib.util
    sp = importlib.util.spec_from_file_location("raw_units", os.path.join(HERE, "raw-units.py")); RU = importlib.util.module_from_spec(sp); sp.loader.exec_module(RU)
    if mode == "build":
        ch = RU.chain(); db = sqlite3.connect("file:%s?mode=ro" % RU.LT.QUEUE, uri=True); indep = {}; out = {}
        for i, iid in enumerate(ids):
            row = db.execute(RU.LT.select_sql("id = ?"), (iid,)).fetchone(); r = RU.run_one(ch, row); RU.merge_units(r, {iid}); RU.G4.align(r, RU.G, ch); RU.G.pulled.add(iid)
            S = RU.G.g4; indep[iid] = {a: sorted({S.arts[x]["publisher"] for x in v["arts"] if S.arts[x]["independent"]}) for a, v in S.asr.items()}
        out["indep_pubs_after"] = indep; S = RU.G.g4
    else:   # load: the Store is created and attached by the first align(); here it is attached directly the same way
        S = RU.G4.Store().attach(os.path.join(d, "store.jsonl")); out = {"pulled_seed": len(set(S.arts) | set(a for n in RU.G.nodes.values() for a in n["arts"]))}
    out.update(counts=S.counts(), digest=S.digest(), nodes_index=len(RU.G.nodes), node_articles=len({a for n in RU.G.nodes.values() for a in n["arts"]}), store_sha=sha(os.path.join(d, "store.jsonl")) if os.path.exists(os.path.join(d, "store.jsonl")) else None, nodes_sha=sha(os.path.join(d, "raw-units-nodes.jsonl")) if os.path.exists(os.path.join(d, "raw-units-nodes.jsonl")) else None)
    print("CHILD " + json.dumps(out, sort_keys=True)); sys.exit(0)
sys.path.insert(0, WS); tmp = tempfile.mkdtemp(prefix="durable-check-")
try:
    # ---- journal ----
    import journal as J
    A = ("Big storm hits the northern coast tonight heavy rain", "Big storm hits the northern coast tonight. " * 8)
    items = [("i0", A[0], A[1], "bbc"), ("i1", A[0], A[1], "cnn"), ("i2", "Council votes to close the old library branch next spring", "The council voted on Tuesday to close the old library branch next spring. " * 4, "bbc"), ("i1", A[0], A[1], "cnn")]   # i1 twice = the same item replayed
    def play(p, run):
        D = J.Durable(p)
        for seq, (iid, t, b, s) in enumerate(items): D.add(iid, J.story_keys(t, b), s, seq, run, "lv-test", "2026-11-20")
        return D
    p1, p2 = tmp + "/a/j.jsonl", tmp + "/b/j.jsonl"; D1 = play(p1, "run-x"); D2 = play(p2, "run-x")
    ck("journal: two replays of the same input give the same sha256", sha(p1) == sha(p2), sha(p1)[:16])
    E = J.Durable(p1)
    ck("journal: reload in a fresh Durable gives the same rows and day table", E.rows == D1.rows and E.day_table() == D1.day_table(), json.dumps(E.day_table()))
    t = E.day_table()["2026-11-20"]; ck("journal: a syndicated copy is counted once (3 items, 2 stories, 1 copy; the replayed i1 adds nothing)", (t["items"], t["stories"], t["copies"]) == (3, 2, 1), str(t))
    D3 = J.Durable(p1); r = D3.add("i0", {}, "x", 99, "run-y", "lv-test", "2026-11-21"); ck("journal: an item already logged in another run is not counted again", r["replayed"] and len(D3.rows) == 3 and sha(p1) == sha(p2))
    # ---- ledger / resource state ----
    import ledger_split as LS
    spec = json.load(open(LS.SPEC)); lines = list(traced(TRACE)); log = tmp + "/ledger/ticks.jsonl"; lv = {"test": 1}
    RS = LS.ResourceState(spec, "auto", log=log, run_id="run-test", label_version=lv); new1 = sum(RS.add(l) for l in lines); res1 = RS.result()
    new2 = sum(RS.add(l) for l in lines); res1b = RS.result()
    ck("ledger: a second pass over the same lines adds 0 ticks and gives the same sha256", new1 == len(lines) and new2 == 0 and res1["sha256"] == res1b["sha256"], "%d lines, sha %s" % (new1, res1["sha256"][:16]))
    RF = LS.ResourceState(spec, "auto", log=None, run_id="run-test", label_version=lv); [RF.add(l) for l in lines]
    ck("ledger: a replay without any log gives the same sha256", RF.result()["sha256"] == res1["sha256"])
    code = "import sys, json; sys.path.insert(0, %r); import ledger_split as LS; spec = json.load(open(LS.SPEC)); R = LS.ResourceState(spec, 'auto', log=%r, run_id='run-test', label_version={'test': 1}); print('CHILD ' + json.dumps({'rows': R.L.rows(), 'sha': R.result()['sha256'], 'tick': R.L.tick, 'items': R.L.items, 'kinds': dict(R.L.kinds)}, sort_keys=True))" % (WS, log)
    o = subprocess.run([PY, "-c", code], capture_output=True, text=True); ch = json.loads(next(x for x in o.stdout.splitlines() if x.startswith("CHILD "))[6:])
    live_rows = json.loads(json.dumps(RS.L.rows(), sort_keys=True))
    ck("ledger: a fresh process reloading the tick log gives equal Ledger rows (%d resources), equal state sha256, equal tick and item counts" % len(live_rows), ch["rows"] == live_rows and ch["sha"] == res1["sha256"] and (ch["tick"], ch["items"]) == (RS.L.tick, RS.L.items), "tick %d, items %d" % (ch["tick"], ch["items"]))
    st = res1["states"]; ck("ledger: 100 percent of state rows carry >= 1 evidence pointer", st and all(x["evidence"] for x in st), "%d rows, %d pointers" % (len(st), res1["counts"]["evidence_pointers"]))
    tot = collections.defaultdict(float)
    for d, cs in res1["day_shares"].items():
        for c, v in cs.items(): tot[(d, c)] += sum(v.values())
    ck("ledger: per-day shares are written and sum to 1 per (country, day) within 1e-4 (6-decimal rounding)", len(tot) > 0 and all(abs(v - 1) < 1e-4 for v in tot.values()), "%d (day, country) cells, %d days" % (len(tot), len(res1["day_shares"])))
    ck("ledger: the seed is marked PROVISIONAL and all rows say so", res1["seed"]["provisional"] and all(x["status"].startswith("PROVISIONAL") for x in st), "seed %d rows, %s" % (res1["seed"]["rows"], res1["seed"]["status"]))
    # ---- G4 store ----
    if "--no-g4" not in sys.argv:
        lines_by_seq = {l["seq"]: l for l in lines}; cp = next(l for l in lines if (l["journal"].get("dup") or {}).get("kind") == "copy" and lines_by_seq.get(l["journal"]["dup"]["of_seq"]))
        root = lines_by_seq[cp["journal"]["dup"]["of_seq"]]; others = [l["id"] for l in lines if l is not cp and l is not root and l.get("input", {}).get("has_body")][:2]; ids = [root["id"], cp["id"]] + others
        def child(d, mode, idl):
            o = subprocess.run([PY, os.path.abspath(__file__), "--g4-child", d, mode, ",".join(idl)], capture_output=True, text=True, timeout=1500)
            try: return json.loads(next(x for x in o.stdout.splitlines() if x.startswith("CHILD "))[6:])
            except StopIteration: print(o.stdout[-800:], o.stderr[-1500:]); raise
        a = child(tmp + "/g1", "build", ids); b = child(tmp + "/g2", "build", ids); c = child(tmp + "/g1", "load", ids)
        ck("g4: two replays of the same input give the same store digest and the same log sha256", a["digest"] == b["digest"] and a["store_sha"] == b["store_sha"] and a["nodes_sha"] == b["nodes_sha"], "digest %s, counts %s" % (a["digest"][:16], a["counts"]))
        ck("g4: a fresh process reloading the file gives identical entity, assertion, edge, node counts and digest", c["counts"] == a["counts"] and c["digest"] == a["digest"], str(c["counts"]))
        ck("g4: the merge index (raw-units) reloads with the same node count (%d nodes over %d articles)" % (a["nodes_index"], a["node_articles"]), c["nodes_index"] == a["nodes_index"] and a["nodes_index"] > 0)
        ia = a["indep_pubs_after"]; before = ia[ids[0]]
        ck("g4: the syndicated copy does not raise any assertion's independent-publisher count", all(ia[ids[1]].get(k) == v for k, v in before.items()), "%d assertions after the root; copy %s of %s" % (len(before), cp["id"][:8], root["id"][:8]))
finally:
    print("temp stores kept for inspection:", tmp)   # not deleted (no rm on a variable path); they are small
print("ALL PASS" if not bad else "FAILED: " + "; ".join(bad)); sys.exit(1 if bad else 0)
