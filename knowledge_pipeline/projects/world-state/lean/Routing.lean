/-! Routing rules for LLM-labelled items (ledger T27). Votes are class ids. Checked on concrete cases; the general sum identity needs Mathlib and is NOT proved here. -/

/-- Vote counts per class: the soft label numerators. -/
def weights (classes votes : List Nat) : List Nat := classes.map (fun c => votes.count c)

/-- An item is unanimous when every vote equals the first. -/
def unanimous (votes : List Nat) : Bool := votes.all (fun v => v == votes.head!)

/-- Routing: agree = accept the label; split = keep the item with a soft target. No branch drops an item. -/
inductive Route | accept (c : Nat) | soft (w : List Nat)

def route (classes votes : List Nat) : Route :=
  if unanimous votes then Route.accept votes.head! else Route.soft (weights classes votes)

/-- R1. Four unanimous votes route to accept. -/
example : (match route [0,1,2] [1,1,1,1] with | Route.accept c => c == 1 | _ => false) = true := by decide
/-- R2. A 2 to 2 split routes to a soft target, not a drop. -/
example : (match route [0,1,2] [0,0,1,1] with | Route.soft w => w == [2,2,0] | _ => false) = true := by decide
/-- R3. The soft numerators add up to the number of votes (checked on both cases). -/
example : (weights [0,1,2] [0,0,1,1]).sum = 4 := by decide
example : (weights [0,1,2] [0,1,2,1]).sum = 4 := by decide
/-- R4. Totality: route returns a value for every input, so no item is left without a route. -/
theorem route_total (classes votes : List Nat) : ∃ r, route classes votes = r := ⟨_, rfl⟩
