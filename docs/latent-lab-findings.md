# Embedding-based typed classifiers: what works, what doesn't, how we got here

Status 15 Oct 2026. Written to be reviewed by someone who has not seen the conversation. Every number below was measured
on this machine unless marked otherwise; the scripts and raw results are listed at the end. Numbers marked *pending* are
still being computed.

## The goal

We want a "System One" typed classifier: given a text window (a live call transcript) and a question, return
probabilities in the TypeSafe `POST /v1/systemone` format (`noul` = P(yes), `choice` = one probability per label,
`score` = one per ordinal level). Today this is done by decision LLMs: Jev (hosted, TypeSafe) and Clef Flash (Cloudflare,
Qwen3.5-9B with a trained "joint schema head", about 9.7 GB of GPU memory at 4-bit on our server). The goal is
something comparable in accuracy that runs on a plain CPU in milliseconds, or on a GPU with little memory, by
building on embedding vectors plus arithmetic instead of a decision LLM.

Hardware: CPU Intel i9-10900K (10 cores, AVX2, no AVX-512, no VNNI); GPU RTX 5090 (32 GB).

## Terms

- **Embedding model**: text in, one vector out. Classic ones are encoder-only (BERT style: MiniLM, bge, e5).
  Recent strong ones are LLMs turned into embedders (Qwen3-Embedding is Qwen3 with the text-writing layer removed,
  vector = last hidden state at the final token). **Static** embeddings (Model2Vec "potion") are a fixed vector per
  word, averaged: no layers read context.
- **Readout**: the arithmetic that turns vectors into an answer. *Cosine*: pick the option whose description vector
  is closest. *Bias correction* (contextual calibration, Zhao et al. 2021): subtract each option's score for an empty
  input. *Whitening*: remove the directions all vectors share (from unlabelled vectors). *Learned head*: logistic
  regression on the vectors, one weight per dimension, fitted on labelled examples.
- **Angles**: the same question asked five ways (original, opposite, two rephrasings, one adjacent question), scores
  combined. In the literature: prompt ensembling / test-time augmentation, plus a consistency check (Contrast-Consistent
  Search, Burns et al. 2022).

## The test data

21 published labelled probe sets, 64 to 545 items each, built from public datasets (not written by us):
- **Tone and text type** (7, yes/no): anger and fear (GoEmotions), politeness (Stanford Politeness Corpus), threat
  (Civil Comments), phishing (ealvaradob/phishing-dataset), sarcasm in headlines (Onion vs HuffPost) and in tweets (iSarcasmEval).
- **Reading and judging** (6): SNLI entailment, persuasion strategy (7 labels), logical fallacy (8), dark-pattern type (7),
  ContractNLI clause check (3), manipulation in dialogue (MentalManip, yes/no).
- **Code security** (2): C memory bugs (NIST Juliet), web vulnerabilities (OWASP Benchmark).
- **World knowledge** (6): MMLU subjects.

Clef Flash and Jev answers on exactly the same items are stored from earlier runs. On the 7 tone sets they average
**79% (Clef Flash)** and **81% (Jev)**; on MMLU 94% (Clef Flash) and 92% (Jev).

With ~100 items per set, any single set's accuracy carries about ±8 to 12 points of noise; group averages are steadier.

## How we went about it (in order)

1. **Recon.** No published small model does general typed decisions well: on the public JevBench board every
   embedding/encoder system scores under 16 on a scale where Jev scores 64. Nobody has published a smaller Clef; only
   quantizations of the 9B exist.
2. **Zero-shot embeddings, cosine readout** (Qwen3-Embedding 0.6B/4B, MiniLM). The 4B, with the question put into the
   input, matched Clef on some tone sets; MiniLM was near chance.
3. **Is the answer in the vectors at all?** A learned head (5-fold, each item scored by a fit that never saw it) on
   Qwen3-Embedding-4B vectors reached 84% on tone vs Clef 79%, 71% on judging vs 66%, but only 39% on MMLU vs 94%. (An earlier summary in our working notes said 87% and 69%; that was an arithmetic slip, corrected here.)
   A single head trained on the *other* sets and applied to a new one did worse than cosine (too little data).
4. **Several angles** (Qwen 4B, 9 yes/no sets, wordings fixed in `probes/angles.json` before scoring): one question
   60% → bias-corrected 71% → all five angles averaged, no labels, 76% → five angles with five learned weights 80%
   (Clef 77% on these nine). The angles are highly correlated (0.8 to 0.95); most of the gain came from opposing biases
   of the original and opposite questions cancelling, not from new information.
