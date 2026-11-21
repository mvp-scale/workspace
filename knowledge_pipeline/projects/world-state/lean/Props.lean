/-! Props.lean: proof roadmap P1 and P4 (playbook 00 section 11; ledger L2868).
    P1: the evidence-set union used when stores are merged (consolidate.merge_assertions: fragments keyed by (article, sentence), a repeated key is kept once)
        is idempotent, commutative and replay-safe, as sets, and never introduces a duplicate key.
    P4: an is_a insertion that would close a cycle is refused (consolidate.IsA.add walks up from the parent; a hit on the child refuses), so the graph stays acyclic.
    Single file, core Lean only, no proof holes. Python mirror: props_mirror.py. -/
namespace Props

/-! ## P1 evidence-set union -/
-- fragment keys are modelled as Nat; ins adds a key only if it is not there yet (setdefault)
def ins (l : List Nat) (k : Nat) : List Nat := if k ∈ l then l else l ++ [k]
def merge (a b : List Nat) : List Nat := b.foldl ins a
def Same (a b : List Nat) : Prop := ∀ x, x ∈ a ↔ x ∈ b

theorem mem_ins (l : List Nat) (k x : Nat) : x ∈ ins l k ↔ x ∈ l ∨ x = k := by
  unfold ins
  split
  · rename_i h
    constructor
    · intro hx; exact Or.inl hx
    · intro hx; rcases hx with hx | hx
      · exact hx
      · subst hx; exact h
  · simp [List.mem_append]

theorem mem_fold (b a : List Nat) (x : Nat) : x ∈ b.foldl ins a ↔ x ∈ a ∨ x ∈ b := by
  induction b generalizing a with
  | nil => simp
  | cons y t ih =>
    simp only [List.foldl_cons, ih, mem_ins, List.mem_cons]
    constructor
    · intro h; rcases h with (h | h) | h
      · exact Or.inl h
      · exact Or.inr (Or.inl h)
      · exact Or.inr (Or.inr h)
    · intro h; rcases h with h | h | h
      · exact Or.inl (Or.inl h)
      · exact Or.inl (Or.inr h)
      · exact Or.inr h

theorem mem_merge (a b : List Nat) (x : Nat) : x ∈ merge a b ↔ x ∈ a ∨ x ∈ b := mem_fold b a x

theorem merge_idem (a : List Nat) : Same (merge a a) a := by
  intro x; rw [mem_merge]; constructor
  · intro h; rcases h with h | h <;> exact h
  · intro h; exact Or.inl h

theorem merge_comm (a b : List Nat) : Same (merge a b) (merge b a) := by
  intro x; rw [mem_merge, mem_merge]; exact Or.comm

theorem merge_assoc (a b c : List Nat) : Same (merge (merge a b) c) (merge a (merge b c)) := by
  intro x; simp only [mem_merge]; exact or_assoc

-- replaying the same fragments again changes nothing
theorem merge_replay (a b : List Nat) : Same (merge (merge a b) b) (merge a b) := by
  intro x; simp only [mem_merge]; constructor
  · intro h; rcases h with (h | h) | h
    · exact Or.inl h
    · exact Or.inr h
    · exact Or.inr h
  · intro h; exact Or.inl h

-- no duplicate key is ever introduced
theorem ins_nodup (l : List Nat) (k : Nat) (h : l.Nodup) : (ins l k).Nodup := by
  unfold ins
  split
  · exact h
  · rename_i hk
    rw [List.nodup_append]
    refine ⟨h, by simp, ?_⟩
    intro a ha b hb
    simp at hb; subst hb
    intro heq; subst heq; exact hk ha

theorem merge_nodup (b a : List Nat) (h : a.Nodup) : (merge a b).Nodup := by
  unfold merge
  induction b generalizing a with
  | nil => exact h
  | cons y t ih => exact ih (ins a y) (ins_nodup a y h)

/-! ## P4 is_a insertion keeps the graph acyclic -/
-- the graph: par c = some p means c is_a p (IsA.par). Reachability along parents.
abbrev Par := Nat → Option Nat
def step (par : Par) (x y : Nat) : Prop := par x = some y

inductive TG (r : Nat → Nat → Prop) (x : Nat) : Nat → Prop
  | single {y} : r x y → TG r x y
  | tail {y z} : TG r x y → r y z → TG r x z

inductive RT (r : Nat → Nat → Prop) : Nat → Nat → Prop
  | refl (x) : RT r x x
  | head {x y z} : r x y → RT r y z → RT r x z

theorem RT.trans {r : Nat → Nat → Prop} {x y z : Nat} (h1 : RT r x y) (h2 : RT r y z) : RT r x z := by
  induction h1 with
  | refl _ => exact h2
  | head h _ ih => exact RT.head h (ih h2)

