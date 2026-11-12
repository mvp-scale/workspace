"""T110: same labeller as T107 (t106_clef_dials.py) but the story text is headline plus two sentences."""
"""T106: is a cheap local Clef labeller close enough to the engine's full reading to label the pool? Two typed choices per story (local Clef, port 8018, approved in CLAUDE.md, already serving): which of the engine's 39 dials, or none, does the story move; then up or down. Scored against the engine's own stored reading of the same stories (328 questions, data/newsreader/labels/clef-q4km*.jsonl): presence agreement, dial hit, direction agreement. Reference is Clef's full reading, so these are agreement figures.
    NPI=<stories> OUT=<folder> python3 -u t106_clef_dials.py -> <OUT>/t106_clef_dials.json, <OUT>/t106_items.jsonl"""
import os, sys, json, random, re, time, urllib.request, concurrent.futures as cf, collections, pathlib
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
NPI = int(os.environ.get("NPI", 400)); OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t106")); OUT.mkdir(parents=True, exist_ok=True)
ONT = {c["id"]: c for c in json.load(open("/workspace/exports/world-engine-ontology-rules_v2.json"))["conditions"]}
rows = {}
for fn in ("clef-q4km.jsonl", "clef-q4km-w3.jsonl"):
    for l in open("/workspace/data/newsreader/labels/" + fn):
        r = json.loads(l); rows.setdefault(r["id"], r)
R = sorted(rows.values(), key=lambda r: r["id"]); random.Random(5).shuffle(R); R = R[:NPI]
def body(r):
    t = re.sub(r"^#.*?\n", "", r["text"].strip(), count=1).strip(); t = re.sub(r"^Published\s*", "", t)
    sn = re.split(r"(?<=[.!?])\s+", t); return (r["title"].strip() + ". " + " ".join(sn[:2])).strip()  # T110: headline plus two sentences, the Pulse reader's view
D = {k: f"{c['name']}: {c['definition']}" for k, c in ONT.items()}; D["none"] = "The story does not report a change in any of these conditions."
BACKEND = os.environ.get("BACKEND", "clef")
def _key():
    for l in open("/workspace/secrets/vault.env"):
        if l.startswith("TYPESAFE_API_KEY="): return l.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
    return ""
KEY = _key() if BACKEND == "jev" else ""
URL = "https://api.typesafe.ai/v1/systemone" if BACKEND == "jev" else "http://127.0.0.1:8018/v1/systemone"; MODEL = "jev-1.14.0" if BACKEND == "jev" else "clef-flash-q4km"
HDR = {"Content-Type": "application/json", "User-Agent": "kp-t107/0.1", **({"Authorization": "Bearer " + KEY} if KEY else {})}
TOK = [0]
ERR = [0]
def ask(state, instr, crit):
    b = {"state": state, "questions": {"k": {"type": "choice", "instructions": instr, "criteria": crit}}, "model": MODEL}
    last = None
    for attempt in range(4):
        try:
            r = urllib.request.urlopen(urllib.request.Request(URL, json.dumps(b).encode(), HDR), timeout=90); j = json.load(r); a = j["answers"]["k"]; TOK[0] += (j.get("usage") or {}).get("input_tokens", 0); return a["choice"], a.get("confidence")
        except Exception as ex:
            last = ex; ERR[0] += 1; time.sleep(2 + 3 * attempt)
    raise last
def one(r):
    try: return one_(r)
    except Exception: return r["id"], "error", None, None
def one_(r):
    st = "News story:\n" + body(r); dial, c1 = ask(st, "Which one condition of the world does this story report a change in? Choose none if it reports no such change.", D)
    if dial == "none" or dial not in ONT: return r["id"], "none", None, c1
    dr, c2 = ask(st, f"The condition is '{ONT[dial]['name']}'. Does the story report it going up or down? Up means: {ONT[dial]['up_means']}.", {"up": "It goes up: " + ONT[dial]["up_means"], "down": "It goes down: the reverse of that"}); return r["id"], dial, dr, c1
hb.beat("t106-clef-dials" if BACKEND == "clef" else "t107-jev-dials", state="running", where="[5090]" if BACKEND == "clef" else "[HOST]", every_s=180, alive_pid=os.getpid(), why="Is a two-call local Clef labeller close to the engine's full reading (T106)", success="t106_clef_dials.json written", progress=f"0 of {len(R)}")
T0 = time.time(); got = {}
with cf.ThreadPoolExecutor(6) as ex:
    for n, (i, d, dr, c) in enumerate(ex.map(one, R), 1):
        got[i] = (d, dr, c)
        if n % 25 == 0: hb.beat("t106-clef-dials" if BACKEND == "clef" else "t107-jev-dials", progress=f"{n} of {len(R)} at {n / (time.time() - T0):.2f} stories/s")
R = [r for r in R if got[r["id"]][0] != "error"]
ps = []; hit = dirs = dirn = pos = 0; agree = 0; prows = []
for r in R:
    d, dr, c = got[r["id"]]; eng = {x["dial"]: x["direction"] for x in (r.get("readings") or [])}; ps.append((bool(eng), d != "none")); agree += (bool(eng) == (d != "none"))
    if eng:
        pos += 1
        if d in eng:
            hit += 1
            if eng[d] in ("up", "down"): dirn += 1; dirs += (eng[d] == dr)
    prows.append({"id": r["id"], "clef_dial": d, "clef_direction": dr, "engine": eng})
tp = sum(1 for e, c in ps if e and c); fp = sum(1 for e, c in ps if not e and c); fn = sum(1 for e, c in ps if e and not c)
res = {"stories": len(R), "engine_with_reading": pos, "presence_agreement": round(agree / len(R), 4), "presence_precision": round(tp / max(tp + fp, 1), 4), "presence_recall": round(tp / max(tp + fn, 1), 4), "labeller_says_dial_share": round(sum(1 for e, c in ps if c) / len(R), 4), "dial_hit_of_engine_readings": round(hit / max(pos, 1), 4), "direction_agreement_when_dial_hit": round(dirs / max(dirn, 1), 4), "direction_n": dirn, "backend": BACKEND, "call_errors_retried": ERR[0], "stories_failed": sum(1 for v in got.values() if v[0] == "error"), "input_tokens": TOK[0], "seconds": round(time.time() - T0), "stories_per_s": round(len(R) / (time.time() - T0), 3), "note": "Reference is the engine's stored 328-question Clef reading; agreement, not accuracy. Direction scored only where the labeller's dial is one of the engine's dials for the story."}
json.dump(res, open(OUT / "t106_clef_dials.json", "w"), indent=1)
with open(OUT / "t106_items.jsonl", "w") as f:
    for x in prows: f.write(json.dumps(x) + "\n")
hb.finish("t106-clef-dials" if BACKEND == "clef" else "t107-jev-dials", "done", progress=f"{len(R)} stories"); print(json.dumps(res, indent=1))
