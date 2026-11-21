"""resource_truth: T174(c), outside truth for the resource state (owner yes L2870, plan L2869/L2868). Two checks against saved public snapshots; no network here (the fetches are current-events-fetch.py and wikidata_cache.py).
(1) EVENT PEAK. Truth = Wikipedia Portal:Current_events (CC BY-SA 4.0), one snapshot per calendar day in /workspace/data/anchors/current_events/. An event = a bullet that has a source link (header bullets are topic labels, not events). It is mapped to a resource by the keyword table KEYMAP below
    (resource ids and conditions from specs/iptc_condition_v0.json, read-only; the words are ours, PROVISIONAL, a guess). Unit = (event day, resource) with >= 1 mapped event: many war bullets on one day are one unit, not many.
    Checkable = the day has >= MIN_ITEMS independent traced items. Peak = the day (among days with >= MIN_ITEMS items) on which the resource has its highest share of the day's attention mass (mass summed over countries; the resource state of ledger_split.py --state, v1 rules, unchanged).
    Hit = peak within +/- 1 calendar day of the event day. Bar (pre-registered in ledger L2880) = >= 80 percent of checkable units hit (4 of 5). Reported, not used for the verdict: peak on raw mass, a local-spike reading (the event day or a neighbour is the resource's maximum share within +/- 3 days), and chance (the share of checkable days within +/- 1 of the peak, averaged over the units).
(2) IDENTITY. Truth = Wikidata (CC0) through wikidata_cache.py. G4 merges several surface forms into one entity (alias list). For every entity in the cache plan with >= 1 alias differing from the canon: canon and each alias surface are resolved to the top wbsearchentities hit; a pair is RESOLVED when both resolve; CONFLICT when the QIDs differ. Bar = 0 conflicts on the resolved pairs. Unresolved pairs are counted and not scored. Reported by entity type: the place entity is a country roll-up by design (city and demonym surfaces join their country), so its conflicts say 'rolled up, not the same Wikidata item', the other types are plain same-entity claims.
    python3 resource_truth.py --snapshot [--trace <folder>]   (builds the resource-state snapshot with ledger_split.py; CPU; writes /workspace/data/anchors/truth/resource-state-snapshot.json)
    python3 resource_truth.py [--json <out>]                   (scores from the snapshots only)"""
import sys, os, re, json, glob, hashlib, subprocess, tempfile, collections, datetime
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
TRUTH = "/workspace/data/anchors/truth"; EVENTS = "/workspace/data/anchors/current_events"; SNAP = TRUTH + "/resource-state-snapshot.json"
TRACE = "/workspace/demo/mockups/structure-live/runs-v7/trace"; PYNP = "/workspace/models/embed-zs/.venv/bin/python"; SPEC = H + "/specs/iptc_condition_v0.json"
MIN_ITEMS = 20; BAR_EVENT = 0.8; BAR_IDENTITY = 0
KEYMAP = {   # resource id -> words (regex, word-start, case-insensitive). PROVISIONAL: ours, a guess, 'attention' (news_overload) has no event words.
    "water": r"drought|water shortage|water supply|reservoir|water crisis", "land_soil": r"desertification|soil|erosion|farmland|land degradation",
    "biodiversity": r"wildlife|endangered|extinct|biodiversity|deforestation|coral|species|poach", "atmosphere_climate": r"climate|emission|greenhouse|air pollution|smog|heatwave|carbon|cop\d\d",
    "primary_energy": r"\boil\b|crude|opec|petrol|fuel|refiner|natural gas|\blng\b|solar|wind farm|nuclear power|electricity|power plant|pipeline|energy",
    "minerals_materials": r"lithium|rare earth|copper|\bmining\b|\bmine\b|mineral|cobalt|nickel", "food_stock": r"famine|hunger|food|harvest|\bcrop|wheat|grain|malnutrition",
    "built_infrastructure": r"bridge|railway|\brail\b|airport|blackout|power outage|infrastructure|collaps|\bdam\b|derail|highway|\bport\b", "housing_stock": r"housing|\brent\b|mortgage|homeless|real estate|property market",
    "productive_capital": r"factory|manufactur|industrial|steel|carmaker|assembly plant", "computing_capacity": r"cyber|hack|ransomware|internet|\bai\b|artificial intelligence|data cent|software|semiconductor|\bchip|outage|telecom",
    "supply_networks": r"tariff|trade|shipping|supply chain|export|import|sanction|embargo|blockade", "monetary_credit": r"interest rate|central bank|inflation|\bbank\b|\bloan|credit|currency|\bfed\b|rate cut|rate hike",
    "asset_wealth": r"stock market|stocks|shares|billionaire|bitcoin|crypto|\bipo\b|wall street|\bindex\b|market crash|valuation", "public_finances": r"budget|deficit|national debt|\btax|government spending|shutdown|bond yield|bailout",
    "population": r"migrant|refugee|migration|asylum|immigra|deport|displaced", "population_health": r"outbreak|disease|virus|vaccin|cholera|epidemic|pandemic|measles|\bflu\b|mental health|ebola|infection",
    "care_capacity": r"hospital|nurse|healthcare|health care|ambulance|doctors|clinic", "skills": r"school|universit|student|education|teacher|\bcollege",
    "labour_force": r"strike action|\bstrikes?\b|unemploy|\bunion|workers|layoff|wages|\bjobs?\b|employment|walkout", "social_trust": r"discriminat|racis|polariz|xenophob|hate crime|antisemit|islamophob",
    "community_ties": r"volunteer|charity|solidarity|vigil|community", "legitimacy": r"election|\bvote|referendum|parliament|constitution|corruption|\bcoup\b|impeach|resign|prime minister|president|opposition|supreme court",
    "state_capacity": r"\bwar\b|attack|\bkilled\b|shooting|terror|police|protest|\briot|crime|military|airstrike|missile|drone|arrest|ceasefire|explosion|bomb|gunmen|\bkills?\b",
    "knowledge": r"disinformation|misinformation|fake news|research|scientists|\bstudy\b|journal|fact-check|propaganda|censorship"}
