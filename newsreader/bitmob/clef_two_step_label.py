"""Two-step labeller on the NORMAL Clef (Q4_K_M, :8018), round 6 (D-0038, F-0047 v2 rule). Same client, state text and engine pipeline as clef_label.py; only the 328-question ask() is replaced:
  step 1: the 78 screen questions s2|dial|dir ('Does the story report any of these: <attribute (definition)>; ...?') + the 10 meta questions (g|*, s|*, x|*) in ONE call (88 questions);
  step 2: only those 20-question blocks of the full battery (classify.QS order, chunks of 20, the very same requests ask() sends) that contain an attribute question of a flagged dial|direction (screen >= threshold, default 0.20).
  Attribute questions in blocks that were not asked get the value 0.01 (F-0047 v2). Meta answers come from step 1 (the full battery would send them in its last block).
  Then read(P), place(), ask_country_detailed(), expected() (e_raw captured), severity() exactly as clef_label.py. Record = clef_label.py schema + two_step, screen, blocks_asked, blocks_total, requests, threshold.
  /workspace/kev/.venv/bin/python newsreader/bitmob/clef_two_step_label.py IN.jsonl OUT.jsonl [--n N] [--offset K] [--minutes M] [--workers 4] [--threshold 0.20]
Resumable; STOP file /workspace/data/progress/STOP is checked before launch and per story; only calls Clef :8018 (never stops it)."""
import os, sys, json, time, argparse, datetime, threading
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob"]
import classify as C, offline as O, backends
from progress import event
b = backends.BACKENDS["clef-flash-q4km"]; O.set_reader(b["url"], b.get("model", ""), b.get("key", ""), "clef-flash-q4km")
ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out"); ap.add_argument("--n", type=int, default=50); ap.add_argument("--workers", type=int, default=2)
ap.add_argument("--minutes", type=float, default=45); ap.add_argument("--offset", type=int, default=0); ap.add_argument("--job", default="clef-2step"); ap.add_argument("--threshold", type=float, default=0.20); ap.add_argument("--meta_blocks", action="store_true", help="answer g|/s|/x| in their normal battery blocks (same requests as the full battery) instead of in the screen call")
a = ap.parse_args()
if os.path.exists("/workspace/data/progress/STOP"): print("STOP file set: not launching"); sys.exit(1)
t_end = time.time() + 60 * a.minutes
rows = [json.loads(l) for l in open(a.inp)][a.offset:a.offset + a.n]
done = set()
if os.path.exists(a.out): done = {json.loads(l)["id"] for l in open(a.out) if l.strip()}
todo = [r for r in rows if r["id"] not in done]; lock = threading.Lock(); st = {"n": 0, "err": 0, "t": time.time()}


_orig_call = O.call; TL = threading.local()
def _rec_call(state, qs):
    TL.nreq = getattr(TL, "nreq", 0) + 1; a = _orig_call(state, qs); L = getattr(TL, "rec", None)
    if L is not None: L.append({k: (v.get("noul") if "noul" in v else v.get("probabilities")) for k, v in a.items()})
    return a
O.call = _rec_call


def screen_q(d, dirn): return "Does the story report any of these: " + "; ".join(f"{x['attribute']} ({x['definition'].strip().rstrip('.')})" for x in C.ATTRS[(d, dirn)]) + "?"
SCREEN = {f"s2|{d}|{dirn}": screen_q(d, dirn) for (d, dirn) in C.ATTRS}
NAMES = list(C.QS); BLOCKS = [NAMES[j:j + 20] for j in range(0, len(NAMES), 20)]; META = [k for k in NAMES if not k.startswith("a|")]


def ask2(ev, day):
    state = f"News item (published {ev['published_at']}; today is {day}):\n{ev['title']}. {ev['description']}"; qs = dict(SCREEN) if a.meta_blocks else {**SCREEN, **{k: C.QS[k] for k in META}}
    a1 = O.call(state, {k: {"type": "noul", "instructions": q} for k, q in qs.items()}); screen = {k[3:]: float(a1[k]["noul"]) for k in SCREEN}
    P = {} if a.meta_blocks else {k: float(a1[k]["noul"]) for k in META}; flagged = {k for k, v in screen.items() if v >= a.threshold}; P.update({k: 0.01 for k in NAMES if k.startswith("a|")}); asked = 0
    for blk in BLOCKS:
        if not (a.meta_blocks and any(k in META for k in blk)) and not any(k.startswith("a|") and "|".join(k.split("|")[1:3]) in flagged for k in blk): continue
        asked += 1; a2 = O.call(state, {k: {"type": "noul", "instructions": C.QS[k]} for k in blk}); P.update({k: float(a2[k]["noul"]) for k in a2})
    return P, screen, asked


def story_ev(r):
    day = r.get("date") or datetime.date.today().isoformat(); d250 = (r.get("description") or "")[:250]
    return {"evidence_id": r["id"], "published_at": day, "title": r["title"], "description": d250}, day       # same state text as build_trainset: title. desc[:250]


def label(r):
    ev, day = story_ev(r); t0 = time.time(); tm = {}
    TL.nreq = 0; P, screen, asked = ask2(ev, day); rd = C.read(P); tm["ask"] = time.time() - t0; nreq_ask = TL.nreq; t1 = time.time()
    pl = C.place(ev, today=day); tm["place"] = time.time() - t1; t1 = time.time()
    country, cp, cdet = C.ask_country_detailed(ev, today=day); tm["country"] = time.time() - t1; t1 = time.time()
    readings = [x for x in rd["readings"] if x["direction"] != "conflict"]
    TL.rec = []; ex = C.expected(ev, {x["dial"] for x in readings}, C.allowed_dials(pl), today=day); e_raw = {k: v for d in TL.rec for k, v in d.items()}; TL.rec = None; tm["expected"] = time.time() - t1; t1 = time.time()
    sd = {x["dial"]: x["direction"] for x in readings + ex}
    sv = C.severity(ev, sd, today=day) if sd else {}; tm["severity"] = time.time() - t1
    # expected(): also keep the raw e| answers is not possible (function returns the filtered list); the filtered list is what the engine uses
    return {"id": r["id"], "state_text": f"{ev['title']}. {ev['description']}", "day": day, "P": P, "read": rd, "place": pl, "country": country, "country_p": cp, "country_detail": cdet,
            "expected": ex, "e_raw": e_raw, "severity": sv, "teacher": "clef-flash-q4km", "two_step": True, "threshold": a.threshold, "meta_blocks": a.meta_blocks, "screen": {k: round(v, 3) for k, v in screen.items()}, "blocks_asked": asked, "blocks_total": len(BLOCKS), "requests_ask": nreq_ask + 0, "labelled_at": datetime.datetime.now().isoformat(timespec="seconds"), "secs": round(time.time() - t0, 2), "t": {k: round(v, 2) for k, v in tm.items()}}


def work(it):
    while True:
        with lock:
            if not todo or time.time() > t_end or os.path.exists("/workspace/data/progress/STOP"): return
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
