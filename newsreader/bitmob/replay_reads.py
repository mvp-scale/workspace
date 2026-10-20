"""Replay the World engine's logged feed reads with another reader (by registry name) and put its readings beside the original's.
Usage (kev venv, from /workspace/probes/world-engine): WE_RULES=rules_v2 python -I /workspace/newsreader/bitmob/replay_reads.py <backend id> [out]"""
import sys, os, json, time, concurrent.futures as cf
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine"); sys.path.insert(0, "/workspace/demo")
import classify as C, backends
bid = sys.argv[1]; b = backends.BACKENDS[bid]; C.O.set_reader(b["url"], b["model"], b["key"], bid)
OUT = sys.argv[2] if len(sys.argv) > 2 else f"/workspace/data/world-engine/replay-{bid}.jsonl"
src = [json.loads(l) for l in open("/workspace/data/world-engine/reads.jsonl")]; src = [r for r in src if r["source"] == "feed"]
calls = [0]; orig = C.O.call
def counted(*a, **k): calls[0] += 1; return orig(*a, **k)
C.O.call = counted
def one(r):
    ev = {"published_at": r["published"], "title": r["title"], "description": r["text"]}; t = time.time()
    P = C.ask(ev, today=r["published"]); rd = C.read(P)
    return {"at": r["at"], "title": r["title"], "reader": bid, "orig_reader": r["reader"], "P": P, "readings": rd["readings"], "gate_ok": rd["gate_ok"],
            "orig_readings": r["readings"], "s": round(time.time() - t, 1)}
t0 = time.time()
with cf.ThreadPoolExecutor(4) as ex, open(OUT, "w") as f:
    for rec in ex.map(one, src): f.write(json.dumps(rec) + "\n")
print(json.dumps({"stories": len(src), "calls": calls[0], "minutes": round((time.time() - t0) / 60, 1), "out": OUT}))
