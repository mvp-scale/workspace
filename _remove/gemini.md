Your agent’s experimental approach in `latent-lab-findings.md` is thorough and hits on the exact right architectural conclusion: **encode the transcript window once with a lightweight backbone, and run dozens of ultra-fast mathematical readout heads on top of that single vector**. Reaching **86% accuracy on tone** with `e5-small-v2` (beating both Clef Flash 9B and Jev) at ~12 ms on CPU proves that the information is already in the latent space—you just need the right geometry to extract it.

Below is an architectural review, answers to the 6 open questions in your findings document, and a direct, copy-pasteable engineering brief you can give to your agent to build the next iteration.

---

## 1. Architectural Strategy: Maturing the Latent Space

Your agent discovered that standard cosine similarity fails zero-shot on small models because cosine measures **topical similarity** ("are these about the same subject?"), whereas classification requires **directional projection** ("where does this text sit along the *angry $\leftrightarrow$ calm* axis?").

To turn an embedding space into a mathematical "System 1" classifier without a 10 GB LLM, guide your agent toward three geometric upgrades:

* **Contrastive Concept Vectors (Improving Zero/Few-Shot):** Instead of taking the cosine similarity between a transcript vector $\mathbf{x}$ and a prompt vector $\mathbf{p}^+$, define a **concept axis** using the difference between the positive and opposite angles:

$$\mathbf{v}_{\text{axis}} = \frac{\mathbf{\mu}^+ - \mathbf{\mu}^-}{\Vert{}\mathbf{\mu}^+ - \mathbf{\mu}^-\Vert{}_2}$$



where $\mathbf{\mu}^+$ and $\mathbf{\mu}^-$ are the averaged vectors of your positive and negative angle phrasings (or class centroids). Projecting a centered, whitened vector onto this difference axis ($\mathbf{x} \cdot \mathbf{v}_{\text{axis}}$) naturally cancels out common baseline bias—which is the exact mathematical reason your agent found that "asking the opposite question too" gave the biggest label-free boost.


* **Mahalanobis / Covariance-Aware Readouts (LDA & QDA):** Logistic regression is great, but fitting **Linear Discriminant Analysis (LDA)** or **Shrinkage Mahalanobis Distance** (Ledoit-Wolf covariance) on your vectors often converges with far fewer examples ($N=50$ to $250$) because it explicitly models the elliptical shape of the embedding clusters.
* **Bilinear / Multiplicative Interaction Heads (Solving SNLI & Judging):** Your agent noted that small models struggled on "Reading and Judging" (42–52%). Linear heads only draw a single flat hyperplane ($W\mathbf{x} + b$). Adding a lightweight **2-layer MLP with Residual Connections and SiLU/GELU** or a **Low-Rank Bilinear pooling layer** ($\mathbf{x}^T U V^T \mathbf{x} + W\mathbf{x} + b$) takes less than **0.05 ms** on CPU and allows the readout to capture non-linear feature combinations (e.g., *polite words* + *hostile intent* = *sarcasm/manipulation*).



---

## 2. Direct Answers to Your Agent's 6 Open Questions

### Q1. Can we get true zero-shot quality from a small model?

**Not with a bi-encoder alone, because bi-encoders compress everything before knowing what question you are asking.** However, you can get very close on CPU using two specific model families your agent hasn't tested yet:

1. **Zero-Shot NLI Cross-Encoders (`DeBERTa-v3-small` or `xsmall` trained on MNLI/FEVER/ANLI, such as `MoritzLaurer/DeBERTa-v3-small-mnli-fever-anli-ling-wanli`):** Instead of encoding text and question separately, an NLI model takes `[CLS] Transcript [SEP] Hypothesis [SEP]` and outputs `[Entailment, Neutral, Contradiction]`. It takes ~15–25 ms on CPU, uses <0.5 GB RAM, and is purpose-built for zero-shot "Is this statement true about this text?" tasks.
2. **GLiClass (`knowledgator/gliclass-small-v1.0`):** A newer architecture built specifically for zero-shot sequence classification. Unlike standard cross-encoders that have to re-run for every label, GLiClass encodes the text and all candidate labels together in a single forward pass, running in milliseconds on CPU.

