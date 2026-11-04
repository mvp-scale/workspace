/-! A ledger note that quotes a number and cites a source (ledger L686, gap G6).
    OLD check (note_guard.py E1): the note contains a path-like string.  It never opens the file.
    NEW check (E5): every quoted number carries (src: path#key); the file must exist, the key must resolve, and the stored value, rounded to the
    number of decimals quoted, must equal the quote.  Numbers are in thousandths here (0.790 is 790); the Python rounds the same way.
    Proved: the old check accepts a claim the source does not support; the new check accepts only claims that are in the source; wrong
    numbers, missing keys and missing files are each rejected. -/
structure Entry where
  key : String
  milli : Int
deriving DecidableEq

def lookup : List Entry → String → Option Int
  | [], _ => none
  | e :: es, k => if e.key = k then some e.milli else lookup es k

/-- old: any non-empty citation passes -/
def weakOk (citedKey : String) : Bool := citedKey != ""
/-- new: the cited key exists and holds exactly the quoted value -/
def strongOk (S : List Entry) (k : String) (v : Int) : Bool :=
  match lookup S k with
  | some w => w == v
  | none => false

theorem old_check_accepts_unsupported_claim : ∃ S k v, weakOk k = true ∧ strongOk S k v = false := ⟨[], "end2end#topic", 790, by decide, by decide⟩
theorem wrong_number_rejected : strongOk [⟨"end2end#topic", 790⟩] "end2end#topic" 791 = false := by decide
theorem missing_key_rejected : strongOk [⟨"end2end#topic", 790⟩] "end2end#story" 790 = false := by decide
theorem missing_file_rejected : strongOk [] "end2end#topic" 790 = false := by decide
theorem matching_claim_accepted : strongOk [⟨"end2end#topic", 790⟩, ⟨"end2end#story", 919⟩] "end2end#story" 919 = true := by decide
/-- soundness: if the new check accepts, the source really holds that value under that key (first match wins, as in the code) -/
theorem strong_sound (S : List Entry) (k : String) (v : Int) (h : strongOk S k v = true) : lookup S k = some v := by
  unfold strongOk at h; split at h
  · rename_i w hw; simp at h; rw [hw, h]
  · simp at h
/-- completeness for the first match: if the source holds the value under that key, the new check accepts -/
theorem strong_complete (S : List Entry) (k : String) (v : Int) (h : lookup S k = some v) : strongOk S k v = true := by
  unfold strongOk; rw [h]; simp
/-- nothing unsupported gets through -/
theorem rejects_unsupported (S : List Entry) (k : String) (v : Int) (h : lookup S k ≠ some v) : strongOk S k v = false := by
  cases hb : strongOk S k v
  · rfl
  · exact absurd (strong_sound S k v hb) h
