"""live_trace_v4: the chain stages added to live_trace.py by contract live-trace-v4 (T172, owner yes L2870, design L2869; schema live_trace_schema_v4.json, v3 stays untouched).
Five stages run AFTER the v3 stages and the story-key journal step, in this switch-on order, each behind its own env flag (LT_V4_<NAME>=1), default OFF until its gate passed (numbers in the ledger):
  journal         journal_durable  the durable journal write (journal.Durable, append-only JSONL, fsync per item) counted in the line's time; flag off = the v3 behaviour (durable only when JOURNAL_DIR is set, not timed)
  fewnerd         ner_fewnerd      Few-NERD v1 entity types (fewnerd_typing.py, 66 fine types), one pass per article
  claims          claims_v1        claims v1 (claims_units.py / claims_v1.py, lg dependency rules), one parse per article
  identity        identity_g4      the page's record builder (raw_core.build_rec) + merge rule + G4 alignment (g4_align.align): entity identity, assertions, hierarchy and relation edges, on a chain-owned graph
  contradictions  contradictions   g4_align.contradict_edges inside the identity step (needs identity); its time is booked here, not in identity_g4
A flag that is off is recorded with a why, so every v4 line has all five stages: state "deferred" (why "slow clock") for the stages the slow clock computes after the window (claims_v1, identity_g4, contradictions; T158 plan 1a, LT_SLOW_CLOCK=0 turns this off), state not_attached (the v3 pattern, OFF_WHY) for the rest. Nothing here changes a v3 stage: trace() is untouched, this module only appends.
The page (simulation/raw-units.py) imports the same modules (raw_core, fewnerd_typing, claims_units, g4_align, journal), so the page and the chain run the same code. CPU only, no hosted calls."""
import os, time, json, collections, pathlib
HERE = pathlib.Path(__file__).resolve().parent
FLAGS = ("journal", "fewnerd", "claims", "identity", "contradictions")   # switch-on order
DEFAULT_ON = {"journal": True, "fewnerd": True, "claims": False, "identity": False, "contradictions": False}   # a flag turns ON by default only after its gate passed (replay match + p90 <= 600 ms on the warm timing run). 2026-11-21 wave 1: journal (p90 541) and fewnerd (551) passed and are ON; claims failed (676), identity and contradictions stay OFF (identity goes to the slow clock). Ledger T158 / T172
STAGE = {"journal": "journal_durable", "fewnerd": "ner_fewnerd", "claims": "claims_v1", "identity": "identity_g4", "contradictions": "contradictions"}
META = {"journal_durable": ("G4", "tool", "Observed"), "ner_fewnerd": ("G2", "model", "Inferred"), "claims_v1": ("G2", "tool", "Inferred"), "identity_g4": ("G4", "tool", "Inferred"), "contradictions": ("G4", "tool", "Candidate")}
VERSION = {"journal_durable": "journal.py Durable (journal-v0 keys, MIRROR_RULE on)", "ner_fewnerd": "fewnerd_typing.py + runs/pulse/names_fewnerd_v2 (test F1 coarse 0.713 / fine 0.566)", "claims_v1": "claims_units.py + claims_v1.py (en_core_web_lg 3.8.0, CaRB F1 0.557 in-house scorer)",
           "identity_g4": "raw_core.build_rec + g4_align.align (G4/G5 v1, unmeasured)", "contradictions": "g4_align.contradict_edges (window 7 days, polarity and rise/fall)"}
