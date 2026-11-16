"""Time judge at scale: regex date phrases from the story body, resolved against published_at (rule of t162_time_judge.py). Scores Jev time_recent_p (AUROC).
Run: python3 -I t163_time_judge_scale.py (from projects/world-state) -> runs/pulse/t162/t163_scale.json"""
import json, sqlite3, datetime as dt, re, pathlib, importlib.util
spec = importlib.util.spec_from_file_location("t162", "t162_time_judge.py")
src = open("t162_time_judge.py").read().split("db = sqlite3.connect")[0]
ns = {}; exec(src, ns); resolve = ns["resolve"]
OUT = pathlib.Path("runs/pulse/t162")
PAT = re.compile(r"\b(today|tonight|yesterday|last night|this week|last week|last month|last year|monday|tuesday|wednesday|thursday|friday|saturday|sunday|(?:january|february|march|april|may|june|july|august|september|october|november|december) (?:\d{1,2}|\d{4}))\b", re.I)
L = "/workspace/data/newsreader/labels/"
p_of = {}
for f in ("calibration-1000.jsonl", "t144_read.jsonl"):
    for l in open(L + f):
        r = json.loads(l); a = r.get("answers_call1", {}).get("time_recent")
        if a and a.get("noul") is not None: p_of[r["id"]] = a["noul"]
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
rows = []
for i, p in p_of.items():
    q = db.execute("select body, published from items where id=?", (i,)).fetchone()
    if not q or not q[0] or not q[1]: continue
    pub = dt.datetime.fromisoformat(q[1].replace("Z", "+00:00"))
    ds = [x for x in (resolve(s, pub) for s in PAT.findall(q[0])) if x is not None]
    truth = (1 if min(ds) <= 7 else (0 if min(ds) > 30 else None)) if ds else None
    rows.append({"id": i, "p": p, "truth": truth})
dec = [r for r in rows if r["truth"] is not None]
pos = [r["p"] for r in dec if r["truth"] == 1]; neg = [r["p"] for r in dec if r["truth"] == 0]
auc = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg)) if pos and neg else None
res = {"with_p": len(p_of), "with_body_and_date": len(rows), "decidable": len(dec), "recent": len(pos), "not_recent": len(neg), "auroc": auc}
json.dump({"result": res}, open(OUT / "t163_scale.json", "w"), indent=1); print(res)
