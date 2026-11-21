"""slow_clock: the slow pass over a finished live_trace window (T158, plan 1c, owner directive L2901: every part must RUN end to end; weak quality is output marked PROVISIONAL or an abstain, never a blocker).
The chain (live_trace.py) keeps the 600 ms budget, so the parts that cost more run here, once per traced id of a finished window, read-only on the window's trace:
  claims      claims v1 (claims_units.extract_claims, lg dependency rules, one parse per article)
  direction   direction_v1.read_claims on those claims + read_story (ext rules); story up / down / unknown, PROVISIONAL until runs/pulse/t173-direction says the bar is met AND the non-finance check is done
  change      the decider's "change" field: the direction read goes in as a STATED_FACT proposal with validated=False and decider.decide() is called READ-ONLY; the outcome is recorded next to the chain's own outcome. decider.py and lean/ are not touched
  heads       function_p and factuality_p per sentence from the saved CPU heads (raw_core.saved_heads, switched on here by RC.RAW_HEADS = True; the flag RAW_HEADS=0 stays the default everywhere else); story level mean / max / counts
  identity_g4 raw_core.build_rec + merge_units + g4_align.align on a durable graph (LT_V4_G4_DIR, --g4-dir, or <window>/g4)
  contradictions  g4_align.align(contradictions=True): the contradiction edges this article drew against the store
Output: <trace>/slow.jsonl (one line per id, every key always present; a part that cannot say anything is {"state": "abstain" | "empty" | "error", "why": ...}), <trace>/slow_run.json (summary, pid, counts, ms p50/p90 per part).
Hard cap 60 minutes (SIGTERM or the cap finish the current id, write the summary and exit; a watchdog hard-exits 90 s after the cap). Resumable by id: ids already in slow.jsonl are skipped, the durable G4 dir keeps the graph. Stop by verified PID:  slow_clock.py --stop <trace>
    /workspace/models/embed-zs/.venv/bin/python slow_clock.py <window or trace dir> [--limit N] [--start N] [--g4-dir D] [--cap-min 60]      (from projects/world-state, CPU only, no hosted calls)"""
import os, sys, json, time, signal, threading, collections, statistics, hashlib
os.environ["PYTHONHASHSEED"] = "0"   # live_trace re-execs the process unless this is "0"; set before the import so slow_clock is not re-executed (the raw-units.py pattern)
if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[1] == "--stop":   # light path: no model imports
    tr = sys.argv[2]; tr = tr if os.path.exists(os.path.join(tr, "slow_run.json")) else os.path.join(tr, "trace"); run = json.load(open(os.path.join(tr, "slow_run.json"))); pid = run.get("pid")
    try: cmd = open("/proc/%d/cmdline" % pid, "rb").read().decode(errors="replace").replace("\0", " ")
    except Exception: print("no process %s (state %s): nothing to stop" % (pid, run.get("state"))); sys.exit(0)
    if "slow_clock.py" not in cmd or run.get("cmd", "\0") not in cmd: print("pid %s is not this slow_clock run, refusing: %s" % (pid, cmd[:160])); sys.exit(1)
    os.kill(pid, signal.SIGTERM); print("SIGTERM sent to verified pid %d" % pid); sys.exit(0)
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WORLD_GPU", "0"); os.environ.setdefault("HF_HUB_OFFLINE", "1")
import pathlib
HERE = pathlib.Path(__file__).resolve().parent; os.chdir(HERE); sys.path.insert(0, str(HERE))
CAP_S_DEFAULT = 3600; PROVISIONAL = "PROVISIONAL"; VERSION = "slow-clock-v1"
KEYS = ("claims", "direction", "change", "function_p", "factuality_p", "identity_g4", "contradictions")
def atomic(path, obj):
    tmp = path + ".tmp"; open(tmp, "w").write(json.dumps(obj, ensure_ascii=False, indent=1)); os.replace(tmp, path)
def arg(name, default=None, cast=str):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default
def trace_dir(p):
    p = os.path.abspath(p)
    return p if os.path.exists(os.path.join(p, "chain.jsonl")) else os.path.join(p, "trace")
def lines_of(tr):
    """traced lines of the window in seq order: [(seq, line)]; the line is the one chain.jsonl holds (its sha chain is the chain's, not re-checked here: verify_trace.py does that)"""
    out = []
    for ln in open(os.path.join(tr, "chain.jsonl"), encoding="utf-8"):
        if not ln.strip(): continue
        r = json.loads(ln); l = json.loads(r["line"])
        if l.get("state") == "traced": out.append((r["seq"], l))
    return out
