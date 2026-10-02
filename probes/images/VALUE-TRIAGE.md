# Where the money is: value triage across the image lab

Merged from seven research agents (five domain slices, medical, and workflows outside the 50 domains) and joined to what the lab measured on Winnow. The idea: a model that answers confidently and correctly on the easy ~80% lets people review only the uncertain ~20%. That only pays where (a) a person does a high-volume, per-item review today, and (b) the model's confident answers are actually right.

## How to read this

**Evidence grade on every cost claim** (set by the type of source, not checked by me; I did not open the URLs):
- **A** regulator, peer-reviewed trial, FDA clearance, or a government rate card
- **B** industry benchmark body or trade press quoting one (APQC via CFO.com, ComplexDiscovery, NRF)
- **C** vendor blog or vendor case study
- **D** no source, or the agent said unverified

**Two corrections to the agents' method.** They ranked by macro totals (the $696B tax gap, $220B crop-pest losses, $467B counterfeit trade). Those are not savings from triage. The numbers that matter are per-item cost x volume x share a model can clear. Where an agent gave a per-item cost I used it; otherwise the row says "no per-item figure". Also, one agent wrote a file despite a read-only instruction (`/tmp/d11_d20_analysis.md`, the full goods-and-logistics table). It was harmless.

**"Auto-handled" from the lab** is measured, not guessed: the share of the 25 images the model answers with no mistakes when taken from most confident down (`handled @ 100% right`), and the share handled at 95% or better precision. 25 images is small, so read these as indicative.

## 1. Pilot first: real money, per-item evidence, and the lab shows it works

| Workflow | Per-item cost evidence | Lab task | Handled cleanly (95% precision) | Consistency |
|---|---|---|---|---|
| Invoice, receipt and cheque data entry and checking (AP) | APQC median about $6 per invoice, $10+ in the bottom quartile (B) | t01 invoice fields, t02/t32 receipts, t06 cheques | 92% to 100% | holds |
| Utility meter and gauge reading | $18 to $22 per manual read, 64% of US meters still manual (agent gave no source link; D) | t36 meter, t22 gauge | 100% | holds |
| Document type and page routing (tax forms, contracts, archives) | per-document cost not found; IRS and NARA volumes are context only | t03 document type, t07 charts | 84% and 80% | holds |
| Licence-plate reading (tolling, parking, access) | no per-item figure | t16 plates | 92% | holds |
| Brand and logo recognition (counterfeit and brand-safety screening) | OECD counterfeit-trade total only, no per-item (A for total) | t17 logos | 100% | holds |
| Concrete crack screening (buildings, bridges) | FHWA 24-month cycle on about 620,000 bridges (A); $4,200 per inspection is vendor-sourced (C) | t11 cracks | 100% | holds |
| Produce freshness at receiving | USDA ERS loss rates of 11.6% (vegetables) and 12.6% (fruit) (A) | t15 fresh/rotten | 92% | holds |

For these the "filter 80%" story is supported. Table-reading and transcription tasks reach 80% to 100% handled at 95% precision; the ones that go lower are the ones with more steps (t31 receipt line count: 40%).

## 2. Big money but the model is not ready: do not pitch yet

| Workflow | Money case | Lab task | Handled at 95% precision | Why |
|---|---|---|---|---|
| Vehicle damage at first notice of loss | insurance fraud and leakage totals (vendor and Coalition estimates, C/B) | t09 | 0% | model is consistently wrong; negatives are parts-only photos, so the label is weak too |
| Fire and smoke detection | NFPA total fire loss (B) | t19 | 0% | never reaches the confidence bar even at 76% accuracy |
| Out-of-stock shelf gaps | IHL $1.2T/year (C) | t13 | 28% | fragile under rewording |
| Road damage | UK and US pothole-damage totals (B) | t37 | 28% | fragile |
| Parking free spots | INRIX driver time (B) | t26 | 8% | accuracy fell from 19/25 to 11/25 under option reorder |
| Herd and cattle counts, crop disease, pigs, floorplan doors | agri totals (macro only) | t27, t38, t23, t28, t29 | 0% to 16% | counting and fine detail |
| Screenshot element triage | IT support tier costs ($6 vs $35+, C) | t24 | 4% | label is instruction-derived |

Several of these have a strong money story and should be the focus of any improvement work, but they cannot be sold as "filter 80%" today.

## 3. High money, no lab task yet (testable data exists or is close)

From the agents; every figure here is as reported and unverified.

