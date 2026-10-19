# Evaluating the CPU news classifier: standard practice and what it means for our numbers (2026-10-18)

Scope: the CPU student that labels news stories with 44 yes/no "atoms" for the World engine, taught by a local LLM (Clef). Today it is
scored only against the teacher's labels on 486 held-out stories. On that test the smallest difference we can resolve is about 0.03 macro
average precision (AP: the area under the precision-recall curve, averaged over atoms) and about 0.065 recall at a fixed false-positive count
(R@9), both computed as 1.96 x the bootstrap standard deviation of the difference (`newsreader/bitmob/power_check.py`, `docs/proof-standard.md`).

Every outside claim has a link. Statements marked **(our reading)** are my own inference, not a cited finding. All arithmetic is in the
"Worked numbers" section and can be re-run with the formulas given.

## The short version

1. Set the acceptance bar on the engine, not on agreement with the teacher: decide how far a World engine condition may drift, then find the
   classifier error rates that stay inside that limit by injecting errors into replayed stories.
2. Build a small human "gold" set designed for estimation: all teacher positives for the atoms that matter (for precision), plus a sample of
   teacher negatives weighted by student score (for recall), with recorded sampling probabilities so the estimates can be reweighted.
3. Our "smallest detectable difference" (1.96 SD) gives only **50% power**. At the usual 80% power, detecting 0.03 macro AP needs about 990
   stories at today's positive rates, not 486; and a noisy reference makes this worse.
4. Use paired tests (paired bootstrap over stories, McNemar at a fixed threshold), fix the comparisons in advance, and correct for many atoms.
5. Before tuning the student further, measure the teacher on the gold set. If student and teacher are about equally far from gold, or human
   judges side with the student on many disagreements, the teacher is the bottleneck.

---

## 1. A downstream (task-level) acceptance target

