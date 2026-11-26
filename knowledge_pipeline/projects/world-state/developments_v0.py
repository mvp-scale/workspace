"""developments_v0: group a window's articles into developments and project each one for the page (PROVISIONAL).
Method: playbook/design/knowledge-consolidation-method.md sections 1, 2, 5. Words: playbook/design/terminology.md.
A development = a group of articles about one dated event or sequence of events, with the assertions they carry.
Build rule (D3, the setting the method settled on; in-sample on two staged windows, c1 and mix):
  average-link agglomerative clustering of articles; sim(i,j) = ((cos headline + cos evidence text) / 2 + 0.5 * cos entities) * exp(-gap_hours / 96); merge while sim >= 0.04.
  headline / evidence text: TF-IDF; entities: IDF-weighted named endpoints of the article's assertions; tokens and entities in more than 40% of articles are dropped (hub rule).
Qualifies: 2 or more articles and at least 1 full read; otherwise "thin" (listed collapsed).
No model call, no network, no model-written text: every title is a quoted headline, every summary and line a quoted source sentence. Deterministic.
Inputs: the window's slow_consolidate/knowledge.json (assertions = edges, evidence = their fragments, contradictions = contested), chain.jsonl (headline, day, read depth, url), via concepts_v0.load.
MISSING (stated in the output notes): development id stable across windows; forward statement speaker; attributed cause; processing time.
    python3 developments_v0.py <trace dir> [area] [--cut <seq>] [--json]"""
import os, re, sys, json, math, hashlib, collections
from datetime import datetime
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import concepts_v0 as CV
import lexicons as LX

PARAMS = dict(thr=0.04, tau=96.0, wt=1.0, wc=0.5, hub=0.4)
# Round B2 (ledger L3024): the merge threshold as a rule of the window, not a constant. rule None = thr as is (production until a rule passes its bar);
# rule "decay": thr_eff = thr * d_win / d_ref, d_win = mean over article pairs of exp(-gap / tau); d_ref = mean of d_win over the tuning windows c1 and mix (measured, scratchpad b2/dref.py).
RULE_REF = {"decay": 0.8087}
PARAMS["rule"] = None

def thr_eff(P, decays, bases=None):
    """the merge threshold for one window: P["thr"] unless P["rule"] names a rule (see RULE_REF); label-free, order independent (fsum)"""
    r = P.get("rule")
    if r is None or not decays: return P["thr"]
    if r == "decay": return P["thr"] * (math.fsum(decays) / len(decays)) / RULE_REF["decay"]
    if r == "similarity" and bases: return P["thr"] * (math.fsum(bases) / len(bases)) / RULE_REF["similarity"]
    return P["thr"]
STOP = set("the a an of to in on and or for with by at from as is are was were be been it its that this his her their after over into than but not has have had will would said says say who which about up out new s".split())
GEN = set("says say said after days amid live news photos video over new how what could why who first more than year time back".split())
NAMED = {"iso", "person", "org", "place", "facility", "event", "product", "other", "substance"}
FWD = re.compile(r"\b(will|would|could|may|expected to|plans? to|preparing|warn(?:s|ed|ing)?|threat(?:en|ens|ened)?|vow|pledge|forecast|to last)\b", re.I)
_NOT_FWD = LX.seq("forward.not_forward_phrases")   # data (lexicons.json, round A); KP_LEXICONS=off leaves it empty
FWD_NOT = re.compile(r"\b(" + "|".join(re.escape(w) for w in _NOT_FWD) + r")\b", re.I) if _NOT_FWD else re.compile(r"(?!)")
SAYV = r"(?:also |had |has |have )?(?:said|says|warned|warns|told|predicted|forecast|insisted|added|vowed|pledged|announced)"
SAYER = re.compile(r"(?:^|[.;:\u201c\"]\s*)((?:[A-Z][\w’'.-]*|of|for|the|at|and|de)(?:[\s,]+(?:[A-Z][\w’'.-]*|of|for|the|at|and|de)){0,7}?|[A-Z][a-z]+ (?:officials|leaders|authorities|residents|analysts)|[A-Z][a-z]+)\s*,?\s+" + SAYV + r"\b")
PRON = {"he", "she", "they", "it", "we", "i", "you", "the", "this", "that", "later", "but", "and"}
ROLE = re.compile(r"((?:[A-Z][\w.-]*(?:\s+[A-Z][\w.-]*)*(?:’s|'s)\s+(?:[a-z-]+\s+){0,2}(?:forces|military|army|ministry|government|officials|spokesperson|spokesman|spokeswoman|commander-in-chief|chief))|(?:[Aa]n?\s+)?(?:spokesperson|spokesman|spokeswoman)\s+for\s+the\s+[A-Z][\w]*(?:\s+[A-Z][\w]*)*)\s*,?\s+" + SAYV + r"\b")
APPOS = re.compile(r",\s*((?:[A-Z][\w.’'-]*\s+){1,5}[A-Z][\w’'-]*),\s+" + SAYV + r"\b")
def sayer(q):
    """the speaker written in the sentence itself ('X said ...', 'X's military said', ', Name, warned'); None for pronouns or no reporting verb"""
    for rx in (APPOS, ROLE):
        m = rx.search(q or "")
        if m: return m.group(1).strip(" ,")
    m = SAYER.search(q or "")
    if not m: return None
    w = re.sub(r"^(?:Later|But|And|Meanwhile),?\s+", "", m.group(1).strip(" ,"))
    return None if not w or w.split()[0].lower() in PRON or len(w) > 70 else w
