# Agent brief: a System-1 typed classifier from local embeddings

Written 15 Oct 2026 against `latent-lab-findings.md`. Purpose: tell the agent which established methods apply, which
subset we need, and what to run next, in order. Verify every cited link before relying on it.

## 1. Name the discipline

What we are doing is **linear probing of frozen representations** (Alain & Bengio 2016; survey: Belinkov 2022): treat the
encoder as a fixed feature extractor and fit a cheap readout on top. Everything in the findings doc (cosine, bias
correction, whitening, learned head, angles) is a readout in that family. The three adjacent disciplines we also need are
**zero-shot classification via NLI** (Yin et al. 2019), **knowledge distillation** (Hinton et al. 2015) for teacher
labels, and **probability calibration / selective prediction** (Guo et al. 2017; Geifman & El-Yaniv 2017). Nothing here
needs a new pipeline; it needs the standard versions of these four, in the right order.

## 2. What the findings already settle

| Question | Settled answer | Evidence |
|---|---|---|
| Is the signal in the vector? | Yes for tone/text-type and judging; no for world knowledge | Head on Qwen-4B: 84% / 71% / 39% |
| Does a small CPU encoder suffice? | Yes, with ~1,000–2,000 labels per detector | e5-small-v2 86% vs Jev 81% |
| Does cosine work on small models? | No | 50–55% |
| Does one general head transfer to new questions? | No | worse than cosine |
| Does bias correction help? | Yes on single-text yes/no; hurts on two-text (NLI, contract) | enable per detector |

Conclusion for the agent: stop re-running cosine/angle variants. The remaining work is readouts, zero-shot, labels,
calibration, runtime, and evaluation hygiene.

## 3. Readouts: the standard menu (open question 2)

All operate on the same cached vector(s); cost is microseconds unless noted. Run them as one sweep with the existing
5-fold harness and the N=80/250/1,000 curves.

| Readout | What it is | Why try it | Cost | Source |
|---|---|---|---|---|
| Logistic regression (current) | Linear head, L2 | Baseline | μs | — |
| LDA / Gaussian class-conditional | Closed-form linear head from class means + shared covariance | Often beats logistic at N=80; no tuning | μs | Hastie, Tibshirani, Friedman, *ESL* ch. 4 |
| Whitening then logistic | Remove top shared directions, then head | Helps small encoders whose vectors are anisotropic | μs | Mu & Viswanath 2018 (all-but-the-top); Su et al. 2021 (BERT-whitening) |
| Prototype / kNN | Distance to class means or nearest labelled examples | Strong few-shot baseline; no fit | μs–ms | Snell et al. 2017 |
| Kernel SVM / small MLP | Non-linear head | Tests whether linear is the ceiling | ms | — |
| Ordinal logistic | For `score` (ordinal levels) | Right loss for ordered labels; current multinomial ignores order | μs | McCullagh 1980 |
| Multi-vector (token-level) + attention pool | Keep token vectors, learn a pooling query per detector | Late-interaction idea applied to classification; may recover negation | ms | Khattab & Zaharia 2020 (ColBERT) |
| SetFit | Contrastive fine-tune of the small encoder on pairs, then head | Reported near full-fine-tune accuracy from 8–64 examples; directly targets our N=80 gap | one-off training, inference unchanged | Tunstall et al. 2022 |

Priority: LDA, whitening+logistic, ordinal logistic, SetFit. Skip kernel/MLP unless the first three plateau.

## 4. Zero-shot (open question 1)

A pooled single vector does not encode "true of this text"; the literature's answer for zero-shot classification of
arbitrary questions is a **cross-encoder trained on NLI**: premise = window, hypothesis = "This text is {label}", read
the entailment probability (Yin et al. 2019). Models: `cross-encoder/nli-deberta-v3-base` (~180M params), DeBERTa-v3
MNLI/ANLI variants. Expected CPU cost: tens of ms per (window, hypothesis) pair, so cost scales with number of labels.

What to measure: NLI cross-encoder zero-shot on the 7 tone sets and 6 judging sets against Clef 79%/66%. If it lands
within ~5 points on tone it becomes the "no head yet" path and Clef is reserved for reasoning/world knowledge.

Also in scope, lower priority: linear probes on **mid-layer hidden states of a small decoder** (0.5–1.5B) rather than
the final pooled embedding (Zou et al. 2023, representation engineering; Burns et al. 2022, which the findings already
cite). Same probing discipline; the agent already has the harness.

## 5. Teacher labels (open question 3)