def pct(v, q): v = sorted(v); return round(v[min(len(v) - 1, int(q * (len(v) - 1)))], 2) if v else None
class Slow:
    def __init__(self, tr, g4_dir, cap_s):
        self.tr = tr; self.g4_dir = g4_dir; self.cap_s = cap_s; self.stop = False; self.t0 = time.time(); self.state = "starting"
        import live_trace as LT, raw_core as RC, g4_align as G4, claims_units as CU, direction_v1 as DV, decider as D
        self.LT, self.RC, self.G4, self.CU, self.DV, self.D = LT, RC, G4, CU, DV, D
        self.lean = D.check_against_lean(); assert self.lean == 160, "check_against_lean must stay 160, got %s" % self.lean
        t = time.time(); self.ch = LT.Chain(); CU.claims_nlp(); RC.lg_nlp(); self.load_s = round(time.time() - t, 1)
        RC.RAW_HEADS = True; RC._SH.update(h=None, err=None, tried=False)   # force the saved heads on for this process only (module flag, env untouched)
        t = time.time(); self.heads = RC.saved_heads(); self.heads_err = RC._SH["err"]; self.heads_load_s = round(time.time() - t, 1)
        os.makedirs(g4_dir, exist_ok=True); self.G = RC.Graph(dur_dir=g4_dir, durable=True, ledger=False); RC.set_chain(ch=self.ch)
        self.seqmap = {}
    # ---- one part, guarded: returns (value, ms); an exception becomes {"state": "error"}, never a missing key
    def part(self, fn):
        t = time.perf_counter()
        try: v = fn()
        except Exception as e: v = {"state": "error", "why": "%s: %s" % (type(e).__name__, str(e)[:200])}
        return v, round((time.perf_counter() - t) * 1000, 2)
    def one(self, seq, line):
        RC, G4, CU, DV, D, ch = self.RC, self.G4, self.CU, self.DV, self.D, self.ch; ms = {}; out = {"id": line["id"], "seq": seq, "title": line.get("title"), "source": line.get("source"), "published": line.get("published"), "version": VERSION, "provisional": PROVISIONAL}
        try: a = json.load(open(os.path.join(self.tr, "a", "%d.json" % seq), encoding="utf-8")); text, full = a["text"], a["stages_full"]
        except Exception as e:
            why = "trace file a/%d.json unreadable: %s" % (seq, type(e).__name__)
            for k in KEYS: out[k] = {"state": "error", "why": why}
            out["ms"] = {}; return out
        ctx = {}
        def claims():
            c = CU.extract_claims(text); ctx["claims"] = c; s = CU.summary(c)
            return {"state": "ran" if c else "empty", "why": None if c else "no claim found", "n": len(c), **s, "items": [{k: x.get(k) for k in ("s", "s_short", "p", "o", "neg", "modal", "attrib", "said_by", "passive", "rule")} for x in c][:40], "label": CU.CLAIMS_V1_LABEL, "provisional": PROVISIONAL}
        out["claims"], ms["claims"] = self.part(claims)
        def direction():
            rows = DV.read_claims(ctx.get("claims") or []); d, how = DV.read_story(text, rows)
            return {"state": "ran" if d != "unknown" else "abstain", "why": None if d != "unknown" else (how or "no direction word in claims or text"), "story_direction": d, "via": how, "claims_read": len(rows), "up": sum(1 for r in rows if r["direction"] == "up"), "down": sum(1 for r in rows if r["direction"] == "down"),
                    "rows": [{k: r[k] for k in ("i", "direction", "evidence", "amount", "negated", "attributed_to", "conditions", "resources")} for r in rows if r["direction"] != "unknown" or r["evidence"]][:30],
                    "provisional": PROVISIONAL if DV.PROVISIONAL else "met", "label": "direction_v1 ext rules; SENTiVENT confirm half all-items 0.859 (L2895, finance only), non-finance check open"}
        out["direction"], ms["direction"] = self.part(direction)
        def change():
            dr = out["direction"]; sd = dr.get("story_direction") if dr.get("state") in ("ran", "abstain") else None
            mk = ch.FT["change"]["marker"]; oc = D.decide(mk, D.Source.STATED_FACT, False, 0, ch.X.thr, True); hv = D.harvest(oc, D.Source.STATED_FACT)   # read-only call: the proposal is NOT validated, so the decider abstains by its own rule
            chain_oc = ((line.get("decider") or {}).get("change") or {}).get("outcome") if isinstance(line.get("decider"), dict) else None
            return {"state": "proposal" if sd in ("up", "down") else "abstain", "why": None if sd in ("up", "down") else "no direction to propose", "proposed": sd if sd in ("up", "down") else None, "validated": False, "marker": D.Marker(mk).name if isinstance(mk, int) else str(mk),
                    "decider_outcome": oc.name, "decider_harvest": hv.name, "chain_outcome": chain_oc, "provisional": PROVISIONAL, "note": "proposal only: decider.py is not edited, the chain's own change field is unchanged; wiring it into the decision needs the field validated (non-finance precision check)"}
        out["change"], ms["change"] = self.part(change)
        # ---- identity + contradictions + heads, from one build_rec
        rec = {"read": {}, "text": text, "title_len": len(line["title"]), "id": line["id"], "publisher": line["source"], "title": line["title"], "url": line["url"], "published": line["published"], "state": "traced", "skip_reason": None, "total_ms": line.get("total_ms")}
        j = line.get("journal") or {}; dup = j.get("dup") or {}; own = seq; rec["story"] = {"kind": dup.get("kind"), "publishers": j.get("publishers"), "of": self.seqmap.get(dup.get("of_seq")), "seq": own}
        rec["stage_out"] = {s["name"]: {"state": s["state"], "n": s["n"], "why": s["why"], "out": s["out"]} for s in line["stages"]}; self.seqmap[own] = {"id": line["id"], "title": line["title"], "publisher": line["source"]}
        def build():
            with self.G.lock: RC.build_rec(ch, line, text, full, rec, fewnerd=True, claims=True, pre={"claims": ctx["claims"]} if "claims" in ctx else None); RC.merge_units(rec, None, self.G, ch)
            return {"state": "ran"}
        b, ms["build_rec"] = self.part(build)
        if b["state"] == "error": ms["heads"] = 0.0; out["function_p"] = out["factuality_p"] = out["identity_g4"] = out["contradictions"] = {**b, "why": "build_rec: " + b["why"]}; out["ms"] = ms; return out
        ms["heads"] = rec.get("heads_ms", 0.0); ms["build_rec"] = round(ms["build_rec"] - ms["heads"], 2)
        sents = rec.get("sentences") or []
        def head(key, ans=None):
            v = [s[key] for s in sents if key in s]
            if not v: return {"state": "abstain", "why": "heads not loaded: %s" % (self.heads_err or "saved head files missing") if self.heads is None else "no sentence scored", "n": 0, "provisional": PROVISIONAL}
            o = {"state": "ran", "why": None, "n": len(v), "mean": round(sum(v) / len(v), 3), "max": round(max(v), 3), "min": round(min(v), 3), "per_sentence": [round(x, 3) for x in v][:60], "provisional": PROVISIONAL}
            if ans: c = collections.Counter(s.get(ans) for s in sents if key in s); o["answers"] = dict(c)
            return o
        out["function_p"] = head("function_p", "function"); out["function_p"]["label"] = "function head AUC 0.79 vs CheckThat gold (bar 0.85, Jev 0.88); function_p = P(opinion)"
        out["factuality_p"] = head("factuality_p"); out["factuality_p"]["label"] = "factuality head bal acc 0.56-0.64 (bar 0.80); factuality_p = P(happened); trained on event sentences only"
        def align():
            G4.align(rec, self.G, ch, contradictions=True); g = rec["g4"]; ev = collections.Counter(e["via"] for e in g["edges"]); mr = collections.Counter((u.get("merge") or {}).get("result") for u in rec["units"] if u.get("merge")); cn = self.G.g4.counts()
            ce = [e for e in g["edges"] if e["via"] == "contradiction"]; ctx["ce"] = ce; ctx["cms"] = g.get("contradictions_ms", 0.0); ctx["g4ms"] = g["ms"]
            idn = {"state": "ran" if g["entities"] or g["assertions"] else "empty", "why": None if (g["entities"] or g["assertions"]) else "no entity or assertion aligned", "units": len(rec["units"]), "entities": len(g["entities"]), "assertions": len(g["assertions"]), "edges": len(g["edges"]), "edges_by_via": dict(sorted(ev.items())),
                   "alias_merges": g["alias_merges"], "merge": dict(sorted((k, v) for k, v in mr.items() if k)), "store": {k: cn[k] for k in cn}, "g4_ms": g["ms"], "story": g.get("story"), "entities_list": [{k: e.get(k) for k in ("id", "type", "canon", "fine", "articles")} for e in g["entities"]][:40],
                   "label": G4.LABEL, "provisional": PROVISIONAL}
            return idn
        out["identity_g4"], ms["identity_g4"] = self.part(align)
        if out["identity_g4"]["state"] == "error": out["contradictions"] = {"state": "error", "why": "identity did not run on this article: " + out["identity_g4"]["why"], "n": 0}; ms["contradictions"] = 0.0
        else:
            ce = ctx.get("ce") or []; ms["contradictions"] = round(ctx.get("cms", 0.0), 2); ms["identity_g4"] = round(ms["identity_g4"] - ms["contradictions"], 2)
            out["contradictions"] = {"state": "ran" if ce else "empty", "why": None if ce else "no contradicting pair inside the window", "n": len(ce), "kinds": dict(collections.Counter(e.get("kind") for e in ce)), "store_edges": sum(1 for e in self.G.g4.edges.values() if e["via"] == "contradiction"),
                                     "edges": [{k: e.get(k) for k in ("a", "b", "kind", "note", "sources")} for e in ce][:12], "label": "g4_align.contradict_edges (window 7 days, polarity and rise/fall), structural truth only", "provisional": PROVISIONAL}
        ms["total"] = round(sum(v for k, v in ms.items() if k != "total"), 2); out["ms"] = ms
        return out
