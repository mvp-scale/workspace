"""Hosted Jev bulk labels with the ENGINE'S OWN questions (D-0042), same record schema as clef_label.py so Jev and Clef answers compare per question.
Jev sees only title + description[:250] (state 'News item (published D; today is D):\\ntitle. desc'). Price $0.042 per million INPUT tokens, output free (demo/models.json public tariff).
  /workspace/kev/.venv/bin/python newsreader/bitmob/jev_label.py IN.jsonl OUT.jsonl [--n N] [--offset K] [--workers W] [--minutes M] [--cap-usd 5.5] [--ids FILE] [--job jev-label]
  ... --audit OUT.jsonl      audit an output file
Calls: ONE combined call per story for the noul questions of ask() (328) + place() (choice c + 48 y|) served to the engine functions through a cache; expected(), severity() and the country steps run the engine functions unchanged (their own calls).
Resumable by id; STOP file checked per story; stops when the dollar cap (summed over data/jev-labels/*.jsonl) is reached. Never labels an id in data/clef-labels/test_in.jsonl."""
import os, sys, json, time, argparse, datetime, threading, glob, urllib.request
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob"]
import classify as C, offline as O, backends
from progress import event
PROMPT_VERSION = "engine-full-v1: ask328+place49 one combined call; expected/severity/country engine calls unchanged; jev-1.14.0"
PRICE_IN = 0.042 / 1e6      # USD per input token; output free (public tariff)
STOP = "/workspace/data/progress/STOP"; JD = "/workspace/data/jev-labels"
B = backends.BACKENDS["jev"]; tls = threading.local(); TEST_IDS = {json.loads(l)["id"] for l in open("/workspace/data/clef-labels/test_in.jsonl")}
ap = argparse.ArgumentParser(); ap.add_argument("inp", nargs="?"); ap.add_argument("out", nargs="?"); ap.add_argument("--n", type=int, default=50); ap.add_argument("--offset", type=int, default=0)
ap.add_argument("--workers", type=int, default=6); ap.add_argument("--minutes", type=float, default=40); ap.add_argument("--cap-usd", type=float, default=5.5); ap.add_argument("--ids"); ap.add_argument("--job", default="jev-label"); ap.add_argument("--audit")
a = ap.parse_args()


def real_call(state, qs):
    body = {"state": state, "questions": qs, **({"model": B["model"]} if B["model"] else {})}
    hdr = {"Content-Type": "application/json", "User-Agent": "jev-demo/0.1", **({"Authorization": f"Bearer {B['key']}"} if B["key"] else {})}
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(B["url"].rstrip("/") + "/v1/systemone", json.dumps(body).encode(), hdr), timeout=300) as r: d = json.load(r)
            tls.model = d.get("model") or getattr(tls, "model", None); u = d.get("usage") or {}
            tls.tin += u.get("input_tokens", 0); tls.tout += u.get("output_tokens", 0); tls.calls += 1
            return d["answers"]
        except Exception:
            if attempt == 2: raise
            time.sleep(2 * (attempt + 1))


def cached_call(state, qs):
    out = _cached_call(state, qs); L = getattr(tls, "rec", None)
    if L is not None: L.update({k: (v.get("noul") if "noul" in v else v.get("probabilities")) for k, v in out.items()})
    return out


def _cached_call(state, qs):      # serve from the combined prefetch when the engine asks the same question text; otherwise a real call
    cache = tls.cache; keys = {k: json.dumps(q, sort_keys=True) for k, q in qs.items()}
    if state == tls.state and all(keys[k] in cache for k in qs): return {k: cache[keys[k]] for k in qs}
    return real_call(state, qs)


def prefetch(state, ev):
    qs = {k: {"type": "noul", "instructions": q} for k, q in C.QS.items()}
    qs["c"] = {"type": "choice", "instructions": "Which area is this story mainly about?", "criteria": {d["id"]: d["definition"] for d in C.DOMAINS}}
    qs.update({"y|" + d["id"]: {"type": "noul", "instructions": f"Is this story about {d['name']}? ({d['definition']})"} for d in C.DOMAINS if d["id"] != "other"})
    ans = real_call(state, qs); tls.cache = {json.dumps(q, sort_keys=True): ans[k] for k, q in qs.items() if k in ans}; tls.state = state
    return len(qs), len(ans)


O.call = cached_call


def label(r):
    day = r.get("date") or datetime.date.today().isoformat(); d250 = (r.get("description") or "")[:250]; ev = {"evidence_id": r["id"], "published_at": day, "title": r["title"], "description": d250}
    state = f"News item (published {day}; today is {day}):\n{ev['title']}. {ev['description']}"; tls.tin = tls.tout = tls.calls = 0; tls.model = None; t0 = time.time()
    nq, na = prefetch(state, ev)
    if na != nq: raise RuntimeError(f"combined call returned {na} of {nq} answers")
    P = C.ask(ev, today=day); rd = C.read(P); pl = C.place(ev, today=day)
    country, cp, cdet = C.ask_country_detailed(ev, today=day)
    readings = [x for x in rd["readings"] if x["direction"] != "conflict"]
    tls.rec = {}
    try: ex = C.expected(ev, {x["dial"] for x in readings}, C.allowed_dials(pl), today=day); ex_raw = tls.rec
    finally: tls.rec = None
    e_raw = {k: v for k, v in ex_raw.items() if k.startswith("e|") or k == "done"}
    sd = {x["dial"]: x["direction"] for x in readings + ex}; sv = C.severity(ev, sd, today=day) if sd else {}
    return {"id": r["id"], "state_text": f"{ev['title']}. {ev['description']}", "day": day, "P": P, "read": rd, "place": pl, "country": country, "country_p": cp, "country_detail": cdet,
            "expected": ex, "e_raw": e_raw, "severity": sv, "teacher": "jev", "teacher_model": tls.model or B["model"], "prompt_version": PROMPT_VERSION,
            "labelled_at": datetime.datetime.now().isoformat(timespec="seconds"), "secs": round(time.time() - t0, 2), "tokens": {"input": tls.tin, "output": tls.tout, "calls": tls.calls}}


