"""live_trace: one runner that reads real articles from the news queue as the reader extracts them and runs the whole local chain on each, in-process, CPU only.
Writes a per-step hash-chained trace under PAGE_DIR/trace/ (contract: live_trace_schema.json, T160). Observational: no pass bar, no accuracy, no labels read.
    START=<epoch> DURATION=3600 POLL=15 THREADS=4 PAGE_DIR=/workspace/demo/mockups/structure-live /workspace/models/embed-zs/.venv/bin/python live_trace.py
    live_trace.py --time N            time N queue rows through the stages, print p50/p90 and each stage's share (writes nothing)
    live_trace.py --replay-run id,id  print JSON of every stage's state, n and out for those queue ids (used by verify_trace.py --replay)
live-trace-v4 (T172): five chain stages after the v3 stages, each behind its own env flag LT_V4_<STAGE>=1 (names in live_trace_v4.py), default off; an off stage is recorded as "deferred" (why "slow clock", the slow clock computes claims_v1, identity_g4 and contradictions after the window, LT_SLOW_CLOCK=0 reverts) or not_attached (schema live_trace_schema_v4.json).
T158 plan 0b/1a/1b additions, all add-only (stage states, n and out unchanged): line.input.read = {depth, reason, words} from the queue (READ_SQL, outside ALLOW); scan_dates out.time_proxy and line.journal.novelty_proxy, both PROVISIONAL proxies; decider change/traits carry reason "pending slow clock" and provisional true
    --time reads the last N rows of the window; TIME_SINCE=<epoch> fixes the window, TIME_IDS=<json list of queue ids> times exactly those articles; it prints the v3 stages alone and each v4 stage's share"""
import os, sys
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"; os.execv(sys.executable, [sys.executable] + sys.argv)
THREADS = int(os.environ.get("THREADS", 4))
for _k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"): os.environ[_k] = str(THREADS)
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WORLD_GPU", "0")
import json, re, time, hashlib, sqlite3, collections, pathlib, statistics, glob
from urllib.parse import urlparse
HERE = pathlib.Path(__file__).resolve().parent; os.chdir(HERE); sys.path.insert(0, str(HERE))
import numpy as np
import journal as JR
import live_trace_v4 as V4M   # live-trace-v4: five chain stages behind env flags, default off (live_trace_schema_v4.json); trace() below is untouched
ALLOW = ["id", "url", "source", "title", "teaser", "body", "published", "ready_at"]
FORBIDDEN = ("category", "region", "country", "story")
QUEUE = "/workspace/data/newsreader/queue.sqlite"; MEDTOP = "/workspace/data/ontology_src/iptc/medtop.json"; SCHEMA_VERSION = "live-trace-v4"; SCHEMAS_OK = ("live-trace-v1", "live-trace-v2", "live-trace-v2-nojournal", "live-trace-v3", "live-trace-v4")
BUDGET = {"p50": 300, "p90": 600}; CAP_CHARS = 12000; MIN_CHARS = 40; SLOW_MS = 2000
def select_sql(where, limit=None):
    sql = "select " + ", ".join(ALLOW) + " from items where " + where + " order by ready_at, id" + (" limit %d" % limit if limit else "")
    cols = [c.strip() for c in sql[len("select "):sql.index(" from ")].split(",")]
    assert cols == ALLOW and not any(w in sql for w in FORBIDDEN), "SQL must name only the allowlisted columns"
    return sql
READ_SQL = "select depth, reason, words from items where id = ?"   # T158 plan 0b: how the queue read the article (full text, or teaser only and why). Kept apart from ALLOW so columns_allowlist (run.json, verify_trace, schema) is unchanged; none of the FORBIDDEN columns
assert not any(w in READ_SQL for w in FORBIDDEN)
def read_info(i):
    """{depth, reason, words} of one queue row, copied into line.input.read; None when the queue cannot be read. One short read-only connection per call (safe across threads, not part of any stage time)"""
    try:
        db = sqlite3.connect("file:%s?mode=ro" % QUEUE, uri=True)
        try: r = db.execute(READ_SQL, (i,)).fetchone()
        finally: db.close()
    except Exception: return None
    return {"depth": r[0], "reason": r[1], "words": r[2]} if r else None
def novelty_proxy(d): return {"label": "novelty_proxy", "marker": "PROVISIONAL", "value": d["kind"], "why": "story-key duplicate kind (first | copy | republished | generic_title | no_key), not a Novelty model (none exists, AUROC 0.51, L2791)"}   # T158 plan 0b
def time_proxy(spots, date):
    """PROVISIONAL time proxy (T158 plan 0b): days from the publish date to each resolved date of scan_dates (negative = earlier). No Time model exists (judge AUC 0.607, L2791); a spot that does not resolve to a date, or an article without a publish date, adds nothing"""
    import datetime as dt
    off = []
    if date:
        try:
            a0 = dt.date.fromisoformat(date)
            for sp in spots:
                if sp[2] == "date" and len(sp) > 3 and sp[3]:
                    try: off.append((dt.date.fromisoformat(str(sp[3])[:10]) - a0).days)
                    except ValueError: pass
        except ValueError: pass
    return {"label": "time_proxy", "marker": "PROVISIONAL", "offset_days": off[:20], "n": len(off), "of": "resolved date minus published date, in days"}
def collapse(s): return re.sub(r"\s+", " ", s or "").strip()
def build_text(row):
    """row: allowlisted tuple. Returns (text, title, body_used, has_body, body_chars, capped)."""
    title = collapse(row[3]); body = collapse(row[5]); teaser = collapse(row[4]); has_body = bool(body); used = body if has_body else teaser
    full = (title + ". " + used) if used else title; capped = len(full) > CAP_CHARS
    return full[:CAP_CHARS], title, used, has_body, len(body), capped
