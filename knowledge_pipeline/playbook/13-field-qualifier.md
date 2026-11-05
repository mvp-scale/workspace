# 13 · Field qualifier (triage before labelling)

**Position:** it sits between chapter 02 (guidelines) and chapter 03 (teacher labels). The 13 is a stable file ID, not the order; the README lists it in reading order.

**Goal:** decide at the start whether a field can be classed and measured, so a field is never defined at the end. Ledger T32, owner 2026-11-04. Basis: pilot annotation and guideline revision before scaling (the MATTER cycle, Pustejovsky and Stubbs; overview arXiv 1602.05753). No published go/no-go threshold was found; lines marked *ours* are ours and are set before the pilot, never after.

## The gate: a pilot of 50 to 100 items, local raters, no hosted spend

| # | Check | Pass line | Source of the line |
|---|---|---|---|
| 1 | Definable and measurable | The field is one checkable sentence with examples and boundary rules; announced, in-progress, planned and inferred cases each have a stated answer | *ours* |
| 2 | Reliable | Panel alpha lower end >= 0.667 on the pilot AND every rater's yes-rate (for yes/no fields) within 10 points of the others | alpha: Krippendorff 0.667 tentative band; the 10 points: *ours* |
| 3 | Enough real cases | At least 30 positives per answer in the pool the pilot is drawn from | *ours* (the Fit test 2 line) |
| 4 | Outside anchor | A public labelled source exists (even one-sided), or the reason there is none is written down | *ours* |
| 5 | Directly in the input | Each positive has a quoted span that alone states the answer; the share needing inference or background knowledge is reported; pass if at least 90 percent of positives have a valid span | *ours* |

## Outcome
- **GO:** all five pass.
- **REVISE:** checks 1 and 5 pass, at least one of 2, 3, 4 fails. Fix the definition (checks 2) or find cases or an anchor (3, 4). At most two rounds, each pre-registered on the ledger with a prediction.
- **PARK:** check 1 or 5 fails, or a second REVISE round still fails. Parked fields stay off the page as Ready and are not retrained.
- A field may be revised after GO; it never skips the gate.

The decision rule is checked in `projects/world-state/lean/FieldGate.lean`.
