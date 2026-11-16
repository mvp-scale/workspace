"""T174: Jev time question reworded and given the publish date, scored on the strict publish-date truth of t164_time_judge_strict.py (ledger L2208). Prediction in ledger L2234.
Run: N=<limit> OUT=<json> /workspace/kev/.venv/bin/python -I t174_time_reword.py  (from projects/world-state)"""
import os, re, json, time, random, sqlite3, urllib.request, concurrent.futures as cf, collections, datetime as dt
N = int(os.environ.get("N", 0)); OUT = os.environ["OUT"]; os.makedirs(os.path.dirname(OUT), exist_ok=True)
KEY = ""
for l in open("/workspace/secrets/vault.env"):
    if l.startswith("TYPESAFE_API_KEY="): KEY = l.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
src = open("t164_time_judge_strict.py").read().split("db = sqlite3.connect")[0]; ns = {"__name__": "x"}; exec(src, ns)
t135 = open("t135_full_read.py").read(); b0 = t135.index("def build_state"); b1 = t135.index("qh = lambda"); ns2 = {"re": re}; exec(t135[b0:b1], ns2); build_state = ns2["build_state"]
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); rows = []
for i, p in ns["p_of"].items():
    q = db.execute("select title, body, published from items where id=?", (i,)).fetchone()
    if not q or not q[1] or not q[2]: continue
    pub = dt.datetime.fromisoformat(q[2].replace("Z", "+00:00"))
    ds = [x for x in (ns["days_before"](s, pub) for s in ns["PAT"].findall(q[1])) if x is not None]
    truth = (1 if min(ds) <= 7 else (0 if min(ds) > 30 else None)) if ds else None
    if truth is not None: rows.append({"id": i, "title": q[0] or "", "body": q[1], "published": q[2], "truth": truth, "p_old": p})
rows.sort(key=lambda r: r["id"])
if N: random.Random(174).shuffle(rows); rows = rows[:N]
Q = {"time_window": {"type": "noul", "instructions": "Using the publish date, is the main event of this story from the 3 days before publication?", "criteria": {"true": "The main event happened or was announced within 3 days before the publish date.", "false": "The main event is older, ongoing background or undated."}}}
tok = collections.Counter()
def one(r):
    st, _ = build_state(r["title"], " ".join(r["body"].split()[:1200]), r["published"]); body = {"state": st, "questions": Q, "model": "jev-1.14.0"}; last = None
    for a in range(3):
        try:
            req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json", "User-Agent": "kp-t174/0.1", "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=300) as rr: j = json.load(rr)
            tok["in"] += (j.get("usage") or {}).get("input_tokens", 0); return {"id": r["id"], "truth": r["truth"], "p_old": r["p_old"], "p_new": j["answers"]["time_window"]["noul"]}
        except Exception as e: last = e; time.sleep(2 + 3 * a)
    return {"id": r["id"], "error": repr(last)[:150]}
with cf.ThreadPoolExecutor(8) as ex: out = list(ex.map(one, rows))
ok = [r for r in out if "error" not in r]
def auc(f):
    P = [f(r) for r in ok if r["truth"] == 1]; Nn = [f(r) for r in ok if r["truth"] == 0]; return sum((a > b) + 0.5 * (a == b) for a in P for b in Nn) / (len(P) * len(Nn))
rng = random.Random(1); bs = []
for _ in range(500):
    s = [rng.choice(ok) for _ in ok]; P = [r["p_new"] for r in s if r["truth"] == 1]; Nn = [r["p_new"] for r in s if r["truth"] == 0]
    if P and Nn: bs.append(sum((a > b) + 0.5 * (a == b) for a in P for b in Nn) / (len(P) * len(Nn)))
bs.sort(); res = {"n": len(rows), "ok": len(ok), "errors": len(out) - len(ok), "recent": sum(r["truth"] == 1 for r in ok), "not_recent": sum(r["truth"] == 0 for r in ok), "auc_new": round(auc(lambda r: r["p_new"]), 3), "ci95_new": [round(bs[int(0.025 * len(bs))], 3), round(bs[int(0.975 * len(bs)) - 1], 3)] if len(bs) > 100 else None, "auc_old_same_rows": round(auc(lambda r: r["p_old"]), 3), "input_tokens": tok["in"], "cost_usd_at_0_042_per_million": round(tok["in"] * 0.042 / 1e6, 3)}
json.dump({"result": res, "rows": out}, open(OUT, "w")); print(json.dumps(res))
