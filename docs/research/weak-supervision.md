# Weak supervision for the CPU news-story reader: tools, evidence, fit

Researched 2026-10-18. Read-only: public sources only, nothing installed or run, no project data sent anywhere. Every claim has a link. "Not found" means I looked and found nothing, not that it does not exist.

## Our problem in one paragraph

A local LLM (the "teacher") answers yes/no questions ("atoms") about news stories. Each atom is asked in 2-3 wordings. We have about 2,300 stories, 44 atoms and 5-100 positives per atom, and no human ground truth. We want to:

- **(a)** estimate how accurate each noisy labelling source is without ground truth;
- **(b)** combine several noisy sources (teacher wordings, keyword/regex patterns, embedding-similarity heads) into cleaner training labels;
- **(c)** find individual labels that are probably wrong.

Terms used below:

- **Labelling function (LF)**: any source that votes yes, no or abstain on an item.
- **Label model**: a statistical model that learns how accurate each LF is from how the LFs agree and disagree, then outputs a probability per item.
- **Conditional independence**: the assumption that, once the true answer is known, the LFs' errors are unrelated. Our wordings of the same LLM break this assumption.

## Summary table

| Tool | Solves | CPU / deps | Correlated sources | Last release / activity | Licence |
|---|---|---|---|---|---|
| Snorkel `LabelModel` | a, b | CPU fine; needs torch, Py ≥3.11 | Assumes independence; no dependency input | v0.10.0, 2024-02-27; README says the team moved to the commercial Snorkel Flow | Apache-2.0 |
| skweak `NaiveBayes` / `MultilabelNaiveBayes` | a, b | spaCy 3 + hmmlearn | Down-weights sources whose *names* match (`redundancy_factor`) | 0.3.3, 2023-09; README: "no longer actively maintained" | MIT |
| cleanlab (`find_label_issues`, multilabel, CROWDLAB) | c, a, b | numpy/sklearn/pandas only | Not modelled | v2.9.0, 2026-01-13 | Apache-2.0 |
| FlyingSquid | a, b | light, closed-form | Explicit `lambda_edges` dependency input | last commit 2020-09 | Apache-2.0 |
| Wrench | benchmark + 15 label models | pins torch<2, numpy≤1.22.3, faiss-gpu | `dependency_structure.py` (structure learning) | v1.1 2021-11; last commit 2024-02 | Apache-2.0 |
| crowd-kit (Dawid-Skene, GLAD, MACE…) | a, b | pandas, CPU | Assumes independence | 1.4.2, 2025-10-13 | Apache-2.0 |
| Alfred (prompted WS) | b (prompts as LFs) | torch; aimed at GPU/API models | Not modelled | last commit 2025-04 | BSD-3-Clause |
| Embroid / Smoothie / LLM structure learning | b, a | research code | Embroid and the structure work address it | 2023-2024 research repos | mixed / none |

