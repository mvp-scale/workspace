/-! Order of operations for the BitMob stack (playbook chapter 15, ledger T42). Models the rule only: tools first, then the BitMob model, then the teacher. It proves this rule model, not the Python code, not model accuracy. No Mathlib. -/

/-- Who settled a head for one article. -/
inductive Who | tools | model | teacher
  deriving DecidableEq, Repr

/-- Strength a label carries in the label store. -/
inductive Strength | proved | rule | weak
  deriving DecidableEq, Repr

/-- What the tools found for one head. `settled` = the text proves the answer; `validated` = all four validator checks passed. -/
structure Evidence where
  settled   : Bool
  validated : Bool
  conf      : Nat   -- model confidence in permille, 0 when no model exists for this head
  hasModel  : Bool

/-- The router. Tools first; the model only for a head the tools left open; the teacher only for what is left. -/
def route (e : Evidence) (thr : Nat) : Who :=
  if e.settled && e.validated then Who.tools
  else if e.hasModel && thr ≤ e.conf then Who.model
  else Who.teacher

/-- Strength written to the label store for each source. -/
def strength : Who → Strength
  | Who.tools   => Strength.proved
  | Who.model   => Strength.weak
  | Who.teacher => Strength.weak

/-- Retrain is due at every positive multiple of the batch size. -/
def retrainDue (batch n : Nat) : Bool := 0 < n && n % batch == 0

/-- The teacher is never asked about a head the tools settled and validated. -/
theorem tools_settle_no_teacher (e : Evidence) (thr : Nat) (h : (e.settled && e.validated) = true) : route e thr = Who.tools := by
  simp [route, h]

/-- The teacher is only reached when the tools left the head open and no model cleared the bar. -/
theorem teacher_only_if_open (e : Evidence) (thr : Nat) (h : route e thr = Who.teacher) :
    (e.settled && e.validated) = false ∧ (e.hasModel && decide (thr ≤ e.conf)) = false := by
  unfold route at h
  by_cases h1 : (e.settled && e.validated) = true
  · simp [h1] at h
  · by_cases h2 : (e.hasModel && decide (thr ≤ e.conf)) = true
    · simp [h1, h2] at h
    · exact ⟨by simpa using h1, by simpa using h2⟩

/-- A model is called only when the tools did not settle the head. -/
theorem model_only_if_open (e : Evidence) (thr : Nat) (h : route e thr = Who.model) : (e.settled && e.validated) = false := by
  unfold route at h
  by_cases h1 : (e.settled && e.validated) = true
  · simp [h1] at h
  · simpa using h1

/-- Only tool-validated answers are marked proved; model and teacher labels are weak. -/
theorem only_tools_proved (e : Evidence) (thr : Nat) (h : strength (route e thr) = Strength.proved) : route e thr = Who.tools := by
  cases hr : route e thr <;> simp [strength, hr] at h ⊢

/-- Without a model for the head, the answer is the tools' or the teacher's, never the model's. -/
theorem no_model_no_model_call (e : Evidence) (thr : Nat) (h : e.hasModel = false) : route e thr ≠ Who.model := by
  unfold route
  split <;> simp [h]
  
/-- A head the tools did not validate is never marked proved. -/
theorem unvalidated_not_proved (e : Evidence) (thr : Nat) (h : e.validated = false) : strength (route e thr) ≠ Strength.proved := by
  unfold route
  simp [h]
  split <;> simp [strength]

/-- The batch rule: retrain at 10000, 20000, ... and at no other count. -/
example : retrainDue 10000 0 = false := by decide
example : retrainDue 10000 9999 = false := by decide
example : retrainDue 10000 10000 = true := by decide
example : retrainDue 10000 10001 = false := by decide
example : retrainDue 10000 20000 = true := by decide

/-- Concrete routes: a stated amount stays with the tools; an open topic with a confident model goes to the model; an open head with no model goes to the teacher. -/
example : route ⟨true, true, 0, false⟩ 700 = Who.tools := by decide
example : route ⟨false, false, 850, true⟩ 700 = Who.model := by decide
example : route ⟨false, false, 400, true⟩ 700 = Who.teacher := by decide
example : route ⟨false, false, 0, false⟩ 700 = Who.teacher := by decide
example : route ⟨true, false, 0, false⟩ 700 = Who.teacher := by decide