# ---------------------------------------------------------------- the chain (copies the bench loaders in simulation/server.py lines 10-40)
class Chain:
    def __init__(self, threads=THREADS):
        import analyze2 as A2, facts_lib as FL, span_rules as SR, extract as EX, scan_gate as SG, decider as D, pickle, spacy, torch
        torch.set_num_threads(threads); self.A2, self.FL, self.SR, self.EX, self.SG, self.D = A2, FL, SR, EX, SG, D
        from expert1_runtime import ExpertS
        self.E = ExpertS("runs/expert1/expert1_v6b_student.pkl"); self.FT = json.load(open("runs/pulse/field_table.json"))
        self.X = A2.Analyzer(self.E.S, self.FT, threads=threads); self.R = self.X.reader; self.S = self.E.S
        from sentence_transformers import SentenceTransformer
        self.PLACE = pickle.load(open("runs/pulse/t200/place_student.pkl", "rb")); self.PLACE_ENC = SentenceTransformer("intfloat/e5-small-v2", device="cpu"); self.PLACE_ENC.max_seq_length = 128
        t = json.load(open("runs/pulse/t230/capability_tiers.json")); self.CAP_REC = {tuple(x.split(" ", 1)) for x in t["recurring_pairs"] if " " in x and x not in ("injure other", "speak condition", "update inbox")}
        self.CAP_CAND = {(r["predicate"], r["object"]) for r in map(json.loads, open("runs/pulse/t222/capability_candidates.jsonl"))}
        self.TOPIC2DOM = json.load(open("specs/topic_to_iptc_v1.json"))["map"]
        EX.init(); self.cinfo = {}
        for l in open("/workspace/data/geo/countryInfo.txt"):
            if l.startswith("#") or not l.strip(): continue
            f = l.split("\t"); self.cinfo[f[0]] = f[8]
        from structure_pack import Pack
        self.pack = Pack(FL.nlp); self.bge = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); self.bge.max_seq_length = 256   # owned by the landing; the pack stage no longer embeds, so nothing switches the length per call
        self.NA = {"function_sentence": ("G3a", "source runs/pulse/function_head_v1/function_head.pkl (saved, sha a0ad99d1; AUC 0.791 on CheckThat gold, L2795, bar 0.85 not met = PROVISIONAL): the sentence-level Function head exists but the chain does not call it (669 ms per article, over the budget); it runs on the slow clock via raw_core.attach_heads (RAW_HEADS=1)"),
                   "novelty": ("G5", "source runs/pulse/t151/head_table.json and t169_novelty_pilot.py: no Novelty model exists (AUROC 0.51); the journal duplicate kind is shown as the PROVISIONAL novelty_proxy (line.journal.novelty_proxy)"),
                   "time": ("G3a", "source t162_time_judge.py to t165_time_head.py: no Time model exists (no trustworthy judge, AUC 0.607); the offset in days of each resolved date from the publish date is shown as the PROVISIONAL time_proxy (scan_dates out.time_proxy)"),
                   "factuality_story": ("G3a", "source runs/pulse/factuality_v1/factuality_head.pkl (saved, sha b0f857be; balanced accuracy 0.56 to 0.63 against the 0.80 bar, L2795 = PROVISIONAL, from t178_factuality_student.py): the head exists but the chain does not call it (669 ms per article); it runs on the slow clock via raw_core.attach_heads (RAW_HEADS=1)")}
        try:   # step 2 (live-trace-v2): the topic landing is the trace's topic head; no landing means no run unless the operator opts into a degraded one
            from pack_view import Landing; self.landing = Landing(self.pack, alias=False, emb=self.bge); self.iptc_release = json.load(open(MEDTOP)).get("dateReleased")
            self.landing_version = "landing-v0; bge-small-en-v1.5; medtop %s; cards %s; alias=off; seq256; text[:2000]" % (self.iptc_release, self.landing.cards_sha[:16])
            import landing_calibrate as LC; self.LC = LC; self.calib, self.calib_why = LC.load(self.landing.cards_sha)   # step 4: no calibration file, or one fitted on other cards, means v0 (EVIDENCE_ONLY, p null) and run.json says why
            if self.calib: self.share = LC.share_array(self.landing, self.calib); self.landing_version = self.landing_version.replace("landing-v0", "landing-v1", 1) + "; calib " + self.calib["sha16"]
        except Exception as e:
            why = "%s: %s" % (type(e).__name__, str(e)[:200])
            if os.environ.get("ALLOW_NO_LANDING") != "1": raise RuntimeError("topic_landing could not build: " + why)
            self.landing = None; self.landing_version = None; self.rerank = None; self.rerank_why = "no landing"; self.iptc_release = None; self.calib = None; self.calib_why = "no landing"; self.NA["topic_landing"] = ("G3a", "source pack_view.Landing: medtop.json unreadable: " + why)
        self.rerank = getattr(self, "rerank", None); self.rerank_why = getattr(self, "rerank_why", None)
        if self.landing is not None:   # live-trace-v3: the round-1 topic re-ranker answers the level-1 code; a card list or cards_sha mismatch fails fast unless ALLOW_NO_RERANK=1 (landing-only run, run.json degraded)
            try:
                import reranker as RR; self.rerank = RR.Reranker(self.landing, share=self.share if self.calib else None)
            except Exception as e:
                self.rerank_why = "%s: %s" % (type(e).__name__, str(e)[:200])
                if os.environ.get("ALLOW_NO_RERANK") != "1": raise RuntimeError("topic re-ranker could not build: " + self.rerank_why)
            if self.rerank and self.rerank.cal is None:
                self.rerank_why = self.rerank.cal_why
                if os.environ.get("ALLOW_NO_RERANK") != "1": raise RuntimeError("topic re-ranker has no matching calibration: " + str(self.rerank_why))
                self.rerank = None
        import mnds_codes; self.table_version = mnds_codes.table()["version"]
        self.versions = {"windows": "analyze2.Reader.read_detail + expert1_v6b_student.pkl", "scan_dates": "scan_gate.scan", "facts": FL.FACT_VERSION, "independent_counter": FL.FACT_VERSION + " (ff[1])", "tags_bundles": "%s + %s" % (A2.CHG_VER, A2.FAC_VER), "span_rules": "span-rules-v0 + FL.quarantine",
                         "place_linker": "structure_pack.link_place (geonames+alias-v0, case fold, WordNet part of; L2710)", "area_function": "expert1_v6b_student.pkl topic+story heads", "domain_rollup": "specs/topic_to_iptc_v1.json", "condition": "expert1_runtime.ExpertS.read", "place_student": "runs/pulse/t200/place_student.pkl + e5-small-v2",
                         "capability_list": "t230 capability_tiers + t222 candidates", "structure_pack": "structure_pack.Pack (WordNet placement on the IPTC tree; the topic guess moved to topic_landing)", "topic_landing": (self.landing_version + ("; " + self.rerank.version if self.rerank else "")) if self.landing_version else None, "decider": "decider.py (Lean-checked)"}
        self.v4 = V4M.V4(self, budget=BUDGET["p90"], slow_ms=SLOW_MS); self.v4.warm()   # live-trace-v4: flags from LT_V4_*; with every flag off nothing is loaded
    def region(self, cc):
        MENA = set("DZ BH DJ EG IR IQ IL JO KW LB LY MA OM PS QA SA SY TN AE YE AF PK EH".split()); SOUTH = set("IN BD LK NP BT MV".split()); CENTRAL = set("KZ UZ TM KG TJ AM AZ GE TR RU".split()); c = self.cinfo.get(cc)
        if c is None: return None
        if cc in MENA: return "Middle East, North Africa, Afghanistan & Pakistan"
        if cc in SOUTH: return "South Asia"
        if cc in CENTRAL or c == "EU": return "Europe & Central Asia"
        if cc in ("US", "CA"): return "North America"
        if c in ("SA", "NA"): return "Latin America & Caribbean"
        if c == "AF": return "Sub-Saharan Africa"
        if c in ("AS", "OC"): return "East Asia & Pacific"
        return None
    # each stage returns dict(state, out, n, why, full)
    def trace(self, row):
        """-> (article_line without seq/read_at/lag/ chain fields, text, stages_full). row = allowlisted tuple."""
        text, title, body, has_body, body_chars, capped = build_text(row); D, FL, SR, EX, A2 = self.D, self.FL, self.SR, self.EX, self.A2
        pub = (row[6] or "")[:10]; date = pub if re.match(r"^\d{4}-\d{2}-\d{2}$", pub) else None; ds = (date + "T00:00:00Z") if date else None
        dom = (urlparse(row[1] or "").netloc.lower() or "").replace("www.", "", 1)
        line = {"id": row[0], "title": title, "url": row[1], "source": row[2], "published": row[6], "ready_at": row[7], "input": {"chars": len(text), "has_body": has_body, "body_chars": body_chars, "text_sha1": hashlib.sha1(text.encode()).hexdigest(), "capped": capped, "pct_read_per_model": {}, "read": read_info(row[0])}}
        if len(text) < MIN_CHARS or not (title or body): line.update(state="skipped", skip_reason="empty" if not text else "too short (under %d characters)" % MIN_CHARS, stages=[], decider={}, gaps=[], total_ms=0.0, over_budget=False); return line, text, {}
        ctx = {}; stages = []; full = {}
        def run(name, gate, kind, prov, fn):
            t0 = time.perf_counter()
            try: r = fn()
            except Exception as e: r = {"state": "error", "out": None, "n": None, "why": "%s: %s" % (type(e).__name__, str(e)[:200]), "full": None}
            ms = round((time.perf_counter() - t0) * 1000, 2); out = r.get("out")
            if out is not None and len(json.dumps(out, ensure_ascii=False)) > (1000 if name == "topic_landing" else 700): out = {"truncated": True, "head": json.dumps(out, ensure_ascii=False)[:560 if name != "topic_landing" else 800]}
            stages.append({"name": name, "gate": gate, "kind": kind, "version": self.versions.get(name), "state": r["state"], "out": out, "n": r.get("n"), "ms": ms, "provenance": prov, "why": r.get("why")}); full[name] = r.get("full", out)
            if ms > SLOW_MS: stages[-1]["slow"] = True
        def need(*k):
            for x in k:
                if x not in ctx: raise RuntimeError("upstream stage missing: " + x)
        def windows():
            det = self.R.read_detail(title, body); ctx["det"] = det; nb = max(1, len(body)); rd = sum(b - a for a, b in det["offsets"]); pct = min(100, round(100 * rd / nb)) if body else 100; line["input"]["pct_read_per_model"]["v6b_windows"] = pct
            ctx["nw"] = det["nw"]; o = {"windows": det["nw"], "cap": self.R.cap, "pct_body_read": pct}
            return {"state": "ran", "out": o, "n": det["nw"], "why": None, "full": {**o, "offsets_text": det["offsets_text"]}}
        run("windows", "G3a", "model", "Observed", windows)
        def scan():
            spots, sents = self.SG.scan(text, ds or "2026-01-01T00:00:00Z"); cnt = collections.Counter(s[2] for s in spots); dr = sum(1 for s in spots if s[2] == "date" and len(s) > 3 and s[3] is not None)
            o = {"spots": dict(sorted(cnt.items())), "dates": cnt.get("date", 0), "dates_resolved": dr, "anchor": date or "default 2026-01-01 (no published date)"}
            o["time_proxy"] = time_proxy(spots, date)
            return {"state": "ran" if spots else "empty", "out": o, "n": len(spots), "why": None if spots else "no spot in the text", "full": {**o, "dates": [[text[s[0]:s[1]], s[3] if len(s) > 3 else None] for s in spots if s[2] == "date"][:40]}}
        run("scan_dates", "G1", "tool", "Observed", scan)
        def facts():
            ff = FL.facts_for(text, ds); ctx["ff"] = ff; kept, held = FL.quarantine(ff[0], text); ctx["facts"] = kept; ctx["held_f"] = held; k = collections.Counter(f["kind"] for f in kept); st = collections.Counter(f["status"] for f in kept)
            o = {"kinds": dict(sorted(k.items())), "stated": st.get("stated", 0), "unbound": st.get("unbound", 0), "invalid": st.get("invalid", 0), "stated_amount": sum(1 for f in kept if f["kind"] == "amount" and f["status"] == "stated"), "stated_date": sum(1 for f in kept if f["kind"] == "date" and f["status"] == "stated"), "quarantined": len(held)}
            return {"state": "ran" if kept else "empty", "out": o, "n": len(kept), "why": None if kept else "no fact found", "full": {**o, "held": [{k_: x.get(k_) for k_ in ("kind", "s", "e", "why")} for x in held][:30], "items": [{k_: f[k_] for k_ in ("kind", "s", "e", "text", "status")} for f in kept][:120]}}
        run("facts", "G2", "tool", "Observed", facts)
        def indep():
            need("ff"); ind = ctx["ff"][1]; o = {"amount": ind["amount"], "date": ind["date"], "name": ind["name"]}; n = ind["amount"] + ind["date"]
            return {"state": "ran" if (n or ind["name"]) else "empty", "out": o, "n": n, "why": None if (n or ind["name"]) else "no independent run counted", "full": {**o, "amount_runs": ind["amount_runs"][:60], "date_runs": ind["date_runs"][:60]}}
        run("independent_counter", "G2", "tool", "Observed", indep)
        def bundles():
            need("ff", "facts"); b, info = A2.build_bundles(ctx["ff"][2], text, ctx["facts"]); ctx["bundles"] = b; c = collections.Counter(x["condition"] for x in b)
            o = {"bundles": len(b), "with_size": sum(1 for x in b if x["size"]), "hits": info["hits"], "negated_skipped": info["negated_skipped"], "held": len(info["held"]), "by_condition": dict(sorted(c.items())), "factuality": dict(sorted(collections.Counter(x["factuality"] for x in b).items()))}
            return {"state": "ran" if b else "empty", "out": o, "n": len(b), "why": None if b else "no change-lexicon hit in the text", "full": {**o, "bundles": b[:40]}}
        run("tags_bundles", "G2", "tool", "Inferred", bundles)
        def spans():
            sp = SR.spans(text, ds); kept, held = FL.quarantine(sp, text); ctx["held_s"] = held; c = collections.Counter(x["kind"] for x in kept); o = {"kinds": dict(sorted(c.items())), "quarantined": len(held)}
            return {"state": "ran" if kept else "empty", "out": o, "n": len(kept), "why": None if kept else "no span rule fired", "full": {**o, "held": [{k_: x.get(k_) for k_ in ("kind", "s", "e", "why")} for x in held][:30]}}
        run("span_rules", "G1", "tool", "Observed", spans)
        def place_linker():
            with EX.nlp.select_pipes(enable=["tok2vec", "ner"]): d = EX.nlp(text)
            ents = [(x.text.strip(), x.start_char, x.end_char) for x in d.ents if x.label_ in ("GPE", "LOC", "FAC")]
            strip = lambda p: re.sub(r"^the ", "", p, flags=re.I); explicit = {EX.ALIAS[strip(p[0])] if strip(p[0]) in EX.ALIAS else EX.ctry.get(strip(p[0])) for p in ents} - {None}
            items = []
            for nm, a, b in ents: items.append({"text": nm, **self.pack.link_place(nm, dom, explicit, EX), "span": [a, b]})   # GeoNames + measured fixes (L2710)
            for it in items: it["src"] = "spacy"
            for lk in self.pack.lookup_places(text, EX):   # L2779: whole-word country / alias / demonym lookup beside spaCy; union, deduped by span (a lookup hit overlapping a spaCy candidate is the same mention)
                if not any(lk["span"][0] < b and a < lk["span"][1] for _, a, b in ents): items.append({**lk, "src": "lookup"})
            items.sort(key=lambda i: i["span"][0])
            cc = collections.Counter(i["country"] for i in items if i["country"]); top = sorted(cc.items(), key=lambda kv: (-kv[1], kv[0]))[:3]; reg = self.region(top[0][0]) if top else None; ctx["linker_region"] = reg; ctx["places"] = [c for c, _ in top]   # ISO-2 codes for the journal
            ctry_ = None
            if top:
                c0 = top[0][0]; hit = [i for i in items if i["country"] == c0]; ctry_ = {"iso2": c0, "mentions": len(hit), "spans": [i["span"] for i in hit][:20], "via": dict(collections.Counter(i.get("how") or "spacy" for i in hit))}   # linker answer; NOT a decider field
            o = {"places": len(items), "linked": sum(cc.values()), "top_countries": [list(t) for t in top], "region": reg, "country": ctry_, "from_lookup": sum(1 for i in items if i["src"] == "lookup")}
            return {"state": "ran" if items else "empty", "out": o, "n": len(items), "why": None if items else "no place name (GPE, LOC, FAC) found", "full": {**o, "items": items[:60]}}
        run("place_linker", "G1", "tool", "Resolved", place_linker)
        def area():
            need("det"); det = ctx["det"]; S = self.S; pt, ps = det["pt"], det["ps"]; tn, sn = S["topic_cl"], S["story_cl"]; ctx["pt"], ctx["ps"] = pt, ps
            ot = [[str(tn[int(i)]), round(float(pt[i]), 3)] for i in np.argsort(-pt)[:3]]; os_ = [[str(sn[int(i)]), round(float(ps[i]), 3)] for i in np.argsort(-ps)[:3]]; o = {"topic": ot, "story_type": os_}
            return {"state": "ran", "out": o, "n": 2, "why": None, "full": o}
        run("area_function", "G3a", "model", "Inferred", area)
        def rollup():
            need("pt"); dom_ = collections.defaultdict(float)
            for n, p in zip(self.S["topic_cl"], ctx["pt"]): dom_[(self.TOPIC2DOM.get(n) or ["unmapped"])[0]] += float(p)
            top = sorted(dom_.items(), key=lambda kv: (-kv[1], kv[0]))[:3]; o = {"top": [[k, round(v, 3)] for k, v in top]}; ctx["rollup_top"] = top[0][0] if top else None
            return {"state": "ran", "out": o, "n": 1, "why": None, "full": o}
        run("domain_rollup", "G3a", "model", "Inferred", rollup)
        def landing():
            need("ff"); cal = self.calib; kp = {}; r = self.landing.land(ctx["ff"][2], text, share=self.share if cal else None, gate=bool(cal and cal.get("gate")), keep=kp); art = r["article"]; b = art[0]; l1 = b["path_codes"][0]; ctx["l1_code"] = l1; ctx["ids_topic"] = {"best": b["qcode"], "l1": l1, "l2": b["path_codes"][1] if len(b["path_codes"]) > 1 else None, "top3": [a["qcode"] for a in art[:3]]}; vote = [[c, n] for c, n in r["vote_by_code"]]; rt = ctx.get("rollup_top")
            from pack_view import l1_code as name_code
            o = {"best": {"qcode": b["qcode"], "layer": b["layer"], "score": b["score"], "margin": round(r["rank_scores"][0] - r["rank_scores"][1], 3) if cal else round(b["score"] - art[1]["score"], 3)}, "top3": [[a["qcode"], a["score"]] for a in art[:3]], "l1_code": l1, "l1_agree3": sum(1 for a in art[:3] if a["path_codes"][0] == l1),
                 "vote": vote, "voted": r["voted"], "n_sent": r["n_sentences"], "agrees_rollup": (l1 == name_code(rt)) if "rollup_top" in ctx else None, "decision": "EVIDENCE_ONLY"}   # code join; the roll-up is the legacy 49-to-17 map, reference only
            why = None if r["n_sentences"] else "no sentence of 40 characters"; ff_ = None
            if cal:   # landing-v1: hub-damped ranking, calibrated p, and the line where running accuracy held 0.80 on T28 (specs/landing_calibration_v1.json)
                ff_ = self.LC.features(r, len(text[:2000]), cal["hubs_set"], bool(cal.get("gate"))); pm = self.LC.permille(self.LC.prob(ff_, cal)); o["p"] = pm / 1000; o["damped"] = r["damped"]; o["decision"] = self.LC.decide_pm(pm, cal); ctx["topic_pm"] = pm; ctx["topic_line"] = cal["line_permille"]; ctx["topic_src"] = "landing-v1"   # p is stored as floor(1000 p) / 1000: the page's p, the decision and the decider all use this one integer
                if o["decision"] == "ABSTAIN": why = "p %.3f below the line %.3f" % (pm / 1000, cal["line_permille"] / 1000)
            rr = None
            if self.rerank is not None:   # live-trace-v3: the re-ranker's level-1 answer replaces the landing's; the landing's own best, top3, vote, p and decision stay as evidence
                rr = self.rerank.apply(kp["sc"], l1); o["landing_l1_code"] = l1; o["landing_p"] = o.get("p"); o["landing_decision"] = o["decision"]; rl1 = rr["l1_code"]
                o["l1_code"] = rl1; o["agrees_rollup"] = (rl1 == name_code(rt)) if "rollup_top" in ctx else None; o["p"] = rr["p"]; o["decision"] = rr["decision"]; ctx["l1_code"] = rl1; ctx["topic_pm"] = rr["pm"]; ctx["topic_line"] = self.rerank.cal["line_permille"]; ctx["topic_src"] = "rerank-r1"
                ctx["ids_topic"] = {"best": rr["node"], "l1": rl1, "l2": rr["node_l2"], "top3": [a["qcode"] for a in art[:3]]}   # the node is the best card under the answered level-1 code, so l2 sits under l1
                o["rerank"] = {"l1_code": rl1, "p": rr["p"], "top2": rr["top2"], "version": "rerank-r1:" + self.rerank.model_sha16, "node": rr["node"]}; why = None
                if o["decision"] == "ABSTAIN": why = "re-ranker p %.3f below the line %.3f" % (rr["p"], ctx["topic_line"] / 1000)
            return {"state": "abstain" if o["decision"] == "ABSTAIN" else "ran", "out": o, "n": 1 + r["n_sentences"], "why": why, "full": {**o, **({"rerank_features": rr["features"], "rerank_calibration": {"sha16": self.rerank.cal["sha16"], "line_permille": self.rerank.cal["line_permille"], "model_sha16": self.rerank.model_sha16}} if rr else {}), "article": art, "sentences": r["sentences"], **({"features": ff_, "calibration": {"sha16": cal["sha16"], "line_permille": cal["line_permille"], "as_of": cal.get("as_of"), "stale": not cal.get("as_of") or cal["as_of"]["label_version"] != "%s/%s" % (self.iptc_release, self.landing.cards_sha[:8])}} if cal else {})}}
        if self.landing is not None: run("topic_landing", "G3a", "model", "Inferred", landing)
        def cond():
            p = self.E.read(title + ". " + body[:1200]); line["input"]["pct_read_per_model"]["condition"] = min(100, round(100 * min(1200, len(body)) / max(1, len(body)))) if body else 100
            cp = p.get("condition_present", {}); c = p.get("condition"); which = c.get("answer") if c and c.get("status") == "answered" else None
            o = {"present": cp.get("answer"), "present_conf": round(float(cp.get("confidence", 0)), 3), "status": cp.get("status"), "which": which, "direction": c.get("direction") if c else None, "size": c.get("size") if c else None, "path": p.get("path")}
            if cp.get("reason"): o["reason"] = cp["reason"]
            return {"state": "ran" if cp.get("status") == "answered" else "abstain", "out": o, "n": 1 if which else 0, "why": None if cp.get("status") == "answered" else (cp.get("reason") or "below the condition confidence cut"), "full": o}
        run("condition", "G3a", "model", "Inferred", cond)
        def place_student():
            v = self.PLACE_ENC.encode(["query: " + (title + ". " + body)[:1500]], normalize_embeddings=True, show_progress_bar=False); pp = self.PLACE["model"].predict_proba(v)[0]; cl = self.PLACE["classes"]
            line["input"]["pct_read_per_model"]["place_student"] = min(100, round(100 * 1500 / max(1, len(title + ". " + body)))); top = [[str(cl[int(i)]), round(float(pp[i]), 3)] for i in np.argsort(-pp)[:3]]; ok = float(pp.max()) >= float(self.PLACE["line"])
            o = {"top1": top[0][0], "top": top, "line": round(float(self.PLACE["line"]), 3), "answered": ok}
            return {"state": "ran" if ok else "abstain", "out": o, "n": 1 if ok else 0, "why": None if ok else "top probability below the place answer line", "full": o}
        run("place_student", "G3a", "model", "Inferred", place_student)
        def cap():
            need("facts"); tr = [(f["value"][1], f["value"][2]) for f in ctx["facts"] if f["kind"] == "triple" and isinstance(f.get("value"), list) and len(f["value"]) == 3 and f["value"][1] and f["value"][2]]
            rec = sorted({"%s %s" % p for p in tr if p in self.CAP_REC}); cand = sorted({"%s %s" % p for p in tr if p in self.CAP_CAND and p not in self.CAP_REC}); o = {"triples": len(tr), "recurring": rec[:6], "candidate": cand[:6], "n_recurring": len(rec), "n_candidate": len(cand)}
            return {"state": "ran" if (rec or cand) else "empty", "out": o, "n": len(rec) + len(cand), "why": None if (rec or cand) else "no triple matches the verb-object list", "full": {**o, "recurring": rec, "candidate": cand}}
        run("capability_list", "G4", "tool", "Candidate", cap)
        def pack():
            need("ff"); doc = ctx["ff"][2]; top = ctx.get("l1_code")   # the landing's L1 code (a code join); None when the landing did not run
            terms = self.pack.terms(doc); hops = collections.Counter(); placed = 0; intop = 0; un = []
            for w in terms:
                c = self.pack.place(w)
                if c:
                    placed += 1; hops[c[0][0]] += 1; intop += any(self.pack.chain(x[1])[0] == top for x in c) if top else 0
                else: un.append(w)
            sp_out = []; seen_t = {}
            def info(w):
                if w not in seen_t:
                    c = self.pack.place(w); f = [x for x in c if self.pack.chain(x[1])[0] == top]; x = (f or c or [None])[0]
                    seen_t[w] = None if x is None else {"hop": x[0], "via": x[2], "path": self.pack.path(x[1]), "in_topic": bool(f) if top else None}
                return seen_t[w]
            tset = set(terms)
            for t in doc:
                if t.pos_ == "NOUN" and t.is_alpha and len(t.lemma_) > 2 and t.lemma_.lower() in tset and info(t.lemma_.lower()):
                    sp_out.append({"start": t.idx, "end": t.idx + len(t.text), "word": t.lemma_.lower(), **info(t.lemma_.lower())})
            for chk_ in doc.noun_chunks:
                w = [t for t in chk_ if t.pos_ in ("NOUN", "PROPN", "ADJ") and t.is_alpha]
                if 2 <= len(w) <= 3:
                    k = " ".join(t.lemma_.lower() for t in w)
                    if k in tset and info(k): sp_out.append({"start": w[0].idx, "end": w[-1].idx + len(w[-1].text), "word": k, **info(k)})
            sp_out.sort(key=lambda d: (d["start"], d["end"], d["word"]))
            o = {"l1_code_used": top, "n_terms": len(terms), "n_placed": placed, "in_topic": intop if top else None, "hops": dict(sorted(hops.items())), "unplaced_share": round(1 - placed / len(terms), 3) if terms else None}
            return {"state": "ran" if terms else "empty", "out": o, "n": len(terms), "why": None if terms else "no noun term", "full": {**o, "unplaced": un[:80], "placed_spans": sp_out[:600]}}
        run("structure_pack", "G5", "pack", "Inferred", pack)
        def decider():
            need("det"); det = ctx["det"]; pt, ps = ctx["pt"], ctx["ps"]; S = self.S; o2 = np.argsort(-pt)[:2]; facts = ctx["facts"]; am = [f for f in facts if f["kind"] == "amount" and f["status"] == "stated"]; P = A2.Proposal
            props = {"story_type": P(D.Source.TRAINED_HEAD, float(ps.max()), True, S["story_cl"][int(ps.argmax())], "reader"), "topic": P(D.Source.TRAINED_HEAD, float(pt[o2].sum()), True, " / ".join(S["topic_cl"][k] for k in o2), "reader"),
                     "change": P(D.Source.STATED_FACT, 0.0, False, "not run", "pending slow clock"), "size": P(D.Source.STATED_FACT, 0.0, bool(am), "; ".join(f["text"] + " (" + (f["noun"] or f["verb"] or "") + ")" for f in am[:4]) or "no stated amount", "%d amounts stated" % len(am)),
                     "traits": P(D.Source.STATED_FACT, 0.0, False, "not run", "pending slow clock")}
            res = {}; thr = {}
            if "topic_pm" in ctx and "topic_node" in self.FT: props["topic_node"] = P(D.Source.TRAINED_HEAD, ctx["topic_pm"] / 1000, True, ctx["l1_code"], ctx["topic_src"]); thr["topic_node"] = ctx["topic_line"]   # step 4: the sixth field, threshold = the calibration's line, not Analyzer.thr
            for k, p in props.items():
                mk = self.FT[k]["marker"]; oc = D.decide(mk, p.source, p.validated, ctx["topic_pm"] if k == "topic_node" else int(1000 * p.confidence), thr.get(k, self.X.thr), True); hv = D.harvest(oc, p.source)
                res[k] = {"outcome": oc.name, "answer_or_proposed": p.answer, "marker": D.Marker(mk).name if isinstance(mk, int) else str(mk), "harvest": hv.name == "TRAINING_LABEL" or hv.name == "LABEL_QUEUE" and False}
                res[k]["harvest"] = hv.name
                if k in ("change", "traits"): res[k]["reason"] = p.how; res[k]["provisional"] = True   # T158 plan 1b: the outcome code is the decider's and unchanged; the reason says where the answer comes from (claims -> direction on the slow clock)
            ctx["decider"] = res; o = {k: v["outcome"] for k, v in res.items()}
            return {"state": "ran", "out": o, "n": len(res), "why": None, "full": res}
        run("decider", "G3b", "tool", "Inferred", decider)
        for nm, (gate, why) in self.NA.items():
            stages.append({"name": nm, "gate": gate, "kind": "model", "version": None, "state": "not_attached", "out": None, "n": None, "ms": 0, "provenance": None, "why": why}); full[nm] = None
        names = list(dict.fromkeys(f["text"] for f in ctx.get("facts", []) if f["kind"] == "name" and f["status"] == "stated"))[:20]   # strings until step 7 gives IDs
        line["journal"] = {"label_version": {"iptc_release": self.iptc_release, "cards": self.landing.cards_sha[:16] if self.landing else None, "table": self.table_version}, "ids": {"topic": ctx.get("ids_topic"), "places": ctx.get("places", []), "names": names, "names_id_space": "string"},
                           "story_key": JR.story_keys(title, body), "dup": None, "publishers": None, "permission": "public-news"}   # dup and publishers need the run's key index: main() fills them
        tot = round(sum(s["ms"] for s in stages), 2); line.update(state="traced", skip_reason=None, stages=stages, decider=ctx.get("decider") or "not_attached", total_ms=tot, over_budget=tot > BUDGET["p90"])
        return line, text, full
