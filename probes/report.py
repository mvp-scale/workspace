"""Summarise probe runs: accuracy vs chance per model and set, plus where the errors are. python3 probes/report.py"""
import json, glob, os, collections, math
RUNS = "/workspace/data/probe-runs"; PROBES = os.path.join(os.path.dirname(__file__))
SETS = ["manipulation", "fallacies", "contradiction", "sarcasm", "social_engineering"]
truth = {s: {json.loads(l)["id"]: json.loads(l) for l in open(f"{PROBES}/{s}.jsonl")} for s in SETS}
chance = {s: 1 / len({t["expected"] for t in truth[s].values()}) for s in SETS}
R = collections.defaultdict(dict)
for s in SETS:
    for d in glob.glob(f"{RUNS}/*-{s}"):
        m = os.path.basename(d)[: -len(s) - 1]
        R[m][s] = [json.loads(l) for l in open(f"{d}/results.jsonl")]
def acc(rs): return sum(r["correct"] for r in rs) / len(rs)
def brier_conf(rs):  # mean probability given to the chosen label, split by right/wrong
    right = [max(r["probs"].values()) for r in rs if r["correct"]]; wrong = [max(r["probs"].values()) for r in rs if not r["correct"]]
    return (sum(right) / len(right) if right else None, sum(wrong) / len(wrong) if wrong else None)
order = sorted(R, key=lambda m: -sum(acc(R[m][s]) for s in SETS))
print(f"{'model':10}" + "".join(f"{s[:11]:>12}" for s in SETS) + f"{'mean':>8}")
print(f"{'chance':10}" + "".join(f"{chance[s]*100:11.0f}%" for s in SETS) + f"{sum(chance.values())/5*100:7.0f}%")
for m in order:
    a = [acc(R[m][s]) for s in SETS]; print(f"{m:10}" + "".join(f"{x*100:11.0f}%" for x in a) + f"{sum(a)/5*100:7.1f}%")
print("\nn=18 per set: 95% half-width is about ±22 points, so gaps under ~20 points are noise.\n")
for s in ("manipulation", "social_engineering", "sarcasm"):
    print(f"--- {s}: where the errors are (per model)")
    for m in order:
        rs = R[m][s]; by = collections.defaultdict(lambda: [0, 0])
        for r in rs:
            e = truth[s][r["task_id"]]["expected"]; by[e][1] += 1; by[e][0] += r["correct"]
        print(f"{m:10}", "  ".join(f"{k}:{v[0]}/{v[1]}" for k, v in by.items()))
print("\n--- confidence when right vs wrong (mean top probability)")
for m in order:
    allr = [r for s in SETS for r in R[m][s]]; ok, bad = brier_conf(allr); print(f"{m:10} right {ok:.2f}  wrong {bad if bad is None else round(bad,2)}  (n wrong {sum(not r['correct'] for r in allr)})")
