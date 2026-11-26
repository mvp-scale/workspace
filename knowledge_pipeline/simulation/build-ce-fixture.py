"""build-ce-fixture (round C, 00.1 Phase 2, T158-C1): builds the staged window `ce1` from the Wikipedia current-events adapter (projects/world-state/source_adapters.py) with the UNEDITED fixture builder.
How: CurrentEventsAdapter.items({days}) -> source items -> a queue-shaped sqlite (fixtures/knowledge/ce1/source-queue.sqlite) -> live_trace.QUEUE pointed at it for this process only -> build-knowledge-fixture.build() (Chain.trace, journal, v4 stage step, exactly as for the news areas) -> fixtures/knowledge/ce1/trace + an areas.json entry (key, label, note, ids, bars, publishers, days) and fixtures/knowledge/ce1/items.json (the source items, the dropped bullets, licence and attribution).
CPU only, no network (saved snapshots), no hosted call. The news queue is not read.
    /workspace/models/embed-zs/.venv/bin/python simulation/build-ce-fixture.py [--days 2026-11-17,2026-11-18,2026-11-19] [--key ce1]"""
import sys, os, json, importlib.util, time
HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]
DAYS = args[args.index("--days") + 1].split(",") if "--days" in args else ["2026-11-17", "2026-11-18", "2026-11-19"]
KEY = args[args.index("--key") + 1] if "--key" in args else "ce1"
sp = importlib.util.spec_from_file_location("bkf", os.path.join(HERE, "build-knowledge-fixture.py")); B = importlib.util.module_from_spec(sp)
sys.argv = [sys.argv[0]]; sp.loader.exec_module(B)   # the builder's own argv parsing sees no flags; it chdirs to projects/world-state and puts it on sys.path
import source_adapters as SA, live_trace as LT, live_gaps as G, journal as JR
ad = SA.CurrentEventsAdapter(); items = ad.items({"days": DAYS})
out = os.path.join(B.OUT, KEY); os.makedirs(out, exist_ok=True)
db = SA.write_queue_db(items, os.path.join(out, "source-queue.sqlite")); LT.QUEUE = db   # this process only
json.dump({"adapter": ad.name, "days": DAYS, "licence": "CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/)", "attribution": "Wikipedia contributors, Portal:Current events (per-day pages), https://en.wikipedia.org/wiki/Portal:Current_events; revision ids in each item's meta",
           "items": items, "dropped": ad.dropped}, open(out + "/items.json", "w"), ensure_ascii=False, indent=1)
t0 = time.time(); ch = LT.Chain(); print("chain loaded in %.1f s; %d items, %d dropped bullets (no cited outlet)" % (time.time() - t0, len(items), len(ad.dropped)), flush=True)
label = "CE1 Wikipedia current events %s" % " ".join(DAYS); note = "second source type: Wikipedia current-events bullets of %s (saved snapshots, CC BY-SA 4.0); unit = one bullet citing an outlet; publisher = first cited outlet" % ", ".join(DAYS)
a = B.build(ch, LT, JR, G, LT.hash_sets, KEY, label, [x["id"] for x in items], note)
a["bars"] = {"counters_gt0": ["new"], "known_case": None, "contradiction_min": None}; a["short"] = "Wikipedia current events"; a["source_adapter"] = ad.name
areas = json.load(open(B.OUT + "/areas.json")); areas = [x for x in areas if x["key"] != KEY] + [a]; B.atomic(B.OUT + "/areas.json", areas, indent=1)
print("%s: %d of %d items traced (%d dropped), %d publishers, days %s, %.1f s" % (KEY, len(a["ids"]), len(items), len(a["dropped"]), len(a["publishers"]), ",".join(a["days"]), time.time() - t0))
for d in a["dropped"]: print("   dropped", d["id"][:12], d["why"])
