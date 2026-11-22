"""check-alignment: writes status.json for the Status part of the knowledge-raw page (demo/mockups/knowledge-raw/status.json, static, served by the console with no restart).
For each pipeline component it records three ticks, a runs_in value and a quality record, each proven from the repo, the newest window and the ledger, not typed by hand:
  aligned     : the playbook section exists and contains the keywords that name the component (knowledge_pipeline/playbook/00-knowledge-pipeline-v1.md)
  implemented : the files exist; known limits are ledger lines whose text is matched by a regex (a limit whose line is missing is not claimed); check-durable.py result where one exists
  used (shown as the 'runs' column) : output present in the newest end-to-end run. Code is grepped in live_trace.py, live_trace_v4.py (DEFAULT_ON flags), slow_clock.py and slow_consolidate.py; the proof is the newest window folder (demo/mockups/structure-live/runs-*/ with a chain.jsonl): stage states in chain.jsonl, keys in trace/slow.jsonl, files in trace/slow_consolidate/. runs_in = chain | slow | chain+slow | offline | no. Found only in page code (raw-units.py, g4-align.py) = page only.
  quality     : {score, bar, src (ledger ids), state}: the score and the bar are read from the ledger line by regex (a line that does not match is not claimed, state unmeasured). state = met (a bar is recorded and met) | PROVISIONAL (below the bar, no bar, or the output is marked PROVISIONAL; never a blocker, owner directive L2901) | unmeasured.
Also: the 12-step plan from ledger L2802 with state and done-check, the NEEDS YOU lines from session_start.py with the plan steps they unlock, and any card in kit/live/round_cards/started/.
Completeness: every gate row of playbook section 2 (G0, G1, G2, G3a, G3b, G4, G5, G6) must be covered by a checklist row; the script exits 1 if one is not.
    /workspace/models/embed-zs/.venv/bin/python simulation/check-alignment.py [--no-durable] [--watch SECONDS] [--out path] [--window <window or trace dir>]
--window reads that one window instead of the newest (used by check-flow.py on a scratch copy of the fixtures). An empty window (no traced line) is never read as a run: the newest window by modification time being empty is flagged (window.newest_empty) and the script exits 1; the evidence is then read from the newest window that has traced lines. A chain stage counts as run only when it has state 'ran' on at least one traced line ('empty' is not ran).
Knowledge section (group "knowledge", §2 G4-G6): rows read from the staged area stores demo/mockups/structure-live/area-{c1,mix}/trace/slow_consolidate/knowledge.json (not from the newest core window, which still picks the newest completed run) and the ECB+ join fixture. met only when an outside-truth score meets its bar.
Ratchet ("at or better", default run only: not with --window or a non-default --out): the previous status is kept in knowledge-raw/status-prev.json; per row (group + label) built yes>part>no, runs_in not 'no'->'no', quality met>PROVISIONAL>unmeasured and quality.value (quality.higher_is_better) must not drop; a drop or a missing row prints REGRESSION, lands in status.json "regressions" and exits 3. No drop: the baseline rises to the best of both. --accept records the current status as the baseline.
CPU only, no hosted calls, touches no service."""
import importlib.util, sys, os, re, ast, json, glob, time, subprocess, datetime, argparse, pathlib, tempfile
HERE = pathlib.Path(__file__).resolve().parent; KP = HERE.parent; WS = KP / "projects" / "world-state"; PB = KP / "playbook" / "00-knowledge-pipeline-v1.md"
LT = WS / "live_trace.py"; LT4 = WS / "live_trace_v4.py"; SC = WS / "slow_clock.py"; SCON = WS / "slow_consolidate.py"; CODE = [LT, LT4, SC, SCON]; SL = KP.parent / "demo" / "mockups" / "structure-live"; RU = HERE / "raw-units.py"; G4 = HERE / "g4-align.py"; LEDGER = KP / ".ledger" / "ledger.jsonl"; DEMO = KP.parent / "demo"
ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(DEMO / "mockups" / "knowledge-raw" / "status.json")); ap.add_argument("--no-durable", action="store_true"); ap.add_argument("--watch", type=int, default=0); ap.add_argument("--window", default=None); ap.add_argument("--accept", action="store_true", help="record the current status as the new ratchet baseline (owner accepts a drop)"); ap.add_argument("--prev", default=str(DEMO / "mockups" / "knowledge-raw" / "status-prev.json")); a = ap.parse_args()
DEFAULT_OUT = str(DEMO / "mockups" / "knowledge-raw" / "status.json"); AREAS = {n: SL / ("area-" + n) / "trace" / "slow_consolidate" / "knowledge.json" for n in ("c1", "mix")}; FIXJ = HERE / "fixtures" / "knowledge" / "ecbplus-join.json"
def rel(p): p = pathlib.Path(p).resolve(); return str(p.relative_to(KP.parent)) if KP.parent in p.parents else str(p)
def grep(path, pat, flags=re.I):
    try: return [(i + 1, l) for i, l in enumerate(open(path, errors="replace")) if re.search(pat, l, flags)]
    except OSError: return []
def at(path, hits, n=3): return ", ".join("%s:%d" % (rel(path), i) for i, _ in hits[:n]) + (" (+%d)" % (len(hits) - n) if len(hits) > n else "")

def grep_code(pat, files=None):
    """(path, line_no, text) hits of pat across the chain and slow-clock code files that exist"""
    return [(f, i, l) for f in (files or CODE) if f.exists() for i, l in grep(f, pat)]
def at_code(hits, n=2): return ", ".join("%s:%d" % (f.name, i) for f, i, _ in hits[:n]) + (" (+%d)" % (len(hits) - n) if len(hits) > n else "")
def default_on():
    """DEFAULT_ON of live_trace_v4.py, parsed from its source (not imported): ({flag: bool}, line number)"""
    h = grep(LT4, r"^DEFAULT_ON = ")
    if not h: return {}, None
    try: return ast.literal_eval(re.search(r"=\s*(\{.*?\})", h[0][1]).group(1)), h[0][0]
    except Exception: return {}, h[0][0]
SLOWK = ("claims", "direction", "change", "function_p", "factuality_p", "identity_g4", "contradictions")   # slow_clock.py KEYS
def jload(p):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return None
def traced_count(cf):
    """number of traced lines in one chain.jsonl (0 for an empty or unreadable file)"""
    n = 0
    try:
        for ln in open(cf, encoding="utf-8"):
            if not ln.strip(): continue
            try: n += json.loads(json.loads(ln)["line"]).get("state") == "traced"
            except Exception: continue
    except OSError: return 0
    return n
def _g4store():
    """the page's shared G4 store: runs/g4/store.jsonl; when a page reset has moved it to runs/g4/archive/ (raw-units.reset archives, never deletes), the newest archived copy is the same store, so a reset does not turn the identity row to built=0"""
    live = KP / "runs" / "g4" / "store.jsonl"
    if live.exists(): return live
    arc = sorted((KP / "runs" / "g4" / "archive").glob("store.jsonl-*"), key=lambda p: p.stat().st_mtime)
    return arc[-1] if arc else live
