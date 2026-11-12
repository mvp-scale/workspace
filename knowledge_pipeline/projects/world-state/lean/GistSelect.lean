/-! Gist selection: pick a few pieces (sentences) of ONE article that together cover its meaning, within a word budget.
    Similarities are integers (cosine x 1000) so the rules are exact. Mirrors gist.py (greedy facility location).
    Proved: chosen indices are inside the article, none is chosen twice, the word budget is never exceeded, at most `fuel` pieces,
    and adding a piece never lowers coverage. -/
section
variable (sim : Nat → Nat → Nat) (w : Nat → Nat) (n B : Nat)

/-- Credit of piece i: its best similarity to any chosen piece (0 if none chosen). -/
def credit (S : List Nat) (i : Nat) : Nat := S.foldl (fun m j => max m (sim i j)) 0
/-- Coverage of a chosen set: total credit over all pieces of the article. -/
def coverage (S : List Nat) : Nat := (List.range n).foldl (fun acc i => acc + credit sim S i) 0
/-- Words used by a chosen set. -/
def used (S : List Nat) : Nat := (S.map w).sum
/-- A piece may be added if it is not chosen yet and fits in the budget. -/
def eligible (S : List Nat) (j : Nat) : Bool := !S.contains j && used w S + w j ≤ B
/-- Coverage gained by adding j. -/
def gain (S : List Nat) (j : Nat) : Nat := coverage sim n (S ++ [j]) - coverage sim n S

def pickAux (g : Nat → Nat) : List Nat → Option Nat → Option Nat
  | [], b => b
  | j :: js, none => pickAux g js (some j)
  | j :: js, some b => pickAux g js (if g b < g j then some j else some b)

theorem pickAux_mem (g : Nat → Nat) (js : List Nat) (b : Option Nat) (r : Nat)
    (h : pickAux g js b = some r) : r ∈ js ∨ b = some r := by
  induction js generalizing b with
  | nil => simp [pickAux] at h; right; exact h.symm ▸ rfl
  | cons j js ih =>
    cases b with
    | none =>
      simp only [pickAux] at h
      rcases ih (some j) h with h1 | h1
      · exact Or.inl (List.mem_cons_of_mem _ h1)
      · simp at h1; exact Or.inl (h1 ▸ List.mem_cons_self ..)
    | some b0 =>
      simp only [pickAux] at h
      rcases ih _ h with h1 | h1
      · exact Or.inl (List.mem_cons_of_mem _ h1)
      · split at h1
        · simp at h1; exact Or.inl (h1 ▸ List.mem_cons_self ..)
        · simp at h1; exact Or.inr (by simp [h1])

/-- One greedy step: the eligible piece with the largest gain (earliest on a tie); stop if nothing adds coverage. -/
def step (S : List Nat) : Option Nat :=
  match pickAux (gain sim n S) ((List.range n).filter (eligible w B S)) none with
  | none => none
  | some j => if 0 < gain sim n S j then some j else none

theorem step_spec (S : List Nat) (j : Nat) (h : step sim w n B S = some j) :
    j < n ∧ S.contains j = false ∧ used w S + w j ≤ B := by
  unfold step at h
  split at h
  · simp at h
  · rename_i j0 hj0
    split at h
    · simp at h; subst h
      have hm := pickAux_mem _ _ _ _ hj0
      rcases hm with hm | hm
      · simp [List.mem_filter, List.mem_range, eligible] at hm
        obtain ⟨h1, h2, h3⟩ := hm
        exact ⟨h1, by simpa using h2, h3⟩
      · simp at hm
    · simp at h

def greedy : Nat → List Nat → List Nat
  | 0, S => S
  | f + 1, S => match step sim w n B S with
    | none => S
    | some j => greedy f (S ++ [j])

theorem used_append (S : List Nat) (j : Nat) : used w (S ++ [j]) = used w S + w j := by
  simp [used, List.map_append, List.sum_append]

/-- Everything the selection promises, for any similarity table, word counts, budget and number of pieces. -/
theorem greedy_ok (fuel : Nat) : ∀ S : List Nat, (∀ x ∈ S, x < n) → S.Nodup → used w S ≤ B →
    (∀ x ∈ greedy sim w n B fuel S, x < n) ∧ (greedy sim w n B fuel S).Nodup ∧ used w (greedy sim w n B fuel S) ≤ B ∧
    (greedy sim w n B fuel S).length ≤ S.length + fuel := by
  induction fuel with
  | zero => intro S h1 h2 h3; simp [greedy]; exact ⟨h1, h2, h3⟩
  | succ f ih =>
    intro S h1 h2 h3
    unfold greedy
    cases hs : step sim w n B S with
    | none => simp; first | exact ⟨h1, h2, h3⟩ | exact ⟨h1, h2, h3, by omega⟩
    | some j =>
      simp only []
      obtain ⟨hj1, hj2, hj3⟩ := step_spec sim w n B S j hs
      have n1 : ∀ x ∈ S ++ [j], x < n := by intro x hx; simp at hx; rcases hx with hx | hx; exact h1 x hx; omega
      have n2 : (S ++ [j]).Nodup := by
        rw [List.nodup_append]; refine ⟨h2, by simp, ?_⟩
        intro a ha b hb; simp at hb; subst hb; intro hab; subst hab; simp at hj2; exact absurd ha hj2
      have n3 : used w (S ++ [j]) ≤ B := by rw [used_append]; exact hj3
      obtain ⟨r1, r2, r3, r4⟩ := ih (S ++ [j]) n1 n2 n3
      exact ⟨r1, r2, r3, by simp at r4 ⊢; omega⟩

theorem fold_max_mono (i : Nat) (S : List Nat) (a b : Nat) (h : a ≤ b) :
    S.foldl (fun m j => max m (sim i j)) a ≤ S.foldl (fun m j => max m (sim i j)) b := by
  induction S generalizing a b with
  | nil => simpa using h
  | cons j S ih => exact ih _ _ (by show max a (sim i j) ≤ max b (sim i j); omega)

theorem foldl_add_mono (xs : List Nat) (f g : Nat → Nat) (h : ∀ i, f i ≤ g i) (a b : Nat) (hab : a ≤ b) :
    xs.foldl (fun acc i => acc + f i) a ≤ xs.foldl (fun acc i => acc + g i) b := by
  induction xs generalizing a b with
  | nil => simpa using hab
  | cons i xs ih => exact ih _ _ (by show a + f i ≤ b + g i; have := h i; omega)

/-- Adding a piece never lowers coverage. -/
theorem coverage_mono (S : List Nat) (j : Nat) : coverage sim n S ≤ coverage sim n (S ++ [j]) := by
  unfold coverage
  apply foldl_add_mono _ _ _ _ 0 0 (Nat.le_refl _)
  intro i
  unfold credit
  have : S.foldl (fun m j => max m (sim i j)) 0 ≤ (S ++ [j]).foldl (fun m j => max m (sim i j)) 0 := by
    rw [List.foldl_append]; exact Nat.le_max_left _ _
  exact this
end

-- a tiny worked example: 4 pieces, pieces 0 and 1 alike, 2 and 3 alike, budget of two pieces' words
def exSim : Nat → Nat → Nat := fun i j => if i = j then 1000 else if (i < 2) = (j < 2) then 800 else 100
def exW : Nat → Nat := fun _ => 10
#eval greedy exSim exW 4 20 4 []
example : greedy exSim exW 4 20 4 [] = [0, 2] := by native_decide
