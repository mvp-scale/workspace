# Distilling a Noisy LLM Labeller to CPU: What the Evidence Supports

Date of research: 2026-10-18. Terms: "LLM" = the local large language model labeller; "student" = the CPU classifier. Every acronym is spelled out at first use. Source types are marked: **[paper]** = peer-reviewed or arXiv paper; **[README/blog/card]** = GitHub README, vendor blog, docs page or model card; **[sim]** = this report's own simulation or arithmetic.

## Bottom line

1. There is no single published pipeline that matches this setting end to end (long news, 45 rare binary atoms, 2–4 paraphrased prompts to one LLM, CPU student). Every step below is proven in isolation; the combination is not.
2. The 35–37% recall plateau is most likely a **label-quality ceiling, not a student-architecture problem**: six student families all stopped at the same place, and 2–4 paraphrases of one LLM are nearly one rater, so the "LLM positives" the student is scored against are themselves noisy.
3. A label model (Snorkel, Dawid-Skene, FlyingSquid) over 2–4 correlated prompts is **not supported by the evidence**; majority vote (MV) is the benchmark winner at low label density, and all label models assume conditional independence the paraphrases violate.
4. The downstream consumes **daily rates, not per-article labels**. Under quantification learning, a 35%-recall student with stable, measured true-positive rate (TPR) and false-positive rate (FPR) gives unbiased daily counts after an Adjusted Classify & Count (ACC) correction. The acceptance target must come from the simulation's sensitivity to rate error, not from recall against the LLM.
5. A **human reference set is unavoidable**: ~100 labelled predicted positives per atom gives precision to ±0.10; recall needs a stratified, importance-weighted predicted-negative stratum. The 486-article test cannot rank students (this report's simulation puts its minimum detectable macro-AP (average precision) difference near 0.05).
6. For the student, **static embeddings (model2vec/potion) are the only option with evidence of sub-millisecond CPU inference**; 22–33M-parameter int8 encoders probably fit 50 ms but no absolute latency is published.
7. Label budget: spend it on **positive-hunting first** (search beats active learning (AL) at 1–5% base rates), then uncertainty sampling; re-asking the LLM pays only where its per-atom accuracy is ~0.6–0.7, not ~0.9.

---

## Ranked step-by-step pipeline

Order is by expected return on effort. Each step names the discipline it comes from, the tool, and the reason. Sections 1–8 below give the evidence.

| # | Step | Discipline | Tool choice | Reason |
|---|---|---|---|---|
| 1 | Decide what "good enough" means in the simulation's units: run the agent-based model (ABM) with (a) LLM-derived daily rates and (b) noise-injected rates on a grid of (TPR, FPR) per atom; record where ABM outputs leave tolerance. | Quantification learning + global sensitivity analysis | SALib (Sobol or Morris) or extended one-factor-at-a-time (OFAT) | Recall vs the LLM is a classifier-centric number; the ABM's tolerance for rate error is the property of the problem. |
| 2 | Aggregate the 2–4 wordings per atom by MV, treating the reversed wording as a consistency flag, not an equal rater. Keep the per-prompt votes and any LLM log-probabilities; do not store only the aggregate. | Weak supervision / label models | Plain MV; Dawid-Skene (DS) only with a strong prior and dependency edges | Label models need ≥3 conditionally independent sources per atom; paraphrases of one model are not independent, and MV won or tied on WRENCH and BoxWRENCH. |
| 3 | Build a trusted human reference set: per atom, ~100 student-predicted positives (precision) plus a shared pool of ~300–600 predicted negatives stratified by max-over-atoms score (recall), 2 raters each, third adjudicates, store all labels. Report Krippendorff's α with bootstrap confidence interval (CI). | Content analysis + active evaluation (importance-weighted estimation) | OASIS or hand-rolled Horvitz-Thompson weights; `krippendorff` or similar | Precision to ±0.10 needs ~97 predicted positives; recall at 2% base rate from random sampling needs ~4,700 articles per atom, so stratify and reweight. |
| 4 | Re-score the LLM and every prior student against the reference set from step 3, not against the LLM. This tells you whether the 35% plateau is the student missing LLM positives or the LLM positives being wrong. | Measurement | sklearn per-atom precision/recall with Wilson CIs | The 35–37% plateau across six architectures is the signature of a label ceiling, which only human labels can confirm. |
| 5 | Switch the downstream from raw counts to ACC-corrected counts: p = (p_CC − FPR)/(TPR − FPR), with TPR/FPR estimated on the reference set from step 3. Use SLD/EMQ (Saerens-Latinne-Decaestecker expectation-maximisation quantification) or PACC (probabilistic ACC) if daily topic drift is visible. | Quantification learning | QuaPy (`pip install quapy`) | On LeQua 2022 raw Classify & Count had ~6× the relative error of ACC; a low-recall student with stable TPR/FPR gives unbiased rates after correction. |
| 6 | Flag individually wrong LLM labels with confident learning on out-of-sample student probabilities (multi-label, one-vs-rest), and send the top-ranked flags plus student-vs-LLM disagreements to the LLM for re-asking or to humans. | Confident learning | cleanlab `multilabel_classification` (v2.9.0) | Confident learning needs only predicted probabilities and noisy labels; CelebA Lift@100 ≈ 4.5. Disagreement-based relabelling beat round-robin by ~6 points in Sheng et al. |
| 7 | Spend the LLM budget on positive-hunting first: embedding nearest-neighbour or keyword retrieval around known positives from the 1,500/day stream, LLM-label the candidates, then switch to uncertainty sampling (Breaking Ties: smallest margin between the top two class probabilities) with the student as query model once positives per atom are in the tens-to-hundreds. | Active learning / guided learning | small-text (SetFit and transformers integrations) | Guided search dominated AL and random at skews ≥20:1 and stayed cheaper until a found positive cost ~8× a label; AL transfers poorly across models, so query with the student itself. |
| 8 | Student body: potion-base-8M or -32M static embeddings, chunk the article into sentences or ~128-token windows, encode each, max-pool per atom, logistic or small multilayer perceptron (MLP) head with binary cross-entropy (BCE) or focal loss, trained on MV labels weighted by prompt agreement. Export via ONNX (Open Neural Network Exchange). | Knowledge distillation (KD) + long-document classification | model2vec `StaticModelForClassification` (v0.10.0), or sentence-transformers `StaticEmbedding.from_model2vec` + SetFit head | Only static embeddings have evidence of sub-ms CPU cost; chunk+max-pool beat first-512 truncation by 0.2–13.4 F1; soft/weighted targets have classical KD support. |
| 9 | Thresholds: do not tune 45 free per-atom thresholds on 5–100 positives; use a smoothed F-measure or shared threshold, and prefer the threshold that maximises TPR − FPR (the ACC denominator from step 5) over the one that maximises precision. | Multi-label thresholding + quantification | Lin & Lin smoothed-F; Forman "MAX" variant | Per-label SCut thresholding overfits rare labels (macro-F 8.27 vs 12.69 on Wiki10-31K); ACC variance scales as 1/(TPR − FPR)². |
| 10 | Fit a learning curve: evaluate the student at ≥5 nested subset sizes, fit error = a + b·n^(−c) by weighted least squares, invert for the n needed to reach the step-1 target. Repeat per atom indexed by positives. | Learning-curve extrapolation | Figueroa et al. recipe (nonlinear weighted least squares) | Tells you whether to buy more labels or change the labeller; fine-tuning exponents ~0.1 mean doubling data cuts excess error only ~7%. |
| 11 | Compare students on the reference set with a pre-registered protocol: per-atom paired bootstrap on ΔAP, Wilcoxon signed-rank over the 45 per-atom deltas, Holm correction and a Bonferroni replicability count, ≥3 seeds. Grow the reference set until the minimum detectable effect is below the effect you care about. | Statistical comparison + replicability analysis | sklearn `average_precision_score(average=None)`, statsmodels `mcnemar`, custom bootstrap | 486 articles (~10 positives per atom) cannot detect a 0.03 macro-AP difference; the resampled t-test and raw win-counting are both known to be unsafe. |
| 12 | Monitor drift: keep LLM-labelling a random daily slice as a reference series, re-estimate TPR/FPR monthly, and re-run step 1's noise-injection curve when the atom set or prompts change. | Measurement-error inference | PPI (prediction-powered inference) or DSL (design-based supervised learning) estimators | Google Flu Trends overshot 100 of 108 weeks because bias was not constant; GPT-4 re-run six months later shifted F1 by +0.022. |

---

## 1. The standard pipeline and its canonical references

**Discipline.** This is programmatic weak supervision (data programming) feeding knowledge distillation: noisy labelling functions (LFs) → a label model that estimates each LF's accuracy from agreement statistics without gold → probabilistic training labels → a discriminative end model (the student) that generalises beyond the LFs. The LLM-prompt variant replaces hand-written LFs with prompts.

**Up front.** No primary source combines LLM-prompt LFs, ≤5 correlated sources per label, 1–5% base rates and a CPU-class student. The canonical references are each one piece.

| Stage | Canonical reference | What it established | Number |
|---|---|---|---|
| LFs + generative label model | Data Programming, Ratner et al. NeurIPS 2016 [paper] ([arXiv:1605.07723](https://arxiv.org/abs/1605.07723)) | Noise-aware discriminative loss on label-model marginals | +2.34 F1 average over rule aggregation on three information-extraction tasks; LSTM (long short-term memory network) +6 F1 on TAC-KBP slot filling |
| System + MV-vs-model decision | Snorkel, Ratner et al. VLDB 2017 [paper] ([arXiv:1711.10160](https://arxiv.org/pdf/1711.10160)) | "Modelling advantage" over MV is largest at medium label density, near zero at low density | Measured advantage 0.1–7.0 points at densities 1.2–2.3 with 11–33 LFs; optimiser chose MV for one of five tasks |
| Multi-task, correlated sources | Snorkel MeTaL, Ratner et al. AAAI 2019 [paper] ([arXiv:1810.02840](https://arxiv.org/abs/1810.02840)) | Sources may be correlated if the dependency graph is given | +6.8 accuracy over MV average on three tasks |
| Fast closed-form label model | FlyingSquid, Fu et al. ICML 2020 [paper] ([arXiv:2002.11955](https://arxiv.org/pdf/2002.11955)) | Triplet method; needs ≥3 mutually conditionally independent sources per estimate | 170× faster than Data Programming (DP); up to +4.9 F1 |
| LLM prompts as LFs | Smith et al. 2022 [paper, arXiv] ([arXiv:2205.02318](https://arxiv.org/abs/2205.02318)) | Yes/No prompts → votes/abstains → FlyingSquid → RoBERTa student | 19.5% average error reduction over single-prompt zero-shot; 9–73 prompts per task |
| Benchmark of label models | WRENCH, Zhang et al. NeurIPS 2021 D&B [paper] ([arXiv:2109.11377](https://arxiv.org/abs/2109.11377)) | "MeTaL and MV are the most worth-a-try"; no method consistently wins | 22 datasets, >120 variants |
| Finding wrong labels | Confident Learning, Northcutt et al. JAIR 2021 [paper] ([arXiv:1911.00068](https://web3.arxiv.org/pdf/1911.00068v6)) | Label-error detection from out-of-sample probabilities + noisy labels | CIFAR-10 (image benchmark) 20% noise: detection F1 75%; test acc after cleaning 91.1% vs 78.4% baseline |
| Soft-target distillation | Hinton et al. 2015 [paper, arXiv] ([arXiv:1503.02531](https://arxiv.org/pdf/1503.02531)) | Soft targets carry more information than hard labels | MNIST (handwritten-digit benchmark) small net 146 → 74 errors with soft targets |
| LLM labels → student | Wang et al. Findings EMNLP 2021 [paper] ([arXiv:2108.13487](https://arxiv.org/abs/2108.13487)) | GPT-3 labels 50–96% cheaper than human for same student performance; confidence-route lowest-logit labels to humans | Top-10% confident labels ~90–95% accurate |
| Few-shot contrastive student | SetFit, Tunstall et al. 2022 [paper, arXiv] ([arXiv:2209.11055](https://arxiv.org/pdf/2209.11055)) | Siamese fine-tune + logistic head | 62.3 avg at 8/class vs T-Few 3B 63.4 with 19× fewer FLOPs (floating-point operations) |
| Static embedding student | model2vec [README] ([repo](https://github.com/MinishLab/model2vec)) | Distil a sentence transformer's vocabulary to static vectors | potion-base-8M = 91.96% of all-MiniLM-L6-v2 MTEB (Massive Text Embedding Benchmark) average |
| Label budget allocation | Zhang, Strubell & Hovy EMNLP 2022 survey [paper] ([arXiv:2210.10109](https://arxiv.org/pdf/2210.10109)) | AL gains can be "negligible or even negative" under model mismatch, cold start, noise | Qualitative only |

**Maintenance status (checked 2026-10-18).** The `snorkel` package's last release is v0.10.0 (2023-02-27) and the team says it is "focusing our efforts on Snorkel Flow" ([release page](https://github.com/snorkel-team/snorkel/releases/tag/v0.10.0); [README](https://github.com/snorkel-team/snorkel)). WRENCH's last README entry is January 2023 ([repo](https://github.com/JieyuZ2/wrench)). Treat both as reference implementations. cleanlab v2.9.0, model2vec v0.10.0 (2026-10-11), SetFit v1.2.0 (2026-09-04) and sentence-transformers 6.1.0 (2026-09-18) are live ([cleanlab releases](https://github.com/cleanlab/cleanlab/releases); [PyPI model2vec](https://pypi.org/project/model2vec/); [PyPI setfit](https://pypi.org/project/setfit/); [PyPI sentence-transformers](https://pypi.org/project/sentence-transformers/)).

---

## 2. Estimating each wording's accuracy without ground truth

**Discipline.** Label models (weak supervision) and crowdsourcing aggregation (Dawid-Skene (DS), GLAD, MACE) both solve the same problem: recover per-source accuracies from agreement patterns. All assume sources are conditionally independent given the true label unless a dependency graph says otherwise.

**Up front.** No primary source studies label models with ≤5 sources at 1–5% base rates, and none measures the error correlation of paraphrased prompts to one LLM. The regime is unstudied.

### 2.1 What the assumptions require

| Model | Independence requirement | Class balance | Dependency handling | Source |
|---|---|---|---|---|
| Data Programming | LFs independent given Y, except user-declared edges | Assumed 0.5 in the analysis | User-specified edge types: Similar, Fixing, Reinforcing, Exclusive | [arXiv:1605.07723](https://arxiv.org/pdf/1605.07723) [paper] |
| MeTaL | Independent except edges in a known, chordal graph | Estimated from three-way overlaps of independent sources (Kruskal rank condition) | Edges can be added; misspecification not analysed | [arXiv:1810.02840](https://arxiv.org/pdf/1810.02840) [paper] |
| FlyingSquid | ≥3 mutually conditionally independent sources per accuracy estimate | User-provided or estimated | Graph augmented for abstains | [arXiv:2002.11955](https://arxiv.org/pdf/2002.11955) [paper] |
| Dawid-Skene | Observers independent given truth | Estimated | None | [RePEc record](https://ideas.repec.org/a/bla/jorssc/v28y1979i1p20-28.html) [paper] |
| MACE | Annotators independent; spamming independent of truth | Estimated | None; paper does not analyse correlated annotators | [N13-1132](https://aclanthology.org/N13-1132.pdf) [paper] |

Note: structure learning (Bach et al. 2017; Varma et al. 2019) can estimate the dependency graph, but its sample complexity is stated in terms of many sources and many samples, and the reported gains are +1.5 to +4.64 F1 over assuming independence on tasks with dozens of LFs ([arXiv:1703.00854](https://arxiv.org/abs/1703.00854); [PMLR v97](https://proceedings.mlr.press/v97/varma19a.html)) [paper].

### 2.2 What happens with correlated sources

- Balasubramanian, Podkopaev & Kasiviswanathan (AWS, Jan 2026) prove conditionally-independent (CI) aggregators (DS, weighted MV) "interpret agreement as multiple independent pieces of evidence", stay strictly suboptimal as the number of judges grows, and yield "miscalibrated posteriors and even confidently incorrect predictions". With six LLM judges, dependence-aware Ising aggregation scored 0.90 / 0.79 / 0.68 vs CI weighted MV 0.82 / 0.72 / 0.61 on relevance, toxicity and summarisation ([arXiv:2601.22336](https://arxiv.org/pdf/2601.22336)) [paper]. No DS parameter-bias number is given.
- Liu (Apr 2026): 20 semantically equivalent prompts, temperature 0, GPT-4o mini on TREC had accuracy range 0.546–0.808; MV over k = 10 prompts raised pairwise agreement from ~0.71 to ~0.95 but may "reinforce consistent but incorrect predictions" ([arXiv:2604.16413](https://arxiv.org/pdf/2604.16413)) [paper].
- Camuffo et al. (Jan 2026): semantics-preserving rewrites shifted annotations 8.38–28.10 percentage points; 100 identical-prompt GPT-4o runs gave agreement 0.68–0.92; the authors recommend DS or GLAD when κ < 0.6 but do not apply them ([arXiv:2601.02370](https://arxiv.org/pdf/2601.02370)) [paper].
- Ibrahim et al. NeurIPS 2019: MV-initialised DS expectation-maximisation (EM) collapsed on sparse/imbalanced data (Nursery p = 0.5: 66.48% error vs MV 4.83%) ([arXiv:1909.12325](https://arxiv.org/pdf/1909.12325)) [paper]. This is the direct warning for 1–5% atoms with 5–100 positives.

### 2.3 Benchmark verdict: MV vs label models

| Benchmark | Finding | Numbers | Source |
|---|---|---|---|
| WRENCH | No label model consistently beats MV | Basketball (4 LFs): FlyingSquid 43.18, weighted MV 40.73, Data Programming 40.70, gold 64.97 | [arXiv:2109.11377](https://arxiv.org/pdf/2109.11377) [paper] |
| BoxWRENCH (Jan 2025) | "Majority Vote and Dawid-Skene performed the best among the label models tested" | Claude9 F1: MV 0.582, DS 0.572, Snorkel 0.557, FlyingSquid 0.352 | [arXiv:2501.07727](https://arxiv.org/html/2501.07727v2) [paper] |
| Snorkel VLDB | MV near-optimal at low label density | Optimiser predicted advantage within 2.16 points on average | [arXiv:1711.10160](https://arxiv.org/pdf/1711.10160) [paper] |
| Smith et al. 2022 | Gains over zero-shot came with 9–73 prompts; Babbage prompts "strongly correlated" limited ensemble gains; no MV-vs-label-model ablation | 19.5% error reduction vs zero-shot | [arXiv:2205.02318](https://arxiv.org/pdf/2205.02318) [paper] |

### 2.4 The reversed wording

LLMs are often insensitive to negation. Truong et al. (*SEM 2023) found non-instruction-tuned models at or below chance on negated NLI (natural language inference) (InstructGPT MoNLI 0.470, below chance) and that models "cannot differentiate between identical contexts, differing only on whether negation is present or absent" ([2023.starsem-1.10](https://aclanthology.org/2023.starsem-1.10.pdf)) [paper]. Hossain et al. ACL 2022 found RoBERTa drops of 9–33% on instances where negation matters ([arXiv:2203.08929](https://arxiv.org/pdf/2203.08929)) [paper]. Vrabcová et al. 2025 found negation sensitivity rising with model size (Spearman 0.867), 37.85% to 94.81% across Llama 3, Qwen 2.5 and Mistral ([arXiv:2503.22395](https://arxiv.org/html/2503.22395v2)) [paper]. No paper evaluates a reversed prompt as a weak-supervision source. Treat it as a consistency check (flag articles where direct and reversed prompts both say "yes") or, if used in a label model, give it a "Similar" dependency edge and per-label (asymmetric) accuracies as MeTaL allows.

### 2.5 Finding individual wrong labels

Confident learning assumes class-conditional noise (flip probability depends on the true class, not the article), takes out-of-sample predicted probabilities plus noisy labels, and sets a per-class threshold at the mean predicted probability among items carrying that label ([arXiv:1911.00068](https://web3.arxiv.org/pdf/1911.00068v6)) [paper]. The multi-label variant runs one-vs-rest per class and pools scores with an exponential moving average (α = 0.8); on CelebA, 67 of the top-100 flagged images were truly mislabelled against a 15% base error rate (Lift@100 ≈ 4.5) ([arXiv:2211.13895](https://arxiv.org/pdf/2211.13895)) [paper]. Neither paper tests 1–5% positive rates; with 5–100 positives the positive-class threshold rests on very few items. Training-dynamics alternatives (Dataset Cartography, AUM) need a multi-epoch end model and are evaluated only on single-label tasks ([arXiv:2009.10795](https://arxiv.org/abs/2009.10795); [arXiv:2001.10528](https://arxiv.org/abs/2001.10528)) [paper].

**What this means for 2–4 wordings of one LLM.** The effective number of independent raters is closer to 1 than 3 or 4. A learned label model will estimate each wording's accuracy upward toward the consensus. Use MV, keep the per-wording votes, and get accuracy estimates from the human reference set (pipeline step 3).

---

## 3. Setting the acceptance target from the downstream system

**Discipline.** Four layers apply. Cost-sensitive classification (Elkan 2001) sets a per-article threshold from a cost ratio. Quantification learning (Forman 2008; González et al. 2017) handles "I only need counts". Inference with predicted data (Fong & Tyler 2021; Egami et al. 2023; prediction-powered inference, Angelopoulos et al. 2023) handles using predictions as inputs to estimation. Global sensitivity analysis for simulation (ten Broeke et al. 2016; SALib) propagates input uncertainty through the ABM.

**Up front.** No retrieved paper runs classifier labels through an ABM and reports output error against classifier precision/recall. The protocol below is assembled from pieces, each standard in its own field.

### 3.1 Quantification: why 35% recall need not be fatal

Binary ACC: p̂ = (p̂_CC − FPR)/(TPR − FPR), with TPR/FPR estimated on a validation set and the result clipped to [0,1]; it becomes unstable when TPR ≈ FPR ([QuaPy paper](https://arxiv.org/pdf/2106.11057); [Schumacher et al.](https://arxiv.org/pdf/2103.03223)) [paper]. With TPR ≈ 0.35 and small FPR the denominator is ~0.35, so the correction multiplies the raw count by ~2.9 and its variance by ~8× [sim: arithmetic from the formula]. ACC's bias cancellation assumes only the class prior shifts between validation and each day; topic drift breaks it, and SLD/EMQ and PACC are more robust.

| Method | LeQua 2022 T1A (binary) RAE | AE | Source |
|---|---|---|---|
| MLPE (maximum-likelihood prevalence estimation: predict training prevalence) | 3.267 | 0.323 | [LeQua overview](https://ceur-ws.org/Vol-3180/paper-146.pdf) [paper] |
| PCC (probabilistic Classify & Count) | 1.394 | 0.117 | same |
| CC (Classify & Count, raw) | 1.084 | 0.092 | same |
| ACC | 0.170 | 0.037 | same |
| PACC | 0.152 | 0.030 | same |
| SLD/EMQ | 0.114 | 0.025 | same |

Note: RAE = relative absolute error, AE = absolute error, averaged over 5,000 test samples of 250 documents each under the artificial prevalence protocol (prevalence spread over [0,1], not 1–5%). "The overall ordering MLPE < PCC < CC < ACC < PACC < SLD holds across all four tasks." Schumacher et al. (40 binary datasets) found mean AE: CC 0.529, ACC 0.279, HDy (Hellinger-distance y) 0.224, FM (Friedman's method) 0.102 ([arXiv:2103.03223](https://arxiv.org/pdf/2103.03223)) [paper].

### 3.2 Why validate at the aggregate, with measured error propagation

| Case | What was measured | Reported number | Source |
|---|---|---|---|
| Economic Policy Uncertainty (EPU) index (Baker, Bloom & Davis 2016) | Audit of 12,009 articles; machine vs human index correlation | 0.86 quarterly, 0.93 annual; net error uncorrelated with gross domestic product growth (0.02) | [QJE PDF](https://users.ssc.wisc.edu/~mchinn/bakerbloomdavis_QJE2016.pdf) [paper] |
| EPU re-audit (Keith et al. 2020) | Keyword rule F1 vs humans; logistic regression student; index correlation | Rule F1 0.64; bag-of-words logreg F1 0.71; classifier index vs keyword index correlation 0.38 | [arXiv:2010.04706](https://arxiv.org/pdf/2010.04706) [paper] |
| Google Flu Trends (Lazer et al. 2014) | Weeks overestimated; MAE (mean absolute error) vs lagged CDC (Centers for Disease Control) data | 100 of 108 weeks too high; MAE 0.486 vs 0.311 for 3-week-old CDC data | [Science PDF](https://cdanfort.w3.uvm.edu/csc-reading-group/lazer-flu-science-2014.pdf) [paper] |
| GDELT (Global Database of Events, Language and Tone) vs hand-coded conflict data (Hammond & Weidmann 2014) | Time-series and cell-month correlation | 0.64 (ACLED), 0.33 (GED); 0.26 / 0.20 at cell-month | [SAGE](https://journals.sagepub.com/doi/10.1177/2053168014539924) [paper] |
| LLM-labelled inflation index (2024) | Classifier F1; nowcast root-mean-squared-error delta | F1 0.570; RMSE 0.0409 → 0.0407, p = 0.19 | [arXiv:2410.20198](https://arxiv.org/pdf/2410.20198) [paper] |
| Surrogate labels in regression (Egami et al. 2023) | Coverage of 95% CI when using 90%-accurate surrogate directly | 40% coverage | [arXiv:2306.04746](https://arxiv.org/html/2306.04746v3) [paper] |
| Prediction-powered inference (Angelopoulos et al. 2023) | Gold labels needed vs classical | 21 vs 35 (deforestation); 316 vs 799 (proteomics) | [arXiv:2301.09633](https://arxiv.org/pdf/2301.09633) [paper] |

Lesson across cases: a text-derived rate is useful when its bias is stable and measured against an independent reference series, and harmful when bias drifts. Note: ACLED and GED are the Armed Conflict Location & Event Data and Uppsala Georeferenced Event Dataset hand-coded series.

### 3.3 Protocol to derive the target (assembled, not from one source)

1. Hold a random daily slice LLM-labelled and, later, human-labelled (the reference series).
2. Downstream delta: run the ABM on LLM-derived rates and on student-derived ACC-corrected rates; report the distribution of output differences over replicates (mirrors Egami Figure 1 and Lazer's with/without comparison).
3. Noise injection: from LLM labels, flip positives at rate (1 − TPR) and negatives at rate FPR on a grid, aggregate, run the ABM, plot output error vs (TPR, FPR). The knee is the acceptance target. ten Broeke et al. recommend extended OFAT as the starting point for ABMs (OFAT cost 110 runs per parameter; Sobol 17,000 runs on 15 parameters; OFAT found tipping points in 11 of 15 parameters that global methods averaged away) ([JASSS](https://www.jasss.org/19/1/5/5.pdf)) [paper]. SALib's Saltelli design needs N×(2D+2) runs ([SALib docs](https://salib.readthedocs.io/en/latest/user_guide/basics.html)) [README].
4. Measure the ABM's replicate variance first (0.88% of total variance in ten Broeke's model); classifier noise is adequate when its contribution to output variance is comparable to or below replicate noise or below the effect size the simulation is meant to detect.
5. Threshold: with ACC in place, both error types are corrected in expectation and the relevant cost is variance, which argues for the threshold that maximises TPR − FPR (Youden's J; Forman's "MAX" variant) rather than precision. Elkan's cost threshold p* = C_FP/(C_FP + C_FN) applies if per-article decisions are also consumed ([Elkan 2001](https://cseweb.ucsd.edu/~elkan/rescale.pdf); [Ling & Sheng](https://www.csd.uwo.ca/~xling/papers/cost_sensitive.pdf)) [paper]. Hand 2009 makes the general point: misclassification severity "is a property of the problem, not of the classifier chosen" ([Hand 2009](https://mlanthology.org/mlj/2009/hand2009mlj-measuring)) [paper].

---

## 4. Building and sizing a small trusted reference set

**Discipline.** Content-analysis reliability (Krippendorff's α; Artstein & Poesio 2008) for the rater protocol; active evaluation / importance-weighted estimation (Sawade et al. 2010; OASIS, Marchant & Rubinstein 2017) for the sampling design.

**Up front.** No primary source gives a closed-form sample size for stratified recall estimation; the variance depends on stratum false-negative rates known only after a pilot. The AP-power numbers below are this report's simulation.

### 4.1 Rater protocol

| Item | Recommendation | Evidence | Source |
|---|---|---|---|
| Raters per item | 2 independent + third adjudicates; 3–5 only on a calibration subset | Artstein & Poesio: test with more than two coders so shared misreadings surface; Pangakis et al.: at least two subject-matter experts | [J08-4004](https://aclanthology.org/J08-4004.pdf); [arXiv:2306.00176](https://arxiv.org/pdf/2306.00176) [paper] |
| Statistic | Krippendorff's α with bootstrap CI, plus raw agreement and prevalence | Hayes & Krippendorff 2007; α works for any number of observers | [ASC PDF](https://www.asc.upenn.edu/sites/default/files/2021-03/Answering%20the%20Call%20for%20a%20Standard%20Reliability%20Measure%20for%20Coding%20Data.pdf) [paper] |
| Thresholds | α ≥ 0.800 reliable; reject below 0.667; both "tentative" | Krippendorff conventions via ATLAS.ti manual; Artstein & Poesio call them "little more than a black art" | [ATLAS.ti](https://doc.atlasti.com/ManualWin/ICA/ICASampleSizeAndDecisionRules.html) [README]; [J08-4004](https://aclanthology.org/J08-4004.pdf) [paper] |
| Rare classes | Expect low chance-corrected agreement at 2% prevalence even with high raw agreement; test reliability on an enriched sample | Feinstein–Cicchetti paradox: 0.90 agreement can give κ = −0.05 | [PMC4236536](https://pmc.ncbi.nlm.nih.gov/articles/PMC4236536) [paper] |
| Store | All per-rater labels, not only the adjudicated label | Uma et al. 2021: soft labels from many judgments beat gold | [JAIR](https://mlanthology.org/jair/2021/uma2021jair-learning) [paper] |
| Reliability sample size | 139 codings for α ≥ 0.800 at four equiprobable codes; far more when the rarest value is 2% | Krippendorff rule "five chance agreements per code"; 5/0.02² ≈ 12,500 paired codings for a 2% value [sim: arithmetic from the stated rule] | [ATLAS.ti](https://doc.atlasti.com/ManualWin/ICA/ICASampleSizeAndDecisionRules.html) [README] |
| Validation size for LLM labels | 250–1,250 random human labels per task; "significantly more" below 1% positives | Pangakis et al. 2023: 9 of 27 GPT-4 tasks had precision or recall < 0.5 | [arXiv:2306.00176](https://arxiv.org/pdf/2306.00176) [paper] |

Realistic ceiling: the Baker-Bloom-Davis EPU annotation (13,797 docs, 14 annotators) reached α = 0.60; Keith et al.'s own re-annotation reached 0.21–0.27 ([arXiv:2010.04706](https://arxiv.org/pdf/2010.04706)) [paper]. Atoms that look like observable facts can be interpretive.

### 4.2 Worked calculation: precision and recall of a 2% atom to ±0.10 [sim: arithmetic]

Formula: Wald sample size n = z²·p(1−p)/h², z = 1.96, h = 0.10 (same binomial basis as the MedCalc precision/recall page, [MedCalc](https://www.medcalc.org/manual/sample-size-CI-precisionrecall.php)).

| Quantity | p assumed | n needed | Arithmetic |
|---|---|---|---|
| Any proportion, worst case | 0.5 | 97 | 3.8416 × 0.25 / 0.01 |
| Any proportion | 0.6 | 93 | 3.8416 × 0.24 / 0.01 |
| Any proportion | 0.7 | 81 | 3.8416 × 0.21 / 0.01 |

- **Precision, sampling predicted positives:** ~93–97 labelled predicted positives per atom. Sawade et al. show the optimal sampling distribution for precision puts zero weight on predicted negatives ([NeurIPS 2010](https://papers.NeurIPS.cc/paper_files/paper/2010/file/d7a728a67d909e714c0774e22cb806f2-Paper.pdf)) [paper].
- **Precision, random sampling:** predicted-positive rate = π·recall/precision = 0.02 × 0.6/0.6 = 0.020; 93/0.020 = 4,650 random articles (4,850 at p = 0.5). The 486-article set holds ~10 predicted positives, giving half-width 1.96 × √(0.25/10) ≈ ±0.31.
- **Recall, random sampling:** need ~93–97 true positives; 0.02 × 486 = 9.7 positives in the current set (half-width ±0.31); 4,650–4,850 articles per atom; the rarest 1% atom needs ~9,700.
- **Recall, stratified:** false negatives occur in predicted negatives at rate π(1−rec)/(1−P(pred pos)) = 0.02 × 0.4/0.98 = 0.0082 at rec = 0.6; ~2,450 random predicted negatives to see ~20 false negatives. Oversample predicted negatives with high scores and reweight by inverse inclusion probability (Horvitz–Thompson). Sawade et al. report the active estimator matched 800 passive labels with <150 labels for recall and ~100 for precision on a 5%-minority spam task; OASIS (Optimal Asymptotic Sequential Importance Sampling) reports up to 83% fewer labels at ~1:3000 imbalance ([arXiv:1703.00617](https://arxiv.org/pdf/1703.00617)) [paper]; Poms et al. report F1 variance 0.005 with ~100 labels at ≤0.1% positives using self-normalised importance sampling ([arXiv:2109.05720](https://arxiv.org/pdf/2109.05720)) [paper]. These are F-measure results; the saving for recall alone is plausible, not proven.
- **Budget sketch:** ~100 predicted positives per atom (45 × 100 = 4,500 labels, little overlap across atoms) plus a shared pool of ~300–600 predicted negatives stratified by max-over-atoms score, weighted per atom. One article's label vector covers all 45 atoms, so the negative pool is shared. Report Wilson or Clopper–Pearson, not Wald, for n < ~40 or p near 0.

### 4.3 Worked calculation: test size to detect Δ macro-AP = 0.03 [sim: this report's own simulation; an illustration]

No closed form exists for the variance of AP; Boyd, Eng & Page 2013 recommend binomial or logit intervals for a single AUCPR (area under the precision-recall curve) and warn that "cross-validation and bootstrap do not provide the advertised coverage for small data sets" ([UW PDF](https://asset.library.wisc.edu/1711.dl/OUTUDKUSNU53G9C/R/file-7ea2f.pdf)) [paper].

Assumptions of the simulation: binormal scores (negatives N(0,1), positives N(μ,1)) tuned to population AP 0.400 and 0.428 at π = 0.02; two classifiers sharing a latent noise component so scores correlate at ρ = 0.7; paired bootstrap over articles, B = 300, one-sided α = 0.05; 150 repetitions per cell; AP computed as sklearn's non-interpolated Σ(R_n − R_{n−1})P_n.

| K atoms | Positives per atom | Articles per atom | SD of observed Δ macro-AP | Power |
|---|---|---|---|---|
| 1 | 10 | 500 | 0.134 | 0.09 |
| 1 | 50 | 2,500 | 0.062 | 0.14 |
| 1 | 200 | 10,000 | 0.033 | 0.17 |
| 5 | 10 | 500 | 0.055 | 0.08 |
| 5 | 50 | 2,500 | 0.027 | 0.21 |
| 5 | 100 | 5,000 | 0.021 | 0.37 |

Extrapolation: SD of a single-atom Δ AP ≈ 0.44/√(positives). Required SD for 80% power one-sided = 0.03/(1.645 + 0.842) = 0.0121.

| Design | Positives per atom needed | Articles at 2% |
|---|---|---|
| K = 1 atom | ~1,320 | ~66,000 |
| K = 5 independent atoms | ~264 | ~13,000 |
| K = 45 independent atoms, all shifting by 0.03 | ~29 | ~1,470 |
| Current: 486 articles, 45 atoms (~9.7 positives each) | SD(Δ macro-AP) ≈ 0.021 | Minimum detectable effect (MDE) ≈ 0.052 |

Caveats: 150 repetitions give power to ±0.03–0.04; at 10 positives the mean observed Δ was 0.017 not 0.028 (AP small-sample bias differs between classifiers); cross-atom independence is optimistic because the same articles feed all 45 atoms. The stated ~0.03 detectability for the 486 set is plausible only if per-atom differences are more consistent than this binormal model assumes. Sakai's topic-set-size design is the information-retrieval template: treat each atom as a topic, estimate the variance of per-atom Δ AP from a pilot, solve for the number of atoms/articles ([Sakai EVIA 2016](https://research.nii.ac.jp/ntcir/workshop/OnlineProceedings12/pdf/evia/02-EVIA2016-SakaiT.pdf)) [paper].

---

## 5. Comparing students on small test sets

**Discipline.** Statistical comparison of classifiers (Dietterich 1998; Demšar 2006; Dror et al. 2018) plus replicability analysis for multiple datasets (Dror et al. 2017) and pre-registration (van Miltenburg et al. 2021).

| Question | Recommendation | Evidence | Source |
|---|---|---|---|
| Binary decisions at a fixed threshold, one test set | McNemar (exact binomial) | Resampled paired t-test and difference-of-proportions have inflated Type I error and "should never be used" | [Dietterich 1998](https://web.engr.oregonstate.edu/~tgd/publications/dietterich-approximate-statistical-tests-nc1998.pdf) [paper]; [statsmodels mcnemar](https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.mcnemar.html) [README] |
| AP or F1 on one test set | Paired bootstrap or approximate randomisation, same resample for both models | Smucker et al.: t-test, bootstrap and randomisation agree; discontinue Wilcoxon/sign for single collections; Berg-Kirkpatrick et al.: correlated systems need smaller gains; calibration drops out of domain (92% → 48%) | [CIIR PDF](https://ciir-publications.cs.umass.edu/getpdf.php?id=744); [D12-1091](https://aclanthology.org/D12-1091.pdf) [paper] |
| Across 45 atoms (two students) | Wilcoxon signed-rank over per-atom Δ AP | Demšar: paired t-test across datasets is "conceptually inappropriate and statistically unsafe"; counting wins makes tests less reliable | [JMLR](https://www.jmlr.org/papers/volume7/demsar06a/demsar06a.pdf) [paper] |
| Multiple comparisons on dependent atoms | Holm for which atoms; Bonferroni replicability count (valid under any dependency) for "A beats B on at least u of 45" | Naive counting over-optimistic: sentiment 10 naive vs 6 Bonferroni of 12 | [TACL Q17-1033](https://aclanthology.org/Q17-1033.pdf) [paper] |
| Per-atom AP interval | Binomial or logit interval, not bootstrap, at ~10 positives | Boyd et al. 2013 | [UW PDF](https://asset.library.wisc.edu/1711.dl/OUTUDKUSNU53G9C/R/file-7ea2f.pdf) [paper] |
| Seeds | ≥3–5 seeds, treat seed as a variance source; data bootstrap dominates | Bouthillier et al.: init "generally less than 50% of the variance of bootstrap"; N ≥ 29 paired runs for γ = 0.75 | [arXiv:2103.03098](https://arxiv.org/pdf/2103.03098v1) [paper] |
| Power | Compute MDE by simulation from expected Δ and model agreement | Card et al. 2020: GLUE (General Language Understanding Evaluation) MDE at 80% power ranges 5.26 points (WNLI, n = 147) to 0.11 (QQP, n = 390,965); ~46% of past comparisons adequately powered | [EMNLP 2020](https://aclanthology.org/2020.emnlp-main.745.pdf) [paper] |
| Pre-registration | Hypotheses, variables and measurement, data and splits, parameter settings, analysis plan, time-stamped on OSF (Open Science Framework) or AsPredicted; label exploratory work | van Miltenburg et al. 2021 | [NAACL 2021](https://aclanthology.org/2021.naacl-main.51.pdf) [paper] |

Protocol for this project: pre-register Δ macro-AP ≥ 0.03 (or the step-1 downstream target) as primary; per atom paired bootstrap on Δ AP; Wilcoxon over 45 deltas plus bootstrap CI on the macro Δ; Holm-adjusted per-atom p-values and the Bonferroni replicability count; ≥3 seeds; a stopping rule for reference-set growth. Koehn 2004: at 300 sentences a 2–3% BLEU (bilingual evaluation understudy) gap is reliably detected and 100-sentence sets produce more false conclusions ([W04-3250](https://aclanthology.org/W04-3250.pdf)) [paper]; the analogous unit here is positives per atom, and 10 is below any of these regimes.

---

## 6. Labelling under a budget

**Discipline.** Active learning (query selection), guided learning (search for minority examples), repeated labelling under noisy oracles (Sheng, Provost & Ipeirotis 2008), and learning-curve extrapolation (power-law fits).

**Up front.** No fetched source compares re-asking an LLM vs labelling new items under a fixed budget for classification, and no learning curve indexed by positives per class exists for imbalanced binary text with small encoders.

### 6.1 When AL beats random and when it does not

| Study | Setting | Result | Source |
|---|---|---|---|
| Ein-Dor et al. EMNLP 2020 | BERT; binary; 10–15% positives; 100 seed + 5 × 50 | All AL strategies beat random by ~4–8 F1 (Wilcoxon + Bonferroni); no strategy consistently best | [2020.emnlp-main.638](https://aclanthology.org/2020.emnlp-main.638.pdf) [paper] |
| Schröder et al. ACL Findings 2022 | BERT; ≤525 labels | Best uncertainty strategy +0.9 to +4.7 accuracy over random; Breaking Ties proposed as default; query step 480–529 s vs 0.002 s random | [arXiv:2107.05687](https://arxiv.org/pdf/2107.05687) [paper] |
| Lowell et al. EMNLP 2019 | Transfer of AL-selected data to a different model | AL beat random (i.i.d., independent and identically distributed) sampling in 60.9% of same-model points but only 37.5% of transfer points; differences within ±0.02 accuracy | [arXiv:1807.04801](https://arxiv.org/pdf/1807.04801) [paper] |
| "Fragility of Active Learners" 2024 | 350 configurations × 3 runs, 7 pipelines | AL worse than random 51.82% of the time overall; RoBERTa end-to-end worse only 7.71% with ~1% relative gain | [arXiv:2403.15744](https://arxiv.org/pdf/2403.15744) [paper] |
| Karamcheti et al. ACL 2021 | VQA (visual question answering) | AL fails to beat random due to collective outliers | [arXiv:2107.02331](https://arxiv.org/abs/2107.02331) [paper] |
| Hakimi et al. 2026 | 278K comments; GPT-5.2 and Qwen3.5 annotators | LLM annotation at scale beat human-supervised classifiers at ~1/10 cost; "AL gave no reliable advantage over random sampling in the prefiltered pool" | [alphaXiv 2604.13899](https://www.alphaxiv.org/abs/2604.13899) [paper, no figures on page] |
| Yuan et al. EMNLP 2020 (ALPS) | Cold start | Entropy sampling weakest early on imbalanced PubMed: "entropy estimates are uninformative in early iterations" | [2020.emnlp-main.637](https://aclanthology.org/2020.emnlp-main.637.pdf) [paper] |

Reading for this setting: a fine-tuned encoder querying for itself on skewed binary labels is the favourable case (+1–8 points); cross-model transfer, non-transformer pipelines and cold start are where AL loses. Keep the query model and the student the same.

### 6.2 Imbalance: search for positives first

Attenberg & Provost 2010: at skews 20:1 to 200:1 "guided learning strongly dominates active learning"; at the most extreme skew random and uncertainty sampling "could not reliably find any minority examples in 10,000 draws"; at 999:1 ~30,000 labels buy 30 positives; guided learning and uncertainty sampling were equal per unit cost when a searched positive cost ~8× one label; a hybrid (search, then switch to uncertainty when the learning-curve slope flattens) was cheapest ([CeDER-09-07](https://archive.nyu.edu/bitstream/2451/28533/2/CeDER-09-07.Dec09.pdf)) [paper, tech report]. Guided learning was simulated by class-conditional sampling, not real search. Ein-Dor's keyword seeds had recall 0.08–0.48, and AL recovered recall afterwards. Retrieval-based candidate generation (embedding nearest neighbours of known positives) is near-free per candidate, so it is very likely to beat the 8:1 break-even.

### 6.3 Re-asking the LLM vs labelling new articles

Sheng, Provost & Ipeirotis 2008 (independent labellers): MV helps only if labeller accuracy p > 0.5; at p = 0.7, 1 → 3 labels raises label quality ~0.1; at p = 0.9, 3 → 11 labels adds little; at p = 0.6 repeated labelling beat new items, at p = 0.8 new items won; selecting items to relabel by combined label + model uncertainty gave 79.46% vs 73.65% for round-robin at p = 0.6 ([CPP-02-08](https://archive.nyu.edu/bitstream/2451/27818/2/CPP-02-08.pdf)) [paper]. Repeated LLM calls are correlated, so these thresholds are optimistic. Wang et al. 2021: routing the lowest-logit GPT-3 labels to humans beat random on most tasks (TREC 77% → 80% at $2.2) ([arXiv:2108.13487](https://arxiv.org/pdf/2108.13487)) [paper]. Pangakis & Wolken 2024: GPT-4 labelled each item 3× at temperature 0.7, ~85% fully consistent, consistent labels 19.4% more accurate, but training only on consistent labels changed BERT F1 by −0.004 ([arXiv:2406.17633](https://arxiv.org/pdf/2406.17633)) [paper]. Self-consistency gains (+3.9 to +17.9 points) are documented on reasoning benchmarks only ([arXiv:2203.11171](https://arxiv.org/abs/2203.11171)) [paper].

### 6.4 Learning-curve fits

Form: error(n) = a + b·n^(−c), a = irreducible error (includes mislabelled-data error per Hestness et al.), c ∈ (0,1]. Figueroa et al. 2012 fit with weighted nonlinear least squares from ≥5 points starting at ~80–100 samples and reached extrapolation RMSE (root mean squared error) < 0.01 with ~200 (range 80–560) samples on medical text ([PMC3307431](https://pmc.ncbi.nlm.nih.gov/articles/PMC3307431)) [paper]. Hestness et al. measured exponents far smaller than the theoretical −0.5 (word language model −0.066, machine translation −0.128, speech −0.299) ([arXiv:1712.00409](https://arxiv.org/pdf/1712.00409)) [paper]. Zhang et al. ICLR 2024: fine-tuning exponents β ≈ 0.087–0.15 for full fine-tuning, 0.015–0.081 for LoRA (low-rank adaptation)/prompt tuning ([arXiv:2402.17193](https://arxiv.org/pdf/2402.17193)) [paper]. Viering & Loog: curves are "surprisingly diverse", "no universal model can be identified" ([arXiv:2103.10948](https://arxiv.org/abs/2103.10948)) [paper]. For 1–5% atoms the effective sample size is the positive count, so expect much wider extrapolation error than Figueroa's. SetFit's one imbalanced dataset (AmazonCF, 10% positives) was still 18 MCC (Matthews correlation coefficient) points below full-data at 64 positives per class (61.9 vs 80.1) ([arXiv:2209.11055](https://arxiv.org/pdf/2209.11055)) [paper]: 5–100 positives per atom is not saturated.

### 6.5 Tools

small-text (PyPI 1.4.1, 2024-08-18; 2.0.0.dev4 2026-05-23; SetFit and transformers integrations; author is Schröder of the 2022 paper) is the fit ([repo](https://github.com/webis-de/small-text)). modAL's last release is 2023-06-01; ALiPy's 2021-07-28; baal 2.1.0 2025-06-24 ([PyPI](https://pypi.org/pypi/small-text/json)) [README].

---

## 7. CPU-fast students

**Discipline.** Knowledge distillation (static embeddings, distilled encoders), few-shot contrastive fine-tuning (SetFit), post-training quantisation (int8 ONNX/OpenVINO), and long-document and long-tailed multi-label classification.

**Up front.** No published source gives absolute per-article CPU latency in milliseconds for any candidate at news-article length on a named CPU. The one absolute datapoint is roberta-base int8 at 64.9 ms for 128 tokens on a 2-core m5.xlarge.

### 7.1 Candidate bodies

| Option | Params | Reported quality | Reported speed | Multi-label | Source type |
|---|---|---|---|---|---|
| TF-IDF + logistic regression | n/a | 70.8 avg over 14–15 classification sets | 108,434 samples/s, CPU unspecified | sklearn one-vs-rest | README ([model2vec results](https://github.com/MinishLab/model2vec/blob/main/results/README.md)) |
| fastText bigram | n/a | AG 92.5 vs VDCNN 91.3; Yelp Full 63.9 vs 64.7 | 1–10 s per training epoch | native one-vs-all | paper ([arXiv:1607.01759](https://arxiv.org/pdf/1607.01759)) |
| potion-base-8M + logreg or MLP | 7.5M | MTEB classification 70.34 vs all-MiniLM-L6-v2 69.25; frozen+logreg 78.0 / finetune 79.2 avg | 17,925 / 24,744 samples/s; 67 ms per 2,000 sentences | list-of-lists in `fit` | card/README ([card](https://huggingface.co/minishlab/potion-base-8M); [train README](https://github.com/MinishLab/model2vec/blob/main/model2vec/train/README.md)) |
| potion-base-32M | 32.3M | MTEB classification 71.70; 94.66% of MiniLM average | same speed as 8M per vendor | same | card ([card](https://huggingface.co/minishlab/potion-base-32M)) |
| static-retrieval-mrl-en-v1 | ~31M | NanoBEIR 0.5032 vs mpnet 0.5757 | 107,419 sentences/s on i7-13700K; 397× vs mpnet | via sklearn/SetFit head | blog ([HF blog](https://huggingface.co/blog/static-embeddings)) |
| SetFit on all-MiniLM-L6-v2 | 22M | 82.6 avg full-data; 60.3 at 8/class (MiniLM-L3) | 716 samples/s CPU; 1.3e9 FLOPs | one-vs-rest / multi-output / classifier-chain | paper + README ([arXiv:2209.11055](https://arxiv.org/pdf/2209.11055); [docs](https://huggingface.co/docs/setfit/en/how_to/multilabel)) |
| bge-small / gte-small / e5-small-v2 + head, int8 ONNX | 33.4M | MTEB classification 74.14 / 72.31 / 72.94 | int8 2.9×–6× vs fp32 on Intel; ~0.3–0.4 point loss | via head | card + blog ([bge card](https://huggingface.co/BAAI/bge-small-en-v1.5); [gte card](https://huggingface.co/thenlper/gte-small); [MS blog](https://medium.com/microsoftazure/faster-and-smaller-quantized-nlp-with-hugging-face-and-onnx-runtime-ec5525473bb7)) |
| bge-base frozen + logreg | 109M | 82.8 avg | 118 samples/s CPU | sklearn head | README ([model2vec results](https://github.com/MinishLab/model2vec/blob/main/results/README.md)) |
| ModernBERT-base | 149M | GLUE 88.4 | 148.1k tokens/s on RTX 4090; no CPU data | BCE head | paper ([arXiv:2412.13663](https://arxiv.org/pdf/2412.13663)) |

Note: MiniLM 6×384 is 5.3× faster than BERT-base with avg 79.6 vs 81.5 ([arXiv:2002.10957](https://arxiv.org/pdf/2002.10957)) [paper]. Scaling the one absolute datapoint (roberta-base int8, 64.9 ms, 128 tokens, 2 cores) by 5.3× suggests ~10–15 ms per 128-token chunk for a 22M encoder; a 512-token article in four chunks lands near 50 ms on 2 cores [sim: estimate]. Static bodies need no quantisation to hit the budget; the per-sentence cost of 0.03 ms (67 ms / 2,000) scales linearly with tokens.

### 7.2 Static embeddings vs small encoders: the quality gap

- model2vec's own benchmark: model2vec finetune 79.2 vs SetFit (all-MiniLM-L6-v2) 82.6 average, but per-dataset gaps reach >10 points on nuanced tasks (tweet_sentiment_extraction 62.65 vs 75.15; sst5 37.95 vs 42.31) ([model2vec results](https://github.com/MinishLab/model2vec/blob/main/results/README.md)) [README].
- sentence-transformers v3.2 release notes: static models give "50x-500x speedups at ~10%-20% performance cost" ([v3.2.0](https://github.com/UKPLab/sentence-transformers/releases/tag/v3.2.0)) [README].
- No peer-reviewed evaluation of any potion model exists; all numbers are the vendor's.
- Keith et al. 2020 found bag-of-words logistic regression (F1 0.71) beat a frozen Longformer embedding probe (F1 0.60) on long news ([arXiv:2010.04706](https://arxiv.org/pdf/2010.04706)) [paper]: the frozen-embedding plateau the prior attempts hit has precedent on long news.

### 7.3 Multi-label with rare classes

| Issue | Finding | Source |
|---|---|---|
| Per-label thresholds overfit rare labels | SCut macro-F 8.27 vs smoothed-F 12.69 on Wiki10-31K; F is zero whenever tp = 0 so very low thresholds look "better" | [Lin & Lin CIKM 2023](https://www.csie.ntu.edu.tw/~cjlin/papers/thresholding/smooth_acm.pdf) [paper] |
| Long-tailed multi-label loss | Distribution-balanced loss beats standard losses on Reuters-21578 and PubMed; resampling ineffective under label dependency | [arXiv:2109.04712](https://arxiv.org/abs/2109.04712) [paper, abstract] |
| Focal / asymmetric loss | Vision results only; model2vec v0.10.0 added focal loss and sample weights | [arXiv:1708.02002](https://arxiv.org/abs/1708.02002); [arXiv:2009.14119](https://arxiv.org/abs/2009.14119) [paper]; [changelog](https://data.safetycli.com/changelogs/model2vec) [README] |
| Long documents | Chunk ≤512 tokens, encode, max-pool: MIMIC-III 56.1 → 69.5 micro-F1, ECtHR 73.5 → 81.1, 20 News 86.1 → 86.3; start with overlapping ~128-token segments | [arXiv:2204.06683](https://arxiv.org/pdf/2204.06683) [paper] |
| SetFit pair sampling | Balances positive vs negative pairs, not classes; a label with 5 positives has ≤10 unique positive pairs; AmazonCF (10% positive) had the largest variance at 8/class (±11.8) | [arXiv:2209.11055](https://arxiv.org/pdf/2209.11055) [paper]; [sampling guide](https://huggingface.co/docs/setfit/en/conceptual_guides/sampling_strategies) [README] |
| Frozen vs fine-tuned learning curve | SetFit student vs baseline student gap 24.8 / 25.1 / 8.9 points at 8/class, "on par at N=1K" | [arXiv:2209.11055](https://arxiv.org/pdf/2209.11055) [paper] |
| Soft targets from the LLM | No controlled study of LLM log-prob soft labels vs argmax for a small text classifier; classical KD support only | [arXiv:1503.02531](https://arxiv.org/pdf/1503.02531) [paper] |

Operational pattern from the POLECAT event coder: one DistilBERT binary model per event class trained on 8–464 positives at forced 1:1 balance; transformers "over-generalize and over-classify" so only scores above the 90th percentile were reported; split-sample validation on tiny classes likely overstated accuracy ([arXiv:2304.01331](https://arxiv.org/pdf/2304.01331)) [paper].

---

## 8. End-to-end case studies

**Up front.** No case study combines long news, ~45 rare binary labels, multiple prompt wordings and CPU latency figures. The three below are the closest on the dimensions that matter: rare classes with weak sources (DryBell), LLM prompts as sources (Smith et al.), and LLM labels into a small student on rare social-science classes (Pangakis & Wolken).

### 8.1 Snorkel DryBell at Google (SIGMOD 2019) [paper]

- Setup: 10 and 8 labelling functions over 684K and 6.5M unlabelled documents; conditionally independent label model; logistic regression student in TFX; non-servable features used only in LFs. Test positive rates 0.86% and 1.48% ([arXiv:1812.00417](https://arxiv.org/pdf/1812.00417v2)).
- Results (F1 relative to a classifier trained on the hand-labelled dev set = 100): topic end model 117.5 (recall 132.1); product 105.2; within 4.6 and 5.1 F1 points of models trained on 175K and 50K hand labels. Learned LF weights vs equal weights: 117.5 vs 109.0 and 105.2 vs 103.24.
- Reported pitfalls: a label-definition change depreciated a large hand-labelling investment and old positives slightly reduced F1; the label model alone was not deployable; conditional independence named as a limitation; estimated LF accuracies were used to find and remove bad sources.
- Transfer: the student generalised beyond its sources (recall 132% of the hand-label baseline), so the student is not capped by teacher coverage. Reference sets were 11K–14K hand-labelled documents, far above anything here.

### 8.2 Smith et al. 2022, prompts as labelling functions [paper, arXiv]

- Setup: T0++ (11B) and InstructGPT Ada/Babbage/Curie; yes/no prompts mapped to vote or abstain; contextual calibration; FlyingSquid; RoBERTa student; WRENCH YouTube (10 prompts), SMS (73), Spouse (9, ~8% positive) ([arXiv:2205.02318](https://arxiv.org/pdf/2205.02318)).
- Results (mean of 6 seeds): T0++ prompted weak supervision 92.0 acc / 91.8 F1 / 62.9 F1 vs single-prompt zero-shot student 58.7 / 83.2 / 41.5 vs hand-written LFs 94.9 / 92.4 / 37.9. Spouse: +25 F1 over hand-written rules.
- Reported pitfalls: calibration added +18 F1 on Spouse but traded accuracy for coverage and was inconsistent per prompt; Babbage prompts "strongly correlated", limiting ensemble gains; results heavily model-dependent; prompts hand-tuned per model and dataset; no ablation on prompt count; no MV-vs-label-model comparison.

### 8.3 Pangakis & Wolken 2024, GPT-4 → BERT on 14 rare binary tasks [paper, workshop]

- Setup: 14 binary tasks (headlines, tweets, speeches, manifestos), mean positive rate 16.2%, minimum 0.04%; 1,000 GPT-4 labels per task; students BERT, RoBERTa, DistilBERT; 1,000 human-labelled test per task ([arXiv:2406.17633](https://arxiv.org/pdf/2406.17633)).
- Results (median): GPT-4 few-shot F1 0.59 / precision 0.51 / recall 0.80; BERT on 1,000 GPT labels F1 0.59 / P 0.50 / R 0.74; BERT on 1,000 human labels F1 0.62 / P 0.71 / R 0.54; BERT on 250 human labels F1 0.34.
- Reported pitfalls: students scored F1 = 0.00 on several rare classes (Race, Religion, one hate category where GPT-4 itself scored 0.06); GPT-trained students magnify LLM bias; consistency filtering changed F1 by −0.004; GPT-4 re-run 6 months later shifted F1 by +0.022; code in supplementary material only.
- Transfer: recall-heavy, precision-poor students are the expected failure mode when the teacher is recall-heavy; rare classes can fail outright.

### 8.4 Supporting cases (partial)

- Keith et al. 2020 (EPU re-audit): bag-of-words logistic regression F1 0.71 vs keyword rule 0.64 on human labels; classifier index correlated 0.38 with the keyword index, showing the labeller choice changes the downstream measurement ([arXiv:2010.04706](https://arxiv.org/pdf/2010.04706)) [paper].
- Luccioli et al. 2025 (Federal Reserve): gemma-3-27b teacher; SVM (support vector machine), LDA (linear discriminant analysis), RF (random forest) and XGBoost students on all-MiniLM-L6-v2 embeddings; uncertainty sampling needed 58–81% fewer LLM labels to hit accuracy thresholds; inference per batch of 32: GBDT (gradient-boosted decision trees) 0.08 ms, SVM 0.55 ms, DistilBERT (on GPU) 2.80 ms; no human gold, teacher treated as truth ([arXiv:2511.11574](https://arxiv.org/html/2511.11574v1)) [paper, submitted]. Only source with latency in the target band, but no ground truth.
- Wang et al. 2021: GPT-3 labels into RoBERTa-large at 50–96% lower cost than human labels; authors judged GPT-3 "not reliable enough" for high-stakes labelling; costs exclude prompt design ([arXiv:2108.13487](https://arxiv.org/pdf/2108.13487)) [paper].

---

## Evidence table

| Claim | Source | Reported number | Source type |
|---|---|---|---|
| Label-model advantage over MV is small at low label density | [Snorkel VLDB 2017](https://arxiv.org/pdf/1711.10160) | 0.1–7.0 points at densities 1.2–2.3; optimiser chose MV for Chem | paper |
| MeTaL beats MV with correlated multi-task sources | [arXiv:1810.02840](https://arxiv.org/abs/1810.02840) | +6.8 accuracy average | paper |
| FlyingSquid needs ≥3 conditionally independent sources per estimate | [arXiv:2002.11955](https://arxiv.org/pdf/2002.11955) | Error O(√(m/n)) | paper |
| Prompted weak supervision beats zero-shot | [Smith et al. 2022](https://arxiv.org/abs/2205.02318) | 19.5% average error reduction; 9–73 prompts | paper |
| MV and DS best among label models | [BoxWRENCH](https://arxiv.org/html/2501.07727v2) | Claude9 F1 MV 0.582, DS 0.572, FlyingSquid 0.352 | paper |
| CI aggregators miscalibrated under dependent LLM judges | [arXiv:2601.22336](https://arxiv.org/pdf/2601.22336) | Ising 0.90 vs CI-WMV 0.82 (relevance) | paper |
| MV-initialised DS collapses on sparse/imbalanced data | [arXiv:1909.12325](https://arxiv.org/pdf/1909.12325) | Nursery p = 0.5: 66.48% error vs MV 4.83% | paper |
| Paraphrased prompts disagree substantially | [arXiv:2604.16413](https://arxiv.org/pdf/2604.16413) | GPT-4o mini TREC accuracy 0.546–0.808 over 20 prompts | paper |
| Semantics-preserving rewrites shift annotations | [arXiv:2601.02370](https://arxiv.org/pdf/2601.02370) | 8.38–28.10 percentage points | paper |
| LLMs insensitive to negation | [2023.starsem-1.10](https://aclanthology.org/2023.starsem-1.10.pdf) | InstructGPT MoNLI 0.470 (below chance) | paper |
| Negation sensitivity grows with model size | [arXiv:2503.22395](https://arxiv.org/html/2503.22395v2) | 37.85% to 94.81%; Spearman 0.867 | paper |
| Confident learning detects label errors | [arXiv:1911.00068](https://web3.arxiv.org/pdf/1911.00068v6) | CIFAR-10 20% noise: detection F1 75%; test acc 91.1% vs 78.4% | paper |
| Multi-label confident learning ranks errors | [arXiv:2211.13895](https://arxiv.org/pdf/2211.13895) | CelebA (celebrity-face attribute dataset) 67/100 top-ranked mislabelled vs 15/100 random | paper |
| Raw count vs ACC error | [LeQua 2022](https://ceur-ws.org/Vol-3180/paper-146.pdf) | T1A RAE: CC 1.084, ACC 0.170, SLD 0.114 | paper |
| Surrogate labels in regression break coverage | [Egami et al. 2023](https://arxiv.org/html/2306.04746v3) | 40% coverage of nominal 95% CI at 90% accuracy | paper |
| PPI reduces gold labels needed | [Angelopoulos et al. 2023](https://arxiv.org/pdf/2301.09633) | 21 vs 35; 316 vs 799 | paper |
| EPU machine vs human index correlation | [Baker, Bloom & Davis 2016](https://users.ssc.wisc.edu/~mchinn/bakerbloomdavis_QJE2016.pdf) | 0.86 quarterly, 0.93 annual; 12,009 articles audited | paper |
| Google Flu Trends drift | [Lazer et al. 2014](https://cdanfort.w3.uvm.edu/csc-reading-group/lazer-flu-science-2014.pdf) | 100 of 108 weeks over; MAE 0.486 vs 0.311 lagged CDC | paper |
| GDELT vs hand-coded conflict | [Hammond & Weidmann 2014](https://journals.sagepub.com/doi/10.1177/2053168014539924) | r = 0.64 (ACLED), 0.33 (GED) | paper |
| OFAT recommended first for ABM sensitivity | [ten Broeke et al. 2016](https://www.jasss.org/19/1/5/5.pdf) | OFAT 1,650 runs vs Sobol 17,000; replicate variance 0.88% | paper |
| Precision needs zero weight on predicted negatives | [Sawade et al. 2010](https://papers.NeurIPS.cc/paper_files/paper/2010/file/d7a728a67d909e714c0774e22cb806f2-Paper.pdf) | <150 labels for recall, ~100 for precision matched 800 passive | paper |
| Stratified evaluation saves labels at extreme imbalance | [OASIS, Marchant & Rubinstein 2017](https://arxiv.org/pdf/1703.00617) | Up to 83% fewer labels at ~1:3000 | paper |
| Rare-class F1 with ~100 labels via importance sampling | [Poms et al. 2021](https://arxiv.org/pdf/2109.05720) | F1 variance 0.005 at ≤0.1% positives | paper |
| Sample size for ±0.10 at p = 0.5 | [MedCalc](https://www.medcalc.org/manual/sample-size-CI-precisionrecall.php) | 97 | this report's arithmetic (formula from source) |
| Random articles for 93 positives at 2% | — | 4,650 | this report's arithmetic |
| Positives per atom to detect Δ macro-AP 0.03 at 80% power, 45 independent atoms | — | ~29 per atom, ~1,470 articles | this report's simulation |
| Minimum detectable Δ macro-AP on 486 articles | — | ≈ 0.052 | this report's simulation |
| Bootstrap and cross-validation AP intervals under-cover on small data | [Boyd et al. 2013](https://asset.library.wisc.edu/1711.dl/OUTUDKUSNU53G9C/R/file-7ea2f.pdf) | Binomial/logit intervals recommended | paper |
| Krippendorff α reliability sample size | [ATLAS.ti manual](https://doc.atlasti.com/ManualWin/ICA/ICASampleSizeAndDecisionRules.html) | 139 codings for α ≥ 0.800 at pc = 0.25 | README-blog-card |
| GPT-4 validation needs 250–1,250 human labels | [Pangakis et al. 2023](https://arxiv.org/pdf/2306.00176) | 9 of 27 tasks had P or R < 0.5 | paper |
| EPU annotation reliability | [Keith et al. 2020](https://arxiv.org/pdf/2010.04706) | α 0.60 (BBD), 0.21–0.27 (re-annotation); BOW logreg F1 0.71 vs Longformer probe 0.60 | paper |
| Resampled t-test unsafe; use McNemar or 5×2 cross-validation | [Dietterich 1998](https://web.engr.oregonstate.edu/~tgd/publications/dietterich-approximate-statistical-tests-nc1998.pdf) | — | paper |
| Wilcoxon across datasets; t-test inappropriate | [Demšar 2006](https://www.jmlr.org/papers/volume7/demsar06a/demsar06a.pdf) | — | paper |
| Replicability count beats naive counting | [Dror et al. 2017](https://aclanthology.org/Q17-1033.pdf) | Sentiment 10 naive vs 6 Bonferroni of 12 | paper |
| Small test sets underpowered | [Card et al. 2020](https://aclanthology.org/2020.emnlp-main.745.pdf) | WNLI (n = 147) MDE 5.26 points; ~46% of GLUE comparisons powered | paper |
| Data bootstrap dominates variance | [Bouthillier et al. 2021](https://arxiv.org/pdf/2103.03098v1) | Init < 50% of bootstrap variance | paper |
| AL beats random on skewed binary with BERT | [Ein-Dor et al. 2020](https://aclanthology.org/2020.emnlp-main.638.pdf) | +4–8 F1 | paper |
| AL beats random by small margins | [Schröder et al. 2022](https://arxiv.org/pdf/2107.05687) | +0.9 to +4.7 accuracy | paper |
| AL transfers poorly across models | [Lowell et al. 2019](https://arxiv.org/pdf/1807.04801) | 37.5% of transfer points beat random | paper |
| AL worse than random about half the time across configs | [arXiv:2403.15744](https://arxiv.org/pdf/2403.15744) | 51.82% | paper |
| Guided search dominates AL at high skew | [Attenberg & Provost 2010](https://archive.nyu.edu/bitstream/2451/28533/2/CeDER-09-07.Dec09.pdf) | Break-even at ~8× label cost per found positive | paper (tech report) |
| Repeated labelling pays only at moderate noise | [Sheng et al. 2008](https://archive.nyu.edu/bitstream/2451/27818/2/CPP-02-08.pdf) | LMU 79.46% vs round-robin 73.65% at p = 0.6 | paper |
| Consistency filtering did not help the student | [Pangakis & Wolken 2024](https://arxiv.org/pdf/2406.17633) | BERT F1 −0.004 | paper |
| Learning-curve extrapolation accuracy | [Figueroa et al. 2012](https://pmc.ncbi.nlm.nih.gov/articles/PMC3307431) | RMSE < 0.01 with ~200 samples | paper |
| Fine-tuning data exponent | [Zhang et al. 2024](https://arxiv.org/pdf/2402.17193) | β 0.087–0.15 | paper |
| Soft targets beat hard labels | [Hinton et al. 2015](https://arxiv.org/pdf/1503.02531) | MNIST 146 → 74 errors | paper |
| GPT-3 labels cheaper than human for same student | [Wang et al. 2021](https://arxiv.org/pdf/2108.13487) | 50–96% cheaper; top-10% confident labels 90–95% accurate | paper |
| SetFit few-shot | [arXiv:2209.11055](https://arxiv.org/pdf/2209.11055) | 62.3 at 8/class; AmazonCF 61.9 at 64/class vs 80.1 full | paper |
| potion-base-8M quality | [model card](https://huggingface.co/minishlab/potion-base-8M) | 91.96% of all-MiniLM-L6-v2; MTEB classification 70.34 vs 69.25 | README-blog-card |
| model2vec classifier speed | [train README](https://github.com/MinishLab/model2vec/blob/main/model2vec/train/README.md) | 67 ms per 2,000 instances CPU | README-blog-card |
| model2vec vs SetFit quality | [results README](https://github.com/MinishLab/model2vec/blob/main/results/README.md) | 79.2 vs 82.6 avg; 24,744 vs 716 samples/s | README-blog-card |
| Static embeddings CPU speedup | [HF blog](https://huggingface.co/blog/static-embeddings) | 397× vs mpnet on i7-13700K | README-blog-card |
| MiniLM speed/quality | [arXiv:2002.10957](https://arxiv.org/pdf/2002.10957) | 6×384: 5.3× faster, avg 79.6 vs 81.5 | paper |
| int8 ONNX speedup | [Optimum blog](https://huggingface.co/blog/optimum-inference) | roberta-base 117.6 → 64.9 ms at 128 tokens, 2 cores; F1 82.15 → 81.83 | README-blog-card |
| Per-label thresholds overfit rare labels | [Lin & Lin 2023](https://www.csie.ntu.edu.tw/~cjlin/papers/thresholding/smooth_acm.pdf) | Wiki10-31K macro-F 8.27 → 12.69 | paper |
| Chunk + max-pool beats truncation | [Dai et al. 2022](https://arxiv.org/pdf/2204.06683) | MIMIC-III 56.1 → 69.5; 20 News 86.1 → 86.3 | paper |
| DryBell rare-class weak supervision | [arXiv:1812.00417](https://arxiv.org/pdf/1812.00417v2) | F1 117.5 relative; within 4.6 F1 of 175K hand labels; 0.86% positive | paper |
| GPT-4 → BERT on rare classes | [Pangakis & Wolken 2024](https://arxiv.org/pdf/2406.17633) | Median F1 0.59 / P 0.50 / R 0.74; several F1 = 0.00 | paper |
| Embedding + GBDT student latency | [Luccioli et al. 2025](https://arxiv.org/html/2511.11574v1) | 0.08 ms per batch of 32 | paper (submitted) |
| snorkel package frozen | [releases](https://github.com/snorkel-team/snorkel/releases/tag/v0.10.0) | Last release 2023-02-27 | README-blog-card |

---

## Known pitfalls

1. Treating 2–4 paraphrases of one LLM as independent raters inflates posterior confidence and estimated accuracies; shared failure modes are counted as separate confirmations ([arXiv:2601.22336](https://arxiv.org/pdf/2601.22336)).
2. MV-initialised Dawid-Skene EM can collapse on sparse, imbalanced data (66% error vs 5% for MV) ([arXiv:1909.12325](https://arxiv.org/pdf/1909.12325)).
3. Majority vote over many prompts raises agreement but can "reinforce consistent but incorrect predictions" ([arXiv:2604.16413](https://arxiv.org/pdf/2604.16413)).
4. The reversed wording is not an independent check because LLMs often ignore negation ([2023.starsem-1.10](https://aclanthology.org/2023.starsem-1.10.pdf)).
5. Scoring the student against the LLM's positives cannot distinguish student error from labeller error; only human labels can ([arXiv:2306.00176](https://arxiv.org/pdf/2306.00176)).
6. Labelling only predicted positives gives unbiased precision but a recall biased to 1.0 and an F-measure that inherits the bias ([Sawade et al. 2010](https://papers.NeurIPS.cc/paper_files/paper/2010/file/d7a728a67d909e714c0774e22cb806f2-Paper.pdf)).
7. Bootstrap and cross-validation AP intervals under-cover with ~10 positives ([Boyd et al. 2013](https://asset.library.wisc.edu/1711.dl/OUTUDKUSNU53G9C/R/file-7ea2f.pdf)).
8. Tuning 45 free per-atom thresholds on 5–100 positives overfits because F is zero whenever tp = 0 ([Lin & Lin 2023](https://www.csie.ntu.edu.tw/~cjlin/papers/thresholding/smooth_acm.pdf)).
9. Confident learning's positive-class threshold is the mean probability over items labelled positive, so with 5–100 positives it is noisy; no paper tests this regime ([arXiv:1911.00068](https://web3.arxiv.org/pdf/1911.00068v6)).
10. ACC's bias cancellation needs TPR/FPR to transfer from validation to each day; topic drift breaks it and the correction amplifies raw-count variance by ~1/(TPR − FPR)² ([QuaPy paper](https://arxiv.org/pdf/2106.11057)).
11. Plugging predicted labels into downstream estimation without correction gives biased estimates and CIs with 40% coverage at 90% surrogate accuracy ([Egami et al. 2023](https://arxiv.org/html/2306.04746v3)).
12. Text-derived indices drift when the generator changes; Google Flu Trends overshot 100 of 108 weeks after 86 algorithm changes in two months ([Lazer et al. 2014](https://cdanfort.w3.uvm.edu/csc-reading-group/lazer-flu-science-2014.pdf)).
13. A GPT-4 re-run six months later shifted F1 by +0.022 on the same data ([arXiv:2406.17633](https://arxiv.org/pdf/2406.17633)).
14. Students trained on recall-heavy LLM labels inherit low precision and can score F1 = 0 on the rarest classes ([arXiv:2406.17633](https://arxiv.org/pdf/2406.17633)).
15. Changing an atom's definition can depreciate the labelled set and old positives can reduce F1 ([arXiv:1812.00417](https://arxiv.org/pdf/1812.00417v2)).
16. AL-selected data transfers poorly to a different student; keep query model and student the same ([arXiv:1807.04801](https://arxiv.org/pdf/1807.04801)).
17. Uncertainty sampling at cold start on imbalanced data is uninformative ([2020.emnlp-main.637](https://aclanthology.org/2020.emnlp-main.637.pdf)).
18. Random and uncertainty sampling can fail to find any positives at extreme skew; search first ([CeDER-09-07](https://archive.nyu.edu/bitstream/2451/28533/2/CeDER-09-07.Dec09.pdf)).
19. Re-asking the LLM when its per-atom accuracy is already ~0.9 wastes budget ([CPP-02-08](https://archive.nyu.edu/bitstream/2451/27818/2/CPP-02-08.pdf)).
20. SetFit's sampler balances pair types, not classes; a label with 5 positives yields ≤10 unique positive pairs ([sampling guide](https://huggingface.co/docs/setfit/en/conceptual_guides/sampling_strategies)).
21. all-MiniLM-L6-v2 truncates at 256 word pieces and bge/gte/e5-small at 512; news articles exceed both, so chunk regardless of body ([all-MiniLM-L6-v2 card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)).
22. Transformers "over-generalize and over-classify" on tiny rare classes, and split-sample validation on them overstates accuracy ([arXiv:2304.01331](https://arxiv.org/pdf/2304.01331)).
23. The resampled paired t-test and counting significant wins across atoms are both statistically unsafe ([Dietterich 1998](https://web.engr.oregonstate.edu/~tgd/publications/dietterich-approximate-statistical-tests-nc1998.pdf); [Demšar 2006](https://www.jmlr.org/papers/volume7/demsar06a/demsar06a.pdf)).
24. Query-time compute for AL on transformers (480–529 s per step vs 0.002 s random) can cancel the label savings ([arXiv:2107.05687](https://arxiv.org/pdf/2107.05687)).
25. The `snorkel` and WRENCH packages are effectively frozen; do not build on them as maintained dependencies ([snorkel releases](https://github.com/snorkel-team/snorkel/releases/tag/v0.10.0)).

---

## What is unproven or contested

1. No paper compares a label model over k ≤ 5 paraphrased prompts vs MV over the same prompts vs the best single prompt; the exact comparison this project needs does not exist.
2. No paper measures the pairwise error correlation of paraphrased prompts to one LLM, nor bounds Dawid-Skene accuracy over-estimation as a function of that correlation.
3. No paper studies label-model identifiability or performance with ≤5 sources at 1–5% base rates.
4. No paper evaluates a negated/reversed prompt as a weak-supervision source, or compares "reversed prompt as rater" vs "as consistency filter".
5. No paper evaluates confident learning or its multi-label variant at 1–5% positive rates with <100 positives per class.
6. No paper runs classifier labels through an agent-based model and reports output error as a function of classifier TPR/FPR; the classifier-to-ABM link is unaddressed.
7. No quantification paper reports error at 1–5% prevalence with ~250-article days; LeQua spreads prevalence over [0,1].
8. No closed-form sample size exists for stratified recall estimation; variance depends on stratum false-negative rates known only after a pilot.
9. The power calculation for Δ macro-AP = 0.03 is this report's binormal simulation (ρ = 0.7, all atoms shifting equally, cross-atom independence); no published paper quantifies paired-bootstrap power for AP on rare classes.
10. No fetched source compares re-asking the LLM vs labelling new articles under a fixed budget for classification; Sheng et al.'s thresholds assume independent labellers.
11. No learning curve indexed by positives per class exists for imbalanced binary text classification with small encoders; the e5-small fine-tuning curve is unpublished.
12. Whether a student can beat its LLM teacher on ground truth is shown only in Wang et al. 2021 (figures and a theorem) and marginally in Ding et al. 2023 (two of four tasks, <1 point); it is not a design assumption.
13. No controlled study compares LLM log-probability soft labels vs argmax labels for a small text classifier.
14. No peer-reviewed evaluation of any model2vec/potion model exists; all quality and speed numbers are the vendor's, and the CPU for the throughput table is unspecified.
15. No published per-article CPU latency in milliseconds exists for any 22–33M-parameter encoder at 512 tokens on a named CPU; the 10–15 ms per 128-token chunk figure is this report's extrapolation from one roberta-base datapoint.
16. No text-domain paper gives numbers for focal or asymmetric loss on multi-label text at 1–5% base rates.
17. Guided-learning dominance (Attenberg & Provost) was simulated with perfect class-conditional sampling, not real retrieval; real retrieval returns biased positives.
18. The Krippendorff sample-size table was only available through a secondary manual; the "five chance agreements per code" arithmetic for a 2% value (~12,500 paired codings) is this report's, not a quoted figure.
19. Negation-insensitivity benchmarks are NLI/cloze tasks on short inputs; no benchmark covers yes/no classification prompts over long documents with 2025–2026 local models.
20. Hakimi et al. 2026 ("AL gave no reliable advantage over random") was read from an abstract page without figures; title differs between versions.
21. Alfred's label models and the Osprey (Intel, DEEM 2019) numbers could not be verified; the "Logical constraints in weak supervision" and "ConsistentLLM" references in the brief did not resolve to papers.
22. Whether the 35–37% recall plateau is a label ceiling or a student ceiling is a hypothesis this report draws from the pattern across six architectures; only the human reference set (pipeline steps 3–4) can confirm it.