| Workflow | Cost or volume claim (grade) | Data status |
|---|---|---|
| Tax form page identification | IRS tax-gap total only (A, macro) | NIST SD2 rated USE |
| E-commerce returns condition grading | 600M+ US returns, about $10 to $15 labour each (C) | no open dataset; vendor/proprietary |
| Legal e-discovery image and document review | $6.9B/year review spend (B); $0.50 to $1.00 per document | partly image; TREC data, unverified |
| KYC / identity document checks | $13 to $130 per individual check (C) | synthetic ID sets only |
| Hotel room turnover checks | about $48 per room labour, 25 to 45 minutes (B) | no open data |
| Food-safety inspection photos | FSIS rate about $226/hour (A) | no open data |
| Recycling contamination | municipal fines $24k to $75k a year (A, city pages) | TrashNet rated USE |
| Power line insulator and cable faults | $28B outage figure is a vendor claim (C); drone vs helicopter cost differences from PwC (B) | one dataset rated USE |
| Tyre condition | NHTSA deaths (A, macro) | one dataset rated USE |
| Sewer CCTV defect coding | $113 to $244 per inspection (B/C) | not verified |
| Construction permit review | $200 to $439/hour plan-review rates (A, city rate card) | no open data |

## 4. Medical first-line triage

The agent found the strongest published triage results of any domain. As reported, not verified:
- **Mammography:** a published randomised trial (MASAI) reported 44% less screen-reading workload with more cancers found (A, trial; the link was a trade site).
- **Diabetic retinopathy:** FDA-cleared autonomous systems report about 87% to 93% sensitivity at 90%+ specificity (A).
- **Chest X-ray, fractures, skin, pathology:** published triage studies exist; backlog is documented (UK: 976,000 scans waiting more than a month, B).

**Dataset cautions: the agent's USE ratings are too generous.**
- MIMIC-CXR and CheXpert labels are extracted from reports by text mining. That is machine labelling, which our rules reject; the agent rated MIMIC-CXR "USE" and gave it a CC-BY licence, but it is credentialed (gated) data with its own terms.
- APTOS was described as biopsy confirmed. Diabetic retinopathy grades are by ophthalmologists, not biopsy.
- CBIS-DDSM is 163 GB and Camelyon slides are gigapixel images, neither fits our "sample first" and 1536 px limits.
- Realistic first candidates: **ISIC / HAM10000** (pathology-confirmed, CC-BY-NC, open), **MURA** (radiologist normal/abnormal, needs the Stanford agreement), and a diabetic-retinopathy set with expert grades after checking its terms.

Anything medical goes in the lab labelled **research only, not for clinical use**, and stays out of the business-readiness summary.

## 5. What I would do next

1. **Verify the ten numbers that matter** by opening the primary source: APQC $6/invoice, meter-read cost, FHWA bridge cycle, USDA loss rates, MASAI, IDx-DR, ComplexDiscovery, NRF shrink, hotel labour, FSIS rate.
2. **Add a "Value" view to the Image Lab:** per workflow, cost evidence with its grade, lab task, handled share, consistency, so the page itself answers "where is it worth piloting".
3. **Build medical tasks** from the open, expert- or pathology-labelled sets (skin first), with the research-only banner.
4. **Fix the weak money cases** (t09 labels, t19, t13) before presenting them.

## Appendix: handled share per lab task (Winnow, 25 images each)

`clean` = answered most-confident first with no mistakes; `95%` = largest share handled at 95% or better precision.

| Task | accuracy | clean | 95% |
|---|---|---|---|
| t01 invoice fields | 25/25 | 100% | 100% |
| t02 receipt capture | 22/25 | 84% | 92% |
| t03 document type | 22/25 | 68% | 84% |
| t04 signature | 13/25 | 44% | 44% |
| t05 form completeness | 25/25 | 100% | 100% |
| t06 cheque amount | 25/25 | 100% | 100% |
| t07 chart reading | 22/25 | 64% | 80% |
| t08 handwritten line | 25/25 | 100% | 100% |
| t09 vehicle damage | 12/25 | 0% | 0% |
| t10 damaged part | 21/25 | 72% | 84% |
| t11 property damage | 25/25 | 100% | 100% |
| t12 package condition | 18/25 | 32% | 32% |
| t13 shelf out of stock | 12/25 | 28% | 28% |
| t14 count items | 13/25 | 32% | 32% |
| t15 fresh/rotten | 22/25 | 48% | 92% |
| t16 licence plate | 23/25 | 88% | 92% |
| t17 logo | 24/25 | 96% | 100% |
| t18 hard hat | 20/25 | 64% | 64% |
| t19 fire/smoke | 19/25 | 0% | 0% |
| t20 floor hazard | 18/25 | 32% | 32% |
| t21 surface defect | 14/25 | 16% | 16% |
| t22 gauge | 24/25 | 96% | 100% |
| t23 crop disease | 18/25 | 16% | 16% |
| t24 screenshots | 12/25 | 4% | 4% |
| t25 room type | 17/25 | 36% | 36% |
| t26 parking | 19/25 | 8% | 8% |
| t27 herd count | 14/25 | 0% | 0% |
| t28 pigs standing | 11/25 | 12% | 12% |
| t29 floorplan doors | 9/25 | 8% | 8% |
| t30 damage severity | 14/25 | 24% | 24% |
| t31 receipt lines | 21/25 | 40% | 40% |
| t32 receipt total | 24/25 | 96% | 100% |
| t36 meter reading | 24/25 | 96% | 100% |
| t37 road damage | 14/25 | 28% | 28% |
| t38 cattle count | 19/25 | 16% | 16% |
