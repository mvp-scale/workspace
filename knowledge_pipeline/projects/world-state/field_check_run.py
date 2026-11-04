"""One command for the whole field-check sequence (the repeatable process). Stdlib only.
  python3 -I field_check_run.py [--skip a,b] [--post] [--list]
Steps run in order, each timed; a manifest goes to runs/pulse/field_check_run_<time>.json and a summary table is printed.
Each step is an existing, ledger-registered script; this file only orders them. Posting the card to the ledger needs --post."""
import json, os, subprocess, sys, time, datetime
H = os.path.dirname(os.path.abspath(__file__)); EMB = "/workspace/models/embed-zs/.venv/bin/python"
ENV = dict(os.environ, PATH=os.path.expanduser("~/.elan/bin") + ":" + os.environ["PATH"], CUDA_VISIBLE_DEVICES="")
STEPS = [
 ("screen",  ["python3", "-I", "fitness_screen.py"],                      "consensus screen: alpha, per-answer agreement, split, self (runs/pulse/fitness_screen_v1.json)"),
 ("sourced", ["python3", "-I", "sourced_checks_test.py"],                 "kappa, AC1, PABAK, specific agreement, Dawid-Skene vs majority"),
 ("proofs",  ["lean", "lean/FitChecks.lean"],                             "Lean proofs: vote status, binary alpha"),
 ("proofs2", ["lean", "lean/PairStats.lean"],                             "Lean model: kappa, AC1, specific agreement"),
 ("proofs3", ["lean", "lean/Verdict.lean"],                               "Lean proofs: verdict bands total, exclusive, monotone"),
 ("verdict", ["python3", "-I", "lean/verdict_test.py"],                   "Python verdict equals the Lean table on 2,001 alpha values; planted bugs caught"),
 ("gate",    ["python3", "-I", "lean/replication_test.py"],               "planted-bug gate: fixtures, Lean oracle, independent reference on alpha and pair_stats"),
 ("stall",   [EMB, "stall_test.py", "v6b-student", "devq2"],              "do the checks predict per-condition stalls (DEVQ2)"),
 ("stall2",  [EMB, "stall_test.py", "v6b-student", "devq"],               "same on DEVQ (out of sample)"),
 ("revote",  ["python3", "-I", "revote_compare.py"],                      "alpha, same two voters, v2 codebook vs v3 codebook (if v3 labels exist)"),
 ("card",    ["python3", "-I", "build_qualify.py"],                       "build the Engine card (cards/card_v17.json)"),
]
if "--list" in sys.argv: [print(f"{n:8} {d}") for n, _, d in STEPS]; sys.exit(0)
skip = set((sys.argv[sys.argv.index("--skip") + 1] if "--skip" in sys.argv else "").split(","))
rows = []; t0 = time.time()
for name, cmd, desc in STEPS:
    if name in skip: rows.append({"step": name, "status": "skipped"}); continue
    t = time.time(); r = subprocess.run(cmd, cwd=H, env=ENV, capture_output=True, text=True)
    ok = r.returncode == 0 and ("error" not in r.stdout.lower()[:2000] if name.startswith("proofs") else True)
    rows.append({"step": name, "status": "ok" if ok else "FAIL", "seconds": round(time.time() - t, 1), "tail": (r.stdout + r.stderr).strip().splitlines()[-1][:200] if (r.stdout + r.stderr).strip() else ""})
    print(f"{name:8} {'ok' if ok else 'FAIL':5} {rows[-1]['seconds']:7.1f}s  {desc}", flush=True)
    if not ok: print("   ", rows[-1]["tail"]); 
if "--post" in sys.argv and all(r["status"] != "FAIL" for r in rows):
    card = open(os.path.join(H, "cards/card_v17.json")).read()
    r = subprocess.run(["node", "cp.mjs", "engine", "T20", "--card", card, "--who", "S?"], cwd=os.path.join(H, "../../.ledger"), capture_output=True, text=True)
    rows.append({"step": "post", "status": "ok" if r.returncode == 0 else "FAIL", "tail": (r.stdout + r.stderr).strip()[-120:]}); print("post    ", rows[-1]["status"], rows[-1]["tail"])
man = {"when": datetime.datetime.now().isoformat(timespec="seconds"), "total_seconds": round(time.time() - t0, 1), "steps": rows}
p = os.path.join(H, "runs/pulse/field_check_run_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"); json.dump(man, open(p, "w"), indent=1)
print(f"total {man['total_seconds']}s  failures: {sum(r['status']=='FAIL' for r in rows)}  manifest {os.path.relpath(p, H)}")
sys.exit(1 if any(r["status"] == "FAIL" for r in rows) else 0)