CAUSE = re.compile(r"\b(because|due to|in response to|as a result|caused|causing|led to|leading to|triggered)\b", re.I)
DEFAULT_CUT_SHARE = 0.25     # "since your last look" default: the last 25% of the window's articles are new
MAX_KNOW, MAX_EVID, MAX_FOLLOW_PER_DAY, MAX_FWD, MAX_CAUSE = 8, 10, 2, 5, 3
MOVED = "moved: new + corroborated or contradicted"; SINGLE = "new, single-source"; NOTHING = "nothing new"
MOVED_ORDER = {MOVED: 0, SINGLE: 1, NOTHING: 2}
_CACHE = {}

def toks(s): return [w for w in re.findall(r"[a-z0-9£%']+", (s or "").lower().replace("’", "'")) if w not in STOP and len(w) > 2]
def ctoks(s): return {w for w in toks(s) if w not in GEN}
def ptype(x): return x.split(":")[0] if x and ":" in x else None
def clean(s): return 35 <= len(s or "") <= 260 and not re.search(r"[#*|]", s)
def _day(p): return (p or "")[:10]
def _ts(p):
    try: return datetime.fromisoformat((p or "").replace("Z", "")[:19])
    except Exception: return datetime(1970, 1, 1)
def idf(sets, n):
    df = collections.Counter(x for s in sets for x in set(s)); return {k: math.log((n + 1) / (v + .5)) for k, v in df.items()}, df
def cos(u, v):
    if not u or not v: return 0.0
    num = sum(u[k] * v[k] for k in u if k in v)
    return num / (math.sqrt(sum(x * x for x in u.values())) * math.sqrt(sum(x * x for x in v.values()))) if num else 0.0

def _articles(td):
    """article records in seq order: id, seq, publisher, title, url, published, read depth (chain.jsonl rows; same row format as raw-units _inner)"""
    out = []
    for l in open(os.path.join(td, "chain.jsonl"), encoding="utf-8"):
        try:
            x = json.loads(l); ln = x.get("line")
            if isinstance(ln, str): ln = json.loads(ln)
            if not isinstance(ln, dict): ln = x if "stages" in x else None
        except Exception: continue
        if not ln or not ln.get("id"): continue
        rd = ((ln.get("input") or {}).get("read") or {})
        out.append({"id": ln["id"], "seq": ln.get("seq"), "publisher": ln.get("source"), "title": ln.get("title") or "", "url": ln.get("url"), "published": ln.get("published") or "", "read_depth": rd.get("depth")})
    out.sort(key=lambda a: (a["seq"] is None, a["seq"] if a["seq"] is not None else 0))
    for i, a in enumerate(out): a["i"] = i       # index in seq order; the cut is on seq
    return out