# ---------------------------------------------------------------- run, time, replay
def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
def hf_file(repo, names=("model.safetensors", "pytorch_model.bin")):
    try:
        from huggingface_hub import try_to_load_from_cache
        for n in names:
            p = try_to_load_from_cache(repo, n)
            if isinstance(p, str): return p
    except Exception: pass
    return None
def hash_sets(ch):
    code = [__file__, "live_gaps.py", "structure_pack.py", "specs/demonyms_wordnet_v0.json", "pack_view.py", "landing_calibrate.py", "specs/landing_calibration_v1.json", "reranker.py", "specs/rerank_calibration_v1.json", "journal.py", "mnds_codes.py", "specs/mnds_name_to_code_v1.json", "analyze2.py", "facts_lib.py", "scan_gate.py", "span_rules.py", "extract.py", "decider.py", "expert1_runtime.py", "live_trace_schema.json", "/workspace/data/ontology_src/iptc/medtop.json", "/workspace/data/ontology_src/wordnet/wordnet/data.noun", "/workspace/data/ontology_src/wordnet/wordnet/index.noun"] + list(V4M.CODE_FILES)   # live-trace-v4 modules and schema, listed in live_trace_v4.py
    mod = ["runs/expert1/expert1_v6b_student.pkl", "runs/pulse/field_table.json", "runs/pulse/topic_loop/r1/primary_reranker.pkl", "runs/pulse/t200/place_student.pkl", "runs/pulse/t230/capability_tiers.json", "runs/pulse/t222/capability_candidates.jsonl", "specs/topic_to_iptc_v1.json", ch.S.get("onnx_path"), ch.S.get("tok_path")]
    mod += [hf_file("intfloat/e5-small-v2"), hf_file("BAAI/bge-small-en-v1.5")]
    fs = {os.path.relpath(os.path.abspath(p), str(HERE)) if not str(p).startswith("/workspace/data") else p: sha_file(p) for p in code if os.path.exists(p)}
    ms = {str(p): sha_file(p) for p in mod if p and os.path.exists(p)}
    return fs, ms
