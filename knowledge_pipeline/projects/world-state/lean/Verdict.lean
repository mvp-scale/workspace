/-! Consensus verdict from alpha, in per mille (alpha 0.667 is 667). 2 = Clear, 1 = Tentative, 0 = Reject.
    Bands: Krippendorff, Content Analysis, Sage 2004, p.241 (via secondary sources; book not opened).
    These proofs show the rule has no gaps or overlaps and never rewards lower agreement. -/
def verdict (a : Int) : Nat := if 800 ≤ a then 2 else if 667 ≤ a then 1 else 0

theorem verdict_clear_iff (a : Int) : verdict a = 2 ↔ 800 ≤ a := by
  by_cases h1 : 800 ≤ a <;> by_cases h2 : 667 ≤ a <;> simp [verdict, h1, h2] <;> omega
theorem verdict_tentative_iff (a : Int) : verdict a = 1 ↔ 667 ≤ a ∧ a < 800 := by
  by_cases h1 : 800 ≤ a <;> by_cases h2 : 667 ≤ a <;> simp [verdict, h1, h2] <;> omega
theorem verdict_reject_iff (a : Int) : verdict a = 0 ↔ a < 667 := by
  by_cases h1 : 800 ≤ a <;> by_cases h2 : 667 ≤ a <;> simp [verdict, h1, h2] <;> omega
theorem verdict_total (a : Int) : verdict a = 0 ∨ verdict a = 1 ∨ verdict a = 2 := by
  by_cases h1 : 800 ≤ a <;> by_cases h2 : 667 ≤ a <;> simp [verdict, h1, h2]
theorem verdict_monotone (a b : Int) (h : a ≤ b) : verdict a ≤ verdict b := by
  by_cases h1 : 800 ≤ a <;> by_cases h2 : 667 ≤ a <;> by_cases h3 : 800 ≤ b <;> by_cases h4 : 667 ≤ b <;>
    simp [verdict, h1, h2, h3, h4] <;> omega
theorem verdict_edges : verdict 800 = 2 ∧ verdict 799 = 1 ∧ verdict 667 = 1 ∧ verdict 666 = 0 ∧ verdict (-1000) = 0 := by decide
