"""Analyse v2 probe runs (published datasets). python3 probes/report_v2.py [runs_dir]
Accuracy with Wilson 95% intervals vs chance, and whether confidence is informative: accuracy by confidence band,
expected calibration error, and selective accuracy (accept only answers above a confidence threshold)."""
import json, glob, os, sys, math, collections
RUNS = sys.argv[1] if len(sys.argv) > 1 else "/workspace/data/probe-runs-v2"
V2 = os.path.join(os.path.dirname(__file__), "v2")
SETS = ["memsafety", "websec", "manipulation_dialogue", "fallacy_logic", "nli_snli", "sarcasm_isarcasm", "sarcasm_headlines", "phishing", "checklist_contractnli", "darkpatterns"]
truth = {s: [json.loads(l) for l in open(f"{V2}/{s}.jsonl")] for s in SETS if os.path.exists(f"{V2}/{s}.jsonl")}
chance = {s: 1 / len({t["expected"] for t in truth[s]}) for s in truth}
R = collections.defaultdict(dict)
for s in truth:
    for d in glob.glob(f"{RUNS}/*-{s}"):
        p = f"{d}/results.jsonl"
        if os.path.exists(p): R[os.path.basename(d)[: -len(s) - 1]][s] = [json.loads(l) for l in open(p)]
def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)
acc = lambda rs: sum(r["correct"] for r in rs) / len(rs)
conf = lambda r: max(r["probs"].values()) if r.get("probs") else 0.0
def ece(rs, bins=10):
    e = 0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins; sel = [r for r in rs if lo <= conf(r) < hi or (b == bins - 1 and conf(r) == 1)]
        if sel: e += len(sel) / len(rs) * abs(acc(sel) - sum(conf(r) for r in sel) / len(sel))
    return e
full = [m for m in R if all(s in R[m] for s in truth)]
order = sorted(full, key=lambda m: -sum(acc(R[m][s]) for s in truth))
short = {s: s[:9] for s in truth}
print(f"{'model':9}" + "".join(f"{short[s]:>10}" for s in truth) + f"{'macro':>8}")
print(f"{'chance':9}" + "".join(f"{chance[s]*100:9.0f}%" for s in truth) + f"{sum(chance.values())/len(chance)*100:7.0f}%")
for m in order:
    a = [acc(R[m][s]) for s in truth]; print(f"{m:9}" + "".join(f"{x*100:9.0f}%" for x in a) + f"{sum(a)/len(a)*100:7.1f}%")
print("\nn per set: " + ", ".join(f"{short[s]} {len(truth[s])} (±{(wilson(len(truth[s])//2, len(truth[s]))[1]-wilson(len(truth[s])//2, len(truth[s]))[0])/2*100:.0f})" for s in truth))
print("\nIs confidence informative?  (all sets pooled per model; 'gap' = mean confidence when right minus when wrong)")
print(f"{'model':9}{'n':>6}{'acc':>7}{'ECE':>7}{'gap':>7}  selective accuracy / coverage at confidence >= 0.6 | 0.8 | 0.9")
for m in order:
    rs = [r for s in truth for r in R[m][s]]; right = [conf(r) for r in rs if r["correct"]]; wrong = [conf(r) for r in rs if not r["correct"]]
    gap = (sum(right) / len(right) - (sum(wrong) / len(wrong) if wrong else 0))
    sel = []
    for t in (0.6, 0.8, 0.9):
        k = [r for r in rs if conf(r) >= t]; sel.append(f"{acc(k)*100:4.0f}%/{len(k)/len(rs)*100:3.0f}%" if k else "  – ")
    print(f"{m:9}{len(rs):6}{acc(rs)*100:6.1f}%{ece(rs):7.3f}{gap:7.2f}  " + " | ".join(sel))
