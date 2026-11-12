"""Round retrospective (ch16 step 8, D24): reads every PREDICTION and SCORE note the round runner wrote and tabulates what happened, so the miss log is reviewed in bulk from the ledger.
For each scored round: the predicted range, the value, where the value fell (inside, below, above) and how far outside as a share of the range width, plus failed rounds and the time they took.
    python3 retro.py [--since YYYY-MM-DD]  -> runs/retro.json and one summary block on stdout"""
import json, pathlib, re, sys, datetime as dt, statistics as st
ROOT = pathlib.Path(__file__).resolve().parents[2]; since = sys.argv[sys.argv.index("--since") + 1] if "--since" in sys.argv else "2026-11-10"
L = [json.loads(x) for x in (ROOT / ".ledger/ledger.jsonl").read_text().splitlines()]
pred = {}; rows = []
for x in L:
    t = x.get("text", "")
    if x.get("kind") != "note" or x.get("ts", "")[:10] < since: continue
    m = re.match(r"PREDICTION (\S+) .*?Expect (.*?) between ([\d.]+) and ([\d.]+)", t)
    if m: pred[m.group(1)] = (float(m.group(3)), float(m.group(4)), x["id"]); continue
    m = re.match(r"SCORE (\S+?)[ :(]", t)
    if not m: continue
    i = m.group(1)
    if ": FAILED" in t[:90]: rows.append({"id": i, "outcome": "failed", "score": x["id"]}); continue
    v = re.search(r" = ([\d.]+) \(src", t); sec = re.search(r"Ran (\d+) s", t)
    if i in pred and v:
        lo, hi, pid = pred[i]; val = float(v.group(1)); w = max(hi - lo, 1e-9)
        pos = "inside" if lo <= val <= hi else "below" if val < lo else "above"
        rows.append({"id": i, "outcome": pos, "value": val, "low": lo, "high": hi, "miss_distance_share_of_width": 0 if pos == "inside" else round((lo - val if val < lo else val - hi) / w, 2), "position_in_range": round((val - lo) / w, 2) if pos == "inside" else None, "seconds": int(sec.group(1)) if sec else None, "score": x["id"], "prediction": pid})
n = len(rows); c = {k: sum(1 for r in rows if r["outcome"] == k) for k in ("inside", "below", "above", "failed")}
ins = [r["position_in_range"] for r in rows if r["outcome"] == "inside"]
res = {"since": since, "rounds_scored": n, **c, "inside_share": round(c["inside"] / max(n - c["failed"], 1), 3), "median_position_when_inside": round(st.median(ins), 2) if ins else None, "rows": rows}
json.dump(res, open(ROOT / "runs/retro.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "rows"}))
for r in rows: print(r["id"], r["outcome"], r.get("value"), (r.get("low"), r.get("high")), r.get("miss_distance_share_of_width"), r.get("position_in_range"))