def main():
    tr = trace_dir(sys.argv[1]); lim = arg("--limit", None, int); start = arg("--start", 0, int); cap = arg("--cap-min", CAP_S_DEFAULT / 60, float) * 60; g4 = arg("--g4-dir") or os.environ.get("LT_V4_G4_DIR") or os.path.join(tr, "g4")
    cap = min(cap, 3600.0); sj = os.path.join(tr, "slow.jsonl"); sr = os.path.join(tr, "slow_run.json"); t_start = time.time(); deadline = t_start + cap
    allr = lines_of(tr)[start:]; ids = allr[:lim] if lim else allr
    done = set()
    if os.path.exists(sj):
        for ln in open(sj, encoding="utf-8"):
            if ln.strip():
                try: done.add(json.loads(ln)["id"])
                except Exception: pass
    prev = json.load(open(sr)) if os.path.exists(sr) else {}; summ = {"version": VERSION, "trace": tr, "pid": os.getpid(), "cmd": " ".join(sys.argv), "state": "starting", "start_epoch": t_start, "cap_s": cap, "deadline_epoch": deadline, "g4_dir": g4, "target_ids": len(ids), "resumed_ids": len([1 for _, l in ids if l["id"] in done]),
                                                                                                                 "runs": (prev.get("runs") or 0) + 1, "provisional": PROVISIONAL}
    atomic(sr, summ)
    def wd():   # hard stop: the loop checks the deadline between ids, this covers a stuck call
        time.sleep(cap + 90); summ.update(state="cap_hard_exit", now_epoch=time.time()); atomic(sr, summ); os._exit(3)
    threading.Thread(target=wd, daemon=True).start()
    S = None; stop = {"v": False}; signal.signal(signal.SIGTERM, lambda *a: stop.update(v=True))
    try:
        S = Slow(tr, g4, cap)
    except Exception as e:
        summ.update(state="error", why="%s: %s" % (type(e).__name__, str(e)[:300]), now_epoch=time.time()); atomic(sr, summ); raise
    summ.update(state="running", load_s=S.load_s, heads_load_s=S.heads_load_s, heads_loaded=S.heads is not None, heads_error=S.heads_err, check_against_lean=S.lean); atomic(sr, summ)
    for sq, l in lines_of(tr): S.seqmap[sq] = {"id": l["id"], "title": l["title"], "publisher": l["source"]}   # every traced line of the window, so a story root (of_seq) resolves on a resumed or offset run
    per = collections.defaultdict(list); states = collections.defaultdict(collections.Counter); n_new = 0; f = open(sj, "a", encoding="utf-8"); dirs = collections.Counter(); ctr_edges = 0; last_w = 0.0
    def write(state):
        nonlocal last_w
        summ.update(state=state, now_epoch=time.time(), elapsed_s=round(time.time() - t_start, 1), done_new=n_new, done_total=len(done), ms_p50={k: pct(v, 0.5) for k, v in per.items()}, ms_p90={k: pct(v, 0.9) for k, v in per.items()}, part_states={k: dict(v) for k, v in states.items()},
                    direction_story=dict(dirs), contradiction_edges_new=ctr_edges, g4_counts=(S.G.g4.counts() if S.G.g4 is not None else None), slow_jsonl=sj, keys=list(KEYS)); atomic(sr, summ); last_w = time.time()
    state = "done"
    try:
        for sq, l in ids:
            if l["id"] in done: continue
            if stop["v"]: state = "stopped"; break
            if time.time() >= deadline: state = "cap"; break
            o = S.one(sq, l); f.write(json.dumps(o, ensure_ascii=False, sort_keys=True) + "\n"); f.flush(); os.fsync(f.fileno()); done.add(l["id"]); n_new += 1
            for k in KEYS: states[k][o[k].get("state")] += 1
            for k, v in (o.get("ms") or {}).items(): per[k].append(v)
            dirs[(o["direction"].get("story_direction") or "unknown")] += 1; ctr_edges += o["contradictions"].get("n", 0) or 0
            if time.time() - last_w >= 5: write("running")
    except Exception as e:
        summ["why"] = "%s: %s" % (type(e).__name__, str(e)[:300]); write("error"); raise
    write(state); print("slow_clock %s: %d new ids (%d total) in %.0f s, pid %d, trace %s" % (state, n_new, len(done), time.time() - t_start, os.getpid(), tr))
if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    main()
