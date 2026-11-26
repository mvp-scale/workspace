"""check-developments: the gate of developments v0 (projects/world-state/developments_v0.py; page feed /api/raw/developments via raw-units.py developments()). PROVISIONAL: only STRUCTURAL assertions fail.
Runs the module directly (import, no server) on the two staged area windows (demo/mockups/structure-live/area-c1, area-mix; read only, CPU, offline, no model, no hosted call).
  D1 build        both windows build; compression (articles / developments) >= 4; >= 3 non-thin developments each
  D2 quotes       every title is a member headline and every summary / assertion line / forward statement / stated cause / contradiction quote is a verbatim source sentence (exists in the window's data)
  D3 words        every development has one of the four certainty words; disputed only with named speakers on both sides
  D4 contradiction mix has >= 1 development with a contradiction; pairs about one assertion collapse (contradictions attached < pairs in knowledge.contested)
  D5 known case   an area with bars.known_case has a development whose members include the headline (all title_all regexes match); areas.json bars, no area named here
  D6 ids          no development id repeats; ids come from the member article ids
  D7 since        the cut is selectable: a cut at the last article leaves nothing new; a cut before the first leaves the default priority proxies valid; every proxy is one of the three named
  D8 determinism  two builds (cache cleared) are identical; the module imports no network or model library
  D9 stable ids  (round D) replay at 25/50/75/100% article-count cuts with the carry rule: survival >= 90% on the stream window runs-e2e-101 (info on each area), 0 id collisions, seeded shuffle gives the same ids and memberships, one append-only history file per development at every cut
    python3 simulation/check-developments.py [--area c1,mix]"""
import sys, os, json, re, importlib, copy
HERE = os.path.dirname(os.path.abspath(__file__)); KP = os.path.dirname(HERE); WS = os.path.join(KP, "projects", "world-state"); sys.path.insert(0, WS)
STRUCT = os.path.abspath(os.path.join(KP, "..", "demo", "mockups", "structure-live"))
import developments_v0 as DV
args = sys.argv[1:]; AREAS = args[args.index("--area") + 1].split(",") if "--area" in args else [a_["key"] for a_ in json.load(open(os.path.join(KP, "simulation", "fixtures", "knowledge", "areas.json")))]
res = []
AREAS_JSON = os.path.join(KP, "simulation", "fixtures", "knowledge", "areas.json")   # per-area bars (round A, L3012): the gate names no area
BARS = {a_["key"]: a_.get("bars") for a_ in json.load(open(AREAS_JSON))}
def ok(name, cond, msg=""): res.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + (("  " + msg) if msg else ""), flush=True)
def td_of(a): return os.path.join(STRUCT, "area-" + a, "trace")
def norm(s): return re.sub(r"\s+", " ", s or "").strip()
WORDS = {"established", "reported", "single source", "disputed"}; PROX = {DV.MOVED, DV.SINGLE, DV.NOTHING}
B = {}
for a in AREAS:
    if not isinstance(BARS.get(a), dict) or not {"counters_gt0", "known_case", "contradiction_min"} <= set(BARS[a]):
        ok("D0 bars %s" % a, False, "area missing from areas.json or without a complete bars block (counters_gt0, known_case, contradiction_min)"); continue
    td = td_of(a)
    if not os.path.exists(os.path.join(td, "slow_consolidate", "knowledge.json")): ok("D1 build %s" % a, False, "area window not staged (start the server once, or run build_area)"); continue
    DV._CACHE.clear(); B[a] = DV.build(td, a)
