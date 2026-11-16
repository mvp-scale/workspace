"""T172 phase 1: Jev (hosted) labels news sentences from queue bodies with the L2224 function_subjective question. Resumable (appends rows to the jsonl), time-capped.
Run: N=20000 CAP_MIN=50 OUT=<dir> /workspace/kev/.venv/bin/python -I t172_label_sentences.py"""
import os, re, json, time, random, sqlite3, urllib.request, concurrent.futures as cf, pathlib, collections
OUT = pathlib.Path(os.environ["OUT"]); OUT.mkdir(parents=True, exist_ok=True); N = int(os.environ.get("N", 20000)); CAP = float(os.environ.get("CAP_MIN", 50)) * 60; ROWS = OUT / "t172_rows.jsonl"
KEY = ""
for l in open("/workspace/secrets/vault.env"):
    if l.startswith("TYPESAFE_API_KEY="): KEY = l.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
Q = {"function_subjective": {"type": "noul", "instructions": "Does this sentence express the writer's own opinion, feeling, belief or judgment rather than stating facts?", "criteria": {"true": "The sentence shows a personal view: an opinion, emotion, evaluation, speculation or persuasion.", "false": "The sentence states facts, events or neutral quotes."}}}
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); rng = random.Random(172)
ids = [r[0] for r in db.execute("select id from items where body is not null")]; rng.shuffle(ids); S = []
for i in ids:
    b = db.execute("select body from items where id=?", (i,)).fetchone()[0]
    ss = [s.strip() for s in re.split(r"(?<=[.!?])\s+", b) if 40 <= len(s.strip()) <= 300]
    for k, s in enumerate(rng.sample(ss, min(3, len(ss)))): S.append({"id": f"q:{i}:{k}", "text": s})
    if len(S) >= N: break
S = S[:N]; done = set()
if ROWS.exists():
    for l in open(ROWS): done.add(json.loads(l)["id"])
todo = [x for x in S if x["id"] not in done]; tok = collections.Counter(); t0 = time.time(); print("todo", len(todo), "done", len(done), flush=True)
def one(x):
    if time.time() - t0 > CAP: return None
    body = {"state": x["text"], "questions": Q, "model": "jev-1.14.0"}; last = None
    for a in range(3):
        try:
            req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json", "User-Agent": "kp-t172/0.1", "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=120) as r: j = json.load(r)
            tok["in"] += (j.get("usage") or {}).get("input_tokens", 0); return {"id": x["id"], "text": x["text"], "p": j["answers"]["function_subjective"]["noul"]}
        except Exception as e: last = e; time.sleep(2 + 3 * a)
    return {"id": x["id"], "error": repr(last)[:150]}
n = err = 0
with cf.ThreadPoolExecutor(8) as ex, open(ROWS, "a") as f:
    for r in ex.map(one, todo):
        if r is None: continue
        if "error" in r: err += 1; continue
        f.write(json.dumps(r) + "\n"); n += 1
        if n % 1000 == 0: f.flush(); print(n, round(time.time() - t0), "s, tokens", tok["in"], flush=True)
print(json.dumps({"labelled_now": n, "errors": err, "seconds": round(time.time() - t0), "input_tokens": tok["in"], "cost_usd_at_0_042_per_million": round(tok["in"] * 0.042 / 1e6, 3)}))