Sources for the table: GitHub API metadata pulled 2026-10-18 for [snorkel](https://github.com/snorkel-team/snorkel), [skweak](https://github.com/NorskRegnesentral/skweak), [cleanlab](https://github.com/cleanlab/cleanlab), [flyingsquid](https://github.com/HazyResearch/flyingsquid), [wrench](https://github.com/JieyuZ2/wrench), [crowd-kit](https://github.com/Toloka/crowd-kit) and [alfred](https://github.com/BatsResearch/alfred), plus PyPI pages for [snorkel](https://pypi.org/project/snorkel/), [skweak](https://pypi.org/project/skweak/), [cleanlab](https://pypi.org/project/cleanlab/) and [crowd-kit](https://pypi.org/project/crowd-kit/). Each tool's section gives its specifics.

---

## 1. Snorkel: data programming with `LabelModel`

**What it does.** You write LFs that vote or abstain. `LabelModel` learns each LF's accuracy from its agreements and conflicts with the other LFs, with no labels needed, and outputs a probabilistic label per item. You train your end classifier on those probabilities ([Snorkel paper, VLDB 2017](https://arxiv.org/abs/1711.10160)). It covers **(b)**, and **(a)** through the learned weights. `LFAnalysis` gives agreement statistics that need no labels.

**API** ([LabelModel docs](https://snorkel.readthedocs.io/en/master/packages/_autosummary/labeling/snorkel.labeling.model.label_model.LabelModel.html)). Snorkel is not indexed in Context7, so these come from the official docs.

- `LabelModel(cardinality=2)`
- `.fit(L_train, Y_dev=None, class_balance=None, n_epochs=100, lr=0.01, l2=0.0, optimizer="sgd", prec_init=0.7, seed=…)`. `L_train` is an n×m int matrix with −1 = abstain.
- `.predict_proba(L)` returns an n×k array. `.predict(L, tie_break_policy="abstain")` returns hard labels.
- `.get_weights()` returns per-LF accuracy estimates, which is (a).
- `.get_conditional_probs()` returns an m×(k+1)×k array of P(LF output | true class), with abstain included.
- `.score(L, Y, metrics=[…])` needs gold labels.
- `LFAnalysis(L).lf_summary()`, `.lf_coverages()`, `.lf_overlaps()`, `.lf_conflicts()` need no labels. `.lf_empirical_accuracies(Y)` needs gold ([LFAnalysis docs](https://snorkel.readthedocs.io/en/master/packages/_autosummary/labeling/snorkel.labeling.LFAnalysis.html)).

**Evidence.**

- Snorkel paper: an average 132% improvement over prior heuristic approaches, and within an average 3.60% of large hand-curated training sets ([arXiv:1711.10160](https://arxiv.org/abs/1711.10160)).
- Multi-task version (MeTaL): +6.8 points over majority vote and +4.1 over a prior WS method that models tasks separately, on three fine-grained problems ([arXiv:1810.02840](https://arxiv.org/abs/1810.02840)).
- The independent benchmark Wrench found that "MeTaL and MV [majority vote] are the best label models" overall and that no label model consistently wins ([Wrench paper](https://ar5iv.labs.arxiv.org/html/2109.11377)). The "Wrench" section below has the details.

**Maintenance.** The last release is v0.10.0 (2024-02-27, Apache-2.0). The README says the team is "now focusing their efforts on Snorkel Flow", their commercial platform ([README](https://github.com/snorkel-team/snorkel)). The library still installs and works, but expect no new features. It requires Python ≥3.11 and torch ([PyPI](https://pypi.org/project/snorkel/)).

**Fit to our case.**

- CPU and small data are fine: the model is a small matrix-factorisation fit.
- It is binary per atom, so we would run 44 separate models.
- Correlated labellers are the main problem. The docs say the class "uses a conditionally independent label model, in which the LFs are assumed to be conditionally independent given Y" ([docs](https://snorkel.readthedocs.io/en/master/packages/_autosummary/labeling/snorkel.labeling.model.label_model.LabelModel.html)). So three wordings of one LLM are counted as three independent witnesses.
- The authors' own structure-learning work says "the generative model's dependency structure directly affects the quality of the estimated labels" ([Bach et al. 2017](https://arxiv.org/abs/1703.00854)). Modelling dependencies gave up to +4.64 F1 over independent models ([Varma et al. 2019](https://arxiv.org/abs/1903.05844)).
- Neither the structure-learning code nor MeTaL's multi-task graph is in Snorkel 0.10. A form of it survives in Wrench's `dependency_structure.py` ([code](https://github.com/JieyuZ2/wrench/tree/main/wrench/labelmodel)).

**Pitfalls.**

- Correlated LFs inflate confidence. Collapse the wordings first (see the recommendation).
- With 5 positives in 2,300 stories, the class balance is unidentifiable from votes alone. Pass `class_balance` explicitly.
- If the loss turns NaN, `fit` raises an exception ([docs](https://snorkel.readthedocs.io/en/master/packages/_autosummary/labeling/snorkel.labeling.model.label_model.LabelModel.html)).
- Wrench found that soft labels train end models better than hard labels "in most cases" ([Wrench](https://ar5iv.labs.arxiv.org/html/2109.11377)).

## 2. skweak

**What it does.** A spaCy-based weak-supervision toolkit for sequence labelling and text classification. LFs annotate spaCy `Doc`s, and a generative model (HMM for spans, Naive Bayes for documents, fit by EM) aggregates them ([README](https://github.com/NorskRegnesentral/skweak); [ACL 2021 demo paper](https://aclanthology.org/2021.acl-demo.40/)). It covers **(b)** and **(a)**.

**API.**

- `heuristics.FunctionAnnotator`, `TokenConstraintAnnotator` and `gazetteers.GazetteerAnnotator` create LFs.
- `generative.NaiveBayes(name, labels, prior_probs=None, initial_weights=None, redundancy_factor=0.1)` aggregates document labels, and `generative.MultilabelNaiveBayes` handles multi-label.
- `voting.MajorityVoter` and `MultilabelMajorityVoter` are the voting baselines.

All of these are in the source: [generative.py](https://github.com/NorskRegnesentral/skweak/blob/main/skweak/generative.py) and [voting.py](https://github.com/NorskRegnesentral/skweak/blob/main/skweak/voting.py).

**Correlated sources.** skweak is the only one of these tools that down-weights redundant sources out of the box. Each source's weight is multiplied by `exp(-redundancy_factor · Σ recall with correlated sources)`. "Correlated" is decided purely by *name* (`_get_correlated_sources` matches names that are prefixes or suffixes of each other, e.g. `_cased`/`_uncased`) ([source](https://github.com/NorskRegnesentral/skweak/blob/main/skweak/generative.py)). If we named our sources `teacher_atomX_w1`, `teacher_atomX_w2` and so on, they would be grouped. That is a crude but direct fit to our wording problem.

**Evidence.** The paper's abstract reports no numbers. It illustrates the toolkit on NER and sentiment ([ACL Anthology](https://aclanthology.org/2021.acl-demo.40/)). I found no independent benchmark of the redundancy weighting.

**Maintenance.** The README says "no longer actively maintained" ([README](https://github.com/NorskRegnesentral/skweak)). The last PyPI release is 0.3.3 (2023-09), MIT licence ([PyPI](https://pypi.org/project/skweak/)).

**Fit and pitfalls.**

- It forces a spaCy `Doc` pipeline for what is, for us, a plain story×LF vote matrix.
- It is unmaintained.
- The redundancy weight is a fixed heuristic, not estimated.

Its useful contribution is the redundancy idea, which we can reproduce in a few lines.

## 3. cleanlab: confident learning, multi-label issues, CROWDLAB

**What it does.**

- **Confident learning** compares each item's given label with out-of-fold model probabilities. It estimates the joint distribution of noisy and true labels and flags the items most likely mislabelled ([Northcutt et al., JAIR 2021](https://arxiv.org/abs/1911.00068)). This covers **(c)**. The noise matrix it estimates is a form of **(a)** for the label source as a whole.
- The **multi-label** extension handles our 44 non-exclusive atoms ([Thyagarajan et al. 2022](https://arxiv.org/abs/2211.13895)).
- **CROWDLAB** treats each source as an "annotator". It combines the annotators' labels with a classifier's predictions to produce a consensus label, a quality score per item and a quality score per annotator ([Goh, Tkachenko, Mueller 2022](https://arxiv.org/abs/2210.06812)). This covers **(a)**, **(b)** and **(c)** in one call.

**API** (Context7 `/cleanlab/cleanlab` and the official docs):

- `cleanlab.multilabel_classification.filter.find_label_issues(labels, pred_probs, filter_by='prune_by_noise_rate', return_indices_ranked_by=None, frac_noise=1.0, min_examples_per_class=1, …)` ([docs](https://docs.cleanlab.ai/stable/cleanlab/multilabel_classification/filter.html)).
  - `labels` is a list of lists of active atom indices.
  - `pred_probs` is an N×K array of per-atom probabilities that need not sum to 1.
  - It returns a boolean mask, or ranked indices.
- `find_multilabel_issues_per_class(...)` returns one mask per atom, or ranked indices per atom ([same page](https://docs.cleanlab.ai/stable/cleanlab/multilabel_classification/filter.html)).
- `Datalab(dataset, label_name='label', task='multilabel').find_issues(pred_probs=…, features=…)` is the high-level wrapper, with `lab.report()` ([multilabel tutorial](https://github.com/cleanlab/cleanlab/blob/master/docs/source/tutorials/multilabel_classification.ipynb)).
- `cleanlab.multiannotator.get_label_quality_multiannotator(labels_multiannotator, pred_probs, consensus_method=…, quality_method='crowdlab', return_weights=False)` ([docs](https://docs.cleanlab.ai/stable/cleanlab/multiannotator.html)).
  - `labels_multiannotator` is N×M, with NaN where a source abstained.
  - It returns `label_quality`, a per-item frame with `consensus_label`, `annotator_agreement` and `consensus_quality_score`.
  - It also returns `annotator_stats`, a per-source frame with `annotator_quality`, `agreement_with_consensus` and `worst_class`, plus the weights.
  - The docs page is inconsistent about the default `consensus_method`: the signature says `best_quality`, the text says `majority_vote`. Set it explicitly.
- `get_label_quality_multiannotator_ensemble(...)` takes P models' `pred_probs` ([docs](https://docs.cleanlab.ai/stable/cleanlab/multiannotator.html)).
- `get_active_learning_scores(...)` picks which items to send to a human next ([docs](https://docs.cleanlab.ai/stable/cleanlab/multiannotator.html)).
- `cleanlab.count.estimate_py_and_noise_matrices_from_probabilities(labels, pred_probs)` returns the class prior, the noise matrix P(given label | true label), its inverse and the confident joint. It "assumes pred_probs are out-of-sample holdout probabilities" ([count docs](https://docs.cleanlab.ai/stable/cleanlab/count)).

**Evidence.**

- Confident learning: under stated sufficient conditions it "exactly finds label errors". It beat seven competing noisy-label methods on CIFAR and found label errors in MNIST and ImageNet ([arXiv:1911.00068](https://arxiv.org/abs/1911.00068)). The abstract gives no detection precision or recall.
- Multi-label method: reported to outperform other label-error detectors, and found many errors in CelebA. The abstract gives no numbers ([arXiv:2211.13895](https://arxiv.org/abs/2211.13895)).
- CROWDLAB: best overall against Dawid-Skene and GLAD (with or without the model) on CIFAR-10H subsets. An ablation removing per-annotator weights hurt only slightly. All experiments were on images, and evaluation required ground truth ([paper](https://ar5iv.labs.arxiv.org/html/2210.06812)).
- I found no evidence of these methods on LLM-generated labels for text.

**Maintenance.** v2.9.0 (2026-01-13), Apache-2.0, actively maintained. Its dependencies are only numpy, scikit-learn, pandas, tqdm and termcolor (Python ≥3.10) ([PyPI](https://pypi.org/project/cleanlab/)).

**Fit to our case.**

- It fits well on CPU, needs no torch, and works with a few thousand items.
- The multi-label module matches our 44 atoms.
- The "model" it needs can be our e5/embedding logistic head, trained out-of-fold.
- Correlated sources are not modelled. CROWDLAB weights each annotator by agreement with the others, so three near-identical wordings agree with each other and get high weights. It also only supports multiclass (one label per item) for multi-annotator data ([docs](https://docs.cleanlab.ai/stable/cleanlab/multiannotator.html)), so we would run it once per atom as a binary task.

**Pitfalls.**

- `pred_probs` must be out-of-sample (cross-validated), or the model just echoes its training labels ([count docs](https://docs.cleanlab.ai/stable/cleanlab/count)).
- Confident learning assumes class-conditional noise: the error rate depends only on the true class, not on the story ([arXiv:1911.00068](https://arxiv.org/abs/1911.00068)). A teacher that fails on one kind of story breaks this.
- CROWDLAB's own limitations section says overconfident models give overly optimistic quality estimates, and results depend on a well-trained classifier ([paper](https://ar5iv.labs.arxiv.org/html/2210.06812)).
- Atoms with 5 positives give the model almost nothing to learn from, so flags there are weak.

## 4. Wrench (Weak supeRvision bENCHmark)

**What it does.** A benchmark of 22 real datasets for classification and sequence tagging, with more than 120 method variants ([arXiv:2109.11377](https://arxiv.org/abs/2109.11377)). It ships a uniform interface to many label models: MV, weighted MV, Dawid-Skene, Data Programming, MeTaL, FlyingSquid, EBCC, IBCC, Fable, HyperLM, and a `dependency_structure` learner ([code](https://github.com/JieyuZ2/wrench/tree/main/wrench/labelmodel)). It covers **(b)** and **(a)**, and it is a way to compare label models. The datasets are mirrored on Hugging Face ([jieyuz2/WRENCH](https://huggingface.co/datasets/jieyuz2/WRENCH)).

**API.** Each label model has `fit(dataset_train, …)` and `predict_proba(dataset)`, and takes a `BaseDataset` or a numpy vote matrix with −1 = abstain (e.g. [hyper_label_model.py](https://github.com/JieyuZ2/wrench/blob/main/wrench/labelmodel/hyper_label_model.py)).

**Evidence** ([full paper](https://ar5iv.labs.arxiv.org/html/2109.11377)):

- "There is no such method that could consistently outperform others."
- "MeTaL and MV are the best label models" overall.
- The best per dataset varies, e.g. IMDb (MeTaL) 88.86 accuracy, Youtube (MV) 98.00, AGNews (Dawid-Skene) 88.20, TREC (Data Programming) 82.36.

**Maintenance.** v1.1 (2021-11); the last commit was 2024-02. It pins `torch<2.0`, `numpy<=1.22.3`, `scikit-learn<0.25`, `faiss-gpu`, `numba==0.43.0` and others ([setup.py](https://github.com/JieyuZ2/wrench/blob/main/setup.py)).

**Fit and pitfalls.** It will not install cleanly on a modern Python 3.12 CPU box because of those pins. Its value to us is the *finding*: majority vote is a strong baseline and should always be reported next to any label model. Individual model files can be copied out if needed.

### Related: HyperLM and FlyingSquid (both runnable outside Wrench)

- **HyperLM** is a label model pre-trained on synthetic data. It labels a new vote matrix in one pass with no fitting. It reports +1.4 points average accuracy and about 6× efficiency over the best prior methods on 14 datasets ([Wu et al., ICLR 2023](https://arxiv.org/abs/2207.13545v3); [code](https://github.com/wurenzhi/hyper_label_model)). The last PyPI release is 0.0.5, from 2023-01 ([PyPI](https://pypi.org/project/hyperlm/)).
- **FlyingSquid** is a closed-form "triplet" label model, which avoids SGD.
  - Signature: `LabelModel(m, lambda_edges=[], allow_abstentions=True, triplets=None, …)`, then `.fit(L)`, `.predict(L)` and `.estimated_accuracies()`.
  - **`lambda_edges` lets you declare which LFs are dependent** ([label_model.py](https://github.com/HazyResearch/flyingsquid/blob/master/flyingsquid/label_model.py); [README](https://github.com/HazyResearch/flyingsquid); [Fu et al., ICML 2020](https://arxiv.org/abs/2002.11955)).
  - That makes it the only maintained-enough option where we can say "wordings 1-3 of atom X are linked". It was last updated in 2020, Apache-2.0.
  - Triplet methods need at least three sources that are conditionally independent of each other, which constrains how many correlated wordings help. That is my reading of the method, not a stated limit in the README.

## 5. crowd-kit (crowdsourcing aggregation)

**What it does.** A scikit-learn-style library of classic crowd-label aggregators: Majority Vote, One-coin and full Dawid-Skene, GLAD (item difficulty), MACE (spammer detection), M-MSR, Wawa, KOS and Zero-Based Skill ([README](https://github.com/Toloka/crowd-kit)). It covers **(a)** (worker skill or confusion matrices) and **(b)**.

**API.** `DawidSkene(n_iter).fit_predict_proba(df)` takes a DataFrame with columns `task, worker, label`. The fitted model exposes `errors_` (each worker's confusion matrix, which is (a)), `probas_`, and an optional `initial_error` prior ([dawid_skene.py](https://github.com/Toloka/crowd-kit/blob/main/crowdkit/aggregation/classification/dawid_skene.py)).

**Evidence.** I found no crowd-kit benchmark on weak supervision. Recent studies on LLM annotators are a direct warning for us:

- With multiple LLMs labelling child speech, Dawid-Skene estimated one model's accuracy at 90.7%, against 71.0% measured on a 500-item expert gold set, and reversed the model ranking. MV, Dawid-Skene and MACE "produce near-identical consensus labels". The authors locate the error in "shared annotator bias rather than in the aggregation rule itself" ([Said & Villaneau, CAS@LREC 2026](https://aclanthology.org/2026.cas-1.11/)).
- Majority vote across semantically equivalent prompts "significantly improves reproducibility and reduces variance". The abstract does not claim better correctness ([Liu 2026, arXiv:2604.16413](https://arxiv.org/abs/2604.16413)).

**Maintenance.** 1.4.2 (2025-10-13), Apache-2.0 ([PyPI](https://pypi.org/project/crowd-kit/)).

**Fit.** CPU, tiny and easy. Like Snorkel, it assumes errors are independent across workers, which our wordings violate.

## 6. LLM-as-labeller plus label-model pipelines

### Prompted weak supervision (Smith et al. 2022) and Alfred (Yu & Bach 2023)

- **Idea.** Each prompt to an LLM is an LF. Its responses are mapped to votes or abstains, and Snorkel denoises them. On Wrench this gave an average 19.5% reduction in errors versus zero-shot prompting, and was comparable to or better than hand-written rules ([Smith et al., arXiv:2205.02318](https://arxiv.org/abs/2205.02318)). This is our setup almost exactly.
- **Alfred** packages the idea ([ACL 2023 demo](https://arxiv.org/abs/2305.18623); [repo](https://github.com/BatsResearch/alfred)).
  - It provides `alfred.client.Client` (local Hugging Face or API models), `alfred.template.StringTemplate` (prompt templates with answer choices) and `Voter(label_map).vote(responses)`.
  - Label models live in `alfred.labeling`: `MajorityVote`, `NaiveBayes`, `FlyingSquid` and `NPLM` ([labeling/](https://github.com/BatsResearch/alfred/tree/main/alfred/labeling)). The `FlyingSquid` wrapper calls `fit(votes)` then `predict(votes)` with no dependency edges ([flyingsquid.py](https://github.com/BatsResearch/alfred/blob/main/alfred/labeling/flyingsquid.py)).
  - Reported evidence is only a 2.9× throughput gain from batching. No accuracy benchmark is in the demo paper ([arXiv:2305.18623](https://arxiv.org/abs/2305.18623)).
  - BSD-3-Clause; last commit 2025-04.
  - The label models come from BatsResearch's [labelmodels](https://github.com/BatsResearch/labelmodels): `NaiveBayes(num_classes, num_lfs).estimate_label_model(votes)`, `.get_accuracies()` and `.get_label_distribution(votes)`, with **0 = abstain** in that convention ([README](https://github.com/BatsResearch/labelmodels)).
- **Fit.** We already have our own teacher client. Alfred's value would be its label models, which are available standalone in `labelmodels`. Alfred does nothing about correlated prompts.

### Structure learning for prompted LFs (Su, Yu, Zhang, Bach 2023/24)

This work tackles our exact correlation problem. Its Structure Refining Module uses the LLM's embeddings *of the prompts* on the hypothesis that "similar prompts tend to yield correlated labels". It removes redundant prompted LFs (LaRe) and generates a correlation structure (CosGen). It reports up to +12.7 points over the plain prompted-WS pipeline ([arXiv:2402.01867](https://arxiv.org/abs/2402.01867), IEEE BigData 2023; [code](https://github.com/BatsResearch/su-bigdata23-code)). The research code has no licence and its last push was 2023-11. Treat it as a method to copy, not a dependency.

### Ask Me Anything (AMA) prompting (Arora et al. 2022)

AMA asks several prompts per input and combines them with weak supervision, noting that prompts "can have very different accuracies and complex dependencies". It reports an average +10.2% over few-shot. GPT-J-6B matched or beat few-shot GPT-3-175B on 15 of 20 benchmarks ([arXiv:2210.02441](https://arxiv.org/abs/2210.02441); [repo](https://github.com/HazyResearch/ama_prompting), last push 2023-07).

### Embroid (Guha et al. 2023)

Embroid corrects an LLM's predictions using *embedding neighbourhoods*: neighbours under several embedding models vote, and a latent-variable model combines those votes with the original prediction. It reports +7.3 points on average with GPT-JT, across six LMs and up to 95 tasks ([arXiv:2307.11031](https://arxiv.org/abs/2307.11031); [repo](https://github.com/HazyResearch/embroid), no licence, 2023). This is very close to our "embedding-similarity head" source, and it is CPU-feasible once the embeddings exist.

### Smoothie (Guha et al., NeurIPS 2024)

Smoothie estimates each LLM's quality per sample without labels, from agreement among embeddings of their outputs. Its scores tracked true quality and picked the best model on 9 of 14 tasks ([arXiv:2412.04692](https://arxiv.org/abs/2412.04692); [blog](https://hazyresearch.stanford.edu/blog/2024-12-10-smoothie); [repo](https://github.com/HazyResearch/smoothie), MIT). It is built for generated text, not yes/no votes, so it is only loosely relevant to (a).

### Snorkel Flow foundation-model LFs

These are commercial and closed ([snorkel.ai](https://snorkel.ai)). Not usable here.

---

## Cross-cutting pitfalls for our case

1. **Same-LLM wordings are not independent witnesses.**
   - Every standard label model (Snorkel, Dawid-Skene, Naive Bayes, CROWDLAB) assumes independent errors ([Snorkel docs](https://snorkel.readthedocs.io/en/master/packages/_autosummary/labeling/snorkel.labeling.model.label_model.LabelModel.html)). Three wordings that share a bias will outvote a correct regex and *raise* their own estimated accuracy.
   - This is the effect measured in [Said & Villaneau 2026](https://aclanthology.org/2026.cas-1.11/): 90.7% estimated vs 71.0% true.
   - Disagreement between wordings is real information about uncertainty. Agreement between them is weak evidence of correctness.
2. **Embedding heads trained on teacher labels are teacher copies.** A head fitted on teacher labels inherits the teacher's errors, so as a voting source it is correlated with the teacher by construction. It is valid as a cross-fitted `pred_probs` model for cleanlab or CROWDLAB, which is what those methods expect. As an independent LF, only a zero-shot similarity (to an atom description or seed examples) qualifies. That is my reading, consistent with the conditional-independence requirement above.
3. **Rare atoms.** With 5 positives, the class prior and the LF accuracies are poorly determined. Supply `class_balance` and report per-atom intervals; do not trust a single number.
4. **No tool handles cross-atom logic** (e.g. "price went up" contradicts "price went down") in the open-source versions. MeTaL modelled task hierarchies ([arXiv:1810.02840](https://arxiv.org/abs/1810.02840)), but that code is not in Snorkel 0.10. We have to encode these rules ourselves, as extra LFs or as post-hoc contradiction flags.
5. **Validation without ground truth is circular.** Every (a) estimate is model-based. A small human-checked audit set is the only way to measure the error of the label model itself ([Said & Villaneau 2026](https://aclanthology.org/2026.cas-1.11/); [CROWDLAB limitations](https://ar5iv.labs.arxiv.org/html/2210.06812)). cleanlab's `get_active_learning_scores` can choose which stories to audit ([docs](https://docs.cleanlab.ai/stable/cleanlab/multiannotator.html)).
6. **Always report majority vote next to any label model.** Wrench found MV among the best overall ([Wrench](https://ar5iv.labs.arxiv.org/html/2109.11377)).

---

## Recommendation (ranked)

### 1. cleanlab, for (c) and per-source accuracy (a)

- Maintained (2026-01 release), Apache-2.0, pure numpy/sklearn on CPU.
- It has a native multi-label API that matches our 44 atoms.
- CROWDLAB is designed for the situation where few labels exist per item and a feature-based model has to fill in.
- It plugs straight into the e5 logistic heads we already train, as long as they are trained out-of-fold.

### 2. Snorkel `LabelModel`, for (b), with wordings collapsed first

- It is the reference label model, and Wrench ranks it (MeTaL) with MV as the best overall.
- It works on CPU in seconds for 2,300×≈5 matrices.
- `get_weights()` gives (a) and `LFAnalysis` gives label-free diagnostics.
- It is stable but frozen (v0.10.0, 2024).

If we want to *declare* the wording dependence instead of collapsing it, swap in FlyingSquid with `lambda_edges`. It uses the same vote-matrix input but is unmaintained since 2020. skweak's name-based `redundancy_factor` is the other ready-made option, but it is unmaintained and spaCy-bound. Its formula is easy to copy.

### Minimal pipeline (per atom, all CPU)

1. **Build the vote matrix** `L` (2,300 × m, values {−1 abstain, 0 no, 1 yes}).
   - Teacher wordings w1..w3 are kept as separate columns for diagnostics only.
   - Keyword/regex LFs vote yes on a match and abstain otherwise. Do not let them vote "no" on absence.
   - Add an optional zero-shot embedding-similarity LF (similarity to the atom description, with a threshold), not trained on teacher labels.
2. **Run label-free diagnostics** with `LFAnalysis(L).lf_summary()`: coverage, overlap and conflict per source. Also compute the wording-agreement rate per atom.
3. **Collapse correlated wordings** into one `teacher` source: yes if all wordings say yes, no if all say no, otherwise −1 abstain. Keep the disagreement as a flag. Optional: also add one `teacher_any` source to test sensitivity.
4. **Combine with a label model**: `LabelModel(cardinality=2).fit(L_collapsed, class_balance=[1-p, p], seed=0)` with `p` from the teacher's base rate. Then `P = predict_proba(L_collapsed)` and `w = get_weights()`. Report it next to majority vote over the same columns.
5. **Fit the model out-of-fold.** Train the e5 logistic head with 5-fold cross-fitting on the soft labels `P` (or on hard consensus), and collect the out-of-fold `pred_probs`.
6. **Run CROWDLAB per atom**: `get_label_quality_multiannotator(labels_multiannotator=L_with_NaN_for_abstain, pred_probs=oof_probs, consensus_method="best_quality")`. Read `annotator_stats` for each source's estimated quality, which is (a). Read `consensus_label` and `consensus_quality_score` per story, which give (b) and (c).
7. **Run multi-label issue finding across all 44 atoms**: `cleanlab.multilabel_classification.filter.find_label_issues(labels=consensus_lists, pred_probs=oof_matrix, return_indices_ranked_by="self_confidence")`, plus a hand-written cross-atom contradiction check.
8. **Audit.** Rank stories by low consensus quality, wording disagreement, contradictions and `get_active_learning_scores`. Hand-check about 100-200 of them. That set becomes the first ground truth for measuring how much steps 4-7 actually help. State the pass/fail bar before looking.
