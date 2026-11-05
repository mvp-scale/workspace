/-! Decision rule of the field qualifier (playbook 13, ledger T32). Pure logic: it fixes what each combination of check results means. It does not judge any field. -/
inductive Outcome | go | revise | park deriving DecidableEq

/-- c1 definable, c2 reliable, c3 enough cases, c4 outside anchor, c5 directly in the input; `round` counts REVISE rounds already used. -/
def outcome (c1 c2 c3 c4 c5 : Bool) (round : Nat) : Outcome :=
  if !c1 || !c5 then Outcome.park
  else if c2 && c3 && c4 then Outcome.go
  else if round ≥ 2 then Outcome.park
  else Outcome.revise

/-- G1. A field that is not definable or not directly in the input is parked, whatever else passes. -/
theorem park_if_1_or_5_fails (c2 c3 c4 : Bool) (r : Nat) :
    outcome false c2 c3 c4 true r = Outcome.park ∧ outcome true c2 c3 c4 false r = Outcome.park := by
  simp [outcome]
/-- G2. GO needs all five. -/
theorem go_needs_all (c1 c2 c3 c4 c5 : Bool) (r : Nat) (h : outcome c1 c2 c3 c4 c5 r = Outcome.go) :
    c1 = true ∧ c2 = true ∧ c3 = true ∧ c4 = true ∧ c5 = true := by
  cases c1 <;> cases c2 <;> cases c3 <;> cases c4 <;> cases c5 <;> simp [outcome] at h ⊢ <;> (by_cases hr : 2 ≤ r <;> simp [hr] at h)
/-- G3. A third round is never granted: after two REVISE rounds a failing field is parked. -/
theorem no_third_round (c2 c3 c4 : Bool) (h : ¬ (c2 = true ∧ c3 = true ∧ c4 = true)) (r : Nat) (hr : r ≥ 2) :
    outcome true c2 c3 c4 true r = Outcome.park := by
  cases c2 <;> cases c3 <;> cases c4 <;> simp [outcome] at h ⊢ <;> omega
/-- G4. Examples: not definable is PARK in round 0; definable but unreliable and without an anchor is REVISE in round 0. -/
example : outcome false false true false true 0 = Outcome.park := by decide
example : outcome true false true false true 0 = Outcome.revise := by decide