OFF_WHY = {"journal": "flag LT_V4_JOURNAL=0 for this run (default is on since 2026-11-21, L2898): the story-key journal runs as in v3 (durable only when JOURNAL_DIR is set, and not timed); source journal.py Durable",
           "fewnerd": "flag LT_V4_FEWNERD=0 for this run (default is on since 2026-11-21, L2898): Few-NERD typing is not run in this window; source fewnerd_typing.py, model runs/pulse/names_fewnerd_v2",
           "claims": "flag LT_V4_CLAIMS is off and no slow clock is configured (LT_SLOW_CLOCK=0): claims v1 is not computed in this window (p90 676 ms against the 600 ms budget, L2898); source claims_units.py, claims_v1.py",
           "identity": "flag LT_V4_IDENTITY is off and no slow clock is configured (LT_SLOW_CLOCK=0): G4 alignment is not computed in this window; source raw_core.py, g4_align.py",
           "contradictions": "flag LT_V4_CONTRADICTIONS is off and no slow clock is configured (LT_SLOW_CLOCK=0): contradiction edges are not computed in this window; source g4_align.py contradict_edges"}
CODE_FILES = ("live_trace_schema_v4.json", "live_trace_v4.py", "raw_core.py", "claims_units.py", "claims_v1.py", "fewnerd_typing.py", "g4_align.py")   # hashed into run.json file_sha (drift check) beside live_trace.py
SLOW_STAGES = ("claims", "identity", "contradictions")   # the stages the slow clock runs per finished window (latency over the 600 ms budget, L2898); output is PROVISIONAL there
SLOW_CLOCK = os.environ.get("LT_SLOW_CLOCK", "1") != "0"   # slow clock configured (default): an off slow stage is "deferred", not "not_attached"
SLOW_DETAIL = {"claims": "claims v1 is computed after the window by the slow clock (chain p90 676 ms against the 600 ms budget, L2898); output PROVISIONAL",
               "identity": "entity identity and G4 alignment are computed after the window by the slow clock (+600 to 760 ms in the chain, L2898); output PROVISIONAL",
               "contradictions": "contradiction edges are computed after the window by the slow clock, inside the identity pass (needs identity); output PROVISIONAL"}
def env_name(f): return "LT_V4_" + f.upper()
def read_flags(env=None):
    """{flag: bool} from the environment (LT_V4_JOURNAL=1 ...), falling back to DEFAULT_ON"""
    env = os.environ if env is None else env
    return {f: (env[env_name(f)] == "1") if env_name(f) in env else DEFAULT_ON[f] for f in FLAGS}
def default_journal_dir(): return os.environ.get("JOURNAL_DIR") or str(HERE / "runs" / "journal")
def cap(out, limit=700):
    if out is not None and len(json.dumps(out, ensure_ascii=False)) > limit: return {"truncated": True, "head": json.dumps(out, ensure_ascii=False)[:limit - 140]}
    return out
