"""check-truth: structural done-check for T174 (outside-truth fetch: current-events-fetch.py, wikidata_cache.py, resource_truth.py). Reads the SAVED snapshots only: urllib and socket are blocked for the whole run, so a test that reaches the network fails.
    python3 simulation/check-truth.py
Checks (each prints PASS or FAIL): parser (synthetic wikitext), current-events snapshots (manifest sha256, licence, every traced day present, bullets), wikidata cache (manifest sha256, key = query, licence, planned-name coverage), scoring rules on synthetic data (+/-1 day, MIN_ITEMS, one unit per (day, resource), chance, identity conflict), determinism of the real scoring.
The measured bars (event peak >= 80 percent, identity conflicts = 0) are PRINTED as RESULT lines with their numbers; they do not fail this check: a bar that is missed is a finding, recorded in the ledger, not a broken tool."""
import sys, os, json, glob, hashlib, tempfile, importlib.util, socket, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); WS = os.path.join(os.path.dirname(HERE), "projects", "world-state"); sys.path.insert(0, WS)
def _no_net(*a, **k): raise RuntimeError("network blocked in check-truth")
urllib.request.urlopen = _no_net; socket.socket.connect = _no_net
bad = []
def ck(name, ok, detail=""):
    print("%s %s %s" % ("PASS" if ok else "FAIL", name, detail)); bad.extend([] if ok else [name])
def load(name, f):
    s = importlib.util.spec_from_file_location(name, os.path.join(WS, f)); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
CE = load("ce_fetch", "current-events-fetch.py"); import wikidata_cache as W, resource_truth as R
# ---------- parser ----------
wt = "{{Current events|year=2026|month=11|day=5|top=yes}}\n<!-- x -->\n'''Armed conflicts and attacks'''\n*[[Gaza war]]\n**[[A|An]] officer is killed in [[Amman]]. [https://ex.org/a (AP)] [https://ex.org/b (''Reuters'')]\n\n'''Business and economy'''\n*[[Mexico]] approves a law.[https://ex.org/c (N+ {{small|in Spanish}})]\n"
b = CE.parse_wikitext(wt)
ck("parser: categories and depth", [(x["category"], x["depth"]) for x in b] == [("Armed conflicts and attacks", 1), ("Armed conflicts and attacks", 2), ("Business and economy", 1)], str([(x["category"], x["depth"]) for x in b]))
ck("parser: header bullet has no source, event bullets do; parent kept", not b[0]["sources"] and len(b[1]["sources"]) == 2 and b[1]["parent"] == "Gaza war" and b[2]["sources"][0]["url"] == "https://ex.org/c", "")
ck("parser: link markup removed, wikilinks kept", b[1]["text"] == "An officer is killed in Amman." and b[1]["wikilinks"] == ["A", "Amman"], b[1]["text"])
ck("page name", CE.page_name("2026-11-05") == "Portal:Current_events/2026_November_5" and CE.page_name("2025-01-12") == "Portal:Current_events/2025_January_12", "")
# ---------- current-events snapshots ----------
snap = json.load(open(R.SNAP)); days = sorted(snap["independent_items_per_day"]); man = json.load(open(R.EVENTS + "/MANIFEST.json"))
ck("events: licence and attribution in the manifest", "CC BY-SA 4.0" in man["licence"] and "Wikipedia contributors" in man["attribution"] and "knowledge-pipeline-research" in man["user_agent"], man["licence"])
shaok = all(hashlib.sha256(open(R.EVENTS + "/" + f, "rb").read()).hexdigest() == v["sha256"] for f, v in man["files"].items()); ck("events: every manifest sha256 matches its file", shaok and len(man["files"]) > 0, "%d files" % len(man["files"]))
ck("events: every traced day has a snapshot (%d days)" % len(days), all(d + ".json" in man["files"] for d in days), "missing: %s" % [d for d in days if d + ".json" not in man["files"]])
ok = [f for f, v in man["files"].items() if v["status"] == "ok"]; ck("events: days that parsed", len(ok) == len(man["files"]), "%d of %d ok, bullets %d" % (len(ok), len(man["files"]), sum(v["bullets"] for v in man["files"].values())))
d0 = json.load(open(R.EVENTS + "/" + days[-1] + ".json")); ck("events: a day file carries page title, revid, licence, source links", d0["page"].startswith("Portal:Current events/") and d0["revid"] and "CC BY-SA" in d0["licence"] and any(x["sources"] for x in d0["bullets"]), d0["page"])
# ---------- wikidata cache ----------
wm = json.load(open(W.CACHE + "/MANIFEST.json")); ck("wikidata: licence CC0 in manifest", "CC0" in wm["licence"], wm["licence"])
ck("wikidata: every manifest sha256 matches, and the file name is the key of its query", all(hashlib.sha256(open(W.CACHE + "/" + f, "rb").read()).hexdigest() == v["sha256"] and f == W.key(v["query"]) + ".json" for f, v in wm["files"].items()), "%d files" % len(wm["files"]))
P = W.load_plan(); cov = sum(1 for n in P["names"] if W.lookup(n)); ck("wikidata: planned names cached", cov == len(P["names"]), "%d of %d (%d articles, %d merge entities)" % (cov, len(P["names"]), len(P["per_article"]), len(P["merges"])))
ck("wikidata: top-20 names per article", all(len(v) <= 20 for v in P["per_article"].values()), "max %d" % max(len(v) for v in P["per_article"].values()))
ck("wikidata: qname strips possessives, key is case-insensitive", W.qname("Spain’s") == "Spain" and W.key("SPAIN") == W.key("spain") and W.qname("Trump's") == "Trump", "")
# ---------- scoring rules on synthetic data ----------
def mk(per_day, series):
    return {"independent_items_per_day": per_day, "resource_day": {r: {d: {"items": 1, "mass": m} for d, m in x.items()} for r, x in series.items()}}
