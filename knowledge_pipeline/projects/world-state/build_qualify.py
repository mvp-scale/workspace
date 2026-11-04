"""Builds cards/card_v17.json: Consensus verdicts (sourced bands only), Fit tests, verification table, assumptions.
Inputs: cards/card_base_v16.json, runs/pulse/fitness_screen_v1.json, selfcons voters. Prediction: ledger L526."""
import json, glob, collections, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qualify import consensus_verdict
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
def load(pats):
    d = {}
    for p in pats:
        for f in glob.glob(p):
            for r in J(f): d[r["item_id"]] = r["label"]
    return d
V = [load(["runs/p7b/*/labels.jsonl"]), load(["runs/pulse/selfcons/labels.jsonl"]), load(["runs/p7/*/labels.jsonl"]), load(["runs/pulse/selfcons_haiku/labels.jsonl"])]
ids = [i for i in json.load(open("runs/pulse/selfcons/ids.json")) if all(i in v for v in V)]
mode3 = lambda xs: next((k for k, c in collections.Counter(xs).items() if c >= 3), None)
cnt = {k: collections.Counter() for k in ["story_type", "topic", "condition_present", "which_condition", "direction", "size"]}
for i in ids:
    L = [v[i] for v in V]
    for key, vals in [("story_type", [l.get("story_type") for l in L]), ("topic", [l.get("topic") for l in L]), ("condition_present", ["yes" if l.get("conditions") else "no" for l in L])]:
        a = mode3(vals)
        if a: cnt[key][a] += 1
    named = collections.defaultdict(list)
    for l in L:
        for c in l.get("conditions", []): named[c["condition"]].append(c)
    for cond, cs in named.items():
        if len(cs) >= 3:
            cnt["which_condition"][cond] += 1
            d = mode3([c.get("direction") for c in cs]); s = mode3([c.get("level") for c in cs])
            if d: cnt["direction"][d] += 1
            if s: cnt["size"][s] += 1
BAR_N = 30
import re as _re
_ns = {}; exec("import collections, itertools\n" + _re.search(r"def alpha\(.*?\n(?=\ndef status)", open("fitness_screen.py").read(), _re.S).group(0), _ns); _alpha = _ns["alpha"]
QW = {}
for _l in open("runs/pulse/selfcons_qwen/labels.jsonl", encoding="utf-8"):
    _r = json.loads(_l); QW[_r["item_id"]] = _r["label"]
_LV = ["minor", "notable", "major", "severe", "extreme"]
_i3 = [i for i in ids if i in QW]; _S, _H = V[0], V[2]
def three(key):
    U = []
    if key in ("story_type", "topic"):
        U = [[_S[i][key], _H[i][key], QW[i][key]] for i in _i3]; return round(_alpha(U), 3)
    if key == "condition_present":
        U = [[bool(_S[i]["conditions"]), bool(_H[i]["conditions"]), bool(QW[i]["conditions"])] for i in _i3]; return round(_alpha(U), 3)
    D = []; Z = []
    for i in _i3:
        cs = [{c["condition"]: c for c in L[i]["conditions"]} for L in (_S, _H, QW)]
        for c in set(cs[0]) & set(cs[1]) & set(cs[2]):
            D.append([x[c]["direction"] for x in cs]); Z.append([_LV.index(x[c]["level"]) for x in cs])
    if key == "direction": return round(_alpha(D), 3)
    if key == "size": return round(_alpha(Z, True), 3)
    return None
def f2(key):
    c = cnt[key]; small = sorted([(a, n) for a, n in c.items() if n < BAR_N], key=lambda x: x[1]); tot = len(c)
    state = "pass" if not small else ("fail" if len(small) > tot / 2 else "warn")
    rare = ", ".join(f"{a} {n}" for a, n in small[:3])
    return {"s": state, "t": (f"all {tot} answers have {BAR_N}+ cases" if not small else f"{len(small)} of {tot} answers under {BAR_N} cases (rarest: {rare})"), "small": len(small), "answers": tot}
