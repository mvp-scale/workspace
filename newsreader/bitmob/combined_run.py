"""Kaggle runner for the combined reader (F-0110): real Clef calls, one worker per GPU, calls sequential inside a story (clean latency).
Per story: read_story() (BitMob heads come precomputed in the stories file; Clef answers shortlisted blocks, the unsure gate block, the expected questions).
Control stories (ctrl=true, last in the file): then the engine's whole Clef path (17-call ask, place, country, expected, severity) with the engine's own functions, timed per phase, for the same-hardware time baseline.
  python3 combined_run.py IN.jsonl OUT.jsonl --minutes M"""
import os, sys, json, time, argparse
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob", "/workspace/newsreader/bitmob/reader"]
import classify as C, offline as O, backends, combined_reader as CR
b = backends.BACKENDS["clef-flash-q4km"]; O.set_reader(b["url"], b.get("model", ""), b.get("key", ""), "clef-flash-q4km")
ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out"); ap.add_argument("--minutes", type=float, default=30); a = ap.parse_args(); t_end = time.time() + 60 * a.minutes
KEYS = json.load(open("/workspace/newsreader/bitmob/reader/bitmob_keys.json")); orig = O.call
done = set(json.loads(l)["id"] for l in open(a.out)) if os.path.exists(a.out) else set()
def full_engine(text, day):
    """The engine's whole Clef path on one story, per phase: seconds, questions, calls. Engine functions are used as they are; only the story text is injected (state_text is already 'title. description')."""
    state = f"News item (published {day}; today is {day}):\n{text}"; ph = {}; cur = {"n": 0, "c": 0}
    def counted(st, qs): cur["n"] += len(qs); cur["c"] += 1; return orig(state, qs)
    def phase(name, fn):
        cur["n"] = cur["c"] = 0; t = time.time(); r = fn(); ph[name] = {"s": round(time.time() - t, 3), "q": cur["n"], "calls": cur["c"]}; return r
    ev = {"published_at": day, "title": text, "description": ""}; O.call = counted
    try:
        def ask_all():
            P = {}
            for blk in CR.BLOCKS: r = counted(state, {k: {"type": "noul", "instructions": C.QS[k]} for k in blk}); P.update({k: r[k]["noul"] for k in r})
            return P
        P = phase("ask", ask_all); rd = C.read(P); rep = {x["dial"]: x["direction"] for x in rd["readings"] if x["direction"] != "conflict"}
        pl = phase("place", lambda: C.place(ev, today=day, call=counted)); allowed = C.allowed_dials(pl)
        phase("country", lambda: C.ask_country_detailed(ev, today=day, call=counted))
        ex = phase("expected", lambda: C.expected(ev, set(rep), allowed, today=day))
        dials = dict(rep); dials.update({x["dial"]: x["direction"] for x in ex}); phase("severity", lambda: C.severity(ev, dials, today=day))
    finally: O.call = orig
    return {"phases": ph, "total_s": round(sum(v["s"] for v in ph.values()), 3), "total_q": sum(v["q"] for v in ph.values()), "total_calls": sum(v["calls"] for v in ph.values()), "F": P}
first = next(json.loads(l) for l in open(a.inp)); orig(f"News item (published {first['day']}; today is {first['day']}):\n{first['text']}", {k: {"type": "noul", "instructions": C.QS[k]} for k in CR.BLOCKS[0]})   # warm-up
for l in open(a.inp):
    r = json.loads(l)
    if r["id"] in done: continue
    if time.time() > t_end: break
    out = CR.read_story(r["text"], r["day"], r["heads"], KEYS, orig); rec = {"id": r["id"], "out": out}
    if r["ctrl"]: rec["ctrl"] = full_engine(r["text"], r["day"])
    open(a.out, "a").write(json.dumps(rec) + "\n")