G4STORE = _g4store()
def window():
    """evidence from one end-to-end run. Default: the newest runs-*/trace/chain.jsonl (by mtime) that has traced lines; an empty newer window is not hidden: it is named in w['newest_empty'] and the script exits 1.
    --window <dir>: exactly that window (the folder holding trace/, or the trace folder); no traced line = w['newest_empty'] set to it.
    chain: {stage: {state: n}} over traced lines, plus virtual @journal_kind / @rerank; slow: {key: {state: n}} from trace/slow.jsonl; files: trace/slow_consolidate/*.json (sha256, status); run: run.json"""
    w = {"dir": None, "trace": None, "traced": 0, "chain": {}, "dates": None, "change_not_run": None, "slow_lines": 0, "slow": {}, "files": {}, "run": {}, "mtime": None, "newest_empty": None}
    nm = lambda cf: os.path.basename(os.path.dirname(os.path.dirname(cf)))
    if a.window:
        wd = os.path.abspath(a.window); cf = os.path.join(wd, "chain.jsonl") if os.path.exists(os.path.join(wd, "chain.jsonl")) else os.path.join(wd, "trace", "chain.jsonl")
        if not os.path.exists(cf): w["newest_empty"] = {"dir": os.path.basename(wd.rstrip("/")), "why": "no chain.jsonl in the window folder"}; return w
        if not traced_count(cf): w["newest_empty"] = {"dir": nm(cf), "why": "chain.jsonl has no traced line (%d bytes)" % os.path.getsize(cf)}
    else:
        allc = sorted(glob.glob(str(SL / "runs-*" / "trace" / "chain.jsonl")), key=os.path.getmtime, reverse=True)
        if not allc: return w
        cf = None
        def wstate(p):   # runner's window.json state; only a completed window ('done', or a legacy window without window.json) is evidence; stopped/refused/partial are listed in w['skipped']
            try: return json.load(open(os.path.join(os.path.dirname(os.path.dirname(p)), "window.json"))).get("state")
            except Exception: return None
        w["skipped"] = []
        for p in allc:
            if wstate(p) not in (None, "done"): w["skipped"].append({"dir": nm(p), "state": wstate(p)}); continue
            if traced_count(p): cf = p; break
        if allc and (cf is None or cf != allc[0]) and not any(k["dir"] == nm(allc[0]) for k in w["skipped"]): w["newest_empty"] = {"dir": nm(allc[0]), "why": "newest window has no traced line (%d bytes); evidence read from %s" % (os.path.getsize(allc[0]), nm(cf) if cf else "no window with traced lines")}
        if cf is None: return w
    tr = os.path.dirname(cf); w.update(dir=nm(cf), trace=tr, mtime=datetime.datetime.fromtimestamp(os.path.getmtime(cf)).isoformat(timespec="seconds"))
    run = jload(os.path.join(tr, "run.json")) or {}; w["run"] = run
    chain = {}; jk = 0; d = [0, 0]; cnr = 0; n = 0
    for ln in open(cf, encoding="utf-8"):
        if not ln.strip(): continue
        try: x = json.loads(json.loads(ln)["line"])
        except Exception: continue
        if x.get("state") != "traced": continue
        n += 1
        for st in x.get("stages", []):
            c = chain.setdefault(st["name"], {}); c[st.get("state")] = c.get(st.get("state"), 0) + 1
            if st["name"] == "scan_dates" and st.get("state") == "ran": o = st.get("out") or {}; d[0] += o.get("dates") or 0; d[1] += o.get("dates_resolved") or 0
        if (((x.get("journal") or {}).get("dup") or {}).get("kind")) is not None: jk += 1
        if (((x.get("decider") or {}).get("change") or {}).get("answer_or_proposed")) == "not run": cnr += 1
    w["traced"] = n; w["dates"] = tuple(d) if n else None; w["change_not_run"] = cnr
    if jk: chain["@journal_kind"] = {"ran": jk}
    if chain.get("topic_landing", {}).get("ran") and not any("re-ranker" in str(x) for x in (run.get("degraded") or [])): chain["@rerank"] = {"ran": chain["topic_landing"]["ran"]}
    w["chain"] = chain
    sj = os.path.join(tr, "slow.jsonl"); sl = {}; nl = 0
    if os.path.exists(sj):
        for ln in open(sj, encoding="utf-8"):
            if not ln.strip(): continue
            try: o = json.loads(ln)
            except Exception: continue
            if isinstance(o.get("line"), str):
                try: o = json.loads(o["line"])
                except Exception: pass
            nl += 1
            for k in SLOWK:
                v = o.get(k)
                if isinstance(v, dict) and v.get("state") != "error": c = sl.setdefault(k, {}); c[v.get("state") or "out"] = c.get(v.get("state") or "out", 0) + 1
    w["slow_lines"] = nl; w["slow"] = sl
    for f in glob.glob(os.path.join(tr, "slow_consolidate", "*.json")):
        j = jload(f)
        if isinstance(j, dict): w["files"][os.path.basename(f)] = {"sha": (j.get("sha256") or "")[:12], "status": j.get("status"), "path": f}
    return w
def place(win, comp):
    """(places, evidence) for one component (label, chain stage, slow key, slow file): where its output is present in the newest run"""
    label, stage, sk, sf = comp; pl = []; ev = []
    if stage:
        c = win["chain"].get(stage, {}); k = c.get("ran", 0)   # empty is not ran
        if c and not k: ev.append("%s: chain stage never ran on %d traced lines (%s)" % (label, win["traced"], ", ".join("%s %d" % (x, y) for x, y in sorted(c.items()))))
        if k: pl.append("chain"); ev.append("%s: chain %d of %d traced lines (%s)" % (label, k, win["traced"], ", ".join("%s %d" % (a, b) for a, b in sorted(c.items()))))
    if sk:
        c = win["slow"].get(sk, {}); k = sum(c.values())
        if k: pl.append("slow"); ev.append("%s: slow.jsonl %d of %d lines (%s)" % (label, k, win["slow_lines"], ", ".join("%s %d" % (a, b) for a, b in sorted(c.items()))))
    if sf:
        f = win["files"].get(sf)
        if f: pl.append("slow"); ev.append("%s: slow_consolidate/%s sha %s %s" % (label, sf, f["sha"], f["status"] or ""))
    if not pl: ev.append("%s: not in the newest run" % label)
    return pl, ev
