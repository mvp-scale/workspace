"""educate: G6 educate v0 (lean wave 0, L2868; playbook 00 section 10 and the G6 row of section 2). Template answers over stored edges. No model, no hosted call, no generated free text, CPU only, read-only on every input.
    python3 educate.py "<question>" [--consolidated <consolidated.json>] [--state <resource state json>] [--seed <resources.csv>] [--trace <trace folder>] [--ticks <ticks.jsonl>] [--json]
Inputs: the consolidate.py output (edges with fragments, publishers, strength; if --consolidated is not given it is computed in memory from the G4 stores, the trace and the tick log, exactly as consolidate.py does) and the resource state of ledger_split.py --state (V, dV, N, C, U per resource, country, day; optional).
Answer (playbook 00 section 10): what it is / what is changing / why / known / uncertain / adjacent. Each section is a list of statements. A statement is one template (TEMPLATES, the only place text lives) filled with slots taken from the stored data, plus its pointers:
  refs        : fragment pointers {art, sent (sentence id, or null for a resource tick, which has no sentence), span, pub, day, src}; at most MAX_REFS are listed, refs_total says how many support the statement
  publishers_n: independent publishers (edge strength) for a statement about one edge, otherwise the number of distinct publisher names over the cited fragments (publishers_basis says which)
  weights     : every fragment counts 1.0, equal. PROVISIONAL: the weighting is an owner decision (T178, pending). No weighted score is computed; ranking is by independent publishers, then fragments, then id.
A question that matches nothing gets one templated abstain line and no statements. The one statement kind that is not a count over fragments, the seed definition of a resource, points at its seed-file row (kind seed-row) and says PROVISIONAL (resources.csv, status guess).
Question resolution is deterministic string matching: a resource id or seed name, an upper-case ISO country code (or iso:XX / country:XX), an entity label or a capability label (longest match; capabilities come from concepts.capabilities of the consolidated body: Domain > Area > Capability, PROVISIONAL, nothing promoted). Country names are not mapped (no stored name table)."""
import os, sys, re, json, glob, csv, hashlib, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(os.path.dirname(HERE)); SEED = "/workspace/probes/persona/rules_v2/resources.csv"
VERSION = "educate-v0"; MAX_REFS = 12; TOPN = 5
WEIGHTS = "equal (every fragment 1.0), PROVISIONAL, owner decision T178 pending"
SECTIONS = ["what_it_is", "what_is_changing", "why", "known", "uncertain", "adjacent"]
TITLES = {"what_it_is": "What it is", "what_is_changing": "What is changing", "why": "Why it matters", "known": "What is known", "uncertain": "What remains uncertain", "adjacent": "Adjacent"}
# The only text this module can emit. Slots are filled from stored data only.
TEMPLATES = {
    "is.edges": "{label}: {edges} stored edges, {frags} fragments over {arts} source items, {pubs} distinct publishers, {days} dated days ({first} to {last}).",
    "is.seed": "Seed definition of resource {name} (group {group}): {definition} [seed list {source}, status {status}, PROVISIONAL]",
    "chg.state": "{resource} in {country} on {day}: V={V} items from {publishers} publishers, baseline {baseline_V}, dV={dV}, N={N}, C={C}, U={U}.",
    "chg.window": "{label}: first fragment dated {first}, latest {last}, {windows} {window_days}-day windows with evidence.",
    "chg.none": "{label}: no state row with a change against baseline (dV not 0) and no dated fragment span of more than one day among the stored edges.",
    "why.assert": "{subj} {pred} {obj}: stated in {stories} stories by {strength} independent publishers. Source sentence: {sent}",
    "why.direction": "{label}: {up} stated rises and {down} stated falls among {rows} resource-state rows ({items} items).",
    "why.resource_edge": "{resource} attention in {country}: {stories} stories, {strength} independent publishers, days {first} to {last}.",
    "known.edge": "{key}: supported by {strength} independent publishers ({names}) over {stories} stories.",
    "known.none": "None of the {edges} stored edges for {label} has two or more independent publishers.",
    "unc.single": "{single} of {edges} stored edges for {label} rest on one independent publisher.",
    "unc.polarity": "{k} of {edges} stored edges for {label} carry both positive and negative fragments (assertion edges only).",
    "unc.undated": "{k} of {frags} fragments for {label} have no day recorded.",
    "unc.fresh": "{label}: latest state day {latest}; {fresh} of {rows} state rows are at most 1 day old, {stale} are 7 days or older; {conflict} rows have C above 0, {unresolved} have U above 0.",
    "unc.nostate": "{label}: no resource-state rows were supplied or matched, so V, dV, N, C, U and freshness are not stated.",
    "adj.item": "{rank}. {label} ({kind}): {edges} edges, {frags} fragments, {pubs} distinct publishers.",
    "adj.none": "{label}: no neighbouring item in the stored edges.",
    "label.pair": "{resource} in {country}",
    "abstain": "No stored edge matches the question {question}.",
    "is.capability": "{label}: capability {id} ({kind} in the verb-object list), seen in {articles} source items from {pubs} distinct publishers over {stories} stories; {edges} stored assertion edges link to it. PROVISIONAL, not promoted.",
    "cap.where": "{label}: sits under areas {areas} and domains {domains} as named by the chain's own roll-up (association by co-occurrence in an article, not an is_a link).",
    "cap.once": "{label}: dated at most one day among its source items.",
    "cap.unvalidated": "{label}: listed by a fixed verb-object list (t230, t222), not learned or validated; status PROVISIONAL, there is no promote step.",
}
SUFFIX = " [refs {refs_total}; {publishers_n} {basis}; weights equal PROVISIONAL (T178)]"
def render(tpl, slots): return TEMPLATES[tpl].format(**slots)
def canon(o): return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
def sid(sent): return hashlib.sha1(sent.encode()).hexdigest()[:10] if sent else None
def lab(x): return "-" if x is None else str(x).split(":", 1)[-1]
def kind_of(x): return "unknown" if x is None else str(x).split(":", 1)[0]
# ---------- data ----------
def load_seed(path):
    if not path or not os.path.exists(path): return {}
    return {r["id"]: r for r in csv.DictReader(open(path, encoding="utf-8"))}