def _agglo(n, S, thr):
    """average-link agglomerative clustering on the similarity matrix S (Lance-Williams update = exact average link); the best pair wins, ties go to the first found"""
    cl = {i: [i] for i in range(n)}; sim = {(i, j): S[i][j] for i in range(n) for j in range(i)}
    def key(a, b): return (a, b) if a > b else (b, a)
    while len(cl) > 1:
        best = None
        for (a, b), s in sim.items():
            if best is None or s > best[0]: best = (s, a, b)
        if best is None or best[0] < thr: break
        _, a, b = best; na, nb = len(cl[a]), len(cl[b])      # a > b: a merges into b
        for k in cl:
            if k in (a, b): continue
            sim[key(b, k)] = (na * sim.pop(key(a, k)) + nb * sim[key(b, k)]) / (na + nb)
        sim.pop(key(a, b)); cl[b] = cl[b] + cl.pop(a)
    return [sorted(v) for v in cl.values()]

def _group(D, arts, P=PARAMS):
    """cluster the articles of one window -> groups of article indexes (largest first), headline vectors"""
    K = D["K"]; n = len(arts); idx = {a["id"]: a["i"] for a in arts}
    evs = [[] for _ in range(n)]; ents = [[] for _ in range(n)]
    for eid, e in sorted((K.get("edges") or {}).items()):
        seen = set()
        for f in e.get("fragments") or []:
            i = idx.get(f.get("art"))
            if i is None: continue
            evs[i].append(f.get("sent") or "")
            if i not in seen:
                seen.add(i)
                for x in (e.get("subject"), e.get("object")):
                    if x and ptype(x) in NAMED: ents[i].append(x)
    w, df = idf(ents, n); cast = [{x: w[x] for x in set(S) if df[x] / n <= P["hub"]} for S in ents]
    def tv(sets):
        w2, df2 = idf(sets, n); return [{k: (1 + math.log(c)) * w2[k] for k, c in collections.Counter(T).items() if df2[k] / n <= P["hub"]} for T in sets]
    title = tv([toks(a["title"]) for a in arts]); evt = tv([[t for s in evs[i] for t in toks(s)] for i in range(n)])
    ts = [_ts(a["published"]) for a in arts]
    S = [[0.0] * n for _ in range(n)]; decs = []; bases = []
    for i in range(n):
        for j in range(i):
            gap = abs((ts[i] - ts[j]).total_seconds()) / 3600
            v = P["wt"] * (cos(title[i], title[j]) + cos(evt[i], evt[j])) / 2 + P["wc"] * cos(cast[i], cast[j]); dec = math.exp(-gap / P["tau"])
            S[i][j] = S[j][i] = v * dec; decs.append(dec); bases.append(v)
    groups = _agglo(n, S, thr_eff(P, decs, bases)); groups.sort(key=lambda g: (-len(g), g[0]))
    return groups, title

def _owner(pub): return CV.owners_map().get(pub, pub)

def _evidence_rows(e, members, arts, idx):
    """the evidence of one assertion inside a development: one row per fragment in a member article"""
    rows = []
    for f in e.get("fragments") or []:
        i = idx.get(f.get("art"))
        if i is None or i not in members: continue
        a = arts[i]; pub = f.get("pub") or a["publisher"]
        rows.append({"quote": f.get("sent") or "", "publisher": pub, "owner": _owner(pub), "day": _day(a["published"]), "read_depth": a["read_depth"], "article_id": a["id"], "seq": a["seq"], "title": a["title"], "url": a["url"], "_i": i})
    return rows

def _word(owners, against, disputed=False):
    """certainty word, the four words of concepts_v0.sureness; certainty number = owners / (owners + contradictions + 1)"""
    return CV.sureness(owners, owners / (owners + against + 1.0), disputed)

