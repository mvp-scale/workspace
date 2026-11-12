"""Main-loop round runner (owner, 2026-11-04: keep steps clean and consistent; ledger L663 classes C1-C4). One JSON card per round. The numbers in the ledger come from files, not from typing.
    python3 run_round.py card.json [--dry-run]
Card fields: id, task, part (main-loop part this moves), field, question, one_change, baseline {model, file, key}, prediction {metric, file_key, low, high, why}, command, result {file, key}, cap_minutes, who.
Flow: validate card -> read baseline from its file -> note_guard on the PREDICTION text -> write PREDICTION note -> run command (time cap) -> read result -> verdict -> write SCORE note -> print one line.
Verdict (words fixed): HIT/MISS against the predicted range; vs baseline: GAIN (above baseline by more than noise), NO GAIN (within noise), WORSE (below by more than noise). noise = max(card noise or 0.03, 0)."""
import json, sys, subprocess, time, pathlib, re, os
HERE = pathlib.Path(__file__).resolve().parent; LEDGER = HERE.parents[1] / ".ledger"; W = HERE.parents[1] / "projects/world-state"
def get(path, key):
    d = json.load(open(path)); 
    for k in key.split("."): d = d[int(k)] if isinstance(d, list) else d[k]
    return float(d)
def note(task, text, who, dry):
    bad = subprocess.run([sys.executable, str(HERE / "note_guard.py"), text], capture_output=True, text=True)
    if bad.returncode: sys.exit("GUARD BLOCKED THE NOTE:\n" + bad.stdout + "\n" + text)
    if dry: print("[dry-run note]", text); return "L---"
    r = subprocess.run(["node", "cp.mjs", "note", task, text, "--who", who], cwd=LEDGER, capture_output=True, text=True); m = re.search(r"L\d+", r.stdout); print(r.stdout.strip()); return m.group(0) if m else "L?"
def main():
    card = json.load(open(sys.argv[1])); dry = "--dry-run" in sys.argv
    need = ["id", "task", "part", "field", "question", "one_change", "baseline", "prediction", "command", "result", "cap_minutes", "who", "smoke"]
    miss = [k for k in need if k not in card]
    if miss: sys.exit("card missing: " + ", ".join(miss))
    if len(card["one_change"].split(" and ")) > 2 and "," in card["one_change"]: sys.exit("one_change reads as several changes; split the round")
    bad = [k for k in ("question", "one_change") if re.search(r"\bbaseline\b|\bnew best\b|\bgain\b|\bbeats?\b", card[k], re.I)] + (["prediction.why"] if re.search(r"\bbaseline\b|\bnew best\b|\bgain\b|\bbeats?\b", card["prediction"].get("why", ""), re.I) else [])
    if bad: sys.exit("free-text fields must not carry comparison words (the runner writes the comparison from files): " + ", ".join(bad))
    b = card["baseline"]; bpath = (W / b["file"]) if not b["file"].startswith("/") else pathlib.Path(b["file"])
    if not bpath.exists(): sys.exit("baseline file not found: %s" % bpath)
    base = get(bpath, b["key"]); p = card["prediction"]; noise = float(card.get("noise", 0.03))
    py = sorted({m for t in (card["command"], str(card["smoke"].get("command", ""))) for m in re.findall(r"[\w./-]+\.py\b", t) if (W / m).exists() or pathlib.Path(m).exists()})
    lint = subprocess.run([sys.executable, str(HERE / "lint_swallow.py")] + [str(W / m) if (W / m).exists() else m for m in py], capture_output=True, text=True)
    if lint.returncode: sys.exit("LINT: " + lint.stdout.strip() + "\nNothing launched, no prediction written.")
    sys.path.insert(0, str(HERE)); import heartbeat as hb; RJ = "round-" + card["id"]
    if not dry: hb.beat(RJ, state="running", where="[CPU]", alive_pid=os.getpid(), every_s=180, why=card["question"][:160], success=f"SCORE note for {card['id']} on the ledger", progress="smoke test")
    sm = card["smoke"]  # {"command": ..., "cap_minutes": n} runs on a few items into a scratch folder; or {"skip": "reason of 20+ characters"}
    if "command" in sm:
        if dry: print("[dry-run] smoke not run:", sm["command"])
        else:
            r0 = subprocess.run(sm["command"], shell=True, cwd=W, timeout=int(sm.get("cap_minutes", 10)) * 60)
            if r0.returncode: hb.finish(RJ, "failed", progress="smoke failed"); sys.exit("SMOKE FAILED (exit %d): nothing launched, no prediction written. Fix it and run again." % r0.returncode)
        smoke_text = "Smoke: ran before the full run, passed."
    elif len(sm.get("skip", "")) >= 20: smoke_text = "Smoke: skipped, reason: " + sm["skip"] + "."
    else: sys.exit("card smoke must be {command} or {skip: reason of 20 or more characters}")
    pid = note(card["task"], f"PREDICTION {card['id']} ({card['part']}; field {card['field']}): {card['question']} One change: {card['one_change']}. Baseline = {b['model']} {base:.3f} (src: {b['file']}#{b['key']}). Expect {p['metric']} between {p['low']} and {p['high']} ({p['why']}). Noise floor +-{noise}. Command: {card['command'][:120]}. {smoke_text}", card["who"], dry)
    if dry: print("[dry-run] card valid; command not run:", card["command"]); return  # a dry run must not launch the job (T90, 2026-11-10: it did)
    # the runner is the live process of the round: its row stays fresh however long the command is silent
    hb.beat(RJ, state="running", where="[CPU]", alive_pid=os.getpid(), progress=f"cap {card['cap_minutes']} min")
    t0 = time.time(); r = subprocess.run(card["command"], shell=True, cwd=W, timeout=int(card["cap_minutes"]) * 60)
    hb.finish(RJ, "done" if r.returncode == 0 else "failed", progress=f"exit {r.returncode} after {int(time.time() - t0)} s")
    rf = card["result"]; rpath = W / rf["file"]
    if r.returncode or not rpath.exists(): sys.exit(note(card["task"], f"SCORE {card['id']}: FAILED, exit {r.returncode}, result file {rf['file']} {'present' if rpath.exists() else 'missing'}. Predicted in {pid}. Nothing to score.", card["who"], dry))
    val = get(rpath, rf["key"]); hit = "HIT" if p["low"] <= val <= p["high"] else "MISS"; d = val - base
    vs = "GAIN" if d > noise else "WORSE" if d < -noise else "NO GAIN"
    note(card["task"], f"SCORE {card['id']} ({pid}): {hit}. {p['metric']} = {val:.3f} (src: {rf['file']}#{rf['key']}) (predicted {p['low']} to {p['high']}). Against {b['model']} {base:.3f} (src: {b['file']}#{b['key']}): difference {d:+.3f}, noise floor {noise}: {vs}. Ran {time.time() - t0:.0f} s.", card["who"], dry)
    print(f"{card['id']}: {hit}, {vs}, {p['metric']} {val:.3f} vs {base:.3f}")
main()