S = json.load(open("runs/pulse/fitness_screen_v1.json"))["fields"]
base = json.load(open("cards/card_base_v16.json"))
KEYMAP = {"story_type": "story_type", "topic_top2": "topic", "condition_present": "condition_present", "which_condition_all": "which_condition", "direction_all": "direction", "size_all": "size"}
F3 = {"story_type": "none known; agreement only", "topic": "MN-DS / IPTC (playbook 01); not used yet", "condition_present": "none known; agreement only",
      "which_condition": "none known; agreement only", "direction": "PLOVER / POLECAT (playbook 01); not used yet", "size": "none known; agreement only"}
TXT = {  # key: (why, fix)
 "story_type": ("α 0.695 sits between Krippendorff's 0.667 and 0.80, so conclusions are tentative. 'Fact' agrees 97% but opinion 61% and unclear 52% (the 20-vote bar for a rare answer is ours).", "Rewrite the opinion and unclear rules, re-vote, and see whether α reaches 0.80."),
 "topic": ("α 0.89 is above 0.80. The weakest topic, governance_corruption, agrees 70%.", "Nothing to fix before training. Open question: a trusted outside label set (F3)."),
 "condition_present": ("α 0.50 is under 0.667: labellers do not agree beyond chance. Sonnet says yes 49% of the time, Haiku 67%, and Clef cannot arbitrate (57% on the split items).", "Rewrite the rule (a condition counts only if the story reports it changed), re-vote, re-measure. If α stays under 0.667, drop it or make it two-tier."),
 "which_condition": ("α 0.913 is above 0.80: the labels are clean.", "The stall is elsewhere: too few real cases for most conditions (F2) and model capacity."),
 "direction": ("α 0.945 is above 0.80.", "Nothing to fix. Check F3 (outside label set) before calling it correct."),
 "size": ("Interval α 0.831 is above 0.80. Flags (ours): exact-step agreement is 74% and 'major' 66%.", "Decide whether exact steps matter. If so, the exact-step measure needs your yes."),
}
YN = lambda c: ({{"True": "yes", "False": "no"}.get(str(k), k): v for k, v in c.items()} if c else c)
band = {"Clear": "pass", "Tentative": "warn", "Reject": "fail"}
def st(v, ok, bad, hi=True): return "pass" if (v >= ok if hi else v <= ok) else ("fail" if (v < bad if hi else v > bad) else "warn")
for L in base["layers"]:
    for f in L["fields"]:
        if f["key"] == "traits":
            f.pop("fit", None); f["step"] = "Rescore the 51 trait questions with the Consensus bands before building (the old count of 29 rework used the retired rule)"
        k = KEYMAP.get(f["key"])
        if not k or "fit" not in f: continue
        s = S[k]; old = f["fit"]["checks"]; alpha = s["alpha"]; verdict = consensus_verdict(alpha)
        ans = old["answers"]
        f["fit"] = {"verdict": verdict, "alpha": alpha, "self": s["self"], "cross": s["cross"], "unanimous": s["unanimous"], "majority": s["majority"], "split": s["split"], "kind": s["kind"], "n": s["n"],
                    "pattern": f["fit"].get("pattern"), "recipe": f["fit"].get("recipe"), "why": TXT[k][0], "fix": TXT[k][1], "classes": YN(f["fit"].get("classes")),
                    "checks": {"alpha": {"v": alpha, "s": band[verdict]}, "answers": {"v": ans["v"], "s": st(ans["v"], 0.70, 0.50), **({"which": {"True": "yes", "False": "no"}.get(str(ans["which"]), ans["which"])} if "which" in ans else {})},
                               "three": ({"v": three(k), "s": band[consensus_verdict(three(k))]} if three(k) is not None else {"v": None, "s": "quiet"}), "cross": {"v": s["cross"], "s": st(s["cross"], 0.75, 0.60)}, "split": {"v": s["split"], "s": st(s["split"], 0.10, 0.20, hi=False)}, "self": {"v": s["self"], "s": st(s["self"], 0.90, 0.80)}},
                    "fit_tests": {"f1": {"s": band[verdict], "t": f"{verdict} (α {alpha})"}, "f2": f2(k), "f3": {"s": "warn", "t": F3[k]}, "f4": {"s": "quiet", "t": "not measured"}}}
