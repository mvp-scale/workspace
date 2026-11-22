"""build-knowledge-fixture: offline traces for the Knowledge-step gate (T158, knowledge plan wave 0, owner yes L2936). PROVISIONAL (L2901).
Builds, once, simulation/fixtures/knowledge/<area>/trace/ in the same shape as simulation/fixtures/parts/trace (chain.jsonl with the sha chain, a/<seq>.json = {article_line, text, stages_full}, run.json) plus simulation/fixtures/knowledge/areas.json.
Areas: c1 = cluster 'C1' (Fiona the hippo, one event, many publishers), mix = cluster 'MIX' (Gulf strikes + Saudi-Houthi war + UK energy bills), ids from the scout file story_clusters.json (--clusters, default the session scratchpad; areas.json keeps the ids, so a rebuild without the scout file reads them from there).
How: the per-article trace of live_trace.py (Chain.trace, then the journal classify and the v4 stage step, exactly as live_trace.replay_run and main do, default flags: journal and fewnerd on, claims / identity / contradictions deferred to the slow clock), on the queue ids in order of
published date then id (so the chain seq is the arrival order of the story). The text is read once, read-only, from the news queue database (allowlisted columns of live_trace.select_sql). A row that is missing from the queue, or a line the chain skips (text under 40 characters), is dropped and listed (areas.json 'dropped'). Nothing is written to the queue, the journal or any G4 store.
    /workspace/models/embed-zs/.venv/bin/python simulation/build-knowledge-fixture.py [--refresh] [--only c1,mix] [--clusters <story_clusters.json>]
Without --refresh an area whose fixture already exists is left alone (offline after the first run). CPU only, no hosted call, no service touched, decider.py / lean/ / live_trace*.py not edited."""
import sys, os, re, json, time, hashlib, sqlite3, collections, statistics
HERE = os.path.dirname(os.path.abspath(__file__)); KP = os.path.dirname(HERE); WS = os.path.join(KP, "projects", "world-state")
OUT = os.path.join(HERE, "fixtures", "knowledge")
CLUSTERS = "/tmp/claude-0/-workspace/3ed8559b-0aa2-49c4-a429-a0452a913be2/scratchpad/know/story_clusters.json"
AREAS = [("c1", "C1", "Fiona the hippo (Cincinnati Zoo): one event, many publishers; alive under care versus died"),
         ("mix", "MIX", "Gulf strikes + Saudi-Houthi war + UK energy bills: war_conflict and economy Areas that share capabilities")]
os.environ.setdefault("HF_HUB_OFFLINE", "1"); os.environ.setdefault("CUDA_VISIBLE_DEVICES", ""); os.environ["WORLD_GPU"] = "0"; os.environ.setdefault("TOKENIZERS_PARALLELISM", "false"); os.environ.setdefault("PYTHONHASHSEED", "0")
os.environ.pop("LT_V4_G4_DIR", None)   # the chain graph stays in memory (identity is deferred anyway)
args = sys.argv[1:]; REFRESH = "--refresh" in args
ONLY = set(args[args.index("--only") + 1].split(",")) if "--only" in args else None
if "--clusters" in args: CLUSTERS = args[args.index("--clusters") + 1]
os.chdir(WS); sys.path.insert(0, WS)
def atomic(path, obj, indent=None):
    tmp = path + ".tmp"; open(tmp, "w").write(json.dumps(obj, ensure_ascii=False, indent=indent)); os.replace(tmp, path)
def load_ids():
    """{key: (label, ids)}: from the scout file, else from an existing areas.json"""
    out = {}
    if os.path.exists(CLUSTERS):
        cl = json.load(open(CLUSTERS))
        for key, pre, _ in AREAS:
            c = [x for x in cl if x["label"].split(" ")[0] == pre]
            if len(c) != 1: raise SystemExit("cluster %s: %d matches in %s" % (pre, len(c), CLUSTERS))
            out[key] = (c[0]["label"], c[0]["ids"])
    elif os.path.exists(OUT + "/areas.json"):
        for a in json.load(open(OUT + "/areas.json")): out[a["key"]] = (a["label"], a["ids"])
    else: raise SystemExit("no cluster ids: %s missing and no areas.json" % CLUSTERS)
    return out