def _contradictions(K, idx):
    """contradiction pairs (knowledge.contested) -> one contradiction per group of pairs that share an assertion"""
    E = K.get("edges") or {}; pairs = K.get("contested") or []; par = {}
    def f(x):
        par.setdefault(x, x)
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for c in pairs: par[f(c["a"])] = f(c["b"])
    grp = collections.defaultdict(list)
    for c in pairs: grp[f(c["a"])].append(c)
    out = []
    for g in grp.values():
        sides = {}; kinds = []
        for c in g:
            kinds.append(c.get("kind"))
            for eid, s in (c.get("sides") or {}).items(): sides.setdefault(eid, s)
        edges = sorted(sides); ai = set(); firsts = []
        for eid in edges:
            ii = sorted({idx[fr["art"]] for fr in (E.get(eid) or {}).get("fragments") or [] if fr.get("art") in idx}); ai |= set(ii)
            if ii: firsts.append(ii[0])
        seenq = set(); sl = []
        for eid in edges:
            s = sides[eid]; k = (s.get("quote"), s.get("outcome"))
            if k in seenq: continue
            seenq.add(k); sl.append({"edge_id": eid, "quote": s.get("quote"), "outcome": s.get("outcome"), "said": s.get("said"), "day": s.get("day"), "speakers": [x.get("text") or x.get("entity") for x in s.get("speakers") or []]})
        out.append({"label": g[0].get("label"), "kinds": sorted({k for k in kinds if k}), "pairs": len(g), "sides": sl, "edges": edges, "arts": ai,
                    "first_i": max(firsts) if firsts else None, "named": sum(1 for s in sl if s["speakers"]) >= 2})   # appears once both sides are read: the later side's first article
    out.sort(key=lambda c: (c["label"] or "", c["edges"]))
    return out

def _ent_label(D, cid):
    try: return CV._label_of(cid, D["ents"])
    except Exception: return cid.split(":", 1)[-1]

