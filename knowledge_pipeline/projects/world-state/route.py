"""T42: build the field table (numbers read from result files), grade each field with the Python mirror of lean/Admit.lean,
then route the three mockup articles through the Python mirror of lean/Decide.lean. Mirrors are checked against Lean's own cases first.
    /workspace/models/embed-zs/.venv/bin/python route.py   (from projects/world-state)"""
import json, math, collections, sys, re
sys.path.insert(0, ".")
def dig(d, p):
    for k in p.split("."): d = d[k]
    return d
def wilson(k, n):
    p = k / n; z = 1.96; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d
# ---- mirror of Admit.lean (judge: 0 validator 1 outsideGold 2 claudeAgreement 3 none; marker 0 notAdmissible 1 tooFew 2 belowBar 3 meets)
def sized(n, e, low): return 384 * (low + e) * (1000 - (low + e)) <= 100 * n * e * e
def mark(judge, n, e, low, guess, bar, confirmed, rare):
    if judge not in ("validator", "outsideGold") or not confirmed: return 0
    if not sized(n, e, low): return 1
    return 3 if (bar <= low and guess < low and bar <= rare) else 2
cases = [(("outsideGold", 3000, 20, 850, 300, 800, True, 820), 3), (("outsideGold", 100, 20, 850, 300, 800, True, 820), 1),
         (("validator", 3000, 20, 850, 900, 800, True, 820), 2), (("outsideGold", 3000, 20, 850, 300, 800, True, 0), 2),
         (("claudeAgreement", 3000, 20, 842, 784, 800, True, 0), 0), (("outsideGold", 1600, 20, 779, 100, 800, False, 0), 0)]
assert all(mark(*a) == b for a, b in cases), "Admit mirror differs from the Lean examples"
# ---- mirror of Decide.lean, checked against Lean's 160 vectors
def decide(m, s, v, c, thr, a):
    if m == 0: return 0
    if m == 1: return 1
    if s == 0 and not v: return 2
    if s == 1 and c < thr: return 3
    if s == 1 and not a: return 4
    return 5 if m == 2 else 6
def harvest(m, s, v, c, thr, a):
    o = decide(m, s, v, c, thr, a)
    return {0: 3, 1: 4, 2: 1, 3: 1, 4: 1, 5: 0}.get(o, 2 if s == 0 else 0)
for l in open("rust_decider/vectors.txt"):
    m, s, v, c, a, t, o, hv = map(int, l.split()); assert decide(m, s, bool(v), c, t, bool(a)) == o and harvest(m, s, bool(v), c, t, bool(a)) == hv, "Decide mirror differs from Lean"
OUT = ["abstain: field not admitted", "abstain: too few items", "abstain: not validated", "abstain: low confidence", "abstain: gates disagree", "ANSWER (provisional, field below bar)", "ANSWER"]
T = json.load(open("rust_decider/fields.json")); thr = T["thr_permille"]; rows = {}
for f in T["fields"]:
    r = dict(f)
    if f["src"]:
        d = json.load(open(f["src"])); n = int(dig(d, f["n"]))
        if f["mode"] == "ci": lo, hi = dig(d, f["ci"])
        elif f["mode"] == "counts": lo, hi = wilson(int(dig(d, f["k"])), n)
        else: acc = float(dig(d, f["acc"])); lo, hi = wilson(round(acc * n), n)
        g = f["guess"]
        if g["kind"] == "file": gs = float(dig(d, g["path"]))
        elif g["kind"] == "top2_share_of_gold":
            c = collections.Counter(v["l1"] for v in json.load(open(g["gold"])).values()); gs = sum(x for _, x in c.most_common(2)) / sum(c.values())
        else: gs = g["permille"] / 1000
        low, e = int(lo * 1000), math.ceil((hi - lo) * 500)
        r.update(n=n, low=low, e=e, guess=int(gs * 1000))
    else: r.update(n=0, low=0, e=0, guess=0)
    r["marker"] = mark(f["judge"], r["n"], r["e"], r["low"], r["guess"], 800, f["contract_confirmed"], 0)
    rows[f["field"]] = r
MN = ["not admissible", "too few items", "below bar", "meets"]
print("FIELD TABLE (numbers read from the files in src)")
for k, r in rows.items(): print(f"  {k:11s} n {r['n']:5d}  low end {r['low']/1000:.3f}  commonest-answer {r['guess']/1000:.3f}  judge {r['judge']:16s} contract {'yes' if r['contract_confirmed'] else 'NO '}  -> {MN[r['marker']]}")
json.dump({k: {x: y for x, y in r.items()} for k, r in rows.items()}, open("runs/pulse/field_table.json", "w"), indent=1)
# ---- route the three articles
from expert1_runtime import ExpertS
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); D = json.load(open("/workspace/demo/mockups/gates/data.json"))
print("\nROUTING (confidence line", thr, "permille; gate-agreement check is wired for story type only, other heads pass it by default)")
for ai, a in enumerate(D["articles"]):
    c = a["contract"]; rd = e.read((c["title"] or "") + ". " + (c["description"] or "")); sf = a["stated_facts"]["counts"]
    print(f"\n{a['source']}: {a['title'][:70]}")
    gate_story = a["pulse"]["story_type"]["answer"].split()[0]
    inputs = {"story_type": (1, int(1000 * (rd["story_type"].get("confidence") or 0)), rd["story_type"]["answer"] == gate_story, rd["story_type"]["answer"]),
              "topic": (1, int(1000 * rd["topic_top2"]["confidence"]), True, ", ".join(rd["topic_top2"]["answer"])),
              "change": (0, 0, False, a["pulse"]["change"]["answer"]),
              "size": (0, 0, sf.get("amount", {}).get("stated", 0) > 0, a["pulse"]["size"]["answer"][:60]),
              "traits": (0, 0, False, a["pulse"]["traits"]["answer"])}
    for k, r in rows.items():
        s, cf, ok, ans = inputs[k]
        if k in ("story_type", "topic"): v, ag = True, ok
        else: v, ag = ok, True
        o = decide(r["marker"], s, v, cf, thr, ag)
        print(f"  {k:11s} {OUT[o]:42s} {ans if o >= 5 else ''}   [{MN[r['marker']]}; extractor {r['extractor'].get('model') or r['extractor'].get('name')}; conf {cf/1000:.2f}]")
