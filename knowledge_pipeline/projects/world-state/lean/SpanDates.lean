/-! Date resolver rules, checked on day numbers (days since a fixed Monday; weekday = day % 7, Monday = 0).
    Mirrors scan_gate.resolve and span_rules "last/next <weekday>". Python tests: span_rules.py smoke cases. -/
def weekdayOf (day : Nat) : Nat := day % 7
/-- The most recent occurrence of weekday `w` on or before `anchor` (what a bare "Tuesday" resolves to). -/
def lastOnOrBefore (anchor w : Nat) : Nat := anchor - ((anchor % 7 + 7 - w) % 7)
/-- "last <weekday>": the most recent occurrence strictly before the anchor, 1 to 7 days back. -/
def lastStrictly (anchor w : Nat) : Nat :=
  let back := (anchor % 7 + 7 - w) % 7
  anchor - (if back = 0 then 7 else back)
theorem bare_weekday_matches (a w : Nat) (hw : w < 7) (ha : 7 ≤ a) : weekdayOf (lastOnOrBefore a w) = w := by
  unfold weekdayOf lastOnOrBefore; omega
theorem bare_weekday_within_week (a w : Nat) (_hw : w < 7) (ha : 7 ≤ a) : lastOnOrBefore a w ≤ a ∧ a - lastOnOrBefore a w < 7 := by
  unfold lastOnOrBefore; omega
theorem last_weekday_matches (a w : Nat) (hw : w < 7) (ha : 7 ≤ a) : weekdayOf (lastStrictly a w) = w := by
  unfold weekdayOf lastStrictly; simp only []; split <;> omega
theorem last_weekday_strictly_before (a w : Nat) (hw : w < 7) (ha : 7 ≤ a) : lastStrictly a w < a ∧ a - lastStrictly a w ≤ 7 := by
  unfold lastStrictly; simp only []; split <;> omega
/-- Calendar-day validity used by date_mdy / date_dmy: a day is accepted only if it exists in that month (leap years included). -/
def leap (y : Nat) : Bool := (y % 4 == 0 && y % 100 != 0) || y % 400 == 0
def daysIn (y m : Nat) : Nat := if m == 2 then (if leap y then 29 else 28) else if m == 4 || m == 6 || m == 9 || m == 11 then 30 else 31
def validDate (y m d : Nat) : Bool := 1 ≤ m && m ≤ 12 && 1 ≤ d && d ≤ daysIn y m
example : validDate 2024 2 29 = true := by decide
example : validDate 2023 2 29 = false := by decide
example : validDate 1900 2 29 = false := by decide
example : validDate 2000 2 29 = true := by decide
example : validDate 2018 4 31 = false := by decide
example : validDate 2018 13 1 = false := by decide
theorem valid_day_le_31 (y m d : Nat) (h : validDate y m d = true) : d ≤ 31 := by
  unfold validDate daysIn at h; simp at h; split at h <;> split at h <;> omega