src = lambda s, c: {"src": s, "cite": c}
base["fitness"] = {
 "name": "Field checks v2", "n": 395, "voters": "Sonnet ×2, Haiku ×2 (same spec)", "traits": {}, "agreed": False,
 "rule": "Consensus verdict uses ONLY the sourced α bands (Krippendorff 2004, p.241): 0.80 or more clear, 0.667 to 0.80 tentative, under 0.667 reject. Our own measures are flags and never decide.",
 "measures": [
  {"k": "alpha", "t": "α", "q": "Do labellers agree beyond chance?", "m": "Krippendorff α (nominal; interval for size)", "bar": "0.80+ clear · 0.667–0.80 tentative · under 0.667 reject", "fmt": "n3", **src("sourced", "Krippendorff 2004, p.241 (via secondary sources)")},
  {"k": "three", "t": "Two makers", "q": "Does agreement hold when a model from a different maker (Qwen3-14B) votes with Sonnet and Haiku?", "m": "alpha over Sonnet, Haiku (one maker) and Qwen on the 395 items", "bar": "same bands as the agreement score; a flag only, it does not change the verdict", "fmt": "n3", **src("sourced bands, flag only", "Krippendorff 2004 p.241; third family added 2026-11-03")},
  {"k": "answers", "t": "Every answer", "q": "Does each answer agree, the rare ones too?", "m": "lowest per-answer agreement (answers with 20+ votes)", "bar": "ours: 70%+ ok · under 50% fail", **src("measure sourced, bar ours", "Cicchetti & Feinstein 1990")},
  {"k": "cross", "t": "Sonnet vs Haiku", "q": "Do Sonnet and Haiku agree, not just each with itself? Same maker, so this is not an independent check.", "m": "Sonnet-vs-Haiku agreement (one maker)", "bar": "ours: 75%+ ok · under 60% fail", **src("ours", "none found")},
  {"k": "split", "t": "Contested", "q": "How many items have no 3-of-4 majority?", "m": "share of split items", "bar": "ours: 10% or less ok · over 20% fail", **src("ours", "none found; 3-of-4 rule unsourced")},
  {"k": "self", "t": "Same voter twice", "q": "Does one model repeat itself?", "m": "self-agreement", "bar": "ours: 90%+ ok · under 80% fail", **src("ours", "none found (stability is not correctness: arXiv 2609.15194)")}],
 "fit_tests": [
  {"k": "f1", "t": "Not too subjective", "q": "Would careful readers give the same answer?", "m": "the consensus α above", "bar": "same bands as α", **src("sourced", "Krippendorff 2004, p.241")},
  {"k": "f2", "t": "Enough real cases", "q": "Does every answer have enough cases to learn and to score?", "m": f"cases per answer on the {len(ids)} four-vote items (the full labelled pool is larger, with one voter)", "bar": f"ours: {BAR_N}+ per answer; under that the answer needs targeted data", **src("idea sourced, bar ours", "LESSONS #8 (our notes); Graham & Bull 1998 uses 200+ for intervals")},
  {"k": "f3", "t": "A source of truth", "q": "Is there trusted outside labelled data?", "m": "named outside dataset for the field", "bar": "none = agreement only: the field can never be called correct", **src("our design; datasets named in playbook 01", "playbook/01 rule 5; LESSONS #6")},
  {"k": "f4", "t": "Evidence in the input", "q": "Does the headline plus description carry the evidence?", "m": "agreement between headline-only and full-article labels", "bar": "not measured yet", **src("ours", "LESSONS checklist #3 (our notes)")}],
 "verify": [
  {"check": "α", "source": "Krippendorff 2004 p.241 (secondary)", "lean": "alpha_le_one, alpha_one_iff, alpha_worked_case (lean/FitChecks.lean)", "mm3": "MM3-0570 pass 9 of 9", "bugs": "28 planted: fixtures 96% · reference 93% · Lean oracle 79% · all three 100%"},
  {"check": "κ, AC1, per-answer agreement", "source": "Feinstein & Cicchetti 1990; Cicchetti & Feinstein 1990", "lean": "balanced_case, skewed_case (lean/PairStats.lean)", "mm3": "MM3-0581 clean pass; caught 1 of 10 planted", "bugs": "51 planted: fixtures 88% · oracle 90% · reference 100% · all three 100%"},
  {"check": "Vote status (unanimous / majority / split)", "source": "ours (3-of-4 rule unsourced)", "lean": "status_rule: all 256 vote combinations", "mm3": "MM3-0579 / 0580: weak signal only", "bugs": "1 planted: Lean table caught it, fixtures had no test for it"},
  {"check": "Consensus verdict bands", "source": "Krippendorff 2004 p.241 (secondary)", "lean": "verdict_clear_iff, _tentative_iff, _reject_iff, _total, _monotone, _edges (lean/Verdict.lean)", "mm3": "MM3-0594 pass on the bands; first wording MM3-0592 unsure on rounding", "bugs": "6 planted: all caught by the Lean table (2,001 α values)"},
  {"check": "Two families, contested, same voter, rarest answer, evidence in input", "source": "ours", "lean": "none", "mm3": "none", "bugs": "unverified"}],
 "assumptions": [
  "The 395-item sample represents the news pool beyond its stratification (about half real conditions).",
  "Sonnet and Haiku come from one maker and share habits, so they count as one source; Qwen3-14B is the first independent maker (measured: same-maker agreement is higher than cross-maker on every field, L572).",
  "Krippendorff's bands, set for human coders, also suit LLM voters.",
  "The Lean models cover two coders and two answers; the pipeline uses 4 voters and up to 40 answers.",
  "Catching planted bugs predicts catching real ones; the references, Lean models and fixtures were all written by us, so a shared misreading would survive every method.",
  "MM3's quick 9-question form says nothing about its thorough form.",
  "Sources were read as search summaries; none of the papers was opened."],
 "notes": ["Traits (51 questions) were scored under the old rule and are not shown until rescored.", "Fit and Consensus were one column called 'Fit' before 2026-11-02. Consensus is how well the labels hold up; Fit is whether the field is worth classifying at all.",
           "Source tags: 'sourced' = a published criterion; 'ours' = our own bar or design, not validated.",
           "Story type's κ is 0.58 but its skew-resistant AC1 is 0.92; condition present's κ 0.37 and AC1 0.38 match, so its disagreement is real, not skew (ledger L515)."],
 "clef": "Clef agrees with Sonnet 63% and with Haiku 63% on presence (a different question wording); on the 162 split items it matches majority 57%, so it cannot arbitrate them.",
 "f2_counts": {k: dict(v.most_common()) for k, v in cnt.items() if k not in ("topic",)}}
