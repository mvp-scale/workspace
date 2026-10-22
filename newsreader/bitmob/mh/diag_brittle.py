"""How brittle are the engine's condition readings? Clef's own answers on the frozen test, nudged slightly, re-read with the engine's rules."""
import os, sys, json, numpy as np
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo"]
import classify as C
R = [json.loads(l) for l in open("data/clef-labels/test.jsonl")]
keys = lambda rd: {(x["dial"], x["direction"]) for x in rd["readings"] if x["direction"] != "conflict"}
base = [keys(C.read(r["P"])) for r in R]
same = sum(b == keys(r["read"]) for b, r in zip(base, R)); print(f"sanity: re-read equals stored readings on {same}/{len(R)} stories")
allk = sorted({k for b in base for k in b} | {(d, dr) for r in R for (d, dr) in []}); NK = 78
pos = sum(len(b) for b in base); neg = len(R) * NK - pos
rng = np.random.default_rng(0)
def run(name, f):
    tp = fp = 0
    for r, b in zip(R, base):
        P2 = {k: (float(np.clip(f(v), 0, 1)) if isinstance(v, (int, float)) else v) for k, v in r["P"].items()}
        m = keys(C.read(P2)); tp += len(m & b); fp += len(m - b)
    print(f"{name:42s} conditions kept {tp/pos:6.1%}   false alarms {fp/neg:.4%}  ({fp} extra readings)")
for s in (0.01, 0.02, 0.05, 0.10):
    run(f"random noise ±{s:.2f} on every answer", lambda v, s=s: v + rng.normal(0, s))
run("every answer 2 points lower", lambda v: v - 0.02)
run("every answer 2 points higher", lambda v: v + 0.02)
print(f"positives {pos}, negatives {neg}; pass mark: keep >= 90% with false alarms <= 0.1%")
