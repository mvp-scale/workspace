# Agent brief: CPU-first embedding classifiers with measured decision boundaries

Prepared 2026-10-15. Input: latent-lab-findings.md. This is an experiment and implementation brief, not a claim that the proposed system has been validated.

## Mission

Extend the existing latent-space work into a reproducible classifier system. Determine which fixed detectors can run on CPU using one shared text encoding and cheap mathematical readouts; which need a small task-aware model; and which still require Clef/Jev. Optimize quality, coverage, latency and memory jointly. Preserve the existing TypeSafe interface after verifying its actual schema.

CPU is preferred. Low-memory GPU execution is acceptable. Do not assume a universal zero-shot replacement is required before shipping useful fixed detectors.

## Starting evidence and its limits

The supplied report records e5-small-v2 plus per-detector heads at 86% average tone accuracy with roughly 2,000 same-source training examples, versus zero-shot Clef at 79% and Jev at 81%. Treat these as the report's measurements, not independently reproduced results. They support investigating specialized detectors, not general parity with Jev.

Small-model CPU timings are provisional. Real transcript accuracy and teacher-label training are untested. Raw scripts and outputs, not the summary, must establish sample counts, splits, input templates, pooling, and uncertainty.

Revise two overly broad interpretations:
- Poor pooled-vector MMLU performance establishes failure of that representation/readout/evaluation setup; it does not prove the underlying model contains no relevant knowledge.
- The absence of a good generic head in these experiments does not establish that no small task-aware classifier exists. Test GLiClass and a small NLI model as separate baselines.

## 1. Audit before expanding experiments

Inspect the named probes, cached vectors, data splits and timing code. Verify:
- Exactly what each candidate sees: text, question, answer options, speaker roles and surrounding turns. A text-only detector cannot answer arbitrary questions absent from its input.
- Encoder revision, tokenizer, required prefix, truncation, padding, pooling, normalization, precision and maximum sequence length. E5 recommends the "query: " prefix for classification features; confirm rather than silently changing cached embeddings.
- Duplicate/near-duplicate texts and overlapping call windows. Split by whole conversation, then use appropriate speaker/customer grouping and a later-time holdout. Public source datasets should have a separate source/domain holdout where feasible.
- Training, model selection, calibration, routing selection and final test separation. Fit every data-derived transformation inside the training fold. Freeze the complete pipeline before final evaluation.
- Whether 17-model/readout selection has repeatedly used the same probes. If so, treat those probes as development data and obtain a fresh test set.
- Label provenance: publication-based sarcasm can encode source style; code datasets can expose templates; small balanced public samples do not reproduce production prevalence.

Produce an audit table: observation, evidence, impact, correction. Do not discard useful old runs; mark their evidentiary scope.

## 2. Representations: hold most things fixed

Start with the existing potion-base-8M, e5-small-v2 and bge-small-en-v1.5 embeddings. Keep a sparse word/character TF-IDF plus logistic-regression baseline: it exposes lexical shortcuts and provides a useful non-neural competitor.

Use one text-only embedding per transcript window for the fixed-detector track:
z = normalize(E(text)), z in R^d.

Compare raw and normalized embeddings only as a small controlled ablation. Cache by model revision + preprocessing version + exact input. Cached head-only timings must never be presented as end-to-end timings.

Separate three representation families:
A. Text only: amortizes one encoding across fixed detectors.
B. Question/text or premise/hypothesis interaction: may improve judging, but usually needs fresh computation per question.
C. Token or turn representations: preserve local evidence, at additional memory and aggregation cost.

No vector database is needed for a bank of linear heads. Use exact matrix arithmetic first. An example index is justified only if a prototype/retrieval method earns its cost.

## 3. Test a small, mathematically defined readout ladder

Use the same embeddings, splits and tuning budget. Start with logistic regression as the incumbent, not cosine.

| Readout | Definition | Question answered |
|---|---|---|
| Regularized logistic / softmax | binary sigmoid(w^T z+b); multiclass softmax(Wz+b) | Is the information linearly separable? |
| Class centroids | mu_c = mean training embedding for class c; nearest distance/cosine | Can a simple example-derived prototype suffice? |
| Shrinkage LDA | shared covariance Sigma; score z^T Sigma^-1 mu_c - 0.5 mu_c^T Sigma^-1 mu_c + log prior_c | Does covariance-aware linear classification improve estimation? |
| Multiple prototypes per class | cluster each class on training data; score distances to its prototypes | Are classes multimodal? |
| Small nonlinear readout | bounded one-hidden-layer MLP; optionally approximate RBF features plus linear head | Is a cheap nonlinear boundary sufficient? |
| Supervised encoder adaptation | SetFit-style contrastive adaptation or bounded multitask fine-tuning | Must the representation itself change? |

