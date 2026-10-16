# Latent lab playbook: which ideas help, where they fit, and how fast

Status 15 Oct 2026 (all trials finished; the Latent lab's "What holds up" section shows the same results). Companion to `latent-lab-findings.md` (the long record). This file is the short answer:
each idea we tried, what it is in plain terms, whether it helped, and the situations where a CPU (or a small GPU)
version can stand in for a full decision LLM (Clef Flash, Jev). Every number is measured on our published labelled sets
against the same test items Clef and Jev answered. Items marked *running* are still being measured.

**One-line summary.** A small embedding model plus a trained head per question roughly ties Clef on *fixed* tone and
text-type questions with enough examples, in milliseconds on CPU, and stays a few points below Jev on the sets with
trustworthy labels; on reading/judging it ties Jev, partly by learning each dataset's labelling habits. It does not answer *new* questions, reason across two texts, or recall world knowledge; those stay
with Clef/Jev.

## 0. Corrections after independent review (15 Oct 2026)

Three independent reviewers read the trial reports and scripts. Their corrections, verified against the saved data:
- The escalation figure (85% → 91%) was accuracy on the kept 70% only; the cascade is unmeasured.
- The tone lead over Clef/Jev rests on threat and headline sarcasm; on the 5 sets with trustworthy labels the small head
  is 83% vs Clef 84%, Jev 87%.
- A small NLI cross-encoder given SNLI as a real pair scores 92% with no training; the trial report had dropped it.
- The five angles with no labels already reach 80.2% on the 7 tone sets (Qwen 4B).
- Several "no gain" verdicts came from flawed setups (negated "no" descriptions, the whole pair replaced by "N/A" in bias
  correction, whitening fitted only on the labelled subset, a shared-encoder loss that pits detectors against each other).
  They are marked for retest rather than written off.

## 1. The ideas, one by one

Verdicts: **Helps** (beats the previous best beyond noise), **Modest** (real but a few points), **No** (no gain or worse),
**Running** (being measured).

| # | Idea | What it is | Result | Verdict |
|---|---|---|---|---|
| 1 | Cosine similarity, no training | Pick the answer whose description vector is closest to the text's vector | Small models near chance (50–55% tone); Qwen 4B 63% | No (as a classifier) |
| 2 | Bias correction | Subtract each answer's score for an empty input, so the model's built-in lean cancels | Qwen 4B tone 63% → 75% with no labels; hurts two-text questions (SNLI 82% → 56%) | Helps for zero-shot on single-text yes/no only |
| 3 | Asking from several angles | Same question five ways (original, opposite, rephrasings), scores combined | **No labels: 80.2% on the 7 tone sets (Qwen 4B), Clef 79%, Jev 81%**; 76% over 9 yes/no sets; mostly opposing biases cancelling. Not yet tried on the 0.6B | Helps (zero-shot, GPU) |
| 4 | Whitening | Remove the directions all vectors share | With a head: ties. Without labels: improves judging on all 18 models (+1 to +9), never combined with bias correction | Modest (zero-shot) |
| 5 | **Learned head (logistic regression)** | One weight per vector dimension, fitted on labelled examples; microseconds per question | The readout everything else is compared against | **Helps: the base of every result below** |
| 6 | Other readouts: LDA, prototypes, nearest neighbours, small MLP, "difference axis" | Alternative ways to draw the line between yes and no | None beats the logistic head beyond noise at any number of examples | No |
| 7 | **More examples per question** | Train each head on hundreds or thousands of examples instead of ~80 | e5-small tone 76% (80) → 86% (2,000); judging average with Qwen 0.6B 61% → 73% | **Helps: the biggest lever** |
| 8 | **Middle-layer vectors** | Read the vector from the middle of the model as well as the end; same single pass | +2 to +6 points; Qwen 0.6B layer 19 is the best judging feature found | **Helps (free)** |
| 9 | LLM-based embedder (Qwen3-Embedding 0.6B/4B) vs classic encoder (e5, bge) | Larger models that know more | Equal on tone; far better on two-text reasoning (SNLI 79% vs 61–64%) | Helps where reasoning matters |
| 10 | Static embeddings (Model2Vec potion) | A fixed vector per word, averaged; no layers | 80% tone with 2,000 examples at ~0.4 ms on CPU | Helps where speed matters most |
| 11 | **SetFit, one per detector** (adapt the encoder to the task with pairs of examples) | Contrastive fine-tuning of the small encoder (official `setfit`, standard settings), then a head; 13–55 s per detector on the GPU | Tone: 81% with 64 labels, **85–86% with 250** (frozen 82%, Clef 79%, Jev 81%). Judging: +6 to +11 at 250 (SNLI 40% → 68%) but 64–65% vs Jev 72.5%. No gain at 16 examples | **Helps with 64–250 labels**; costs one encoder pass per detector |
| 12 | One shared adapted encoder for all detectors | SetFit across all detectors at once, so one encode still feeds every head | Tone 5–7 points worse, but the test was flawed (pair loss across 11 detectors in one space, 1 seed, sarcastic tweets below chance). A standard multi-task fine-tune is untested | Inconclusive |
| 13 | **Teacher labels: Clef labels + a few human labels for the cut-off** | Clef labels thousands of texts; 20–50 human labels re-set Clef's yes/no line; a small model learns from the result | Clef labels alone: 70%. With the cut-off re-set: 81–82% tone (Clef 79%, Jev 81%); best recipe on 3 sets 85% vs Clef 69%. But it only **ties SetFit on 64 plain human labels**; SNLI student stays 11–15 points under Clef | Helps when human labels are scarcer than ~50–64 per detector |
| 14 | Small zero-shot models (NLI cross-encoders, GLiClass) | Read question and text together, no training | **Two texts given as a real pair: SNLI 92% with a ~140M NLI model, no training (Clef 84%, Jev 80%).** Tone 73%. The other judging sets were run with a broken input format | Helps for two-text questions; retest the rest |
| 15 | One general head for new questions | One probe trained on many other questions, applied to unseen ones | Tone/judging mix (~2,000): worse than cosine. World knowledge: Qwen 4B probe 74.5% vs cosine 49% and Clef 94%; flat from 1k to 12k training questions | No as a replacement; the knowledge is partly there (4B), not enough |
| 16 | Calibration and escalation | Make "80%" mean right 80% of the time; send the least confident cases to Clef | Heads are better calibrated than Clef/Jev (ECE .09 vs .15). On their most confident 70% they are 91% right; the remaining 30% (where the head is ~72% right) would go to Clef. The overall cascade accuracy has **not** been measured (an earlier version of this table said "lifts 85% → 91%", which was the kept 70% only) | Modest until the cascade is measured |

Deliberately not pursued: re-labelling or fine-tuning the decision LLM itself (out of scope by choice).

## 2. Honest audit: what holds up, what to expect in practice

- **No leakage on tone** (checked only there). Removing near-duplicates changed nothing. Possible same-corpus leakage on persuasion, dark patterns and manipulation was not checked.
- **The tone lead over Clef/Jev rests on two sets**: threat (Clef ranks well but its cut-off is off) and headline sarcasm (label = publication). Without them: small head 83%, Clef 84%, Jev 87%.
- **Calibration comparison is unfair to the LLMs**: the heads were trained in-domain, Clef/Jev are zero-shot.
- **Noise** figures cover item sampling only, not the choice of model, readout and layer, which was made on the same test items.
- **Tone is largely about word choice.** A plain word-count model (TF-IDF) reaches 83% with 2,000 examples; e5-small's
  advantage is needing far fewer examples (+8 points at 80) and picking up style cues (headline sarcasm +13).
- **Synthetic transcript-style text costs about 4 points** (not real ASR output): lowercase, no punctuation, filler words take tone from 85% to ~82%;
  sets whose cue is punctuation or casing drop most (headline sarcasm 93% → 76–80%).
- **Rare events are hard for everyone.** At 1% prevalence, about 1 in 3 flags is right at 80% recall for the small head,
  Clef and Jev alike. Plan on a second stage (escalation or human review) for rare-event detectors.
- **Some judging wins are label habits.** Dark patterns, manipulation and persuasion heads learn each dataset's labelling
  conventions; they will not transfer to our own detectors without our own labels.
- **Code is template matching.** Juliet/OWASP heads score 89–93% on sibling templates but ~72% when a weakness class is held out; TF-IDF matches them.
- **Where it fails:** questions that combine two texts with many hypotheses (contract clauses 56% vs Clef 69%), sarcastic
  tweets (62–66% vs Clef 80%, Jev 86%), and anything the head was not trained for.
- **Noise.** About ±2.5 points on group averages, ±8–12 on single sets (64–545 items per set).

## 3. Situations: when the small version is enough

| Situation | Use | Accuracy measured | Hardware and speed |
|---|---|---|---|
| Fixed tone/text-type detectors on live calls (anger, fear, threat, politeness, phishing) | e5-small (or bge-base) encoder, one encode per window, one head per detector | 7 sets 85% (Clef 79%, Jev 81%), but on the 5 sets with trustworthy labels 83% vs Clef 84%, Jev 87%; synthetic transcript noise −4. Sarcastic tweets (the demo's sarcasm detector) 65% vs Jev 86%: keep with Jev | CPU ~12 ms per window for **all** detectors together; heads ~1–5 µs each |
| Same, at the edge or at very high volume | Static potion model + heads | ~80% | CPU ~0.4 ms per window |
| Fixed reading/judging detectors (does B follow from A, fallacy) | Qwen3-Embedding-0.6B, layer 19 vector, one head per detector | 73% average (Clef 66%, Jev 71%, a tie with Jev); lead partly label habits; fails on contract clauses | Question is in the input, so **per detector**: GPU ~30 ms (2 GB), CPU 0.26–0.95 s |
| A new detector, a little labelling budget | Label 64–250 windows by hand; SetFit e5-small for that detector | Tone 81% (64) to 85–86% (250) | ~1 min training on GPU; then 11–18 ms CPU **per SetFit detector** per window (20 detectors ≈ 240–360 ms per voice) |
| A new detector, almost no labelling budget | Clef labels a few thousand of our own windows; 20–50 human labels re-set the cut-off | Tone 81–82% (Clef 79%); ties 64 hand labels | One-off Clef labelling (~30 calls/s locally); then same as the frozen-encoder row |
| Code security (memory bugs, web vulnerabilities) | Clef or Jev | Small heads reach 89–93% only on template siblings; with a whole weakness class held out they fall to ~72% (Clef 72%, Jev 79%), and a plain word-count model does as well, so it is template matching | Not a CPU candidate |
| World knowledge, open-ended or brand-new questions, images | Clef Flash or Jev | Clef 94%, Jev 91% on MMLU. One general probe on Qwen3-Embedding-4B (layer 24, all four options in the input, trained once on 12k questions from other subjects) reaches 74.5%; the 0.6B 52%; cosine 49%. More training data does not move it | GPU ~10 GB (Clef Q4) or hosted; the 4B probe needs ~10 GB and 25–50 ms per question, so it is not a CPU route |
| Anything uncertain from a small head | Escalate to Clef | Not yet measured as a cascade; the head is 91% right on its most confident 70% | Mixed |

## 4. The pipeline: from a decision LLM to a fast simple decision maker

1. **Define the detector**: the exact TypeSafe question and options.
2. **Collect windows**: our own transcript text, thousands of windows (unlabelled).
3. **Teacher pass**: Clef labels every window (soft probabilities kept), ~30 calls/s on our GPU.
4. **Human pass**: 20–50 windows labelled by a person: used only to set the cut-off and to check the teacher.
5. **Student**: either one frozen small encoder shared by all detectors plus one logistic head each (encode once, ~12 ms for all), or a SetFit-adapted encoder per detector (+3 to +4 points on tone, one encoder pass per detector). A single shared SetFit encoder was worse and is not recommended.
6. **Calibrate** the head's probabilities on held-out labelled windows.
7. **Serve** through `/v1/systemone`: encode each window once, run every head (a single matrix multiply), return typed answers;
   escalate low-confidence answers and questions without a head to Clef.
8. **Check** on a fresh set of real, human-labelled transcript windows before trusting the numbers in production.

Steps 3–4 are the measured part (tone 81–82%, SNLI 82%). Step 8 has not been done yet and is the number that decides production.

## 5. Still being measured

- CPU speed-ups with ONNX Runtime and OpenVINO (plain-PyTorch quiet timings are done: potion 0.3 ms, MiniLM 6 ms, e5-small/bge-small 11 ms short / 18 ms dialogue, bge-base 27 ms, Qwen3-Emb-0.6B 0.26 s / 0.95 s, 4B 1.9 s / 7.0 s).
- A fresh, human-labelled set of our own transcript windows.

Trial reports and scripts: `/tmp/.../scratchpad/trials/{T1..T6,T5b,W1..W4}/REPORT.md` (scratch, not in the repo).
