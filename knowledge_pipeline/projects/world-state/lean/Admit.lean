/-! Admit.lean: the evidence filter. Takes one result and returns a marker.
    Numbers are permille (0.799 = 799). Judge kinds as in PulseDone.lean. -/
namespace Admit
inductive Judge | validator | outsideGold | claudeAgreement | none deriving DecidableEq

inductive Marker
  | notAdmissible   -- the judge cannot show a method right at all
  | tooFewItems     -- judge fine, sample too small for the range claimed
  | belowBar        -- admissible and sized, low end under the bar or not above the guess
  | meets           -- admissible, sized, low end clears the bar and beats the guess
  deriving DecidableEq

structure Result where
  judge : Judge
  n : Nat          -- items judged
  eMilli : Nat     -- half-width of the 95% range, thousandths
  low : Nat        -- low end of the 95% range
  guess : Nat      -- commonest-answer baseline
  bar : Nat
  contractConfirmed : Bool
  rareLow : Nat    -- low end of recall on the rare cases; 0 means not measured

def judgeOk : Judge → Bool | .validator => true | .outsideGold => true | _ => false
-- normal approximation, the rule bootstrap/Wilson ranges follow: n*e^2 >= 1.96^2 * p*(1-p), p taken as low + e (thousandths)
-- Certainty.lean's Hoeffding rule is the worst case and stricter; it would reject 1600 items for a plus-or-minus 0.02 claim.
def sized (n e low : Nat) : Bool := 384 * (low + e) * (1000 - (low + e)) ≤ 100 * n * e * e

def mark (r : Result) : Marker :=
  if !(judgeOk r.judge) || !r.contractConfirmed then .notAdmissible
  else if !(sized r.n r.eMilli r.low) then .tooFewItems
  else if r.bar ≤ r.low && r.guess < r.low && r.bar ≤ r.rareLow then .meets else .belowBar

theorem claude_agreement_never_admissible (r : Result) (h : r.judge = .claudeAgreement) : mark r = .notAdmissible := by
  simp [mark, judgeOk, h]
theorem no_judge_never_admissible (r : Result) (h : r.judge = .none) : mark r = .notAdmissible := by
  simp [mark, judgeOk, h]
theorem meets_means_bar (r : Result) (h : mark r = .meets) : r.bar ≤ r.low ∧ r.guess < r.low ∧ r.bar ≤ r.rareLow := by
  unfold mark at h; split at h <;> try (cases h)
  split at h <;> try (cases h)
  split at h
  · rename_i hh; simp [Bool.and_eq_true] at hh; exact ⟨hh.1.1, hh.1.2, hh.2⟩
  · cases h
theorem unconfirmed_contract_never_meets (r : Result) (h : r.contractConfirmed = false) : mark r ≠ .meets := by
  simp [mark, h]

-- The recorded results (ledger values; guesses typed from the ledger, to be read from files next)
def topicTrained : Result := ⟨.outsideGold, 1600, 20, 779, 100, 800, true, 0⟩    -- MN-DS human labels, L761
def topicGate    : Result := ⟨.outsideGold, 1600, 25, 534, 100, 800, true, 0⟩    -- L973
def storyType    : Result := ⟨.outsideGold, 3312, 22, 663, 250, 800, false, 0⟩   -- CheckThat: contract not confirmed
def directionAgr : Result := ⟨.claudeAgreement, 3000, 20, 842, 784, 800, true, 0⟩
example : mark topicTrained = .belowBar := by decide   -- low end 0.779 < 0.80
example : mark topicGate = .belowBar := by decide
example : mark storyType = .notAdmissible := by decide
example : mark directionAgr = .notAdmissible := by decide
-- the two branches the recorded results do not reach
example : mark ⟨.outsideGold, 3000, 20, 850, 300, 800, true, 820⟩ = .meets := by decide
example : mark ⟨.outsideGold, 100, 20, 850, 300, 800, true, 0⟩ = .tooFewItems := by decide
example : mark ⟨.validator, 3000, 20, 850, 900, 800, true, 0⟩ = .belowBar := by decide   -- clears the bar, does not beat the guess
example : mark ⟨.outsideGold, 3000, 20, 850, 300, 800, true, 0⟩ = .belowBar := by decide   -- rare cases not measured, so not meets
end Admit
