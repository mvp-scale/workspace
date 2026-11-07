"""Builds the recorded rows of lean/TrainReady.lean from result files, computes the verdict with a Python mirror of the rule, writes them as Lean examples (Lean then checks mirror = rule), and writes runs/pulse/train_ready_rows.json for the page.
    python3 train_ready_gen.py   (from projects/world-state)   then   ~/.elan/bin/lean lean/TrainReady.lean"""
import json, random, collections, math
R = "runs/pulse/"; r = json.load(open(R + "tools_to_training.json")); G = json.load(open("/workspace/demo/mockups/gates/data.json"))["stated_facts_suite"]["per_kind"]
pm = lambda x: int(round(1000 * x))
def wilson_low(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); a = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return (c - a) / d
# commonest-two share in the held-out test (same split as tools_to_training.py)
rows = [json.loads(l) for l in open("/workspace/data/anchors/mn_ds/train.jsonl")]
rows = [x for x in rows if (x.get("title") or "").strip() and (x.get("content") or "").strip() and x.get("category_level_1") and x.get("category_level_2")]
src = collections.Counter(x["source"] for x in rows); pubs = sorted(src); rng = random.Random(20261107); rng.shuffle(pubs); tp = set(); n = 0
for p in pubs:
    if n >= 0.2 * len(rows): break
    tp.add(p); n += src[p]
tr = [x for x in rows if x["source"] not in tp]; te = [x for x in rows if x["source"] in tp]
def two(key):
    c = collections.Counter(key(x) for x in tr).most_common(2); top = {k for k, _ in c}; return sum(1 for x in te if key(x) in top) / len(te)
g2_l1 = two(lambda x: x["category_level_1"]); g2_l2 = two(lambda x: x["category_level_1"] + " / " + x["category_level_2"])
ex = r["C_examples_per_class"]; plateau = pm((r["B_l1"]["words"]["top1_range"][1] - r["B_l1"]["words"]["top1_range"][0]) / 2)  # half-width of the 95% range at this test size
gain_l2 = pm(ex["full"]["l2_top1"] - ex["60"]["l2_top1"]); gain_l1 = pm(ex["full"]["l1_top1_via_l2"] - ex["60"]["l1_top1_via_l2"])
st = r["D_story_type"]; n_st = st["test_stories"]; low_st = pm(wilson_low(int(round(st["words"] * n_st)), n_st))
am = G["amount"]; da = G["date"]
J = {"outsideGold": "outsideGold", "claude": "claudeAgreement", "validator": "validator", "none": "none"}
T = [  # name, label, examples, judge, toolsOnly, gain, low, guess, note
 ("domainFirst", "Domain, first guess (17 classes)", r["split"]["train"], "outsideGold", False, gain_l1, pm(r["B_l1"]["words"]["top1_range"][0]), pm(r["B_l1"]["commonest_answer_top1"]), "MN-DS human labels, 35 unseen publishers; curve measured through the 109-class model"),
 ("domainTwo", "Domain, right within two (17 classes)", r["split"]["train"], "outsideGold", False, gain_l1, pm(r["B_l1"]["words"]["top2_range"][0]), pm(g2_l1), "same data; gain proxy is the first-guess curve"),
 ("areaFirst", "Area-sized, first guess (109 classes)", r["split"]["train"], "outsideGold", False, gain_l2, pm(r["B_l2"]["words"]["top1_range"][0]), pm(r["B_l2"]["commonest_answer_top1"]), "MN-DS second level, about 79 examples per class; a stand-in for our Area"),
 ("areaTwo", "Area-sized, right within two (109 classes)", r["split"]["train"], "outsideGold", False, gain_l2, pm(r["B_l2"]["words"]["top2_range"][0]), pm(g2_l2), "same data; gain proxy is the first-guess curve"),
 ("function", "Function: story type (4 classes)", r["D_speed"]["stories"] - n_st, "claudeAgreement", False, 0, low_st, pm(st["commonest_answer"]), "Claude labels only; curve not measured"),
 ("condition", "Condition: 16 kinds", r["D_speed"]["stories"], "claudeAgreement", False, 0, 0, 0, "Claude labels only; score is average precision, not accuracy, so no low end is given"),
 ("size", "Size: amounts, tools only", 0, "validator", True, 0, pm(wilson_low(am["stated"], am["captured"])), 0, "share of captured amounts passing four checks; no commonest-answer baseline exists for this, so 0 is used"),
 ("dates", "Dates, tools only", 0, "validator", True, 0, pm(wilson_low(da["stated"], da["captured"])), 0, "share of captured dates passing four checks; no baseline, 0 used"),
]
for nm in ("Area (our own ontology)", "Capability", "Novelty", "Mention", "Event", "Relation", "Link", "Cluster"):
    T.append((nm.split(" ")[0].lower() + "None", nm, 0, "none", False, 0, 0, 0, "no labelled examples found in the files read for this analysis"))
BAR = 800
def verdict(ex_, judge, tools, gain, low, guess):
    ok = judge in ("validator", "outsideGold")
    if ex_ == 0 and not tools: return "noLabels"
    if not ok: return "needJudge"
    if tools: return "toolsSuffice" if (BAR <= low and guess < low) else "needBetterSignal"
    if plateau <= gain: return "needMoreExamples"
    return "trainable" if (BAR <= low and guess < low) else "needBetterSignal"
out = []; lean = ["-- BEGIN GENERATED (train_ready_gen.py from runs/pulse/tools_to_training.json; plateau = half-width of the 95% range at this test size)"]
for nm, lab, e, j, tools, gain, low, guess, note in T:
    v = verdict(e, j, tools, gain, low, guess); out.append({"id": nm, "label": lab, "examples": e, "judge": j, "tools_only": tools, "gain": gain, "low": low, "guess": guess, "bar": BAR, "plateau": plateau, "verdict": v, "note": note})
    lean.append(f"example : verdict ⟨{e}, .{j}, {'true' if tools else 'false'}, {gain}, {low}, {guess}, {BAR}, {plateau}⟩ = .{v} := by decide   -- {lab}")
lean.append("-- END GENERATED")
s = open("lean/TrainReady.lean").read()
if "-- BEGIN GENERATED" in s: s = s[:s.index("-- BEGIN GENERATED")] + "\n".join(lean) + s[s.index("-- END GENERATED") + len("-- END GENERATED"):]
else: s = s.replace("end TrainReady", "\n".join(lean) + "\nend TrainReady")
open("lean/TrainReady.lean", "w").write(s); json.dump(out, open(R + "train_ready_rows.json", "w"), indent=1)
for o in out: print(o["verdict"].ljust(18), o["label"], "| examples", o["examples"], "gain", o["gain"], "low", o["low"], "guess", o["guess"])
print("plateau", plateau)
