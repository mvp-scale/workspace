/-! TrainReady.lean: for one BitMob target, do we have enough to train it? Takes measured numbers, returns one verdict.
    Numbers are permille (0.799 = 799). Judge kinds and judgeOk copied from Admit.lean (files here are standalone). Rule order is the order of the questions to ask.
    Bars come from the PRD gate (low end of the 95% range must clear the bar) and PulseDone.lean (bar 0.80); the plateau test is ours. -/
namespace TrainReady
inductive Judge | validator | outsideGold | claudeAgreement | none deriving DecidableEq
def judgeOk : Judge → Bool | .validator => true | .outsideGold => true | _ => false   -- same as Admit.lean

inductive Verdict
  | noLabels          -- no labelled examples for this target at all: get a data source
  | needJudge         -- labels exist, but nothing admissible can judge the result: get outside human labels
  | toolsSuffice      -- a validator proves it from the text, bar cleared: no model needed
  | needMoreExamples  -- the learning curve is still rising: more labelled examples will help
  | needBetterSignal  -- curve flat, low end under the bar: more of the same data will not help; add a tool, a feature or a different model
  | trainable         -- judge admissible, curve flat, low end clears the bar and beats the guess
  deriving DecidableEq

structure Target where
  examples : Nat      -- labelled examples available for training
  judge : Judge
  toolsOnly : Bool    -- answered by tools with a validator, no model
  gain : Nat          -- accuracy gain (thousandths) from the last step up in examples per class; 0 if not measured
  low : Nat           -- low end of the 95% range at current data
  guess : Nat         -- commonest-answer baseline
  bar : Nat
  plateau : Nat       -- a gain at or above this still counts as rising

def verdict (t : Target) : Verdict :=
  if t.examples = 0 && !t.toolsOnly then .noLabels
  else if !(judgeOk t.judge) then .needJudge
  else if t.toolsOnly then (if t.bar ≤ t.low && t.guess < t.low then .toolsSuffice else .needBetterSignal)
  else if t.plateau ≤ t.gain then .needMoreExamples
  else if t.bar ≤ t.low && t.guess < t.low then .trainable else .needBetterSignal

theorem claude_agreement_never_trainable (t : Target) (h : t.judge = .claudeAgreement) (hx : t.examples ≠ 0) : verdict t = .needJudge := by
  simp [verdict, judgeOk, h, hx]
theorem rising_curve_never_trainable (t : Target) (h : t.plateau ≤ t.gain) (ht : t.toolsOnly = false) : verdict t ≠ .trainable := by
  unfold verdict; repeat' split
  all_goals simp_all
theorem trainable_means_bar (t : Target) (h : verdict t = .trainable) : t.bar ≤ t.low ∧ t.guess < t.low ∧ t.gain < t.plateau ∧ judgeOk t.judge = true := by
  unfold verdict at h; repeat' split at h
  all_goals simp_all
-- the six verdicts, one synthetic case each
example : verdict ⟨0, .none, false, 0, 0, 0, 800, 20⟩ = .noLabels := by decide
example : verdict ⟨5000, .claudeAgreement, false, 0, 850, 300, 800, 20⟩ = .needJudge := by decide
example : verdict ⟨5000, .validator, true, 0, 950, 300, 800, 20⟩ = .toolsSuffice := by decide
example : verdict ⟨5000, .outsideGold, false, 60, 700, 300, 800, 20⟩ = .needMoreExamples := by decide
example : verdict ⟨5000, .outsideGold, false, 5, 700, 300, 800, 20⟩ = .needBetterSignal := by decide
example : verdict ⟨5000, .outsideGold, false, 5, 850, 300, 800, 20⟩ = .trainable := by decide
-- BEGIN GENERATED (train_ready_gen.py from runs/pulse/tools_to_training.json; plateau = half-width of the 95% range at this test size)
example : verdict ⟨8619, .outsideGold, false, 12, 782, 94, 800, 16⟩ = .needBetterSignal := by decide   -- Domain, first guess (17 classes)
example : verdict ⟨8619, .outsideGold, false, 12, 926, 153, 800, 16⟩ = .trainable := by decide   -- Domain, right within two (17 classes)
example : verdict ⟨8619, .outsideGold, false, 7, 615, 0, 800, 16⟩ = .needBetterSignal := by decide   -- Area-sized, first guess (109 classes)
example : verdict ⟨8619, .outsideGold, false, 7, 788, 2, 800, 16⟩ = .needBetterSignal := by decide   -- Area-sized, right within two (109 classes)
example : verdict ⟨16627, .claudeAgreement, false, 0, 894, 878, 800, 16⟩ = .needJudge := by decide   -- Function: story type (4 classes)
example : verdict ⟨20790, .claudeAgreement, false, 0, 0, 0, 800, 16⟩ = .needJudge := by decide   -- Condition: 16 kinds
example : verdict ⟨0, .validator, true, 0, 971, 0, 800, 16⟩ = .toolsSuffice := by decide   -- Size: amounts, tools only
example : verdict ⟨0, .validator, true, 0, 895, 0, 800, 16⟩ = .toolsSuffice := by decide   -- Dates, tools only
example : verdict ⟨0, .none, false, 0, 0, 0, 800, 16⟩ = .noLabels := by decide   -- Area (our own ontology)
example : verdict ⟨0, .none, false, 0, 0, 0, 800, 16⟩ = .noLabels := by decide   -- Capability
example : verdict ⟨0, .none, false, 0, 0, 0, 800, 16⟩ = .noLabels := by decide   -- Novelty
example : verdict ⟨0, .none, false, 0, 0, 0, 800, 16⟩ = .noLabels := by decide   -- Mention
example : verdict ⟨0, .none, false, 0, 0, 0, 800, 16⟩ = .noLabels := by decide   -- Event
example : verdict ⟨0, .none, false, 0, 0, 0, 800, 16⟩ = .noLabels := by decide   -- Relation
example : verdict ⟨0, .none, false, 0, 0, 0, 800, 16⟩ = .noLabels := by decide   -- Link
example : verdict ⟨0, .none, false, 0, 0, 0, 800, 16⟩ = .noLabels := by decide   -- Cluster
-- END GENERATED
end TrainReady
