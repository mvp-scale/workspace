"""Cumulative hosted-spend budget for xtest (ledger L686 gap G7: per-run caps let Jev reach 1.05 USD against a plan of 0.50).
Spend is the sum of spend_usd_estimate in every run card under runs/xtest; the cap lives in xtest/budget_cap.json and is raised only by the owner's yes.
    budget.py status | check --need USD   (exit 1 if spent + need > cap)"""
import argparse, glob, json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent; W = "/workspace/knowledge_pipeline/projects/world-state"
def spent(): return sum(json.load(open(f)).get("spend_usd_estimate", 0) for f in glob.glob(f"{W}/runs/xtest/*/runs/*/run_card.json"))
def cap(): return json.load(open(HERE / "budget_cap.json"))["cap_usd"]
def check(need, cap_usd=None, s=None):
    s = spent() if s is None else s; c = cap() if cap_usd is None else cap_usd; return s + need <= c + 1e-9, s, c
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["status", "check"]); ap.add_argument("--need", type=float, default=0.0); a = ap.parse_args()
    ok, s, c = check(a.need); print(f"xtest hosted spend {s:.3f} of cap {c:.3f} USD; need {a.need:.3f}: {'OK' if ok else 'REFUSED'}"); sys.exit(0 if ok else 1)