For LDA, use covariance shrinkage and precompute weights: inference becomes Wz+b. Full covariance inversion is a training operation. With hundreds of dimensions and few examples, unregularized per-class covariance is unreliable.

For multiple prototypes, do not assume a distance softmax is a calibrated posterior. Fit any learned aggregation/calibration on separate data. Cap prototypes and memory.

Whitening, rotations and linear projections are not new reasoning abilities. An invertible linear transform before an unrestricted linear head preserves the family of attainable decision boundaries. It can change conditioning, regularization and finite-data behavior; it cannot recover information the pooling step discarded. A linear supervised projection followed by a linear head is still a linear classifier. PCA can throw away discriminative directions; choose dimension by classification validation, not explained variance alone.

Do not train on UMAP/t-SNE coordinates as the default classifier. Those are diagnostic pictures, not evidence of reliable class separation.

## 4. Diagnose the vector space with tests tied to decisions

For each detector record:
- Within-class spread, between-class separation, centroid margins, and nearest-neighbor label purity relative to class-prior baselines.
- Linear-versus-nonlinear held-out performance and learning curves.
- Counterfactual pairs: "I agreed" / "I did not agree"; "I will cancel" / "I already cancelled"; quoted versus endorsed statements; agent versus customer; numeric and temporal changes.
- For dialogue, compare current turn alone against role-preserving recent context. Track evidence lost by truncation.
- Out-of-domain examples and high-confidence mistakes, with representative nearest training examples for review.

These diagnose geometry; they do not replace held-out performance. Cluster boundaries need not coincide with task boundaries. Do not name an embedding dimension "anger" or "intent" without controlled evidence.

Start with 80 / 250 / 1,000 / available examples per detector, multiple seeds and consistent class balance. Report performance against annotation cost, not just model size.

## 5. Address new questions with a separate task-aware track

Test:
1. knowledgator/gliclass-instruct-edge-v1.0 and/or gliclass-edge-v3.0 (32.7M parameters).
2. A larger GLiClass base candidate if edge misses the quality target.
3. One documented small NLI cross-encoder, pinned to a model revision after checking its model card.

Use task descriptions and label meanings, rather than ambiguous labels alone. Test yes/no, mutually exclusive choice, text-pair judging and unseen task families separately. GLiClass is classification-trained; it is not just an off-the-shelf cosine embedder. Publisher benchmarks are not JevBench results or proof of parity on our tasks. The edge model's own card shows substantial weaknesses across several datasets.

Keep questions/task families out of training when measuring unseen-question generalization; holding out texts for known detectors is a different experiment. Record label-count scaling and additional question-conditioned encoding cost.

Optional later research: a shared interaction head on [z_text, z_question, abs(z_text-z_question), z_text*z_question], or a low-rank bilinear scorer z_text^T A z_question. These require diverse task-level supervision and task-disjoint evaluation. They are hypotheses, not label-free shortcuts.

## 6. Change pooling only when the failure analysis justifies it

If evidence is diluted by one pooled vector:
- Compare turn-level embeddings with explicit speaker and temporal features.
- Compare a bounded learned pooling/attention layer or a small cross-encoder on the relevant context.
- Only then consider token-level late interaction.

ColBERT-style MaxSim is a relevance mechanism, not an entailment guarantee. Token interaction can help local evidence while still failing negation, attribution or reasoning. Account for tokens x dimensions storage and per-label interaction work.

If adapting the encoder, try one shared multitask encoder first. Revalidate every head after any encoder, pooling or quantization change. Many separately fine-tuned encoders destroy the one-encode amortization advantage.

## 7. Labels, calibration and rejection are part of the classifier

Use human-reviewed, task-defined transcript labels for the final test. Compare the student and teacher on the same items; teacher agreement is not ground-truth accuracy.

For teacher-labelled training:
- Preserve model/version, prompt, task rubric, source and raw outputs.
- Compare hard labels with soft-label distillation. Teacher probability outputs may themselves be uncalibrated.
- Review disagreement and borderline cases plus a random sample. Agreement filtering alone can remove hard cases and preserve shared errors.
- Separate inadequate evidence/ambiguous annotation from a genuine negative.
- Grow data through uncertainty/disagreement and representative sampling; retain unbiased evaluation data.

Calibrate on independent, production-like labelled data. Compare sigmoid/temperature calibration; use isotonic only with adequate data. Report log loss, Brier score and reliability plots alongside F1, balanced accuracy and task-specific precision/recall. Calibration is distribution-specific.