RX = {r: re.compile(w, re.I) for r, w in KEYMAP.items()}
def build_snapshot(trace=TRACE, out=SNAP):
    """ledger_split --state --persist on the trace folder (CPU), then (resource, day) mass and items and the independent items per day; the snapshot is what the tests read"""
    d = tempfile.mkdtemp(prefix="resource-truth-"); r = subprocess.run([PYNP if os.path.exists(PYNP) else sys.executable, H + "/ledger_split.py", trace, "--state", d + "/state.json", "--persist", d + "/ticks.jsonl", "--state-only"], capture_output=True, text=True, cwd=H)
    if r.returncode: raise SystemExit("ledger_split failed: " + r.stderr[-500:])
    state = json.load(open(d + "/state.json")); rd = collections.defaultdict(lambda: collections.defaultdict(lambda: {"items": 0, "mass": 0.0})); ind = collections.Counter(); allday = collections.Counter()
    for ln in open(d + "/ticks.jsonl"):
        t = json.loads(ln); allday[t["day"]] += 1
        if not t["ind"]: continue
        ind[t["day"]] += 1
        for e in t["events"]: c = rd[e[0]][t["day"]]; c["items"] += 1; c["mass"] += e[1] + e[2] + e[3]
    snap = {"version": "resource-truth-snapshot-v1", "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "trace": trace, "chain_sha256": hashlib.sha256(open(trace + "/chain.jsonl", "rb").read()).hexdigest(), "state_sha256": state["sha256"], "state_version": state["version"], "seed_status": "PROVISIONAL (seed resources.csv, guess)",
            "traced_items_per_day": dict(sorted(allday.items())), "independent_items_per_day": dict(sorted(ind.items())), "resource_day": {r_: {d_: {"items": v["items"], "mass": round(v["mass"], 6)} for d_, v in sorted(x.items())} for r_, x in sorted(rd.items())}}
    os.makedirs(os.path.dirname(out), exist_ok=True); json.dump(snap, open(out, "w"), indent=1); return snap
def day_add(d, n): return (datetime.date.fromisoformat(d) + datetime.timedelta(days=n)).isoformat()
def days_apart(a, b): return abs((datetime.date.fromisoformat(a) - datetime.date.fromisoformat(b)).days)
def load_events(events_dir=EVENTS):
    out = []
    for f in sorted(glob.glob(events_dir + "/????-??-??.json")):
        d = json.load(open(f, encoding="utf-8"))
        for b in d["bullets"]:
            if b["sources"]: out.append({"date": d["date"], "category": b["category"], "text": b["text"], "parent": b["parent"]})
    return out
def map_events(events):
    """unit (date, resource) -> the mapped events; an event may reach several resources"""
    u = collections.defaultdict(list)
    for e in events:
        s = (e["parent"] or "") + " " + e["text"]
        for r, rx in RX.items():
            if rx.search(s): u[(e["date"], r)].append(e["text"][:140])
    return u
def peaks(snap, key):
    ok = sorted(d for d, n in snap["independent_items_per_day"].items() if n >= MIN_ITEMS); tot = collections.Counter()
    for r, x in snap["resource_day"].items():
        for d in ok:
            if d in x: tot[d] += x[d]["mass"]
    ser = {}
    for r, x in snap["resource_day"].items():
        ser[r] = {d: ((x[d]["mass"] / tot[d] if tot[d] else 0.0) if key == "share" else x[d]["mass"]) if d in x else 0.0 for d in ok}
    return ok, ser