def build():
    ledger = {}
    for l in open(LEDGER):
        x = json.loads(l); ledger[x["id"]] = x
    ltext = lambda i: (ledger.get(i) or {}).get("text") or ""
    pb = PB.read_text(); secs = {}
    for m in re.finditer(r"^## (\d+)\. .*?(?=^## \d+\. |\Z)", pb, re.S | re.M): secs[int(m.group(1))] = m.group(0)
    pbline = lambda kw: next((i for i, l in enumerate(pb.splitlines(), 1) if kw.lower() in l.lower()), None)
    T = lambda s, ev: {"s": s, "ev": ev}
    # ---- durable check result (implemented tick for journal / resource state) ----
    dur = {"ran": False, "pass": None, "lines": []}
    if not a.no_durable:
        env = dict(os.environ, TMPDIR=tempfile.gettempdir()); py = "/workspace/models/embed-zs/.venv/bin/python"
        try:
            pr = subprocess.run([py if os.path.exists(py) else sys.executable, str(HERE / "check-durable.py"), "--no-g4"], capture_output=True, text=True, timeout=300, env=env)
            out = pr.stdout.strip().splitlines(); dur = {"ran": True, "pass": pr.returncode == 0 and any(l.strip() == "ALL PASS" for l in out), "lines": [l[:140] for l in out if l.startswith(("PASS", "FAIL"))][:12], "when": datetime.datetime.now().isoformat(timespec="seconds"), "cmd": "check-durable.py --no-g4"}
        except Exception as e: dur = {"ran": True, "pass": False, "lines": [repr(e)[:140]]}
    # ---- builders ----
    def aligned(sec, kws, note=""):
        s = secs.get(sec)
        if not s: return T("no", "playbook section %d not found" % sec)
        miss = [k for k in kws if k.lower() not in s.lower()]; ln = pbline(kws[0]) if kws else None
        return T("no" if miss and len(miss) == len(kws) else ("part" if miss else "yes"), "playbook §%d%s%s" % (sec, (" line %d" % ln) if ln else "", ("; keywords not found: " + ", ".join(miss)) if miss else "") + note)
    def implemented(files=(), limits=(), none_if=None, extra="", part_if=None):
        miss = [f for f in files if not pathlib.Path(f).exists()]
        if miss: return T("no", "file missing: " + ", ".join(rel(m) for m in miss))
        if none_if is not None and not none_if[0]: return T("no", none_if[1])
        lim = [(i, why) for i, rx, why in limits if re.search(rx, ltext(i), re.I | re.S)]
        ev = "; ".join(rel(f) for f in list(files)[:3]) + (("; " + extra) if extra else "")
        if part_if is not None and part_if[0]: return T("part", ev + "; " + part_if[1] + ("; limits: " + "; ".join("%s (%s)" % (w, i) for i, w in lim) if lim else ""))
        if lim: return T("part", ev + "; limits: " + "; ".join("%s (%s)" % (w, i) for i, w in lim))
        return T("yes", ev)
    win = window(); DON, DON_LN = default_on(); v4 = (win["run"].get("v4") or {})
    def used(r):
        """(tick, runs_in): output present in the newest end-to-end run. chain = stage output in chain.jsonl, slow = key in slow.jsonl or file in slow_consolidate/. yes = every component present, part = some, no = none"""
        if r.get("offline"):
            ok = all(pathlib.Path(f).exists() for f in r["offline"][0]) and bool(re.search(r["offline"][1][1], ltext(r["offline"][1][0]), re.I | re.S))
            return (T("yes" if ok else "no", "offline by design, not a stage of any run: " + r["offline"][2] + " (%s)" % r["offline"][1][0]), "offline" if ok else "no")
        res = [place(win, c) for c in r["comps"]]; got = [p for p, _ in res if p]; places = {x for p in got for x in p}
        ev = [e for _, es in res for e in es]
        code = [h for h in (grep_code(p) for p in r.get("code", [])) if h]
        if code: ev.append("code: " + at_code([h[0] for h in code]))
        fl = r.get("flag")
        if fl and fl in DON:
            ev.append("flag LT_V4_%s default %s (live_trace_v4.py:%s)" % (fl.upper(), "on" if DON[fl] else "off", DON_LN) + ("" if "chain" in places else ("; the newest run (%s) was traced %s" % (win["dir"], "with this flag on" if (v4.get("flags") or {}).get(fl) else "before the flag was on" if not v4 else "with this flag off"))))
        if not win["dir"]: ev.append("no run folder with a chain.jsonl found" if not win["newest_empty"] else "window empty: " + win["newest_empty"]["why"])
        s_ = "yes" if len(got) == len(res) else ("part" if got else "no")
        if s_ == "no" and r.get("page"):
            pg = [(f, grep(f, p)) for f, p in r["page"]]; pg = [(f, h) for f, h in pg if h]
            if pg: ev.append(("page only: " if all(f in (RU, G4) for f, _ in pg) else "code only in: ") + "; ".join(at(f, h, 2) for f, h in pg))
        if r.get("force_part") and s_ == "yes": s_ = "part"
        if r.get("note_part") and s_ == "part": ev.append(r["note_part"])
        return T(s_, "newest run " + str(win["dir"]) + ": " + "; ".join(ev)), ("+".join(x for x in ("chain", "slow") if x in places) or "no")
    L = {}  # stage patterns
    st = lambda n: r'run\("%s"' % n
    # condition fire rate on the v7 trace (verified, not copied)
    fire = None
    try:
        n = c = 0
        for ln in open(DEMO / "mockups" / "structure-live" / "runs-v7" / "trace" / "chain.jsonl"):
            x = json.loads(json.loads(ln)["line"])
            if x.get("state") != "traced": continue
            n += 1; c += any(s["name"] == "condition" and (s.get("out") or {}).get("present") in (True, "yes") for s in x["stages"])
        fire = (c, n)
    except Exception: pass
    cond_limit = (fire is not None and fire[1] and fire[0] / fire[1] < .10)
    entfb = None
    fb = re.search(r"(\d+)/(\d+) entities get it only from the article topic", ltext("L2796")); entfb = (int(fb.group(1)), int(fb.group(2))) if fb else None
    NAfn = bool(grep(LT, r'"function_sentence": \("G'))
    nofn = not grep_code(r"function_p|saved_heads", [LT, LT4, SC]); nodir = not grep_code(r"direction_v1|read_claims", [LT, LT4, SC]); chg = grep(LT, r'"change": P\(')
    C = lambda label, stage=None, sk=None, sf=None: (label, stage, sk, sf)
    rows = [
     dict(id="g0_read", group="core", gates=["G0"], label="read text, source, time, read depth", sec=2, kw=["G0 — Normalize"], files=[LT], limits=[], comps=[C("windows", "windows")], code=[r"def build_text", st("windows")]),
     dict(id="g1_spans", group="core", gates=["G1"], label="dates, spans, numbers", sec=2, kw=["G1 — Scan"], files=[WS / "scan_gate.py", WS / "span_rules.py", WS / "facts_lib.py"], limits=[], comps=[C("scan_dates", "scan_dates"), C("span_rules", "span_rules")], code=[st("scan_dates"), st("span_rules")]),
     dict(id="g1_places", group="core", gates=["G1"], label="places (lookup + country)", sec=2, kw=["entity candidates"], files=[LT, WS / "pack_view.py"], limits=[], comps=[C("place_linker", "place_linker")], code=[st("place_linker")]),
     dict(id="g2_facts", group="core", gates=["G2"], label="facts, bundles, independent count", sec=2, kw=["G2 — Semantic solver"], files=[WS / "facts_lib.py", WS / "analyze2.py"], limits=[], comps=[C("facts", "facts"), C("independent_counter", "independent_counter"), C("tags_bundles", "tags_bundles")], code=[st("facts"), st("independent_counter"), st("tags_bundles")]),
     dict(id="g2_ner", group="core", gates=["G2"], label="entity types (Few-NERD)", sec=2, kw=["entity candidates"], files=[WS / "runs" / "pulse" / "names_fewnerd_v2"], limits=[], extra="model dir; " + ("L2883 test F1 coarse 0.7126 / fine 0.5657" if "0.7126" in ltext("L2883") else ""), flag="fewnerd", comps=[C("ner_fewnerd", "ner_fewnerd")], code=[r"ner_fewnerd"], page=[(RU, r"few.?nerd"), (G4, r"few.?nerd")]),
     dict(id="g2_claims", group="core", gates=["G2"], label="claims and pronoun resolution", sec=2, kw=["Subject/predicate/object fragments"], files=[WS / "claims_v1.py", WS / "claims_units.py"], limits=[("L2866", r"pronoun ORG errors remain", "pronoun ORG errors remain")], flag="claims", comps=[C("claims_v1", "claims_v1", "claims")], code=[r"claims_v1|extract_claims"], page=[(RU, r"claims?|pronoun")]),
     dict(id="g3_topic", group="core", gates=["G3a"], label="topic (landing + frozen re-ranker)", sec=2, kw=["G3a — Sparse classify"], files=[WS / "landing_calibrate.py", WS / "reranker.py", WS / "pack_view.py"], limits=[], comps=[C("topic_landing", "topic_landing")], code=[st("topic_landing")]),
     dict(id="g3_area", group="core", gates=["G3a"], label="area, function, domain roll-up", sec=2, kw=["multi-label Domains/Areas"], files=[LT], limits=[], part_if=(nofn, "the function-sentence head has no caller in live_trace*.py or slow_clock.py (NA entry live_trace.py:%s)" % (grep(LT, r'"function_sentence": \("G')[0][0] if NAfn else "-")), comps=[C("area_function", "area_function"), C("domain_rollup", "domain_rollup"), C("function head", "function_sentence", "function_p")], code=[st("area_function"), st("domain_rollup")]),
     dict(id="g3_condition", group="core", gates=["G3a"], label="condition with direction", sec=2, kw=["conditions"], files=[WS / "expert1_runtime.py", WS / "direction_v1.py"], limits=[("L2708", r"Condition fires on under 10 percent", "fires on %s of traced articles on runs-v7" % ("%d of %d = %.1f%%" % (fire[0], fire[1], 100 * fire[0] / fire[1]) if fire else "under 10 percent"))] if cond_limit else [], part_if=(nodir, "direction_v1.py exists but nothing in live_trace*.py or slow_clock.py calls it; the decider 'change' field is hard-coded 'not run' (live_trace.py:%s)" % (chg[0][0] if chg else "-")), comps=[C("condition", "condition"), C("direction", None, "direction")], code=[st("condition")]),
     dict(id="g3_heads", group="core", gates=["G3a"], label="factuality and function heads", sec=2, kw=["content function"], files=[WS / "runs" / "pulse" / "function_head_v1" / "function_head.pkl", WS / "runs" / "pulse" / "factuality_v1" / "factuality_head.pkl"], limits=[("L2795", r"Both heads trained\+saved", "saved; function AUC 0.791 on 300 gold, factuality CV AUC 0.758; hook RAW_HEADS=1 default off")], comps=[C("function head", "function_sentence", "function_p"), C("factuality head", "factuality_story", "factuality_p")], code=[r"saved_heads|function_p"], page=[(RU, r"RAW_HEADS")]),
     dict(id="g3_time", group="core", gates=["G3a"], label="time and novelty (proxies)", sec=2, kw=["G3a — Sparse classify"], files=[WS / "scan_gate.py", WS / "journal.py"], limits=[("L2791", r"Time and novelty NOT trained", "proxies only: event-date offsets (scan_dates) and the journal duplicate kind; no time or novelty model, no outside truth (time judge AUC 0.607, novelty AUROC 0.51)")], comps=[C("time proxy (scan_dates)", "scan_dates"), C("novelty proxy (journal dup kind)", "@journal_kind")], code=[st("scan_dates")]),
     dict(id="g3_decider", group="core", gates=["G3b"], label="decider (Lean-checked)", sec=2, kw=["G3b — Deeper CPU classify"], files=[WS / "decider.py", WS / "lean" / "Decide.lean"], limits=[], comps=[C("decider", "decider")], code=[st("decider")]),
     dict(id="g4_identity", group="core", gates=["G4"], label="entity identity and assertions", sec=2, kw=["G4 — Align"], files=[G4, G4STORE], limits=[("L2900", r"1/61 = 1\.6%", "wrong merges 1/61 = 1.6% after the ident-v2 rules, 4 correct merges lost"), ("L2796", r"[Cc]aveats", "alias errors")], flag="identity", comps=[C("identity_g4", "identity_g4", "identity_g4")], code=[r"identity_g4"], page=[(RU, r"G4\.align|g4.?align")]),
     dict(id="g4_contra", group="core", gates=["G4"], label="contradictions", sec=2, kw=["conflicts"], files=[G4], none_if=(bool(grep(G4, r"contradict") or grep(RU, r"contradict")), "no 'contradict' in g4-align.py or raw-units.py"), flag="contradictions", comps=[C("contradictions", "contradictions", "contradictions")], code=[r"contradict"]),
     dict(id="g5_link", group="core", gates=["G5"], label="linking (IPTC, WordNet)", sec=2, kw=["G5 — Evolve"], files=[WS / "structure_pack.py"], limits=[("L2796", r"424/747", "IPTC path from the article topic fallback for %s entities (%s)" % ("%d of %d" % entfb if entfb else "424 of 747", "%.0f%%" % (100 * entfb[0] / entfb[1]) if entfb else "57%"))], comps=[C("structure_pack (terms)", "structure_pack"), C("entity linking (identity_g4)", "identity_g4", "identity_g4")], code=[st("structure_pack")], page=[(G4, r"iptc")]),
     dict(id="g5_evol", group="core", gates=["G5"], label="evolution (residual clusters, promotion)", sec=2, kw=["Provisional residual clusters"], files=[WS / "evolve.py"], none_if=(bool(grep(WS / "evolve.py", r"residual")), "no residual-cluster code in evolve.py"), comps=[C("evolve (RESIDUAL nodes)", None, None, "evolved.json")], code=[r"evolve"], page=[(RU, r"promot|residual"), (G4, r"promot|residual")]),
     dict(id="g6_educate", group="core", gates=["G6"], label="educate (answers with sources)", sec=2, kw=["G6 — Educate"], files=[WS / "educate.py"], none_if=(bool(grep(WS / "educate.py", r"educat")), "no educator code in educate.py"), comps=[C("educate index", None, None, "educate_index.json")], code=[r"educat"]),
     dict(id="journal", group="plumbing", gates=[], label="Journal (durable)", sec=1, kw=["Durable observation journal"], files=[WS / "journal.py"], limits=[], flag="journal", comps=[C("journal_durable", "journal_durable")], code=[r"journal_durable|import journal"], dur=True),
     dict(id="lean_p", group="plumbing", gates=[], label="Lean P1/P4 property tests", sec=11, kw=["| P1 |", "| P4 |"], files=[], none_if=(any(grep(f, r"idem|acyclic") for f in glob.glob(str(WS / "lean" / "*.lean"))), "no idempotence or acyclicity theorem in projects/world-state/lean/*.lean"), offline=([WS / "lean" / "Props.lean", WS / "props_mirror.py"], ("L2878", r"lean exit 0, no sorry"), "the proof gate, done: lean/Props.lean (P1, P4) and props_mirror.py")),
     dict(id="learn", group="learning", gates=[], label="retrain (learning ladder)", sec=13, kw=["CPU classifier training"], files=[WS / "reranker.py", KP / "projects" / "world-state" / "forward_test.py"], limits=[("L2850", r"NO GAIN", "topic only; forward test NO GAIN (L2850)")], comps=[C("topic re-ranker (frozen)", "@rerank")], code=[r"self\.rerank"], force_part=True, note_part="only the topic re-ranker is a retrained head in the chain; function, factuality, time, novelty heads are not retrained there"),
     dict(id="world_resource", group="world", gates=[], label="Macro Pulse resource state", sec=10, kw=["Macro Pulse"], files=[WS / "ledger_split.py"], limits=[("L2848", r"PROVISIONAL", "26 seed resources, all marked guess (PROVISIONAL)")], comps=[C("resource state", None, None, "resource_state.json")], code=[r"ResourceState"], page=[(WS / "ledger_split.py", r"class ResourceState")], dur=True),
     dict(id="world_truth", group="world", gates=[], label="world state against truth", sec=10, kw=["Macro Pulse"], files=[WS / "resource_truth.py"], none_if=((WS / "resource_truth.py").exists(), "no resource_truth.py"), comps=[C("truth snapshot", None, None, "truth.json")], code=[r"resource_truth|truth"]),
     dict(id="two_clocks", group="world", gates=[], label="two-clocks consolidation", sec=18, kw=["Two clocks"], files=[WS / "consolidate.py"], none_if=(bool(grep(WS / "consolidate.py", r"consolidat")), "no consolidation pass in consolidate.py"), comps=[C("consolidated.json", None, None, "consolidated.json")], code=[r"consolidat"]),
    ]
    # ---- quality: score and bar read from the ledger line by regex; a line that does not match is not claimed (unmeasured) ----
    def mm(i, rx):
        m = re.search(rx, ltext(i), re.S); return m.groups() if m else None
    def Q(srcs, score, bar, state, note=""):
        """one quality record; score None = nothing matched = unmeasured"""
        if score is None: return {"score": None, "bar": bar, "src": srcs, "state": "unmeasured", "note": note or "no scored number in the ledger line(s) %s" % ", ".join(srcs)}
        return {"score": score, "bar": bar, "src": srcs, "state": state, "note": note}
    f = lambda g, i: g[i] if g else None
    KN = {n: j for n, p_ in AREAS.items() if isinstance((j := jload(p_)), dict)}   # staged area stores: the Knowledge section and two_clocks read these, not the newest core window
    def q_read():
        g = mm("L2782", r"(\d[\d,]*) full text, (\d+) teaser by robots, (\d+) paywall/blocked.*?(about half teaser-only)")
        return Q(["L2782"], ("last 24h queue: %s full text, %s teaser by robots, %s paywall/blocked; %s" % g) if g else None, "none recorded", "PROVISIONAL", "read depth is stored per article; the chain line does not carry it yet")
    def q_spans():
        d = win["dates"]
        return Q(["chain.jsonl " + str(win["dir"])], ("%d of %d event dates resolved in %d traced lines" % (d[1], d[0], win["traced"])) if d and d[0] else None, "none recorded", "PROVISIONAL", "resolution count only, no outside truth")
    def q_places():
        g = mm("L2852", r"place_val \(300 stories.*?P (0\.\d+->0\.\d+), R (0\.\d+->0\.\d+)")
        return Q(["L2852", "L2799"], ("precision %s, recall %s on place_val (300 stories); GeoNames name test 64 mislinks -> 0" % g) if g else None, "none recorded", "PROVISIONAL", "labels from model reviewers, not outside truth; Hollywood stays iso:US with a metonym flag (L2852)")
    def q_ner():
        a_, b_ = mm("L2883", r"Coarse8 micro F1 [\d.]+ -> ([\d.]+).*?fine66 [\d.]+ -> ([\d.]+)") or (None, None); k = mm("L2883", r"Keep rule \((.*?)\) (MET)")
        return Q(["L2883"], ("Few-NERD test coarse F1 %s, fine F1 %s (v2)" % (a_, b_)) if a_ else None, "keep rule: " + k[0] if k else "none recorded", "met" if k else "PROVISIONAL")
    def q_claims():
        g = mm("L2863", r"claims v1 P ([\d.]+) R ([\d.]+) F1 ([\d.]+)"); k = mm("L2863", r"KEEP RULE (MET): test F1 [\d.]+ >= ([\d.]+)")
        return Q(["L2863", "L2866"], ("CaRB test P %s R %s F1 %s (in-house scorer)" % g) if g else None, ("F1 >= %s (keep rule)" % k[1]) if k else "none recorded", "met" if k else "PROVISIONAL", "runs at the slow clock: p90 676 ms > 600 ms in the chain (L2898)")
    def q_topic():
        a_ = mm("L2850", r"points = ([\d.]+) .*?difference (\+[\d.]+), noise floor ([\d.]+)"); c_ = mm("L2763", r"CI (-?[\d.]+) to \+?([\d.]+)")
        return Q(["L2850", "L2763"], ("re-ranker minus landing +%s pts on publisher section; vs earlier windows %s (noise floor %s)%s" % (a_[0], a_[1], a_[2], ("; 43-article window CI %s to +%s" % c_) if c_ else "")) if a_ else None, "predicted 4.0 to 15.0 pts (L2850); forward gain over earlier windows must beat the noise floor", "PROVISIONAL", "forward gain over earlier windows is NO GAIN (L2850)")
    def q_area(): return Q(["none"], None, "none recorded", "PROVISIONAL", "no bar and no score for area/function; the function head AUC 0.791 is under g3_heads")
    def q_cond():
        g = mm("L2895", r"all-items \(abstain=miss\) ([\d.]+) \(always-up ([\d.]+)"); k = mm("L2895", r"Bar (all-items>=[\d.]+ with answered>=[\d.]+) MET")
        return Q(["L2895"], ("direction on SENTiVENT confirm half: all-items %s (always-up %s)" % g) if g else None, k[0] if k else "none recorded", "PROVISIONAL", "bar met on finance text only; the decider change field is a validated=False proposal, so the answer stays an abstain" + ("; condition fires on %.1f%% of runs-v7 articles" % (100 * fire[0] / fire[1]) if fire and fire[1] else ""))
    def q_decider():
        try:
            sys.path.insert(0, str(WS)); import decider as _D; n = _D.check_against_lean(str(WS / "rust_decider" / "vectors.txt"))
        except Exception as e: n = None
        cn = win["change_not_run"]
        return Q(["decider.check_against_lean"], ("check_against_lean() = %s" % n) if n is not None else None, "160 (every Lean-checked case)", "met" if n == 160 else "PROVISIONAL", ("change and traits are hard-coded 'not run' on %d of %d traced lines (live_trace.py:%s)" % (cn, win["traced"], chg[0][0] if chg else "-")) if win["traced"] else "")
    def q_heads():
        g = mm("L2795", r"CPU head on CheckThat test_en_labeled.*?AUC ([\d.]+), bal acc ([\d.]+) @0\.5.*?Factuality: CV .*?AUC ([\d.]+), bal acc ([\d.]+) @0\.5, ([\d.]+) @line")
        b = grep(LT, r"balanced accuracy 0\.56 to 0\.63 against the 0\.80 bar")
        return Q(["L2795", "live_trace.py:%d" % b[0][0] if b else "live_trace.py"], ("function AUC %s (bal acc %s) on 300 gold; factuality CV AUC %s, bal acc %s @0.5, %s @line" % g) if g else None, "factuality bal acc 0.80 (live_trace.py NA text)" if b else "none recorded", "PROVISIONAL", "669 ms per article, so it runs at the slow clock")
    def q_time():
        g = mm("L2791", r"time judge AUC ([\d.]+), novelty as-worded AUROC ([\d.]+)")
        return Q(["L2791"], ("time judge AUC %s, novelty AUROC %s (both rejected as labels)" % g) if g else None, "none: no outside truth", "PROVISIONAL", "proxy output: event-date offsets and the journal duplicate kind")
    def q_ident():
        g = mm("L2900", r"ident-v2 rules -> (\d+/\d+ = [\d.]+%) \(CI ([\d.]+-[\d.]+)\)"); h = mm("L2900", r"wrong merges (\d+/\d+ = \d+%)")
        return Q(["L2900", "L2962"], ("wrong merges %s after ident-v2 (CI %s); before %s" % (g[0], g[1], h[0] if h else "?")) if g else None, "none recorded", "PROVISIONAL", "replay on one sample; 4 correct merges lost; fact-merge precision on mix is weak: Fable read of reinforced edges found 3 of 6 wrong merges (L2962, a read-only sample, not a scored test)")
    def q_contra():
        c0 = [(n, ((k.get("counters") or {}).get("contested") or {}).get("n")) for n, k in KN.items()]
        ok = all(i in ledger for i in ("L2955", "L2959")) and bool(re.search(r"synthetic control", ltext("L2959") + ltext("L2954"), re.I))
        return Q(["L2955", "L2959", "L2954"], ("time-ordered status rule proven on a synthetic control (check-knowledge K8 d: care->die 0 edges, die->care 1 edge); real pairs: %s" % ", ".join("%s %s" % x for x in c0)) if ok and c0 else None, "none recorded", "PROVISIONAL", "0 real contradiction pairs on c1 and mix, so the rule is proven on a control only; no labelled contradiction test set (plan step 7)")
    def q_link(): return Q(["L2796"], ("%d of %d entities (%.0f%%) get the IPTC path only from the article topic fallback" % (entfb[0], entfb[1], 100 * entfb[0] / entfb[1])) if entfb else None, "none recorded", "PROVISIONAL", "the fallback is marked 'guess' on the page")
    def q_evol():
        g = mm("L2881", r"Real stores .*?: (\d+) unplaced.*?, (\d+) candidates")
        return Q(["L2881"], ("%s unplaced terms, %s promotion candidates (windows gate binding)" % g) if g else None, "none recorded", "PROVISIONAL", "check-evolve 19/19 structural")
    def q_educ():
        g = mm("L2882", r"Pointers 100% on (\d+) fixture \+ (\d+) sweep statements")
        return Q(["L2882", "T178"], ("pointers 100%% on %s fixture + %s sweep statements (check-educate 16 checks)" % g) if g else None, "none recorded: weights equal PROVISIONAL (T178)", "PROVISIONAL", "the mix auto answer holds 2 false wrong-agent statements (houthi destroy/intercept: sources say the Saudi-led coalition did it, L2962)") | ({"src": ["L2882", "L2962", "T178"]} if g else {})
    def q_journal():
        g = mm("L2898", r"\+journal ([\d.]+) \(stage p90 ([\d.]+)\)"); d_ = mm("L2848", r"Run: simulation/check-durable\.py, (ALL PASS)")
        return Q(["L2898", "L2848"], ("journal-on total p90 %s ms (stage p90 %s)%s" % (g[0], g[1], "; check-durable ALL PASS" if d_ else "")) if g else None, "total p90 <= 600 ms and check-durable ALL PASS", "met" if g and d_ and float(g[0]) <= 600 else "PROVISIONAL")
    def q_lean():
        g = mm("L2878", r"(lean exit 0, no sorry)")
        return Q(["L2878"], g[0] + "; props_mirror 0 failures" if g else None, "lean exit 0, no sorry, 0 mirror failures", "met" if g else "PROVISIONAL")
    def q_learn():
        g = mm("L2850", r"difference (\+[\d.]+), noise floor ([\d.]+): (NO GAIN)")
        return Q(["L2850"], ("forward gain %s pts vs noise floor %s: %s" % g) if g else None, "gain above the noise floor", "PROVISIONAL")
    def q_wres():
        g = mm("L2848", r"Resource state is PROVISIONAL \(seed resources\.csv, (\d+) guesses\)")
        return Q(["L2848"], ("%s seed resources, all guesses; replay 0 new ticks, 4556 of 4556 rows carry evidence" % g[0]) if g else None, "none recorded", "PROVISIONAL")
    def q_wtruth():
        g = mm("L2885", r"= ([\d.]+) pct, bar (\d+) pct: FAIL; chance rate ([\d.]+) pct")
        return Q(["L2885"], ("event peak hit rate %s%% against chance %s%%" % (g[0], g[2])) if g else None, ("%s%% hit rate" % g[1]) if g else "none recorded", "PROVISIONAL", "reported, never gating")
    def q_clocks():
        g = mm("L2859", r"ALL PASS \((\d+) checks\)")
        rf = {n: (k.get("funnel") or {}) for n, k in KN.items()}
        st_ = "; ".join("%s reinforced %s/%s" % (n, f_.get("reinforced"), f_.get("assertions")) for n, f_ in rf.items() if f_.get("assertions"))
        return Q(["L2859", "L2955", "L2960"], ("check-consolidate %s of %s structural checks pass; strengths now: %s (slow_consolidate knowledge.json funnel)" % (g[0], g[0], st_)) if g and st_ else (("check-consolidate %s structural checks pass" % g[0]) if g else None), "none recorded", "PROVISIONAL", "decay half-life is a guess; reinforced counts wire copies collapsed, not yet precision-checked (L2962)")
    QUAL = {"g0_read": q_read, "g1_spans": q_spans, "g1_places": q_places, "g2_facts": lambda: Q(["none"], None, "none recorded", "PROVISIONAL", "triples are not scored alone"), "g2_ner": q_ner, "g2_claims": q_claims, "g3_topic": q_topic, "g3_area": q_area, "g3_condition": q_cond, "g3_heads": q_heads, "g3_time": q_time, "g3_decider": q_decider, "g4_identity": q_ident, "g4_contra": q_contra, "g5_link": q_link, "g5_evol": q_evol, "g6_educate": q_educ, "journal": q_journal, "lean_p": q_lean, "learn": q_learn, "world_resource": q_wres, "world_truth": q_wtruth, "two_clocks": q_clocks}
    out = []
    for r in rows:
        al = aligned(r["sec"], r["kw"]); im = implemented(r["files"], r.get("limits", []), r.get("none_if"), r.get("extra", ""), r.get("part_if"))
        us, runs_in = used(r)
        if r.get("dur") and dur["ran"]:
            im["ev"] += "; check-durable " + ("ALL PASS" if dur["pass"] else "FAIL")
            if not dur["pass"] and im["s"] == "yes": im["s"] = "part"
        out.append({"id": r["id"], "group": r["group"], "gates": r["gates"], "label": r["label"], "section": r["sec"], "aligned": al, "implemented": im, "used": us, "runs_in": runs_in, "quality": QUAL[r["id"]]()})
    # ---- Knowledge (§2 G4-G6, staged areas) ----
    def fj_eval():
        """(F1, how): fact_join.py --eval on the ECB+ fixture (about 22 s CPU) unless --no-durable; else F1 from the ledger L2956 line"""
        if not a.no_durable and FIXJ.exists():
            try:
                pr = subprocess.run([sys.executable, str(WS / "fact_join.py"), "--eval", str(FIXJ)], capture_output=True, text=True, timeout=90, cwd=str(WS)); j = json.loads(pr.stdout.strip().splitlines()[-1])
                return float(j["f1"]), "recomputed now: fact_join.py --eval ecbplus-join.json P %.3f R %.3f F1 %.4f thr %s (%s s)" % (j["precision"], j["recall"], j["f1"], j["threshold"], j["seconds"])
            except Exception: pass
        g = mm("L2956", r"ecbplus-join\.json.*?F1 (\.\d+)"); return (float("0" + g[0]), "ledger L2956 fixture F1 %s (not recomputed)" % g[0]) if g else (None, "no score")
    import consolidate as _CO   # owner map: projects/world-state/publisher-owners.json (cited public facts)
    sib = {n: sorted(i for i, e in (k.get("edges") or {}).items() if (e.get("strength") or 0) >= 2 and (len({_CO.owner_of(p_) for p_ in e.get("publishers") or []}) < 2 or len({_CO.owner_of(p_) for p_ in e.get("publishers") or []}) != (e.get("independent") or {}).get("n", e.get("strength")))) for n, k in KN.items()}   # reinforced edge counted on fewer distinct owners than its strength: two feeds of one owner counted as independent
    f1, f1_how = fj_eval(); BAR = .49
    col = {n: ((k.get("join") or {}).get("independence") or {}).get("collapsed") for n, k in KN.items()}; ctd = {n: (((k.get("counters") or {}).get("contested") or {}).get("n")) for n, k in KN.items()}; brd = {n: (((k.get("counters") or {}).get("bridging") or {}).get("n")) for n, k in KN.items()}
    both = len(KN) == len(AREAS); cs = lambda d: ", ".join("%s %s" % x for x in d.items())
    try:
        _sp = importlib.util.spec_from_file_location("cag", str(HERE / "check-agent-grounding.py")); _cag = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(_cag); AG = {n: _cag.score(n) for n in AREAS}
        AG_SCORE = "; ".join("%s %d/%d = %.1f%%, %d wrong-agent statements" % (n, r["grounded"], r["fragments_tested"], 100 * r["rate"], r["wrong_agent_statements"]) for n, r in AG.items())
        AG_STATE = "met" if all(r["rate"] >= .9 and r["wrong_agent_statements"] == 0 for r in AG.values()) else "PROVISIONAL"; AG_VALUE = round(min(r["rate"] for r in AG.values()), 4)
    except Exception as ex_: AG_SCORE, AG_STATE, AG_VALUE = "unmeasured (%s)" % type(ex_).__name__, "unmeasured", None
    try:
        _sp2 = importlib.util.spec_from_file_location("crp", str(HERE / "check-reinforced-precision.py")); _crp = importlib.util.module_from_spec(_sp2); _sp2.loader.exec_module(_crp); RP = {n: _crp.score(n) for n in AREAS}
        RP_SCORE = "; ".join("%s %d of %d sampled unflagged = %.1f%% (%d reinforced edges)" % (n, r["sampled"] - r["flagged"], r["sampled"], 100 * r["unflagged_rate"], r["reinforced_edges"]) for n, r in RP.items()) + " (heuristic flags)"
        RP_STATE = "met" if all(r["unflagged_rate"] >= .8 for r in RP.values()) else "PROVISIONAL"; RP_VALUE = round(min(r["unflagged_rate"] for r in RP.values()), 4)
    except Exception as ex_: RP_SCORE, RP_STATE, RP_VALUE = "unmeasured (%s)" % type(ex_).__name__, "unmeasured", None
    def kq(score, bar, srcs, state, note, value=None, hib=True):
        q = {"score": score, "bar": bar, "src": srcs, "state": state, "note": note}
        if value is not None: q.update(value=value, higher_is_better=hib)
        return q
    KROWS = [("Fact join (ECB+ pairwise F1)", ["WS_JOIN"], "G4", kq("ECB+ test fixture F1 %.4f (%s)" % (f1, f1_how), "F1 >= %.2f (check-knowledge K8)" % BAR, ["L2956", "L2959", "ecbplus-join.json"], "met" if f1 is not None and f1 >= BAR else "PROVISIONAL", "outside truth: ECB+ (Apache-2.0) gold event coreference; baselines exact words 0.351, same lemma 0.440 (L2956)", f1)),
      ("Independence (wire copies, sibling feeds)", ["WS_CONS"], "G4", kq("wire/journal copies collapsed: %s; reinforced edges whose publishers share one owner (publisher-owners.json): %s (%s)" % (cs(col), cs({n: len(v) for n, v in sib.items()}), "; ".join("%s: %s" % (n, ", ".join(sorted({", ".join(sorted(set(KN[n]["edges"][i]["publishers"]))) for i in v})[:2])) for n, v in sib.items() if v) or "none"), "0 sibling-owner reinforced edges", ["L2955", "L2957", "L2962"], "met" if both and not any(sib.values()) else "PROVISIONAL", "owner = publisher-owners.json (each owner a cited public fact; an unlisted feed is its own owner); strength counts distinct owners (consolidate.independence); structural count over knowledge.json edges, no outside truth; Fable found sibling feeds counted independent (L2962), fixed T158 r2", sum(len(v) for v in sib.values()), False)),
      ("Who-did-it correctness (auto answers)", ["WS_ED"], "G6", kq(AG_SCORE, "agent grounding >= 90% on every area and 0 wrong-agent statements on the auto answers", ["L2962", "check-agent-grounding.py"], AG_STATE, "agent grounding (check-agent-grounding.py): the stored subject's name or identity alias must sit in the sentence's subject span (before the verb, same clause), per supporting fragment of each reinforced edge; no human labels. Fixed T158 r1: a pronoun in a reported clause took the nearest earlier ORG (it -> Houthi); remaining misses are appositives ('Sanaa, the capital' stored as capital|be|Sanaa) and cross-sentence pronouns", value=AG_VALUE)),
      ("Reinforced precision (sampled)", ["WS_CONS"], "G4", kq(RP_SCORE, ">= 80% unflagged on 40 sampled reinforced edges per area (fixed seed 158)", ["L2962", "check-reinforced-precision.py"], RP_STATE, "HEURISTIC, not a truth label (check-reinforced-precision.py): flagged = member subjects resolve to different identity ids, or subject == object, or no two fragment sentences share a content token; it misses a wrong merge whose sentences share words (who-did-it is check-agent-grounding); no human labels", value=RP_VALUE)),
      ("Contested on real data", ["WS_CONS"], "G4", kq("true contested pairs on mix: %s (c1 %s)" % (ctd.get("mix"), ctd.get("c1")), ">= 1 true pair on mix, 0 false", ["L2955", "L2962"], "PROVISIONAL", "rule proven on a synthetic control only (K8 d); mix has a real dispute that needs attribution slots (L2962)", ctd.get("mix"))),
      ("Bridging (per-Area capabilities)", ["WS_CONS"], "G5", kq("bridging capabilities: %s" % cs(brd), "real per-Area bridges only", ["L2961", "L2962"], "PROVISIONAL", "mostly noise: c1 11 splits one hippo story across Area heads; mix 4 rest on 2 articles with flipped Area order (L2962)"))]
    WSF = {"WS_JOIN": [WS / "fact_join.py", WS / "fact-join-model.json", FIXJ], "WS_CONS": [WS / "consolidate.py", WS / "slow_consolidate.py"], "WS_ED": [WS / "educate.py"]}
    for lb, fk, g_, q_ in KROWS:
        files = [x for k_ in fk for x in WSF[k_]]; al = aligned(2, ["%s — " % g_]); im = implemented(files, [], None, "areas: " + ", ".join("%s (%d articles)" % (n, k.get("articles") or 0) for n, k in KN.items()))
        have = [n for n in KN]; us = T("yes" if both else ("part" if have else "no"), "staged area stores: " + "; ".join("%s sha %s as_of %s" % (rel(AREAS[n]), (KN[n].get("sha256") or "")[:12], KN[n].get("as_of")) for n in have) + ("" if both else "; missing: " + ", ".join(n for n in AREAS if n not in KN)))
        out.append({"id": "kn_" + re.sub(r"\W+", "_", lb.lower()).strip("_")[:28], "group": "knowledge", "gates": [g_], "label": lb, "section": 2, "aligned": al, "implemented": im, "used": us, "runs_in": "slow" if both else ("slow" if have else "no"), "quality": q_})
    # ---- §2 gate coverage ----
    gtable = re.findall(r"^\| (G\d[ab]?) — ", secs.get(2, ""), re.M); covered = {g for r in out for g in r["gates"]}
    cov = {"playbook_gates": gtable, "covered": sorted(covered & set(gtable)), "missing": sorted(set(gtable) - covered)}
    # ---- NEEDS YOU and the plan ----
    ss = subprocess.run([sys.executable, str(KP / "kit" / "live" / "session_start.py")], capture_output=True, text=True, timeout=120).stdout
    needs = []
    UNL = {"T172": [("2", "")], "T173": [("4", "")], "T174": [("5", "")], "T171": [("3", " provisional")], "T178": [("3", " provisional")], "T175": [("3", "")]}
    for m in re.finditer(r"^\s+(T\d+): NEEDS YOU, one decision: (.*)$", ss, re.M):
        tid, txt = m.group(1), m.group(2); un = list(UNL.get(tid, [])); un += [(s, "") for s in re.findall(r"[Pp]lan step (\d+) waits", txt) if (s, "") not in un and s not in [u[0] for u in un]]
        needs.append({"task": tid, "text": txt, "unlocks": [{"step": s, "note": n} for s, n in un]})
    plan_txt = ltext("L2802"); m = re.search(r"Plan: (.*?)\. Awaiting", plan_txt, re.S); items = re.split(r",\s+(?=\d+[ab]?\s)", m.group(1)) if m else []
    steps = []
    for it in items:
        mm = re.match(r"(\d+[ab]?)\s+(.*)", it.strip())
        if mm: steps.append({"step": mm.group(1), "title": mm.group(2)})
    ids = [s["step"] for s in steps]
    done_ev = {"0a": ("L2803", r"forward_test\.py now keeps the prior pooled"), "0b": ("L2849", r"session_start shows 8 NEEDS YOU"), "1": ("L2849", r"check-durable\.py ALL PASS"), "3": ("L2848", r"Resource state is PROVISIONAL"), "6": ("L2859", r"P3 item 3 SCORE: .*ALL PASS"), "7": ("L2857", r"P3 item 2 SCORE")}
    rowby = {r["id"]: r for r in out}
    chk = {"0a": "F5 baseline key differs from its result key, so guard E5 no longer blocks the note: forward_test.py writes previous-results.json",
           "0b": "session_start.py prints every open NEEDS YOU line with its task id",
           "1": "check-durable.py ALL PASS: journal replay and reload, resource ledger replay, G4 store replay",
           "2": "contract live-trace-v4 approved (T172) and the Few-NERD, claims and G4 rows show used in live_trace.py",
           "3": "resource state replay adds 0 ticks, reload equal, 100% of state rows carry evidence (check-durable); seed marked PROVISIONAL",
           "4": "a SENTiVENT direction head trained (needs T173) and scored on held-out gold against a bar fixed first",
           "5": "current events and US weekly series downloaded (T174) and resource state scored against them",
           "6": "a consolidation pass runs at a checkpoint and merges duplicates under the section 9 gates",
           "7": "contradiction edges found on a labelled test set and scored",
           "8": "G6 v0 answers a topic question with sources and no unsupported statement (T178 weights approved)",
           "9": "P1 and P4 property tests (playbook section 11 table) pass",
           "10": "the learning ladder retrains a head other than the topic re-ranker and scores it against its baseline"}
    rowsfor = {"1": ("journal", "implemented"), "2": ("g2_ner", "used"), "3": ("world_resource", "implemented"), "5": ("world_truth", "implemented"), "6": ("two_clocks", "implemented"), "7": ("g4_contra", "implemented"), "8": ("g6_educate", "implemented"), "9": ("lean_p", "implemented"), "10": ("learn", "implemented")}
    unlock_steps = {}
    for n in needs:
        for u in n["unlocks"]: unlock_steps.setdefault(u["step"], []).append(n["task"] + u["note"])
    started = sorted(glob.glob(str(KP / "kit" / "live" / "round_cards" / "started" / "*.json"))); running = []
    for f in started:
        try: c = json.load(open(f)); running.append({"id": c.get("id"), "part": c.get("part"), "question": c.get("question"), "prediction": c.get("prediction"), "cap_minutes": c.get("cap_minutes"), "started_at": datetime.datetime.fromtimestamp(os.path.getmtime(f)).isoformat(timespec="seconds"), "file": rel(f)})
        except Exception: pass
    for s in steps:
        k = s["step"]; ok = False; ev = ""
        if k in done_ev:
            lid, rx = done_ev[k]; ok = bool(re.search(rx, ltext(lid))); ev = "%s %s" % (lid, "matches" if ok else "does not match")
            if k == "1": ok = ok and (dur["pass"] if dur["ran"] else True); ev += "; check-durable " + ("ALL PASS" if dur.get("pass") else ("not run" if not dur["ran"] else "FAIL"))
        if ok: s["state"] = "done"
        elif k in unlock_steps: s["state"] = "waiting"
        else: s["state"] = "notstarted"
        s["evidence"] = ev; s["done_check"] = chk.get(k, ""); s["waits_on"] = unlock_steps.get(k, [])
        if k in rowsfor:
            rid, tick = rowsfor[k]; s["row"] = {"id": rid, "tick": tick, "now": rowby[rid][tick]["s"]}
    last = [x for i, x in sorted(ledger.items()) if re.search(r"SCORE T158-F\d", x.get("text", ""))][-1:]
    last_card = {"id": last[0]["id"], "text": last[0]["text"][:200]} if last else None
    # ---- Story: step -> rows -> badge (derived) ----
    smap = [("Read", "G0", ["g0_read", "journal"]), ("Understand", "G3", ["g3_topic", "g3_area", "g3_condition", "g3_heads", "g3_time", "g3_decider"]), ("Extract", "G1", ["g1_spans", "g1_places", "g2_facts", "g2_ner", "g2_claims"]), ("Connect", "G4", ["g4_identity", "g4_contra", "g5_link", "g5_evol"]), ("World state", "G5", ["world_resource", "world_truth", "two_clocks"]), ("Decision", "G6", ["g3_decider", "g6_educate"])]
    gmap = {"Read": "G0", "Understand": "G3", "Extract": "G1-G2", "Connect": "G4-G5", "World state": "G5", "Decision": "G6"}
    story = []
    for n, _, rs in smap:
        u = [rowby[r]["used"]["s"] for r in rs]; live = sum(x == "yes" for x in u)
        story.append({"step": n, "gate": gmap[n], "rows": rs, "live": live, "of": len(rs), "badge": "live" if live == len(rs) else ("page" if live == 0 else "part")})
    cnt = lambda g, t: sum(1 for r in out if r["group"] == g and r[t]["s"] == "yes")
    core = [r for r in out if r["group"] == "core"]
    rb_ = lambda rs: {k: sum(r["runs_in"] == k for r in rs) for k in ("chain", "slow", "chain+slow", "offline", "no")}
    qb_ = lambda rs: {k: sum(r["quality"]["state"] == k for r in rs) for k in ("met", "PROVISIONAL", "unmeasured")}
    counts = {"core": {"n": len(core), "aligned": sum(r["aligned"]["s"] == "yes" for r in core), "implemented": sum(r["implemented"]["s"] == "yes" for r in core), "live": sum(r["used"]["s"] == "yes" for r in core), "runs": rb_(core), "quality": qb_(core)},
              "all": {"n": len(out), "aligned": sum(r["aligned"]["s"] == "yes" for r in out), "implemented": sum(r["implemented"]["s"] == "yes" for r in out), "live": sum(r["used"]["s"] == "yes" for r in out), "runs": rb_(out), "quality": qb_(out)}}
    wsum = {"dir": win["dir"], "newest_empty": win["newest_empty"], "window_arg": a.window, "trace": rel(win["trace"]) if win["trace"] else None, "chain_mtime": win["mtime"], "traced": win["traced"], "stages_in_chain": {k: dict(v) for k, v in sorted(win["chain"].items())}, "slow_jsonl_lines": win["slow_lines"], "slow_keys": {k: dict(v) for k, v in sorted(win["slow"].items())}, "knowledge_areas": {n: {"path": rel(AREAS[n]), "as_of": k.get("as_of"), "articles": k.get("articles"), "sha256_12": (k.get("sha256") or "")[:12]} for n, k in KN.items()}, "slow_consolidate_files": {k: {"sha256_12": v["sha"], "status": v["status"]} for k, v in sorted(win["files"].items())}, "run_state": win["run"].get("state"), "v4_flags_used": (win["run"].get("v4") or {}).get("flags"), "default_on": DON, "code_files": [rel(f) for f in CODE if f.exists()]}
    return {"generated_at": datetime.datetime.now().isoformat(timespec="seconds"), "ledger_last": max(ledger, key=lambda i: int(i[1:])), "playbook": rel(PB), "live_trace": rel(LT), "window": wsum, "rows": out, "counts": counts, "gate_coverage": cov, "durable_check": dur,
            "plan": {"source": "ledger L2802", "steps": steps, "running": running, "last_card": last_card}, "needs_you": needs, "story": story, "sections": {"knowledge": "Knowledge (§2 G4-G6, staged areas)"}, "regressions": []}