Typed outputs:
- noul: P(yes) for the exact registered predicate and evidence policy.
- choice: categorical probabilities summing to one only for mutually exclusive exhaustive alternatives. Independent labels require separate binary probabilities.
- score: ordinal probabilities. If using cumulative outputs q_k=P(Y>k), enforce monotonicity; obtain level probabilities by adjacent differences and endpoints. Compare against a softmax baseline.
Verify the actual API schema before implementing this mapping.

Choose routing thresholds on validation data using selective risk versus coverage. Include distance/novelty, disagreement and evidence availability as candidate signals; none is automatically a reliable OOD detector. High confidence can still be wrong. Report accepted-case error, escalated fraction, false accepts, fallback cost and total latency. Missing heads and unsupported tasks must route explicitly.

## 8. Benchmark on the actual deployment hardware

Report hardware from the live machine; the supplied experiment used i9-10900K AVX2 and RTX 5090. Do not substitute another remembered server specification.

For the best one or two quality candidates compare:
- PyTorch FP32, ONNX Runtime FP32 and AVX2-targeted dynamic INT8, and OpenVINO where supported.
- Threads 1 / 2 / 4 / 8 with concurrency controlled to avoid oversubscription.
- Representative 32 / 128 / 256 / supported maximum token lengths, batch 1 latency and separate throughput batches.
- CPU first; optional GPU FP16/BF16 only when supported, with device synchronization and data movement included.

Measure warm p50/p95/p99, cold start, tokenization, encoding, head bank, calibration, serialization, queueing and total request time. Record idle and peak RSS, GPU allocated/reserved and process/device overhead. Quantization may help or hurt on AVX2; measure both quality and latency.

Weight-only arithmetic:
- 33M parameters ~132 MB FP32 or ~33 MB INT8; neither is total runtime memory.
- 100 binary 384-dimensional FP32 heads plus biases use 154,000 bytes (~150 KiB), and one inference requires 38,400 multiply-accumulate terms before calibration.
These are calculated storage/work counts, not measured performance.

Report proposed operating budgets separately from measurements. Useful initial goals: CPU p95 <=20 ms for a 128-token window plus 100 binary heads, peak process RSS <=1 GB; optional GPU process peak <=2 GB. These are starting hypotheses, not user-mandated SLOs or promises. Include the static-model candidate for an aggressively lower latency tier.

At 1% fallback, p99 can approach fallback latency depending on the mixture and quantile convention; always measure the cascade distribution and route-specific tail latencies.

## 9. Deliver a decision, then package the interface

Deliver:
1. Audit and reproducible split manifests.
2. A bounded experiment matrix with configs, seeds, raw predictions and pinned revisions.
3. Per-task Pareto tables: quality, calibration, CPU p95, RAM/VRAM, training examples, accepted coverage and fallback cost.
4. A route decision per detector: static CPU, contextual CPU, small task-aware CPU/GPU, or Clef/Jev.
5. A minimal validated prototype through the existing TypeSafe schema, after selecting a viable route.

Version encoder, tokenizer, preprocessing, feature transform, detector rubric, label order, head, calibrator, thresholds and data lineage together. Changing a detector question requires a new version/evaluation, not silently reusing its old head.

For fixed detectors, ship the simplest configuration meeting validation requirements. If a proposed geometry method does not improve the held-out quality/cost frontier, keep the linear head. If a task fails, report the failure and route it rather than hiding it in an aggregate.

Do not expand to another large embedding sweep until the audit and initial readout comparison show what is missing. Do not claim production performance from cached vectors, teacher agreement, same-source accuracy or vendor benchmarks.

## Primary references

Checked 2026-10-15. These support methods/candidate selection, not speed or accuracy promises on our hardware.

- E5 model card: prefix, pooling, 384 dimensions and 512-token limit: https://huggingface.co/intfloat/e5-small-v2
- SetFit paper: contrastive encoder adaptation then classification head: https://arxiv.org/abs/2209.11055
- GLiClass paper: https://arxiv.org/abs/2508.07662
- GLiClass implementation and task/label-conditioned architectures: https://github.com/Knowledgator/GLiClass
- GLiClass instruct edge model card, size and task examples: https://huggingface.co/knowledgator/gliclass-instruct-edge-v1.0
- GLiClass edge v3 model card and publisher benchmark limitations: https://huggingface.co/knowledgator/gliclass-edge-v3.0
- Shrinkage LDA and covariance-aware classification: https://scikit-learn.org/stable/modules/lda_qda.html
- Independent probability calibration: https://scikit-learn.org/stable/modules/calibration.html
- ONNX/OpenVINO and quantization guidance: https://sbert.net/docs/sentence_transformer/usage/efficiency.html

