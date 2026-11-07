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
/-- T41 round 1, six revised wordings (B18, B19): t_x008r1 reliable (lower end 0.842) but in the text 0.66 under 0.90: PARK because check 5 fails. -/
example : outcome true true true true false 1 = Outcome.park := by decide
/-- t_x032r1: reliable (lower end 0.891), 17 majority yes, in the text 1.000 with control 0.235: GO once c1 (MM3 goal gate) passes. -/
example : outcome true true true true true 1 = Outcome.go := by decide
/-- T41 hunt (B22, B23): t_x027r1 goal gate MM3-0617 pass, reliable on the enriched sample (lower end 0.810, 46 majority yes), in the text 0.935 with control 0.178: GO as written, with cautions on the ledger. -/
example : outcome true true true true true 1 = Outcome.go := by decide
/-- t_x026r1, t_x028r1, t_x030r1: reliable on the enriched sample but check 5 control rate 0.306, 0.313, 0.328 over the 0.30 line: PARK. -/
example : outcome true true true true false 1 = Outcome.park := by decide
/-- T41 round 2 and hunt 2 (B24, B25, B26): t_x019r2 reliable on the enriched sample but in the text 0.75 under 0.90: PARK. t_x020r2 reliable on the enriched sample, in the text 0.889 under 0.90: PARK. Both are second round wordings. -/
example : outcome true true true true false 2 = Outcome.park := by decide
