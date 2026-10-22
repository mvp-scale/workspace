---
name: acceptance-criteria
description: Write and review acceptance criteria for trained classifiers (one atomic, measurable sentence per criterion, at source, data, model and pipeline level, with bars derived from a baseline and a ceiling). Use when asked to define, tighten, audit or score pass/fail criteria for a reader, a label set or an ontology area, or before any scorecard bar is set or moved.
---

# Acceptance criteria for classifiers

Parent method (generic, any label list or ontology; start there for a new list): `docs/research/2026-10-21 Acceptance criteria methodology (generic).md`.

Owner's rule: a criterion is not arbitrary. It is one clear, measurable sentence that measures the element AND a set of other characteristics around it. Sources are in the last section and in `docs/research/2026-10-20 Criteria best practices (sources).md`. Our own review: `docs/research/2026-10-20 Criteria review (Fable).md`. This skill only writes criteria; it never changes code, bars or the ledger by itself (bars move only with the owner's approval, ledger `--authorised-by`).

## Terms
- **Reader**: the classifier under test. **Teacher / judge**: the model or person whose labels are the reference. **Consumer**: whatever uses the reader's output (here the World engine).
- **Probe set**: a named set of items chosen to test one behaviour. **Slice**: a subset that matters on its own (an outlet, a region, a look-alike group).
- **Baseline**: score of a trivial or existing method. **Ceiling**: how well two competent judges agree with each other.
- **Gate**: a precondition that must hold before scoring means anything. **Graded criterion**: counts toward the grade. **Informational**: reported, no bar.
- **Wilson bound**: the statistical edge of what the true rate could be, given n items. With p observed: lower = (p + z2/2n - z*sqrt(p(1-p)/n + z2/4n2)) / (1 + z2/n), z = 1.96, z2 = 3.84 (standard formula; upper is the + version).

## 1. The atomic criterion template (every field required)

> On **<probe set: name, size n, how chosen, who labelled it>**, **<reader>** **<measure, in the unit the consumer uses>** for **<element / condition / slice>** is **<op> <bar>**, because **<derivation: baseline / ceiling / tolerance, with its id>**; it fails when **<concrete failing example, one real item>**.

Why each field (and source):
- Probe set with size, choice and labeller: a Datasheet's "composition, collection process" (Gebru 2021) and a probe that is "small and focused" (CheckList MFT, Ribeiro 2020). Without n you cannot say how sure the pass is (section 3).
- Measure in the consumer's unit: the ML Test Score checks quality where it is used (Breck 2017). If the engine cuts at 0.5, measure agreement at 0.5, not AP.
- Op and bar with a "because": a bar without derivation cannot be defended or moved (our review, principle 1).
- Fails when: the Given-When-Then habit of a concrete expected outcome (Gherkin: Then = "an expected outcome, or result"). If you cannot name a failing item, the criterion cannot fail.
- Atomic: one set, one scorer, one number, one example. Two numbers = two criteria. Gherkin advises 3-5 steps per example; a longer sentence is two criteria.

Context / action / outcome map: probe set = Given, reader reads = When, measure and bar = Then.

## 2. Four levels, each with its own rows

