"""Time judge, strict rule (pre-registered in ledger L2208). Evidence: today/tonight/yesterday/last night/this week, month+day, month+year, resolved to the nearest PAST date. Weekdays, last week/month/year and future dates dropped.
Run: python3 -I t164_time_judge_strict.py (from projects/world-state) -> runs/pulse/t162/t164_strict.json"""
import json, sqlite3, datetime as dt, re, pathlib, random
OUT = pathlib.Path("runs/pulse/t162")
MON = {m: i + 1 for i, m in enumerate("january february march april may june july august september october november december".split())}
REL = {"today": 0, "tonight": 0, "yesterday": 1, "last night": 1, "this week": 3}
PAT = re.compile(r"\b(today|tonight|yesterday|last night|this week|(?:january|february|march|april|may|june|july|august|september|october|november|december) (?:\d{1,2}(?:, \d{4})?|\d{4}))\b", re.I)
def days_before(s, pub):
    s = s.lower()
    if s in REL: return REL[s]
    m = re.fullmatch(r"([a-z]+) (\d{4})", s)
    try:
        if m: d = dt.date(int(m[2]), MON[m[1]], 15)
        else:
            m = re.fullmatch(r"([a-z]+) (\d{1,2})(?:, (\d{4}))?", s)
            y = int(m[3]) if m[3] else pub.year
            d = dt.date(y, MON[m[1]], int(m[2]))
            if not m[3] and d > pub.date(): d = dt.date(y - 1, MON[m[1]], int(m[2]))   # no year given: nearest past date
    except ValueError: return None
    n = (pub.date() - d).days
    return n if n >= 0 else None                                                 # future dates dropped
L = "/workspace/data/newsreader/labels/"; p_of = {}
for f in ("calibration-1000.jsonl", "t144_read.jsonl"):
    for l in open(L + f):
        r = json.loads(l); a = r.get("answers_call1", {}).get("time_recent")
        if a and a.get("noul") is not None: p_of[r["id"]] = a["noul"]
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); rows = []
for i, p in p_of.items():
    q = db.execute("select body, published from items where id=?", (i,)).fetchone()
    if not q or not q[0] or not q[1]: continue
    pub = dt.datetime.fromisoformat(q[1].replace("Z", "+00:00"))
    ds = [x for x in (days_before(s, pub) for s in PAT.findall(q[0])) if x is not None]
    truth = (1 if min(ds) <= 7 else (0 if min(ds) > 30 else None)) if ds else None
    rows.append({"id": i, "p": p, "truth": truth})
def auc(rs):
    pos = [r["p"] for r in rs if r["truth"] == 1]; neg = [r["p"] for r in rs if r["truth"] == 0]
    return sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg)) if pos and neg else None
dec = [r for r in rows if r["truth"] is not None]; random.seed(0); bs = []
for _ in range(1000):
    a = auc([random.choice(dec) for _ in dec])
    if a is not None: bs.append(a)
bs.sort(); res = {"with_body_and_date": len(rows), "decidable": len(dec), "recent": sum(r["truth"] == 1 for r in dec), "not_recent": sum(r["truth"] == 0 for r in dec), "auroc": auc(dec), "ci95": [bs[25], bs[974]] if len(bs) > 900 else None}
json.dump({"result": res}, open(OUT / "t164_strict.json", "w"), indent=1); print(res)