for a, r in B.items():
    n = r["window"]["articles"]; L = r["developments"]; T = r["thin"]
    ok("D1 build %s: exists, compression %.1f >= 4 (%d articles -> %d developments), non-thin %d >= 3, thin %d" % (a, r["counts"]["compression"] or 0, n, len(L), len(L), len(T)), r["exists"] and (r["counts"]["compression"] or 0) >= 4 and len(L) >= 3)
    td = td_of(a); K = json.load(open(os.path.join(td, "slow_consolidate", "knowledge.json")))
    titles = {norm(x["title"]) for x in DV._articles(td)}
    sents = [norm(f.get("sent")) for e in K["edges"].values() for f in e.get("fragments") or []]; blob = "\n".join(sents)
    cq = {norm(s.get("quote")) for c in K.get("contested") or [] for s in (c.get("sides") or {}).values()}
    bad = []; cnt = 0
    for d in L + T:
        if norm(d["title"]) not in titles: bad.append(("title", d["title"][:60]))
        cnt += 1
        if d["summary"] is not None:
            cnt += 1
            if norm(d["summary"]["quote"]) not in sents: bad.append(("summary", d["summary"]["quote"][:60]))
        qs = [x["quote"] for x in d["know"] if x["quote"]] + [i["quote"] for s in d["follow"]["steps"] for i in s["items"] if i["quote"]] + [x["quote"] for x in d["expect"]["statements"]] + [x["quote"] for x in d["follow"]["stated_causes"]] + [x["quote"] for x in d["since"]["lines"] if x["quote"]]
        cnt += len(qs); bad += [("line", q[:60]) for q in qs if norm(q) not in sents]
        bad += [("contradiction", s["quote"][:60]) for c in d["contradictions"] for s in c["sides"] if norm(s["quote"]) not in cq]
        for x in d["know"]:
            bad += [("evidence", r_["quote"][:60]) for r_ in x["evidence"] if norm(r_["quote"]) not in sents]
        if not d["thin"] and d["summary"] is None: bad.append(("no summary", d["title"][:60]))
    ok("D2 quotes %s: %d quoted titles and lines, all verbatim in the window's data, every non-thin development has a quoted summary" % (a, cnt), not bad, str(bad[:3]))
    wb = [d["title"][:40] for d in L + T if d["certainty_word"] not in WORDS or (d["certainty_word"] == "disputed" and not any(c["speakers_named_both_sides"] for c in d["contradictions"]))]
    ok("D3 words %s: %s" % (a, sorted({d["certainty_word"] for d in L + T})), not wb, str(wb))
    ok("D6 ids %s: %d ids, no repeat" % (a, len(L + T)), len({d["id"] for d in L + T}) == len(L + T) and all(re.fullmatch(r"dev:[0-9a-f]{10}", d["id"]) for d in L + T))
    last = r["cut"]["last_seq"]; r2 = DV.build(td, a, last); r0 = DV.build(td, a, -1)
    ok("D7 since %s: cut at last seq -> all 'nothing new' (%s); cut before first -> proxies named; default cut after #%s leaves %d new articles; moved first in the list" % (a, sorted({d["moved"] for d in r2["developments"]}), r["cut"]["seq"], r["cut"]["articles_after"]),
       all(d["moved"] == DV.NOTHING for d in r2["developments"] + r2["thin"]) and all(d["moved"] in PROX for d in r0["developments"] + r["developments"]) and [DV.MOVED_ORDER[d["moved"]] for d in L] == sorted(DV.MOVED_ORDER[d["moved"]] for d in L) and r["cut"]["articles_after"] >= 1)
    DV._CACHE.clear(); r3 = DV.build(td, a)
    ok("D8 determinism %s: two builds identical" % a, json.dumps(r, sort_keys=True) == json.dumps(r3, sort_keys=True))
lex_off = os.environ.get("KP_LEXICONS", "on").strip().lower() == "off"   # D4 tests the attack lexicon (declared in L3011): off, a failure is a SKIP
for a, r in B.items():
    bars = BARS[a]; cmin = bars["contradiction_min"]
    if cmin is None: print("SKIP (no contradiction_min in the %s bars) D4 contradiction %s" % (a, a), flush=True)
    else:
        K = json.load(open(os.path.join(td_of(a), "slow_consolidate", "knowledge.json"))); pairs = len(K.get("contested") or [])
        cd = [d for d in r["developments"] + r["thin"] if d["contradictions"]]; ncon = sum(len(d["contradictions"]) for d in cd)
        d4 = len(cd) >= cmin and ncon < pairs
        if d4 or not lex_off: ok("D4 contradiction %s: %d development(s) with a contradiction (bar >= %d); %d pairs collapse to %d contradiction(s)" % (a, len(cd), cmin, pairs, ncon), d4)
        else: print("SKIP (lexicons off, needs attack.*) D4 contradiction %s: %d development(s), %d pairs, %d contradiction(s)" % (a, len(cd), pairs, ncon), flush=True)
    kc = bars["known_case"]
    if kc is None: print("SKIP (no known_case in the %s bars) D5 known case %s" % (a, a), flush=True)
    else:
        hit = [d for d in r["developments"] + r["thin"] if any(all(re.search(x, m["title"], re.I) for x in kc["title_all"]) for m in d["members"])]
        ok("D5 known case %s: a development contains the headline matching %s (%s; %s)" % (a, kc["title_all"], "; ".join("%d articles" % d["articles"] for d in hit), kc["why"]), len(hit) >= 1)