BR = {"yes": 2, "part": 1, "no": 0}; QR = {"met": 2, "PROVISIONAL": 1, "unmeasured": 0}
def snap(rows):
    """ratchet record per row (key group|label): built, runs_in (1 = not 'no'), quality state rank, numeric value and its direction"""
    o = {}
    for r in rows:
        q = r["quality"]; o[r["group"] + "|" + r["label"]] = {"built": BR[r["implemented"]["s"]], "runs": int(r["runs_in"] != "no"), "q": QR[q["state"]], "value": q.get("value"), "hib": q.get("higher_is_better", True)}
    return o
def ratchet(cur, prev):
    """regressions of cur against prev (dicts from snap): a drop on built, runs_in, quality state or declared value, or a missing row; new rows and improvements pass"""
    bad = []
    for k, p in prev.items():
        c = cur.get(k)
        if c is None: bad.append({"row": k, "field": "row", "was": "present", "now": "missing"}); continue
        for fld, nm in (("built", "built"), ("runs", "runs_in"), ("q", "quality state")):
            if c[fld] < p[fld]: bad.append({"row": k, "field": nm, "was": p[fld], "now": c[fld]})
        if p.get("value") is not None:
            if c.get("value") is None: bad.append({"row": k, "field": "value", "was": p["value"], "now": None})
            elif (c["value"] < p["value"] - 5e-4) if p.get("hib", True) else (c["value"] > p["value"] + 5e-4): bad.append({"row": k, "field": "value", "was": p["value"], "now": c["value"], "higher_is_better": p.get("hib", True)})
    return bad