def _build_group(D, arts, idx, g, title_vec, pubs_in_window, cons, cut_i):
    """one development record. cut_i = index (seq order) of the last article already seen; later articles are new"""
    E = D["K"].get("edges") or {}; members = set(g); mem = [arts[i] for i in g]
    def avg(i): return sum(cos(title_vec[i], title_vec[j]) for j in g if j != i) / max(1, len(g) - 1)
    med = max(g, key=lambda i: (avg(i), -i)) if len(g) > 1 else g[0]       # the headline most like the others (medoid)
    T = set().union(*[ctoks(arts[i]["title"]) for i in g])
    owners = {_owner(a["publisher"]) for a in mem}
    full = sum(1 for a in mem if a["read_depth"] == "full"); teaser = sum(1 for a in mem if a["read_depth"] == "teaser")
    # on-story assertions: evidence in a member article that shares 2+ content words with the member headlines
    asr = []
    for eid, e in sorted(E.items()):
        rows = _evidence_rows(e, members, arts, idx)
        if rows and any(len(ctoks(r["quote"]) & T) >= 2 for r in rows): asr.append((eid, e, rows))
    ebid = {eid: (e, rows) for eid, e, rows in asr}
    dcons = [c for c in cons if c["arts"] & members]; cons_edges = {x for c in dcons for x in c["edges"]}
    first_i = {eid: min(r["_i"] for r in rows) for eid, e, rows in asr}
    def best_row(rows):
        c = sorted([r for r in rows if clean(r["quote"])], key=lambda r: (len(r["quote"]), r["day"]))
        return c[0] if c else None
    def pack(eid):
        e, rows = ebid[eid]; ow = len({r["owner"] for r in rows}); r0 = best_row(rows)
        disp = eid in cons_edges and any(c["named"] for c in dcons if eid in c["edges"])
        return {"id": eid, "quote": r0["quote"] if r0 else None, "triple": [e.get("subject"), e.get("predicate"), e.get("object")], "owners": ow, "owner_names": sorted({r["owner"] for r in rows}), "articles": len({r["article_id"] for r in rows}),
                "certainty_word": _word(ow, 1 if eid in cons_edges else 0, disp), "first_day": min(r["day"] for r in rows), "last_day": max(r["day"] for r in rows), "in_contradiction": eid in cons_edges,
                "evidence": [{k: v for k, v in r.items() if k != "_i"} for r in sorted(rows, key=lambda r: (r["day"], r["seq"] if r["seq"] is not None else 0))[:MAX_EVID]], "evidence_total": len(rows)}
    # best-supported quote: owners, then articles, then shortest; predicate not be/have; clean sentences only
    cand = []
    for eid, e, rows in asr:
        if e.get("predicate") in ("be", "have"): continue
        ow = len({r["owner"] for r in rows}); na = len({r["article_id"] for r in rows})
        for r in rows:
            if clean(r["quote"]): cand.append((-ow, -na, len(r["quote"]), eid, r))
    cand.sort(key=lambda t: t[:4])
    summary = None
    if cand:
        r = cand[0][4]; eid = cand[0][3]
        summary = {"quote": r["quote"], "publisher": r["publisher"], "owner": r["owner"], "day": r["day"], "owners": len({z["owner"] for z in ebid[eid][1]}), "article_id": r["article_id"], "url": r["url"], "assertion_id": eid}
    know = []; shown = set()   # one line per quoted sentence: several assertions can share one sentence
    for c in cand:
        if len(know) >= MAX_KNOW: break
        if all(k["id"] != c[3] for k in know):
            p = pack(c[3])
            if p["quote"] not in shown: shown.add(p["quote"]); know.append(p)
    # FOLLOW: dated steps = the best-supported assertions first read on each day
    firstday = {eid: min(r["day"] for r in rows) for eid, e, rows in asr}; perday = collections.defaultdict(list); seen_e = set()
    for c in cand:
        if c[3] not in seen_e: seen_e.add(c[3]); perday[firstday[c[3]]].append(c[3])
    days = sorted({_day(a["published"]) for a in mem})
    steps = []; shown_f = set()
    for d in days:
        items = []
        for x in perday.get(d, []):
            if len(items) >= MAX_FOLLOW_PER_DAY: break
            p = pack(x)
            if p["quote"] not in shown_f: shown_f.add(p["quote"]); items.append(p)
        steps.append({"day": d, "articles": sum(1 for a in mem if _day(a["published"]) == d), "items": items})
    causes = []; seen_s = set()
    for eid, e, rows in asr:
        for r in rows:
            if CAUSE.search(r["quote"]) and clean(r["quote"]) and r["quote"] not in seen_s and len(causes) < MAX_CAUSE:
                seen_s.add(r["quote"]); causes.append({"quote": r["quote"], "publisher": r["publisher"], "day": r["day"], "article_id": r["article_id"], "url": r["url"], "assertion_id": eid})
    # EXPECT: forward statements (wording match; speaker shown when claims v1 read one)
    seen_s = set(); allfwd = []
    for eid, e, rows in asr:
        for r in rows:
            if FWD.search(r["quote"]) and not FWD_NOT.search(r["quote"]) and clean(r["quote"]) and r["quote"] not in seen_s: seen_s.add(r["quote"]); allfwd.append((r["_i"], eid, r))
    # speaker: claims v1 attrs.speaker on the consolidated assertion (G2 -> slow consolidate); None when not read
    CE = (D.get("C") or {}).get("edges") or {}; CE = CE.values() if isinstance(CE, dict) else CE
    spk = {x.get("id"): (x.get("attrs") or {}).get("speaker") for x in CE if (x.get("attrs") or {}).get("speaker")}
    def who(eid, q):
        if spk.get(eid): return _ent_label(D, spk[eid]), "claims"
        w = sayer(q); return (w, "sentence") if w else (None, None)
    allfwd.sort(key=lambda t: (0 if who(t[1], t[2]["quote"])[0] else 1, -len({z["owner"] for z in ebid[t[1]][1]}), t[0], t[2]["quote"]))
    fwd = []
    for i0, eid, r in allfwd[:MAX_FWD]:
        w, src = who(eid, r["quote"])
        fwd.append({"quote": r["quote"], "publisher": r["publisher"], "owner": r["owner"], "day": r["day"], "article_id": r["article_id"], "url": r["url"], "assertion_id": eid,
                    "speaker": w, "speaker_source": src, "speaker_id": spk.get(eid), "new": i0 > cut_i})
    con_out = [{"label": c["label"], "kinds": c["kinds"], "pairs": c["pairs"], "sides": c["sides"], "speakers_named_both_sides": c["named"], "new": c["first_i"] is not None and c["first_i"] > cut_i} for c in dcons]
    cert_word = _word(len(owners), len(dcons), any(c["named"] for c in dcons))
    # since your last look
    before = [i for i in g if i <= cut_i]; after = [i for i in g if i > cut_i]
    new_a = [eid for eid in ebid if first_i[eid] > cut_i]
    new_corr = [eid for eid in new_a if len({r["owner"] for r in ebid[eid][1]}) >= 2]
    reinf = [eid for eid in ebid if first_i[eid] <= cut_i and len({r["owner"] for r in ebid[eid][1] if r["_i"] <= cut_i}) == 1 and len({r["owner"] for r in ebid[eid][1]}) >= 2]
    old_cons = [c for c in dcons if c["first_i"] is not None and c["first_i"] <= cut_i]
    word_before = _word(len({_owner(arts[i]["publisher"]) for i in before}), len(old_cons), any(c["named"] for c in old_cons)) if before else None
    word_changed = bool(before and word_before != cert_word)
    if not after: moved = NOTHING
    elif new_corr or any(c["new"] for c in con_out) or reinf or word_changed: moved = MOVED
    elif new_a: moved = SINGLE
    else: moved = NOTHING
    pick = sorted(new_corr, key=lambda x: (-len({r["owner"] for r in ebid[x][1]}), x))
    lines = [dict(pack(x), kind="new, corroborated") for x in pick if best_row(ebid[x][1])][:3]
    lines += [dict(pack(x), kind="new, single-source") for x in new_a if x not in new_corr and best_row(ebid[x][1])][:max(0, 3 - len(lines))]
    lines += [dict(pack(x), kind="reinforced (second owner since the cut)") for x in reinf if best_row(ebid[x][1])][:2]
    since = {"cut_seq": arts[cut_i]["seq"] if cut_i >= 0 else None, "articles_before": len(before), "articles_after": len(after), "new_assertions": len(new_a), "new_corroborated": len(new_corr), "reinforced": len(reinf),
             "new_contradictions": sum(1 for c in con_out if c["new"]), "new_forward_statements": sum(1 for x in fwd if x["new"]), "certainty_word_before": word_before, "certainty_word_changed": word_changed, "lines": lines}
    cast = collections.Counter()
    for eid, e, rows in asr:
        for x in (e.get("subject"), e.get("object")):
            if x and ptype(x) in NAMED: cast[x] += 1
    chips = []
    for x, c in sorted(cast.items(), key=lambda t: (-t[1], t[0])):
        lab = _ent_label(D, x)
        if lab.lower() in pubs_in_window: continue
        chips.append({"id": x, "label": lab, "kind": ptype(x), "assertions": c})
        if len(chips) >= 6: break
    return {"id": "dev:" + hashlib.sha1("|".join(sorted(arts[i]["id"] for i in g)).encode()).hexdigest()[:10], "title": arts[med]["title"], "title_article_id": arts[med]["id"], "title_publisher": arts[med]["publisher"], "title_url": arts[med]["url"],
            "summary": summary, "first_day": days[0], "last_day": days[-1], "days": len(days), "articles": len(g), "owners": len(owners), "full_reads": full, "teaser_reads": teaser, "thin": len(g) < 2 or full == 0,
            "certainty_word": cert_word, "certainty_basis": "owners of the member articles; disputed only when a contradiction has named speakers on both sides",
            "assertions": len(asr), "corroborated_assertions": sum(1 for eid in ebid if len({r["owner"] for r in ebid[eid][1]}) >= 2),
            "contradictions": con_out, "entities": chips, "know": know,
            "follow": {"steps": steps, "stated_causes": causes, "connectives": "after = time order only; because = only a cause written in a source sentence (speaker not read); but = a contradiction"},
            "expect": {"statements": fwd, "n_found": len(allfwd), "empty_note": None if allfwd else "No forward statement read in %d articles (%d teaser-only). Not the same as nothing expected." % (len(g), teaser)},
            "since": since, "moved": moved, "members": [{"seq": arts[i]["seq"], "title": arts[i]["title"], "publisher": arts[i]["publisher"], "day": _day(arts[i]["published"]), "read_depth": arts[i]["read_depth"], "url": arts[i]["url"], "id": arts[i]["id"]} for i in g],
            "_last": max(arts[i]["published"] for i in g)}

