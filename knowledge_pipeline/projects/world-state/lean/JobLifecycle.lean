/-! What a job's row on the page says versus what happened (ledger L685, L686).
    Truth: the job really finished ok or bad.  Shown: done, failed or lost (unknown).  A job is registered when its starter
    reported a heartbeat; otherwise the watchdog only sees a process.  Report: the final state a job told the heartbeat, if any.
    OLD rule (heartbeat.py before the fix): a process that is gone with no report is shown failed.  NEW rule: lost if unregistered.
    These theorems are about the RULES, not about any model.  They say: the old rule could show a good job failed; the new rule shows
    failed only on evidence of failure; a job that reports gets the state it reported; and the two summary statements the scripts
    print (a run's done or failed from its failure count, and the bundle's last line) cannot say done when a part was not done. -/
inductive Truth | ok | bad deriving DecidableEq
inductive Shown | done | failed | lost deriving DecidableEq
inductive Reg | registered | unregistered deriving DecidableEq

def oldShown (_ : Reg) : Option Shown → Shown
  | some s => s
  | none => Shown.failed
def newShown (g : Reg) : Option Shown → Shown
  | some s => s
  | none => match g with
    | Reg.registered => Shown.failed
    | Reg.unregistered => Shown.lost
def honest : Truth → Shown
  | Truth.ok => Shown.done
  | Truth.bad => Shown.failed

/-- THE DEFECT: an unregistered job that ended fine, with nothing reported, was shown failed. -/
theorem old_rule_shows_good_job_failed : oldShown Reg.unregistered none ≠ honest Truth.ok := by decide
/-- the fix -/
theorem new_rule_does_not_show_failed : newShown Reg.unregistered none ≠ Shown.failed := by decide
/-- failed is shown only on evidence: a reported failure, or a registered job that vanished without reporting -/
theorem new_failed_needs_evidence (g : Reg) (r : Option Shown) (h : newShown g r = Shown.failed) :
    r = some Shown.failed ∨ (r = none ∧ g = Reg.registered) := by
  cases r with
  | none => cases g <;> simp [newShown] at h <;> simp
  | some s => simp [newShown] at h; simp [h]
/-- a job that reports is shown as it reported -/
theorem new_faithful (g : Reg) (s : Shown) : newShown g (some s) = s := by simp [newShown]
/-- a registered job that reports the honest state is shown the truth -/
theorem registered_report_is_truth (t : Truth) : newShown Reg.registered (some (honest t)) = honest t := by cases t <;> decide
/-- pins what honest means, so the theorem above is not satisfied by any mapping: a bad job is never shown done, a good one is never shown failed -/
theorem honest_pinned : honest Truth.ok = Shown.done ∧ honest Truth.bad = Shown.failed := by decide
theorem bad_job_never_shown_done (g : Reg) : newShown g (some (honest Truth.bad)) ≠ Shown.done := by cases g <;> decide
theorem good_job_never_shown_failed (g : Reg) : newShown g (some (honest Truth.ok)) ≠ Shown.failed := by cases g <;> decide

/-- run.py: done only when at most 5 percent of calls failed or were not attempted -/
def finalState (failed notAttempted total : Nat) : Shown :=
  if 20 * (failed + notAttempted) ≤ total then Shown.done else Shown.failed
theorem final_done_is_sound (f n t : Nat) (h : finalState f n t = Shown.done) : 20 * (f + n) ≤ t := by
  unfold finalState at h; split at h <;> simp_all
theorem final_failed_is_justified (f n t : Nat) (h : finalState f n t = Shown.failed) : 20 * (f + n) > t := by
  unfold finalState at h; split at h <;> simp_all <;> omega
theorem final_monotone (f f' n t : Nat) (hf : f ≤ f') (h : finalState f' n t = Shown.done) : finalState f n t = Shown.done := by
  have := final_done_is_sound f' n t h; unfold finalState; split
  · rfl
  · exfalso; omega
theorem observed_runs : finalState 4 0 1800 = Shown.done ∧ finalState 90 0 1800 = Shown.done ∧ finalState 91 0 1800 = Shown.failed := by decide

/-- the script's last line: before, it printed DONE whatever happened; now it says done only if every part is done -/
def oldBundleSays (_ : List Shown) : Shown := Shown.done
def bundleSays (rs : List Shown) : Shown := if rs.all (fun r => r == Shown.done) then Shown.done else Shown.failed
theorem old_bundle_line_unsupported : oldBundleSays [Shown.done, Shown.failed] = Shown.done := by decide
theorem bundle_done_is_sound (rs : List Shown) (h : bundleSays rs = Shown.done) : ∀ r ∈ rs, r = Shown.done := by
  unfold bundleSays at h; split at h
  · rename_i hall; intro r hr; have := List.all_eq_true.mp hall r hr; simpa using this
  · simp_all
theorem bundle_failed_when_a_part_is_not_done : bundleSays [Shown.done, Shown.failed, Shown.done] = Shown.failed := by decide
