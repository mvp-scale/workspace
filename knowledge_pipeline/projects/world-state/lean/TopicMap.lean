/-! Generated from specs/topic_to_iptc_v1.json (ledger T28). Topics are indexed in guideline order, IPTC categories 0..16. Checks totality and coverage of the mapping only; it says nothing about accuracy. -/
def mapping : List (List Nat) := [[4], [4], [4], [4], [4, 11], [4, 11], [14, 4], [9], [9], [13], [14, 9], [14], [4, 6], [4, 14], [4, 6], [6, 4], [6], [6], [3, 16, 6], [7], [7], [7, 13], [7], [2], [2], [3], [13, 2], [1], [1, 2], [1, 11], [11, 1], [11, 4, 1], [14, 11], [11], [11], [11, 2], [14, 11], [14, 11], [14, 8], [12], [5], [13], [13], [0], [4, 10], [4], [4, 6], [0, 10, 15], []]
def otherIdx : Nat := 48
/-- 49 guideline topic values (48 topics plus other) are mapped. -/
theorem n_topics : mapping.length = 49 := by decide
/-- Every topic except `other` has at least one accepted category. -/
theorem nonempty_except_other : (List.range 49).all (fun i => i == otherIdx || !(mapping.getD i []).isEmpty) = true := by decide
/-- `other` maps to nothing, so it is excluded from scoring. -/
theorem other_excluded : mapping.getD otherIdx [] = [] := by decide
/-- Every accepted id is a real IPTC first-level category (0 to 16). -/
theorem ids_in_range : mapping.all (fun r => r.all (fun j => decide (j < 17))) = true := by decide
/-- At most three accepted categories per topic, so a lenient score cannot be won by listing many. -/
theorem at_most_three : mapping.all (fun r => decide (r.length ≤ 3)) = true := by decide
/-- Categories no topic can reach (ids): []. Empty means every gold category can be scored right by some topic. -/
theorem unreachable : (List.range 17).filter (fun j => !(mapping.any (fun r => r.contains j))) = [] := by decide