src = open(os.path.join(WS, "developments_v0.py")).read()
ok("D8 determinism: no network, model or random import in developments_v0.py", not re.search(r"^\s*(import|from)\s+(requests|urllib|http|socket|random|torch|onnxruntime|transformers|openai|anthropic)", src, re.M))
# ---- D9 stable ids across cuts (round D, L3015): rule = a development carries the id of the previous-cut development whose members are >= 50% contained in it (developments_v0.build(prev=...)); the checks below recompute the survival from members only
import tempfile, shutil
import developments_history as H
STREAM = os.path.join(STRUCT, "runs-e2e-101", "trace")   # multi-cut stream window (464 articles, not an area): the survival bar is measured here
SEED = 20261124; FRACS = (0.25, 0.5, 0.75, 1.0); SURV_BAR = 0.90
def _replay(td, label, shuffle_seed=None, hist_root=None):
    """build the window at article-count cuts, each with prev = the previous cut's members; -> [{m, devs: {id: [article ids]}, ids: [ids as listed], res}]"""
    arts = DV._articles(td); order = [x["id"] for x in arts]; n = len(order); out = []; prev = None
    for f in FRACS:
        m = max(1, int(round(n * f))); DV._CACHE.clear()
        r = DV.build(td, label, only=set(order[:m]), prev=prev, shuffle_seed=shuffle_seed)
        devs = DV.members_of(r); ids = [d["id"] for d in r["developments"] + r["thin"]]
        out.append({"m": m, "devs": {k: sorted(v) for k, v in devs.items()}, "ids": ids, "res": r}); prev = devs
        if hist_root: H.append(r, hist_root, "%s@%d" % (label, m))
    return out
def _survival(A, B):
    """A, B = {id: members} at cut k and k+1. Eligible: A dev with >= 2 articles whose members are >= 50% contained in one B dev (the one with the most overlap). Returns n, kept, and the Jaccard-based n, kept (info)."""
    n = kept = jn = jk = 0
    for pid, pm in A.items():
        if len(pm) < 2: continue
        ps = set(pm); best = None; bj = None
        for nid, nm in B.items():
            inter = len(ps & set(nm))
            if not inter: continue
            c = inter / len(ps); j = inter / len(ps | set(nm))
            if best is None or (c, nid == pid) > (best[0], best[2]): best = (c, nid, nid == pid)
            if bj is None or (j, nid == pid) > (bj[0], bj[2]): bj = (j, nid, nid == pid)
        if best and best[0] >= 0.5: n += 1; kept += best[2]
        if bj and bj[0] >= 0.5: jn += 1; jk += bj[2]
    return n, kept, jn, jk
