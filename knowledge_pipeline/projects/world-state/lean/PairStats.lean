set_option linter.unusedVariables false
/-! Two coders, two answers: raw agreement, kappa, Gwet AC1, PABAK and per-answer (specific) agreement as exact fractions.
    n11 = both say A, n22 = both say B, n12 = coder 1 says A and coder 2 says B, n21 = the reverse.
    Sources: Feinstein & Cicchetti 1990 (kappa paradox), Cicchetti & Feinstein 1990 (specific agreement), Gwet (AC1).
    Limit: proves nothing about the Python; it supplies exact values for comparison. -/
def n (n11 n22 n12 n21 : Nat) : Rat := (n11 + n22 + n12 + n21 : Nat)
def po (n11 n22 n12 n21 : Nat) : Rat := ((n11 + n22 : Nat) : Rat) / n n11 n22 n12 n21
def maA (n11 n12 : Nat) : Rat := ((n11 + n12 : Nat) : Rat)
def mbA (n11 n21 : Nat) : Rat := ((n11 + n21 : Nat) : Rat)
def maB (n22 n21 : Nat) : Rat := ((n22 + n21 : Nat) : Rat)
def mbB (n22 n12 : Nat) : Rat := ((n22 + n12 : Nat) : Rat)
def pe (n11 n22 n12 n21 : Nat) : Rat :=
  (maA n11 n12 * mbA n11 n21 + maB n22 n21 * mbB n22 n12) / (n n11 n22 n12 n21 * n n11 n22 n12 n21)
def kappa (n11 n22 n12 n21 : Nat) : Rat :=
  (po n11 n22 n12 n21 - pe n11 n22 n12 n21) / (1 - pe n11 n22 n12 n21)
def piA (n11 n22 n12 n21 : Nat) : Rat :=
  (maA n11 n12 + mbA n11 n21) / (2 * n n11 n22 n12 n21)
def spread (n11 n22 n12 n21 : Nat) : Rat :=
  2 * piA n11 n22 n12 n21 * (1 - piA n11 n22 n12 n21)
def ac1 (n11 n22 n12 n21 : Nat) : Rat :=
  (po n11 n22 n12 n21 - spread n11 n22 n12 n21) / (1 - spread n11 n22 n12 n21)
def pabak (n11 n22 n12 n21 : Nat) : Rat := 2 * po n11 n22 n12 n21 - 1
def specA (n11 n22 n12 n21 : Nat) : Rat := (2 * n11 : Nat) / (maA n11 n12 + mbA n11 n21)
def specB (n11 n22 n12 n21 : Nat) : Rat := (2 * n22 : Nat) / (maB n22 n21 + mbB n22 n12)

/-- 40/40/10/10: raw 0.8, kappa 0.6, AC1 0.6, PABAK 0.6, both specific agreements 0.8. -/
theorem balanced_case :
    kappa 40 40 10 10 = 3/5 ∧ ac1 40 40 10 10 = 3/5 ∧ pabak 40 40 10 10 = 3/5 ∧
    specA 40 40 10 10 = 4/5 ∧ specB 40 40 10 10 = 4/5 := by decide +kernel

/-- 85/5/5/5 (skewed): raw 0.9 but kappa 4/9 (the paradox); AC1 36/41; specific agreement 17/18 for the common answer, 1/2 for the rare one. -/
theorem skewed_case :
    po 85 5 5 5 = 9/10 ∧ kappa 85 5 5 5 = 4/9 ∧ ac1 85 5 5 5 = 36/41 ∧
    specA 85 5 5 5 = 17/18 ∧ specB 85 5 5 5 = 1/2 := by decide +kernel