This is **knowledge distillation** (Hinton et al. 2015). Required subset:
1. Keep the teacher's probabilities (soft labels), not argmax; train the head with soft-target cross-entropy.
2. Label every transcript with both Clef and Jev; keep agreement cases, hold out disagreements as a review set.
3. Run **confident learning** (Northcutt et al. 2021, `cleanlab`) on the teacher labels to flag likely-wrong ones.
4. Measure: head trained on teacher labels vs head trained on human labels, on the public sets where both exist.
   This is the one untested claim the whole design depends on.
5. Volume: the curves say ~1,000 per detector reaches the plateau; start there.

## 6. Calibration and escalation (open question 4)

Standard process: hold out a calibration split, fit **temperature scaling** (Guo et al. 2017) or Platt scaling
(Platt 1999) on the head's logits, report **expected calibration error (ECE)** and a reliability diagram per detector.
Escalation is **selective prediction** (Geifman & El-Yaniv 2017): sweep a confidence threshold, plot accuracy vs
coverage, pick the threshold that meets the target accuracy; everything below it goes to Clef. Angle disagreement can
be a second escalation signal, but measure it against the threshold alone first.

## 7. CPU runtime (open question 5)

| Step | Tool | Note |
|---|---|---|
| Export encoder to ONNX | `sentence-transformers` `backend="onnx"` or `optimum` | Expect 1.5–3× over eager PyTorch on CPU |
| Dynamic int8 | ONNX Runtime quantization | Without VNNI on the i9-10900K the gain may be small or negative; measure, as the findings note |
| OpenVINO | `backend="openvino"` | Often the fastest on Intel CPUs; test once |
| Static model | Model2Vec distil from e5-small-v2 | Sub-ms; findings show potion within ~6 points of e5-small at N=2,000, so distil the best encoder rather than using the stock potion |
| Threads / window | fix `OMP_NUM_THREADS`, batch windows | Re-measure on a quiet machine before quoting ms |

## 8. Evaluation hygiene (open question 6)

1. Near-duplicate check between pool and probe items (MinHash or embedding cosine > 0.95); drop leaks.
2. Report group-level 95% confidence intervals (bootstrap over items), not per-set point estimates.
3. Build one small human-labelled set of **real call-transcript windows** per detector (even 100 items). Everything else
   is in-distribution; this is the only number that predicts production.
4. Keep Clef/Jev answers on the same split so every comparison is paired.

## 9. Ordered plan for the agent

1. Readout sweep (§3: LDA, whitening+logistic, ordinal) on existing vectors. One script, one table.
2. NLI cross-encoder zero-shot on tone + judging (§4).
3. SetFit on e5-small-v2 at N=80 and N=250 (§3).
4. Teacher-vs-human head comparison on public sets (§5, step 4).
5. Temperature scaling + ECE + coverage curves per detector (§6).
6. ONNX/OpenVINO timing on a quiet machine (§7).
7. Real-transcript holdout (§8, step 3).

Each step produces one table in the format of the findings doc; no step depends on a later one.

## References

- Alain & Bengio 2016, Understanding intermediate layers using linear classifier probes — arXiv:1610.01644
- Belinkov 2022, Probing classifiers: promises, shortcomings, and advances — arXiv:2102.12452
- Yin, Hay & Roth 2019, Benchmarking zero-shot text classification — arXiv:1909.00161
- Tunstall et al. 2022, Efficient few-shot learning without prompts (SetFit) — arXiv:2209.11055
- Mu & Viswanath 2018, All-but-the-top — arXiv:1702.01417
- Su et al. 2021, Whitening sentence representations — arXiv:2103.15316
- Snell, Swersky & Zemel 2017, Prototypical networks — arXiv:1703.05175
- Khattab & Zaharia 2020, ColBERT — arXiv:2004.12832
- Zhao et al. 2021, Calibrate before use — arXiv:2102.09690
- Burns et al. 2022, Discovering latent knowledge (CCS) — arXiv:2212.03827
- Zou et al. 2023, Representation engineering — arXiv:2310.01405
- Hinton, Vinyals & Dean 2015, Distilling the knowledge in a neural network — arXiv:1503.02531
- Northcutt, Jiang & Chuang 2021, Confident learning — arXiv:1911.00068
- Guo et al. 2017, On calibration of modern neural networks — arXiv:1706.04599
- Platt 1999, Probabilistic outputs for support vector machines
- Geifman & El-Yaniv 2017, Selective classification for deep neural networks — arXiv:1705.08500
- Hastie, Tibshirani & Friedman, *The Elements of Statistical Learning*, 2nd ed., ch. 4 (LDA, logistic regression)
- Model2Vec — https://github.com/MinishLab/model2vec
- sentence-transformers ONNX/OpenVINO backends — https://sbert.net/docs/sentence_transformer/usage/efficiency.html
