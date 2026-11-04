"""Tests for run_round.py: each bad card must be refused with its reason, the good card must run and write HIT/MISS and GAIN/NO GAIN/WORSE from files. python3 test_run_round.py"""
import subprocess, sys, pathlib
H = pathlib.Path(__file__).resolve().parent
def run(card): r = subprocess.run([sys.executable, str(H / "run_round.py"), str(H / "round_cards" / card), "--dry-run"], capture_output=True, text=True); return r.returncode, (r.stdout + r.stderr)
cases = [("bad_missing_prediction.json", "card missing: prediction"), ("bad_baseline_file.json", "baseline file not found"), ("bad_comparison_words.json", "must not carry comparison words")]
ok = True
for c, want in cases:
    rc, out = run(c); good = rc != 0 and want in out; ok &= good; print("PASS" if good else "FAIL", c)
rc, out = run("example_ok.json"); good = rc == 0 and "MISS" in out and "NO GAIN" in out and "0.794 vs 0.790" in out; ok &= good; print("PASS" if good else "FAIL", "example_ok.json")
sys.exit(0 if ok else 1)
