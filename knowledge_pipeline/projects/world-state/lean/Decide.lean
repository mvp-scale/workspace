/-! Decide.lean: the per-article decider, as a specification. The Rust copy must reproduce `decide` on every case
    that `vectors` prints; any difference fails the build. Codes (all Nat, so the Rust side has no translation layer):
      marker  0 notAdmissible, 1 tooFewItems, 2 belowBar, 3 meets        (same order as Admit.Marker)
      source  0 stated fact (validator), 1 trained head
      out     0 abstain: field not admitted, 1 abstain: too few items, 2 abstain: not validated,
              3 abstain: low confidence, 4 abstain: gates disagree, 5 answer provisional, 6 answer -/
namespace Decide

structure In where
  marker : Nat
  source : Nat
  validated : Bool     -- stated fact passed the four checks
  conf : Nat           -- calibrated confidence of the head, permille
  thr : Nat            -- abstain line, permille
  agrees : Bool        -- gate evidence does not contradict the head

def decide (i : In) : Nat :=
  if i.marker == 0 then 0
  else if i.marker == 1 then 1
  else if i.source == 0 && !i.validated then 2
  else if i.source == 1 && i.conf < i.thr then 3
  else if i.source == 1 && !i.agrees then 4
  else if i.marker == 2 then 5 else 6

theorem not_admitted_abstains (i : In) (h : i.marker = 0) : decide i = 0 := by simp [decide, h]
theorem too_few_abstains (i : In) (h : i.marker = 1) : decide i = 1 := by simp [decide, h]
theorem answer_needs_admission (i : In) (h : 5 ≤ decide i) : 2 ≤ i.marker := by
  unfold decide at h; split at h <;> try omega
  all_goals (split at h <;> try omega)
  all_goals (rename_i h0 h1; simp at h0 h1; omega)
theorem full_answer_needs_meets (i : In) (hm : i.marker ≤ 3) (h : decide i = 6) : i.marker = 3 := by
  unfold decide at h; repeat (split at h <;> try omega)
  all_goals (simp_all; omega)
theorem head_answer_needs_confidence (i : In) (hs : i.source = 1) (h : 5 ≤ decide i) : i.thr ≤ i.conf := by
  unfold decide at h; repeat (split at h <;> try omega)
  all_goals (simp_all)

/-- What happens to the item afterwards (the training-data rule). Codes:
      0 discard (provisional answers are never reused), 1 label queue (needs an outside label),
      2 training label (a validated rule answered, nothing else), 3 needs a judge or a confirmed contract, 4 needs more items.
    A head's own answer is never a training label: no self-training. -/
def harvest (i : In) : Nat :=
  match decide i with
  | 0 => 3
  | 1 => 4
  | 2 => 1
  | 3 => 1
  | 4 => 1
  | 5 => 0
  | _ => if i.source == 0 then 2 else 0

theorem decide_le_six (i : In) : decide i ≤ 6 := by
  unfold decide; repeat (split <;> try omega)

theorem head_never_trains (i : In) (h : i.source = 1) : harvest i ≠ 2 := by
  unfold harvest; split <;> simp_all
theorem provisional_never_trains (i : In) (h : decide i = 5) : harvest i = 0 := by
  unfold harvest; simp [h]
theorem train_label_needs_full_answer (i : In) (h : harvest i = 2) : decide i = 6 ∧ i.source = 0 := by
  have := decide_le_six i
  unfold harvest at h; split at h <;> simp_all <;> omega

/-- One line per case: marker source validated conf agrees thr -> out. Exhaustive over the grid. -/
def vectors : List String :=
  [0,1,2,3].flatMap fun m => [0,1].flatMap fun s => [false,true].flatMap fun v => [0,500,699,700,900].flatMap fun c =>
    [false,true].map fun a =>
      let i : In := ⟨m, s, v, c, 700, a⟩
      s!"{m} {s} {if v then 1 else 0} {c} {if a then 1 else 0} 700 {decide i} {harvest i}"

end Decide
def main : IO Unit := Decide.vectors.forM IO.println