def build_body(a):
    """the consolidated body: read from --consolidated, else computed in memory (consolidate.py logic, nothing written)"""
    opt = lambda f: a[a.index(f) + 1] if f in a else None
    if opt("--consolidated"): return json.load(open(opt("--consolidated")))
    import consolidate as C
    items = []; tr = opt("--trace")
    if tr: items += C.load_trace(tr)
    jr = os.path.join(ROOT, "runs", "journal", "journal.jsonl"); items += C.load_journal(jr)
    g4 = [os.path.join(ROOT, "runs", "g4", "store.jsonl")] + sorted(glob.glob(os.path.join(ROOT, "runs", "g4", "archive", "store.jsonl-*")))
    tk = opt("--ticks") or os.path.join(ROOT, "runs", "ledger", "ticks.jsonl")
    return C.seal(C.consolidate(items, [C.load_g4(p) for p in g4 if os.path.exists(p)], C.load_ticks(tk)))
class Index:
    def __init__(self, body, state=None, seed=None):
        self.body = body; self.state = state or {}; self.seed = seed or {}; self.edges = body["edges"]
        self.caps = {n["id"]: n for n in ((body.get("concepts") or {}).get("capabilities") or body.get("capabilities") or {}).get("nodes", [])}   # Domain > Area > Capability nodes (PROVISIONAL), by id
        self.res = sorted({e["subj"][9:] for e in self.edges if e["kind"] == "resource"} | set(self.seed))
        self.countries = sorted({e["obj"][8:] for e in self.edges if e["kind"] == "resource"} | {x[4:] for e in self.edges if e["kind"] == "assertion" for x in (e["subj"], e["obj"]) if x and x.startswith("iso:")})
        self.labels = {}   # entity key (type:label) -> label, assertion ends only
        for e in self.edges:
            if e["kind"] != "assertion": continue
            for x in (e["subj"], e["obj"]):
                if x and not x.startswith("iso:"): self.labels[x] = lab(x)
    def resolve(self, q):
        """question -> {"kind", "label", "resource", "country", "entity"} or None"""
        ql = q.lower(); res = None
        for r in self.res:
            names = {r, r.replace("_", " ")} | ({self.seed[r]["name"].lower()} if r in self.seed else set())
            if "resource:" + r in ql or any(re.search(r"(?<![a-z0-9_])" + re.escape(n) + r"(?![a-z0-9_])", ql) for n in names): res = r; break
        ctry = None
        m = re.search(r"\b(?:country|iso):([A-Za-z]{2}|WORLD)\b", q)
        if m: ctry = m.group(1).upper()
        else:
            for t in re.findall(r"\b[A-Z]{2}\b|\bWORLD\b", q):
                if t in self.countries: ctry = t; break
        if res and ctry: return {"kind": "resource-country", "label": render("label.pair", {"resource": res, "country": ctry}), "resource": res, "country": ctry}
        if res: return {"kind": "resource", "label": res, "resource": res}
        if ctry: return {"kind": "country", "label": ctry, "country": ctry}
        best = None
        for k, l in sorted(self.labels.items()):
            if len(l) < 3: continue
            if k.lower() in ql or re.search(r"(?<![a-z0-9])" + re.escape(l) + r"(?![a-z0-9])", ql):
                if best is None or len(l) > len(best[1]): best = (k, l)
        cbest = None
        for i, n in sorted(self.caps.items()):
            if re.search(r"(?<![a-z0-9])" + re.escape(n["label"].lower()) + r"(?![a-z0-9])", ql) and (cbest is None or len(n["label"]) > len(cbest["label"])): cbest = n
        if cbest and (best is None or len(cbest["label"]) > len(best[1])): return {"kind": "capability", "label": cbest["label"], "capability": cbest["id"]}
        if best: return {"kind": "entity", "label": best[1], "entity": best[0]}
        return None
    def select(self, t):
        E = self.edges
        if t["kind"] == "resource-country": return [e for e in E if e["kind"] == "resource" and e["subj"] == "resource:" + t["resource"] and e["obj"] == "country:" + t["country"]]
        if t["kind"] == "resource": return [e for e in E if e["kind"] == "resource" and e["subj"] == "resource:" + t["resource"]]
        if t["kind"] == "country": return [e for e in E if (e["kind"] == "resource" and e["obj"] == "country:" + t["country"]) or (e["kind"] == "assertion" and "iso:" + t["country"] in (e["subj"], e["obj"]))]
        if t["kind"] == "capability": return [e for e in E if e["kind"] == "assertion" and t["capability"] in (e.get("capabilities") or [])]
        return [e for e in E if e["kind"] == "assertion" and t["entity"] in (e["subj"], e["obj"])]
    def states(self, t):
        S = self.state.get("states") or []
        return [s for s in S if (not t.get("resource") or s["resource"] == t["resource"]) and (not t.get("country") or s["country"] == t["country"])] if t["kind"] != "entity" else []