def build(ch, LT, JR, G, hash_sets, key, label, ids, note):
    db = sqlite3.connect("file:%s?mode=ro" % LT.QUEUE, uri=True); rows = []; dropped = []
    for i in ids:
        r = db.execute(LT.select_sql("id = ?"), (i,)).fetchone()
        if r is None: dropped.append({"id": i, "why": "not in the queue"})
        else: rows.append(r)
    rows.sort(key=lambda r: ((r[6] or ""), r[0]))   # published, then id: arrival order of the story
    tr = os.path.join(OUT, key, "trace"); tmp = tr + ".building"
    import shutil
    if os.path.exists(tmp): shutil.rmtree(tmp)
    os.makedirs(tmp + "/a")
    fsha, msha = hash_sets(ch); code_hash = hashlib.sha256("".join(fsha[k] for k in sorted(fsha)).encode()).hexdigest()[:16]; t0 = time.time()
    run_id = "run-%d-%s" % (int(t0), code_hash[:6]); kidx = JR.new_index(); prev = run_id; seq = 0; lines = []; lag = []; slow = []
    lab = lambda q: ch.pack.lab(q) if q in ch.pack.node else q; cf = open(tmp + "/chain.jsonl", "w")
    for row in rows:
        rd = time.time(); line, text, full = ch.trace(row)
        if line["state"] != "traced": dropped.append({"id": row[0], "why": "skipped by the chain: %s" % line.get("skip_reason")}); continue
        d = JR.classify(kidx, line["journal"]["story_key"], line["source"], seq)   # in-memory story-key index in the order of the chain, as live_trace.replay_run does
        line["journal"].update(story_key=d["keys"], dup={"kind": d["kind"], "of_seq": d["of_seq"]}, publishers=d["publishers"], novelty_proxy=LT.novelty_proxy(d)); ch.v4.post(line, text, full, row, d, 0.0, seq)
        line.update(seq=seq, read_at=rd, lag_s=round(rd - row[7], 2) if row[7] else None); line["gaps"] = G.per_article_gaps(line)
        js = json.dumps(line, sort_keys=True, separators=(",", ":"), ensure_ascii=False); sha = hashlib.sha256((prev + js).encode()).hexdigest()
        json.dump({"article_line": line, "text": text, "stages_full": full}, open(tmp + "/a/%d.json" % seq, "w"), ensure_ascii=False)
        cf.write(json.dumps({"seq": seq, "prev": prev, "sha": sha, "line": js}, ensure_ascii=False) + "\n")
        prev = sha; seq += 1; lines.append(line); lag.append(line["lag_s"] or 0.0)
        for s in line["stages"]:
            if s.get("slow"): slow.append({"seq": line["seq"], "stage": s["name"], "ms": s["ms"]})
    cf.close(); agg = G.aggregate(lines, lab); lg = sorted(lag)
    lv = {"iptc_release": ch.iptc_release, "cards": ch.landing.cards_sha[:16] if ch.landing else None, "table": ch.table_version, "calibration": ch.calib["sha16"] if ch.calib else None, "rerank_model": ch.rerank.model_sha16 if ch.rerank else None, "rerank_calibration": ch.rerank.cal["sha16"] if ch.rerank else None}
    jr = {"journal": {**agg["journal"], "as_of": {"run_id": run_id, "seq": seq - 1, "label_version": lv}}} if agg["journal"] else {}
    atomic(tmp + "/run.json", {"run_id": run_id, "version": LT.SCHEMA_VERSION, "journal_version": "journal-v0", **jr, "label_version": lv, "degraded": ["no landing"] if ch.landing is None else (([] if ch.calib else ["landing-v0: " + str(ch.calib_why)]) + ([] if ch.rerank else ["no re-ranker: " + str(ch.rerank_why)])),
        "start_epoch": t0, "ends_epoch": time.time(), "now_epoch": time.time(), "state": "stopped", "code_hash": code_hash, "file_sha": fsha, "model_sha": msha, "columns_allowlist": LT.ALLOW, "budget_ms": LT.BUDGET,
        "counts": {"traced": seq, "skipped": len(dropped), "backlog_ready": 0, "rows_ready_since_start": 0, "never_ready_since_start": 0, "rows_found_since_start": 0, "ready_found_before_start": 0},
        "queue_lag_p50_s": round(statistics.median(lg), 1) if lg else None, "total_p50_ms": agg["total_p50_ms"], "total_p90_ms": agg["total_p90_ms"], "over_budget_n": agg["over_budget_n"], "stages": agg["stages"], "decider": agg["decider"], "gaps": agg["gaps"],
        "slow_stages": slow[-20:], "v4": ch.v4.run_block(), "gap_rules": G.RULES, "load_s": None, "check_cmd": [], "not_attached_why": {k: v[1] for k, v in ch.NA.items()},
        "fixture": {"kind": "knowledge-fixture", "area": key, "label": label, "built_by": "simulation/build-knowledge-fixture.py", "source": "queue ids replayed through live_trace.Chain.trace, ordered by published date then id; offline copy", "provisional": True}})
    if os.path.exists(tr): shutil.rmtree(tr)
    os.rename(tmp, tr)
    pubs = sorted({l["source"] for l in lines}); days = sorted({(l["published"] or "")[:10] for l in lines if l.get("published")})
    return {"key": key, "label": label, "ids": [l["id"] for l in lines], "publishers": pubs, "days": days, "note": note, "n_cluster": len(ids), "dropped": dropped}
def main():
    import live_trace as LT, live_gaps as G, journal as JR
    ids = load_ids(); old = {a["key"]: a for a in json.load(open(OUT + "/areas.json"))} if os.path.exists(OUT + "/areas.json") else {}
    todo = [(k, p, n) for k, p, n in AREAS if (ONLY is None or k in ONLY) and (REFRESH or k not in old or not os.path.exists(os.path.join(OUT, k, "trace", "chain.jsonl")))]
    res = dict(old)
    if todo:
        t0 = time.time(); ch = LT.Chain(); print("chain loaded in %.1f s" % (time.time() - t0), flush=True)
        for k, p, n in todo:
            lab, i = ids[k]; t1 = time.time(); a = build(ch, LT, JR, G, LT.hash_sets, k, lab, i, n); res[k] = a
            print("%s: %d of %d articles traced (%d dropped), %d publishers, days %s, %.1f s" % (k, len(a["ids"]), len(i), len(a["dropped"]), len(a["publishers"]), ",".join(a["days"]), time.time() - t1), flush=True)
            for d in a["dropped"]: print("   dropped", d["id"][:12], d["why"])
    os.makedirs(OUT, exist_ok=True); atomic(OUT + "/areas.json", [res[k] for k, _, _ in AREAS if k in res], indent=1)
    print("areas.json:", ", ".join("%s=%d" % (k, len(res[k]["ids"])) for k, _, _ in AREAS if k in res))
if __name__ == "__main__": main()
