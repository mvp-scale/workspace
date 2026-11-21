"""live_wire_compare: the live check of the wired topic re-ranker (ledger L2756) on one live-trace-v3 run: publisher-section agreement of the landing alone vs the re-ranker on the SAME articles
(feed-section rule of topic_loop.py / field_test.py: exactly one of business, science, tech, health, entertain, politic, environment, climate in the queue feed name, never 'world'; agreement = the level-1 code equals the section's code),
topic_node answer share, topic_landing latency p50/p90 (run.json), RERANK_DISAGREE share. Reads the trace and the queue (feed column, read-only); no model, no label other than the publisher's own section.
    python3 live_wire_compare.py <trace dir> [--out file.json] [--base <older trace dir>]   (--base: prints the same latency and answer-share numbers for that run)"""
import sys, os, json, sqlite3, collections, random, pathlib
HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE)); os.chdir(HERE)
SEC = {"business": "economy, business and finance", "science": "science and technology", "tech": "science and technology", "health": "health", "entertain": "arts, culture, entertainment and media", "politic": "politics and government", "environment": "environment", "climate": "environment"}
def lines(tr):
    for l in open(tr + "/chain.jsonl"):
        a = json.loads(json.loads(l)["line"])
        if a["state"] == "traced": yield a
def run_numbers(tr):
    r = json.load(open(tr + "/run.json")); n = r["counts"]["traced"]; tn = r["decider"].get("topic_node", {}); ans = sum(v for k, v in tn.items() if k.startswith("ANSWER")); g = {x["code"]: x for x in r["gaps"]}; tl = r["stages"]["topic_landing"]
    return {"run_id": r["run_id"], "version": r.get("version"), "traced": n, "topic_node_answer_share": round(ans / n, 4), "topic_node_outcomes": tn, "topic_landing_p50_ms": tl["p50_ms"], "topic_landing_p90_ms": tl["p90_ms"], "total_p50_ms": r["total_p50_ms"], "total_p90_ms": r["total_p90_ms"],
            "LANDING_WEAK_share": g.get("LANDING_WEAK", {}).get("rate", 0), "RERANK_DISAGREE_share": g.get("RERANK_DISAGREE", {}).get("rate", 0), "label_version": r.get("label_version")}
def main():
    tr = sys.argv[1].rstrip("/"); out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None; res = {"run": run_numbers(tr)}
    if "--base" in sys.argv: res["base_run"] = run_numbers(sys.argv[sys.argv.index("--base") + 1].rstrip("/"))
    import spacy; from structure_pack import Pack; P = Pack(spacy.blank("en")); lab2code = {P.lab(q).lower(): q for q in P.node if len(P.chain(q)) == 1}
    db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); A = list(lines(tr)); feed = {}
    for i in range(0, len(A), 500): feed.update(dict(db.execute("select id, feed from items where id in (%s)" % ",".join("?" * len(A[i:i + 500])), [a["id"] for a in A[i:i + 500]]).fetchall()))
    rows = []
    for a in A:
        f = (feed.get(a["id"]) or "").lower(); hit = {v for k, v in SEC.items() if k in f}
        if len(hit) != 1 or "world" in f: continue
        o = next(s for s in a["stages"] if s["name"] == "topic_landing")["out"] or {}; g = lab2code[next(iter(hit))]
        rows.append({"src": a["source"], "gold": g, "land": o.get("landing_l1_code") or o.get("l1_code"), "rr": o.get("l1_code") if o.get("rerank") else None, "dec": o.get("decision"), "ldec": o.get("landing_decision") or o.get("decision")})
    n = len(rows); rr = [r for r in rows if r["rr"]]; res["section_articles"] = n; res["rerank_present_on"] = len(rr); rng = random.Random(20261120); pubs = sorted({r["src"] for r in rr}); byp = collections.defaultdict(list)
    for r in rr: byp[r["src"]].append(r)
    ag = lambda L, key: sum(r[key] == r["gold"] for r in L) / max(1, len(L))
    res["agreement"] = {"landing_alone": round(ag(rr, "land"), 4), "reranker": round(ag(rr, "rr"), 4), "change_pts": round(100 * (ag(rr, "rr") - ag(rr, "land")), 2)}
    d = []
    for _ in range(2000): L = [x for p in (pubs[rng.randrange(len(pubs))] for _ in pubs) for x in byp[p]]; d.append(ag(L, "rr") - ag(L, "land"))
    d.sort(); res["agreement"]["change_pts_ci95_publisher_bootstrap"] = [round(100 * d[49], 2), round(100 * d[1949], 2)]; res["publishers_with_sections"] = len(pubs)
    an = [r for r in rr if r["dec"] == "ANSWER_L1"]; la = [r for r in rr if r["ldec"] == "ANSWER_L1"]
    res["answered_only"] = {"reranker_answered": len(an), "reranker_agreement_on_answered": round(ag(an, "rr"), 4), "landing_answered_on_same_articles": len(la), "landing_agreement_on_its_answered": round(ag(la, "land"), 4)}
    res["sections"] = dict(collections.Counter(r["gold"] for r in rr)); print(json.dumps(res, indent=1))
    if out: json.dump(res, open(out, "w"), indent=1)
main()
