"""check-parts: owner track step 1 (ledger L2913). Proves each checklist part of demo/mockups/knowledge-raw/status.json (rows[].id, 23 rows) runs ON ITS OWN.
Every part calls its own function(s) directly: no live_trace.run, no Chain class, no runner, no page, no service. CPU only, no hosted calls, no restarts, nothing in decider.py or lean/ is edited.
    cd /workspace/knowledge_pipeline/projects/world-state && /workspace/models/embed-zs/.venv/bin/python ../../simulation/check-parts.py [--refresh] [--only id,id]
Fixtures (simulation/fixtures/parts/, written on the first run, offline after): 5 articles of the run runs-e2e-1 (chain.jsonl: each record's 'line' is a JSON string). The text is read once, read-only, from the
news queue database (the file the chain read; the allowlisted columns of live_trace.select_sql), together with the chain's own traced line. --refresh re-reads them.
A part PASSES when, on every fixture, it returns a non-empty output or an explicit abstain object without an exception, and it is not empty on all five. An empty result on some fixtures is shown (empty k/5).
A part FAILS on any exception, on a missing input, or when all five fixtures give empty output. Output: one line per part: id | function | PASS/FAIL | short output sample. Exit 1 if any part FAILs.
Stores written by the parts (G4 store, journal, tick log) go to a temp folder. Known test-only choices: the 5 fixtures are unrelated stories, so identity merges and contradictions are expected to be empty
across them; the contradiction check therefore adds one synthetic positive control (a rise and a fall of the same subject and object)."""
import sys, os, re, json, time, glob, shutil, sqlite3, tempfile, hashlib, importlib.util, subprocess, traceback, collections, types
HERE = os.path.dirname(os.path.abspath(__file__)); KP = os.path.dirname(HERE); WS = os.path.join(KP, "projects", "world-state")
FIX = os.path.join(HERE, "fixtures", "parts"); STATUS = "/workspace/demo/mockups/knowledge-raw/status.json"; TRACE = "/workspace/demo/mockups/structure-live/runs-e2e-1/trace"
PICK = [6, 21, 38, 41, 1]   # chain seq numbers: Nepal PM to Delhi, El Chapo Isidro, Canada climate lawsuit, FBI crime database hack, US midterms (all full text, mixed topics and places)
os.environ.setdefault("HF_HUB_OFFLINE", "1"); os.environ.setdefault("CUDA_VISIBLE_DEVICES", ""); os.environ["WORLD_GPU"] = "0"; os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.chdir(WS); sys.path.insert(0, WS)
args = sys.argv[1:]; ONLY = set(args[args.index("--only") + 1].split(",")) if "--only" in args else None
TMP = tempfile.mkdtemp(prefix="check-parts-")
def rel(p): return os.path.relpath(p, KP)
# ------------------------------------------------------------------ fixtures
def build_fixtures():
    import live_trace as LT
    recs = [json.loads(l) for l in open(TRACE + "/chain.jsonl")]; by = {}
    for r in recs: by[json.loads(r["line"])["seq"]] = r
    db = sqlite3.connect("file:%s?mode=ro" % LT.QUEUE, uri=True); arts = []; keep = []
    for s in PICK:
        r = by[s]; line = json.loads(r["line"]); row = db.execute(LT.select_sql("id = ?"), (line["id"],)).fetchone()
        if not row: raise SystemExit("fixture article %s not in the queue; cannot build fixtures" % line["id"])
        arts.append({"seq": s, "row": list(row), "line": line}); keep.append(r)
    os.makedirs(FIX + "/trace", exist_ok=True)
    json.dump(arts, open(FIX + "/articles.json", "w"), ensure_ascii=False, indent=1)
    with open(FIX + "/trace/chain.jsonl", "w") as f:   # the chain's own records, same format (used by journal, resource state, consolidate)
        for r in keep: f.write(json.dumps(r, ensure_ascii=False) + "\n")
if "--refresh" in args or not os.path.exists(FIX + "/articles.json"): build_fixtures()
ARTS = json.load(open(FIX + "/articles.json"))
ROWS = [r["id"] for r in json.load(open(STATUS))["rows"] if r.get("group") != "knowledge"]   # the Knowledge rows (kn_*) are staged-area scores, not pipeline parts (added after the 23 parts; T158 r1)
# ------------------------------------------------------------------ shared heavy objects, loaded once, each from its own module
class R_:
    """lazy resources; a load error is re-raised for every part that needs it (so the part FAILs, with the reason)"""
    def __init__(s): s._c = {}; s._e = {}
    def get(s, name, fn):
        if name in s._e: raise s._e[name]
        if name not in s._c:
            try: s._c[name] = fn()
            except Exception as e: s._e[name] = e; raise
        return s._c[name]
R = R_()
def mod(n): return R.get("mod:" + n, lambda: importlib.import_module(n))
def mod_path(n, f): return R.get("mod:" + n, lambda: (lambda sp: (lambda m: (sp.loader.exec_module(m), m)[1])(importlib.util.module_from_spec(sp)))(importlib.util.spec_from_file_location(n, os.path.join(WS, f))))
def torch1():
    import torch; torch.set_num_threads(4)
