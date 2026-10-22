# Acceptance criteria for a trained classifier: a generic method

Date 2026-10-21. Parent of `.claude/skills/acceptance-criteria/SKILL.md` (which keeps the sentence template, the checklist and our worked examples). This note is domain-agnostic: give it a list of labels, or an ontology (areas, each with elements), and it produces a short, defensible set of pass/fail criteria. Our own project appears only in the appendix. Nothing here changes code, bars or the ledger.

## 0. The idea in one paragraph
Decomposing the label list tells you WHAT to test. It does not tell you how good is good enough, or how much each test matters. So three jobs stay separate: (a) decomposition builds a matrix of things that could be tested; (b) risk picks the cells worth testing; (c) bars come from measurement (a baseline, a ceiling set by how well two judges agree, and what the consumer can tolerate), and weights come from the cost of each kind of error. And before any criterion on an element counts, the element's definition must be shown to be one that judges can apply the same way.

## 1. Terms
- **Element**: one label (or one label|direction key). **Area**: a group of elements (an ontology branch). A flat label list is one area.
- **Consumer**: whatever uses the classifier's output (a router, a score, a filter, a person), and *how*: a cut-off, a weight, a count.
- **Reader**: the classifier under test. **Judge**: a person or model whose labels are the reference. **Ceiling**: how well two competent judges agree with each other on the same items. **Baseline**: score of a trivial or existing method. **Tolerance**: how much reader error the consumer absorbs before its own output is wrong.
- **Characteristic family**: a kind of property to test (overall quality, slice floor, invariance, ...; section 4, step 3). **Level**: source, data, model, pipeline (the skill, section 2). **Slice**: a subset that matters on its own. **Probe set**: a named set of items chosen to test one cell.
- **Gate**: precondition that must hold before scores mean anything; not graded. **Graded criterion**: counts toward the grade. **Informational**: reported, no bar.
- **Wilson bound**: the edge of what the true rate could be given n items (formula in the skill, section Terms). 0 of 30 allows a true rate up to 11%; 0 of 120, up to 3.1%.
- **Krippendorff's alpha**: agreement between judges beyond chance. 1 = perfect, 0 = chance.
- **Six directions** (from the skill): LEFT/RIGHT = along the pipeline (source, data, labels, model, consumer); UP/DOWN = zoom (area, element, slice); SIDEWAYS = neighbours (near-miss look-alikes, edits that must not flip the label, edits that must, the none case).

## 2. Inputs (collect before step 1)
1. **The label list or ontology**: element names, one-line definitions, which area each sits in.
2. **The consumer**: what reads each element's output, and how (cut-off value, weight, count, human queue), and what each kind of error costs there. If you cannot say, step 1 will find the elements nobody reads.
3. **Reference judges**: at least two independent judges (people, or models from different vendors), a written codebook, and a budget for labelling.
4. **A pool of real, unlabelled items** that looks like what the reader will see live, and a frozen part of it that nobody trains on.

## 3. The method at a glance
| # | Step | Output | Stop rule |
|---|---|---|---|
| 1 | List elements and what the consumer reads | Element register | Every element is "read by X" or "informational" |
| 2 | Validate each definition | Agreement table | Every graded element has alpha >= 0.667 on enough items, else it is fixed or dropped |
| 3 | Build the characteristic matrix | Matrix (section 5) | Every element row has every family cell filled with "candidate" or "n/a + reason" |
| 4 | Select cells by risk | Selected cells | Coverage rule met (all six directions or a written reason) |
| 5 | Measure baseline, ceiling, tolerance | Three numbers per selected cell (or "not yet measured") | Each has a run id or is marked provisional |
| 6 | Set bars | Bar, n, bound per cell | Baseline < bar <= ceiling (or tolerance), and n supports the claim |
| 7 | Write atomic sentences | One sentence per cell | Template fields complete, one number, one failing example |
| 8 | Split gates from graded; grade | Gate list, graded list, grade rule | A reader that reads nothing fails every graded row |
| 9 | Review | Checklist signed, independent reviewer's verdict | Checklist clean; splits between reviewers recorded, not resolved by picking one |
| 10 | Maintain | Updated sets and bars | Each round: near-misses refreshed; bars re-derived when ceiling or tolerance moves |

## 4. The steps