### Why label agreement is not enough
- Plugging model labels straight into a downstream analysis can bias it badly even when labels are 80-90% accurate: Egami et al. show that
  "direct use of surrogate labels in downstream statistical analyses leads to substantial bias and invalid confidence intervals"
  ([Egami, Hinck, Stewart, Wei, NeurIPS 2023](https://proceedings.neurips.cc/paper_files/paper/2023/hash/d862f7f5445255090de13b825b880d59-Abstract.html),
  [arXiv 2306.04746](https://arxiv.org/abs/2306.04746)). The World engine is exactly such a downstream analysis: atoms move conditions.
- Coupling between a model and the systems that consume its output is a recognised source of hidden cost: Sculley et al. name "undeclared
  consumers" and "correction cascades", where improving one component can make the whole system worse
  ([Hidden Technical Debt in ML Systems, NeurIPS 2015](https://proceedings.neurips.cc/paper/2015/file/86df7dcfd896fcaf2674f757a2463eba-Paper.pdf)).
  A student that agrees better with the teacher is not automatically a better input to the engine.

### Methods
**1a. Decision-weighted scoring (decision curve analysis).** Medicine's standard for "is this predictor good enough to act on" scores a model
by its *net benefit* at the threshold where acting is worthwhile: net benefit = sensitivity x prevalence - (1 - specificity) x (1 - prevalence)
x w, where w is the odds at the threshold, i.e. how many false alarms one true hit is worth
([Vickers & Elkin 2006, Medical Decision Making](https://pmc.ncbi.nlm.nih.gov/articles/PMC2577036); Python package
[`dcurves`](https://pypi.org/project/dcurves/), `dca(data=..., outcome=..., modelnames=..., thresholds=...)`).
*Apply:* for each atom, the engine owner states the exchange rate w ("one missed real price shock costs as much as N false ones"). That turns
the acceptance bar into a number per atom instead of "as close to Clef as possible". **(our reading)**

**1b. Error injection (sensitivity / tolerance analysis).** Replay a fixed stream of stories through the engine twice: once with reference
labels, once with labels perturbed at a given false-positive and false-negative rate (randomly, and also with the student's actual error
pattern). Measure the change in what the engine produces (condition values, people's states, decision flips). Increase the error rates until
the change exceeds a tolerance the engine owner set in advance. The largest tolerable rates are the per-atom acceptance target. This is the
standard way to propagate measurement error when no closed form exists **(our reading; the need for it follows from Egami et al. above)**.
It also ranks atoms: atoms the engine barely reacts to need no gold labels at all.

**1c. When the engine uses counts or rates, correct the count, not each label.** If a condition depends on "how many stories this week
mention X", the relevant error is in the *prevalence*, and it can be corrected with the classifier's measured true- and false-positive rates
("adjusted classify and count"); plain counting of predictions is known to be biased, especially under distribution shift
([QuaPy, BSD-3, `qp.method.aggregative.ACC`](https://github.com/HLT-ISTI/QuaPy)). The true- and false-positive rates must come from a trusted
reference, which is one more reason for section 2.

**1d. Valid downstream estimates from many model labels plus few gold labels.** Two families give valid confidence intervals on a downstream
quantity (a mean, a rate, a regression coefficient) using a large set of model labels and a small gold set:
- Prediction-powered inference, PPI and PPI++ ([`ppi_py`](https://github.com/aangelopoulos/ppi_py),
  [docs and API, e.g. `ppi_mean_ci`](https://ppi-py.readthedocs.io/en/stable/ppi.html);
  [PPI++ paper](https://arxiv.org/abs/2311.01453)). Precision, recall and prevalence are all means, so they fit directly.
- Design-based supervised learning, DSL: stays valid "even when surrogates are arbitrarily biased" provided the gold items are drawn with known
  probabilities ([Egami et al. 2023](https://arxiv.org/abs/2306.04746); a Python port of the authors' R package:
  [`dsl_kit`](https://pypi.org/project/dsl-kit/)).

*Apply:* the acceptance test becomes "the engine's condition X, computed from student labels and corrected with the gold set, has a 95%
interval within the tolerance from 1b". This is a statement about the engine, not about agreement with Clef.

## 2. A small trusted gold (reference) set

### Guidelines and documentation
- Write one page per atom: definition, what counts, what does not, and 3-5 borderline examples with the decision. Record who labelled, how,
  and when, in the Hugging Face dataset-card layout, whose "Annotations" section has "Annotation process" and "Who are the annotators?"
  ([HF dataset card guide](https://huggingface.co/docs/hub/datasets-cards); template from
  [`huggingface_hub` datasetcard_template.md](https://github.com/huggingface/huggingface_hub/blob/main/src/huggingface_hub/templates/datasetcard_template.md)).
- Label blind: the annotator does not see the teacher's or the student's answer, so neither anchors the label **(our reading; standard
  practice, and required for 4b to mean anything)**.

### Tools (all can run locally; nothing needs to leave the machine)
| Tool | Agreement metrics | Notes |
|---|---|---|
| [Argilla](https://docs.argilla.io/en/latest/reference/python/python_annotation_metrics.html) | Krippendorff's alpha only (`compute_agreement_metrics("alpha", question_name=...)`, NLTK implementation) ([tutorial](https://docs.argilla.io/en/latest/tutorials_and_integrations/tutorials/feedback/end2end_examples/use-metrics-007.html)) | Rule of thumb in its docs: alpha >= 0.8 reliable, >= 0.667 tentative conclusions only |
| [Label Studio](https://docs.humansignal.com/guide/stats) | Per-task agreement, annotator-vs-annotator matrix, agreement with ground truth | The Community Edition "does not perform these statistical calculations"; agreement stats are Enterprise only |
| [doccano](https://github.com/doccano/doccano) | none built in | Multi-label text classification, JSON/CSV import and export, collaborative |
| [`krippendorff`](https://pypi.org/project/krippendorff/) (PyPI) | `krippendorff.alpha(reliability_data=...)` | Any number of annotators, missing values allowed |
| [scikit-learn `cohen_kappa_score`](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.cohen_kappa_score.html) | Cohen's kappa | Exactly two annotators |

Cohen's kappa is defined for two raters; Krippendorff's alpha handles any number of raters and incomplete data
([HumanSignal on Krippendorff's alpha](https://labelstud.io/videos/in-the-loop-krippendorff-s-alpha),
[on Cohen and Fleiss kappa](https://labelstud.io/videos/in-the-loop-cohen-and-fleiss-kappas)). For rare atoms, report raw positive agreement
alongside kappa/alpha: chance-corrected scores are unstable when almost every item is "no" **(our reading)**.

### Single-annotator risk
Today the only non-Clef reference is the user's hand check (R3 in `docs/proof-standard.md`). One annotator's systematic misreadings become
the "truth". Minimum mitigations **(our reading)**: (a) a second person labels an overlap of at least 20-30% of the gold items, and alpha/kappa
is reported per atom; (b) failing that, the same person re-labels a random 10-20% after a gap of a week or more, without seeing their first
answer (intra-rater agreement); (c) every disagreement is adjudicated against the written guideline and the guideline is updated.
Agreement between humans sets the ceiling on what any model can be shown to achieve: the GLUE human baseline used five crowd labels per item
on 500 test items and a majority vote ([Nangia & Bowman, ACL 2019](https://aclanthology.org/P19-1449/),
[slides](https://cims.nyu.edu/~sbowman/StarSEM2019.pdf)). When annotators genuinely disagree, scoring against one aggregated label misstates
performance ([Gordon et al., "The Disagreement Deconvolution", CHI 2021](https://hci.stanford.edu/publications/paper.php?id=404)).

### How to sample: stratify, record probabilities, reweight
Random sampling is hopeless for atoms at a 2% base rate (see worked numbers). The standard answer is to sample *on purpose* and correct for it:
- Draw items with known, unequal probabilities (oversample where errors are likely), then weight each item by 1/probability. DSL's validity
  rests on exactly this ([Egami et al.](https://arxiv.org/abs/2306.04746)).
- Choosing which test items to label to minimise estimation error is "active testing" ([Kossen et al., ICML 2021](https://proceedings.mlr.press/v139/kossen21a.html));
  for F-measures (precision/recall), Sawade et al. derive the variance-optimal sampling distribution
  ([Active Estimation of F-Measures, NIPS 2010](https://papers.nips.cc/paper/3999-active-estimation-of-f-measures)).
- Weighted metrics are supported directly: `sklearn.metrics.average_precision_score(y, s, sample_weight=w)`
  ([docs](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html)), which `power_check.py` already
  uses for bootstrap weights.

*Proposed design for us **(our reading)***, per atom chosen in 1b:
- **Precision stratum:** every story the teacher (or any candidate student) calls "yes". Sampling probability 1, so precision needs no weights.
- **Recall stratum:** teacher "no" stories split into bands by the best student's score; label all of the top band (where misses concentrate)
  and a small random share of the rest; weight by 1/share.
- One story is read once for all relevant atoms, so the per-story cost is shared.

### Sample size: formulas and tools
- Interval half-width h for a proportion p: n = z^2 p(1-p) / h^2; this is `statsmodels.stats.proportion.samplesize_confint_proportion(proportion,
  half_length, alpha=0.05)` ([statsmodels source](https://www.statsmodels.org/stable/_modules/statsmodels/stats/proportion.html)). For the
  final interval use `proportion_confint(count, nobs, method="wilson")` (or `"beta"` for Clopper-Pearson), not the default `"normal"`, which
  is poor at small n.
- Interval for AP: Boyd, Eng & Page compare AUCPR estimators and intervals, find some procedures invalid, and recommend two simple intervals
  ([ECML PKDD 2013](https://link.springer.com/10.1007/978-3-642-40994-3_29), [project page](https://pages.cs.wisc.edu/~boyd/projects/2013ecml_aucprestimation),
  [R code `raucpr`](https://github.com/kboyd/raucpr); MedCalc's [precision-recall sample-size calculator](https://www.medcalc.org/manual/sample-size-CI-precisionrecall.php)
  uses their logit method).
- Power for comparing two classifiers: see section 3; McNemar sample size by Connor's (1987) formula, as implemented in SAS
  `PROC POWER ... TEST=MCNEMAR METHOD=CONNOR` ([SAS docs](https://support.sas.com/documentation/cdl/en/statug/63962/HTML/default/statug_power_sect009.htm),
  [formula write-up](https://metricgate.com/docs/sample-size-mcnemar-paired)).
- For anything else (macro AP, R@9, kappa), simulate: Card et al. release notebooks for exactly this
  ([With Little Power Comes Great Responsibility, EMNLP 2020](https://aclanthology.org/2020.emnlp-main.745)).

## 3. Comparing classifiers fairly on small test sets

- **Power is usually the problem.** Card et al. find underpowered comparisons common in NLP; small GLUE test sets leave most state-of-the-art
  comparisons underpowered, and a 2,000-sentence MT test set has about 75% power for a 1 BLEU difference
  ([Card et al. 2020](https://arxiv.org/abs/2010.06595)).
- **Pick the test by protocol.** Dror et al. give a selection protocol and find significance testing often skipped or misused in ACL/TACL
  2017 papers ([Hitchhiker's Guide, ACL 2018](https://aclanthology.org/P18-1128/)).
- **Paired bootstrap** over stories (resample stories, recompute both systems' metric on the same resample, look at the difference): works for
  any metric, including macro AP and R@9 ([Berg-Kirkpatrick, Burkett & Klein, EMNLP 2012](https://aclanthology.org/D12-1091/)).
  `scipy.stats.bootstrap(..., paired=True)` resamples the same indices across both samples; default interval is BCa
  ([scipy source](https://github.com/scipy/scipy/blob/main/scipy/stats/_resampling.py)). Hugging Face `evaluate`'s evaluator has
  `strategy="bootstrap"` (`confidence_level=0.95`, `n_resamples=9999`, scipy underneath), but that gives a per-model interval, not the
  paired difference ([evaluator docs](https://huggingface.co/docs/evaluate/v0.4.0/en/package_reference/evaluator_classes)).
- **McNemar** at a fixed threshold, per atom (counts only items where the two classifiers disagree): Dietterich found it the only test with
  acceptable false-alarm rate when each system is trained once
  ([Neural Computation 1998](https://web.engr.oregonstate.edu/~tgd/publications/dietterich-approximate-statistical-tests-nc1998.pdf)).
  API: `statsmodels.stats.contingency_tables.mcnemar(table, exact=True)`
  ([source](https://www.statsmodels.org/stable/_modules/statsmodels/stats/contingency_tables.html)); also
  [HF `evaluate` comparison "mcnemar"](https://github.com/huggingface/evaluate/tree/main/comparisons/mcnemar)
  ([types of evaluations](https://huggingface.co/docs/evaluate/main/en/types_of_evaluations)).
- **Many atoms, many comparisons.** For the few headline comparisons use Holm (family-wise); for per-atom claims across 44 atoms use
  Benjamini-Hochberg (false discovery rate): `statsmodels.stats.multitest.multipletests(pvals, method="holm" | "fdr_bh")`
  ([source](https://www.statsmodels.org/stable/_modules/statsmodels/stats/multitest.html)).
- **Pre-registration.** Write the claim, data split, metric, operating point, test and pass bar before running
  ([van Miltenburg, van der Lee & Krahmer, "Preregistering NLP Research", NAACL 2021](https://arxiv.org/abs/2103.06944)). Our
  `docs/proof-standard.md` item 2 already requires this; add "the power calculation" to the pre-registered items.
- **Label errors in the test set change rankings.** Northcutt et al. estimate about 3.3% label errors across 10 benchmark test sets (6% of
  ImageNet validation) and show that on corrected labels a smaller model can overtake a larger one
  ([NeurIPS 2021 D&B](https://arxiv.org/abs/2103.14749), [code](https://github.com/cleanlab/label-errors)). With an LLM teacher as the test
  reference, our error rate is very likely higher than that **(our reading)**.

## 4. Is the teacher (reference) the bottleneck, or the student?

All of these need the gold set from section 2.
1. **Three-way comparison on gold.** Report teacher-vs-gold, student-vs-gold and student-vs-teacher at the same operating point, with
   intervals. If student-vs-gold is about equal to teacher-vs-gold, the student has learned what the teacher can teach; further gains need a
   better teacher or better labels **(our reading)**.
2. **Adjudicate the disagreements.** Sample stories where student and teacher disagree and have a blind human decide. A large share decided in
   the student's favour means the teacher-only test is penalising correct answers. This is the Northcutt et al. procedure (flag likely errors,
   then human validation; 51-54% of flagged items were confirmed errors) ([arXiv 2103.14749](https://arxiv.org/abs/2103.14749)). To find
   likely teacher errors, use `cleanlab.filter.find_label_issues` with the student's *out-of-fold* probabilities (the docs warn in-sample
   probabilities are unsuitable) ([cleanlab docs](https://docs.cleanlab.ai/v2.6.1/_modules/cleanlab/filter.html),
   [tabular tutorial](https://docs.cleanlab.ai/v2.2.0/tutorials/tabular.html)).
3. **Teacher test-retest.** Re-ask the teacher the same atom with a second fixed wording (or seed). Its agreement with itself caps the agreement
   any student can show with it, the way human agreement caps benchmark scores ([Nangia & Bowman 2019](https://aclanthology.org/P19-1449/))
   **(our reading)**.
4. **Learning curve vs noise floor.** If more teacher labels stop helping (our A5 curve) while the teacher's own error on gold is still large,
   the reference is the limit, not the student's capacity **(our reading)**.
5. **Attenuation.** Reference noise shrinks measured differences between students, so it raises the sample size needed to see a real
   difference (section "Worked numbers") **(our reading)**.

---

## Worked numbers (our data)

All at 95% confidence (z = 1.96) unless noted; 80% power uses z = 0.84. Normal-approximation formulas from the statsmodels source above;
Wilson intervals computed with the standard formula.

### A. Teacher precision on an atom at a ~2% base rate, to +/- 0.1
Precision = share of teacher "yes" stories that gold says are "yes". n = number of *teacher-positive* stories judged.
| assumed precision | n for +/- 0.10 (95%) | n for +/- 0.10 (90%) |
|---|---|---|
| 0.5 (worst case) | 97 | 68 |
| 0.7 | 81 | 57 |
| 0.9 | 35 | 25 |

- At 2% of 2,300 stories the teacher flags about 46 stories, so the whole corpus does not hold enough positives for +/- 0.1 at 95% on one atom.
  Judging all 46 (a census, about 46 readings) gives roughly +/- 0.13 (Wilson 0.55-0.81 if 32 of 46 are correct).
- Smaller atoms: 20 positives give about +/- 0.19, 10 give +/- 0.25, 5 give +/- 0.29. Atoms with 5-20 positives cannot have their precision
  pinned down individually; pool them by family or accept wide intervals.
- Random sampling instead of targeting teacher positives would need about 97 / 0.02 = 4,850 stories read to collect 97 teacher positives.
- Recall is harder: if 0.5% of the ~2,254 teacher "no" stories are real positives (about 11 missed stories), a uniform sample of 200
  negatives estimates the missed count with a standard deviation of about 11, i.e. useless. Hence the score-banded recall stratum in section 2.

### B. Detecting a 0.03 difference in macro AP (and 0.065 in R@9)
`power_check.py` reports the smallest detectable difference as 1.96 x SD(difference). A true difference of exactly that size is detected only
half the time (50% power). For 80% power the difference must be (1.96 + 0.84) x SD. With SD = 0.03 / 1.96 = 0.0153 at 486 stories and SD
shrinking as 1/sqrt(n) (assumes the same atom mix and positive rates, and teacher labels as reference):
| target | alpha 0.05 | alpha 0.01 (e.g. Bonferroni over 5 comparisons) |
|---|---|---|
| macro AP 0.03 at 80% power | about 990 stories | about 1,480 |
| macro AP 0.02 at 80% power | about 2,240 | about 3,330 |
| R@9 0.065 at 80% power | about 990 | about 1,480 |
| R@9 0.03 at 80% power | about 4,660 | about 6,940 |

Caveats: AP's variance is driven by the number of *positives* per atom, not stories, so a test set enriched for positives (section 2
sampling, with weights) needs fewer stories than these numbers; against a noisy reference the true difference is attenuated and more stories
are needed. A simulation (resample from our own score files, inject a known difference, count detections) is the reliable check, as Card et al.
recommend.

### C. McNemar per atom at a fixed threshold (Connor's formula, 80% power, alpha 0.05)
| share of stories where the two classifiers disagree | true difference in error rate | stories needed |
|---|---|---|
| 10% | 0.03 | about 870 |
| 6% | 0.03 | about 520 |
| 10% | 0.02 | about 1,960 |

### D. What this implies (our reading)
- Stop comparing student variants on the 486 teacher-labelled stories for differences under ~0.04 macro AP; the test cannot see them at
  useful power.
- Spend the next labelling effort on (1) the error-injection run (1b) to learn which atoms matter and by how much, then (2) a gold set for those
  atoms: precision census of teacher positives plus a score-banded recall stratum, with a second rater or a blind re-label on 20-30%.
- Re-state acceptance as "engine condition within tolerance, with a 95% interval, using PPI/DSL on student labels plus gold", and pre-register it.