def atomic(path, obj):
    tmp = path + ".tmp"; open(tmp, "w").write(json.dumps(obj, ensure_ascii=False)); os.replace(tmp, path)
def main():
    import live_gaps as G, mnds_codes
    kidx = JR.new_index(); jdir = os.environ.get("JOURNAL_DIR") or (V4M.default_journal_dir() if V4M.read_flags()["journal"] else None); JD = JR.Durable(os.path.join(jdir, "journal.jsonl")) if jdir else None; lab = lambda q: ch.pack.lab(q) if q in ch.pack.node else q
    START = float(os.environ.get("START", time.time())); DUR = min(3600.0, float(os.environ.get("DURATION", 3600))); POLL = float(os.environ.get("POLL", 15))
    TR = os.path.join(os.environ.get("PAGE_DIR", "/workspace/demo/mockups/structure-live"), "trace"); os.makedirs(TR + "/a", exist_ok=True)
    if os.path.exists(TR + "/chain.jsonl") and os.path.getsize(TR + "/chain.jsonl"): sys.exit("refusing: %s/chain.jsonl already has lines (a chain never restarts in place; use a new PAGE_DIR)" % TR)
    t_load = time.time()
    try: ch = Chain()
    except Exception as e:   # start-up failure (missing model file, no landing): leave a run.json that says so, no chain line, exit 1
        why = "%s: %s" % (type(e).__name__, str(e)[:300]); atomic(TR + "/run.json", {"run_id": None, "version": SCHEMA_VERSION, "state": "error", "why": why, "start_epoch": START, "now_epoch": time.time(), "counts": {}, "stages": {}, "decider": {}, "gaps": []}); print("run refused: " + why, file=sys.stderr); sys.exit(1)
    fsha, msha = hash_sets(ch); code_hash = hashlib.sha256("".join(fsha[k] for k in sorted(fsha)).encode()).hexdigest()[:16]
    run_id = "run-%d-%s" % (int(time.time()), code_hash[:6]); t_start = time.time(); ends = t_start + DUR
    db = sqlite3.connect("file:%s?mode=ro" % QUEUE, uri=True); sql = select_sql("ready_at is not null and (ready_at > ? or (ready_at = ? and id > ?))", 25)
    chk = ["sqlite3 'file:%s?mode=ro' \"select count(*) from items where ready_at >= %s\"   # rows_ready_since_start = traced + skipped + backlog_ready" % (QUEUE, START), "sqlite3 'file:%s?mode=ro' \"select count(*) from items where found_at >= %s and ready_at is null\"   # never_ready_since_start" % (QUEUE, START)]
    st = {"state": "running", "cursor": (START, ""), "seq": 0, "prev": run_id, "lines": [], "tail": [], "lag": [], "slow": []}; counts = {"traced": 0, "skipped": 0, "backlog_ready": 0, "rows_ready_since_start": 0, "never_ready_since_start": 0, "rows_found_since_start": 0, "ready_found_before_start": 0}
    cf = open(TR + "/chain.jsonl", "a"); last_w = 0.0; last_h = time.time(); agg = {}
    def counts_refresh():
        c, i = st["cursor"]
        counts["backlog_ready"] = db.execute("select count(*) from items where ready_at is not null and (ready_at > ? or (ready_at = ? and id > ?))", (c, c, i)).fetchone()[0]
        counts["rows_ready_since_start"] = db.execute("select count(*) from items where ready_at >= ?", (START,)).fetchone()[0]
        counts["never_ready_since_start"] = db.execute("select count(*) from items where found_at >= ? and ready_at is null", (START,)).fetchone()[0]
        counts["rows_found_since_start"] = db.execute("select count(*) from items where found_at >= ?", (START,)).fetchone()[0]
        counts["ready_found_before_start"] = db.execute("select count(*) from items where found_at < ? and ready_at >= ?", (START, START)).fetchone()[0]
    def write_run(state=None):
        nonlocal agg, last_w
        if state: st["state"] = state
        agg = G.aggregate(st["lines"], lab); counts_refresh()
        lag = sorted(st["lag"]); lv = {"iptc_release": ch.iptc_release, "cards": ch.landing.cards_sha[:16] if ch.landing else None, "table": ch.table_version, "calibration": ch.calib["sha16"] if ch.calib else None, "rerank_model": ch.rerank.model_sha16 if ch.rerank else None, "rerank_calibration": ch.rerank.cal["sha16"] if ch.rerank else None}
        jr = {"journal": {**agg["journal"], "as_of": {"run_id": run_id, "seq": st["seq"] - 1, "label_version": lv}}} if agg["journal"] else {}   # counts per run: the day table of step 5 sums runs by key
        atomic(TR + "/run.json", {"run_id": run_id, "version": SCHEMA_VERSION, "journal_version": "journal-v0", **jr, "label_version": lv, "degraded": ["no landing"] if ch.landing is None else (([] if ch.calib else ["landing-v0: " + str(ch.calib_why)]) + ([] if ch.rerank else ["no re-ranker: " + str(ch.rerank_why)])), "start_epoch": START, "ends_epoch": ends, "now_epoch": time.time(), "state": st["state"], "code_hash": code_hash, "file_sha": fsha, "model_sha": msha, "columns_allowlist": ALLOW, "budget_ms": BUDGET, "counts": dict(counts),
                                 "queue_lag_p50_s": round(statistics.median(lag), 1) if lag else None, "total_p50_ms": agg["total_p50_ms"], "total_p90_ms": agg["total_p90_ms"], "over_budget_n": agg["over_budget_n"], "stages": agg["stages"], "decider": agg["decider"], "gaps": agg["gaps"],
                                 "slow_stages": st["slow"][-20:], "v4": ch.v4.run_block(), "gap_rules": G.RULES, "load_s": round(t_start - t_load, 1), "check_cmd": chk, "not_attached_why": {k: v[1] for k, v in ch.NA.items()}})
        atomic(TR + "/tail.json", st["tail"]); last_w = time.time()
    write_run()
    try:
        while time.time() < ends and st["state"] == "running":
            rows = db.execute(sql, (st["cursor"][0], st["cursor"][0], st["cursor"][1])).fetchall()
            for row in rows:
                if time.time() >= ends: break
                rd = time.time(); line, text, full = ch.trace(row); line.update(seq=st["seq"], read_at=rd, lag_s=round(rd - row[7], 2))
                if line["state"] == "traced":
                    _tj = time.perf_counter(); d = JD.add(line["id"], line["journal"]["story_key"], line["source"], st["seq"], run_id, code_hash, (line.get("published") or "")[:10] or None) if JD else JR.classify(kidx, line["journal"]["story_key"], line["source"], st["seq"]); _jms = (time.perf_counter() - _tj) * 1000
                    line["journal"].update(story_key=d["keys"], dup={"kind": d["kind"], "of_seq": d["of_seq"]}, publishers=d["publishers"], novelty_proxy=novelty_proxy(d))   # skipped lines carry no journal
                    ch.v4.post(line, text, full, row, d, _jms, JD.seen[line["id"]]["gseq"] if JD else st["seq"])   # live-trace-v4 stages (five, off ones recorded as not_attached), total_ms updated
                line["gaps"] = G.per_article_gaps(line)
                js = json.dumps(line, sort_keys=True, separators=(",", ":"), ensure_ascii=False); sha = hashlib.sha256((st["prev"] + js).encode()).hexdigest()
                json.dump({"article_line": line, "text": text, "stages_full": full}, open(TR + "/a/%d.json" % st["seq"], "w"), ensure_ascii=False)
                cf.write(json.dumps({"seq": st["seq"], "prev": st["prev"], "sha": sha, "line": js}, ensure_ascii=False) + "\n"); cf.flush()
                st["prev"] = sha; st["seq"] += 1; st["cursor"] = (row[7], row[0]); st["lines"].append(line); st["tail"] = ([line] + st["tail"])[:40]; st["lag"].append(line["lag_s"]); counts["traced" if line["state"] == "traced" else "skipped"] += 1
                for s in line["stages"]:
                    if s.get("slow"): st["slow"].append({"seq": line["seq"], "stage": s["name"], "ms": s["ms"]})
                if time.time() - last_w >= 3: write_run()
                if time.time() - last_h >= 300:
                    last_h = time.time(); f2, m2 = hash_sets(ch)
                    if f2 != fsha or m2 != msha: st["state"] = "drift_stop"; st["drift"] = [k for k in set(f2) | set(m2) if (f2.get(k) != fsha.get(k)) and (m2.get(k) != msha.get(k))][:10]; break
            if st["state"] != "running": break
            if len(rows) < 25:
                if time.time() - last_w >= 3: write_run()
                time.sleep(min(POLL, max(0.0, ends - time.time())) if not rows else 0.5)
        write_run("drift_stop" if st["state"] == "drift_stop" else "stopped")
    except Exception as e:
        write_run("error"); raise