### Step 1. List the elements and what the consumer reads
- Input: label list or ontology; the consumer's description.
- Do: write one row per element: name, one-line definition, area, who reads it, how, cost of a miss, cost of a false alarm (low / medium / high is enough). Elements nobody reads are marked **informational** (reported, no bar, until a consumer is named). Elements the consumer reads only in combination (e.g. "exactly one of two directions must fire") get a note: the combination is the thing to test.
- Output: element register. Stop when every row is read-by or informational.

### Step 2. Validate each definition before any criterion on it counts
- Why: a criterion on a label that judges cannot apply the same way measures noise (Krippendorff 2011, section 7 here).
- Do: two or more judges label the same random sample blind to each other and to the reader. Compute alpha per element (binary: the element present or not). Size the sample by the **rarest** element, not by total items: the paper's table gives values needed for alpha_min .800 at p = .05 of 103 for a 50/50 label and 560 for a 5%-frequency label; keep sampling "until the least frequent kind is informationally adequate". If a rare element is too scarce in a random sample, add positives found by any method, but keep them out of the random-sample statistics.
- Cut-offs (conventional; the 2011 paper's alpha_min columns): alpha >= 0.800 accept; 0.667 to 0.800 tolerated, bar marked provisional; below 0.667 the element is not reliably readable.
- Below 0.667: tighten the definition or merge or split the label, re-test; if it still fails, mark informational. Do not write bars on it.
- Output: agreement table (element, n, positives, alpha, verdict). Stop when every graded element passes or is dropped. The same table gives the **ceiling** for step 5.

### Step 3. Build the characteristic matrix
Rows are elements. Columns are characteristic families, each applied at the levels where it makes sense. This matrix idea is the one CheckList uses (capabilities by test types, Ribeiro 2020) and is the matrix form of the classification tree (section 7).

| Family | One-line test | Typical level |
|---|---|---|
| Overall quality | Agreement with the reference at the consumer's cut-off, on a random frozen set | model |
| Slice floors | Every slice with enough items clears a floor | model, source |
| No regression | Not worse than the last accepted release beyond its interval | model |
| Minimal-functionality probes | Small named probe per behaviour (e.g. headline only) | model |
| Invariance | Irrelevant edits leave the label alone | model |
| Directional / flip | Edits that reverse the claim move the label across the cut | model |
| Near-miss neighbours | Look-alike items from a different element get no claim | model |
| None case | Items without any element get no claim | model |
| False alarms by direction | Wrong claims per 1,000, miss and false alarm set apart by cost | model, pipeline |
| Calibration | Stated probability matches the observed rate, per band and slice | model |
| Definition reliability | Judges agree (step 2) | data |
| Source fit | Pool looks like the live feed (mix, language, empty fields, duplicates) | source |
| Label provenance | Reference labelled from exactly the text the reader sees; frozen set never trained on; no near-duplicate leakage | data, pipeline |
| End-to-end | Consumer's output with the reader vs with the reference | pipeline |

Partitioning each element's input space (what the slices, probes and near-misses ARE) uses the classification-tree and equivalence-partition ideas (section 7): pick several aspects (source, length, language, phrasing, look-alike group); split each aspect into classes that do not overlap and together cover everything; a slice is a class or a pair of classes. For ordered aspects (text length, score near the cut-off), also test the edges of each class, as boundary-value analysis does.

Stop when no cell is blank. A cell can be "n/a" only with a reason.

### Step 4. Select cells by risk
- Score each candidate cell: **likelihood** (how likely the reader fails there: use the baseline, past errors, rarity, known confusions) times **downstream cost** (from step 1; the cost of the error the cell guards). Low / medium / high mapped to 1 / 2 / 3 is enough; ISTQB defines the same product-risk logic, risk level = likelihood x impact, and says it decides test scope and thoroughness (section 7).
- Rule: test all cells scoring 6 or 9; sample the 3s and 4s (one per family per area); report the 1s and 2s informationally or skip with a written reason.
- **Coverage rule**: every graded element has at least one selected cell in each of the six directions (or a written reason one does not apply). This follows the NIST finding that failures come mostly from one factor or an interaction of two (section 7): cover every single factor and every pair of (element x one other aspect) before spending effort on three-way interactions. For a high-risk element, add selected three-way cells (element x slice x edit type).
- Output: the selected-cell list. Stop when the coverage rule holds.

### Step 5. Measure the baseline, the ceiling and the tolerance
- **Baseline**: score a trivial method (majority class, keywords, the old system) on the cell's probe set.
- **Ceiling**: judge-vs-judge agreement on the same items, in the cell's measure (from step 2 for overall cells; measure again for slices and probes).
- **Tolerance**: perturb the consumer with synthetic reader errors at several error rates and find where its output leaves its own run-to-run noise. This is the only way to get a bar from the consumer rather than from the judges. If you cannot run it yet, write "tolerance not measured" and make the run a task.
- Output: three numbers per cell, each with a run id, or "not yet measured". Stop when each is measured or marked provisional.

### Step 6. Set the bars
1. A tolerance, when measured, beats a ceiling-based bar.
2. Otherwise: the bar lies **above the baseline and at or below the ceiling** (write "ceiling minus x"). Above the ceiling the reader would copy one judge's noise; at or below the baseline the bar is empty.
3. Weight error directions by cost: set miss and false-alarm bars apart, tighter on the dearer one.
4. Choose n so a pass proves the claim. For "at most x": n large enough that the Wilson upper bound is below x. For "at least y": the Wilson lower bound must clear y, so set the pass line on the bound, not the point value. Size by the rarest class in the probe set.
5. Round numbers with no derivation are labelled **provisional**, with the measurement that replaces them.
- Output: bar, n, bound rule, derivation id for each cell. Stop when each cell passes the baseline < bar <= ceiling test.

### Step 7. Write each selected cell as one atomic sentence
Template (from the skill): "On [probe set: name, size n, how chosen, who labelled] the reader's [measure, in the consumer's unit] for [element / slice] is [op] [bar], because [baseline / ceiling / tolerance + id]; it fails when [one real failing item]." One set, one scorer, one number, one example. Two numbers are two criteria. If you cannot name a failing item, the criterion cannot fail. Probe sets are chosen without the reader's help and labelled blind to its output.

### Step 8. Split gates from graded criteria; grade
- Gate: definition reliability, minimum positives, regression rule, source fit, label provenance. Listed once per area, outside the grade.
- Graded: every row a bad reader can fail. Test: would a reader that reads nothing pass it? Then it is a gate.
- Grade = **minimum over areas** (and over families within an area if you want the strict form), not an average (Breck 2017: "taking the minimum of the scores"). A strong area cannot buy back a weak one.
- Output: gate list, graded list, grade rule. Stop when the nothing-reader test fails every graded row.

### Step 9. Review
Run the skill's checklist (section 6 there). Then give an independent reviewer the criteria and the evidence, not your conclusion, and ask for a verdict per row. With two reviewers (e.g. a local model and a hosted one) record splits as splits; do not resolve them by picking one. Fix and re-review once; remaining splits go to the owner as a list.

### Step 10. Maintain
- Each training or release round: add the reader's newest near-misses and failures to the sideways probe sets (Dynabench, Kiela 2021, idea only) and re-run.
- Re-derive a bar when its ceiling moves (judges retrained, codebook changed) or its tolerance moves (consumer changed). A bar that moved for any other reason is a defect.
- Re-run step 2 when a definition changes. Keep the frozen set frozen.

## 5. Blank template (copy per area)
One row per selected cell. Fill each of the seven columns; empty means the step is not finished.

| Element | Characteristic family | Level | Risk (L x C) | Probe set (name, n, how chosen, labeller) | Measure + bar + derivation (id) | Fails when (one item) |
|---|---|---|---|---|---|---|
| | | | | | | |

Element register (step 1):

| Element | Definition | Area | Read by / how | Cost of miss | Cost of false alarm | Alpha (n) | Status |
|---|---|---|---|---|---|---|---|
| | | | | | | | graded / informational / fix |

Coverage check per graded element (tick or write the reason):

| Element | Left (source) | Right (consumer) | Up (area) | Down (slice) | Sideways (near-miss / invariance / flip / none) |
|---|---|---|---|---|---|

## 6. Worked mini-example (all numbers are illustrative, made up to show the method)
A support-ticket classifier with 5 labels and a "none" outcome: `billing`, `bug`, `how_to`, `account_access`, `cancel_request`. One area.

**Inputs.** Consumer: a router. A label with probability >= 0.6 sends the ticket to that team's queue; otherwise it goes to a human triage desk. `cancel_request` also pages the retention team, who call within an hour. `account_access` is urgent (locked-out customers). Judges: two support leads plus one model, a written codebook, 4,000 tickets per day live.

**Step 1.** Register: billing (read by Finance queue; miss = delay, false alarm = small), bug (Engineering queue; miss = delay), how_to (Docs queue; both cheap), account_access (miss = customer locked out: high; false alarm = low), cancel_request (miss = customer lost: high; false alarm = a wasted retention call: medium). Nothing is unread, so none is informational.

**Step 2.** Random sample of 600 tickets, two judges blind. Rarest label: `cancel_request` at 5% (about 30 tickets), below the 560-value line for alpha_min .800, so 100 more cancel candidates are added from a keyword search and kept out of the random-sample statistics. Alpha: billing .86, bug .81, account_access .88, cancel_request .84, how_to .61. `how_to` is below .667: the judges disagree on "how do I..." vs "feature request". The definition is split into `how_to` and `feature_request` and re-tested (alpha .79 and .70). Ceiling for `cancel_request` = judge-judge recall of .90 on the positives.

**Step 3.** Matrix 6 elements by the 14 families = 84 candidate cells. Slices chosen from aspects (classification-tree style): channel (email / chat / app store review), length (< 20 words / longer), language (English / Spanish). Near-miss neighbours: `cancel_request` vs "cancel my last order" (billing/order cancel), "cancel the meeting invite" (none); `account_access` vs `bug` ("app crashes at login").

**Step 4.** Risk (likelihood x cost), 1 to 3 each. `cancel_request` miss: likelihood 2 (rare, indirect phrasing), cost 3 = 6, tested. `cancel_request` false alarm vs order-cancel look-alikes: 3 x 2 = 6, tested. `account_access` miss on app-store reviews: 2 x 3 = 6, tested. `how_to` slice floors: 2 x 1 = 2, informational. Coverage rule: for `cancel_request` all six directions get a cell: LEFT outlet/channel mix of pool vs live; RIGHT retention pages per 1,000 tickets; UP area-level routing accuracy; DOWN channel slice; SIDEWAYS look-alike set, flip pair ("I want to cancel" vs "I do not want to cancel"), invariance (add a typo), none case. Selected: about 20 of the 84 cells.

**Step 5.** Baseline (keyword rule "cancel") on the cancel probe set: recall .55, false alarms 38 per 1,000. Ceiling: .90 recall. Tolerance (run: inject false cancel pages into a replay of one week): the retention team can take 40 extra pages per day, which is 10 per 1,000 tickets, i.e. a false-alarm rate of 1%.

**Step 6.** Recall bar: ceiling minus .03 = .87, provisional until the replay of a second week. n: 100 positives gives, at an observed .90, a Wilson lower bound of .83, which is under the bar, so the pass line is set on the bound: observed >= .94 at n = 100, or raise n to 300. False alarms: the tolerance gives <= 1% on 900 non-cancel tickets; the Wilson upper bound stays <= 1% only for 3 or fewer false alarms of 900 (4 gives 1.14%), so the pass line is <= 3 of 900. Look-alike swaps: 0 of 120 (upper bound 3.1%) rather than 0 of 30 (11%).

**Step 7.** Example sentence: "On CANCEL-L (n = 120: 40 each 'cancel last order', 'cancel meeting', 'cancel subscription trial' look-alikes, mined by script from the pool, labelled by two blind support leads), the reader's count of tickets wrongly labelled `cancel_request` is <= 3 of 120 at cut 0.6 (derived from the 1% retention-page tolerance, run R-7), because the retention team can absorb 10 extra pages per 1,000; it fails when 'Please cancel my meeting invite' pages retention."

**Step 8.** Gates: alpha >= .667 per label, >= 100 positives per label, source fit (channel mix of pool within 5 points of the live week), frozen set never trained on. Graded: the roughly 20 cells. A reader that always says "none" fails every recall row, so no graded row is secretly a gate. Grade = lowest of the area's cell results.

**Step 9.** Checklist: the `how_to` row used AP, not agreement at the 0.6 cut, so it is rewritten in the router's unit. Independent reviewer: flags that no probe covers Spanish app-store reviews; one added. Reviewer split on whether feature_request needs a bar: recorded for the owner.

**Step 10.** Next round: add the 15 tickets the reader mislabelled to CANCEL-L; if the retention team's capacity changes to 60 extra pages per day, re-derive the false-alarm bar from the new tolerance.

## 7. What the sources support (opened and read; see section 9)
- **Classification-tree method** (Grochtmann and Grimm 1993): the input domain is seen through several aspects, each split into disjoint, complete classes that can be refined; test cases are formed by combining classes from different classifications; the tree is turned into a combination table. We use this for building the matrix rows and slices (step 3). Only the Crossref abstract was opened, not the full paper; the claim that the tree-building step was informal is from a search summary, not opened, and is not relied on.
- **Equivalence partitioning and boundary-value analysis** (ISTQB CTFL v4.0.1, sections 4.2.1 and 4.2.2): EP divides data into partitions "based on the expectation that all the elements of a given partition are to be processed in the same way by the test object", so one test per partition suffices; BVA exercises the boundaries of partitions and "can only be used for ordered partitions". Our adaptation: a classifier does not treat a partition uniformly, so we test each partition with n items and a bound, not one representative (this adaptation is ours, not the syllabus's). Boundary values map to the consumer's cut-off and ordered attributes.
- **Risk-based testing** (ISTQB CTFL v4.0.1, section 5.2): product risk analysis focuses test effort to minimise residual risk; "in the quantitative approach the risk level is calculated as the multiplication of risk likelihood and risk impact", in the qualitative approach by a risk matrix; results decide scope, thoroughness and priority.
- **Combinatorial testing** (NIST SP 800-142, Kuhn, Kacker, Lei 2010): the interaction rule, "most failures are induced by single factor faults or by the joint combinatorial effect (interaction) of two factors, with progressively fewer failures induced by interactions between three or more factors"; pairwise "may miss 10% to 40% or more of system bugs", so not enough for mission-critical software. Note that these are findings about software faults, not about classifier errors; we use them only as the reason to cover single and pair cells first, and add three-way cells for high-risk elements.
- **CheckList, ML Test Score, slices, Krippendorff, Gebru, Gardner, Kaushik, Kiela**: as listed in the skill and the 2020-10-20 and 2021-10-21 notes.

## 8. Appendix: how our news ontology maps onto this
- Labels and areas: the World engine ontology (`exports/world-engine-ontology.yaml`): areas country, story type, scope, topic, conditions; elements are countries, story types, topics and 78 condition|direction keys.
- Consumer (step 1): the World engine, which cuts each probability at a threshold (0.5 for story type, 0.65 for conditions), weights story types, and drops a story when both directions of a condition fire.
- Judges (step 2): Jev (hosted, never sees article text) and Clef (local), Opus as tie-break; ceiling = Jev-vs-Clef agreement, measured per element.
- Tolerance (step 5): the engine tolerance measured in F-0020 (TPR and false-alarm ceilings for conditions); other areas await a tolerance run.
- Six directions, probe sets, atomic sentences, bars and gates: the skill's section 7 (country look-alike set, story-type weight class, conditions keys) are filled-in rows of the section 5 table.
- Provisional: all bars in the Criteria review (Fable) are provisional until the measurements in its section 4 run. Bars move only with the owner's approval.

## 9. Sources (opened and read this session unless marked)
- Grochtmann, Grimm. Classification trees for partition testing. Software Testing, Verification and Reliability 3(2):63-82, 1993. DOI 10.1002/stvr.4370030203; Crossref record https://api.crossref.org/works/10.1002/STVR.4370030203 (abstract only; full text not opened).
- ISTQB. Certified Tester Foundation Level Syllabus v4.0.1 (2024-09-15), sections 4.2.1, 4.2.2, 5.2. https://istqb.org/wp-content/uploads/2024/11/ISTQB_CTFL_Syllabus_v4.0.1.pdf
- Kuhn, Kacker, Lei. Practical Combinatorial Testing. NIST SP 800-142, 2010. https://nvlpubs.nist.gov/nistpubs/legacy/sp/nistspecialpublication800-142.pdf ; NIST ACTS project page https://csrc.nist.gov/projects/automated-combinatorial-testing-for-software
- Opened earlier and recorded in the skill and the 2020-10-20 note: Ribeiro et al. 2020 (https://arxiv.org/abs/2005.04118); Breck et al. 2017 (https://research.google/pubs/pub46555/); Chen et al. 2019 (https://arxiv.org/abs/1909.06349); Krippendorff 2011 (URL in the skill); Gardner et al. 2020 (https://arxiv.org/abs/2004.02709); Kaushik et al. 2020 (https://arxiv.org/abs/1909.12434); Kiela et al. 2021 (https://arxiv.org/abs/2104.14337); Gebru 2021 and Mitchell 2019 (abstracts only).
- Not verified, not cited as fact: ISO/IEC/IEEE 29119 (Wikipedia page 404; ISTQB glossary pages returned no text); the ISTQB glossary wording; Krippendorff 2004; the NASA 67/93/98 percent fault figures (a secondary source's claim, not found in the text I searched); the claim that classification-tree construction is informal.
- Our own, no external source: the six-direction coverage rule, the risk-score cut (6 and 9 tested), the nothing-reader test, the mini-example numbers.
