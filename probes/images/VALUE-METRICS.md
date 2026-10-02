# Value metrics: five numbers per expert image-review workflow

Purpose: pick demo targets where a vision model's first pass could take about 70% of an expensive expert's routine image work, while the expert keeps the hard 30% and the sign-off. Every candidate is scored on the same five measurable metrics, each with a unit, a source URL and an evidence grade.

Evidence grade: **A** regulator, rate card, peer-reviewed study, official statistics. **B** industry body or trade press quoting a primary figure. **C** vendor claim. **D** none (leave the number blank).

| # | Metric | Unit | How it is measured | Bar for a "go" |
|---|---|---|---|---|
| M1 | Cost per case today | US$ per case or engagement, fully loaded | expert fee or rate card x hours, or a published fixed price | at least $5,000 (or $500+ per image-heavy unit repeated 10+ times per case) |
| M2 | Expert hours per case | hours | published time-and-motion figure, fee schedule hours, or survey | at least 8 h |
| M3 | Routine first-pass share | % of M2 spent on first-pass image screening (finding, counting, classifying, checking against a checklist), not judgement or sign-off | time-and-motion study, expert survey, or the structure of the standard report | at least 40% |
| M4 | Annual case volume | cases per year (national, plus a typical single client) | regulator or industry statistics | at least 1,000 per year nationally |
| M5 | Cost of a miss and required sensitivity | US$ per missed finding (or liability or regulatory penalty) and the sensitivity the field demands | claim data, fines, standards (for example a required detection rate) | stated, not blank |

Derived (computed, not guessed):
- **Addressable spend per year** = M1 x M3 x M4
- **Pitch number per client** = Addressable spend per client x 70% (the share a first pass could take)
- **Triage bar** = the confidence level at which the model's answers must be right at M5's required sensitivity

A workflow only counts as a demo target if it is also **testable**: the expert's first pass can be written as at least 10 typed yes/no or pick-one questions, and at least 25 images with answers that come from a dataset's own annotation or a generator exist or can be drawn.