def members_of(result):
    """{development id: [member article ids]} over the developments and the thin ones of a build() result (round D: the 'prev' of the next cut)"""
    ds = sorted((result.get("developments") or []) + (result.get("thin") or []), key=lambda d: (-len(d["members"]), d["id"]))   # canonical order (larger first, then id), independent of the arrival order: carry_ids reads it as "older first" on ties
    return {d["id"]: [m["id"] for m in d["members"]] for d in ds}

def carry_ids(devs, prev, age=None):
    """round D, rule D4 (ledger L3015): a development carries the id of the previous-cut development whose members are >= 50% contained in it
    (|prev members in new| / |prev members| >= 0.5). One-to-one; ties: highest containment, then the older id (age = {id: first-seen cut index}, optional; unknown ages rank last), then the smaller id. The dict order of prev is NOT read (it depends on the arrival order); no id is reused.
    Developments that carry nothing keep their own hash id (a suffix .k when that hash is already taken). Rewrites dev["id"] in place; pure and deterministic.
    Returns [{new_id, prev_id, containment, jaccard, hash_id}] for the carried ids (jaccard is information only)."""
    if not prev: return []
    order = {pid: ((age or {}).get(pid, 1 << 30)) for pid in prev}; mem = [set(m["id"] for m in d["members"]) for d in devs]; pm = {pid: set(v) for pid, v in prev.items()}
    cand = []
    for i, d in enumerate(devs):
        for pid, P in pm.items():
            if not P: continue
            c = len(P & mem[i]) / len(P)
            if c >= 0.5: cand.append((-c, order[pid], pid, d["id"], i))
    cand.sort(); used_new = set(); used_prev = set(); out = []
    for nc, _, pid, hid, i in cand:
        if i in used_new or pid in used_prev: continue
        used_new.add(i); used_prev.add(pid); P = pm[pid]; u = len(P | mem[i])
        out.append({"new_id": pid, "prev_id": pid, "containment": round(-nc, 4), "jaccard": round(len(P & mem[i]) / u, 4) if u else 0.0, "hash_id": hid, "_i": i})
    taken = {o["new_id"] for o in out}
    for i, d in enumerate(devs):
        if i in used_new: continue
        h = d["id"]; k = 1; nid = h
        while nid in taken: k += 1; nid = "%s.%d" % (h, k)
        taken.add(nid); d["id"] = nid
    for o in out: devs[o.pop("_i")]["id"] = o["new_id"]
    return sorted(out, key=lambda o: o["new_id"])

