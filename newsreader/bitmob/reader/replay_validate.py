"""D-0037 step 3: replay the same held-out stories through the engine's reader path (classify.py: ask, read, country, place, expected, severity) with one reader.
Stories: seeded sample of the frozen test (testA, never trained on), with Jev's labels beside them. Reader by registry name: clef-flash-q4km | bitmob-clef | bitmob-cpu.
  cd /workspace/probes/world-engine && WE_RULES=rules_v2 WORLD_GPU=0 /workspace/kev/.venv/bin/python -I /workspace/newsreader/bitmob/reader/replay_validate.py <reader> <N> <workers> <out.jsonl> [skip]
Records per story: gate, condition readings, entry country, placement, expected readings, severity, seconds per phase, and what each phase sent to Clef."""
import sys, os, json, time, random, datetime, concurrent.futures as cf
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine"); sys.path.insert(0, "/workspace/demo"); sys.path.insert(0, "/workspace/probes/persona")
import classify as C, backends, urllib.request
bid, N, WK, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]; SKIP = int(sys.argv[5]) if len(sys.argv) > 5 else 0
b = backends.BACKENDS[bid]; C.O.set_reader(b["url"], b["model"], b["key"], bid)
rows = [json.loads(l) for l in open("/workspace/data/trainset/testA.jsonl")]; random.Random(7).shuffle(rows); rows = rows[SKIP:SKIP + N]
ids = {r["id"] for r in rows}; today = datetime.date.today().isoformat()
def stats():
    try:
        with urllib.request.urlopen(b["url"].rstrip("/") + "/stats", timeout=3) as r: return json.load(r)
    except Exception: return {}
def one(r):
    ev = {"evidence_id": "val", "published_at": today, "title": r["title"], "description": r.get("description") or ""}; t = {}; T0 = time.time()
    s = time.time(); P = C.ask(ev); rd = C.read(P); t["ask_read"] = time.time() - s
    s = time.time(); country, cp, det = C.ask_country_detailed(ev); t["country"] = time.time() - s
    s = time.time(); pl = C.place(ev); t["place"] = time.time() - s
    reported = [x for x in rd["readings"] if x["direction"] != "conflict"]
    s = time.time(); ex = C.expected(ev, {x["dial"] for x in reported}, C.allowed_dials(pl)); t["expected"] = time.time() - s
    s = time.time(); sv = C.severity(ev, {x["dial"]: x["direction"] for x in reported + ex}) if (reported or ex) else {}; t["severity"] = time.time() - s
    keys = sorted(f'{x["dial"]}|{x["direction"]}' for x in reported)
    return {"id": r["id"], "reader": bid, "title": r["title"], "gate_ok": rd["gate_ok"], "gate": rd["gate"], "g": {k: P[f"g|{k}"] for k in ("happened", "announced", "opinion", "forecast")}, "recent": P["x|recent"], "keys": keys,
            "strength": {f'{x["dial"]}|{x["direction"]}': x["strength"] for x in reported}, "conflicts": sorted(x["dial"] for x in rd["readings"] if x["direction"] == "conflict"), "country": country, "country_detail": det,
            "topic": next((x["id"] for x in pl if x["tagged"]), None), "tagged": [x["id"] for x in pl if x["tagged"]], "topic_choice": max(pl, key=lambda x: x["p_choice"])["id"],
            "expected": [{"dial": x["dial"], "direction": x["direction"], "strength": x["strength"]} for x in ex], "severity": {d: v["level"] for d, v in sv.items()}, "size_mult": {d: round(v["mult"], 3) for d, v in sv.items()},
            "t": {k: round(v, 3) for k, v in t.items()} | {"total": round(time.time() - T0, 3)},
            "truth": {"keys": sorted(r["target_keys"]), "topic": r["topic"], "country": r["country"], "happened": r["P"].get("g|happened"), "announced": r["P"].get("g|announced"), "opinion": r["P"].get("g|opinion"), "recent": r["P"].get("x|recent"), "gate_ok": r.get("gate_ok")}}
s0 = stats(); t0 = time.time(); done = 0
with cf.ThreadPoolExecutor(WK) as ex, open(OUT, "a") as f:
    for rec in ex.map(one, rows):
        f.write(json.dumps(rec) + "\n"); f.flush(); done += 1
        if done % 25 == 0: print(done, "stories", round(time.time() - t0), "s", flush=True)
s1 = stats(); print(json.dumps({"reader": bid, "stories": done, "wall_s": round(time.time() - t0, 1), "stats_before": s0, "stats_after": s1}))