def plain(x):
    if isinstance(x, str):
        y = x.replace("Krippendorff α", "Krippendorff's alpha").replace("α", "agreement score")
        if x.startswith("α"): y = "Agreement score" + y[len("agreement score"):]
        return y
    if isinstance(x, list): return [plain(v) for v in x]
    if isinstance(x, dict): return {k: plain(v) for k, v in x.items()}
    return x
base["fitness"] = plain(base["fitness"])
for L in base["layers"]:
    for f in L["fields"]:
        for key in ("work", "bad", "step", "what"):
            if isinstance(f.get(key), str): f[key] = plain(f[key])
        if f.get("fit"): f["fit"] = {k: (plain(v) if k in ("why", "fix", "fit_tests") else v) for k, v in f["fit"].items()}
for m in base["fitness"]["measures"]:
    if m["k"] == "alpha": m["t"] = "Agreement score"; m["m"] = "Krippendorff's alpha: agreement beyond chance (1 = perfect, 0 = no better than guessing)"
for v in base["fitness"]["verify"]:
    if v["check"].lower().startswith("agreement score"): v["check"] = "Agreement score (Krippendorff's alpha)"
for t in base["fitness"]["fit_tests"]:
    if t["k"] == "f1": t["m"] = "the Agreement score above"
json.dump(base, open("cards/card_v17.json", "w"), ensure_ascii=False, indent=1)
for L in base["layers"]:
    for f in L["fields"]:
        if f.get("fit"): print(f["key"], f["fit"]["verdict"], f["fit"]["alpha"], "|", f["fit"]["fit_tests"]["f2"]["t"])