def timeit(n):
    db = sqlite3.connect("file:%s?mode=ro" % QUEUE, uri=True); rows = db.execute(select_sql("ready_at is not null and ready_at >= ?", 400), (float(os.environ["TIME_SINCE"]) if os.environ.get("TIME_SINCE") else time.time() - 7200,)).fetchall()[-n:]   # TIME_SINCE=<epoch> fixes the window, so two timed runs read the same rows
    if os.environ.get("TIME_IDS"): rows = [r for r in (db.execute(select_sql("id = ?"), (i,)).fetchone() for i in json.load(open(os.environ["TIME_IDS"]))[:n]) if r]   # TIME_IDS=<json list of queue ids>: time exactly these articles (read-only), e.g. the articles of an earlier live run
    t0 = time.time(); ch = Chain(); print("load_s", round(time.time() - t0, 1), "v4 flags on:", ch.v4.active() or "none", flush=True); res = []
    kidx = JR.new_index(); jdir = None; JD = None
    if ch.v4.on["journal"]:
        import tempfile; jdir = os.environ.get("JOURNAL_DIR") or tempfile.mkdtemp(prefix="lt-time-journal-"); JD = JR.Durable(os.path.join(jdir, "journal.jsonl")); print("journal dir", jdir, flush=True)   # timing writes a throwaway journal (JOURNAL_DIR if given)
    for i, r in enumerate(rows):
        l, text, full = ch.trace(r)
        if l["state"] == "traced":   # the same journal + v4 steps main() runs
            _tj = time.perf_counter(); d = JD.add(l["id"], l["journal"]["story_key"], l["source"], i, "time", "time", (l.get("published") or "")[:10] or None) if JD else JR.classify(kidx, l["journal"]["story_key"], l["source"], i); _jms = (time.perf_counter() - _tj) * 1000
            l["journal"].update(story_key=d["keys"], dup={"kind": d["kind"], "of_seq": d["of_seq"]}, publishers=d["publishers"], novelty_proxy=novelty_proxy(d)); ch.v4.post(l, text, full, r, d, _jms, JD.seen[l["id"]]["gseq"] if JD else i)
        res.append(l)
    tr = [l for l in res if l["state"] == "traced"]; print("traced", len(tr), "skipped", len(res) - len(tr))
    v4n = {V4M.STAGE[f] for f in V4M.FLAGS}; SK = int(os.environ.get("TIME_SKIP", 2)); base = sorted(round(sum(s["ms"] for s in l["stages"] if s["name"] not in v4n), 2) for l in tr[SK:])   # TIME_SKIP=N: leave the first N traced rows out of the stats (default 2); warm-up rows put in front of TIME_IDS then fill the caches as the live process has them   # the v3 stages alone, to tell load drift from what the v4 stages add
    if base: print("v3 stages alone (excluding first %d) p50" % SK, base[len(base) // 2], "p90", base[min(len(base) - 1, int(0.9 * len(base)))], "n", len(base))
    for label, sub in (("all", tr), ("excluding first %d (warm-up)" % SK, tr[SK:])):
        t = sorted(l["total_ms"] for l in sub); print(label, "p50", t[len(t) // 2], "p90", t[min(len(t) - 1, int(0.9 * len(t)))], "n", len(t))
    sub = tr[SK:]; tot = sum(l["total_ms"] for l in sub); per = collections.defaultdict(list)
    for l in sub:
        for s in l["stages"]: per[s["name"]].append(s["ms"])
    for k, v in sorted(per.items(), key=lambda kv: -sum(kv[1])): print("%-20s share %5.1f%%  p50 %7.1f  p90 %7.1f" % (k, 100 * sum(v) / tot, statistics.median(v), sorted(v)[int(0.9 * (len(v) - 1))]))
    print("states", dict(collections.Counter((s["name"], s["state"]) for l in tr for s in l["stages"] if s["state"] in ("error", "timeout"))))
def replay_run(ids):
    db = sqlite3.connect("file:%s?mode=ro" % QUEUE, uri=True); ch = Chain(); out = {}; kidx = JR.new_index()   # replay never writes a journal: the story keys go through the in-memory index, in the order of the ids
    for seq, i in enumerate(ids):
        r = db.execute(select_sql("id = ?"), (i,)).fetchone()
        if r is None: out[i] = None; continue
        l, text, full = ch.trace(r)
        if l["state"] == "traced":
            d = JR.classify(kidx, l["journal"]["story_key"], l["source"], seq); l["journal"].update(story_key=d["keys"], dup={"kind": d["kind"], "of_seq": d["of_seq"]}, publishers=d["publishers"], novelty_proxy=novelty_proxy(d)); ch.v4.post(l, text, full, r, d, 0.0, seq)
        out[i] = {"text_sha1": l["input"]["text_sha1"], "state": l["state"], "stages": [[s["name"], s["state"], s["n"], s["out"]] for s in l["stages"]], "decider": l["decider"]}
    print("REPLAY_JSON " + json.dumps(out, sort_keys=True, ensure_ascii=False))
if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--time": timeit(int(sys.argv[2]))
    elif len(sys.argv) > 2 and sys.argv[1] == "--replay-run": replay_run(sys.argv[2].split(","))
    else: main()
