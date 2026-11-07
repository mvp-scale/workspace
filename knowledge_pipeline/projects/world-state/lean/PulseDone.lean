/-! Definition of done for the Pulse (owner, 2026-11-05; ledger task T42). Pure logic: it says what DONE means for a pulse field and lists what blocks a field. It judges nothing itself; the status records at the bottom are my reading of the ledger, each with its line. -/
inductive Judge | validator | outsideGold | claudeAgreement | none deriving DecidableEq

/-- A field is judged acceptably only by a validator against the text (atomic stated facts) or by an OUTSIDE human-labelled anchor (interpretive fields). Agreement between Claude models, or no judge, is not enough. -/
def judgeOk : Judge → Bool
  | Judge.validator => true
  | Judge.outsideGold => true
  | _ => false

/-- contract: defined near the text and confirmed by the owner. evidence: the exact spans are shown. rule: the arithmetic from evidence to answer is shown.
    source: every number links to its file and ledger line and every term is defined. lowEnd: low end of the 95 percent range is 0.80 or more.
    beatsGuess: beats always answering the commonest answer. rare: if it finds something rare it finds 0.80 or more of the real cases.
    ref: the ledger line the status rests on; an empty ref is a blocker, so a status cannot be flipped without naming its evidence. A true flag on `evidence` means the page shows the exact spans in the article for that field; a true flag on `source` means every number and term has a source link or a definition. -/
structure Field where
  contract : Bool
  evidence : Bool
  rule : Bool
  source : Bool
  judge : Judge
  lowEnd : Bool
  beatsGuess : Bool
  rare : Bool
  ref : String

def blockers (f : Field) : List String :=
  (if f.contract then [] else ["contract"]) ++ (if f.evidence then [] else ["evidence"]) ++ (if f.rule then [] else ["rule"]) ++
  (if f.source then [] else ["source"]) ++ (if judgeOk f.judge then [] else ["judge"]) ++ (if f.lowEnd then [] else ["lowEnd"]) ++
  (if f.beatsGuess then [] else ["beatsGuess"]) ++ (if f.rare then [] else ["rare"]) ++ (if f.ref = "" then ["ref"] else [])

def done (f : Field) : Bool := (blockers f).isEmpty

/-- The pulse is done only when all five answers are done: story type, topic, change with direction, size, traits. -/
def pulseDone (fs : List Field) : Bool := fs.length == 5 && fs.all done

/-- P1. Agreement between Claude models is never enough, whatever else passes. -/
theorem claude_agreement_is_not_enough (f : Field) (h : f.judge = Judge.claudeAgreement) : done f = false := by
  cases f; simp_all [done, blockers, judgeOk]

/-- P2. No judge is never enough either. -/
theorem no_judge_is_not_enough (f : Field) (h : f.judge = Judge.none) : done f = false := by
  cases f; simp_all [done, blockers, judgeOk]

/-- P3. The pulse is done only if every one of the five fields is done. -/
theorem pulse_needs_every_field (fs : List Field) (h : pulseDone fs = true) : ∀ f ∈ fs, done f = true := by
  simp [pulseDone] at h
  exact h.2

/-- P4. A field with a blocker is not done. -/
theorem blocker_means_not_done (f : Field) (s : String) (h : s ∈ blockers f) : done f = false := by
  simp [done]; intro hh; simp [hh] at h

/-! Status on 2026-11-05, my reading of the ledger. Each blocker list is what is still missing, not a judgement of the work.
 story type: Sonnet agreement 0.915 (L771) but against the CheckThat human labels the balanced accuracy is 0.684 with low end 0.663 (L970), under the 0.80 line; rare classes (forecast, opinion) not shown to reach 0.80 of real cases; page numbers not yet source-linked.
 topic: human labels MN-DS 0.799 with low end 0.779 (L756, L761), 0.001 short of the line at the point and 0.021 at the low end; not yet source-linked.
 change with direction: contract not confirmed (change set untested); direction learned at 0.842 against Sonnet only (L954); low end not computed; falls found 0.772 under 0.80.
 size: stated amount contract awaits the owner (T38); validity 0.975 is a pass rate, no 95 percent range computed; not yet source-linked.
 traits: 3 of 51 GO (L920); judged by a Claude panel plus a text test; the owner has not named the traits the product needs. -/
def storyType : Field := { contract := true, evidence := true, rule := true, source := false, judge := Judge.claudeAgreement, lowEnd := false, beatsGuess := true, rare := false , ref := "L970" }
def topic : Field := { contract := true, evidence := true, rule := true, source := false, judge := Judge.outsideGold, lowEnd := false, beatsGuess := true, rare := true , ref := "L761" }
def changeDirection : Field := { contract := false, evidence := true, rule := true, source := false, judge := Judge.claudeAgreement, lowEnd := false, beatsGuess := true, rare := false , ref := "L954" }
def size : Field := { contract := false, evidence := true, rule := true, source := false, judge := Judge.validator, lowEnd := false, beatsGuess := true, rare := true , ref := "L959" }
def traits : Field := { contract := true, evidence := true, rule := true, source := false, judge := Judge.claudeAgreement, lowEnd := false, beatsGuess := true, rare := false , ref := "L920" }

example : blockers storyType = ["source", "judge", "lowEnd", "rare"] := by decide
example : blockers topic = ["source", "lowEnd"] := by decide
example : blockers changeDirection = ["contract", "source", "judge", "lowEnd", "rare"] := by decide
example : blockers size = ["contract", "source", "lowEnd"] := by decide
example : blockers traits = ["source", "judge", "lowEnd", "rare"] := by decide
example : pulseDone [storyType, topic, changeDirection, size, traits] = false := by decide
/-- P5. What the pulse would need to be done: every blocker above cleared. -/
example : pulseDone (List.replicate 5 { contract := true, evidence := true, rule := true, source := true, judge := Judge.outsideGold, lowEnd := true, beatsGuess := true, rare := true, ref := "L1" }) = true := by decide

/-- P6. A status with no ledger line named is not done, even with every flag true. -/
example : done { contract := true, evidence := true, rule := true, source := true, judge := Judge.outsideGold, lowEnd := true, beatsGuess := true, rare := true, ref := "" } = false := by decide
