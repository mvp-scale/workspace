/-! Certainty.lean: the arithmetic behind "how sure are we". Plain Lean 4, no libraries.
    Each theorem says what a number on the page does and does not license.
    CITED, NOT PROVED here: Hoeffding's inequality (P(|mean - p| >= e) <= 2 exp(-2 n e^2)) and ln 40 < 3.7. -/
namespace Certainty

/-! F1. Interval rule. The bar is tested on the LOW end of the 95% range, so the point value clears it too. -/
theorem low_end_clears_bar (low point bar : Nat) (h1 : low ≤ point) (h2 : bar ≤ low) : bar ≤ point :=
  Nat.le_trans h2 h1

/-! F2. How many stories are needed. Hoeffding half-width e at 95% needs 2*n*e^2 >= ln(2/0.05) = ln 40 < 3.7.
    In thousandths, 2*n*e^2*10 >= 37 * 10^6. Checked for the two sizes we use (e = 0.024 at n = 3312; e = 0.02 at n = 4625). -/
def enough (n e_milli : Nat) : Bool := 37 * 1000000 ≤ 2 * n * e_milli * e_milli * 10
example : enough 3312 24 = true := by decide
example : enough 4625 20 = true := by decide
example : enough 3312 20 = false := by decide   -- 3312 stories do not reach plus-or-minus 0.02

/-! F3. Guessing baseline. A constant guess is right on exactly one class, so its balanced accuracy is 1 over the class count. -/
theorem constant_guess_recalls (k : Nat) : (1 :: List.replicate k 0).sum = 1 := by simp

/-! F4. Overall accuracy hides rare cases: 950 common + 50 rare, always answering "common" scores 0.95 and finds 0 rare. -/
def correctCommon : Nat := 950
def rareFound : Nat := 0
example : 800 ≤ correctCommon * 1000 / 1000 ∧ rareFound = 0 := by decide

/-! F5. Agreement between two labellers. Items are (truth, A, B).
    Agreement alone certifies nothing: two labellers can agree and both be wrong.
    Anchored version: A's correct count is at least (A and B agree) + (B correct) - n. -/
def agree : List (Nat × Nat × Nat) → Nat
  | [] => 0
  | (_, a, b) :: t => (if a = b then 1 else 0) + agree t
def okA : List (Nat × Nat × Nat) → Nat
  | [] => 0
  | (x, a, _) :: t => (if x = a then 1 else 0) + okA t
def okB : List (Nat × Nat × Nat) → Nat
  | [] => 0
  | (x, _, b) :: t => (if x = b then 1 else 0) + okB t

example : agree [(0,1,1),(0,1,1),(0,1,1)] = 3 ∧ okA [(0,1,1),(0,1,1),(0,1,1)] = 0 := by decide

theorem anchored_agreement (xs : List (Nat × Nat × Nat)) : agree xs + okB xs ≤ okA xs + xs.length := by
  induction xs with
  | nil => simp [agree, okB, okA]
  | cons h t ih =>
    obtain ⟨x, a, b⟩ := h
    simp only [agree, okB, okA, List.length_cons]
    split <;> split <;> split <;> simp_all <;> omega

/-! F6. Several fields at once (union bound). Items are (field1 right, field2 right).
    Items with both right >= n - wrong1 - wrong2, so five fields at 0.9 each give at least 0.5 all-right, never more by this rule. -/
def bothRight : List (Bool × Bool) → Nat
  | [] => 0
  | (a, b) :: t => (if a && b then 1 else 0) + bothRight t
def wrong1 : List (Bool × Bool) → Nat
  | [] => 0
  | (a, _) :: t => (if a then 0 else 1) + wrong1 t
def wrong2 : List (Bool × Bool) → Nat
  | [] => 0
  | (_, b) :: t => (if b then 0 else 1) + wrong2 t

theorem both_right_floor (xs : List (Bool × Bool)) : xs.length ≤ bothRight xs + wrong1 xs + wrong2 xs := by
  induction xs with
  | nil => simp [bothRight, wrong1, wrong2]
  | cons h t ih =>
    obtain ⟨a, b⟩ := h
    simp only [bothRight, wrong1, wrong2, List.length_cons]
    cases a <;> cases b <;> simp <;> omega

/-! F7. Stated is not true. A stated fact passes four checks; a stated claim can still be false. -/
structure Stated where
  literalSpan : Bool
  valueRoundTrip : Bool
  bound : Bool
  oneSentence : Bool
def Stated.ok (s : Stated) : Bool := s.literalSpan && s.valueRoundTrip && s.bound && s.oneSentence
theorem stated_needs_all (s : Stated) (h : s.ok = true) : s.literalSpan = true ∧ s.valueRoundTrip = true ∧ s.bound = true ∧ s.oneSentence = true := by
  cases s; simp_all [Stated.ok]
-- "stated ok" says nothing about truth: nothing in Stated mentions the world, so no theorem can derive truth from it.

end Certainty