5. **Correction after review**: we had tested only one small model and only with cosine, then generalised. We ran
   17 embedding models (8M to 4B) through the same readouts.
6. **More examples per question**: the ~80 training examples per set in the 5-fold test were the bottleneck. We built
   pools of ~2,000 extra labelled examples per tone set from the same source datasets with the same labelling rule
   (probe texts excluded), trained heads on 80 / 250 / 1,000 / all of them, and tested on the probe items.

## What works

### Small and static models, given enough examples, reach Clef and Jev on tone and text type

Tone-set average accuracy, head trained on N pool examples, tested on the probe items. Input = the text alone
(no question), so one encode per window can feed every detector's head.

| Model | Size | CPU per call* | N=80 | N=250 | N=1,000 | all (~2,000) |
|---|---|---|---|---|---|---|
| potion-base-8M (static) | 8M | 0.4 ms | 72% | 76% | 79% | 80% |
| potion-base-32M (static) | 32M | 0.4 ms | 73% | 76% | 80% | 80% |
| all-MiniLM-L6-v2 | 23M | 6 ms | 73% | 76% | 79% | 81% |
| bge-small-en-v1.5 | 33M | 11 ms | 74% | 76% | 81% | 82% |
| **e5-small-v2** | 33M | 12 ms | 76% | 80% | 84% | **86%** |
| bge-base-en-v1.5 | 109M | 28 ms | 78% | 80% | 83% | 85% |
| gte-modernbert-base | 149M | 67 ms | 77% | 79% | 82% | 82% |
| bge-large, multilingual-e5-large-instruct, Qwen3-Emb 0.6B, Qwen3-Emb 4B | | | *pending* | | | |
| Clef Flash 9B (zero-shot, GPU) | | | | | | 79% |
| Jev (zero-shot, hosted) | | | | | | 81% |

\* CPU per call: plain PyTorch, untuned, option vectors cached; measured while other jobs ran, *pending a quiet re-measure*.

### The ranking with few examples (5-fold, ~80 per set)

Learned head, average over the group. CPU ms for a short comment (same caveat as above).

| Model | Tone | Judging | Code | MMLU | CPU ms |
|---|---|---|---|---|---|
| potion-base-8M / 32M | 62% / 69% | 42% / 48% | 44% / 43% | 27% / 29% | 0.4 |
| all-MiniLM-L6-v2 | 64% | 43% | 37% | 28% | 6 |
| bge-small / e5-small | 67% / 67% | 42% / 45% | 37% | 29% | 11 to 12 |
| bge-base / e5-base | 71% / 71% | 44% / 43% | 38% / 48% | 30 to 32% | 25 to 28 |
| gte-modernbert-base | 69% | 47% | 48% | 30% | 67 |
| bge-large / mxbai-large | 69% / 68% | 47% / 48% | 38% / 40% | 34% | 90 / 153 |
| multilingual-e5-large-instruct | 74% | 52% | 43% | 30% | 213 |
| Qwen3-Embedding-0.6B | 81% | 57% | 60% | 33% | 260 (measured alone) |
| Qwen3-Embedding-4B | 84% | 71% | 75% | 39% | 1,900 (measured alone) |
| Clef Flash | 79% | 66% | 72% | 94% | GPU |
| Jev | 81% | 71% | 79% | 92% | hosted |

With few examples, bigger LLM-based embedders win clearly. With ~2,000 examples, the small ones catch up on tone.

### Label-free improvements that help

- **Bias correction** lifts zero-shot cosine on most tone sets (Qwen 4B tone 63% → 75%; phishing 50% → 84%;
  iSarcasm 53% → 81%).
- **Asking the opposite question too** and averaging is the single cheapest label-free gain on yes/no questions
  (Qwen 4B, 9 sets: 71% → 76% with all five angles).

### Memory and speed

| Model | GPU memory (measured) | GPU per call | CPU per call (measured alone) |
|---|---|---|---|
| Qwen3-Embedding-0.6B | 1.8 GB | 31 ms | 0.26 s short / 0.97 s dialogue |
| Qwen3-Embedding-4B (bf16) | 8.0 GB idle, ~9 GB in use | 36 ms | 1.9 s / 7.3 s |
| e5-small / bge-small / MiniLM | under 0.5 GB | ~4 ms | ~6 to 20 ms (pending re-measure) |
| potion (static) | ~0.1 GB | | ~0.4 ms |
| Clef Flash Q4 (for reference) | 9.7 GB | 46 ms (llama.cpp) | |