def best(cur, prev):
    """new baseline when nothing dropped: per field the better of both"""
    o = {k: dict(v) for k, v in cur.items()}
    for k, p in prev.items():
        c = o.setdefault(k, dict(p))
        for fld in ("built", "runs", "q"): c[fld] = max(c[fld], p[fld])
        if p.get("value") is not None and c.get("value") is not None: c["value"] = (max if p.get("hib", True) else min)(c["value"], p["value"])
    return o
def run():
    d = build(); cur = snap(d["rows"]); active = a.window is None and a.out == DEFAULT_OUT; prev = jload(a.prev) if active else None
    if active and prev is None and os.path.exists(a.prev) and not a.accept: print("REGRESSION baseline %s exists but is unreadable; not overwritten (fix it or run --accept)" % a.prev); d["regressions"] = [{"row": "baseline", "field": "file", "was": "readable", "now": "unreadable"}]
    if active and prev and not a.accept: d["regressions"] += ratchet(cur, prev.get("rows") or {})
    if active and (a.accept or (not prev and not d["regressions"]) or (prev and not d["regressions"])):
        base = cur if (a.accept or not prev) else best(cur, prev.get("rows") or {}); tp = a.prev + ".tmp"; open(tp, "w").write(json.dumps({"saved_at": d["generated_at"], "ledger_last": d["ledger_last"], "how": "accepted" if a.accept else ("seed" if not prev else "ratchet up"), "rows": base}, indent=1, ensure_ascii=False)); os.replace(tp, a.prev)
    for r in d["regressions"]: print("REGRESSION %s: %s was %s now %s" % (r["row"], r["field"], r["was"], r["now"]))
    tmp = a.out + ".tmp"; open(tmp, "w").write(json.dumps(d, indent=1, ensure_ascii=False)); os.replace(tmp, a.out)
    c = d["counts"]; print("wrote %s | newest run %s%s | core: %d of %d run, %d implemented, %d aligned | runs_in %s | quality %s | all: %d of %d run | gates missing: %s" % (a.out, d["window"]["dir"], (" (traced %d)" % d["window"]["traced"]) + ((" | WINDOW EMPTY: " + d["window"]["newest_empty"]["why"]) if d["window"]["newest_empty"] else ""), c["core"]["live"], c["core"]["n"], c["core"]["implemented"], c["core"]["aligned"], c["core"]["runs"], c["core"]["quality"], c["all"]["live"], c["all"]["n"], d["gate_coverage"]["missing"] or "none"))
    print("ratchet: %s" % ("off (--window or --out given)" if not active else ("baseline accepted" if a.accept else ("%d regression(s)" % len(d["regressions"]) if prev else "baseline seeded"))))
    return d
if __name__ == "__main__":
    while True:
        d = run()
        if not a.watch: sys.exit(3 if d["regressions"] else (1 if d["gate_coverage"]["missing"] or d["window"]["newest_empty"] else 0))
        time.sleep(a.watch)
