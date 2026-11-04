/-! Proofs about two checks used by the field screen. No Mathlib.
    Limit: these prove the maths models below, not that fitness_screen.py matches them.
    The only link to the code is the shared worked example (P2c). -/

/-! P1. The vote-status rule: four votes over four answers. unanimous / majority (more than half) / split. -/
inductive Status | unanimous | majority | split deriving DecidableEq

def top (v : List (Fin 4)) : Nat :=
  (List.finRange 4).foldl (fun m x => max m (v.count x)) 0

def status (v : List (Fin 4)) : Status :=
  if top v = v.length then .unanimous
  else if 2 * top v > v.length then .majority
  else .split

/-- With four votes, "majority" means some answer has exactly 3, "split" means none has 3 or more,
    and "unanimous" means one answer has all 4. Checked for all 256 vote combinations. -/
theorem status_rule :
    ∀ a b c d : Fin 4,
      (status [a, b, c, d] = .majority ↔ top [a, b, c, d] = 3) ∧
      (status [a, b, c, d] = .split ↔ top [a, b, c, d] ≤ 2) ∧
      (status [a, b, c, d] = .unanimous ↔ top [a, b, c, d] = 4) := by
  decide

/-! P2. Binary Krippendorff alpha for two coders, kept as an exact fraction numerator/denominator.
    a = items both coders put in answer A, b = both in B, d = items they disagree on.
    N = a+b+d items, n = 2N values, nA = 2a+d, nB = 2b+d.
    alpha = 1 - Do/De with Do = d/N and De = 2*nA*nB / (n*(n-1)),
    so alpha = (2*nA*nB*N - d*n*(n-1)) / (2*nA*nB*N). -/
def items (a b d : Nat) : Nat := a + b + d
def vals (a b d : Nat) : Nat := 2 * items a b d
def den (a b d : Nat) : Nat := 2 * (2 * a + d) * (2 * b + d) * items a b d
def sub (a b d : Nat) : Nat := d * (vals a b d * (vals a b d - 1))
def num (a b d : Nat) : Int := (den a b d : Int) - (sub a b d : Int)

theorem sub_le_self_int (D X : Nat) : (D : Int) - (X : Int) ≤ (D : Int) := by omega
theorem eq_self_iff (D X : Nat) : (D : Int) - (X : Int) = (D : Int) ↔ X = 0 := by omega

/-- P2a. Alpha never exceeds 1. -/
theorem alpha_le_one (a b d : Nat) : num a b d ≤ (den a b d : Int) :=
  sub_le_self_int _ _

/-- P2b. With at least two values, alpha equals 1 exactly when the coders never disagree. -/
theorem alpha_one_iff (a b d : Nat) (h : 1 ≤ items a b d) :
    num a b d = (den a b d : Int) ↔ d = 0 := by
  unfold num
  rw [eq_self_iff]
  unfold sub
  have hv : 0 < vals a b d * (vals a b d - 1) := by
    unfold vals
    apply Nat.mul_pos <;> omega
  constructor
  · intro h0
    rcases Nat.mul_eq_zero.mp h0 with h1 | h1
    · exact h1
    · omega
  · intro h0
    rw [h0]; simp

/-- P2c. The worked case the Python test used: 4 items both A, 4 both B, 2 disagreements gives 31/50 = 0.62. -/
theorem alpha_worked_case : num 4 4 2 * 50 = 31 * (den 4 4 2 : Int) := by decide