WIN = [("%s" % a, td_of(a), False) for a in AREAS if a in B] + [("stream:runs-e2e-101", STREAM, True)]
RP = {}; tmp = tempfile.mkdtemp(prefix="check-dev-hist-")
try:
    for label, td, bar in WIN:
        if not os.path.exists(os.path.join(td, "slow_consolidate", "knowledge.json")) or not os.path.exists(os.path.join(td, "chain.jsonl")):
            ok("D9 window %s" % label, False, "trace missing: %s" % td); continue
        RP[label] = (_replay(td, label, None, os.path.join(tmp, label.replace(":", "_"))), _replay(td, label, SEED, None), td, bar)
    for label, (R, RS, td, bar) in RP.items():
        tot = [0, 0, 0, 0]; parts = []
        for k in range(len(R) - 1):
            sv = _survival(R[k]["devs"], R[k + 1]["devs"]); parts.append("%d->%d: %d/%d" % (R[k]["m"], R[k + 1]["m"], sv[1], sv[0])); tot = [x + y for x, y in zip(tot, sv)]
        share = tot[1] / tot[0] if tot[0] else None; jsh = tot[3] / tot[2] if tot[2] else None
        msg = "%s; containment: %d of %d keep their id = %s; Jaccard info: %d of %d = %s" % ("; ".join(parts), tot[1], tot[0], "%.1f%%" % (100 * share) if share is not None else "n/a", tot[3], tot[2], "%.1f%%" % (100 * jsh) if jsh is not None else "n/a")
        if bar: ok("D9a survival %s (>= %d%% of developments with >= 2 articles whose members are >= 50%% contained keep the id): %s" % (label, SURV_BAR * 100, msg), tot[0] > 0 and share >= SURV_BAR)
        else: print("INFO D9a survival %s (single window, not a bar): %s" % (label, msg), flush=True)
    ok("D9b collisions: 0 duplicate ids at every cut (%s)" % "; ".join("%s %s" % (l, "/".join(str(len(c["ids"]) - len(set(c["ids"]))) for c in R)) for l, (R, _, _, _) in RP.items()),
       bool(RP) and all(len(c["ids"]) == len(set(c["ids"])) for R, _, _, _ in RP.values() for c in R))
    same = {l: all(a["devs"] == b["devs"] for a, b in zip(R, RS)) for l, (R, RS, _, _) in RP.items()}
    twice = {}
    for l, (R, RS, td, _) in RP.items():
        DV._CACHE.clear(); prevm = R[-2]["devs"] if len(R) > 1 else None; order = [x["id"] for x in DV._articles(td)]
        r1 = DV.build(td, l, only=set(order), prev=prevm); DV._CACHE.clear(); r2_ = DV.build(td, l, only=set(order), prev=prevm); twice[l] = json.dumps(r1, sort_keys=True) == json.dumps(r2_, sort_keys=True)
    ok("D9c seeded shuffle (seed %d): ids and memberships at every cut equal the unshuffled replay; two builds with prev equal (%s)" % (SEED, "; ".join("%s shuffle %s, twice %s" % (l, same[l], twice[l]) for l in RP)), bool(RP) and all(same.values()) and all(twice.values()))
    hbad = []; hinfo = []
    for l, (R, _, _, _) in RP.items():
        root = os.path.join(tmp, "step_" + l.replace(":", "_")); seen = {}; cuts_of = {}
        for c in R:
            lab = "%s@%d" % (l, c["m"]); H.append(c["res"], root, lab)
            for did in set(seen) | set(c["ids"]):
                e = H.load(root, did)
                if did in c["ids"] and (not e or e[-1].get("window") != lab): hbad.append((l, c["m"], did, "no entry for this cut"))
                if did in seen and e[:len(seen[did])] != seen[did]: hbad.append((l, c["m"], did, "earlier entries changed"))
                if did not in c["ids"] and e != seen[did]: hbad.append((l, c["m"], did, "entry written for an id not in this cut"))
                seen[did] = e
            for did in c["ids"]: cuts_of[did] = cuts_of.get(did, 0) + 1
        files = os.listdir(os.path.join(root, "history")) if os.path.isdir(os.path.join(root, "history")) else []
        if len(files) != len(cuts_of): hbad.append((l, "files", len(files), "ids %d" % len(cuts_of)))
        if any(len(seen[d]) != cuts_of[d] for d in cuts_of): hbad.append((l, "entries per id", "!= cuts the id appears in"))
        hinfo.append("%s %d files for %d ids over %d cuts, %d entries" % (l, len(files), len(cuts_of), len(R), sum(len(v) for v in seen.values())))
    ok("D9d history: one history file per development at every cut, entries append-only (%s)" % "; ".join(hinfo), bool(RP) and not hbad, str(hbad[:3]))
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("\n%-6s %-12s %-5s %-4s %-5s %-14s %-44s %s" % ("area", "id", "arts", "own", "days", "certainty", "title", "moved"))
for a, r in B.items():
    for d in r["developments"] + r["thin"]: print("%-6s %-12s %-5d %-4d %-5d %-14s %-44s %s" % (a, d["id"], d["articles"], d["owners"], d["days"], d["certainty_word"], ("THIN " if d["thin"] else "") + d["title"][:38], d["moved"]))
print("\ncheck-developments: %d of %d passed" % (sum(res), len(res))); sys.exit(0 if all(res) and res else 1)
