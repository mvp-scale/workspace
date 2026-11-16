"""Time judge from publish dates. Truth: recent if a stated date resolves within 7 days before published_at; not recent if every resolved date is >30 days before; else undecided. Scores Jev time_recent_p (AUROC).
Run: python3 t162_time_judge.py -> runs/pulse/t162/t162_time_judge.json"""
import json, sqlite3, datetime as dt, re, pathlib
OUT = pathlib.Path("runs/pulse/t162"); OUT.mkdir(parents=True, exist_ok=True)
MON = {m: i + 1 for i, m in enumerate("january february march april may june july august september october november december".split())}
WD = {d: i for i, d in enumerate("monday tuesday wednesday thursday friday saturday sunday".split())}
def resolve(s, pub):
    """days before publish of the stated date, or None if it cannot be placed"""
    s = s.lower().strip()
    if s in ("today", "tonight", "this morning", "this evening"): return 0
    if s == "yesterday": return 1
    if s in ("this week", "last night"): return 3
    if s == "last week": return 10
    if s in ("last month",): return 35
    if s in ("last year",): return 400
    if s in WD:
        back = (pub.weekday() - WD[s]) % 7
        return back if back else 7   # same weekday = a week ago, upcoming days read as 0..6 away: use distance
    m = re.fullmatch(r"([a-z]+) (\d{4})", s)
    if m and m[1] in MON:
        try: d = dt.date(int(m[2]), MON[m[1]], 15)
        except ValueError: return None
        return abs((pub.date() - d).days)
    m = re.fullmatch(r"([a-z]+) (\d{1,2})", s)
    if m and m[1] in MON:
        try: d = dt.date(pub.year, MON[m[1]], int(m[2]))
        except ValueError: return None
        return abs((pub.date() - d).days)
    return None
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
rows = []
for l in open("runs/pulse/t141/unified_100.jsonl"):
    r = json.loads(l); p = db.execute("select published from items where id=?", (r["id"],)).fetchone()
    if not p or not p[0]: continue
    pub = dt.datetime.fromisoformat(p[0].replace("Z", "+00:00"))
    ds = [x for x in (resolve(s, pub) for s in r["tools"]["stated_dates"]) if x is not None]
    truth = None
    if ds: truth = 1 if min(ds) <= 7 else (0 if min(ds) > 30 else None)
    rows.append({"id": r["id"], "p": r["jev"]["time_recent_p"], "truth": truth, "stated": r["tools"]["stated_dates"]})
dec = [r for r in rows if r["truth"] is not None and r["p"] is not None]
pos = [r["p"] for r in dec if r["truth"] == 1]; neg = [r["p"] for r in dec if r["truth"] == 0]
auc = (sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))) if pos and neg else None
res = {"stories": len(rows), "decidable": len(dec), "recent": len(pos), "not_recent": len(neg), "auroc_jev_time_recent_p": auc}
json.dump({"result": res, "rows": rows}, open(OUT / "t162_time_judge.json", "w"), indent=1); print(res)
