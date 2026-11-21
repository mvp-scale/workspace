"""check-flow: the fast gate for the chained pipeline flow (T158, flow-fix defect 1; owner track step 2 CHAIN). Proves, on the 5 offline fixtures of check-parts.py, that what one stage writes is what the next stage reads:
  A parts        live_trace.py --replay-run <5 ids>: every stage state equals the fixture chain.jsonl line (fixture integrity first: a/<seq>.json id = chain id, run.json present)
  B slow         copy of simulation/fixtures/parts/trace into a scratch window, slow_clock.py --cap-min 2: 5 records, the 7 keys on each, 0 error, change proposal / abstain as recorded for the fixtures
  C consolidate  slow_consolidate.py on that scratch window: the 5 output files, assertion edges > 0, concepts nodes_used > 0 (IPTC carried through), resource states > 0, per-observation 'capabilities' and 'decider_change' keys, truth pass is null when nothing is checkable
  D status       check-alignment.py --window <scratch> --out <scratch>/status.json: core 17 of 17 run (each from a stage that ran), 5 traced shown; an empty window exits 1; a window whose stages are all 'empty' counts nothing as run
  E page feed    raw-units.py sample(src="trace:<scratch>") with no server: 5 articles with the page keys, slow parts, decider change, consolidated counts
    /workspace/models/embed-zs/.venv/bin/python simulation/check-flow.py [--only A,B,C,D,E] [--keep]
One PASS / FAIL line per step with the numbers asserted, then the total seconds; exit 1 on any FAIL. CPU only, offline, no hosted call, no queue write (the replay and the page feed read the news queue database read-only for the 5 fixture ids), no service touched,
decider.py and lean/ are not edited, check_against_lean() must stay 160 (slow_clock asserts it). Scratch folder = a temp dir, removed at exit (--keep leaves it and prints the path). Steps that read the output of an earlier step FAIL with the reason when that output is missing."""
import sys, os, re, json, time, shutil, tempfile, subprocess, collections
HERE = os.path.dirname(os.path.abspath(__file__)); KP = os.path.dirname(HERE); WS = os.path.join(KP, "projects", "world-state")
FIX = os.path.join(HERE, "fixtures", "parts", "trace"); PYNP = "/workspace/models/embed-zs/.venv/bin/python"; PY = PYNP if os.path.exists(PYNP) else sys.executable
SLOWK = ("claims", "direction", "change", "function_p", "factuality_p", "identity_g4", "contradictions")   # slow_clock.py KEYS
ENV = {**os.environ, "PYTHONHASHSEED": "0", "CUDA_VISIBLE_DEVICES": "", "WORLD_GPU": "0", "HF_HUB_OFFLINE": "1", "THREADS": "4", "TOKENIZERS_PARALLELISM": "false"}
args = sys.argv[1:]; ONLY = set(args[args.index("--only") + 1].upper().split(",")) if "--only" in args else None; KEEP = "--keep" in args
def run(cmd, timeout):
    """(returncode, stdout, stderr) of a child in projects/world-state; a timeout is a returncode of -9"""
    try: r = subprocess.run(cmd, capture_output=True, text=True, cwd=WS, env=ENV, timeout=timeout); return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired as e: return -9, (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout after %d s" % timeout
def jl(p):
    out = []
    for ln in open(p, encoding="utf-8"):
        if ln.strip(): out.append(json.loads(ln))
    return out
def jload(p): return json.load(open(p, encoding="utf-8"))
def chain_lines(path):
    """[(seq, line dict)] of a chain.jsonl (each row's 'line' is a JSON string)"""
    return [(r["seq"], json.loads(r["line"])) for r in jl(path)]
def slow_rec(o):
    if isinstance(o.get("line"), str):
        try: return json.loads(o["line"])
        except Exception: pass
    return o
class Fail(Exception): pass
def need(cond, msg, bad):
    """collect one assertion: msg is shown on PASS and FAIL, bad collects the failed ones"""
    if not cond: bad.append(msg)
    return cond
# ---------------------------------------------------------------- A
def step_a(S):
    bad = []; recs = chain_lines(os.path.join(FIX, "chain.jsonl")); ids = [l["id"] for _, l in recs]
    for seq, l in recs:   # fixture integrity: the a/ file and the chain line name the same article
        p = os.path.join(FIX, "a", "%d.json" % seq)
        if not os.path.exists(p): bad.append("fixture a/%d.json missing" % seq); continue
        aid = (jload(p).get("article_line") or {}).get("id"); need(aid == l["id"], "a/%d.json id %s != chain id %s" % (seq, str(aid)[:8], l["id"][:8]), bad)
    need(os.path.exists(os.path.join(FIX, "run.json")), "fixture run.json missing", bad)
    rc, so, se = run([PY, "live_trace.py", "--replay-run", ",".join(ids)], 240)
    j = [x for x in so.splitlines() if x.startswith("REPLAY_JSON ")]
    if rc != 0 or not j: raise Fail("replay process failed (rc %s): %s" % (rc, (se or so)[-300:].replace("\n", " ")))
    out = json.loads(j[0][12:]); tot = ok = 0; nmis = 0
    for seq, l in recs:
        r = out.get(l["id"])
        if not r: bad.append("seq %d: id not in the queue, replay returned nothing" % seq); continue
        want = [(s["name"], s["state"]) for s in l["stages"]]; got = [(s[0], s[1]) for s in r["stages"]]
        tot += len(want); ok += sum(1 for a, b in zip(want, got) if a == b)
        if want != got: bad.append("seq %d stage states differ: %s" % (seq, [(a, b) for a, b in zip(want, got) if a != b][:3]))
        nmis += sum(1 for s, t in zip(l["stages"], r["stages"]) if s["name"] == t[0] and s.get("n") != t[2])
    if bad: raise Fail("; ".join(bad))
    return "%d articles, %d of %d stage states equal the fixture chain.jsonl (stage item counts differing: %d)" % (len(recs), ok, tot, nmis)
# ---------------------------------------------------------------- B
def step_b(S):
    bad = []; shutil.copytree(FIX, os.path.join(S, "trace"))
    rc, so, se = run([PY, "slow_clock.py", S, "--cap-min", "2"], 280)
    sj = os.path.join(S, "trace", "slow.jsonl")
    if rc != 0 or not os.path.exists(sj): raise Fail("slow_clock failed (rc %s): %s" % (rc, (se or so)[-300:].replace("\n", " ")))
    recs = [slow_rec(o) for o in jl(sj)]; run_ = jload(os.path.join(S, "trace", "slow_run.json"))
    need(len(recs) == 5, "%d slow records, want 5" % len(recs), bad)
    errs = 0
    for o in recs:
        miss = [k for k in SLOWK if k not in o]
        if miss: bad.append("seq %s missing keys %s" % (o.get("seq"), miss))
        errs += sum(1 for k in SLOWK if isinstance(o.get(k), dict) and o[k].get("state") == "error")
    need(errs == 0, "%d error states" % errs, bad)
    need(run_.get("state") == "done", "slow_run state %s" % run_.get("state"), bad); need(run_.get("check_against_lean") == 160, "check_against_lean %s" % run_.get("check_against_lean"), bad)
    by = {o.get("seq"): (o.get("change") or {}) for o in recs}
    need(by.get(21, {}).get("state") == "proposal" and by.get(21, {}).get("proposed") == "up", "seq 21 change %s/%s, want proposal up" % (by.get(21, {}).get("state"), by.get(21, {}).get("proposed")), bad)
    need(by.get(6, {}).get("state") == "abstain", "seq 6 change %s, want abstain" % by.get(6, {}).get("state"), bad)
    if bad: raise Fail("; ".join(bad))
    st = collections.Counter(by[s].get("state") for s in by)
    return "%d records, %d keys each, %d error, change %s, lean %s, g4 store %s" % (len(recs), len(SLOWK), errs, dict(st), run_.get("check_against_lean"), "yes" if os.path.exists(os.path.join(S, "trace", "g4", "store.jsonl")) else "no")
# ---------------------------------------------------------------- C
OUTS = ("consolidated.json", "evolved.json", "resource_state.json", "truth.json", "educate_index.json")
def step_c(S):
    bad = []; tr = os.path.join(S, "trace"); g4 = os.path.join(tr, "g4", "store.jsonl")
    if not os.path.exists(os.path.join(tr, "chain.jsonl")): raise Fail("scratch window missing (step B did not run)")
    rc, so, se = run([PY, "slow_consolidate.py", "--trace", tr, "--g4", g4], 240)
    od = os.path.join(tr, "slow_consolidate")
    if rc != 0: raise Fail("slow_consolidate failed (rc %s): %s" % (rc, (se or so)[-300:].replace("\n", " ")))
    have = [f for f in OUTS if os.path.exists(os.path.join(od, f))]; need(len(have) == 5, "output files %d of 5 (missing %s)" % (len(have), sorted(set(OUTS) - set(have))), bad)
    if len(have) < 5: raise Fail("; ".join(bad))
    cons = jload(os.path.join(od, "consolidated.json")); rs = jload(os.path.join(od, "resource_state.json")); tru = jload(os.path.join(od, "truth.json"))
    edges = (cons.get("counts") or {}).get("assertion_edges", 0); need(edges > 0, "assertion edges %s, want > 0" % edges, bad)
    nu = ((cons.get("concepts") or {}).get("iptc") or {}).get("nodes_used", 0); need(nu > 0, "concepts nodes_used %s, want > 0 (iptc not carried into the assertions)" % nu, bad)
    states = (rs.get("counts") or {}).get("states", 0); need(states > 0, "resource states %s, want > 0" % states, bad)
    obs = cons.get("observations") or []; need(len(obs) == 5, "observations %d, want 5" % len(obs), bad)
    nc = sum(1 for o in obs if "capabilities" in o); need(nc == len(obs) and obs, "capabilities key on %d of %d observations" % (nc, len(obs)), bad)
    nd = sum(1 for o in obs if isinstance(o.get("decider_change"), dict) and all(k in o["decider_change"] for k in ("proposed", "outcome", "provisional")))
    need(nd == len(obs) and obs, "decider_change {proposed, outcome, provisional} on %d of %d observations" % (nd, len(obs)), bad)
    ep = tru.get("event_peak") or {}; idn = tru.get("identity") or {}
    need(ep.get("checkable", 0) > 0 or ep.get("pass") is None, "truth event_peak checkable 0 but pass %s (want null)" % ep.get("pass"), bad)
    need(idn.get("pairs_resolved", 0) > 0 or idn.get("pass") is None, "truth identity pairs_resolved 0 but pass %s (want null)" % idn.get("pass"), bad)
    if bad: raise Fail("; ".join(bad))
    return "5 files, assertion edges %d, nodes_used %d, resource states %d, capabilities+decider_change on %d of %d observations, truth event_peak checkable %s pass %s" % (edges, nu, states, nd, len(obs), ep.get("checkable"), ep.get("pass"))
# ---------------------------------------------------------------- D
def align(S, win, out):
    rc, so, se = run([PY, os.path.join(HERE, "check-alignment.py"), "--no-durable", "--window", win, "--out", out], 240)
    if not os.path.exists(out): raise Fail("check-alignment wrote nothing (rc %s): %s" % (rc, (se or so)[-300:].replace("\n", " ")))
    return rc, jload(out)
def step_d(S):
    bad = []; tr = os.path.join(S, "trace")
    if not os.path.exists(os.path.join(tr, "chain.jsonl")): raise Fail("scratch window missing (step B did not run)")
    rc, st = align(S, S, os.path.join(S, "status.json")); c = st["counts"]["core"]; w = st["window"]
    need(rc == 0, "exit %s on the full window, want 0" % rc, bad)
    need(c["n"] == 17 and c["live"] == 17, "core %d of %d run, want 17 of 17" % (c["live"], c["n"]), bad)
    notlive = [r["id"] for r in st["rows"] if r["group"] == "core" and (r["used"]["s"] != "yes" or r["runs_in"] == "no")]; need(not notlive, "core rows not run: %s" % notlive, bad)
    need(w["traced"] == 5, "traced shown %s, want 5" % w["traced"], bad); need(not w.get("newest_empty"), "full window flagged empty: %s" % w.get("newest_empty"), bad)
    sic = w.get("stages_in_chain") or {}; chainonly = [r for r in st["rows"] if r["group"] == "core" and r["runs_in"] == "chain"]
    # variant 1: an empty window (chain.jsonl with no line) is flagged and exits 1
    e = os.path.join(S, "empty-window"); os.makedirs(os.path.join(e, "trace")); open(os.path.join(e, "trace", "chain.jsonl"), "w").close()
    rc1, st1 = align(S, e, os.path.join(S, "status-empty.json")); need(rc1 == 1, "empty window exit %s, want 1" % rc1, bad); need(bool((st1["window"] or {}).get("newest_empty")), "empty window not flagged (window.newest_empty null)", bad)
    need(st1["counts"]["core"]["live"] == 0, "empty window shows core %d run, want 0" % st1["counts"]["core"]["live"], bad)
    # variant 2: stages present but all 'empty' (not ran): none may count as run
    z = os.path.join(S, "all-empty-window"); os.makedirs(os.path.join(z, "trace"))
    with open(os.path.join(z, "trace", "chain.jsonl"), "w") as f:
        for r in jl(os.path.join(FIX, "chain.jsonl")):
            l = json.loads(r["line"])
            for s in l.get("stages", []): s["state"] = "empty"
            f.write(json.dumps({**r, "line": json.dumps(l, ensure_ascii=False)}, ensure_ascii=False) + "\n")
    rc2, st2 = align(S, z, os.path.join(S, "status-all-empty.json")); c2 = st2["counts"]["core"]
    need(c2["live"] == 0, "all-empty stages still count as run: core %d of %d run (%s)" % (c2["live"], c2["n"], c2["runs"]), bad)   # g3_time stays a part: its novelty proxy is the journal duplicate kind, not a stage state
    if bad: raise Fail("; ".join(bad))
    return "core %d of %d run (runs_in %s), traced %d shown, %d stages in chain; empty window exit %d flagged; all-empty stages: core run %d of %d" % (c["live"], c["n"], {k: v for k, v in c["runs"].items() if v}, w["traced"], len(sic), rc1, c2["live"], c2["n"])
# ---------------------------------------------------------------- E
E_CHILD = r'''
import os, sys, json, importlib.util
os.environ["PYTHONHASHSEED"] = "0"; sys.path.insert(0, os.getcwd())
sp = importlib.util.spec_from_file_location("raw_units", sys.argv[1]); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
r = m.sample(src="trace:" + sys.argv[2])
print("FLOW_E_JSON " + json.dumps(r, default=str, ensure_ascii=False))
'''
PAGE_KEYS = ("story", "codes", "decider", "world", "g4")
def step_e(S):
    bad = []
    if not os.path.exists(os.path.join(S, "trace", "chain.jsonl")): raise Fail("scratch window missing (step B did not run)")
    rc, so, se = run([PY, "-c", E_CHILD, os.path.join(HERE, "raw-units.py"), S], 240)
    j = [x for x in so.splitlines() if x.startswith("FLOW_E_JSON ")]
    if rc != 0 or not j: raise Fail("sample(src='trace:<window>') failed (rc %s): %s" % (rc, (se or so)[-300:].replace("\n", " ")))
    res = json.loads(j[0][12:]); arts = res.get("articles") or []
    need(len(arts) == 5, "%d articles, want 5" % len(arts), bad)
    traced = [a for a in arts if a.get("state") == "traced"]; need(len(traced) == len(arts) and arts, "%d of %d articles traced" % (len(traced), len(arts)), bad)
    for k in PAGE_KEYS:
        n = sum(1 for a in traced if k in a); need(n == len(traced) and traced, "key '%s' on %d of %d articles" % (k, n, len(traced)), bad)
    ns = sum(1 for a in traced if isinstance(a.get("slow"), dict) and all(k in a["slow"] for k in SLOWK)); need(ns == len(traced) and traced, "slow parts (7 keys) on %d of %d articles" % (ns, len(traced)), bad)
    nc = sum(1 for a in traced if isinstance(a.get("decider_change"), dict) and "proposed" in a["decider_change"] and "outcome" in a["decider_change"] and "provisional" in a["decider_change"]); need(nc == len(traced) and traced, "decider_change on %d of %d articles" % (nc, len(traced)), bad)
    props = sorted({str((a.get("decider_change") or {}).get("proposed")) for a in traced}); need(any(p in ("up", "down") for p in props), "no article shows a change proposal (proposed values %s)" % props, bad)
    cs = [a.get("consolidated") for a in traced]; ncs = sum(1 for c in cs if isinstance(c, dict) and c.get("observation") and isinstance(c.get("counts"), dict) and (c["counts"].get("assertions", 0) > 0 and c["counts"].get("concepts_iptc_nodes_used", 0) > 0))
    need(ncs == len(traced) and traced, "consolidated {observation, counts.assertions > 0, counts.concepts_iptc_nodes_used > 0} on %d of %d articles" % (ncs, len(traced)), bad)
    cc = next((c["counts"] for c in cs if isinstance(c, dict) and isinstance(c.get("counts"), dict)), {})
    if bad: raise Fail("; ".join(bad))
    return "%d articles, keys %s + slow(7) + decider_change on all, change proposals %s, consolidated %s assertions, %s iptc nodes used on each" % (len(arts), "/".join(PAGE_KEYS), props, cc.get("assertions"), cc.get("concepts_iptc_nodes_used"))
STEPS = [("A", "parts", step_a), ("B", "slow", step_b), ("C", "consolidate", step_c), ("D", "status", step_d), ("E", "page feed", step_e)]
def main():
    t0 = time.time(); S = tempfile.mkdtemp(prefix="check-flow-"); res = []
    print("check-flow: 5 fixtures (%s), scratch window %s" % (os.path.relpath(FIX, KP), S))
    for k, name, fn in STEPS:
        if ONLY and k not in ONLY: continue
        t = time.time()
        try: msg = fn(S); ok = True
        except Fail as e: msg = str(e); ok = False
        except Exception as e: msg = "%s: %s" % (type(e).__name__, str(e)[:300]); ok = False
        res.append((k, ok)); print("%s %s %-12s %5.1f s  %s" % ("PASS" if ok else "FAIL", k, name, time.time() - t, msg), flush=True)
    n = sum(1 for _, o in res if o); print("TOTAL %.1f s | %d of %d steps PASS%s" % (time.time() - t0, n, len(res), "" if n == len(res) else " | FAIL: " + ", ".join(k for k, o in res if not o)))
    if KEEP: print("scratch kept: " + S)
    elif os.path.basename(S).startswith("check-flow-") and os.path.dirname(S) == tempfile.gettempdir(): shutil.rmtree(S, ignore_errors=True)   # only the temp dir this run made
    sys.exit(0 if res and n == len(res) else 1)
if __name__ == "__main__": main()
