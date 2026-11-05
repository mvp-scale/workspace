/-! T41 round 1: gate outcomes of the two revised trait wordings, decided by Lean. The rule is copied from lean/FieldGate.lean.
    Checks in order: c1 definable (MM3 goal gate: MM3-0614 and MM3-0615 pass), c2 reliable (runs/pulse/traits_v1_reliability.json), c3 measurable, c4 anchor or written reason, c5 directly in the input (runs/pulse/traits_v1_check5.json). -/
inductive Outcome | go | revise | park deriving DecidableEq
def outcome (c1 c2 c3 c4 c5 : Bool) (round : Nat) : Outcome :=
  if !c1 || !c5 then Outcome.park
  else if c2 && c3 && c4 then Outcome.go
  else if round ≥ 2 then Outcome.park
  else Outcome.revise
/-- t_x013v1: reliable (lower end 0.790), 28 majority yes, in the text 0.964 with control 0.286: GO. -/
example : outcome true true true true true 1 = Outcome.go := by decide
/-- t_x031v1: lower end 0.655 under 0.667, in the text 0.848 under 0.90: PARK because check 5 fails. -/
example : outcome true false true true false 1 = Outcome.park := by decide
