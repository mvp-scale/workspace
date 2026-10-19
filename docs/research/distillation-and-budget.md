# Distilling the news teacher into CPU students, and spending the label budget

Written 2026-10-18. Read-only desk research: nothing was installed, trained or sent anywhere. Every claim from outside links to its source. Where a source gives no number, this says so. Lines marked **(our reading)** are inference, not something a source states.

**Our case.** A local LLM teacher answers yes/no to 44 news "atoms" (5-100 positives each, about 2,300 labelled stories). The students run on CPU only, in milliseconds. What we have measured:

| Student | Speed | Result |
|---|---|---|
| Frozen potion-base-32M + logistic heads | ~1 ms/story | baseline |
| Frozen e5-small | 50-160 ms/story | — |
| Jury of frozen heads | — | small gain |
| e5-small fine-tuned multi-task | — | recall 0.17 / 0.25 / 0.34 at 25 / 50 / 100% of the data, still rising |

Labelling costs about 5,000 stories per GPU-hour for each 32-question battery.

---

## 1. Distilling an LLM classifier into a small CPU student

### 1a. Soft-label knowledge distillation (the general idea)

- **Method in plain words.** The student is trained on the teacher's probabilities ("soft targets", for example P(yes)=0.7), not just the 0/1 answer. The teacher's uncertainty carries information that a hard label throws away.
- **Evidence.** Hinton, Vinyals and Dean, *Distilling the Knowledge in a Neural Network*, §6 "Soft Targets as Regularizers" ([arXiv:1503.02531](https://arxiv.org/abs/1503.02531)). They trained a speech model on only 3% of the data:
  - hard targets: 44.5% test frame accuracy, with early stopping needed to avoid overfitting;
  - soft targets: 57.0%, with no early stopping;
  - the baseline trained on all the data: 58.9%.

  This is the paper's Table 5, as reported in a search summary of the PDF ([pdf](https://arxiv.org/pdf/1503.02531)).
- **Evidence for text.** Tang et al. distilled BERT into a one-layer BiLSTM. They report results "comparable" to ELMo with about 100x fewer parameters and about 15x less inference time ([arXiv:1903.12136](https://arxiv.org/abs/1903.12136)).
- **Fit to us (our reading).** Jev-class teachers already return probabilities (the noul = P(yes) answer type), so soft labels cost nothing extra. Any head trained with binary cross-entropy can take a float target in [0,1]. That covers sklearn `LogisticRegression` (only via sample-weight tricks) and any torch head.
- **Pitfalls.**
  - The model2vec classifier trainer documents only hard labels (see 1c).
  - SetFit's `DistillationTrainer` distils through sentence-pair similarity, not per-label soft targets (see 1b).
  - Soft targets help only if the teacher is calibrated. Check its reliability curve before relying on them.

### 1b. SetFit (few-shot sentence-transformer fine-tuning)

- **Method.**
  1. Contrastive fine-tuning of a sentence-transformer body on pairs built from the labelled examples (same class vs different class).
  2. A classification head trained on the resulting embeddings.
- **API.**
  - `SetFitModel.from_pretrained(...)`, then `Trainer(model, args=TrainingArguments(...), train_dataset=...)`.
  - **Multi-label:** `multi_target_strategy="one-vs-rest"` (or a differentiable head with `head_params={"out_features": n}`) ([multilabel docs](https://github.com/huggingface/setfit/blob/main/docs/source/en/how_to/multilabel.mdx), [notebook](https://github.com/huggingface/setfit/blob/main/notebooks/text-classification_multilabel.ipynb)).
  - **Distillation:** `DistillationTrainer(teacher_model=..., student_model=..., train_dataset=<unlabelled text>)` ([knowledge distillation how-to](https://github.com/huggingface/setfit/blob/main/docs/source/en/how_to/knowledge_distillation.mdx)).
  - **ONNX:** `setfit.exporters.onnx.export_onnx(body, head, ...)` ([ONNX notebook](https://github.com/huggingface/setfit/blob/main/notebooks/onnx_model_export.ipynb)).
- **Evidence.**
  - The paper says SetFit gets results "comparable" to PEFT and PET and is "an order of magnitude faster to train" ([arXiv:2209.11055](https://arxiv.org/abs/2209.11055)).
  - The README says 8 labelled examples per class on Customer Reviews compete with RoBERTa-large fine-tuned on the full 3k ([README](https://github.com/huggingface/setfit)).
  - **CPU latency:** a bge-small SetFit model at batch size 1 on Intel Xeon ran at 15.69 ms in fp32 and 4.55 ms in int8 (Optimum Intel), with accuracy going from 88.4% to 88.1% ([HF blog](https://huggingface.co/blog/setfit-optimum-intel)).
  - In MinishLab's 26-dataset comparison, SetFit averaged 74.7 weighted F1 at 1,010 samples/s, versus model2vec+logreg at 76.3 ([model2vec results](https://github.com/MinishLab/model2vec/blob/main/results/README.md)).
- **Maintenance and licence.** Apache-2.0. Releases 1.1.2 (Apr 2025), 1.1.3 (Aug 2025), 1.2.0 (4 Sep 2026) ([PyPI](https://pypi.org/project/setfit/#history)).
- **Fit to us (our reading).** SetFit is built for 8-64 examples per class. We already have 2,300 stories and 44 labels, and pair generation grows quickly. The docs themselves warn that distillation steps grow "exponentially" with unlabelled examples and advise a low `max_steps` ([how-to](https://github.com/huggingface/setfit/blob/main/docs/source/en/how_to/knowledge_distillation.mdx)). The body is still a transformer, so latency stays in the e5-small class unless it is int8 ONNX with short inputs. Its main use for us is as a **cold-start labeller for new atoms** (very few positives), not as the production student.

### 1c. model2vec: distillation, classifier fine-tuning, tokenlearn

- **Method.**
  - `distill()` turns any sentence transformer into a static lookup table. Each token gets its output embedding from the teacher, then PCA and weighting are applied. No dataset is needed, and it takes "~30 seconds on a CPU" ([README](https://github.com/MinishLab/model2vec)).
  - The classifier trainer (`model2vec.train`) fine-tunes **both the static embeddings and an MLP head** end to end. `freeze=True` keeps the embeddings fixed ([train README](https://github.com/MinishLab/model2vec/blob/main/model2vec/train/README.md)).
- **API.**
  - Distil: `from model2vec.distill import distill; m = distill(model_name=..., pca_dims=256, vocabulary=...)`. A custom vocabulary from our corpus is supported ([recipe tutorial](https://github.com/minishlab/model2vec/blob/main/tutorials/recipe_search.ipynb)).
  - Train a classifier: `StaticModelForClassification.from_pretrained(model_name="minishlab/potion-base-32M").fit(X, y)`. Multi-label works by passing lists of labels.
  - Useful `fit` options:

    | Option | Default / effect |
    |---|---|
    | `class_weight` | per-class weighting |
    | `focal_gamma` | focal loss, for rare positives |
    | `token_dropout` | regularisation |
    | `early_stopping_patience` | 5 |
    | `n_layers=0` | gives a linear head |
    | `threshold=` | set at predict time |

  - Export: `to_pipeline()` gives a sklearn pipeline that runs without torch and loads in about 30 ms ([train README](https://github.com/MinishLab/model2vec/blob/main/model2vec/train/README.md)).
- **Evidence.**
  - **MinishLab's 26-dataset average weighted F1:**

    | Model | Avg weighted F1 | Samples/s |
    |---|---|---|
    | tfidf | 72.9 | — |
    | fasttext | 68.9 | — |
    | model2vec + logreg | 76.3 | 32,869 |
    | model2vec full fine-tune | 76.3 | 81,018 |
    | SetFit | 74.7 | 1,010 |
    | MiniLM full fine-tune | 77.1 | 274 |

    Full fine-tuning of model2vec beat logreg on 17 of the 26 datasets. Hardware is not stated ([results](https://github.com/MinishLab/model2vec/blob/main/results/README.md)).
  - go_emotions, multi-label: macro F1 0.439 at threshold 0.3.
  - 2,000 texts infer in 66 ms on CPU ([train README](https://github.com/MinishLab/model2vec/blob/main/model2vec/train/README.md)).
  - **MTEB:** potion-base-32M scores 52.13 average and 71.70 on classification, against all-MiniLM-L6-v2 at 55.93 / 69.25 ([model card](https://huggingface.co/minishlab/potion-base-32M)).
- **Soft labels.** Not documented. The trainer describes hard labels only ([train README](https://github.com/MinishLab/model2vec/blob/main/model2vec/train/README.md)).
- **Maintenance and licence.** MIT. Releases 0.8.2 (May 2026), 0.9.0 (Aug 2026), 0.10.0 (11 Oct 2026) ([PyPI](https://pypi.org/project/model2vec/#history)).
- **tokenlearn.**
  - Method: (1) `python -m tokenlearn.featurize` computes a sentence transformer's mean output embeddings over a corpus; (2) `python -m tokenlearn.train` trains a static model to reproduce them. It produces a base model and a recommended "weighted" model. MIT licence, 38 commits on main. It assumes the pad token id is 0 ([repo](https://github.com/MinishLab/tokenlearn)).
  - The potion models were made this way from bge-base-en-v1.5: distil, featurize, tokenlearn, then re-regularise with frequency weighting, PCA and SIF ([potion-base-32M card](https://huggingface.co/minishlab/potion-base-32M)).
  - No published table compares tokenlearn with plain distillation run for run. The Oct 2024 blog reports potion-base-8M at 50.03 MTEB average against M2V_base_output at 45.34, but those runs used different versions ([POTION blog](https://minish.ai/blog/2024-10-29-tokenlearn-blogpost/)).
- **Sentence-transformers equivalent.** `StaticEmbedding` (`from_model2vec`, `from_distillation`) can be trained inside `SentenceTransformerTrainer`. HF reports models "100x to 400x faster on CPU" that keep "at least 85%" of the teacher's performance. One example: 86.52% of multilingual-e5-small on classification at about 125x the CPU speed ([HF blog](https://huggingface.co/blog/static-embeddings)).
- **Fit to us (our reading).** This is the only family that already meets the ~1 ms budget.
  - We use potion **frozen**. The obvious untried step is `fit()` with embeddings unfrozen, multi-label, with `class_weight`/`focal_gamma` for the rare atoms.
  - The second step is **domain distillation**: run `distill()` or tokenlearn with our **fine-tuned e5-small** as teacher, on our news corpus. The static table then inherits the task-tuned token geometry.
  - No source measures distillation from a *task-fine-tuned* classifier body into static embeddings. Treat it as an experiment with a pass/fail bar, not a known win.
- **Pitfalls.**
  - Static models ignore word order and negation.
  - Each `fit()` call re-initialises everything, so training cannot be continued ([train README](https://github.com/MinishLab/model2vec/blob/main/model2vec/train/README.md)).
  - The documented default device is `"auto"`, so set `device="cpu"` explicitly to keep training off the GPU.

### 1d. Fine-tuning and shrinking a small transformer (sentence-transformers)

- **Method.** Keep the fine-tuned e5-small but make it cheaper. Sentence-transformers' distillation example gives two ways ([distillation README](https://github.com/huggingface/sentence-transformers/blob/main/examples/sentence_transformer/training/distillation/README.md)):
  1. **Layer reduction (recommended there):** keep, for example, 4 of the teacher's layers and train with `MSELoss` toward the teacher's embeddings. The README says this "works usually better" because most teacher weights are kept.
  2. **Smaller student** (TinyBERT, BERT-Small) with `EmbedDistillLoss`.

  `AdaptiveLayerLoss` trains a model so that it can be truncated to fewer layers ([adaptive layer example](https://github.com/huggingface/sentence-transformers/blob/main/examples/sentence_transformer/training/adaptive_layer/README.md)).
- **CPU evidence.** int8 bge-small took 4.55 ms per call on Xeon ([HF blog](https://huggingface.co/blog/setfit-optimum-intel)). This workspace's BitMob engine already serves e5-small through ONNX Runtime int8 at about 4 ms (`/workspace/CLAUDE.md`, Latent lab section).
- **Fit to us (our reading).** Our 50-160 ms for e5-small is probably fp32 PyTorch on full-length stories. int8 ONNX, a 128-256 token cap and 4-6 layers should bring it toward 5-15 ms. That still misses "~1 ms", so this path is best used as the **teacher for the static student** or as a second stage that runs only on the stories the static model is unsure about.

### 1e. Multi-label setup notes

- One shared body with 44 sigmoid outputs is the standard way to pool data across atoms. We already measured that this multi-task fine-tune helps.
- Rare atoms (5 positives) need positive weighting or focal loss (`class_weight`, `focal_gamma` in model2vec) and **a threshold per atom**, tuned on held-out data. Where a source's evaluation uses a single global threshold of 0.3 or 0.5 ([train README](https://github.com/MinishLab/model2vec/blob/main/model2vec/train/README.md)), that is not a recommendation for us.

---

## 2. Choosing which items to label under a budget (active learning)

### Method in plain words

Active learning trains the student, then asks the teacher to label the unlabelled stories the student would learn most from, and repeats. The common ways to pick stories:

- **Uncertainty:** least confidence, margin or "breaking ties", entropy.
- **Diversity / representativeness:** k-means on embeddings, core-set, TypiClust.
- **Hybrid:** CAL picks neighbours on which the model disagrees with itself; BADGE.
- **Cold start, before any model exists:** language-model surprisal (ALPS), or zero-shot SetFit.

### Libraries

| Library | Licence | Status | Entry point | Notes |
|---|---|---|---|---|
| **small-text** ([repo](https://github.com/webis-de/small-text)) | MIT | v1.4.1 (Aug 2024); v2.0.0.dev4 alpha (23 May 2026) | `PoolBasedActiveLearner` plus a query strategy (in v1.x: `initialize_data`, `query(num_samples=…)`, `update(y)`; the v2 alpha may change interfaces). See [AL overview](https://small-text.readthedocs.io/en/latest/active_learning.html) and [notebooks](https://github.com/webis-de/small-text/tree/v2.0.0.dev4/examples/notebooks) | Text-specific. Strategies include LeastConfidence, PredictionEntropy, BreakingTies, BALD, EmbeddingKMeans, GreedyCoreset, ProbCover, ContrastiveActiveLearning, DiscriminativeActiveLearning, SEALS, ClassBalancer, BADGE, and multi-label CVIRS / LabelCardinalityInconsistency / AdaptiveActiveLearning ([strategy list](https://small-text.readthedocs.io/en/latest/components/query_strategies.html)). Five stopping criteria, initialisation strategies, a SetFit integration and a SetFit zero-shot cold-start notebook |
| **modAL** ([repo](https://github.com/modAL-python/modAL)) | MIT | Last release 0.4.2.1, 1 Jun 2023 ([PyPI](https://pypi.org/project/modAL-python/#history)): effectively unmaintained | `ActiveLearner(estimator=<sklearn>, query_strategy=…)`, `.query()`, `.teach()` | Thin sklearn wrapper. Easy to replicate in about 30 lines |
| **ALiPy** ([repo](https://github.com/NUAA-AL/ALiPy)) | BSD-3 | Release dates not visible on the repo page | Toolbox with experiment management | Widest strategy list, including multi-label (AUDI, MMC, Adaptive) and **noisy-oracle** strategies (CEAL, IEthresh) |

### Evidence: when active learning beats random sampling

- **Small budget, skewed data, BERT:** AL "can boost BERT performance". The largest gain came when the starting set was keyword-seeded and so biased toward the rare class (Ein-Dor et al., EMNLP 2020, [ACL Anthology](https://aclanthology.org/2020.emnlp-main.638/)). That is close to our rare-atom case.
- **Transformers:** several uncertainty strategies beat prediction entropy, while "state-of-the-art" strategies cost so much runtime that they can cancel the labelling savings (Schröder et al., Findings ACL 2022, [arXiv:2107.05687](https://arxiv.org/abs/2107.05687)).
- **Margin sampling** matched or beat every other strategy across 69 tabular datasets and has no hyperparameters (Bahri et al., [arXiv:2210.03822](https://arxiv.org/abs/2210.03822)).
- **CAL** was better than or equal to the best baseline on 7 NLU datasets ([arXiv:2109.03764](https://arxiv.org/abs/2109.03764)).
- **Budget decides the strategy:** with a low budget, query *typical* examples; with a high budget, query *unrepresentative* (uncertain) ones. TypiClust plus semi-supervised learning gained 39.4 points over random with 10 CIFAR-10 labels (Hacohen et al., ICML 2022, [arXiv:2202.02794](https://arxiv.org/abs/2202.02794)).
- **Rare concepts in huge pools (SEALS):** restricting candidates to nearest neighbours of the labelled set cut selection compute by up to 1,000x with similar mAP and recall ([arXiv:2007.00077](https://arxiv.org/abs/2007.00077)). small-text includes it as `SEALS`.
- **Cold start:** using the language model's loss as an uncertainty proxy reached higher accuracy in fewer rounds (Yuan et al., EMNLP 2020, [arXiv:2010.09535](https://arxiv.org/abs/2010.09535)).
- **LLM as the labeller:**
  - Uncertainty sampling "did not work well" for choosing what an LLM should annotate. A base-vs-finetuned score-gap rule worked better (Bansal & Sharma 2023, [arXiv:2306.15766](https://arxiv.org/abs/2306.15766)).
  - LLMaAA puts the LLM inside the AL loop and down-weights unreliable LLM labels by learned example reweighting. Students trained on a few hundred examples beat the LLM teacher on NER and relation extraction ([arXiv:2310.19596](https://arxiv.org/abs/2310.19596)).

### Evidence: when it does not

- **Collective outliers:** across 5 models, 4 VQA datasets and 8 methods, AL failed to beat random, because AL kept choosing hard-to-learn outliers. Gains returned as outliers were removed (Karamcheti et al., ACL 2021, [arXiv:2107.02331](https://arxiv.org/abs/2107.02331)). **(our reading)** Teacher-noise stories, where the LLM itself is unsure, are our version of these outliers.
- **Strong regularisation:** with it, AL gave "marginal or no advantage" over random; without it, gains were inconsistent (Munjal et al., [arXiv:2002.09564](https://arxiv.org/abs/2002.09564)).
- **Changing the model:** AL ties the labelled set to the model that chose it. A *different* model trained on that set does not reliably beat random sampling (Lowell, Lipton & Wallace, [arXiv:1807.04801](https://arxiv.org/abs/1807.04801)). This matters for us: if the static model selects stories, the fine-tuned e5 may not benefit, and vice versa.
- **Simulation:** simulating AL on already-labelled sets can distort results either way (Margatina & Aletras 2023, [arXiv:2305.13342](https://arxiv.org/abs/2305.13342)).

### Fit to us (our reading)

- **Labels are cheap.** At about 5,000 stories per GPU-hour per battery, doubling 2,300 stories costs about 0.5 GPU-hour per battery, or roughly 1 hour for both batteries covering the 44 atoms. Elaborate AL is hard to justify on cost alone.
- **The real bottleneck is positives for rare atoms.** Random sampling finds few of them. Targeted candidate retrieval helps there: nearest neighbours of known positives (SEALS-style), plus margin or disagreement from the existing jury.
- **Each teacher call answers all 32 questions at once,** so story selection must score all atoms together. One option is to take the maximum, over atoms, of each atom's uncertainty, weighted toward rare atoms.
- **Keep a random share in every batch, and a frozen random test set.** Otherwise the measured numbers are biased by the selection, and the Lowell transfer problem goes unseen.

---

## 3. Learning curves: predicting how much more data the student needs

- **Method.** Train on nested fractions of the labelled data, for example 10, 20, 40, 60, 80 and 100%, several seeds each. Fit an inverse power law and extrapolate.
  - Figueroa et al. use accuracy(n) = 1 − a − b·n^c, where a is the error floor and c lies in [−1, 0]. Fitting is weighted non-linear least squares, with weights growing with n so that larger samples count more ([Figueroa et al. 2012, PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC3307431/)).
  - Tools: `sklearn.model_selection.learning_curve` produces the points ([sklearn docs](https://scikit-learn.org/stable/modules/learning_curve.html)), and `scipy.optimize.curve_fit` (with `sigma=` for weights) fits them ([scipy docs](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.curve_fit.html)).
- **Evidence.**
  - **Figueroa et al.:**
    - fitting needed at least 5 points;
    - 80-560 labelled samples brought prediction error (MAE/RMSE) below 0.01;
    - weighted RMSE ranged 0.29%-1.52%;
    - 95% intervals from the Hessian narrowed with more data, but the authors note they may be optimistic ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC3307431/)).
  - **Hestness et al.:** error follows a power law in data size across translation, language models, images and speech. Model improvements shift the curve but do not change the exponent ([arXiv:1712.00409](https://arxiv.org/abs/1712.00409)).
  - **Mahmood et al. (CVPR 2022):** a plain power law misestimates how much data a target needs. A generalised function family, a tuned correction factor and **several collection rounds** improve the estimate ([arXiv:2207.01725](https://arxiv.org/abs/2207.01725)).
- **Caveat.** "No universal model" fits all learning curves, and some curves get worse with more data. The authors grew more sceptical of power laws in v2 (Viering & Loog, [arXiv:2103.10948](https://arxiv.org/abs/2103.10948)).
- **Applied to our three points (our reading, illustration only, not a forecast).**
  - Recall went 0.17 → 0.25 → 0.34 as data doubled twice: ×1.47, then ×1.36 per doubling. That is a local exponent of about 0.56, then 0.44, and it is falling.
  - If the falling ratio continues (about ×1.25-1.3 per doubling), a fourth doubling (about 4,600 stories) would give recall around 0.42-0.45.
  - Three points are below Figueroa's minimum of 5, and recall is bounded by 1. Fit 1 − a − b·n^c with at least 5 fractions × 3 seeds, **per atom group** (rare atoms have their own curves), and report a bootstrap interval.
  - Better still, follow Mahmood: label in rounds and re-fit after each one.

---

## Ranked recommendation for our case

1. **Fine-tune the static student end to end.** Use model2vec `StaticModelForClassification.fit` with embeddings unfrozen, multi-label over the 44 atoms, `class_weight` or `focal_gamma`, a threshold per atom and `device="cpu"`. It keeps the ~1 ms budget, needs no new labels, and has published evidence (wins 17/26 over logreg). It is the cheapest test of whether we are limited by frozen features.
2. **Label more, in rounds, with a measured learning curve.** Labels are cheap (about 1 GPU-hour to double the set across both batteries), and e5 recall had not levelled off. Re-fit the inverse power law after each round, then stop when the predicted gain per GPU-hour falls below what we care about.
3. **Train on soft targets.** Use the teacher's P(yes), not 0/1, in our own BCE head. It is free and supported by Hinton's small-data result. Check teacher calibration first.
4. **Distil the fine-tuned e5-small into a domain static model.** Use `distill()` with a corpus vocabulary, or tokenlearn featurize → train on our news corpus with the fine-tuned e5 as teacher, then run step 1 on top. If it works, it moves e5's gains to ~1 ms. There is no published evidence for a task-fine-tuned teacher, so pass/fail is decided on held-out stories.
5. **Targeted selection for rare atoms only.** Per round, take about 50% random stories and about 50% chosen from (a) nearest neighbours of known positives for atoms with fewer than about 30 positives (SEALS-style), and (b) margin or jury disagreement. Exclude stories where the teacher is unsure, so we avoid collective outliers. Do not rely on AL for the common atoms (Lowell, Munjal).
6. **A cascade as a fallback.** Run the static model first and send only stories near the threshold to int8 ONNX e5-small, using 4-6 reduced layers and 256 tokens. This is for the case where steps 1-4 leave a gap. Its cost is the measured fraction of stories that escalate.
7. **Skip for now:** SetFit as the production student (transformer latency, built for few-shot use; keep it for cold-starting new atoms), modAL (unmaintained), and complex AL strategies (BADGE, BALD), whose runtime outweighs our labelling cost.

### Minimal pipeline

1. **Freeze the evaluation.** Keep a random held-out set of stories, stratified so every atom has positives, labelled once and never used for training or selection.
2. **Store `P(yes)` from the teacher** for all 44 atoms on every labelled story, not just the thresholded answer.
3. **Baseline:** frozen potion-32M plus logistic heads (already measured).
4. **Train model2vec end to end** (multi-label, `class_weight`/`focal_gamma`, `device="cpu"`). Set per-atom thresholds on a validation split. Report macro and per-atom recall and precision against the teacher, plus ms per story.
5. **Learning curve:** train at 10/20/40/60/80/100% × 3 seeds, fit 1 − a − b·n^c (weighted), and predict the number of labels for the target recall.
6. **Label one round of new stories** (half random, half rare-atom-targeted, as above), retrain, re-fit the curve and check the prediction against what actually happened.
7. **Optional:** distil the fine-tuned e5 into a domain static model, repeat step 4 on it, and keep it only if it beats step 4 on the frozen set at equal latency.
