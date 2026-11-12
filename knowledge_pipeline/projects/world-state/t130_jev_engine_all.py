"""T130: hosted Jev answers the engine's 328 questions (the engine's own reader, set_reader) on N engine stories already read by Clef; presence and direction of Jev's derived readings are compared with Clef's stored readings. Owner allowed hosted Jev (decision D34); text is public crawled news from the queue, as in D25.
    N=<stories> OUT=<folder> then run from /workspace/probes/world-engine:  WE_RULES=rules_v2 /workspace/kev/.venv/bin/python -I <this file> -> <OUT>/t130_jev_engine.json"""
import os, sys, json, time, random, threading, pathlib, urllib.request, collections, concurrent.futures as cf
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine")
import classify as C
N = int(os.environ.get("N", 100)); OUT = pathlib.Path(os.environ.get("OUT", "/workspace/knowledge_pipeline/projects/world-state/runs/pulse/t130")); OUT.mkdir(parents=True, exist_ok=True)
KEY = ""
for l in open("/workspace/secrets/vault.env"):
    if l.startswith("TYPESAFE_API_KEY="): KEY = l.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
C.O.set_reader("https://api.typesafe.ai", "jev-1.14.0", KEY, "jev-1.14.0")
TOK = [0]; CALLS = [0]; lock = threading.Lock()
def _counting_call(ep, model, key, state, qs, tries=2):   # same request as offline._call, also adds up the input tokens
    body = {"state": state, "questions": qs, **({"model": model} if model else {})}
    hdr = {"Content-Type": "application/json", "User-Agent": "kp-t130/0.1", **({"Authorization": f"Bearer {key}"} if key else {})}
    req = urllib.request.Request(ep + "/v1/systemone", json.dumps(body).encode(), hdr)
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=300) as r: j = json.load(r)
            with lock: TOK[0] += (j.get("usage") or {}).get("input_tokens", 0); CALLS[0] += 1
            return j["answers"]
        except Exception:
            if attempt == tries - 1: raise
C.O._call = _counting_call
MODE = os.environ.get("MODE", "stored"); RAW = os.environ.get("ROWS", "/workspace/data/newsreader/labels/jev-engine-stored.jsonl")
if MODE == "stored":
    S = [json.loads(l) for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl")]
    if N: random.Random(130).shuffle(S); S = S[:N]
else:   # queue stories the engine has not read, round-robin across outlets as label.py does
    import sqlite3
    done = {json.loads(l)["id"] for f_ in ("clef-q4km.jsonl", "clef-q4km-ext.jsonl") for l in open("/workspace/data/newsreader/labels/" + f_)}
    rows_ = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True).execute("SELECT id, source, region, title, body FROM items WHERE depth='full' AND body IS NOT NULL ORDER BY found_at").fetchall()
    by = {}
    for r_ in rows_:
        if r_[0] not in done: by.setdefault(r_[1], []).append(r_)
    todo_ = []
    while len(todo_) < N and any(by.values()):
        for k_ in list(by):
            if by[k_]: todo_.append(by[k_].pop())
    S = [{"id": r_[0], "source": r_[1], "title": r_[3], "text": " ".join(r_[4].split()[:1200])} for r_ in todo_[:N]]
def direction(rd):
    w = collections.Counter()
    for x in rd or []: w[x["direction"]] += x.get("strength", 1.0)
    return None if w["up"] == w["down"] else ("up" if w["up"] > w["down"] else "down")
rows = []
def one(r):
    try:
        P = C.ask({"published_at": time.strftime("%Y-%m-%d"), "title": r["title"], "description": r["text"]}); rd = C.read(P)["readings"]
        return {"id": r["id"], "title": r["title"], "text": r["text"], "jev_readings": rd, "clef_readings": r.get("readings") or []}
    except Exception as e: return {"id": r["id"], "error": repr(e)[:150]}
T0 = time.time()
with cf.ThreadPoolExecutor(int(os.environ.get("CONC", 6))) as ex: rows = list(ex.map(one, S))
ok = [r for r in rows if "error" not in r]; pj = [bool(r["jev_readings"]) for r in ok]; pc = [bool(r["clef_readings"]) for r in ok]
tp = sum(a and b for a, b in zip(pj, pc)); fp = sum(a and not b for a, b in zip(pj, pc)); fn = sum(b and not a for a, b in zip(pj, pc))
both = [r for r in ok if r["jev_readings"] and r["clef_readings"] and direction(r["jev_readings"]) and direction(r["clef_readings"])]
dir_ag = sum(direction(r["jev_readings"]) == direction(r["clef_readings"]) for r in both)
dials = sum(r["jev_readings"][0]["dial"] in {x["dial"] for x in r["clef_readings"]} for r in ok if r["jev_readings"] and r["clef_readings"])
res = {"mode": MODE, "rows_file": RAW, "stories_asked": len(S), "stories_read": len(ok), "failed": len(rows) - len(ok), "presence_agreement": round(sum(a == b for a, b in zip(pj, pc)) / max(len(ok), 1), 4),
       "presence_precision": round(tp / max(tp + fp, 1), 4), "presence_recall": round(tp / max(tp + fn, 1), 4), "clef_presence_share": round(sum(pc) / max(len(ok), 1), 4), "jev_presence_share": round(sum(pj) / max(len(ok), 1), 4),
       "direction_agreement": round(dir_ag / max(len(both), 1), 4), "direction_n": len(both), "top_dial_in_clef_dials": dials, "input_tokens": TOK[0], "calls": CALLS[0], "cost_usd_at_0_042_per_million": round(TOK[0] * 0.042 / 1e6, 3),
       "seconds": round(time.time() - T0), "note": "Reference is Clef's stored 328-question reading of the same stories; agreement, not accuracy. Jev answers the same 328 questions and the engine derives readings from them."}
json.dump(res, open(OUT / "t130_jev_engine.json", "w"), indent=1); open(RAW, "w").write("\n".join(json.dumps(r) for r in rows)); print(json.dumps(res, indent=1))
