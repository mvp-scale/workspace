"""Checks the two pages the owner monitors (2026-11-08): the ledger viewer Engine tab (:18766) and the Reading gates page (:8100).
Prints one line per check: OK or STALE/DOWN with the reason. Run it at each loop tick; if anything is STALE, update the page (Engine card: node cp.mjs engine <task> --card <json>; gates: python3 gates_heads.py).
    python3 monitor_pages.py"""
import json, os, re, urllib.request, glob, time
W = "/workspace/knowledge_pipeline/projects/world-state/"; L = "/workspace/knowledge_pipeline/.ledger/ledger.jsonl"
def get(u):
    try: return urllib.request.urlopen(u, timeout=10).read()
    except Exception as e: return None
out = []
d = get("http://localhost:18766/data")
last_id = 0; last_engine = 0; engine_ts = None
for l in open(L):
    try: r = json.loads(l)
    except Exception: continue
    m = re.match(r"L(\d+)$", r.get("id", ""))
    if m:
        last_id = max(last_id, int(m.group(1)))
        if isinstance(r.get("engine"), dict) and r["engine"]: last_engine = int(m.group(1)); engine_ts = r.get("ts")
if d is None: out.append("DOWN  Engine tab: http://localhost:18766/data does not answer (./service.sh start ledger-viewer)")
else:
    c = json.loads(d).get("engine", {}).get("card")
    if not c: out.append("DOWN  Engine tab: no engine card on the ledger")
    else:
        # Expectation (2026-11-09): the card is the engine record, so it is stale when a result that changes the engine is newer than it (a new or re-scored head, a paired comparison with the live head), not after a count of notes.
        import datetime
        ct = datetime.datetime.fromisoformat(engine_ts.replace("Z", "+00:00")).timestamp() if engine_ts else 0
        ER = glob.glob(W + "runs/expert1/*.pkl") + [W + "runs/pulse/" + n for n in ("compare_v6b.json", "learn_loop.json", "field_table.json")]
        newer = sorted([(os.path.getmtime(f), os.path.basename(f)) for f in ER if os.path.exists(f) and os.path.getmtime(f) > ct + 5], reverse=True)
        hint = f"{len(newer)} engine result(s) newer than the card, newest {newer[0][1]}" if newer else "no engine result newer than the card"
        out.append(("STALE " if newer else "OK    ") + f"Engine tab: card '{c['name']} {c['version']}', {len(c['changes'])} changes, last card record L{last_engine}; {hint}. Adopting a new encoder needs the owner's yes. Next: {c['next']['headline'][:60]}")
g = get("http://localhost:8100/mockups/gates/index.html")
if g is None: out.append("DOWN  Reading gates: page does not answer")
else:
    dj = "/workspace/demo/mockups/gates/data.json"; t_data = os.path.getmtime(dj)
    SKIP = ("preplan.json", "opus_review.json", "decisions_open.json", "model_rollout.json")  # plans and reviews are not results; they change no board number
    newest = max((os.path.getmtime(f), f) for f in glob.glob(W + "runs/pulse/*.json") + glob.glob(W + "runs/harvest/toolchain_measure/*.json") if os.path.basename(f) not in SKIP)
    stale = newest[0] > t_data + 5
    out.append(("STALE " if stale else "OK    ") + f"Reading gates: data.json built {time.strftime('%H:%M', time.localtime(t_data))}; newest result file {os.path.basename(newest[1])} at {time.strftime('%H:%M', time.localtime(newest[0]))}" + (" (rerun gates_heads.py)" if stale else ""))
# Page expectations (2026-11-09): every page states when it must be rebuilt. 'results' pages are stale when a result file is newer; 'frozen' pages are not expected to change.
PY = "/workspace/models/embed-zs/.venv/bin/python"
PAGES = [("solver", "solver_shape_page.py", "python3"), ("bitmobs", "bitmob_map_page.py", PY), ("state", "pulse_state_page.py", "python3"), ("learned", "learned_page_data.py", PY)]
FROZEN = {"article-beats": "superseded by the triple work", "article-levels": "superseded", "article-techniques": "superseded", "article-relations": "superseded by T62-T66", "clusters": "superseded, kept not extended", "decider": "fixed test vectors", "training-curve": "throwaway, replaced by the Training tab"}
res = [f for f in glob.glob(W + "runs/pulse/*.json") if os.path.basename(f) not in ("preplan.json", "opus_review.json", "decisions_open.json", "model_rollout.json")]
newest_res = max(os.path.getmtime(f) for f in res) if res else 0
for name, builder, py in PAGES:
    d = "/workspace/demo/mockups/" + name; fs = glob.glob(d + "/*")
    if not fs: out.append(f"DOWN  {name} page: no files"); continue
    built = max(os.path.getmtime(f) for f in fs); st = newest_res > built + 5
    out.append(("STALE " if st else "OK    ") + f"{name} page (rebuilds on new results): built {time.strftime('%m-%d %H:%M', time.localtime(built))}" + (f"; rebuild: cd projects/world-state && {py} {builder}" if st else ""))
out.append("OK    frozen pages, not expected to change: " + ", ".join(FROZEN))
print("\n".join(out))
# The Training tab and loop heartbeats are refreshed by one caller only: the poller runs tick.py (which runs loop_beat.py and health.py) every 180 s. This script only reports page freshness.