def EX(): mod("analyze2"); X = mod("extract"); R.get("ex_init", lambda: X.init()); return X
def pack():
    FL = mod("facts_lib"); return R.get("pack", lambda: mod("structure_pack").Pack(FL.nlp))
def bge(): return R.get("bge", lambda: (torch1(), __import__("sentence_transformers").SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"))[1])
def bge256():
    m = bge(); m.max_seq_length = 256; return m
def expert(): return R.get("expert", lambda: (torch1(), mod("expert1_runtime").ExpertS("runs/expert1/expert1_v6b_student.pkl"))[1])
def analyzer(): return R.get("analyzer", lambda: mod("analyze2").Analyzer(expert().S, json.load(open("runs/pulse/field_table.json")), threads=4))
def landing():
    def mk():
        PV = mod("pack_view"); L = PV.Landing(pack(), alias=False, emb=bge256()); LC = mod("landing_calibrate"); cal, why = LC.load(L.cards_sha)
        return {"L": L, "LC": LC, "cal": cal, "why": why, "share": LC.share_array(L, cal) if cal else None}
    return R.get("landing", mk)
def reranker():
    def mk():
        l = landing(); rr = mod("reranker").Reranker(l["L"], share=l["share"] if l["cal"] else None)
        if rr.cal is None: raise RuntimeError("re-ranker has no matching calibration: %s" % rr.cal_why)
        return rr
    return R.get("reranker", mk)
def place_student(): return R.get("place_student", lambda: (__import__("pickle").load(open("runs/pulse/t200/place_student.pkl", "rb")), __import__("sentence_transformers").SentenceTransformer("intfloat/e5-small-v2", device="cpu")))
def lt(): return mod("live_trace")
def ns():
    """the small object align / build_rec read (pack, EX, FL, SG, SR, bge); a plain namespace of the modules the parts above already use, not live_trace.Chain"""
    return R.get("ns", lambda: types.SimpleNamespace(pack=pack(), EX=EX(), FL=mod("facts_lib"), SG=mod("scan_gate"), SR=mod("span_rules"), bge=bge256()))
# ------------------------------------------------------------------ per-article context (what the earlier parts produced for this article; the same shapes live_trace keeps in stages / full)
class Art:
    def __init__(s, a):
        s.a = a; s.row = tuple(a["row"]); s.chain_line = a["line"]; s.id = s.row[0]; LT = lt()
        s.text, s.title, s.body, s.has_body, s.body_chars, s.capped = LT.build_text(s.row)
        pub = (s.row[6] or "")[:10]; s.date = pub if re.match(r"^\d{4}-\d{2}-\d{2}$", pub) else None; s.ds = (s.date + "T00:00:00Z") if s.date else None
        s.stages = []; s.full = {}; s.ctx = {}
    def put(s, name, out, state="ran", n=None, full=None, why=None, kind="tool"):
        s.stages.append({"name": name, "gate": "", "kind": kind, "version": None, "state": state, "out": out, "n": n, "ms": 0.0, "provenance": None, "why": why}); s.full[name] = full if full is not None else out
A = []
def arts():
    if not A: A.extend(Art(a) for a in ARTS)
    return A
def need(art, *k):
    for x in k:
        if x not in art.ctx: raise RuntimeError("upstream part missing for article %s: %s (run its part first; --only needs the whole chain of parts it reads)" % (art.id[:8], x))
# ------------------------------------------------------------------ the parts. Each takes an Art, returns (output, is_abstain)
PARTS = {}
def part(pid, func):
    def d(fn): PARTS[pid] = (func, fn); return fn
    return d
def nonempty(o):
    if o is None: return False
    if isinstance(o, (dict, list, tuple, set, str)): return len(o) > 0
    return True
@part("g0_read", "live_trace.build_text + read_info (text, source, time, read depth)")
def g0(a):
    LT = lt(); t = LT.build_text(a.row); dom = re.sub(r"^www\.", "", __import__("urllib.parse").parse.urlparse(a.row[1] or "").netloc.lower())
    ri = LT.read_info(a.id)   # read-only, one short connection; None when the queue cannot be opened
    return {"chars": len(t[0]), "title": t[1][:40], "has_body": t[3], "source": a.row[2], "domain": dom, "published": a.date, "read": ri or a.chain_line["input"].get("read")}, False
@part("g1_spans", "scan_gate.scan + span_rules.spans + facts_lib.quarantine")
def g1s(a):
    SG, SR, FL = mod("scan_gate"), mod("span_rules"), mod("facts_lib"); spots, sents = SG.scan(a.text, a.ds or "2026-01-01T00:00:00Z"); sp = SR.spans(a.text, a.ds); kept, held = FL.quarantine(sp, a.text)
    a.ctx["spots"] = spots; a.ctx["sents"] = sents; c = collections.Counter(s[2] for s in spots); k = collections.Counter(x["kind"] for x in kept)
    a.put("scan_dates", {"spots": dict(c), "dates": c.get("date", 0), "time_proxy": None}, n=len(spots), full={"dates": [[a.text[s[0]:s[1]], s[3] if len(s) > 3 else None] for s in spots if s[2] == "date"][:40]})
    a.put("span_rules", {"kinds": dict(k), "quarantined": len(held)}, n=len(kept), full={"held": [{q: x.get(q) for q in ("kind", "s", "e", "why")} for x in held][:30]})
    return {"spots": len(spots), "dates": c.get("date", 0), "sentences": len(sents), "span_kinds": dict(k), "held": len(held)}, False
@part("g1_places", "structure_pack.Pack.lookup_places + link_place (spaCy GPE/LOC/FAC + whole-word lookup)")
def g1p(a):
    X = EX(); P = pack(); re_ = re
    with X.nlp.select_pipes(enable=["tok2vec", "ner"]): d = X.nlp(a.text)
    ents = [(x.text.strip(), x.start_char, x.end_char) for x in d.ents if x.label_ in ("GPE", "LOC", "FAC")]
    strip = lambda p: re_.sub(r"^the ", "", p, flags=re_.I); explicit = {X.ALIAS[strip(p[0])] if strip(p[0]) in X.ALIAS else X.ctry.get(strip(p[0])) for p in ents} - {None}
    dom = re_.sub(r"^www\.", "", __import__("urllib.parse").parse.urlparse(a.row[1] or "").netloc.lower()); items = []
    for nm, s, e in ents: items.append({"text": nm, **P.link_place(nm, dom, explicit, X), "span": [s, e], "src": "spacy"})
    for lk in P.lookup_places(a.text, X):
        if not any(lk["span"][0] < e and s < lk["span"][1] for _, s, e in ents): items.append({**lk, "src": "lookup"})
    items.sort(key=lambda i: i["span"][0]); cc = collections.Counter(i["country"] for i in items if i["country"]); top = sorted(cc.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    o = {"places": len(items), "linked": sum(cc.values()), "top_countries": [list(t) for t in top], "region": None, "country": ({"iso2": top[0][0], "mentions": top[0][1], "spans": [i["span"] for i in items if i["country"] == top[0][0]][:20]} if top else None), "from_lookup": sum(1 for i in items if i["src"] == "lookup")}
    a.ctx["places"] = [c for c, _ in top]; a.put("place_linker", o, n=len(items), full={**o, "items": items[:60]})
    return {"places": len(items), "top": top[:2], "lookup_only": o["from_lookup"]}, False
@part("g2_facts", "facts_lib.facts_for + quarantine + independent runs + analyze2.build_bundles")
def g2f(a):
    FL, A2 = mod("facts_lib"), mod("analyze2"); ff = FL.facts_for(a.text, a.ds); kept, held = FL.quarantine(ff[0], a.text); a.ctx["ff"] = ff; a.ctx["facts"] = kept; k = collections.Counter(f["kind"] for f in kept); ind = ff[1]
    b, info = A2.build_bundles(ff[2], a.text, kept); a.ctx["bundles"] = b
    a.put("facts", {"kinds": dict(k)}, n=len(kept), full={"held": [], "items": [{q: f[q] for q in ("kind", "s", "e", "text", "status")} for f in kept][:120]})
    a.put("independent_counter", {"amount": ind["amount"], "date": ind["date"], "name": ind["name"]}, n=ind["amount"] + ind["date"], full={"amount": ind["amount"], "date": ind["date"], "name": ind["name"], "amount_runs": ind["amount_runs"][:60], "date_runs": ind["date_runs"][:60]})
    a.put("tags_bundles", {"bundles": len(b)}, n=len(b), full={"bundles": b[:40]})
    return {"facts": len(kept), "kinds": dict(k), "indep": {q: ind[q] for q in ("amount", "date", "name")}, "bundles": len(b), "held": len(held)}, False
@part("g2_ner", "fewnerd_typing.fn_ents + summary + apply_fewnerd")
def g2n(a):
    F = mod("fewnerd_typing"); fe = F.fn_ents(a.text); su = F.summary(fe); need(a, "ff", "sents"); sents = a.ctx["sents"]; st = [x for x, y in sents]
    units = [{"type": "name", "spans": [{"role": "name", "s": f["s"], "e": f["e"]}], "subject": f["text"], "predicate": None, "value": None, "sentence": 0, "id": None, "ner": None} for f in a.ctx["facts"] if f["kind"] == "name"]
    new = F.apply_fewnerd(units, a.text, fe, st, sents, {"l1": None, "node": None}, None); typed = sum(1 for u in units if u.get("ner_fine"))
    a.ctx["fents"] = fe; return {"mentions": su["mentions"], "by_coarse": su["by_coarse"], "name_units_typed": typed, "new_units": new}, False
@part("g2_claims", "claims_units.extract_claims + summary")
def g2c(a):
    CU = mod("claims_units"); c = CU.extract_claims(a.text); a.ctx["claims"] = c; s = CU.summary(c); return {k: s[k] for k in ("claims", "both_sides", "partial", "negated", "modal", "attributed")}, False
@part("g3_topic", "pack_view.Landing.land + landing_calibrate + reranker.Reranker.apply")
def g3t(a):
    P = pack(); l = landing(); L, LC, cal = l["L"], l["LC"], l["cal"]; rr = reranker(); need(a, "ff")
    kp = {}; r = L.land(a.ctx["ff"][2], a.text, share=l["share"], gate=bool(cal.get("gate")), keep=kp); art = r["article"]; b = art[0]; l1 = b["path_codes"][0]
    ff = LC.features(r, len(a.text[:2000]), cal["hubs_set"], bool(cal.get("gate"))); pm = LC.permille(LC.prob(ff, cal)); dec = LC.decide_pm(pm, cal); x = rr.apply(kp["sc"], l1)
    out = {"best": b["qcode"], "top3": [[q["qcode"], q["score"]] for q in art[:3]], "l1_code": x["l1_code"], "p": x["p"], "decision": x["decision"], "landing_l1": l1, "landing_p": pm / 1000, "landing_decision": dec, "rerank_node": x["node"]}
    a.ctx["topic"] = out; a.ctx["l1_code"] = x["l1_code"]; a.ctx["topic_pm"] = x["pm"]; a.ctx["topic_line"] = rr.cal["line_permille"]
    a.put("topic_landing", {**out, "rerank": {"l1_code": x["l1_code"], "p": x["p"], "node": x["node"]}, "top3": [[q["qcode"], q["score"]] for q in art[:3]]}, state="abstain" if x["decision"] == "ABSTAIN" else "ran", full={**out, "rerank": {"l1_code": x["l1_code"], "p": x["p"], "node": x["node"]}, "article": art})
    return out, x["decision"] == "ABSTAIN"
@part("g3_area", "analyze2.Reader.read_detail (area + story-type heads) + specs/topic_to_iptc_v1 roll-up")
def g3a(a):
    X = analyzer(); S = expert().S; det = X.reader.read_detail(a.title, a.body); pt, ps = det["pt"], det["ps"]; a.ctx["det"] = det; a.ctx["pt"] = pt; a.ctx["ps"] = ps; import numpy as np
    tn, sn = S["topic_cl"], S["story_cl"]; ot = [[str(tn[int(i)]), round(float(pt[i]), 3)] for i in np.argsort(-pt)[:3]]; os_ = [[str(sn[int(i)]), round(float(ps[i]), 3)] for i in np.argsort(-ps)[:3]]
    m = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; dom = collections.defaultdict(float)
    for n, p in zip(tn, pt): dom[(m.get(n) or ["unmapped"])[0]] += float(p)
    roll = sorted(dom.items(), key=lambda kv: (-kv[1], kv[0]))[:3]; o = {"topic": ot, "story_type": os_}
    a.put("area_function", o, kind="model"); return {"topic": ot[0], "story_type": os_[0], "rollup": [[k, round(v, 3)] for k, v in roll][:1], "windows": det["nw"]}, False
@part("g3_condition", "expert1_runtime.ExpertS.read + direction_v1.read_claims / story_direction")
def g3c_(a):
    E = expert(); p = E.read(a.title + ". " + a.body[:1200]); cp = p.get("condition_present", {}); c = p.get("condition"); D1 = mod("direction_v1"); CU = mod("claims_units")
    cl = a.ctx.get("claims") or CU.extract_claims(a.text); rows = D1.read_claims(cl); sd = D1.story_direction(rows); dirs = collections.Counter(r["direction"] for r in rows)
    a.put("condition", {"present": cp.get("answer"), "present_conf": round(float(cp.get("confidence", 0)), 3), "status": cp.get("status"), "which": c.get("answer") if c else None, "direction": c.get("direction") if c else None}, state="ran" if cp.get("status") == "answered" else "abstain", kind="model")
    ab = cp.get("status") != "answered"; return {"present": cp.get("answer"), "conf": round(float(cp.get("confidence", 0)), 3), "status": cp.get("status"), "claim_dirs": dict(dirs), "story_direction": sd}, ab
@part("g3_heads", "saved-heads.SavedHeads.score (function head + factuality head, saved pickles)")
def g3h(a):
    SH = R.get("saved_heads", lambda: mod_path("saved_heads", "saved-heads.py").SavedHeads()); need(a, "sents"); sents = [a.text[s:e].strip() for s, e in a.ctx["sents"]][:12]; o = SH.score(sents)
    assert len(o["function_p"]) == len(sents) == len(o["factuality_p"]), "score length"; c = collections.Counter(o["function_answer"])
    return {"sentences": len(sents), "function": dict(c), "function_p0": round(o["function_p"][0], 3), "factuality_p0": round(o["factuality_p"][0], 3)}, False
@part("g3_time", "live_trace.time_proxy + novelty_proxy + journal.classify (proxies, no model)")
def g3tm(a):
    LT = lt(); JR = mod("journal"); need(a, "spots"); tp = LT.time_proxy(a.ctx["spots"], a.date); idx = JR.new_index(); d = JR.classify(idx, JR.story_keys(a.title, a.body), a.row[2] or "", 0); nv = LT.novelty_proxy(d)
    return {"time_proxy": tp, "novelty_proxy": nv["value"], "marker": nv["marker"]}, False
@part("g3_decider", "decider.decide + harvest over the six fields, decider.check_against_lean (Lean vectors)")
def g3d(a):
    D = mod("decider"); A2 = mod("analyze2"); FT = json.load(open("runs/pulse/field_table.json")); need(a, "ps", "pt", "facts", "topic"); pt, ps = a.ctx["pt"], a.ctx["ps"]; S = expert().S; import numpy as np; P = A2.Proposal; X = analyzer()
    o2 = np.argsort(-pt)[:2]; am = [f for f in a.ctx["facts"] if f["kind"] == "amount" and f["status"] == "stated"]
    props = {"story_type": P(D.Source.TRAINED_HEAD, float(ps.max()), True, S["story_cl"][int(ps.argmax())], "reader"), "topic": P(D.Source.TRAINED_HEAD, float(pt[o2].sum()), True, " / ".join(S["topic_cl"][k] for k in o2), "reader"),
             "change": P(D.Source.STATED_FACT, 0.0, False, "not run", "pending slow clock"), "size": P(D.Source.STATED_FACT, 0.0, bool(am), "; ".join(f["text"] for f in am[:4]) or "no stated amount", "%d amounts stated" % len(am)),
             "traits": P(D.Source.STATED_FACT, 0.0, False, "not run", "pending slow clock"), "topic_node": P(D.Source.TRAINED_HEAD, a.ctx["topic_pm"] / 1000, True, a.ctx["l1_code"], "rerank-r1")}
    res = {}
    for k, p in props.items():
        mk = FT[k]["marker"]; thr = a.ctx["topic_line"] if k == "topic_node" else X.thr; oc = D.decide(mk, p.source, p.validated, a.ctx["topic_pm"] if k == "topic_node" else int(1000 * p.confidence), thr, True); hv = D.harvest(oc, p.source)
        res[k] = {"outcome": oc.name, "answer_or_proposed": p.answer, "marker": D.Marker(mk).name if isinstance(mk, int) else str(mk), "harvest": hv.name}
    a.ctx["decider"] = res; a.put("decider", {k: v["outcome"] for k, v in res.items()}, n=len(res), full=res)
    if "lean_n" not in R._c: R._c["lean_n"] = D.check_against_lean()   # replays Lean's own vectors (rust_decider/vectors.txt), read-only
    return {"outcomes": {k: v["outcome"] for k, v in res.items()}, "lean_vectors_replayed": R._c["lean_n"]}, False
@part("g5_link", "structure_pack.Pack.terms/place/chain (WordNet placement on the IPTC tree) + Pack.path")
def g5l(a):
    P = pack(); FL = mod("facts_lib"); need(a, "ff"); doc = a.ctx["ff"][2]; top = a.ctx.get("l1_code"); terms = P.terms(doc); placed = 0; intop = 0; hops = collections.Counter(); un = []; ex = None
    for w in terms:
        c = P.place(w)
        if c:
            placed += 1; hops[c[0][0]] += 1; intop += any(P.chain(x[1])[0] == top for x in c) if top else 0
            ex = ex or [w, P.path(c[0][1])]
        else: un.append(w)
    o = {"l1_code_used": top, "n_terms": len(terms), "n_placed": placed, "in_topic": intop, "hops": dict(sorted(hops.items())), "unplaced_share": round(1 - placed / len(terms), 3) if terms else None}
    a.put("structure_pack", o, n=len(terms), full={**o, "unplaced": un[:80], "placed_spans": []}); return {**{k: o[k] for k in ("n_terms", "n_placed", "in_topic")}, "example": ex}, False
# the stateful parts: run once over all 5 fixtures, in order, sharing one temp store. They return one record per article.
def tmp_graph():
    RC = mod("raw_core"); G = RC.Graph(dur_dir=os.path.join(TMP, "g4"), durable=False, ledger=False); RC.set_chain(ch=ns()); return RC, G
def build_line(a):
    """the traced line the page builds from: the chain's own header fields plus the stages the parts above produced for this article"""
    need(a, "decider", "topic"); cl = a.chain_line; jr = {"ids": {"topic": {"best": a.ctx["topic"]["rerank_node"], "l1": a.ctx["l1_code"], "l2": None, "top3": [q[0] for q in a.ctx["topic"]["top3"]]}, "places": a.ctx.get("places", []), "names": [], "names_id_space": "string"}, "story_key": mod("journal").story_keys(a.title, a.body)}
    ps = place_student(); import numpy as np; v = ps[1].encode(["query: " + (a.title + ". " + a.body)[:1500]], normalize_embeddings=True, show_progress_bar=False); pp = ps[0]["model"].predict_proba(v)[0]; cl_ = ps[0]["classes"]
    top = [[str(cl_[int(i)]), round(float(pp[i]), 3)] for i in np.argsort(-pp)[:3]]; a.put("place_student", {"top1": top[0][0], "top": top, "answered": float(pp.max()) >= float(ps[0]["line"])}, kind="model")
    for need_ in ("windows", "capability_list"): a.put(need_, {}, state="empty", full={})
    return {"id": a.id, "title": a.title, "url": a.row[1], "source": a.row[2], "published": a.row[6], "state": "traced", "stages": a.stages, "decider": a.ctx["decider"], "journal": jr, "gaps": [], "total_ms": 0.0}
@part("g4_identity", "raw_core.build_rec + merge_units + g4_align.align (temp store) for all 5 articles in order")
def g4i(a):
    RC, G = R.get("graph", tmp_graph); G4 = mod("g4_align"); line = build_line(a); a.ctx["line"] = line
    rec = {"read": {}, "text": a.text, "title_len": len(a.title), "id": a.id, "publisher": a.row[2], "title": a.title, "url": a.row[1], "published": a.row[6], "state": "traced", "skip_reason": None, "total_ms": 0.0, "story": {"kind": "first", "publishers": 1, "of": None, "seq": a.a["seq"]},
           "stage_out": {s["name"]: {"state": s["state"], "n": s["n"], "why": s["why"], "out": s["out"]} for s in line["stages"]}}
    with G.lock:
        RC.build_rec(ns(), line, a.text, a.full, rec, fewnerd=True, claims=True, pre={"fents": a.ctx["fents"], "claims": a.ctx["claims"]} if "fents" in a.ctx and "claims" in a.ctx else None); RC.merge_units(rec, None, G, ns()); G4.align(rec, G, ns(), contradictions=False)
    g = rec["g4"]; a.ctx["g4"] = g; a.ctx["g4_aids"] = [x["id"] for x in g["assertions"]]; ev = collections.Counter(e["via"] for e in g["edges"])
    return {"units": len(rec["units"]), "entities": len(g["entities"]), "assertions": len(g["assertions"]), "edges": dict(ev), "alias_merges": g["alias_merges"], "store": G.g4.counts()}, False
@part("g4_contra", "g4_align.contradict_edges on the temp store (5 articles) + one synthetic positive control")
def g4c(a):
    G4 = mod("g4_align"); RC, G = R.get("graph", tmp_graph); S = G.g4; need(a, "g4_aids"); e = G4.contradict_edges(S, a.ctx["g4_aids"], a.id)
    if "ctl" not in R._c:   # control: the same subject and object read as rise in one article and fall in another, same week, two publishers
        T = G4.Store(); ctl = lambda pred, art, pub: {"id": "A:" + pred, "key": "k-" + pred, "subj": "E:x", "pred": pred, "obj": "E:y", "obj_text": "y", "kind": "claim", "evid": [{"art": art, "pub": pub, "title": "t", "sent": "s", "spans": [], "independent": True, "attrs": {"polarity": "positive", "direction": None}}]}
        up = next(iter(G4.OPPOSITE)); dn = G4.OPPOSITE[up]; T.asr = {"A:" + up: ctl(up, "c1", "p1"), "A:" + dn: ctl(dn, "c2", "p2")}; T.arts = {"c1": {"publisher": "p1", "root": "c1", "independent": True, "day": "2026-11-20"}, "c2": {"publisher": "p2", "root": "c2", "independent": True, "day": "2026-11-21"}}
        R._c["ctl"] = G4.contradict_edges(T, ["A:" + up], "c1")
    ctl_n = len(R._c["ctl"]); assert ctl_n >= 1, "control pair gave no contradiction edge"
    if not e: return {"edges": 0, "abstain": "no contradicting pair among the 5 unrelated fixtures", "control_edges": ctl_n, "control_kind": R._c["ctl"][0]["kind"]}, True
    return {"edges": len(e), "kinds": dict(collections.Counter(x["kind"] for x in e)), "control_edges": ctl_n}, False
# ------------------------------------------------------------------ whole-set parts (one call over all fixtures)
def run_journal():
    J = mod("journal"); p = os.path.join(TMP, "journal", "j.jsonl"); D = J.Durable(p); rows = []
    for i, a in enumerate(arts()): rows.append(D.add(a.id, J.story_keys(a.title, a.body), a.row[2] or "", i, "check-parts", {"test": 1}, (a.row[6] or "")[:10] or None))
    rep = D.add(arts()[0].id, {}, "x", 99, "check-parts-2", {"test": 1}); E = J.Durable(p)
    assert rep["replayed"] and E.rows == D.rows and len(D.rows) == len(arts()), "replay or reload differs"
    return {"items": len(D.rows), "kinds": dict(collections.Counter(r["kind"] for r in rows)), "days": len(D.day_table()), "replay_ok": True, "reload_equal": True}, False
def run_resource():
    LS = mod("ledger_split"); spec = json.load(open(LS.SPEC)); log = os.path.join(TMP, "ledger", "ticks.jsonl"); RS = LS.ResourceState(spec, "auto", log=log, run_id="check-parts", label_version={"test": 1}); lines = [a.chain_line for a in arts()]
    new = sum(RS.add(l) for l in lines); res = RS.result(); again = sum(RS.add(l) for l in lines); assert again == 0, "second pass added ticks"; R._c["state"] = res; R._c["ticks"] = log; R._c["spec_n"] = len(spec["resources"])
    return {"seed_resources": len(spec["resources"]), "lines": new, "ticks": RS.L.tick, "state_rows": len(res["states"]), "seed_provisional": res["seed"]["provisional"], "sha": res["sha256"][:12]}, len(res["states"]) == 0
def run_truth():
    RT = mod("resource_truth")
    if not os.path.exists(RT.SNAP): raise RuntimeError("cached snapshot missing: " + RT.SNAP)
    snap = json.load(open(RT.SNAP)); ev = RT.load_events(); s = RT.score_events(snap, ev)   # reads the cached snapshot and saved Current Events files only; no network, no rebuild
    assert s["checkable"] >= 0 and "hit_rate" in s; ab = s["checkable"] == 0
    return {"snapshot_days": len(snap["independent_items_per_day"]), "events": s["events_total"], "mapped": s["events_mapped"], "checkable": s["checkable"], "hits": s["hits"], "hit_rate": s["hit_rate"], "bar": s["bar"], "pass_bar": s["pass"]}, ab
def consolidated():
    def mk():
        C = mod("consolidate"); items = C.load_trace(FIX + "/trace"); G = R.get("graph", tmp_graph)[1]; sp = os.path.join(TMP, "g4", "store.jsonl"); ticks = C.load_ticks(R.get("ticks", lambda: R._c["ticks"])) if "ticks" in R._c else []
        stores = [C.load_g4(sp)] if os.path.exists(sp) else []; return C, items, stores, ticks
    return R.get("cons_in", mk)
def run_consolidate():
    C, items, stores, ticks = consolidated(); b = C.seal(C.consolidate(items, stores, ticks)); b2 = C.seal(C.consolidate(items, stores, ticks)); assert b["sha256"] == b2["sha256"], "not deterministic"; R._c["cons"] = b
    assert b["is_a"]["acyclic"]; return {"items": b["stories"]["items"], "stories": b["stories"]["stories"], "edges": b["counts"]["edges"], "candidates": b["counts"].get("candidates"), "is_a_nodes": b["is_a"]["nodes"], "acyclic": b["is_a"]["acyclic"], "sha": b["sha256"][:12]}, b["counts"]["edges"] == 0 and b["counts"].get("candidates", 0) == 0
def run_evolve():
    EV = mod("evolve"); C, items, stores, ticks = consolidated(); b = EV.seal(EV.evolve(items, stores, ticks)); b2 = EV.seal(EV.evolve(items, stores, ticks)); assert b["sha256"] == b2["sha256"], "not deterministic"
    return {"version": b.get("version"), "nodes": len(b["nodes"]), "events": len(b.get("events", [])), "counts": {k: v for k, v in (b.get("counts") or {}).items() if isinstance(v, int)}, "sha": b["sha256"][:12]}, len(b["nodes"]) == 0
def run_educate():
    ED = mod("educate"); body = R._c.get("cons")
    if body is None: raise RuntimeError("needs the consolidate part first")
    state = R._c["state"]; seed = ED.load_seed(ED.SEED); IX = ED.Index(body, state, seed); countries = [a.ctx["places"][0] for a in arts() if a.ctx.get("places")]
    qs = ["What is happening with housing_stock?", "What is going on in %s?" % (countries[0] if countries else "US"), "What is state_capacity in %s?" % (countries[0] if countries else "US"), "Who is Nobody Atall?"]
    ans = [ED.answer(IX, q) for q in qs]; again = ED.answer(IX, qs[0]); assert ED.canon(again) == ED.canon(ans[0]), "answer not deterministic"
    for x in ans: assert x["resolved"] is not None or x["abstain"], "neither resolved nor abstained"
    return {"questions": len(qs), "resolved": sum(1 for x in ans if x["resolved"]), "abstained": sum(1 for x in ans if x["resolved"] is None or not x["statements"]), "statements": [x["statements"] for x in ans], "first": ED.as_text(ans[1])[:70].replace("\n", " ")}, all(x["statements"] == 0 for x in ans)
def run_lean():
    lean = os.path.expanduser("~/.elan/bin/lean"); lean = lean if os.path.exists(lean) else shutil.which("lean")
    if not lean: raise RuntimeError("lean toolchain not found")
    r = subprocess.run([lean, "lean/Props.lean"], capture_output=True, text=True, cwd=WS, timeout=600)   # compile check only (no -o, nothing written); the file is not edited
    assert r.returncode == 0, "lean exit %d: %s" % (r.returncode, (r.stdout + r.stderr)[-300:])
    m = subprocess.run([sys.executable, "props_mirror.py", "--n", "300"], capture_output=True, text=True, cwd=WS, timeout=600); assert m.returncode == 0, "props_mirror exit %d: %s" % (m.returncode, (m.stdout + m.stderr)[-300:])
    return {"lean_Props": "compiled, exit 0", "warnings": len([l for l in (r.stdout + r.stderr).splitlines() if "warning" in l]), "mirror": [l[:60] for l in m.stdout.strip().splitlines()[-2:]]}, False
def run_learn():
    rr = reranker(); fr = "runs/pulse/topic_loop/forward/results.json"
    if not os.path.exists(fr): raise RuntimeError("forward-test results file missing: " + fr)
    f = json.load(open(fr)); return {"reranker": rr.version[:60], "cal_line_permille": rr.cal["line_permille"], "forward_pts": f.get("change_pts"), "ci95": f.get("change_pts_ci95_publisher_bootstrap"), "section_articles": f.get("section_articles"), "frozen_model": f.get("frozen_model")}, False
WHOLE = {"journal": ("journal.Durable (temp dir): add 5 items, replay, reload", run_journal), "world_resource": ("ledger_split.ResourceState (temp tick log): add 5 traced lines, replay adds 0, result()", run_resource),
         "world_truth": ("resource_truth.score_events on the cached snapshot + saved Current Events", run_truth), "two_clocks": ("consolidate.consolidate + seal (5 items, temp G4 store, temp ticks), twice", run_consolidate),
         "g5_evol": ("evolve.evolve + seal over the same inputs, twice", run_evolve), "g6_educate": ("educate.Index + educate.answer, 4 questions incl. one that must abstain", run_educate),
         "lean_p": ("lean Props.lean compile (core Lean) + props_mirror.py P1/P4", run_lean), "learn": ("reranker.Reranker load + forward_test results.json read", run_learn)}
# ------------------------------------------------------------------ runner
ORDER = ["g0_read", "g1_spans", "g1_places", "g2_facts", "g2_ner", "g2_claims", "g3_topic", "g3_area", "g3_condition", "g3_heads", "g3_time", "g3_decider", "g4_identity", "g4_contra", "g5_link", "g5_evol", "g6_educate", "journal", "lean_p", "learn", "world_resource", "world_truth", "two_clocks"]
DEPS = {"g2_ner": ["g1_spans", "g2_facts"], "g3_topic": ["g2_facts"], "g3_condition": ["g2_claims"], "g3_heads": ["g1_spans"], "g3_time": ["g1_spans"], "g3_decider": ["g2_facts", "g3_topic", "g3_area"], "g4_identity": ["g1_places", "g1_spans", "g2_facts", "g2_ner", "g2_claims", "g3_topic", "g3_decider", "g5_link"],
        "g4_contra": ["g4_identity"], "g5_link": ["g2_facts", "g3_topic"], "two_clocks": ["g4_identity", "world_resource"], "g5_evol": ["two_clocks"], "g6_educate": ["two_clocks", "world_resource"]}
assert set(ORDER) == set(ROWS) == set(PARTS) | set(WHOLE), "part list differs from status.json rows: %s" % (set(ROWS) ^ set(ORDER))
EXEC = ["g0_read", "g1_spans", "g1_places", "g2_facts", "g2_ner", "g2_claims", "g3_topic", "g3_area", "g3_condition", "g3_heads", "g3_time", "g3_decider", "g5_link", "g4_identity", "g4_contra", "journal", "world_resource", "world_truth", "two_clocks", "g5_evol", "g6_educate", "lean_p", "learn"]
def closure(ids):
    out = []
    def add(i):
        for d in DEPS.get(i, []): add(d)
        if i not in out: out.append(i)
    [add(i) for i in ids]; return [i for i in EXEC if i in out]
def short(o, n=150):
    s = json.dumps(o, ensure_ascii=False, default=str, sort_keys=True); return s if len(s) <= n else s[:n - 3] + "..."
results = {}
def run_part(pid):
    t0 = time.perf_counter()
    try:
        if pid in PARTS:
            func, fn = PARTS[pid]; outs = []; empties = 0; abst = 0
            for a in arts():
                o, ab = fn(a); outs.append(o); abst += bool(ab); empties += (not nonempty(o)) and not ab
            ok = empties < len(outs); samp = {"n_articles": len(outs), "empty": "%d/%d" % (empties, len(outs)), "abstain": abst, "ex": outs[0] if len(outs) else None}
            results[pid] = (func, "PASS" if ok else "FAIL", samp if ok else {"all_empty": True, **samp})
        else:
            func, fn = WHOLE[pid]; o, ab = fn(); ok = nonempty(o); results[pid] = (func, "PASS" if ok else "FAIL", {"abstain": True, **o} if ab else o)
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)[-1]; results[pid] = (PARTS[pid][0] if pid in PARTS else WHOLE[pid][0], "FAIL", "%s: %s  (at %s:%d)" % (type(e).__name__, str(e)[:160], os.path.basename(tb.filename), tb.lineno))
    results[pid] += (round(time.perf_counter() - t0, 1),)
want = closure(sorted(ONLY)) if ONLY else EXEC
for pid in want:
    if any(d in results and results[d][1] == "FAIL" for d in DEPS.get(pid, [])) and pid in ("g4_contra",):
        results[pid] = (PARTS[pid][0], "FAIL", "upstream part g4_identity failed", 0.0); continue
    run_part(pid)
print("fixtures: %d articles (%s) from %s; temp folder %s" % (len(ARTS), ", ".join(a["row"][0][:8] for a in ARTS), rel(FIX), TMP))
print("id | function | PASS/FAIL | short output sample (seconds)")
for pid in ORDER:
    if pid in results:
        f, st, o, sec = results[pid]; print("%s | %s | %s | %s (%ss)" % (pid, f, st, o if isinstance(o, str) else short(o), sec))
fails = [p for p in ORDER if p in results and results[p][1] == "FAIL"]; done = [p for p in ORDER if p in results]
print("%d of %d parts PASS%s" % (len(done) - len(fails), len(done), ("; FAIL: " + ", ".join(fails)) if fails else "")); sys.exit(1 if fails else 0)