D = ["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06"]
syn = mk({d: 100 for d in D} | {"2026-10-01": 3}, {"war": {"2026-11-01": 1, "2026-11-02": 1, "2026-11-03": 1, "2026-11-04": 9, "2026-11-05": 1, "2026-11-06": 1, "2026-10-01": 50}, "work": {d: 1 for d in D} | {"2026-11-01": 8}})
ev = lambda d, t: {"date": d, "category": "x", "text": t, "parent": None}
evs = [ev("2026-11-05", "Troops attack a town"), ev("2026-11-05", "Another attack on a camp"), ev("2026-11-01", "Troops attack a town"), ev("2026-10-01", "A war begins"), ev("2026-11-06", "Workers strike for higher wages")]
s = R.score_events(syn, evs); u = {(x["date"], x["resource"]): x for x in s["units"]}
ck("score: one unit per (day, resource), not per event", u[("2026-11-05", "state_capacity")]["n_events"] == 2 if ("2026-11-05", "state_capacity") in u else False, "units %d" % len(s["units"]))
sc = {k: v for k, v in u.items()}
R_ = dict(R.RX); R.RX.clear(); R.RX.update({"war": R.re.compile("attack|war", R.re.I), "work": R.re.compile("strike|wages", R.re.I)})
s = R.score_events(syn, evs); u = {(x["date"], x["resource"]): x for x in s["units"]}
ck("score: peak day 11-04: event 11-05 is a hit (+1 day)", u[("2026-11-05", "war")]["hit"] is True, str(u[("2026-11-05", "war")]["peak_share_day"]))
ck("score: event 11-01 is a miss (3 days from the peak)", u[("2026-11-01", "war")]["hit"] is False, "")
ck("score: a day under MIN_ITEMS is not checkable and is excluded from the peak search", u[("2026-10-01", "war")]["checkable"] is False and u[("2026-11-05", "war")]["peak_share_day"] == "2026-11-04", "")
ck("score: 'strike' on 11-06 maps to work; peak 11-01 is 5 days away: miss; hit counts add up", u[("2026-11-06", "work")]["hit"] is False and s["checkable"] == 3 and s["hits"] == 1 and abs(s["hit_rate"] - 1 / 3) < 1e-3, "%d/%d" % (s["hits"], s["checkable"]))
ck("score: chance = share of checkable days within +/-1 of the peak (11-04 peak: 3 of 6 days)", abs(u[("2026-11-05", "war")]["chance"] - 0.5) < 1e-9, "")
R.RX.clear(); R.RX.update(R_)
cd = tempfile.mkdtemp(prefix="truth-check-")
def put(n, ids): json.dump({"query": n, "results": [{"id": i, "label": n, "description": "", "match": "label"} for i in ids]}, open(W.path(n, cd), "w"))
put("Spain", ["Q29"]); put("Spanish", ["Q1321"]); put("Trump", ["Q22686"]); put("Donald Trump", ["Q22686"]); put("Nowhere", [])
r_ = W.resolve("Spain", cd); ck("wikidata: resolve gives the top hit; empty result and uncached name give None", r_["qid"] == "Q29" and W.resolve("Nowhere", cd) is None and W.resolve("Never asked", cd) is None, "")
_resolve = W.resolve; W.resolve = lambda n, cache=cd: _resolve(n, cache)
idn = R.score_identity({"names": [], "merges": [("e1", "place", "Spain", ["Spanish", "Nowhere"]), ("e2", "person", "Donald Trump", ["Trump"])]}); W.resolve = _resolve
ck("identity: different QIDs are a conflict, same QID is not, unresolved is not scored", idn["pairs_resolved"] == 2 and idn["pairs_unresolved"] == 1 and idn["conflicts"] == 1 and idn["conflict_pairs"][0]["alias"] == "Spanish" and idn["pass"] is False, "")
# ---------- real data ----------
a = R.score_events(snap, R.load_events()); b2 = R.score_events(snap, R.load_events()); ck("real: scoring is deterministic", json.dumps(a, sort_keys=True) == json.dumps(b2, sort_keys=True), "")
ck("real: hits <= checkable <= mapped units; secondary counts <= checkable", a["hits"] <= a["checkable"] <= a["units_mapped"] and a["secondary"]["hits_raw_mass_peak"] <= a["checkable"] and a["secondary"]["hits_local_spike"] <= a["checkable"], "hits %d checkable %d mapped %d" % (a["hits"], a["checkable"], a["units_mapped"]))
ck("real: snapshot is the same trace as the v7 chain", snap["chain_sha256"] == hashlib.sha256(open(R.TRACE + "/chain.jsonl", "rb").read()).hexdigest(), snap["chain_sha256"][:12])
i = R.score_identity(); ck("real: identity pairs resolved + unresolved = all pairs", i["pairs_resolved"] + i["pairs_unresolved"] == i["pairs_total"], "")
print("RESULT event peak: events %d, mapped %d, checkable units %d, hits %d, rate %s, bar %.2f -> %s; raw-mass peak hits %d, local-spike hits %d, chance %s" % (a["events_total"], a["events_mapped"], a["checkable"], a["hits"], a["hit_rate"], a["bar"], "MEETS BAR" if a["pass"] else "BELOW BAR", a["secondary"]["hits_raw_mass_peak"], a["secondary"]["hits_local_spike"], a["secondary"]["chance_rate"]))
print("RESULT identity: names %d, with a Wikidata hit %d, alias pairs resolved %d (unresolved %d), conflicts %d, rate %s, bar %d -> %s; by alias length %s, by type %s" % (i["names_planned"], i["names_with_hit"], i["pairs_resolved"], i["pairs_unresolved"], i["conflicts"], i["conflict_rate"], i["bar"], "MEETS BAR" if i["pass"] else "BELOW BAR", {t: "%d/%d" % (v["resolved"], v["conflicts"]) for t, v in i["by_alias_words"].items()}, {t: "%d/%d" % (v["resolved"], v["conflicts"]) for t, v in i["by_type"].items()}))
print("%d checks failed: %s" % (len(bad), bad) if bad else "all structural checks passed"); sys.exit(1 if bad else 0)
