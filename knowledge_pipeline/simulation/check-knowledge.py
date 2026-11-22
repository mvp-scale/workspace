"""check-knowledge: the fast gate for the Knowledge step (T158, knowledge plan section 3, owner yes L2936). PROVISIONAL (L2901): weak numbers are reported, never blocked; only STRUCTURAL assertions fail.
Runs on the two offline fixtures of build-knowledge-fixture.py (simulation/fixtures/knowledge/<area>/trace: c1 = Fiona the hippo, mix = Gulf strikes + energy bills), each copied into a scratch dir. No live stage (check-flow proves the chain); this gate proves knowledge. Schema: projects/world-state/KNOWLEDGE_SCHEMA.md.
  K1 slow         slow_clock.py on the scratch copy (fresh g4/store.jsonl): records = articles, identity_g4 and contradictions keys on each, 0 error states
  K2 consolidate  slow_consolidate.py --trace <scratch> --g4 <scratch>/g4/store.jsonl: the 6 files incl. knowledge.json (schema keys, observations == articles); counters new / reinforced > 0 on c1, new > 0 and bridging > 0 on mix (contested is a maturity number since the time-aware status rule: c1 honestly has 0 pairs, the rule is proven on K8's synthetic control)
  K3 evidence     every counter's evidence list resolves (edge ids in 'edges', capability ids in 'capabilities'), n == len(evidence), every edge has >= 1 fragment with art + pub + sent: 100 percent
  K4 identity     wrong-merge controls on the g4 store = 0 (no entity with two ISO ids / two Wikidata qids / two distinct surnames) and merged_how present on every cross-article merge
  K5 answer       educate.py --auto: one answer, >= 3 statements, every ref resolvable, a publisher count on each statement (knowledge.json 'answer' is checked the same way when present)
  K6 determinism  K2 run a second time into another folder: equal sha256 on all 6 sealed files
  K7 feed         raw-units.py knowledge(src="trace:<scratch>") (the page feed of /api/raw/knowledge): exists, a 'knowledge' block with as_of, counters, funnel, growth, yield equal to knowledge.json, every article named
  K8 join         the fact-join fix (T158 L2954, KNOWLEDGE_SCHEMA join / anchor / independent / slot / contested). (a) join block: slots == funnel.assertions == len(edges), merge_rate == round(1 - slots/facts_raw, 4), every slot n == len(members) >= 2 with min_pair_prob >= threshold, member ids distinct across slots,
                  strength == independent.n == distinct source publishers, counters.reinforced.evidence == edges with strength >= 2, mode is not the lemma fallback when sentence_transformers imports; (b) independence: no two sources of different publishers on one reinforced edge with near-identical sentences (consolidate.sent_sig, Jaccard >= 0.7 on >= 8 tokens), every fragment has a publisher, every source's publisher is one of its own fragments';
                  (c) contested: a != b, both in edges, same anchor, earlier.day <= later.day (ISO), kind in polarity / amount / status / direction, reversal on status, counters.contested.n == distinct sides, kept + sum(dropped) == contradiction edges in the g4 store; (d) synthetic control of g4_align.contradict_edges (care -> die = 0 edges, die -> care = 1 status edge with order.reversal, undated = 0),
                  neg_in_scope (unable ... so hand-milked = False, did not survive = True, Despite = False) and slow_consolidate.contested_pairs (kept / timeline / unordered / cross_anchor / self_pair on a 2-edge store); (e) ECB+ fixture fixtures/knowledge/ecbplus-join.json (Apache-2.0, test split): fact_join.py --eval F1 >= 0.49 (measured 0.5133), P and R > 0; run once per check, shared by the areas
    /workspace/models/embed-zs/.venv/bin/python simulation/check-knowledge.py [--area c1,mix] [--only K1,K2,...] [--keep]
MATURITY numbers (pct reinforced, contested per 100, bridging, answerable, identity pairs resolved / conflicts, merge rate, collapsed wire copies, contested kept / dropped) are printed on the K2 / K4 / K5 / K8 lines, never gated. One PASS / FAIL line per step and area with the numbers asserted, then the total; exit 1 on any FAIL. A step whose input is missing FAILs with the reason (never silently skipped); a failed K1 or K2 makes later steps of that area FAIL as 'needs K1' / 'needs K2'.
CPU only, offline, no hosted call, no queue write, no service touched; decider.py, lean/, live_trace*.py, slow_clock.py, chain_windows.py are not edited (slow_clock asserts check_against_lean() == 160, shown on K1). Target under 120 s per area (seconds shown; the join loads e5-small-v2, so K2 and K6 take ~45 s each and the OVER 120 tag is informational), K8 under 40 s per area plus the shared ~18 s ECB+ eval. Scratch = a temp dir, removed at exit (--keep leaves it and prints the path)."""
import sys, os, re, json, time, shutil, hashlib, tempfile, subprocess, collections, itertools
HERE = os.path.dirname(os.path.abspath(__file__)); KP = os.path.dirname(HERE); WS = os.path.join(KP, "projects", "world-state")
FIXROOT = os.path.join(HERE, "fixtures", "knowledge"); PYNP = "/workspace/models/embed-zs/.venv/bin/python"; PY = PYNP if os.path.exists(PYNP) else sys.executable
ENV = {**os.environ, "PYTHONHASHSEED": "0", "CUDA_VISIBLE_DEVICES": "", "WORLD_GPU": "0", "HF_HUB_OFFLINE": "1", "THREADS": "4", "TOKENIZERS_PARALLELISM": "false"}
SEALED = ("consolidated.json", "evolved.json", "resource_state.json", "truth.json", "educate_index.json", "knowledge.json")
KEYS = ("as_of", "window", "articles", "publishers", "counters", "edges", "contested", "capabilities", "funnel", "growth", "yield", "provisional")
COUNTERS = ("new", "reinforced", "contested", "bridging"); FUNNEL = ("observations", "fragments", "assertions", "reinforced", "contested", "capabilities", "bridging", "concepts")
FEED = ("as_of", "counters", "funnel", "growth", "yield")
args = sys.argv[1:]; KEEP = "--keep" in args
ONLY = set(args[args.index("--only") + 1].upper().split(",")) if "--only" in args else None
AREAS = args[args.index("--area") + 1].lower().split(",") if "--area" in args else ["c1", "mix"]
class Fail(Exception): pass
def need(cond, msg, bad):
    if not cond: bad.append(msg)
    return cond