## What does not work

- **Zero-shot cosine on small models**: near chance (50 to 55% on tone). Cosine measures "about the same thing",
  not "true for this text"; negation and question-answering are lost.
- **World knowledge** (MMLU): no embedding model, no readout, gets close (best 39% vs Clef 94%). The knowledge is not
  in a single pooled vector.
- **Reading-and-judging tasks** on small models: 38 to 52% with ~80 examples, versus Clef 66%. Only Qwen 4B (71%)
  reaches the decision models. Manipulation in dialogue stays near 55 to 66% for every model, Clef and Jev included.
- **One general head for new questions** (trained on other sets, applied to an unseen one): worse than cosine with
  our ~2,000 mixed examples. This is the part Jev-class models actually solve (Clef's head was trained on large
  synthetic data), and we have not reproduced it.
- **Bias correction on two-text questions** (SNLI, contract clauses): it hurts (82% → 56%, 56% → 47%), because an empty
  input is not a neutral reference there. It must be enabled per question, by measurement.
- **Qwen3-Embedding-4B on CPU**: accurate but 2 to 7 s per call.

## What the comparison does and does not show

- The small models are **trained per question**; Clef and Jev answer **zero-shot**. A trained small head matching a
  zero-shot 9B model on a fixed detector is the useful result for us, but it is not "a small model that does what Jev does".
  A new question still needs either labelled examples or the big model.
- The extra examples come **from the same source datasets** as the test items (different rows, same labelling rule).
  That is in-distribution; accuracy on real call transcripts, where the detectors actually run, is untested.
- For our own detectors there are no human labels; the plan is to have Clef (or Jev) label our own transcripts and train
  the heads on those labels. **Untested**: whether heads trained on teacher labels match heads trained on human labels.
- Sarcasm-in-headlines labels come from the publication (Onion vs HuffPost), not from intent annotation.
- CPU speeds for the small models were measured while other jobs used the CPU; a quiet re-measure is pending.
  We have not tried ONNX Runtime or OpenVINO, which typically speed up these encoders on CPU (int8 may be slower on
  this AVX2 CPU without VNNI).

## The design this points to

1. One small encoder (e5-small or bge-small class, or a static model) encodes each transcript window **once**, on CPU.
2. Each fixed detector has its own tiny head (one weight per dimension), trained on a few thousand examples, labelled
   by Clef/Jev on our own transcripts or taken from public datasets.
3. Probabilities are calibrated (temperature/Platt scaling) and returned in the TypeSafe format; uncertain cases
   (head near 0.5, or disagreeing angles) can be escalated.
4. Anything without a head (new questions, reasoning, world knowledge, images) goes to Clef Flash behind the same endpoint.

## Open questions we would like a second opinion on

1. Is there a method that gives **zero-shot** quality (new questions, no examples) from a small embedding model? We tried
   cosine, bias correction, whitening, angles and one general head; only the per-question heads reach the decision models.
2. Are there better readouts than a linear head on one pooled vector, at millisecond CPU cost: token-level vectors
   (late interaction, ColBERT style), a small cross-encoder or NLI model, mid-layer hidden states of a small LLM,
   SetFit-style fine-tuning of the encoder?
3. How to make teacher labels (Clef/Jev on our transcripts) trustworthy enough to train heads on: soft labels vs hard,
   agreement filtering, how many per detector?
4. How to calibrate the final probabilities so that 80% means right 80% of the time, and how to decide when to escalate.
5. CPU runtime choices on an AVX2 desktop CPU (ONNX, OpenVINO, int8 or not, threads, window length).
6. Anything in the evaluation that makes these numbers look better than they will be on real transcripts.

## Where everything is

- Page: `/latent` in the demo console (`demo/latent.html`), currently served at http://127.0.0.1:8101/latent.
- Scripts (`probes/`): `embed_zeroshot.py` (first zero-shot test), `embed_readouts.py` (cosine, whitened, universal and
  learned readouts on Qwen 4B), `latent_angles.py` + `angles.json` (five angles), `embed_sweep.py` (17 models, same
  readouts), `tone_pools.py` (extra examples), `embed_curve.py` (more-examples curves), `embed_timing.py` (CPU timing),
  `latent_export.py` (page data).
- Results (`data/embed-zs/`): `sweep/<model>.json`, `curve/<model>.json`, `vectors/<model>/`, `latent/<model>/`, `pools/`.
- Probe sets and their sources/licences: `probes/v2/*.jsonl` and `*.md`.