def spent():
    t = 0
    for f in glob.glob(f"{JD}/*.jsonl"):
        for l in open(f):
            try: t += json.loads(l).get("tokens", {}).get("input", 0)
            except Exception: pass
    return t * PRICE_IN


def audit(path):
    R = [json.loads(l) for l in open(path) if l.strip()]; bad = {}
    def chk(name, ok, rid): 
        if not ok: bad.setdefault(name, []).append(rid[:50])
    ids = [r["id"] for r in R]; dom = {d["id"] for d in C.DOMAINS}; ctry = {c for c, _ in C.countries()} | {"global"}
    for r in R:
        i = r["id"]; P = r["P"]
        chk("P has 328 answers", len(P) >= 328, i); chk("P in [0,1]", all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in P.values()), i); chk("P not constant", len({round(v, 2) for v in P.values()}) > 3, i)
        chk("place has 49 domains with choice+yes", len(r["place"]) == 49 and all(0 <= x["p_choice"] <= 1 and 0 <= x["p_yes"] <= 1 for x in r["place"]) and {x["id"] for x in r["place"]} == dom, i)
        chk("a domain is tagged", any(x["tagged"] for x in r["place"]), i); chk("country valid", r["country"] in ctry, i); chk("e_raw present", bool(r["e_raw"]) and "done" in r["e_raw"], i)
        chk("severity covers every reading+expected", all(d in r["severity"] for d in {x["dial"] for x in r["read"]["readings"] if x["direction"] != "conflict"} | {x["dial"] for x in r["expected"]}), i)
        chk("not a test id", i not in TEST_IDS, i); chk("state_text non-empty", len(r["state_text"]) > 20, i); chk("teacher jev", r["teacher"] == "jev" and r["teacher_model"], i)
    chk("no duplicate ids", len(ids) == len(set(ids)), "dups")
    tin = sum(r["tokens"]["input"] for r in R); res = {"file": path, "n": len(R), "failed_checks": {k: len(v) for k, v in bad.items()}, "examples": {k: v[:2] for k, v in bad.items()}, "input_tokens": tin,
           "usd": round(tin * PRICE_IN, 4), "usd_per_1000": round(1000 * tin * PRICE_IN / max(len(R), 1), 3), "s_per_story_median": sorted(r["secs"] for r in R)[len(R) // 2] if R else None, "calls_per_story": round(sum(r["tokens"]["calls"] for r in R) / max(len(R), 1), 2)}
    print(json.dumps(res)); return res


if a.audit: audit(a.audit); sys.exit(0)
os.makedirs(JD, exist_ok=True)
rows = [json.loads(l) for l in open(a.inp)]
if a.ids: want = [l.strip() for l in open(a.ids) if l.strip()]; byid = {r["id"]: r for r in rows}; rows = [byid[i] for i in want if i in byid]
rows = rows[a.offset:a.offset + a.n]
assert not any(r["id"] in TEST_IDS for r in rows), "frozen test id in input"
done = {json.loads(l)["id"] for l in open(a.out) if l.strip()} if os.path.exists(a.out) else set()
todo = [r for r in rows if r["id"] not in done]; lock = threading.Lock(); st = {"n": 0, "err": 0, "t": time.time(), "usd0": spent(), "usd": 0.0, "why": "end of list"}; t_end = time.time() + 60 * a.minutes


def work():
    while True:
        with lock:
            if os.path.exists(STOP): st["why"] = "STOP file"; return
            if time.time() > t_end: st["why"] = "minutes cap"; return
            if st["usd0"] + st["usd"] >= a.cap_usd: st["why"] = "dollar cap"; return
            if not todo: return
            r = todo.pop(0)
        try: rec = label(r)
        except Exception as e:
            with lock: st["err"] += 1; sys.stderr.write(f"ERR {r['id'][:60]} {e!r}\n")
            if st["err"] > 25: st["why"] = "too many errors"; return
            continue
        with lock:
            open(a.out, "a").write(json.dumps(rec) + "\n"); st["n"] += 1; st["usd"] += rec["tokens"]["input"] * PRICE_IN
            if st["n"] % 20 == 0: event(a.job, "running", f"{st['n']} stories, ${st['usd0'] + st['usd']:.2f} total spent, {(time.time() - st['t']) / st['n']:.1f} s/story wall", pid=os.getpid())


event(a.job, "running", f"start {len(todo)} stories, {a.workers} workers, ${st['usd0']:.2f} spent so far, cap ${a.cap_usd}", pid=os.getpid())
th = [threading.Thread(target=work) for _ in range(a.workers)]; [t.start() for t in th]; [t.join() for t in th]
el = time.time() - st["t"]; msg = f"{st['n']} stories in {el:.0f}s, ${st['usd']:.3f} this run (${st['usd0'] + st['usd']:.3f} total), {st['err']} errors, stopped: {st['why']}"
event(a.job, "done" if st["err"] <= 25 else "failed", msg, pid=os.getpid(), win=True); print(msg)