### Q2. Better readouts than a linear head at millisecond CPU cost?

* **SetFit (Contrastive Fine-Tuning of the Encoder):** If you have 10–15 fixed detectors that always run together, do **multi-task SetFit fine-tuning** on `e5-small-v2`. You train the encoder itself using contrastive pairs across *all* your detectors so its latent space warps to separate tone, manipulation, and fallacies cleanly. It remains a single 33M-parameter encode at runtime, but its vectors become vastly more linearly separable.


* **Multi-Layer Feature Concatenation:** Right now, your agent takes the final layer's pooled vector. In BERT/LLM encoders, syntax and tone live in the middle layers (layers 6–9), while abstract semantics live in the final layer. Concatenating the mean-pooled vectors from layers $[-1, -3, -6]$ triples the head's input dimension (e.g., $384 \times 3 = 1152$) at **zero extra compute cost**, often boosting judging/code accuracy by 4–7 points.


* **2-Layer Gated MLP Head (SwiGLU):** For the readout head itself, upgrade from flat Logistic Regression to a tiny SwiGLU MLP with extreme dropout (0.5) and Weight Decay, trained on the concatenated multi-layer vectors.

### Q3. Making teacher labels (Clef / Jev) trustworthy for distillation

* **Train on Soft Logits (KL-Divergence), NOT Hard Labels:** Have Clef Flash and Jev output their raw probability distributions (`noul` float, `choice` vector). Instead of rounding to `0` or `1` and using binary cross-entropy, train the small readout heads using **KL-Divergence** or **Logit Regression (MSE on log-odds)** to match the teacher's exact probability curve. One soft label carries 5–10x more geometric information than a hard binary label ("85% angry" vs "52% angry").


* **Active Learning / Uncertainty Sampling:** Don't label 2,000 random transcript windows per detector. Run your cheap zero-shot angles on 50,000 unlabelled call windows, and pick:


* 500 windows where the angles strongly agree (anchors).
* 1,500 windows where the angles disagree or sit near 0.5 (boundary cases).


* **Agreement Filtering:** On the boundary cases, query both Clef Flash and Jev. If $\vert{}\text{P}_{\text{Clef}} - \text{P}_{\text{Jev}}\vert{} > 0.35$, drop the item from training or flag it—it means the question prompt itself is ambiguous on conversational transcripts.

### Q4. Probability calibration & escalation routing

* **Calibration:** Logistic regression trained on soft teacher logits is already well-calibrated, but you should fit **Temperature Scaling** (for multiclass `choice`) or **Isotonic Regression / Beta Calibration** (for binary `noul`) on a held-out 20% validation split of real transcripts. Beta calibration handles skewed probability distributions better than standard Platt scaling.
* **Escalation Router (System 1 $\rightarrow$ System 2 Cascade):** Do not escalate solely when $P \in [0.4, 0.6]$. A model can be **confidently wrong** on out-of-distribution (OOD) text. Build a two-gate router:
1. **Aleatoric Uncertainty (Boundary Check):** The calibrated probability is near the decision threshold (high Shannon entropy $H(p)$).
2. **Epistemic Uncertainty (OOD Mahalanobis Check):** Compute the Mahalanobis distance of the incoming transcript vector $\mathbf{x}$ from the training distribution centroid $\mu_{\text{train}}$. If the transcript looks nothing like the training data (e.g., garbled ASR, foreign language, weird edge case), escalate to Clef Flash even if the linear head says 95%.



### Q5. CPU runtime optimization on Intel i9-10900K (AVX2, no AVX-512/VNNI)

Your agent's suspicion about `int8` on an i9-10900K is **100% correct**:

* **Avoid naive INT8 on Cascade Lake / Comet Lake (no VNNI):** Without `AVX512_VNNI` or `AVX_VNNI`, 8-bit integer matrix multiplication requires expensive up-casting instructions (`vpmaddubsw` + `vpmaddwd`) and suffers from saturation issues, which often makes `int8` *slower* or no faster than `fp32` on a 10900K while hurting embedding geometry.
* **Use OpenVINO (`FP32` or `FP16` weights) or ONNX Runtime with OpenVINO EP:** On an Intel i9-10900K, Intel's **OpenVINO** graph compiler fuses transformer attention layers and GELU activations natively for AVX2+FMA. Exporting `e5-small-v2` to OpenVINO FP32 will typically drop your 12 ms PyTorch latency down to **~2.5–3.5 ms** on 4 threads.
* **Thread Pinning:** Do not let PyTorch or ONNX spawn 10–20 threads for a small 33M model; thread synchronization overhead will dominate the 3 ms compute time. Set `intra_op_num_threads = 4` (pinned to physical cores) and run multiple worker processes if you need high concurrency.
* **Qwen3-Embedding-0.6B on GPU/CPU:** If you want a single model that handles Tone, Judging, and Code well without hitting 10 GB VRAM, `Qwen3-Embedding-0.6B` takes only **1.8 GB VRAM** (or ~500 MB in `Q8_0` via `llama.cpp` / `GGUF`). Running `Qwen3-Embedding-0.6B` in `llama.cpp` with `--pooling last -ub 512` on GPU takes **<4 ms** and <1 GB VRAM, or ~60–90 ms on AVX2 CPU in GGUF `Q4_K_M`/`Q8_0`.



### Q6. Hidden evaluation pitfalls in your current benchmark

1. **Clean Text vs. ASR Call Transcripts:** Public datasets (GoEmotions, Civil Comments, Onion, SNLI) are written, punctuated text. Live call transcripts have **no reliable punctuation, ASR homophone errors, disfluencies ("um, yeah, no, I mean"), and speaker overlap/diarization boundaries**. `e5-small-v2` relies heavily on punctuation and casing. **Fix:** Strip punctuation/casing or inject realistic ASR noise into the public datasets during evaluation, and always format transcript windows with speaker tags (`Agent: ... \n Caller: ...`).


2. **Class Imbalance & Base-Rate Fallacy:** Probe sets are usually balanced (50/50 or uniform across classes). In live calls, "threat" or "phishing" or "manipulation" happens in **<1% of windows**. A model with 86% balanced accuracy (14% false positive rate) will trigger false alarms on **14 out of every 100 normal call windows**. **Fix:** Evaluate using **PR-AUC (Precision-Recall AUC)** and **Precision @ 90% Recall**, not balanced accuracy.

---

## 3. Copy-Paste Prompt / Action Plan for Your AI Agent

You can pass the following structured prompt directly to your agent to execute the next phase of experiments on your machine:

```markdown
### Next Phase Directive: Latent Space System-1 Classifier Architecture

I have reviewed `latent-lab-findings.md`. The finding that `e5-small-v2` + per-detector heads hits 86% on tone at ~12ms CPU (beating Clef Flash and Jev) validates the shared-encoder + multi-head readout architecture. 

Before we lock in the production `/v1/systemone` wrapper, run the following targeted experiments and architectural upgrades to solve the open questions:

#### 1. Upgrade the Feature Extraction & Readout Math (`probes/embed_readouts_v2.py`)
* **Multi-Layer Pooling:** Instead of only taking the final layer hidden state from `e5-small-v2` and `Qwen3-Embedding-0.6B`, extract the pooled embeddings from layers `[-1, -3, -6]` (or last, middle, quarter) and concatenate them. Test if mid-layer syntax features close the gap on the **Reading & Judging** and **Code** probe sets.
* **Distillation via Soft Logits (KL-Divergence):** In our teacher-student tests, do not train the linear heads on hard 0/1 labels. Train a Ridge Regression / Logistic head to predict the **log-odds (logit)** of Clef Flash / Jev probabilities (or minimize KL-divergence against their full probability distributions). Measure how many fewer teacher examples ($N=80, 250, 500$) are needed when training on soft teacher probabilities vs hard labels.
* **Non-Linear & Covariance Readouts:** Benchmark three fast heads against standard Logistic Regression on the 5-fold and pool curves:
  1. **Shrinkage LDA (Linear Discriminant Analysis with Ledoit-Wolf covariance)** — test sample efficiency at $N=80$.
  2. **2-Layer SwiGLU MLP with Residual Connection** (`Linear(D, D//2) -> SwiGLU -> Dropout(0.5) -> Linear(D//2, C)` + linear skip connection) — test if non-linear feature interaction fixes the Judging sets.
  3. **Difference-Vector Projection (Zero-Shot):** Form $\mathbf{v}_{\text{axis}} = \text{norm}(\mathbf{v}_{\text{pos\_angles}} - \mathbf{v}_{\text{neg\_angles}})$ on whitened vectors and score via dot product.

#### 2. Solve the Zero-Shot Fallback without a 9B LLM (`probes/zeroshot_cross.py`)
* Bi-encoders fail zero-shot because the text is encoded without seeing the question. Benchmark two tiny cross-attention classifiers on CPU across all 21 probe sets (especially Judging and SNLI):
  1. `MoritzLaurer/DeBERTa-v3-small-mnli-fever-anli-ling-wanli` (cast yes/no and choices as NLI hypotheses).
  2. `knowledgator/gliclass-small-v1.0` (single-pass zero-shot classifier).
* Compare their zero-shot accuracy and CPU latency against Qwen3-4B cosine and Clef Flash. If a 40M NLI cross-encoder hits ~70%+ zero-shot on CPU in 20ms, that becomes our Tier-2 zero-shot engine before escalating to GPU.

#### 3. Fix the Evaluation Metrics for Production Reality
* In live call transcripts, positive events (threats, manipulation, dark patterns) have a <2% base rate. Balanced accuracy hides false-positive floods.
* Add **ROC-AUC**, **PR-AUC (Average Precision)**, and **Expected Calibration Error (ECE)** to the output tables alongside accuracy.
* Add an **OOD + Uncertainty Escalation simulation**: combine **Beta/Temperature Calibration** with a **Mahalanobis distance gate** (distance from training vector distribution). Plot accuracy vs. % of calls escalated to Clef Flash (e.g., at 10%, 20%, and 30% escalation budgets).

#### 4. Hardware Optimization Benchmark on the i9-10900K (`probes/cpu_bench_clean.py`)
* Re-run the quiet CPU timing benchmark, but export `e5-small-v2` and `bge-small-en-v1.5` to **ONNX Runtime** and **OpenVINO (FP32)** with `intra_op_num_threads=4` (do not use naive INT8 since our i9-10900K lacks VNNI).
* Also test `Qwen3-Embedding-0.6B` via `llama.cpp` (GGUF `Q8_0` and `Q4_K_M`) on both CPU and RTX 5090 (<1 GB VRAM footprint) to see its true production latency.

#### 5. FastAPI `/v1/systemone` Cascading Wrapper Spec
Once the numbers above are logged, design the drop-in service with a 3-tier cascade:
* **Tier 1 (0.5–4 ms CPU):** Shared OpenVINO encoder (`e5-small-v2` or `potion-32M`) $\rightarrow$ cached multi-head readout matrix multiply (runs 50 heads simultaneously in a single `np.dot(X, W_all)` call) $\rightarrow$ Temperature/Beta calibration.
* **Tier 2 (15–30 ms CPU / 3 ms GPU, <2 GB VRAM):** If the question has no trained head OR Tier 1 epistemic/aleatoric uncertainty triggers escalation, route to local `DeBERTa-v3-small-NLI` or `Qwen3-Embedding-0.6B`.
* **Tier 3 (45 ms GPU):** Escalate world-knowledge (MMLU-type) or high-uncertainty reasoning queries to Clef Flash / Jev.

```

Would you like to dive deeper into the math for the **multi-head matrix batching** (where 100 detectors run in a single microsecond matrix multiply on the shared vector), or design the **active-learning transcript labeling pipeline** for Clef/Jev?