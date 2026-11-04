#!/usr/bin/env python3
"""Copy wave events from runs/waves/log.jsonl into the ledger as notes on T14, through cp.mjs (the only ledger writer).
Exits when the wave loop's PID is gone and the log is fully copied. No model calls."""
import json, pathlib, subprocess, time, os
H = pathlib.Path(__file__).resolve().parent; LOG = H / "runs/waves/log.jsonl"; DONE = H / "runs/waves/synced.n"
LEDGER = H.parents[1] / ".ledger"
def alive():
    try: return b"waves.py" in pathlib.Path(f"/proc/{int((H/'runs/waves/pid').read_text())}/cmdline").read_bytes()
    except Exception: return False
while True:
    lines = [l for l in LOG.read_text().splitlines() if l.strip()] if LOG.exists() else []
    k = int(DONE.read_text()) if DONE.exists() else 0
    for l in lines[k:]:
        r = json.loads(l)
        if r["ev"] == "agreement":
            txt = f"RESULT wave {r['n']}: topic {r['topic']}, story_type {r['story_type']}, cond_pair_f1 {r['cond_pair_f1']}, cond_id_f1 {r['cond_id_f1']}, paired {r['paired']}, rejects {r['rejects']} (evidence runs/waves/log.jsonl)"
        elif r["ev"] == "wave_done":
            txt = f"wave {r['n']} done, spent ${r['spent']}; improver added {len(r['added'])} lines. Diagnosis: {r['diagnosis'][:300]}"
        elif r["ev"] == "stop":
            txt = f"STOP: {r.get('why')} (spent {r.get('spent')})"
        else:
            continue
        subprocess.run(["node", "cp.mjs", "note", "T14", txt, "--who", "ledger_sync"], cwd=LEDGER, capture_output=True)
    DONE.write_text(str(len(lines)))
    if not alive() and k == len(lines): break
    time.sleep(120)