theorem RT.tail' {r : Nat → Nat → Prop} {x y z : Nat} (h1 : RT r x y) (h2 : r y z) : RT r x z :=
  h1.trans (RT.head h2 (RT.refl z))

def Acyclic (par : Par) : Prop := ∀ n, ¬ TG (step par) n n

-- IsA.add's walk: from x upward, true if the child is met (x == child), with fuel
def hit (child : Nat) (par : Par) : Nat → Nat → Bool
  | 0, _ => false
  | f + 1, x => x == child || (match par x with | none => false | some y => hit child par f y)

theorem hit_sound (child : Nat) (par : Par) : ∀ f x, hit child par f x = true → RT (step par) x child := by
  intro f; induction f with
  | zero => intro x h; simp [hit] at h
  | succ f ih =>
    intro x h
    simp only [hit, Bool.or_eq_true, beq_iff_eq] at h
    rcases h with h | h
    · subst h; exact RT.refl _
    · cases hp : par x with
      | none => rw [hp] at h; simp at h
      | some y => rw [hp] at h; exact RT.head hp (ih y h)

theorem hit_complete (child : Nat) (par : Par) {x : Nat} (h : RT (step par) x child) : ∃ f, hit child par f x = true := by
  induction h with
  | refl x => exact ⟨1, by simp [hit]⟩
  | @head x y z hs _ ih =>
    obtain ⟨f, hf⟩ := ih
    refine ⟨f + 1, ?_⟩
    simp only [hit, Bool.or_eq_true, beq_iff_eq]
    right
    have : par x = some y := hs
    rw [this]; exact hf

-- the insertion (child gets parent); old parent of child, if any, is replaced
def upd (par : Par) (c p : Nat) : Par := fun x => if x = c then some p else par x

theorem TG.toRT {r : Nat → Nat → Prop} {x y : Nat} (h : TG r x y) : RT r x y := by
  induction h with
  | single hs => exact RT.head hs (RT.refl _)
  | tail _ hs ih => exact ih.tail' hs

-- main lemma: every path in the new graph is an old path, or goes old-path to c, the new edge, old-path from p
theorem upd_reach (par : Par) (c p x : Nat) {y : Nat} (h : TG (step (upd par c p)) x y) :
    TG (step par) x y ∨ (RT (step par) x c ∧ RT (step par) p y) := by
  induction h with
  | @single b hs =>
    simp only [step, upd] at hs
    by_cases hac : x = c
    · simp only [hac, ite_true] at hs
      have h2 : p = b := Option.some.inj hs
      subst h2; subst hac
      exact Or.inr ⟨RT.refl _, RT.refl _⟩
    · simp only [hac, ite_false] at hs
      exact Or.inl (TG.single hs)
  | @tail m e _ hs ih =>
    simp only [step, upd] at hs
    by_cases hmc : m = c
    · simp only [hmc, ite_true] at hs
      have h2 : p = e := Option.some.inj hs
      subst h2
      rcases ih with h | h
      · exact Or.inr ⟨hmc ▸ h.toRT, RT.refl _⟩
      · exact Or.inr ⟨hmc ▸ h.1, RT.refl _⟩
    · simp only [hmc, ite_false] at hs
      rcases ih with h | h
      · exact Or.inl (TG.tail h hs)
      · exact Or.inr ⟨h.1, h.2.tail' hs⟩

-- P4: if the walk from the parent never meets the child (IsA.add does not refuse), the graph with the new edge is still acyclic
theorem p4_add_acyclic (par : Par) (c p : Nat) (hac : Acyclic par)
    (hok : ∀ f, hit c par f p = false) : Acyclic (upd par c p) := by
  intro n hn
  rcases upd_reach par c p n hn with h | ⟨h1, h2⟩
  · exact hac n h
  · have hpc : RT (step par) p c := h2.trans h1
    obtain ⟨f, hf⟩ := hit_complete c par hpc
    rw [hok f] at hf; exact Bool.false_ne_true hf

-- P4, refusal side: if the parent already reaches the child (adding would close a cycle), the walk hits, so add refuses.
theorem p4_refuses_cycle (par : Par) (c p : Nat) (h : RT (step par) p c) : ∃ f, hit c par f p = true :=
  hit_complete c par h

-- a self-parent is refused
theorem p4_refuses_self (par : Par) (c : Nat) : hit c par 1 c = true := by simp [hit]

-- no false refusal: when the walk hits, the parent really reaches the child, so a cycle would have closed
theorem p4_refusal_is_cycle (par : Par) (c p : Nat) (f : Nat) (h : hit c par f p = true) : RT (step par) p c :=
  hit_sound c par f p h

end Props
