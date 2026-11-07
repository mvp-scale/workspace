"""T42 replay (pre-registered L980): the decider on MN-DS fresh 1600 human-labelled articles, topic, right within two guesses.
Line chosen on the calibration half, scored on the test half. Python mirror of lean/Decide.lean is checked against rust_decider/vectors.txt first.
    /workspace/models/embed-zs/.venv/bin/python decider_replay.py   (from projects/world-state)"""
import json, sys, hashlib, math, random
sys.path.insert(0, "."); from expert1_runtime import ExpertS
def decide(m, s, v, c, thr, a):
    if m == 0: return 0
    if m == 1: return 1
    if s == 0 and not v: return 2
    if s == 1 and c < thr: return 3
    if s == 1 and not a: return 4
    return 5 if m == 2 else 6
bad = 0; n = 0
for l in open("rust_decider/vectors.txt"):
    m, s, v, c, a, thr, o, hv = map(int, l.split()); n += 1; bad += decide(m, s, bool(v), c, thr, bool(a)) != o
print("mirror vs Lean vectors:", n, "cases,", bad, "mismatches")
assert bad == 0
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json"))
items = {json.loads(l)["id"]: json.loads(l)["text"] for l in open("/workspace/data/anchors/mn_ds/items_T28b.jsonl")}
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); R = []
for i, t in items.items():
    r = e.read(t)["topic_top2"]; ok = any(G[i]["l1"] in M.get(x, []) for x in r["answer"])
    R.append((i, int(round(1000 * r["confidence"])), ok))
half = lambda i: int(hashlib.sha256(i.encode()).hexdigest(), 16) % 2
cal = [r for r in R if half(r[0]) == 0]; test = [r for r in R if half(r[0]) == 1]
def wilson_low(k, n):
    if n == 0: return 0.0
    p = k / n; z = 1.96; d = 1 + z * z / n; c = p + z * z / (2 * n)
    return (c - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d
def run(rows, thr):
    ans = [r for r in rows if decide(2, 1, False, r[1], thr, True) in (5, 6)]; k = sum(r[2] for r in ans)
    return len(ans), k
print("halves", len(cal), len(test), "all-items accuracy cal", round(sum(r[2] for r in cal) / len(cal), 3), "test", round(sum(r[2] for r in test) / len(test), 3))
print("line  | cal: coverage  accuracy | test: coverage  accuracy  low-end")
best = None
for thr in range(0, 1000, 50):
    na, ka = run(cal, thr); nt, kt = run(test, thr)
    if na and nt: print(f"{thr:4d}  | {na/len(cal):.3f}  {ka/na:.3f} | {nt/len(test):.3f}  {kt/nt:.3f}  {wilson_low(kt, nt):.3f}")
    if na and ka / na >= 0.82 and best is None: best = thr
print("line chosen on calibration half (first with accuracy >= 0.82):", best)
nt, kt = run(test, best) if best is not None else (0, 0)
res = {"mirror_cases": n, "mirror_mismatches": bad, "line_permille": best, "test_items": len(test), "test_answered": nt, "test_coverage": round(nt / len(test), 3), "test_accuracy": round(kt / nt, 3) if nt else None, "test_low_end": round(wilson_low(kt, nt), 3), "pass_bar": {"low_end": 0.80, "coverage": 0.50}}
res["passed"] = bool(nt and res["test_low_end"] >= 0.80 and res["test_coverage"] >= 0.50)
json.dump(res, open("runs/pulse/decider_replay.json", "w"), indent=1); print(res)