| Level | What it asks | Typical rows |
|---|---|---|
| SOURCE | Where do the texts come from, and do they look like what the reader will see? | outlet mix of the pool vs the live feed; share of items with empty description; language; date range; duplicates (same story, many outlets) |
| DATA | Is the labelled set fit to score and train on? | label agreement between judges (Krippendorff's alpha, section 3); balance (n positives per element); leakage (test items or near-duplicates in training); who labelled, with what codebook; frozen set never trained on |
| MODEL | Does the reader read? | overall quality; per-slice floors; flip and invariance tests; false alarms per 1,000; calibration; none case |
| PIPELINE | Do the parts connect? | labels made from exactly the text the reader sees; same preprocessing at train and serve; the consumer's tolerance (error the engine absorbs); conflict handling; end-to-end output vs the teacher-driven output |

Every area gets at least one row at each level. DATA and SOURCE rows are usually gates (they decide if MODEL rows mean anything); PIPELINE rows hold the real goal.

## 3. Circling the target (choosing criteria around one element)

Start from the goal (engine outputs inside tolerance) and ask of each ring: how far from the goal is it, and how would failing there show up?
- **LEFT / RIGHT = along the pipeline**: source -> data -> labels -> model -> engine. At least one criterion on each side of the model (what goes in, what comes out).
- **UP / DOWN = zoom**: area -> element -> slice (per outlet, per region, per rare label). A pooled number passes while a slice collapses ("global accuracy improved by 1% but accuracy for one country dropped by 50%", Breck 2017; slices defined as "application-critical data subsets", Chen 2019). Report each metric per group and intersection (Mitchell 2019).
- **SIDEWAYS = neighbours**: near-miss look-alikes (Niger / Nigeria), minimal edits that should NOT flip the label (invariance: change the outlet name, add a typo), minimal edits that SHOULD flip it (directional: "raises" -> "will raise"), and the none case (nothing is there). CheckList: INV = "label-preserving perturbations ... prediction to remain the same"; DIR = "the label is expected to change in a certain way"; both "test models on unlabeled data", so they can be large.

Sideways rings are also published as contrast sets (Gardner 2020: small manual edits "typically flipping the gold label" to probe the decision boundary) and counterfactual edits (Kaushik 2020: minimal rewrites that flip labels). Keep the ring current by adding the reader's newest near-misses each round (Dynabench, Kiela 2021). Source-stage checks and the none/abstain case have no verified primary source; they rest on our own review.

Coverage check: draw the element in the middle and mark one criterion in each of the six directions. An empty direction is a missing criterion, or a written reason it does not apply.

## 4. Characteristic families (what each element needs)

| Family | One-line test | Source |
|---|---|---|
| Overall quality | agreement with the reference at the consumer's cut-off, on a random frozen set | Breck 2017 (model quality validated before serving) |
| Per-slice floor | every slice with enough items clears an absolute floor | Breck 2017 ("error for slice x must be <5%"); Chen 2019 |
| No regression | an accepted criterion must not drop more than its interval vs the last release | Breck 2017 ("change in error for slice x must be <1%") |
| Minimum functionality | small named probe per behaviour (headline only, demonym only, several places) | CheckList MFT |
| Invariance | irrelevant edits leave the label alone | CheckList INV |
| Directional / flip | reversing the claim moves the label across the consumer's cut | CheckList DIR |
| False alarms | wrong claims per 1,000 items that lack the element, where the downstream cost is | our F-0020 tolerance |
| Direction of error | miss and false alarm bars set separately by cost | our review, principle 6 |
| Calibration | stated probability matches the observed rate, per band and per slice | Breck 2017 ("90% of predictions of probability 0.9 should in fact be positive") |
| None / abstain | items without the element get no claim | CheckList MFT on negatives |
| Simple baseline | the reader beats a trivial model | Breck 2017 (Model 5) |
| Definition reliability | judges agree on the label before it is used | Krippendorff 2011 |
| Documentation | probe set and labeller are written down | Gebru 2021, Mitchell 2019 |

## 5. Rules for bars

1. **Between a measured baseline and a measured ceiling.** Below the baseline the bar is empty; above the ceiling the reader would copy one judge's noise. Ceiling = teacher-teacher agreement on the same items (e.g. Jev vs Sonnet, topic 0.84, F-0049). Write "ceiling minus x" and fill it in when the agreement is measured; mark the value provisional until then. If no ceiling exists, the bar is "provisional" and the first task is to measure it.
2. **From the consumer's tolerance when it exists.** F-0020: TPR 0.95 with FPR up to 0.0025, or TPR 0.90 with FPR 0.001 (conditions only). A tolerance beats a ceiling-based bar. Where none is measured, add "run the tolerance test" as a task.
3. **Sample size decides what a pass proves.** Report the Wilson bound next to every share. 0 of 30 allows a true rate up to 11%; 0 of 120 up to 3.1%. A claim "at most x" needs n large enough that the bound is under x. For label agreement, size the set by the RAREST label, not total items: Krippendorff 2011 (Table 1) lists values needed for alpha_min .667 / .800 / .900 at p = .05, e.g. 103 values for a 50/50 binary label at .800 but 560 for a label with 5% frequency; reliability data should be "a probability sample" and keep sampling "until the least frequent kind is informationally adequate".
4. **Alpha cut-offs.** 0.8 accept, 0.667 the lowest tolerated, below it the element is not reliably readable (conventional; the 2011 paper confirms them as the alpha_min columns; the 2004 book wording is not opened, see Sources).
5. **Gates vs graded criteria.** A gate (codebook agreement, enough positives, speed, regression rule) is listed once per area and not in the grade. A graded row must be able to fail because of the reader. Test: would a reader that reads nothing pass it? Then it is a gate. The grade is a minimum over areas, not an average (Breck 2017: "taking the minimum of the scores").
6. **Informational labels.** If no consumer reads a label, report it with no bar until the owner says the consumer will read it.
7. **Provisional bars say so**, name who sets them, and name the measurement that replaces them.
8. **Probe sets are chosen without the reader's help** (not mined by keywords the reader keys on) and labelled blind to the reader's output.

## 6. Review checklist (run on any criteria set)
- [ ] Every row has all template fields, one number, one example of failure.
- [ ] Every bar has a derivation id (ledger item, measured ceiling, tolerance); round numbers marked provisional.
- [ ] Every bar is in the consumer's unit; no AP where the consumer cuts at a threshold.
- [ ] Each area has rows at all four levels, and each of the six directions has a criterion or a written reason.
- [ ] Each element has a slice floor, a flip or invariance test, a false-alarm rate, a none case.
- [ ] Probe set sizes support the claim (Wilson bound printed); no "0 swaps" on n < 100 stated as "never".
- [ ] No row passes for a reader that reads nothing; gates are outside the grade.
- [ ] Reference labels: labeller named, agreement measured, not made from text the reader does not see.
- [ ] Nothing graded that no consumer reads.
- [ ] Held by an MM3 verdict (local and hosted), splits reported, before the bar is used.

## 7. Worked examples (from `exports/world-engine-ontology.yaml`; numbers from our Criteria review, all provisional until its measurements run)

**Country (entry point: COUNTRY:x, else WORLD:world).**
On **P-lookalike (n = 120: 6 pairs x 20 stories, Niger/Nigeria, Sudan/South Sudan, DR Congo/Congo, North/South Korea, Guinea/PNG, Dominica/Dominican Rep.; mined by script from F, labelled by two blind reviewers)**, **the country reader** **counts swapped countries** for **each look-alike pair** **= 0 of 120 (Wilson upper bound 3.1%)**, because **a swap sends a story to the wrong population and has a predictable cause, and the current 0-of-30 pass (C5) is too small for the draft's own claim**; it fails when **"Niger floods displace 40,000" is read as Nigeria**.
Directions: LEFT source = outlet mix (irishtimes 0.61 recall, F-0072); UP slice floor per outlet >= 0.85 (n >= 60); SIDEWAYS look-alikes (above), invariance (swap "Sudan" for "Chad" in a template, label follows), none case (Georgia the state, club names: no wrong country, >= 95 of 100); RIGHT pipeline: wrong-country claims <= 30 per 1,000 (to be set by a country-tolerance run).

**Story type (engine cuts each probability at 0.5; fact 1.0, forecast/opinion 0.3, unclear 0.5; opinion >= 0.5 drops a story).**
On **J (n = 500 stories drawn at random from the frozen set F, labelled by Jev and Clef, Opus breaks ties)**, **the type reader** **puts the story in the same weight class (fact / forecast / opinion / unclear, after the 0.5 cut) as the jury** for **all stories** **>= ceiling minus 0.03 (provisional 0.90; ceiling = Jev-vs-Clef class agreement on J, not yet measured; Jev-vs-Sonnet per-label 0.71, F-0049)**, because **the weight class is all the engine takes from this area**; it fails when **"Why the Fed is wrong about inflation" is read as fact (enters at 3.3x its weight)**.
Siblings: opinion-as-fact <= 20 per 1,000 and fact-as-opinion <= 30 per 1,000 (separate, by cost); DIR flip: 90 of 100 script-made pairs "Fed raises rates" / "Fed will raise rates" change class; INV: outlet name or typo does not change class; headline-only slice within 0.05 of the overall; per-outlet floor >= 0.80 (bloomberg 0.79 today, F-0072).

**Conditions (78 condition|direction keys; a reading = exactly one direction >= 0.65; both = dial dropped).**
On **F (n = 11,997 stories, 125 outlets, Jev labels, never trained on; the 16 key keys of S-0003 first)**, **the condition reader** **has true-positive rate and false-alarm rate** for **each key, e.g. housing_cost|up** **inside TPR >= 0.95 with FPR <= 0.0025, or TPR >= 0.90 with FPR <= 0.001**, because **F-0020 measured that the engine stays inside its own run-to-run noise there**; it fails when **asset_values|up recall is 0.67 at its false-alarm threshold (k6k8.json)**.
Siblings: false alarms <= 2.5 per 1,000 per key (F-0020); conflict rate (both directions fire) <= Jev's + 5 per 1,000; DIR: 90% of 20 pairs per key "rents rose" / "rents fell" flip across 0.65; none case: sport and recipe stories get no reading; calibration bands 0.65-0.8, 0.8-0.9, 0.9-1.0 within 0.10; gate: a key is graded only once Jev-vs-Clef agreement on its positives is >= 0.6 (else "not readable from headline + 250 characters").

## Sources (opened and read; details and quotes in the research note)
- Ribeiro, Wu, Guestrin, Singh. Beyond Accuracy: Behavioral Testing of NLP models with CheckList. ACL 2020. https://arxiv.org/abs/2005.04118
- Breck, Cai, Nielsen, Salib, Sculley. The ML Test Score. IEEE Big Data 2017. https://research.google/pubs/pub46555/
- Chen et al. Slice-based Learning. NeurIPS 2019. https://arxiv.org/abs/1909.06349
- Mitchell et al. Model Cards for Model Reporting. FAT* 2019. https://arxiv.org/abs/1810.03993 (abstract only)
- Gebru et al. Datasheets for Datasets. CACM 2021. https://arxiv.org/abs/1803.09010 (abstract only)
- Krippendorff. Agreement and Information in the Reliability of Coding. Communication Methods and Measures 2011. https://repository.upenn.edu/server/api/core/bitstreams/86b17550-83f8-422c-9ff0-628df92e1120/content
- Cucumber. Gherkin Reference. https://cucumber.io/docs/gherkin/reference
- Not verified, not cited as fact: Krippendorff 2004 (book, the "0.8 / 0.667 tentative" wording); Brown, Cai, DasGupta 2001 (Wilson interval; paper not opened, formula given as standard statistics).
- From the Haiku circling note, re-opened by me (abstract pages): Gardner et al. 2020, Evaluating Models' Local Decision Boundaries via Contrast Sets, https://arxiv.org/abs/2004.02709 ; Kaushik, Hovy, Lipton, ICLR 2020, https://arxiv.org/abs/1909.12434 ; Kiela et al., Dynabench, NAACL 2021, https://arxiv.org/abs/2104.14337
- The Haiku practitioner note (`docs/research/2026-10-21 Criteria practitioner sources (Haiku).md`) reports that none of its 13 vendor-doc sources gives a numeric acceptance threshold; not cited here. Its other entries are unchecked by me. The circling method in section 3 is the owner's.
