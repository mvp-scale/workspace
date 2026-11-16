"""Needs-you audit (owner 2026-11-12: needs-you went stale unnoticed; find a better method). For every blocked task and every in-progress task, print the facts that show it is stale or already answered: steps ticked vs total, days since its last event, decision lines written after its block whose words overlap its title or block text (a recorded decision may already answer it), and the result files its block text names. Read only. Run: python3 kit/live/needs_you_audit.py   (run it each loop tick, before listing anything to the owner)"""
import json, re, time, datetime as dt, urllib.request, pathlib
data = json.loads(urllib.request.urlopen("http://localhost:18766/data", timeout=10).read()); T = {x["id"]: x for x in data["tasks"]}
led = [json.loads(l) for l in open("/workspace/knowledge_pipeline/.ledger/ledger.jsonl")]
STOP = set("the a an of to and or for in on with is are be it its this that from as by at not no all each one per".split())
words = lambda s: {w for w in re.findall(r"[a-z0-9]{4,}", (s or "").lower()) if w not in STOP}
def ts(s): return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
now = dt.datetime.now(dt.timezone.utc); out = []
for tid, x in T.items():
    if x["status"] not in ("blocked", "in_progress"): continue
    h = x["history"]; REVIEWY = re.compile(r"^(REVIEW|CORRECTION|NEEDS YOU|STATUS|DISPUTE|CLOSURE DISPUTED|NOTE on|ADDITION)")
    real = [e for e in h if not (e["kind"] in ("note", "start", "block") and (REVIEWY.match(str(e.get("text") or "")) or e["who"] == "S?" and e["kind"] in ("start", "block")))]; last = ts((real or h)[-1]["ts"]); idle = (now - last).days
    blk = next((e for e in h if e["kind"] == "block"), None);   # the original block, not a later re-block
    steps = x.get("steps", []); done = sum(1 for s in steps if s["done"])
    flags = []
    if steps and done == len(steps): flags.append("ALL STEPS TICKED: finish or close it")
    if x["status"] == "blocked" and blk:
        w = words(x["title"]) | words(blk["text"]); bt = ts(blk["ts"])
        hits = [d for d in led if d["kind"] == "decision" and ts(d["ts"]) > bt and len(w & words(d["text"])) >= 3]
        if hits: flags.append("DECISIONS AFTER THE BLOCK MAY ANSWER IT: " + ", ".join(f"{d['id']}({d.get('decision')})" for d in hits[:4]))
        files = re.findall(r"runs/[\w./-]+\.json|specs/[\w./-]+|lean/[\w./-]+", blk["text"]); miss = [f for f in files if not any(pathlib.Path(b + f).exists() for b in ("/workspace/knowledge_pipeline/projects/world-state/", "/workspace/knowledge_pipeline/"))]
        if miss: flags.append("names files that do not exist: " + ", ".join(miss[:3]))
        if idle >= 7: flags.append(f"BLOCK IS {idle} DAYS OLD: retire or reconfirm")
    if x["status"] == "in_progress" and idle >= 2: flags.append(f"STALLED {idle} DAYS: next action or close")
    out.append((tid, x["status"], f"{done}/{len(steps)} steps", f"idle {idle} d", flags))
for tid, st, sp, idle, flags in out: print(f"{tid:5} {st:12} {sp:10} {idle:9} " + (" | ".join(flags) if flags else "no flag"))