# ---------- statements ----------
def ref(f): return {"art": f["art"], "sent": sid(f.get("sent")), "span": (f.get("spans") or [None])[0], "pub": f.get("pub"), "day": f.get("day"), "src": os.path.basename(f.get("source") or "")}
def stm(sec, tpl, slots, frags, indep=None, extra=None):
    """one statement: the template rendered from slots, plus pointers. frags: the fragments that support it (>= 1)"""
    uniq = {}; [uniq.setdefault((f["art"], f.get("sent") or "", f.get("pub")), f) for f in frags]; fr = [uniq[k] for k in sorted(uniq, key=lambda k: (str(k[0]), k[1], str(k[2])))]
    pubs = sorted({f["pub"] for f in fr if f.get("pub")}); n = indep if indep is not None else len(pubs); basis = ("publishers (seed row, none)" if extra == "seed-row" else "independent publishers") if indep is not None else "distinct publishers"
    s = {"section": sec, "tpl": tpl, "slots": slots, "refs": [ref(f) for f in fr[:MAX_REFS]], "refs_total": len(fr), "publishers_n": n, "publishers_basis": basis, "publisher_names": pubs[:MAX_REFS], "weights": WEIGHTS}
    s["text"] = render(tpl, slots) + SUFFIX.format(refs_total=len(fr), publishers_n=n, basis=basis)
    if extra: s["pointer_kind"] = extra
    return s
