"""Wake-up delay for the loop: mean duration of the last 10 finished jobs (done or lost, last 24 h) x 1.3, clamped to the scheduler range 60..3600 s (owner rule 2026-11-12: organic, not a fixed window).
Run: python3 -I next_delay.py -> prints seconds, then the basis"""
import json, pathlib, datetime as dt
H = pathlib.Path(__file__).resolve().parents[2] / "runs-history.jsonl"
def ts(s): return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
now = dt.datetime.now(dt.timezone.utc); d = []
for l in H.read_text().splitlines():
    try: r = json.loads(l)
    except Exception: continue
    if r.get("state") not in ("done", "lost") or not r.get("started") or not r.get("ended"): continue
    try: a, b = ts(r["started"]), ts(r["ended"])
    except Exception: continue
    if (now - b).total_seconds() < 86400 and (b - a).total_seconds() > 0: d.append(((b - a).total_seconds(), r["job"]))
d = d[-10:]
if not d: print(600); print("no finished job in the last 24 h: default 600 s")
else:
    m = sum(x for x, _ in d) / len(d); out = int(min(3600, max(60, m * 1.3)))
    print(out); print(f"mean of last {len(d)} finished jobs {m:.0f} s x 1.3 = {m*1.3:.0f} s, clamped {out} s; jobs: " + ", ".join(f"{j[-18:]} {int(x)}s" for x, j in d))
