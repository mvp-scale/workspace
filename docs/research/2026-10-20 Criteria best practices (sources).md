# Criteria best practices: primary sources read

Date 2026-10-20. Research notes behind `.claude/skills/acceptance-criteria/SKILL.md`. No code, bar or ledger item was changed. Quotes are short and verbatim from the text I opened (PDF text extracted with pypdf, or the page fetched). Where I could not open the full text, it says so.

## Verified (opened and read)

### 1. CheckList (behavioural tests)
- Ribeiro, Wu, Guestrin, Singh. "Beyond Accuracy: Behavioral Testing of NLP models with CheckList." ACL 2020. https://arxiv.org/abs/2005.04118 ; PDF https://aclanthology.org/2020.acl-main.442.pdf (read section 2.3).
- "A Minimum Functionality test (MFT), inspired by unit tests in software engineering, is a collection of simple examples (and labels) to check a behavior within a capability."
- "An Invariance test (INV) is when we apply label-preserving perturbations to inputs and expect the model prediction to remain the same."
- "A Directional Expectation test (DIR) is similar, except that the label is expected to change in a certain way."
- "INVs and DIRs allow us to test models on unlabeled data".
- Abstract: held-out accuracy "often overestimates" performance (paraphrase of the abstract on the arXiv page).
- Use for us: probe sets per behaviour (MFT), edits that must not flip (INV: outlet name, typos, a country swapped for a same-class country), edits that must flip (DIR: "raises" vs "will raise"). INV and DIR need no human labels, so they can be large.

### 2. ML Test Score (Google)
- Breck, Cai, Nielsen, Salib, Sculley. "The ML Test Score: A Rubric for ML Production Readiness and Technical Debt Reduction." IEEE Big Data 2017. https://research.google/pubs/pub46555/ ; PDF https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/aad9f93b86b7addfea4c419b9100c6cdd26cacea.pdf
- "Model 6: Model quality is sufficient on all important data slices".
- "Examining sliced data avoids having fine-grained quality issues masked by a global summary metric, e.g. global accuracy improved by 1% but accuracy for one country dropped by 50%."
- "release tests for models can impose absolute thresholds (e.g., error for slice x must be <5%) ... as well as incremental (e.g. the change in error for slice x must be<1% compared to the previously released model)."
- "Model 5: A simpler model is not better: Regularly testing against a very simple baseline model".
- "models should have zero bias, in aggregate and on slices (e.g. 90% of predictions of probability 0.9 should in fact be positive)" (calibration by slice).
- Scoring: "The final ML Test Score is computed by taking the minimum of the scores aggregated for each of the 4 sections." (a system must be good in every section; no averaging away).
- Not used: the TrueFoundry blog's score bands are not from the paper.
- Use for us: per-slice absolute floor plus a no-regression delta; a simple baseline as the lower anchor; the grade is a minimum over areas, not an average.

### 3. Slice-based learning
- Chen, Sala, Hooper, Fu, Ratner, Re, et al. "Slice-based Learning: A Programming Model for Residual Learning in Critical Data Slices." NeurIPS 2019. https://arxiv.org/abs/1909.06349 (PDF read; first-author list differs between NeurIPS and arXiv pages, so cite as "Chen et al.").
- "they may underperform on critical subsets" despite good overall accuracy; "we introduce the notion of slices: application-critical data subsets".
- Use for us: a slice is defined by what matters downstream (an outlet, a region, a look-alike group), not by what is easy to mine.

### 4. Model Cards
- Mitchell, Wu, Zaldivar, Barnes, Vasserman, Hutchinson, Spitzer, Raji, Gebru. "Model Cards for Model Reporting." FAT* 2019. https://arxiv.org/abs/1810.03993 (abstract page read; full text not opened).
- Abstract proposes reporting performance "across different cultural, demographic, or phenotypic groups" and "intersectional groups".
- Use for us: report every metric per group and per intersection (outlet x region), with the intended use stated. Weak support only for numbers; it is a reporting rule.