def score_events(snap, events):
    units = map_events(events); ok, shr = peaks(snap, "share"); _, raw = peaks(snap, "mass"); okset = set(ok); rows = []
    for (d, r), ev in sorted(units.items()):
        if d not in okset or r not in shr: rows.append({"date": d, "resource": r, "n_events": len(ev), "checkable": False, "why": "day under %d items" % MIN_ITEMS if d not in okset else "resource has no state"}); continue
        pk = max(ok, key=lambda x: (shr[r][x], x)); pr = max(ok, key=lambda x: (raw[r][x], x)); w = [x for x in ok if days_apart(x, d) <= 3]; spike = max(w, key=lambda x: (shr[r][x], x)); chance = sum(1 for x in ok if days_apart(x, pk) <= 1) / len(ok)
        rows.append({"date": d, "resource": r, "n_events": len(ev), "example": ev[0], "checkable": True, "peak_share_day": pk, "hit": days_apart(pk, d) <= 1, "peak_raw_day": pr, "hit_raw": days_apart(pr, d) <= 1, "local_spike": days_apart(spike, d) <= 1, "chance": round(chance, 4)})
    c = [x for x in rows if x["checkable"]]; n = len(c); h = sum(x["hit"] for x in c)
    return {"checkable_days": ok, "units_mapped": len(rows), "checkable": n, "hits": h, "hit_rate": round(h / n, 4) if n else None, "bar": BAR_EVENT, "pass": bool(n) and h / n >= BAR_EVENT,
            "secondary": {"hits_raw_mass_peak": sum(x["hit_raw"] for x in c), "hits_local_spike": sum(x["local_spike"] for x in c), "chance_rate": round(sum(x["chance"] for x in c) / n, 4) if n else None}, "units": rows,
            "events_total": len(events), "events_mapped": sum(1 for e in events if any(rx.search((e["parent"] or "") + " " + e["text"]) for rx in RX.values()))}
def score_identity(plan=None):
    import wikidata_cache as W
    P = plan or W.load_plan(); res = []; unresolved = 0; confl = []
    for eid, ty, canon, surf in P["merges"]:
        rc = W.resolve(canon)
        for s in surf:
            rs = W.resolve(s)
            if not rc or not rs: unresolved += 1; continue
            res.append({"entity": eid, "type": ty, "canon": canon, "alias": s, "canon_qid": rc["qid"], "alias_qid": rs["qid"], "same": rc["qid"] == rs["qid"], "canon_label": rc["label"], "alias_label": rs["label"]})
    bad = [x for x in res if not x["same"]]; names = P["names"]; cached = [n for n in names if W.lookup(n)]
    return {"names_planned": len(names), "names_cached": len(cached), "names_with_hit": sum(1 for n in names if W.resolve(n)), "pairs_total": len(res) + unresolved, "pairs_resolved": len(res), "pairs_unresolved": unresolved, "conflicts": len(bad), "conflict_rate": round(len(bad) / len(res), 4) if res else None, "by_alias_words": {k: {"resolved": sum(1 for x in res if (len(x["alias"].split()) > 1) == m), "conflicts": sum(1 for x in bad if (len(x["alias"].split()) > 1) == m)} for k, m in (("one_word", False), ("two_or_more_words", True))}, "by_type": {t: {"resolved": sum(1 for x in res if x["type"] == t), "conflicts": sum(1 for x in bad if x["type"] == t)} for t in sorted({x["type"] for x in res})}, "bar": BAR_IDENTITY, "pass": bool(res) and len(bad) <= BAR_IDENTITY, "conflict_pairs": bad}
def main():
    opt = lambda f: sys.argv[sys.argv.index(f) + 1] if f in sys.argv else None
    if "--snapshot" in sys.argv: s = build_snapshot(opt("--trace") or TRACE); print("snapshot", SNAP, "days", len(s["independent_items_per_day"]), "resources", len(s["resource_day"])); return
    snap = json.load(open(SNAP)); out = {"event_peak": score_events(snap, load_events()), "identity": score_identity(), "snapshot": {"file": SNAP, "state_sha256": snap["state_sha256"], "chain_sha256": snap["chain_sha256"]}}
    p = opt("--json") or TRUTH + "/resource-truth-v7.json"; os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(out, open(p, "w"), indent=1, ensure_ascii=False)
    e = out["event_peak"]; i = out["identity"]
    print("EVENT PEAK: events %d (mapped %d), units mapped %d, checkable %d, hits %d, rate %s, bar %.2f -> %s" % (e["events_total"], e["events_mapped"], e["units_mapped"], e["checkable"], e["hits"], e["hit_rate"], e["bar"], "PASS" if e["pass"] else "FAIL"), e["secondary"])
    print("IDENTITY: names %d cached %d with hit %d; pairs resolved %d unresolved %d conflicts %d (rate %s) bar %d -> %s" % (i["names_planned"], i["names_cached"], i["names_with_hit"], i["pairs_resolved"], i["pairs_unresolved"], i["conflicts"], i["conflict_rate"], i["bar"], "PASS" if i["pass"] else "FAIL")); print("  by alias length (resolved/conflicts):", {t: "%d/%d" % (v["resolved"], v["conflicts"]) for t, v in i["by_alias_words"].items()}); print("  by type (resolved/conflicts):", {t: "%d/%d" % (v["resolved"], v["conflicts"]) for t, v in i["by_type"].items()}); print("wrote", p)
if __name__ == "__main__": main()