def build(td, area=None, cut=None, prev=None, only=None, shuffle_seed=None):
    """the window's developments. cut = article seq of the last article already seen (default: the last 25% of the window is new).
    Round D: prev = {previous-cut development id: [member article ids]} (members_of of the previous build) -> ids carried by carry_ids, extra key "carry";
    only = set of article ids kept (a prefix of the window; the knowledge.json is used as is, fragments of other articles are ignored);
    shuffle_seed = the arrival order of the articles is permuted by sha1(seed|id) before grouping (control: ids and memberships must not change)."""
    td = os.path.abspath(td); kp = os.path.join(td, "slow_consolidate", "knowledge.json")
    if not os.path.exists(kp) or not os.path.exists(os.path.join(td, "chain.jsonl")): return {"exists": False, "why": "this window has no slow_consolidate/knowledge.json + chain.jsonl"}
    D = CV.load(td)
    if not isinstance(D["K"], dict): return {"exists": False, "why": "knowledge.json is not readable"}
    arts = _articles(td)
    if only is not None:
        arts = [x for x in arts if x["id"] in only]
        for i, x in enumerate(arts): x["i"] = i
    if shuffle_seed is not None:
        arts.sort(key=lambda x: hashlib.sha1(("%s|%s" % (shuffle_seed, x["id"])).encode()).hexdigest())
        for i, x in enumerate(arts): x["i"] = i
    n = len(arts)
    if not n: return {"exists": False, "why": "this window has no articles"}
    idx = {a["id"]: a["i"] for a in arts}; sig = (td, os.path.getmtime(os.path.join(td, "chain.jsonl")), os.path.getmtime(kp), None if only is None else tuple(sorted(only)), shuffle_seed); c = _CACHE.get("g")
    if c and c["sig"] == sig: groups, tv = c["groups"], c["tv"]
    else: groups, tv = _group(D, arts); _CACHE["g"] = {"sig": sig, "groups": groups, "tv": tv}
    seqs = [a["seq"] for a in arts]; default_i = n - max(1, int(round(n * DEFAULT_CUT_SHARE))) - 1
    cut_i = default_i if cut is None else max([i for i, s in enumerate(seqs) if s is not None and s <= int(cut)], default=-1)
    pubs = {(a["publisher"] or "").lower() for a in arts}; cons = _contradictions(D["K"], idx)
    devs = [_build_group(D, arts, idx, g, tv, pubs, cons, cut_i) for g in groups]
    live = [d for d in devs if not d["thin"]]; thin = [d for d in devs if d["thin"]]
    live.sort(key=lambda d: d["_last"], reverse=True); live.sort(key=lambda d: MOVED_ORDER[d["moved"]])      # moved first, then the most recent (stable)
    thin.sort(key=lambda d: (-d["articles"], d["id"]))
    for d in devs: d.pop("_last", None)
    carry = carry_ids(live + thin, prev) if prev is not None else None   # after the sorts: the order stays the one of the hash ids
    days = sorted({_day(a["published"]) for a in arts if a["published"]})
    res = {"exists": True, "area": area, "provisional": True, "method": "developments_v0: average-link clustering on headline + evidence text + entities, time decay 96 h, merge while sim >= 0.04 (knowledge-consolidation-method.md section 2.1)",
            "window": {"articles": n, "owners": len({_owner(a["publisher"]) for a in arts}), "publishers": len(pubs), "first_day": days[0] if days else None, "last_day": days[-1] if days else None, "days": len(days),
                       "full_reads": sum(1 for a in arts if a["read_depth"] == "full"), "teaser_reads": sum(1 for a in arts if a["read_depth"] == "teaser")},
            "cut": {"seq": arts[cut_i]["seq"] if cut_i >= 0 else None, "default_seq": arts[default_i]["seq"] if default_i >= 0 else None, "first_seq": seqs[0], "last_seq": seqs[-1], "articles_after": n - 1 - cut_i, "default_share": DEFAULT_CUT_SHARE,
                    "options": [{"seq": arts[i]["seq"], "day": _day(arts[i]["published"])} for i in range(0, n - 1)]},
            "counts": {"developments": len(live), "thin": len(thin), "articles_in_developments": sum(d["articles"] for d in live), "moved": sum(1 for d in live if d["moved"] == MOVED), "contradictions": len(cons),
                       "compression": round(n / len(live), 2) if live else None},
            "developments": live, "thin": thin,
            "notes": {"id_stable_across_windows": "CARRIED by carry_ids (round D, rule D4): when build() is given prev = members_of(the previous cut), a development keeps the id of the earlier development whose members are >= 50% contained in it; one-to-one, ties to the highest containment, then the older id, then the smaller id. Limits: a merge keeps only one id (the other development is reported as merged); without prev the id is still the hash of the sorted member article ids", "forward_statement_speaker": "PARTIAL (speaker from claims v1 attrs.speaker, else the X-said subject written in the sentence; pronouns left unnamed)", "attributed_cause": "MISSING (a cause is shown only as a written sentence, speaker not read)",
                      "moved_proxy": "moved = after the cut: a new assertion with 2+ owners, a new contradiction, an assertion that gained its second owner, or a changed certainty word. It is not importance.", "relevance": "not built (optional focus entity)"}}
    if carry is not None: res["carry"] = carry
    return res

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(2)
    cut = int(a[a.index("--cut") + 1]) if "--cut" in a else None
    r = build(a[0], a[1] if len(a) > 1 and not a[1].startswith("--") else None, cut)
    if "--json" in a: print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(json.dumps({k: v for k, v in r.items() if k not in ("developments", "thin", "cut", "notes")}, ensure_ascii=False))
        for d in (r.get("developments") or []) + (r.get("thin") or []):
            print(d["id"], "art", d["articles"], "own", d["owners"], d["certainty_word"], "|", d["moved"], "|", "THIN" if d["thin"] else "", d["title"][:80])
