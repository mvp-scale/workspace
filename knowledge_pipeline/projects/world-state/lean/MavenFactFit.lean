/-! Assumptions behind using MAVEN-FACT (arXiv 2407.15352, Table 2) as an outside check on `presence`.
    Counts are copied from the paper's Table 2 (Maven-Fact row). Nothing here proves accuracy; it fixes what the check can and cannot show. -/

inductive Fact | CTp | CTm | PSp | PSm | Uu deriving DecidableEq

/-- An event mention: its MAVEN-FACT factuality label, and whether it is one of OUR listed conditions (MAVEN-FACT has no such flag). -/
structure Ev where
  fact : Fact
  listed : Bool

/-- Our rule: the item reports at least one listed condition that has already changed. -/
def hasCondition (es : List Ev) : Bool := es.any (fun e => e.fact == Fact.CTp && e.listed)
/-- All MAVEN-FACT can see: the item has at least one event certain to have happened. -/
def hasCertainEvent (es : List Ev) : Bool := es.any (fun e => e.fact == Fact.CTp)

/-- A1. If our rule says yes, MAVEN-FACT must show a certain event. So a rater saying yes on an item with no CT+ event is a definite error. -/
theorem yes_needs_certain (es : List Ev) (h : hasCondition es = true) : hasCertainEvent es = true := by
  unfold hasCondition at h; unfold hasCertainEvent
  rw [List.any_eq_true] at h ⊢
  obtain ⟨e, he, hp⟩ := h
  exact ⟨e, he, by simp [Bool.and_eq_true] at hp; simp [hp.1]⟩

/-- A2. The converse fails: a certain event that is not a listed condition. So MAVEN-FACT can refute a yes, never confirm one. The check is one-sided. -/
theorem certain_not_enough : ∃ es : List Ev, hasCertainEvent es = true ∧ hasCondition es = false :=
  ⟨[⟨Fact.CTp, false⟩], by decide⟩

/-- A3. Table 2 arithmetic: the classes add to the total, so non-CT+ events are 7067 of 112276 (about 6.3 percent). -/
theorem table2_total : 105209 + 2330 + 3874 + 540 + 323 = 112276 := by decide
theorem non_certain_count : 2330 + 3874 + 540 + 323 = 7067 := by decide

/-- A4. Sample size. With the conservative half-width 1/sqrt(n) (the exact 95 percent figure is 0.98/sqrt(n) at worst case), half-width w needs n * w^2 >= 1. In whole percent: w = 3 needs n*9 >= 10000, w = 2 needs n*4 >= 10000. -/
theorem n_for_3pts : 1112 * 9 ≥ 10000 ∧ ¬ (1111 * 9 ≥ 10000) := by decide
theorem n_for_2pts : 2500 * 4 ≥ 10000 ∧ ¬ (2499 * 4 ≥ 10000) := by decide

/-- A5. The rare classes cannot carry a 3-point interval on their own: even ALL non-CT+ events (7067) cover it only if pooled, and PS- (540) and Uu (323) alone are below 1112. Report them pooled. -/
theorem rare_classes_too_small : 540 < 1112 ∧ 323 < 1112 ∧ 1112 ≤ 7067 := by decide
