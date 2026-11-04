/-! Presence under the READY RULE on devq (ledger L657, L662). n = 1,997 items, 221 with a condition (Sonnet v2 truth), 1,776 without.
    Ready needs (GO.md, L492-L495): (a) the low end of the 95% Wilson range of agreement beats always answering 'no'
    (agreement 1776/1997); (b) for a rare field, at least 80% of real cases found (TP >= 177 of 221); (c) low end >= 0.80.
    The Wilson low end beats a rate g exactly when p > g and (p-g)^2 > z^2 g(1-g)/n (score test); z^2 = 1.96^2 = 38416/10000.
    Cleared of fractions with g = 1776/1997, p = k/1997, d = k - 1776:   10000 * d^2 * 1997 > 38416 * 1776 * 221.
    Proved here: the exact error budget, and that the points of the fine-tuned leaf presence head's ROC (scores in
    runs/pulse/presence_scores_v2mix.npz) never meet it.  Condition (c) (low end >= 0.80) is neither stated as a theorem nor needed:
    failing (a) together with (b) already fails the rule.  NOT proved: that no other reader could (that is empirical, see L662). -/
def n : Nat := 1997
def pos : Nat := 221
def neg : Nat := 1776
/-- agreements k beat 'always no' with the Wilson low end (integer form of the score test) -/
def beats (k : Nat) : Prop := neg < k ∧ 38416 * neg * pos < 10000 * (k - neg) ^ 2 * n
instance (k : Nat) : Decidable (beats k) := by unfold beats; exact inferInstance

/-- the exact threshold: 1804 agreements (193 errors) is the least that beats always-no at 95% -/
theorem beats_iff : ∀ k, k ≤ n → (beats k ↔ 1804 ≤ k) := by
  intro k hk; unfold n at hk; unfold beats neg pos n
  constructor
  · intro ⟨h1, h2⟩
    by_cases hge : 1804 ≤ k
    · exact hge
    exfalso
    have h4 : k - 1776 ≤ 27 := by omega
    have h3 : (k - 1776) * (k - 1776) ≤ 27 * 27 := Nat.mul_le_mul h4 h4
    have h5 : (k - 1776) ^ 2 = (k - 1776) * (k - 1776) := Nat.pow_two _
    rw [h5] at h2
    generalize (k - 1776) * (k - 1776) = e at h2 h3
    omega
  · intro h; refine ⟨by omega, ?_⟩
    have h4 : 28 ≤ k - 1776 := by omega
    have h3 : 28 * 28 ≤ (k - 1776) * (k - 1776) := Nat.mul_le_mul h4 h4
    have h5 : (k - 1776) ^ 2 = (k - 1776) * (k - 1776) := Nat.pow_two _
    rw [h5]
    generalize (k - 1776) * (k - 1776) = e at h3 ⊢
    omega

/-- with TP true positives and FP false positives, agreement is TP + (neg - FP).  To be Ready the false positives
    must stay at TP - 28 or fewer, and TP must be at least 177. At the minimum recall (177) that is 149 false alarms (8.4% of 1,776). -/
theorem ready_fp_bound (tp fp : Nat) (hrec : 177 ≤ tp) (htp : tp ≤ pos) (hfp : fp ≤ neg)
    (hb : beats (tp + (neg - fp))) : fp + 28 ≤ tp := by
  have := (beats_iff (tp + (neg - fp)) (by unfold n pos neg at *; omega)).1 hb
  unfold neg pos at *; omega

theorem budget_at_min_recall : 177 - 28 = 149 ∧ 149 * 1000 / 1776 = 83 := by decide

/-- The head's ROC: the first operating point at each recall level from 177 to 221 real cases found, as (TP, FP). -/
def headRoc : List (Nat × Nat) := [(177,217), (178,218), (179,222), (180,222), (181,223), (182,241), (183,258), (184,259), (185,261), (186,265), (187,271), (188,274), (189,275), (190,276), (191,286), (192,288), (193,297), (194,300), (195,316), (196,339), (197,363), (198,374), (199,378), (200,383), (201,394), (202,407), (203,417), (204,424), (205,435), (206,479), (207,483), (208,484), (209,500), (210,501), (211,551), (212,597), (213,611), (214,633), (215,651), (216,721), (217,846), (218,1027), (219,1104), (220,1207), (221,1614)]
/-- No operating point of the fine-tuned leaf presence head is Ready on devq. -/
theorem head_never_ready : ∀ pt ∈ headRoc, ¬ (pt.2 + 28 ≤ pt.1) := by decide
theorem head_points : headRoc.length = 45 := by decide

/-- My earlier note L657 said the limit was ~3.5% false alarms (62 of 1,776). That was too strict: the exact limit is 149. -/
theorem l657_was_too_strict : 62 < 149 ∧ beats (177 + (neg - 149)) ∧ ¬ beats (177 + (neg - 150)) := by decide