def run(cmd, timeout):
    try: r = subprocess.run(cmd, capture_output=True, text=True, cwd=WS, env=ENV, timeout=timeout); return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired as e: return -9, (e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")), "timeout after %d s" % timeout
def tail(so, se, n=300): return (se or so or "")[-n:].replace("\n", " ")
def jl(p): return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
def jload(p): return json.load(open(p, encoding="utf-8"))
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def slow_rec(o):
    if isinstance(o.get("line"), str):
        try: return json.loads(o["line"])
        except Exception: pass
    return o
class Ctx:
    """one area: its scratch window, its fixture ids, what earlier steps produced"""
    def __init__(self, key, root):
        self.key = key; self.fix = os.path.join(FIXROOT, key, "trace"); self.S = os.path.join(root, key); self.tr = os.path.join(self.S, "trace")
        self.g4 = os.path.join(self.tr, "g4", "store.jsonl"); self.od = os.path.join(self.tr, "slow_consolidate"); self.ids = []; self.k = None; self.edges = {}
    def know(self):
        if self.k is None:
            p = os.path.join(self.od, "knowledge.json")
            if not os.path.exists(p): raise Fail("needs K2: no knowledge.json in %s" % os.path.relpath(self.od, self.S))
            self.k = jload(p); self.edges = self.k.get("edges") or {}
        return self.k
# ---------------------------------------------------------------- K1
def k1(C):
    if not os.path.isdir(C.fix): raise Fail("fixture %s missing (run build-knowledge-fixture.py)" % os.path.relpath(C.fix, KP))
    os.makedirs(C.S, exist_ok=True); shutil.copytree(C.fix, C.tr, dirs_exist_ok=True)
    C.ids = [json.loads(r["line"])["id"] for r in jl(os.path.join(C.tr, "chain.jsonl"))]; n = len(C.ids); bad = []
    rc, so, se = run([PY, "slow_clock.py", C.S, "--cap-min", "6"], 400); sj = os.path.join(C.tr, "slow.jsonl")
    if rc != 0 or not os.path.exists(sj): raise Fail("slow_clock failed (rc %s): %s" % (rc, tail(so, se)))
    recs = [slow_rec(o) for o in jl(sj)]; sr = jload(os.path.join(C.tr, "slow_run.json"))
    need(len(recs) == n, "%d slow records, want %d (articles)" % (len(recs), n), bad)
    need(len({o.get("id") or o.get("seq") for o in recs}) == len(recs), "duplicate slow records", bad)
    miss = sum(1 for o in recs if "identity_g4" not in o or "contradictions" not in o); need(miss == 0, "%d records without identity_g4 / contradictions" % miss, bad)
    errs = sum(1 for o in recs for k in ("identity_g4", "contradictions", "claims", "direction", "change", "function_p", "factuality_p") if isinstance(o.get(k), dict) and o[k].get("state") == "error")
    need(errs == 0, "%d error states" % errs, bad); need(sr.get("state") == "done", "slow_run state %s" % sr.get("state"), bad); need(sr.get("check_against_lean") == 160, "check_against_lean %s" % sr.get("check_against_lean"), bad)
    need(os.path.exists(C.g4), "no g4/store.jsonl written", bad)
    if bad: raise Fail("; ".join(bad))
    return "%d records (= %d articles), identity_g4 + contradictions on each, %d error, lean %s, g4 store yes" % (len(recs), n, errs, sr.get("check_against_lean"))
# ---------------------------------------------------------------- K2
def consolidate(C, out):
    return run([PY, "slow_consolidate.py", "--trace", C.tr, "--g4", C.g4, "--out", out], 300)
def k2(C):
    if not os.path.exists(os.path.join(C.tr, "slow.jsonl")) or not os.path.exists(C.g4): raise Fail("needs K1: no slow.jsonl / g4 store in the scratch window")
    bad = []; rc, so, se = consolidate(C, C.od)
    if rc != 0: raise Fail("slow_consolidate failed (rc %s): %s" % (rc, tail(so, se)))
    have = [f for f in SEALED if os.path.exists(os.path.join(C.od, f))]
    if len(have) < len(SEALED): raise Fail("output files %d of %d (missing %s)" % (len(have), len(SEALED), sorted(set(SEALED) - set(have))))
    k = C.know(); n = len(C.ids)
    miss = [x for x in KEYS if x not in k]; need(not miss, "knowledge.json keys missing %s" % miss, bad)
    mc = [c for c in COUNTERS if not isinstance((k.get("counters") or {}).get(c), dict) or "evidence" not in k["counters"][c]]; need(not mc, "counters without evidence list: %s" % mc, bad)
    mf = [f for f in FUNNEL if f not in (k.get("funnel") or {})]; need(not mf, "funnel keys missing %s" % mf, bad)
    cons = jload(os.path.join(C.od, "consolidated.json")); obs = len(cons.get("observations") or [])
    need(obs == n and (k.get("articles") == n), "observations %s / knowledge articles %s, want %d" % (obs, k.get("articles"), n), bad)
    need(k.get("provisional") is True, "provisional is not true", bad)
    cn = {c: ((k.get("counters") or {}).get(c) or {}).get("n", 0) for c in COUNTERS}
    for c in (("new", "reinforced") if C.key == "c1" else ("new", "bridging") if C.key == "mix" else ("new",)): need(cn[c] > 0, "counter %s = %s, want > 0" % (c, cn[c]), bad)   # contested: maturity only (time-aware rule, proven on K8 (d))
    y = k.get("yield") or {}
    if bad: raise Fail("; ".join(bad))
    return "%d files, articles %d, new %d, reinforced %d, contested %d, bridging %d | maturity: reinforced %s%%, contested/100 %s, bridging %s, answerable %s" % (len(have), n, cn["new"], cn["reinforced"], cn["contested"], cn["bridging"], y.get("pct_reinforced"), y.get("contested_per_100"), y.get("bridging"), y.get("answerable"))
# ---------------------------------------------------------------- K3
def frag_ok(f): return isinstance(f, dict) and all(str(f.get(x) or "").strip() for x in ("art", "pub", "sent"))
def k3(C):
    k = C.know(); bad = []; E = C.edges; caps = {c.get("id") for c in k.get("capabilities") or []}; arts = set(C.ids); total = bad_n = 0; frag_bad = set(); art_bad = 0
    for cname in COUNTERS:
        c = (k.get("counters") or {}).get(cname) or {}; ev = c.get("evidence") or []; need(c.get("n") == len(ev), "%s n %s != %d evidence ids" % (cname, c.get("n"), len(ev)), bad)
        pool = caps if cname == "bridging" else E
        for i in ev:
            total += 1
            if i not in pool: bad_n += 1
            elif cname != "bridging":
                frs = E[i].get("fragments") or []
                if not frs or not all(frag_ok(f) for f in frs): frag_bad.add(i)
                art_bad += sum(1 for f in frs if f.get("art") not in arts)
    need(bad_n == 0, "%d of %d evidence ids do not resolve" % (bad_n, total), bad); need(not frag_bad, "%d edges without a complete fragment (art + pub + sent), e.g. %s" % (len(frag_bad), sorted(frag_bad)[:2]), bad)
    need(art_bad == 0, "%d fragments name an article outside the window" % art_bad, bad)
    for p in k.get("contested") or []: need(p.get("a") in E and p.get("b") in E, "contested pair %s/%s not in edges" % (p.get("a"), p.get("b")), bad)
    if bad: raise Fail("; ".join(bad))
    return "%d evidence ids across %s counters resolve (100%%), %d edges each with art + pub + sent fragments" % (total, len(COUNTERS), len(E))
# ---------------------------------------------------------------- K4
def nrm(s): return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", re.sub(r"['\u2019]s\b", "", str(s).lower()))).strip()
def k4(C):
    if not os.path.exists(C.g4): raise Fail("needs K1: no g4 store")
    sys.path.insert(0, WS); import consolidate as CO
    S = CO.load_g4(C.g4); ent = S["ent"]; bad = []; wrong = []
    owners = collections.defaultdict(set)   # alias -> iso entity ids that own it
    for eid, r in ent.items():
        if str(eid).startswith("iso:"):
            for a in (r.get("aliases") or {}): owners[nrm(a)].add(eid)
    iso2 = {a: sorted(o) for a, o in owners.items() if a and len(o) > 1}
    if iso2: wrong.append("alias owned by two ISO entities: %s" % list(iso2.items())[:2])
    nq = 0
    for eid, r in ent.items():
        q = set(re.findall(r"\bQ\d+\b", json.dumps({k: v for k, v in r.items() if k in ("qid", "qids", "wd", "wikidata", "geo", "wikidata_id")}, default=str)))
        nq += len(q)
        if len(q) > 1: wrong.append("%s has two Wikidata qids %s" % (eid, sorted(q)))
        if r.get("type") == "person":
            last = {nrm(a).split()[-1] for a in (r.get("aliases") or {}) if len(nrm(a).split()) >= 2}
            if len(last) > 1: wrong.append("%s has distinct surnames %s" % (eid, sorted(last)))
        isos = {x for x in (r.get("iso") if isinstance(r.get("iso"), list) else [r.get("iso")]) if x}
        if len(isos) > 1: wrong.append("%s has two ISO codes %s" % (eid, sorted(isos)))
    need(not wrong, "%d wrong-merge controls hit: %s" % (len(wrong), "; ".join(wrong[:3])), bad)
    merged = [e for e, r in ent.items() if len(r.get("arts") or {}) >= 2 and len({nrm(a) for a in (r.get("aliases") or {})} - {""}) >= 2 and not str(e).startswith("iso:")]
    nomh = [e for e in merged if not ent[e].get("merged_how")]; withmh = sum(1 for r in ent.values() if r.get("merged_how"))
    need(not nomh, "%d of %d cross-article merges without merged_how, e.g. %s" % (len(nomh), len(merged), nomh[:3]), bad)
    tp = os.path.join(C.od, "truth.json"); idn = (jload(tp).get("identity") or {}) if os.path.exists(tp) else {}
    if bad: raise Fail("; ".join(bad))
    return "%d entities, wrong-merge controls 0 (iso, qid, surname), merged_how on %d entities, %d cross-article merges all with merged_how | maturity: identity pairs resolved %s, conflicts %s" % (len(ent), withmh, len(merged), idn.get("pairs_resolved"), idn.get("conflicts"))
# ---------------------------------------------------------------- K5
def statements(o):
    """every dict with a 'refs' list, anywhere in an answer"""
    out = []
    if isinstance(o, dict):
        if isinstance(o.get("refs"), list): out.append(o)
        for v in o.values(): out += statements(v)
    elif isinstance(o, list):
        for v in o: out += statements(v)
    return out
def ref_ok(r, C):
    if isinstance(r, str): return r in C.edges
    if isinstance(r, dict):
        if "edge" in r and r["edge"] in C.edges: return True
        return str(r.get("art") or "") in set(C.ids) and bool(str(r.get("pub") or "").strip())
    return False
def judge_answer(a, C, label, bad):
    st = statements(a); q = a.get("question") if isinstance(a, dict) else None
    need(len(st) >= 3, "%s: %d statements, want >= 3" % (label, len(st)), bad)
    nrefs = sum(len(s["refs"]) for s in st); bad_refs = sum(1 for s in st for r in s["refs"] if not ref_ok(r, C))
    need(nrefs > 0 and bad_refs == 0, "%s: %d of %d refs do not resolve" % (label, bad_refs, nrefs), bad)
    nopub = sum(1 for s in st if not isinstance(s.get("publishers", s.get("publishers_n")), int)); need(nopub == 0, "%s: %d statements without a publisher count" % (label, nopub), bad)
    return len(st), nrefs, q
def k5(C):
    k = C.know(); bad = []
    rc, so, se = run([PY, "educate.py", "--auto", "--consolidated", os.path.join(C.od, "consolidated.json"), "--json"], 120)
    a = None
    if rc == 0:
        try: a = json.loads(so)
        except Exception: pass
    if a is None: raise Fail("educate.py --auto gave no JSON (rc %s): %s" % (rc, tail(so, se)))
    ns, nr, q = judge_answer(a, C, "educate --auto", bad)
    auto = (a.get("auto") is True) or ("auto" in json.dumps(a.get("question_kind", a.get("mode", ""))).lower()) or ("auto" in str(q).lower()) if isinstance(a, dict) else False
    need(bool(q), "no question on the answer", bad); need(auto, "answer question is not marked auto", bad)
    kinds = collections.Counter(s.get("kind") for s in statements(a) if s.get("kind"))
    if isinstance(k.get("answer"), dict) and k["answer"].get("statements"): judge_answer(k["answer"], C, "knowledge.json answer", bad)
    elif "answer" not in k: bad.append("knowledge.json has no 'answer' key")
    if bad: raise Fail("; ".join(bad))
    return "1 answer (auto), %d statements, %d refs all resolvable, publisher count on each | maturity: kinds %s, question %s" % (ns, nr, dict(kinds), str(q)[:60])
# ---------------------------------------------------------------- K6
def k6(C):
    C.know(); first = os.path.join(C.S, "slow_consolidate_first"); shutil.rmtree(first, ignore_errors=True); shutil.copytree(C.od, first)   # same --out both times: sealed files carry their own paths
    rc, so, se = consolidate(C, C.od)
    if rc != 0: raise Fail("second slow_consolidate failed (rc %s): %s" % (rc, tail(so, se)))
    bad = []
    for f in SEALED:
        a, b = os.path.join(first, f), os.path.join(C.od, f)
        if not os.path.exists(b): bad.append("%s missing on rerun" % f)
        elif sha(a) != sha(b): bad.append("%s differs (%s vs %s)" % (f, sha(a)[:8], sha(b)[:8]))
    if bad: raise Fail("; ".join(bad))
    return "%d sealed files equal sha256 on rerun (knowledge.json %s)" % (len(SEALED), sha(os.path.join(C.od, "knowledge.json"))[:12])
# ---------------------------------------------------------------- K7
K7_CHILD = r'''
import os, sys, json, importlib.util
os.environ["PYTHONHASHSEED"] = "0"; sys.path.insert(0, os.getcwd())
sp = importlib.util.spec_from_file_location("raw_units", sys.argv[1]); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
print("KNOW_JSON " + json.dumps(m.knowledge(src=sys.argv[2]), default=str, ensure_ascii=False))
'''
def k7(C):
    C.know(); bad = []; src = "trace:" + C.S
    rc, so, se = run([PY, "-c", K7_CHILD, os.path.join(HERE, "raw-units.py"), src], 240); j = [x for x in so.splitlines() if x.startswith("KNOW_JSON ")]
    if rc != 0 or not j: raise Fail("raw-units knowledge(src='trace:<scratch>') failed (rc %s): %s" % (rc, tail(so, se)))
    res = json.loads(j[0][10:]); blk = res.get("knowledge") if res.get("exists") else None
    if not isinstance(blk, dict): raise Fail("no knowledge block in the page feed: %s" % str(res.get("why"))[:300])
    miss = [x for x in FEED if x not in blk]; need(not miss, "knowledge block keys missing %s" % miss, bad)
    need(((blk.get("counters") or {}).get("new") or {}).get("n") == C.k["counters"]["new"]["n"], "feed counters.new differs from knowledge.json", bad)
    na = len(res.get("articles") or {}); need(na == len(C.ids), "feed names %d articles, want %d" % (na, len(C.ids)), bad)
    if bad: raise Fail("; ".join(bad))
    return "page feed knowledge(src=trace:<scratch>) has %s, counters equal knowledge.json, %d articles named (src=area:<key> builds a cache window with slow_clock, not run here)" % ("/".join(FEED), na)
# ---------------------------------------------------------------- K8
JOIN_F1_BAR = 0.49; KINDS = ("polarity", "amount", "status", "direction"); DAY_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$"); _JOIN = {}   # the ECB+ eval runs once per check (~18 s) and is shared by the areas
def ws_mod(name):
    if WS not in sys.path: sys.path.insert(0, WS)
    return __import__(name)
def join_eval():
    """fact_join.py --eval on the ECB+ fixture -> its JSON line (cached); a missing file or a bad run is a Fail (raised by every area)"""
    if "r" not in _JOIN:
        fj, fx = os.path.join(WS, "fact_join.py"), os.path.join(FIXROOT, "ecbplus-join.json"); r = None
        if not os.path.exists(fj): r = Fail("fact_join.py missing in projects/world-state")
        elif not os.path.exists(fx): r = Fail("ECB+ fixture missing: %s" % os.path.relpath(fx, KP))
        else:
            rc, so, se = run([PY, "fact_join.py", "--eval", fx], 400); j = [x for x in so.splitlines() if x.startswith("{")]
            try: r = json.loads(j[-1]) if rc == 0 and j else Fail("fact_join.py --eval failed (rc %s): %s" % (rc, tail(so, se)))
            except Exception as e: r = Fail("fact_join.py --eval gave no JSON line: %s" % e)
        _JOIN["r"] = r
    if isinstance(_JOIN["r"], Fail): raise _JOIN["r"]
    return _JOIN["r"]
def jacc(a, b): return len(a & b) / len(a | b)
def claim(i, subj, pred, status, art, key):
    return {"id": i, "kind": "claim", "subj": subj, "pred": pred, "obj": None, "obj_text": None, "status": status, "key": key, "evid": [{"art": art, "pub": "P-" + art, "independent": True, "attrs": {"polarity": "positive", "place": None, "time": [], "modality": "asserted"}}]}
def synthetic(C, bad):
    """(d) the contradiction rule proven live on a fake store: g4_align.contradict_edges (time-aware status), neg_in_scope, slow_consolidate.contested_pairs"""
    G, SC, CO = ws_mod("g4_align"), ws_mod("slow_consolidate"), ws_mod("consolidate")
    care, die = claim("A:care", "person:fiona", "undergo care", "alive", "a1", "k-care"), claim("A:die", "person:fiona", "die", "dead", "a2", "k-die")
    def ce(d_care, d_die): S = type("S", (), {})(); S.arts = {"a1": {"day": d_care}, "a2": {"day": d_die}}; S.asr = {"A:care": care, "A:die": die}; return G.contradict_edges(S, ["A:care", "A:die"], "a2")
    need(len(ce("2025-11-18", "2025-11-20")) == 0, "synthetic: care(18) then die(20) gives %d contradiction edges, want 0 (timeline)" % len(ce("2025-11-18", "2025-11-20")), bad)
    r = ce("2025-11-20", "2025-11-18"); o = (r[0].get("order") or {}) if r else {}
    need(len(r) == 1 and r[0].get("kind") == "status" and o.get("reversal") is True and o.get("earlier") == "A:die", "synthetic: die(18) then care(20) gives %s, want 1 status edge, order.reversal True, earlier A:die" % ([(x.get("kind"), x.get("order")) for x in r]), bad)
    need(len(ce(None, "2025-11-18")) == 0 and len(ce("2025-11-20", None)) == 0, "synthetic: an undated side fires a status edge", bad)
    def neg(t, nw, vw): n, v = t.index(nw), t.index(vw); return G.neg_in_scope(t, (n, n + len(nw), "negation"), (v, v + len(vw)), 0, len(t))
    ns = (neg("She was unable to nurse, so a zoo staffer hand-milked her mother.", "unable", "hand-milked"), neg("Fiona did not survive the night.", "not", "survive"), neg("Despite the hat she recovered quickly.", "Despite", "recovered"))
    need(ns == (False, True, False), "neg_in_scope (unable..so hand-milked, did not survive, Despite) = %s, want (False, True, False)" % (ns,), bad)
    kd, ka = CO.h("k-die"), CO.h("k-care"); st = os.path.join(C.S, "k8-synthetic-store.jsonl")
    edge = {"via": "contradiction", "a": "A:die", "b": "A:care", "label": "contradicts", "kind": "status", "note": "synthetic", "sources": {"a": [{"art": "a2", "pub": "P-a2", "independent": True}], "b": [{"art": "a1", "pub": "P-a1", "independent": True}]}}
    with open(st, "w", encoding="utf-8") as f: f.write(json.dumps({"edges": [[["contradiction", "A:die", "A:care", "contradicts"], edge]]}) + "\n")
    stores = [{"asr": {"A:die": die, "A:care": care}}]; ST = type("ST", (), {"__init__": lambda s, d: setattr(s, "d", d), "day": lambda s, a: s.d.get(a)})
    def cp(d_die, d_care, anchor_care="person:fiona", jmap=None):
        by = {kd: {"anchor": "person:fiona", "attrs": {"status": "dead"}}, ka: {"anchor": anchor_care, "attrs": {"status": "alive"}}}
        return SC.contested_pairs({"join": {"map": jmap or {}}}, stores, [st], by, ST({"a2": d_die, "a1": d_care}))
    kept, drop = cp("2025-11-18", "2025-11-20")
    need(len(kept) == 1 and kept[0]["kind"] == "status" and kept[0]["reversal"] is True and kept[0]["earlier"] == {"edge": kd, "day": "2025-11-18"} and kept[0]["later"]["edge"] == ka and not drop, "contested_pairs die(18)/care(20): kept %s dropped %s, want 1 status pair earlier = die" % (kept, drop), bad)
    got = {"timeline": cp("2025-11-20", "2025-11-18")[1], "unordered": cp("2025-11-18", None)[1], "cross_anchor": cp("2025-11-18", "2025-11-20", anchor_care="concept:zoo")[1], "self_pair": cp("2025-11-18", "2025-11-20", jmap={ka: kd})[1]}
    need(all(v == {w: 1} for w, v in got.items()), "contested_pairs drop reasons %s, want one each" % got, bad)
def k8(C):
    k = C.know(); E = C.edges; bad = []; J = k.get("join"); F = k.get("funnel") or {}; cnt = k.get("counters") or {}
    if not isinstance(J, dict): raise Fail("knowledge.json has no 'join' block")
    # (a) join block and slots
    miss = [x for x in ("mode", "threshold", "facts_raw", "slots", "merge_rate", "contested_kept", "contested_dropped") if x not in J]; need(not miss, "join keys missing %s" % miss, bad)
    slots, raw, mr, thr = J.get("slots"), J.get("facts_raw") or 0, J.get("merge_rate"), J.get("threshold")
    need(slots == F.get("assertions") == len(E), "join.slots %s / funnel.assertions %s / edges %d differ" % (slots, F.get("assertions"), len(E)), bad)
    need(isinstance(mr, (int, float)) and 0 <= mr <= 1 and raw and mr == round(1 - slots / raw, 4), "merge_rate %s, want round(1 - %s / %s, 4) in [0, 1]" % (mr, slots, raw), bad)
    members = collections.Counter(); sbad = []; nslot = 0
    for i, e in E.items():
        s = e.get("slot")
        if not s: continue
        nslot += 1; ms = s.get("members") or []; members.update(m.get("edge") for m in ms)
        if not (s.get("n") == len(ms) >= 2): sbad.append("%s n %s members %d" % (i, s.get("n"), len(ms)))
        if not (isinstance(s.get("min_pair_prob"), (int, float)) and isinstance(thr, (int, float)) and s["min_pair_prob"] >= thr): sbad.append("%s min_pair_prob %s < threshold %s" % (i, s.get("min_pair_prob"), thr))
    dup = sorted(m for m, c in members.items() if c > 1)
    need(not sbad, "%d slot defects, e.g. %s" % (len(sbad), sbad[:2]), bad); need(not dup, "%d member edge ids in two slots, e.g. %s" % (len(dup), dup[:3]), bad)
    ind_bad = [i for i, e in E.items() if not isinstance(e.get("independent"), dict) or e.get("strength") != e["independent"].get("n") or e["independent"].get("n") != len({s.get("pub") for s in e["independent"].get("sources") or [] if s.get("pub")})]
    need(not ind_bad, "%d edges with strength != independent.n != distinct source publishers, e.g. %s" % (len(ind_bad), ind_bad[:3]), bad)
    reinf = sorted(i for i, e in E.items() if (e.get("strength") or 0) >= 2); rev = sorted((cnt.get("reinforced") or {}).get("evidence") or [])
    need(rev == reinf, "counters.reinforced.evidence (%d) != edges with strength >= 2 (%d)" % (len(rev), len(reinf)), bad)
    mode = str(J.get("mode")); ev = None; fb = ("fallback" in mode.lower()) or ("no-embedding" in mode.lower())
    try: ev = join_eval()
    except Fail as e: ev = e
    if isinstance(ev, dict) and ev.get("mode") == "e5-small-v2": need(not fb, "join.mode is the fallback (%s) although sentence_transformers imports in this python" % mode, bad)
    warn = "" if not fb else " WARNING join.mode is the fallback: %s" % mode
    # (b) independence: no wire-copy reinforcement, publisher attribution per fragment
    CO = ws_mod("consolidate"); viol = []; pub_bad = 0; src_bad = 0
    for i, e in E.items():
        fr = e.get("fragments") or []; pub_bad += sum(1 for f in fr if not str(f.get("pub") or "").strip()); reps = []
        for s in (e["independent"].get("sources") or []) if isinstance(e.get("independent"), dict) else []:
            arts = set(s.get("arts") or []); own = {f.get("pub") for f in fr if f.get("art") in arts}
            if s.get("pub") not in own: src_bad += 1
            f = next((f for f in fr if f.get("art") in arts), None)   # fragments are sorted by day, article: the first of the source's articles is its earliest
            if f is not None: reps.append((s.get("pub"), CO.sent_sig(f.get("sent"))))
        if i in reinf: viol += [(i, pa, pb) for (pa, ga), (pb, gb) in itertools.combinations(reps, 2) if pa != pb and ga and gb and jacc(ga, gb) >= CO.SYN_JACCARD]
    need(not viol, "%d reinforced edges reinforced by a near-identical sentence from another publisher (sent_sig Jaccard >= %.2f), e.g. %s" % (len(viol), CO.SYN_JACCARD, viol[:2]), bad)
    need(pub_bad == 0, "%d fragments without a publisher" % pub_bad, bad); need(src_bad == 0, "%d independent sources whose publisher is not one of their own fragments'" % src_bad, bad)
    ind = J.get("independence") or {}; nfr, nsrc, ncol = ind.get("fragments", F.get("fragments")), ind.get("sources", F.get("sources")), ind.get("collapsed")
    wire = sum(1 for i in reinf if (E[i]["independent"].get("collapsed") or 0) > 0)
    # (c) contested pairs against edges, counters and the store
    pairs = k.get("contested") or []; pbad = []
    for p in pairs:
        a, b, kd = p.get("a"), p.get("b"), p.get("kind"); er, la = p.get("earlier") or {}, p.get("later") or {}; da, db = er.get("day"), la.get("day")
        ok = a != b and a in E and b in E and E[a].get("anchor") == E[b].get("anchor") and kd in KINDS and isinstance(da, str) and isinstance(db, str) and DAY_RX.match(da) and DAY_RX.match(db) and da <= db and {er.get("edge"), la.get("edge")} == {a, b} and (kd != "status" or p.get("reversal") is True)
        if not ok: pbad.append("%s/%s %s %s..%s" % (a, b, kd, da, db))
    need(not pbad, "%d contested pairs break the rule (a != b, in edges, same anchor, dated, ordered, kind, reversal on status), e.g. %s" % (len(pbad), pbad[:2]), bad)
    cev = sorted({x for p in pairs for x in (p.get("a"), p.get("b"))}); cc = cnt.get("contested") or {}
    need(cc.get("n") == len(cev) and sorted(cc.get("evidence") or []) == cev, "counters.contested n %s / evidence %d != %d distinct sides of %d pairs" % (cc.get("n"), len(cc.get("evidence") or []), len(cev), len(pairs)), bad)
    drop = J.get("contested_dropped"); dok = isinstance(drop, dict) and all(isinstance(v, int) and v >= 0 for v in drop.values())
    need(dok, "contested_dropped is not a dict of ints >= 0: %s" % (drop,), bad)
    ncontr = len(ws_mod("slow_consolidate").load_contradictions([C.g4])) if os.path.exists(C.g4) else None
    need(J.get("contested_kept") == len(pairs) and dok and len(pairs) + sum(drop.values()) == ncontr, "contested_kept %s + dropped %s != %s contradiction edges in the g4 store (pairs %d)" % (J.get("contested_kept"), sum(drop.values()) if dok else drop, ncontr, len(pairs)), bad)
    # (d) synthetic control, (e) ECB+ fixture
    synthetic(C, bad)
    if isinstance(ev, Fail): bad.append(str(ev))
    else:
        p, r, f1 = ev.get("precision"), ev.get("recall"), ev.get("f1")
        need(isinstance(f1, (int, float)) and f1 >= JOIN_F1_BAR and (p or 0) > 0 and (r or 0) > 0, "ECB+ fixture P/R/F1 %s/%s/%s, want F1 >= %.2f and P, R > 0" % (p, r, f1, JOIN_F1_BAR), bad)
    if bad: raise Fail("; ".join(bad))
    return "join: %d slots = funnel.assertions = edges (%d raw facts), %d merged slots all min_pair_prob >= %s, strength = independent sources on %d edges, %d reinforced; independence: 0 wire-copy reinforcements, publisher on %d fragments; contested %d pairs = %d store edges - %d dropped; synthetic control 3/3 + neg_in_scope 3/3 + contested_pairs 5/5; ECB+ P/R/F1 %.3f/%.3f/%.3f at thr %s | maturity: merge_rate %s, fragments %s -> sources %s (collapsed %s), reinforced via a collapsed copy %d/%d, dropped %s, mode %s%s" % (
        len(E), raw, nslot, thr, len(E), len(reinf), sum(len(e.get("fragments") or []) for e in E.values()), len(pairs), ncontr, sum(drop.values()), ev["precision"], ev["recall"], ev["f1"], ev.get("threshold"), mr, nfr, nsrc, ncol, wire, len(reinf), drop, mode, warn)
STEPS = [("K1", "slow", k1), ("K2", "consolidate", k2), ("K3", "evidence", k3), ("K4", "identity", k4), ("K5", "answer", k5), ("K6", "determinism", k6), ("K7", "feed", k7), ("K8", "join", k8)]
def main():
    t0 = time.time(); root = tempfile.mkdtemp(prefix="check-knowledge-"); res = []; secs = {}
    print("check-knowledge: areas %s, fixtures %s, scratch %s" % (",".join(AREAS), os.path.relpath(FIXROOT, KP), root))
    for ak in AREAS:
        C = Ctx(ak, root); ta = time.time(); dead = None
        for k, name, fn in STEPS:
            if ONLY and k not in ONLY: continue
            t = time.time()
            try:
                if dead and k != "K1": raise Fail("needs %s: that step failed on this area" % dead)
                msg = fn(C); ok = True
            except Fail as e: msg = str(e); ok = False
            except Exception as e: msg = "%s: %s" % (type(e).__name__, str(e)[:300]); ok = False
            if not ok and not dead and (k == "K1" or (k == "K2" and not os.path.exists(os.path.join(C.od, "knowledge.json")))): dead = k   # a failed counter bar does not stop the later steps; a missing knowledge.json does
            res.append((ak, k, ok)); print("%s %s %-4s %-12s %5.1f s  %s" % ("PASS" if ok else "FAIL", k, ak, name, time.time() - t, msg), flush=True)
        secs[ak] = time.time() - ta
    n = sum(1 for r in res if r[2]); print("TOTAL %.1f s (%s) | %d of %d steps PASS%s" % (time.time() - t0, ", ".join("%s %.0f s%s" % (a, s, "" if s < 120 else " OVER 120") for a, s in secs.items()), n, len(res), "" if n == len(res) else " | FAIL: " + ", ".join("%s/%s" % (a, k) for a, k, o in res if not o)))
    if KEEP: print("scratch kept: " + root)
    elif os.path.basename(root).startswith("check-knowledge-") and os.path.dirname(root) == tempfile.gettempdir(): shutil.rmtree(root, ignore_errors=True)
    sys.exit(0 if res and n == len(res) else 1)
if __name__ == "__main__": main()
