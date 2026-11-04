"""Score voter label directories against Sonnet v3b and Haiku v3b and apply the pre-registered replacement rule (ledger L587). Stdlib only.
Usage: python3 -I compare_voters.py runs/pulse/selfcons_gemma4_off runs/pulse/selfcons_qwen38_27b_off ...   (first argument is the BASELINE)
Rule: a candidate replaces the baseline only if its alpha with Sonnet v3b is higher on at least 2 of story type, topic, presence and not lower by more than 0.05 on the third; parse problems 0 to 1 are checked in each run's report, speed at least 5 items per second likewise."""
import json, re, sys, os
H = os.path.dirname(os.path.abspath(__file__)); ns = {}
exec("import collections, itertools\n" + re.search(r"def alpha\(.*?\n(?=\ndef status)", open(os.path.join(H, "fitness_screen.py")).read(), re.S).group(0), ns); alpha = ns["alpha"]
J = lambda p: {json.loads(l)["item_id"]: json.loads(l)["label"] for l in open(os.path.join(H, p, "labels.jsonl"), encoding="utf-8")}
S, Hk = J("runs/pulse/selfcons_v3b"), J("runs/pulse/selfcons_v3b_haiku")
F = {"story": lambda l: l["story_type"], "topic": lambda l: l["topic"], "presence": lambda l: bool(l["conditions"])}
res = {}
for d in sys.argv[1:]:
    v = J(d); ids = [i for i in v if i in S and i in Hk]
    res[d] = {"n": len(ids), "yes_pct": round(100 * sum(bool(v[i]["conditions"]) for i in ids) / len(ids)),
              **{f"{k}_S": round(alpha([[g(v[i]), g(S[i])] for i in ids]), 3) for k, g in F.items()}, **{f"{k}_H": round(alpha([[g(v[i]), g(Hk[i])] for i in ids]), 3) for k, g in F.items()}}
base = res[sys.argv[1]]
print("%-46s %4s %5s | story S/H | topic S/H | presence S/H | rule vs baseline" % ("voter", "n", "yes%"))
for d, r in res.items():
    if d == sys.argv[1]: verdict = "(baseline)"
    else:
        diffs = {k: round(r[f"{k}_S"] - base[f"{k}_S"], 3) for k in F}; higher = sum(x > 0 for x in diffs.values()); worst = min(diffs.values())
        verdict = ("REPLACES" if higher >= 2 and worst >= -0.05 else "keep baseline") + f"  diffs {diffs}"
    print("%-46s %4d %4d%% | %.2f %.2f | %.2f %.2f | %.2f %.2f | %s" % (d.split("/")[-1], r["n"], r["yes_pct"], r["story_S"], r["story_H"], r["topic_S"], r["topic_H"], r["presence_S"], r["presence_H"], verdict))
json.dump(res, open(os.path.join(H, "runs/pulse/compare_voters.json"), "w"), indent=1)
