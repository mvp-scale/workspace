"""Round backlog (ch16 build item 2). Starts the next ready card from round_cards/queue/ when the pipeline is idle, so a finished round is followed by the next without the agent. The agent decides what goes into the queue (a card with its prediction); this script only runs what is queued, through run_round.py, so every round has its prediction, smoke, cap and score.
Switch: nothing starts unless the file kit/live/backlog.enabled exists.
A card is ready when: run_round.py --dry-run accepts it (valid card, baseline file present, note guard passes), loop_gate.py says free to run, its task is on the ledger and not done, every id in its optional "after" list has a SCORE note, and nothing else is running (a card with "parallel": true may start beside up to two running rounds while the threads of the running cards plus its own (card field threads, default 18) fit the core count). Lowest "priority" first (default 5).
Moves: queue -> started (launched, pid in runs/rounds/<id>.pid, log runs/rounds/<id>.out) -> done (SCORE note found) or failed (process gone, no SCORE note: smoke failed or crash). Writes runs/rounds/<id>.done (JSON) when a round ends: the file a Monitor can wait on to wake the agent.
    python3 backlog.py"""
import json, os, pathlib, re, subprocess, sys, time
H = pathlib.Path(__file__).resolve().parent; ROOT = H.parents[1]; RC = H / "round_cards"; RD = ROOT / "runs/rounds"; LEDGER = ROOT / ".ledger/ledger.jsonl"
for d in ("queue", "started", "done", "failed"): (RC / d).mkdir(exist_ok=True)
RD.mkdir(parents=True, exist_ok=True)
if not (H / "backlog.enabled").exists(): print("backlog: off (no backlog.enabled)"); sys.exit(0)
L = [json.loads(x) for x in LEDGER.read_text().splitlines()]
scored = {m.group(1): x for x in L if x.get("kind") == "note" for m in [re.match(r"SCORE (\S+?)[ :(]", x.get("text", ""))] if m}
ok_scored = {i for i, x in scored.items() if ": FAILED" not in x["text"][:80]}  # a failed round does not release the rounds that wait for it
tasks = {x["task"] for x in L if x.get("kind") == "task"}; done_tasks = {x["task"] for x in L if x.get("kind") == "done"}
alive = lambda pid: pid and os.path.exists(f"/proc/{pid}")
def pid_of(i):
    try: return int((RD / f"{i}.pid").read_text())
    except Exception: return 0
out = []; running = 0
for f in sorted((RC / "started").glob("*.json")):
    c = json.load(open(f)); i = c["id"]
    if alive(pid_of(i)): running += 1; continue
    ok = i in scored; (RD / f"{i}.done").write_text(json.dumps({"id": i, "ok": ok, "score": scored[i]["text"][:300] if ok else None, "log_tail": None if ok else (RD / f"{i}.out").read_text()[-300:] if (RD / f"{i}.out").exists() else ""}))
    f.rename(RC / ("done" if ok else "failed") / f.name); out.append(f"{i} {'scored' if ok else 'ended without a score'}")
if running == 0 and False: pass
load = os.getloadavg()[0]; health = subprocess.run([sys.executable, str(H / "health.py")], capture_output=True, text=True, timeout=90).stdout
busy = health.startswith(("WORKING", "BROKEN")); started = False
for f in sorted((RC / "queue").glob("*.json"), key=lambda p: (json.load(open(p)).get("priority", 5), p.name)):
    if started: break
    c = json.load(open(f)); i = c.get("id", f.stem); why = []
    used = sum(json.load(open(g)).get("threads", 18) for g in (RC / "started").glob("*.json") if alive(pid_of(json.load(open(g))["id"])))  # thread budget: running cards plus this one must fit the core count
    if (busy or running) and not (c.get("parallel") and running < 3 and used + c.get("threads", 18) <= (os.cpu_count() or 12) and not health.startswith("BROKEN")): continue
    if c.get("task") not in tasks or c.get("task") in done_tasks: why.append("task not open on the ledger")
    why += [f"waits for {a}" for a in c.get("after", []) if a not in ok_scored]
    if not why:
        if subprocess.run([sys.executable, str(H / "loop_gate.py"), str(f)], capture_output=True).returncode: why.append("needs the owner's yes (loop_gate)")
        r = subprocess.run([sys.executable, str(H / "run_round.py"), str(f), "--dry-run"], capture_output=True, text=True)
        if r.returncode: why.append("card refused: " + (r.stdout + r.stderr).strip().splitlines()[-1][:120])
    if why: out.append(f"{i} not started: {'; '.join(why)}"); continue
    g = RC / "started" / f.name; f.rename(g)  # move first: the runner reads the card after it starts
    p = subprocess.Popen([sys.executable, str(H / "run_round.py"), str(g)], stdout=open(RD / f"{i}.out", "w"), stderr=subprocess.STDOUT, start_new_session=True)
    (RD / f"{i}.pid").write_text(str(p.pid)); out.append(f"{i} started pid {p.pid}"); started = True; running += 1
q = len(list((RC / "queue").glob("*.json")))
print(f"backlog: {q} queued, {running} running" + (" | " + "; ".join(out) if out else ""))