class V4:
    """per-Chain state of the v4 stages: the flags, the Few-NERD / claims results of the current article, the chain's own G4 graph (identity), the seq -> article map for story roots"""
    def __init__(self, ch, flags=None, g4_dir=None, budget=None, slow_ms=2000):
        self.ch = ch; self.on = dict(flags or read_flags()); self.slow_ms = slow_ms; self.budget = budget; self.G = None; self.seqmap = {}; self.g4_dir = g4_dir if g4_dir is not None else os.environ.get("LT_V4_G4_DIR")
        if self.on["contradictions"] and not self.on["identity"]: self.on["contradictions"] = False; self.forced_off = "contradictions needs identity"
        else: self.forced_off = None
    def active(self): return [f for f in FLAGS if self.on[f]]
    def run_block(self):
        """the run.json block: contract, the flags this run used, the defaults, the stage names, where the chain's G4 store lives"""
        return {"contract": "live-trace-v4", "flags": dict(self.on), "defaults": dict(DEFAULT_ON), "env": {f: env_name(f) for f in FLAGS}, "stages": [STAGE[f] for f in FLAGS], "g4_store": self.g4_dir or "in memory (LT_V4_G4_DIR unset)", "forced_off": self.forced_off, "slow_clock": {"configured": SLOW_CLOCK, "env": "LT_SLOW_CLOCK", "stages": [STAGE[f] for f in SLOW_STAGES], "state_when_off": "deferred" if SLOW_CLOCK else "not_attached"}}
    def warm(self):
        """load what the active flags need before the first article, so the first line does not carry a model load (the load time is the run's load_s)"""
        if self.on["fewnerd"]:
            import fewnerd_typing as FNT; FNT.fn_nlp()
        if self.on["claims"] or self.on["identity"]:
            import claims_units as CU; CU.claims_nlp()
        if self.on["identity"]:
            import raw_core as RC; RC.lg_nlp(); self._graph()
    def _graph(self):
        if self.G is None:
            import raw_core as RC
            self.G = RC.Graph(dur_dir=self.g4_dir, durable=bool(self.g4_dir), ledger=False); RC.set_chain(ch=self.ch)   # in memory unless LT_V4_G4_DIR names a folder; no resource ledger in the chain
        return self.G
    def post(self, line, text, full, row, d, jms=0.0, own_seq=None):
        """append the five stages to a traced line (line["stages"]) and update total_ms / over_budget; d = the journal's classify result (kind, of_seq, publishers), jms = what the journal write cost, own_seq = the key under which of_seq numbers this item.
        Returns nothing; skipped lines get no v4 stages."""
        if line.get("state") != "traced": return
        st = line["stages"]; ctx = {}
        def add(f, state, out, n, ms, why=None, fullout=None):
            nm = STAGE[f]; g, k, pv = META[nm]
            st.append({"name": nm, "gate": g, "kind": k, "version": VERSION[nm] if state != "not_attached" else None, "state": state, "out": cap(out), "n": n, "ms": round(ms, 2), "provenance": pv if state != "not_attached" else None, "why": why})
            full[nm] = fullout if fullout is not None else out
            if ms > self.slow_ms: st[-1]["slow"] = True
        def na(f, why=None):
            if SLOW_CLOCK and f in SLOW_STAGES and not self.on[f]: return defer(f)
            add(f, "not_attached", None, None, 0.0, why or OFF_WHY[f], None)
        def defer(f):   # T158 plan 1a: the slow clock owns this stage; the chain records that, with the version of the code that will run
            nm = STAGE[f]; g, k, pv = META[nm]; o = {"deferred_to": "slow clock", "marker": "PROVISIONAL", "detail": SLOW_DETAIL[f]}
            st.append({"name": nm, "gate": g, "kind": k, "version": VERSION[nm], "state": "deferred", "out": o, "n": None, "ms": 0.0, "provenance": None, "why": "slow clock"}); full[nm] = o
        def guard(f, fn):
            t0 = time.perf_counter()
            try: r = fn()
            except Exception as e: add(f, "error", None, None, (time.perf_counter() - t0) * 1000, "%s: %s" % (type(e).__name__, str(e)[:200])); return None
            ms = (time.perf_counter() - t0) * 1000 - r.get("ms_off", 0.0); add(f, r["state"], r["out"], r["n"], ms, r.get("why"), r.get("full")); return r
        # --- journal
        if self.on["journal"]: add("journal", "ran", {"kind": d["kind"], "publishers": d["publishers"], "durable": True}, 1, jms)
        else: na("journal")
        # --- Few-NERD
        if self.on["fewnerd"]:
            def fn():
                import fewnerd_typing as FNT
                fe = FNT.fn_ents(text); ctx["fents"] = fe; o = FNT.summary(fe)
                return {"state": "ran" if fe else "empty", "out": o, "n": len(fe), "why": None if fe else "no entity found", "full": {**o, "mentions": [[l, a, b] for l, a, b in fe][:200]}}
            guard("fewnerd", fn)
        else: na("fewnerd")
        # --- claims v1
        if self.on["claims"]:
            def cl():
                import claims_units as CU
                c = CU.extract_claims(text); ctx["claims"] = c; o = CU.summary(c)
                return {"state": "ran" if c else "empty", "out": o, "n": len(c), "why": None if c else "no claim found", "full": {**o, "items": [{k: x.get(k) for k in ("s", "s_short", "p", "o", "attrs", "neg", "modal", "attrib", "passive", "said_by", "rule", "v_span")} for x in c[:80]]}}
            guard("claims", cl)
        else: na("claims")
        # --- identity (+ contradictions inside it)
        if self.on["identity"]:
            def ident():
                import raw_core as RC, g4_align as G4
                G = self._graph(); own = own_seq if own_seq is not None else len(self.seqmap)
                rec = {"read": {}, "text": text, "title_len": len(line["title"]), "id": row[0], "publisher": row[2], "title": line["title"], "url": line["url"], "published": row[6], "state": "traced", "skip_reason": None, "total_ms": line.get("total_ms"),
                       "story": {"kind": d["kind"], "publishers": d["publishers"], "of": self.seqmap.get(d["of_seq"]), "seq": own}, "stage_out": {s_["name"]: {"state": s_["state"], "n": s_["n"], "why": s_["why"], "out": s_["out"]} for s_ in st}}
                self.seqmap[own] = {"id": row[0], "title": line["title"], "publisher": row[2]}
                pre = {k: ctx[k] for k in ("fents", "claims") if k in ctx}
                with G.lock:
                    RC.build_rec(self.ch, line, text, full, rec, fewnerd=self.on["fewnerd"], claims=self.on["claims"], pre=pre); RC.merge_units(rec, None, G, self.ch)
                    G4.align(rec, G, self.ch, contradictions=self.on["contradictions"])
                g = rec["g4"]; ev = collections.Counter(e["via"] for e in g["edges"]); mr = collections.Counter((u.get("merge") or {}).get("result") for u in rec["units"] if u.get("merge"))
                ctx["g4"] = g; S = G.g4; cn = S.counts()
                o = {"units": len(rec["units"]), "entities": len(g["entities"]), "assertions": len(g["assertions"]), "edges": len(g["edges"]), "alias_merges": g["alias_merges"], "merge": dict(sorted((k, v) for k, v in mr.items() if k)), "store": {k: cn[k] for k in ("articles", "entities", "assertions", "edges", "nodes")}}
                return {"state": "ran" if g["entities"] or g["assertions"] else "empty", "out": o, "n": len(g["entities"]) + len(g["assertions"]), "why": None if (g["entities"] or g["assertions"]) else "no entity or assertion aligned",
                        "full": {**o, "g4_ms": g["ms"], "edges_by_via": dict(sorted(ev.items())), "graph": g["graph"], "story": g["story"], "entities_list": [{k: e.get(k) for k in ("id", "type", "canon", "fine", "articles")} for e in g["entities"]][:120], "assertions_list": [{k: a.get(k) for k in ("id", "key", "kind", "subj", "pred", "obj")} for a in g["assertions"]][:120]},
                        "ms_off": g.get("contradictions_ms", 0.0) if self.on["contradictions"] else 0.0}
            r = guard("identity", ident)
            if self.on["contradictions"]:
                g = ctx.get("g4")
                if r is None or g is None: add("contradictions", "not_attached", None, None, 0.0, "identity did not run on this article", None)
                else:
                    ce = [e for e in g["edges"] if e["via"] == "contradiction"]; o = {"edges": len(ce), "kinds": dict(collections.Counter(e.get("kind") for e in ce)), "store_edges": sum(1 for e in self.G.g4.edges.values() if e["via"] == "contradiction"), "window_days": 7}
                    add("contradictions", "ran" if ce else "empty", o, len(ce), g.get("contradictions_ms", 0.0), None if ce else "no contradicting pair inside the window", {**o, "edges": [{k: e.get(k) for k in ("a", "b", "kind", "note", "sources")} for e in ce][:20]})
            else: na("contradictions")
        else:
            na("identity"); na("contradictions", "needs identity (flag LT_V4_IDENTITY is off)" if self.on["contradictions"] or self.forced_off else None)   # with the slow clock configured both come out deferred (na() above)
        line["total_ms"] = round(sum(s["ms"] for s in st), 2)
        if self.budget is not None: line["over_budget"] = line["total_ms"] > self.budget
        return line
