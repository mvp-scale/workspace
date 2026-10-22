"""Round 0 labels for the contract loop (D-0038): local Clef answers the ENGINE'S OWN questions (classify.py) on exactly the text BitMob reads.
Per story: ask() 328 yes/no, read() gate+readings, place() choice+48 y|, ask_country_detailed(), expected(), severity() for every reading.
  /workspace/kev/.venv/bin/python newsreader/bitmob/clef_label.py IN.jsonl OUT.jsonl [--n N] [--workers W] [--minutes M] [--offset K]
Resumable (skips ids already in OUT). Stops cleanly after --minutes. Never touches the GPU by itself: only calls Clef on :8018 (never stops it)."""
import os, sys, json, time, argparse, datetime, threading
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob"]
import classify as C, offline as O, backends
from progress import event
b = backends.BACKENDS["clef-flash-q4km"]; O.set_reader(b["url"], b.get("model", ""), b.get("key", ""), "clef-flash-q4km")
ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out"); ap.add_argument("--n", type=int, default=50); ap.add_argument("--workers", type=int, default=2)
ap.add_argument("--minutes", type=float, default=45); ap.add_argument("--offset", type=int, default=0); ap.add_argument("--job", default="clef-label")
a = ap.parse_args(); t_end = time.time() + 60 * a.minutes
rows = [json.loads(l) for l in open(a.inp)][a.offset:a.offset + a.n]
done = set()
if os.path.exists(a.out): done = {json.loads(l)["id"] for l in open(a.out) if l.strip()}
todo = [r for r in rows if r["id"] not in done]; lock = threading.Lock(); st = {"n": 0, "err": 0, "t": time.time()}


_orig_call = O.call; TL = threading.local()
def _rec_call(state, qs):
    a = _orig_call(state, qs); L = getattr(TL, "rec", None)
    if L is not None: L.append({k: (v.get("noul") if "noul" in v else v.get("probabilities")) for k, v in a.items()})
    return a
O.call = _rec_call


def story_ev(r):
    day = r.get("date") or datetime.date.today().isoformat(); d250 = (r.get("description") or "")[:250]
    return {"evidence_id": r["id"], "published_at": day, "title": r["title"], "description": d250}, day       # same state text as build_trainset: title. desc[:250]


def label(r):
    ev, day = story_ev(r); t0 = time.time(); tm = {}
    P = C.ask(ev, today=day); rd = C.read(P); tm["ask"] = time.time() - t0; t1 = time.time()
    pl = C.place(ev, today=day); tm["place"] = time.time() - t1; t1 = time.time()
    country, cp, cdet = C.ask_country_detailed(ev, today=day); tm["country"] = time.time() - t1; t1 = time.time()
    readings = [x for x in rd["readings"] if x["direction"] != "conflict"]
    TL.rec = []; ex = C.expected(ev, {x["dial"] for x in readings}, C.allowed_dials(pl), today=day); e_raw = {k: v for d in TL.rec for k, v in d.items()}; TL.rec = None; tm["expected"] = time.time() - t1; t1 = time.time()
    sd = {x["dial"]: x["direction"] for x in readings + ex}
    sv = C.severity(ev, sd, today=day) if sd else {}; tm["severity"] = time.time() - t1
    # expected(): also keep the raw e| answers is not possible (function returns the filtered list); the filtered list is what the engine uses
    return {"id": r["id"], "state_text": f"{ev['title']}. {ev['description']}", "day": day, "P": P, "read": rd, "place": pl, "country": country, "country_p": cp, "country_detail": cdet,
            "expected": ex, "e_raw": e_raw, "severity": sv, "teacher": "clef-flash-q4km", "labelled_at": datetime.datetime.now().isoformat(timespec="seconds"), "secs": round(time.time() - t0, 2), "t": {k: round(v, 2) for k, v in tm.items()}}


def work(it):
    while True:
        with lock:
            if not todo or time.time() > t_end: return
            r = todo.pop(0)
        try: rec = label(r)
        except Exception as e:
            with lock: st["err"] += 1; sys.stderr.write(f"ERR {r['id'][:60]} {e!r}\n")
            continue
        with lock:
            open(a.out, "a").write(json.dumps(rec) + "\n"); st["n"] += 1
            if st["n"] % 10 == 0:
                el = time.time() - st["t"]; event(a.job, "running", f"{len(done) + st['n']}/{len(rows)} labelled in total (this chunk +{st['n']}), {el / st['n']:.1f} s/story wall, {st['err']} errors", pid=os.getpid())


event(a.job, "running", f"start {len(todo)} stories, {a.workers} workers", pid=os.getpid())
th = [threading.Thread(target=work, args=(i,)) for i in range(a.workers)]; [t.start() for t in th]; [t.join() for t in th]
el = time.time() - st["t"]; event(a.job, "done", f"{st['n']} stories in {el:.0f}s = {el / max(st['n'], 1):.1f} s/story wall, {st['err']} errors", pid=os.getpid(), win=True)
print(json.dumps({"stories": st["n"], "errors": st["err"], "wall_s": round(el), "s_per_story": round(el / max(st["n"], 1), 2)}))
