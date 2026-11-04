"""Generates lean/PresenceWhy.lean from the raw rater tables (suite M, ledger L672, and the Sonnet-positive devq items). Every count the ledger quotes is a theorem proved by `decide` over the literal tables; no model, no float. /workspace/models/embed-zs/.venv/bin/python -I lean/gen_presence_why.py"""
import json, os
J = lambda p: [json.loads(l) for l in open(p)]; D = "runs/pulse/suiteM/"
items = J(D + "items.jsonl"); tab = json.load(open(D + "table.json"))
B = lambda x: "true" if x else "false"
lines = ["/-! WHY do raters disagree on presence? Counts from the raw tables, proved by `decide` (no floats, no sampling).",
 "    Part 1: suite M (ledger L672): 24 base items that report a change that already happened (B), each with one-element edits:",
 "    F forecast, P plan or intent, W warning, S single small local event, plus 24 unrelated neutral items (N).",
 "    A rater follows the written rule when it says yes on all B and no on all F, P, W and N.",
 "    Part 2: the 151 devq items Sonnet A marks positive: first condition kind, and whether Qwen and Gemma also say yes.",
 "    Not proved here: any statement about why a rater says what it says (that is the model's business); only what it said. -/",
 "set_option maxRecDepth 200000", "inductive V | B | F | P | W | S | N deriving DecidableEq", ""]
lines.append("def vars : List V := [" + ", ".join("V." + r["var"] for r in items) + "]")
names = {"Sonnet": "sonnet", "Qwen3.6-27B": "qwen", "Gemma 4 26B": "gemma", "Jev (P>=0.5)": "jev"}
for k, nm in names.items(): lines.append(f"def {nm} : List Bool := [" + ", ".join(B(tab[k][r["id"]]) for r in items) + "]")
lines += ["theorem lens : sonnet.length = 144 ∧ qwen.length = 144 ∧ gemma.length = 144 ∧ jev.length = 144 := by decide"]
lines += ["def count (v : V) (ys : List Bool) : Nat := ((vars.zip ys).filter (fun p => p.1 == v && p.2)).length", "def size (v : V) : Nat := (vars.filter (fun x => x == v)).length", "theorem sizes : size V.B = 24 ∧ size V.F = 24 ∧ size V.P = 24 ∧ size V.W = 24 ∧ size V.S = 24 ∧ size V.N = 24 ∧ vars.length = 144 := by decide", "/-- follows the rule: all B yes; F, P, W, N all no -/", "def follows (ys : List Bool) : Prop := count V.B ys = 24 ∧ count V.F ys = 0 ∧ count V.P ys = 0 ∧ count V.W ys = 0 ∧ count V.N ys = 0", "instance (ys : List Bool) : Decidable (follows ys) := by unfold follows; exact inferInstance", ""]
for k, nm in names.items():
    c = {v: sum(tab[k][r["id"]] for r in items if r["var"] == v) for v in "BFPWSN"}
    lines.append(f"theorem {nm}_counts : count V.B {nm} = {c['B']} ∧ count V.F {nm} = {c['F']} ∧ count V.P {nm} = {c['P']} ∧ count V.W {nm} = {c['W']} ∧ count V.N {nm} = {c['N']} ∧ count V.S {nm} = {c['S']} := by decide")
    ok = c["B"] == 24 and c["F"] == c["P"] == c["W"] == c["N"] == 0
    lines.append(f"theorem {nm}_follows : {'' if ok else '¬ '}follows {nm} := by decide")
lines += ["/-- the four raters differ in what they do with the single small local event (S), not with forecast, plan or warning -/", "theorem same_on_fpw : ∀ ys, ys = sonnet ∨ ys = qwen ∨ ys = gemma ∨ ys = jev → count V.F ys + count V.P ys + count V.W ys = 0 := by", "  intro ys h; rcases h with h | h | h | h <;> subst h <;> decide", ""]
# part 2
L = lambda d: {r["item_id"]: r["label"] for r in J(f"runs/pulse/{d}/labels.jsonl")}
A = L("ceiling_sonnet/a601"); G = L("screen_devq_base"); Q = L("devq601_qwen36_27b_off")
pos = sorted(i for i in A if A[i]["conditions"] and i in G and i in Q)
kinds = [A[i]["conditions"][0]["condition"] for i in pos]; qy = [bool(Q[i]["conditions"]) for i in pos]; gy = [bool(G[i]["conditions"]) for i in pos]
lines.append("def kinds : List String := [" + ", ".join(f'"{k}"' for k in kinds) + "]")
lines.append("def qwenYes : List Bool := [" + ", ".join(B(x) for x in qy) + "]")
lines.append("def gemmaYes : List Bool := [" + ", ".join(B(x) for x in gy) + "]")
lines.append("def yesIn (k : String) (ys : List Bool) : Nat := ((kinds.zip ys).filter (fun p => p.1 == k && p.2)).length")
lines.append("def nIn (k : String) : Nat := (kinds.filter (fun x => x == k)).length")
f = lambda ys, k: sum(1 for kk, y in zip(kinds, ys) if kk == k and y)
n = lambda k: kinds.count(k)
lines.append(f"theorem sizes2 : kinds.length = {len(kinds)} ∧ qwenYes.length = {len(kinds)} ∧ gemmaYes.length = {len(kinds)} := by decide")
lines.append(f"theorem unrest_counts : nIn \"civil_unrest\" = {n('civil_unrest')} ∧ yesIn \"civil_unrest\" qwenYes = {f(qy, 'civil_unrest')} ∧ yesIn \"civil_unrest\" gemmaYes = {f(gy, 'civil_unrest')} := by decide")
for k in ("prices", "disruption", "water_stress"): lines.append(f"theorem {k}_counts : nIn \"{k}\" = {n(k)} ∧ yesIn \"{k}\" qwenYes = {f(qy, k)} ∧ yesIn \"{k}\" gemmaYes = {f(gy, k)} := by decide")
rest_n = len(kinds) - n("civil_unrest"); rest_q = sum(qy) - f(qy, "civil_unrest"); rest_g = sum(gy) - f(gy, "civil_unrest")
lines.append(f"theorem rest_counts : (qwenYes.filter id).length = {sum(qy)} ∧ (gemmaYes.filter id).length = {sum(gy)} ∧ {len(kinds)} - nIn \"civil_unrest\" = {rest_n} ∧ {sum(qy)} - yesIn \"civil_unrest\" qwenYes = {rest_q} ∧ {sum(gy)} - yesIn \"civil_unrest\" gemmaYes = {rest_g} := by decide")
open("lean/PresenceWhy.lean", "w").write("\n".join(lines) + "\n"); print("wrote lean/PresenceWhy.lean", len(lines), "lines; unrest", n("civil_unrest"), f(qy, "civil_unrest"), f(gy, "civil_unrest"), "| rest", rest_n, rest_q, rest_g)