### 5. Datasheets for Datasets
- Gebru, Morgenstern, Vecchione, Vaughan, Wallach, Daume III, Crawford. "Datasheets for Datasets." CACM Dec 2021. https://arxiv.org/abs/1803.09010 (abstract page read; full text not opened).
- A datasheet documents a dataset's "motivation, composition, collection process, and recommended uses".
- Use for us: DATA-level rows: who labelled, how the sample was drawn, what is in and out, recommended use. A criterion set must name its probe set in those terms.

### 6. Inter-annotator reliability and sample size (Krippendorff)
- Krippendorff, K. "Agreement and Information in the Reliability of Coding." Communication Methods and Measures 5(2), 2011 (revised version on ScholarlyCommons). https://repository.upenn.edu/server/api/core/bitstreams/86b17550-83f8-422c-9ff0-628df92e1120/content (read).
- "the only remedy of this inadequacy is to increase the sample size of the reliability data, units, coders or both."
- "reliability data should be representative of the population of units to be coded ... obtained as a probability sample" and "sampling not to a minimum number of units, but until the least frequent kind is informationally adequate."
- Table 1 gives the number of values needed for a "Smallest acceptable alpha_min" of .667, .800 or .900 at p = .05. For a binary variable with P(value) = .5 and alpha_min .800: 103 values; at .667: 60. For a value with P = .05: 560 (at .800), 329 (at .667).
- NOT verified in primary text: the exact phrase "0.800 reliable / 0.667 tentative" belongs to Krippendorff's 2004 book "Content Analysis" (p. 241), which I could not open; I only saw secondary citations (an ESG-ratings paper in Review of Finance cites p. 204). The skill therefore says "0.8 / 0.667 are the conventional cut-offs, here confirmed only as the alpha_min values in Table 1 of the 2011 paper".
- Use for us: the 50-item codebook pilot (skill ontology-trainer 1b) is too small for rare labels; size the agreement set by the rarest label's frequency.

### 7. Gherkin (Given-When-Then)
- Cucumber. "Gherkin Reference." https://cucumber.io/docs/gherkin/reference (read).
- "`Given` steps are used to describe the initial context of the system - the scene of the scenario."
- "`When` steps are used to describe an event, or an action."
- "`Then` steps are used to describe an expected outcome, or result."
- "We recommend 3-5 steps per example".
- Use for us: a criterion sentence has the same three parts: context (probe set), action (reader reads), expected outcome (measure and bar). One scenario, one outcome.

## Dropped (could not open and verify)
- Brown, Cai, DasGupta, "Interval Estimation for a Binomial Proportion", Statistical Science 16(2), 2001 (https://doi.org/10.1214/SS/1009213286): the Project Euclid PDF and page returned empty or blocked; I saw only search snippets (they recommend the Wilson interval over the Wald). Not cited as verified. The skill gives the Wilson formula as standard statistics, uncited; confirm against the paper if a citation is needed.
- Krippendorff 2004 HCR article and 2004 book (thresholds): blocked (403 / SPA page). See item 6.
- Cucumber mirror pages from search: not used; only the official page above.

## From the Haiku notes (added after they appeared)
- Circling note: I re-opened the arXiv abstract pages for Gardner et al. 2020 (contrast sets, 2004.02709), Kaushik, Hovy, Lipton 2020 (counterfactually augmented data, 1909.12434) and Kiela et al. 2021 (Dynabench, 2104.14337); all three match. Abstract-level only. Their other rows (ANLI, reject-option leads) I did not re-open and did not cite.
- Practitioner note: its own summary says none of 13 vendor-doc sources publishes a numeric acceptance threshold. Not cited in the skill; not re-checked.
- The "circling" method (left/right, up/down, sideways) is the owner's; the sources above support the sideways and slice rings only. No verified source found for source-stage checks or for the none/abstain case.
