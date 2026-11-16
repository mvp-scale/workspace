"""Session start briefing (owner 2026-11-12: every new session should tell us what is outstanding). Read only. One screen: needs-you, in-progress, contract, stale pages, unscored predictions, what is running, hosted spend, next free round. Run FIRST in every session: python3 kit/live/session_start.py"""
import json, re, subprocess, pathlib, urllib.request, datetime as dt
W = pathlib.Path("/workspace/knowledge_pipeline"); H = W / "kit/live"
def sh(*a, cwd=None):
    r = subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=120); return (r.stdout or "") + (r.stderr or "")
led = [json.loads(x) for x in open(W / ".ledger/ledger.jsonl")]; last = led[-1]
go = dt.datetime.fromtimestamp(pathlib.Path("/workspace/GO.md").stat().st_mtime, dt.timezone.utc); since = [l for l in led if dt.datetime.fromisoformat(l["ts"].replace("Z", "+00:00")) > go]
print(f"SESSION START {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} | ledger at {last['id']} ({last['ts'][:16]}) | {len(since)} ledger lines since GO.md was last written")
try: D = json.loads(urllib.request.urlopen("http://localhost:18766/data", timeout=8).read())
except Exception as e: D = None; print("!! ledger viewer :18766 is DOWN: ./service.sh start ledger-viewer")
if D:
    c = D["counts"]; print(f"WORK: {c['live']} in progress, {c['needsYou']} needs you, {c['passed']} passed, {c['awaitingReview']} finished with no verdict (nothing for you)")
    print("\nNEEDS YOU (owner calls to action):")
    ny = [a for a in D["attention"] if a.get("id") or a.get("rule")]
    for a in ny: print(f"  {a.get('id') or a.get('rule')}: {str(a['why'])[:330]}")
    if not ny: print("  nothing")
    print("\nIN PROGRESS:")
    for t in D["tasks"]:
        if t["status"] == "in_progress": print(f"  {t['id']} {t['title'][:60]} | {sum(1 for s in t['steps'] if s['done'])}/{len(t['steps'])} steps | last event {t['last'][:10]}")
print("\nAUDIT FLAGS (steps ticked, answered by a later decision, old blocks, stalled):")
fl = [x for x in sh("python3", "-I", str(H / "needs_you_audit.py")).splitlines() if "no flag" not in x]; print("\n".join("  " + x[:170] for x in fl) or "  none")
print("\nCONTRACT:"); print("\n".join("  " + x for x in sh("python3", "-I", str(H / "contract_check.py")).splitlines()))
print("\nPAGES:"); st = [x for x in sh("python3", "-I", str(H / "monitor_pages.py")).splitlines() if x.startswith(("STALE", "DOWN"))]
print("\n".join("  " + x[:150] for x in st) or "  all current (rebuild order: head_coverage.py and gates_heads.py first, then the four results pages)")
pairs = [x for x in sh("python3", "-I", str(H / "ledger_pairs.py")).splitlines() if x.startswith(("MISSING", "NOCITE")) and "L2137" not in x]   # L2137 is a known legacy line that cannot be edited
print("\nUNSCORED PREDICTIONS OR UNCITED CORRECTIONS (ledger_pairs.py):"); print("\n".join("  " + x[:150] for x in pairs[:6]) or "  none")
print("\nRUNNING:"); proc = [x for x in sh("ps", "-eo", "pid,etimes,args").splitlines() if re.search(r"python|node|llama", x) and not re.search(r"claude|mm3.mjs|colab|cursor|cp.mjs serve|hw.py|ps -eo|session_start", x)]
print("\n".join("  " + x[:130] for x in proc) or "  nothing"); print("  GPU memory used:", sh("nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader").strip())
sp = [l for l in led[::-1] if "hosted spend" in (l.get("text") or "").lower()]
if sp:
    t = sp[0]["text"]; i = t.lower().index("hosted spend"); print("\nHOSTED SPEND (D43 cap 2.5 USD), last stated at " + sp[0]["id"] + ": " + t[max(0, i - 10): i + 140].replace("\n", " "))
try:
    ns = json.load(open(W / "projects/world-state/runs/pulse/next_steps.json"))["steps"]; nx = [s for s in ns if s["state"].startswith(("ready", "running"))][:2]
    print("\nNEXT FREE ROUND (runs/pulse/next_steps.json):"); print("\n".join(f"  {s['n']}. {s['step'][:110]} [{s['state']}]" for s in nx) or "  none ready")
except Exception: pass