def frags_of(edges): return [f for e in edges for f in e["fragments"]]
def ekey(e): return (-e["strength"], -e["fragments_n"], e["id"])
def sfrags(rows):
    out = []
    for s in rows:
        for ev in s.get("evidence") or []: out.append({"art": ev["id"], "sent": None, "spans": [ev["span"]] if ev.get("span") else [], "pub": ev.get("publisher"), "day": s["day"], "source": "resource-state"})
    return out
def capability_answer(IX, t, q):
    """a question that names a capability: the node (Domain > Area > Capability, PROVISIONAL) and the stored assertion edges linked to it; same sections, same templates, same pointers"""
    n = IX.caps[t["capability"]]; E = IX.select(t); sec = {s: [] for s in SECTIONS}; label = n["label"]
    F = [{"art": a, "sent": None, "spans": [], "pub": p, "day": d, "source": "capability_list"} for a, p, d in n.get("items", [])]
    sec["what_it_is"].append(stm("what_it_is", "is.capability", {"label": label, "id": n["id"], "kind": n["kind"], "articles": n["articles"], "pubs": len(n["publishers"]), "stories": n["stories"], "edges": len(E)}, F, indep=n["strength"]))
    sec["what_it_is"].append(stm("what_it_is", "cap.where", {"label": label, "areas": ", ".join(n["areas"]) or "-", "domains": ", ".join(n["domains"]) or "-"}, F))
    days = sorted({f["day"] for f in F if f["day"]})
    sec["what_is_changing"].append(stm("what_is_changing", "chg.window", {"label": label, "first": days[0], "last": days[-1], "windows": len({__import__("datetime").date.fromisoformat(d[:10]).toordinal() // 7 for d in days}), "window_days": 7}, F) if len(days) > 1 else stm("what_is_changing", "cap.once", {"label": label}, F))
    for e in sorted(E, key=ekey)[:3]: sec["why"].append(stm("why", "why.assert", {"subj": lab(e["subj"]), "pred": e["pred"], "obj": lab(e["obj"]), "stories": e["stories"], "strength": e["strength"], "sent": (e["fragments"][0].get("sent") or "")[:240]}, e["fragments"], indep=e["strength"]))
    multi = sorted([e for e in E if e["strength"] >= 2], key=ekey)[:TOPN]
    for e in multi: sec["known"].append(stm("known", "known.edge", {"key": e["key"], "strength": e["strength"], "names": ", ".join(e["publishers"][:4]) + ("" if len(e["publishers"]) <= 4 else ", +%d" % (len(e["publishers"]) - 4)), "stories": e["stories"]}, e["fragments"], indep=e["strength"]))
    if not multi: sec["known"].append(stm("known", "known.none", {"edges": len(E), "label": label}, frags_of(E) or F))
    if E: sec["uncertain"].append(stm("uncertain", "unc.single", {"single": sum(e["strength"] <= 1 for e in E), "edges": len(E), "label": label}, frags_of([e for e in E if e["strength"] <= 1]) or frags_of(E)))
    sec["uncertain"].append(stm("uncertain", "cap.unvalidated", {"label": label}, F))
    sib = sorted([m for i, m in IX.caps.items() if i != n["id"] and set(m["areas"]) & set(n["areas"])], key=lambda m: (-m["articles"], m["id"]))[:TOPN]
    for k, m in enumerate(sib, 1): sec["adjacent"].append(stm("adjacent", "adj.item", {"rank": k, "label": m["label"], "kind": "capability", "edges": m["edges"], "frags": m["articles"], "pubs": len(m["publishers"])}, [{"art": a, "sent": None, "spans": [], "pub": p, "day": d, "source": "capability_list"} for a, p, d in m.get("items", [])]))
    if not sib: sec["adjacent"].append(stm("adjacent", "adj.none", {"label": label}, F))
    return {"version": VERSION, "question": q, "resolved": t, "weights": WEIGHTS, "sections": sec, "statements": sum(len(v) for v in sec.values()), "source": {"consolidated_sha256": IX.body.get("sha256"), "state_sha256": IX.state.get("sha256"), "seed": None}}
def answer(IX, q):
    t = IX.resolve(q)
    if not t: return {"version": VERSION, "question": q, "resolved": None, "weights": WEIGHTS, "sections": {s: [] for s in SECTIONS}, "abstain": render("abstain", {"question": json.dumps(q)}), "statements": 0}
    if t["kind"] == "capability": return capability_answer(IX, t, q)
    E = IX.select(t); S = IX.states(t); label = t["label"]; F = frags_of(E); sec = {s: [] for s in SECTIONS}
    if not E: return {"version": VERSION, "question": q, "resolved": t, "weights": WEIGHTS, "sections": sec, "abstain": render("abstain", {"question": json.dumps(q)}), "statements": 0}
    days = sorted({f["day"] for f in F if f["day"]}); wins = sorted({(__import__("datetime").date.fromisoformat(d[:10]).toordinal() // 7) for d in days})
    sec["what_it_is"].append(stm("what_it_is", "is.edges", {"label": label, "edges": len(E), "frags": len(F), "arts": len({f["art"] for f in F}), "pubs": len({f["pub"] for f in F}), "days": len(days), "first": days[0] if days else "-", "last": days[-1] if days else "-"}, F))
    if t.get("resource") in IX.seed and t["kind"] != "country":
        r = IX.seed[t["resource"]]; sec["what_it_is"].append(stm("what_it_is", "is.seed", {"name": r["name"], "group": r["group"], "definition": r["definition"], "source": r["source"], "status": r["status"]}, [{"art": "seed:" + r["id"], "sent": None, "spans": [], "pub": None, "day": None, "source": os.path.basename(SEED)}], indep=0, extra="seed-row"))
    # what is changing
    mv = sorted([s for s in S if s.get("dV")], key=lambda s: (s["day"], abs(s["dV"]), s["resource"], s["country"]), reverse=True)[:3]
    for s in mv:
        if s.get("evidence"): sec["what_is_changing"].append(stm("what_is_changing", "chg.state", {k: s[k] for k in ("resource", "country", "day", "V", "publishers", "baseline_V", "dV", "N", "C", "U")}, sfrags([s])))
    if len(days) > 1: sec["what_is_changing"].append(stm("what_is_changing", "chg.window", {"label": label, "first": days[0], "last": days[-1], "windows": len(wins), "window_days": 7}, F))
    if not sec["what_is_changing"]: sec["what_is_changing"].append(stm("what_is_changing", "chg.none", {"label": label}, F))
    # why
    if t["kind"] == "entity":
        for e in sorted(E, key=ekey)[:3]: sec["why"].append(stm("why", "why.assert", {"subj": lab(e["subj"]), "pred": e["pred"], "obj": lab(e["obj"]), "stories": e["stories"], "strength": e["strength"], "sent": (e["fragments"][0].get("sent") or "")[:240]}, e["fragments"], indep=e["strength"]))
    else:
        if S:
            up = sum(s["up_n"] for s in S); dn = sum(s["down_n"] for s in S); sec["why"].append(stm("why", "why.direction", {"label": label, "up": up, "down": dn, "rows": len(S), "items": sum(s["items"] for s in S)}, sfrags(S)))
        for e in sorted([e for e in E if e["kind"] == "resource"], key=ekey)[:3]: sec["why"].append(stm("why", "why.resource_edge", {"resource": lab(e["subj"]), "country": lab(e["obj"]), "stories": e["stories"], "strength": e["strength"], "first": e["days"][0] if e["days"] else "-", "last": e["days"][-1] if e["days"] else "-"}, e["fragments"], indep=e["strength"]))
        for e in sorted([e for e in E if e["kind"] == "assertion"], key=ekey)[:3]: sec["why"].append(stm("why", "why.assert", {"subj": lab(e["subj"]), "pred": e["pred"], "obj": lab(e["obj"]), "stories": e["stories"], "strength": e["strength"], "sent": (e["fragments"][0].get("sent") or "")[:240]}, e["fragments"], indep=e["strength"]))
    # known
    multi = sorted([e for e in E if e["strength"] >= 2], key=ekey)[:TOPN]
    for e in multi: sec["known"].append(stm("known", "known.edge", {"key": e["key"], "strength": e["strength"], "names": ", ".join(e["publishers"][:4]) + ("" if len(e["publishers"]) <= 4 else ", +%d" % (len(e["publishers"]) - 4)), "stories": e["stories"]}, e["fragments"], indep=e["strength"]))
    if not multi: sec["known"].append(stm("known", "known.none", {"edges": len(E), "label": label}, F))
    # uncertain
    sec["uncertain"].append(stm("uncertain", "unc.single", {"single": sum(e["strength"] <= 1 for e in E), "edges": len(E), "label": label}, frags_of([e for e in E if e["strength"] <= 1]) or F))
    A = [e for e in E if e["kind"] == "assertion"]
    if A:
        both = [e for e in A if len({f["polarity"] for f in e["fragments"] if f["polarity"]}) > 1]; sec["uncertain"].append(stm("uncertain", "unc.polarity", {"k": len(both), "edges": len(A), "label": label}, frags_of(both) or frags_of(A)))
    und = [f for f in F if not f["day"]]; sec["uncertain"].append(stm("uncertain", "unc.undated", {"k": len(und), "frags": len(F), "label": label}, und or F))
    if S:
        latest = max(s["day"] for s in S); sec["uncertain"].append(stm("uncertain", "unc.fresh", {"label": label, "latest": latest, "fresh": sum(s["freshness_days"] <= 1 for s in S), "rows": len(S), "stale": sum(s["freshness_days"] >= 7 for s in S), "conflict": sum(s["C"] > 0 for s in S), "unresolved": sum(s["U"] > 0 for s in S)}, sfrags(S)))
    elif t["kind"] != "entity": sec["uncertain"].append(stm("uncertain", "unc.nostate", {"label": label}, F))
    # adjacent
    nb = collections.defaultdict(list)
    for e in E:
        if e["kind"] == "resource": other = ("country", lab(e["obj"])) if t["kind"] in ("resource", "resource-country") else ("resource", lab(e["subj"]))
        else:
            ends = [x for x in (e["subj"], e["obj"]) if x]; me = {"entity": t.get("entity"), "country": "iso:" + t.get("country", "")}.get(t["kind"])
            oth = [x for x in ends if x != me]; other = (kind_of(oth[0]), lab(oth[0])) if oth else None
            if t["kind"] == "resource": other = None
        if other: nb[other].append(e)
    rk = sorted(nb.items(), key=lambda kv: (-len({p for e in kv[1] for p in e["publishers"]}), -sum(e["fragments_n"] for e in kv[1]), kv[0]))[:TOPN]
    for i, ((k, l), es) in enumerate(rk, 1): sec["adjacent"].append(stm("adjacent", "adj.item", {"rank": i, "label": l, "kind": k, "edges": len(es), "frags": sum(e["fragments_n"] for e in es), "pubs": len({f["pub"] for f in frags_of(es)})}, frags_of(es)))
    if not rk: sec["adjacent"].append(stm("adjacent", "adj.none", {"label": label}, F))
    return {"version": VERSION, "question": q, "resolved": t, "weights": WEIGHTS, "sections": sec, "statements": sum(len(v) for v in sec.values()), "source": {"consolidated_sha256": IX.body.get("sha256"), "state_sha256": IX.state.get("sha256"), "seed": os.path.basename(SEED) if IX.seed else None}}
def as_text(ans):
    if ans.get("abstain"): return ans["abstain"]
    out = ["Q: " + ans["question"], "Resolved: %s (%s) | weights: %s" % (ans["resolved"]["label"], ans["resolved"]["kind"], ans["weights"])]
    for s in SECTIONS:
        out.append("\n" + TITLES[s])
        out += ["- " + st["text"] for st in ans["sections"][s]]
    return "\n".join(out)
def main(a):
    if not a or a[0].startswith("--"): print(__doc__); return
    opt = lambda f: a[a.index(f) + 1] if f in a else None
    state = json.load(open(opt("--state"))) if opt("--state") else {}
    IX = Index(build_body(a), state, load_seed(opt("--seed") or SEED)); ans = answer(IX, a[0])
    print(json.dumps(ans, sort_keys=True, ensure_ascii=False, indent=1) if "--json" in a else as_text(ans))
if __name__ == "__main__": main(sys.argv[1:])
