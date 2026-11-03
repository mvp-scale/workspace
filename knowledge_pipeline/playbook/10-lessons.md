# 10 · Lessons: where 32 GPU-hours went, and agent-token overruns

From the world-engine news classifier ledger. GPU-hours per run are partly recorded; "est." marks arithmetic from
quota checkpoints (L299, L303, L349, L405, L409).

## GPU-hours by job

| Job | GPU-h | Outcome | Lesson → rule |
|---|---|---|---|
| T39 a1/a2: first open-LLM teacher on Kaggle T4 | ~4.3 | Crash, then 4.2 h with no predictions (T4 shared-memory limit + prefix caching) | 5-minute smoke test on a new stack (ch08 r1) |
| T48: teacher prompt rounds v1–v8 | est. ~7 | Eight push-per-patch rounds; teacher later dropped | Iterate locally; remote runs for finished scripts (ch08 r2) |
| T39 a3: one 12k-token generation per article | 2.2 | Answered "this design fails": recall .37, loops | Short per-layer verify calls on CPU candidates (ch03 r6) |
| T39 v3: 14B/32B verify design | 3.7 (0.26 lost to missing `__main__` guard) | 32B passed 6/6 | Guard entry points (ch08 r8) |
| T40: 32B bulk labelling | ~8 | 219 articles; superseded next day by Haiku, 1,000 for $0.87 | Test the cheap teacher first (ch08 r3) |
| T55, T56, T62: student training | ~1 | Shipped student; 14 min lost to an import bug | Students are cheap; spend care on teachers and plumbing |
| T68: 32B judge for the consensus ruler | est. ~5 | Useful result, after a silent failed push, an assert crash, and two overlapping sessions (1.87 h over cap) | Push must fail loudly; one owner per GPU (ch08 r4, r5) |

**Summary:** about 3% of GPU time trained the models we ship. More than half went to runs that failed or
were superseded. With local GPUs, smoke tests and API teachers first, the same results would have taken an estimated
8–10 GPU-hours.

## Other failures and the rule each produced

| What happened | Rule |
|---|---|
| int8 option picked after seeing test scores (T61) | Pick rule fixed on dev and logged before test scoring (ch05, ch06) |
| A judge built from the student's own teacher couldn't discriminate (Silver205 EVENT layer) | The ruler must be independent of the student's teacher |
| 50 ruler articles overlapped another task's test set | Check split overlap across tasks before building a new set |
| Ignore regions applied to the wrong comparison inflated agreement to .999 | Self-check the harness: identical inputs → 1.0, unrelated → low (ch06 r7) |
| Event-noun prompt changed twice, failed both times; judges agree only .38 | Low agreement = fix the definition, not the prompt or model (ch02 r3) |
| Run-to-run sd (.02–.03) as large as the target gain (T63) | Measure run noise first; stop when the target is inside the noise |
| Latency budget set per article, model measured per window | State the unit of every speed number (ch07 r1) |
| Scorer sha differed between CRLF and LF copies | Hash a normalised file, or record both |
| Evidence kept only in an ignored folder couldn't be reproduced | Snapshot + sha manifest; verify from a clean clone |
| Agent rounds: 49M context tokens over 560 turns; a wave hit 34M against a 6M cap | Script plumbing, give exact paths, read ranges, hard token caps (best-practices A1–A6) |
| Longer input gave +.012 against a +.02 target | Don't spend GPU on one knob without a reason it should move the target |

### Failures from the world-state expert 1 build (2026-10-31 to 11-01; ledger L175 to L317)

- **More data stopped helping.** Topic did not move beyond noise from 20,000 to 36,000 labelled items; source name added +0.001 to +0.005 for condition, topic and story type (L233, L237, L245).
- **Third voters did not help.** Local Clef and hosted Jev reached AUC 0.77 to 0.81 against the Claude teachers on clear cases with six wordings each; training on their vote pulled the student toward them (L241 to L255).
- **A joint 38-plus-none softmax was worse than separate models** for presence (weighted AUC 0.734 vs 0.755, L283).
- **Squeezing an encoder into a static embedding kept none of its gain** (model2vec distil of bge-small: topic 0.813 vs 0.832 baseline, L294).
- **Dynamic int8 on the fine-tuned encoder cost 0.019 of topic top-2** against a 0.01 allowance (L297).
- **First fine-tune used one learning rate for encoder and new heads** and collapsed (condition top-1 0.046); heads need their own rate (L292, L296).
- **First ONNX export traced a padding constant** and differed from torch (cosine 0.93); only an equivalence check caught it (L303).
- **Reported numbers were measured on a skewed vote sample** (60 percent positive vs 18 percent in the stream) until re-weighted (L281).

### Process drift, 2026-11-03 (ledger L598 to L602; session notes)

| What drifted | Rule |
|---|---|
| "Loop" meant the scheduler, the pipeline and the improvement cycle at once; checks and groundwork read as progress | One meaning per word (README, Words we use). Open every update by naming the main-loop part it moves, or say "check" or "groundwork" |
| Days went to field checks, codebooks and labeller selection while the best built reader waited for a yes | Every round ends in a reader change or is tagged groundwork. No new check unless a round shows a label problem |
| A question the evidence had settled (codebook v2 or v3b) was offered to the owner as an open choice | Apply the evidence and say so; ask only what evidence cannot answer |
| The scheduler kept ticking after three ticks with nothing it could do | Stop the scheduler when every next step waits on the owner; restart on their answer |
| Pool run failed at start: the engine asked for 26.65 GiB of GPU, 24.0 GiB were free because two services held 7 GB | Size the GPU memory request to free memory at launch (`nvidia-smi` first), not to the model's usual setting |
| The heartbeat logged "done, 0 of 46,775" for that failed start | A job that ends with no progress is recorded as failed, never done (fixed in `beat_pool.py`) |

## What showed the process works (2026-11-03; figures are from the ledger, not recomputed)

- **A pre-registered rule stopped a tempting switch.** Qwen3.8-27B was 0.11 better on topic than the baseline but not higher on
  story type or presence; the rule needed 2 of 3, so Gemma 4 stayed. All three Qwen candidates failed it (L587, L598, L600).
- **A guess baseline changed a verdict.** Story type scored 87.5% against 87.0% for always saying "fact", so it was "Not yet"
  despite a good-looking agreement number (L492 to L495).
- **A clean holdout caught contamination.** The first run on all items gave 98% on story type; the 86 items dated after the
  training cutoff gave 92.5% (L502 to L506).
- **Pinning a setting kept a gain real.** The v3 presence gain needed Haiku to think; with thinking off, agreement fell from
  0.555 to 0.349 (L567). Every spec now pins thinking.
- **The ledger corrected its own cost estimate.** "About 30 of 70 USD" was wrong; 45.9 USD was recorded (L550).
- **A written stop rule held.** Three idle scheduler ticks ended in a stop, not a fourth.

## What worked and should be copied

- Frozen scorer and gold with shas printed in every run log; evaluators re-pulled outputs and matched byte for byte.
- Gates at 0.8 × IAA, judged on the bootstrap lower bound.
- CPU candidates + LLM verification: 6/6 gates at $0.75 per 1,000 articles.
- One pipeline kernel instead of many: 340 s → 72 s per batch.
- 4 processes × 1 thread: 5.94 vs 3.46 articles/s, identical output.
- A two-family consensus ruler on 205 articles: intervals 5.6× narrower than on 11 silver articles.
- Measuring correlation between signal sources before combining them (0.49–0.59 meant double counting).

- **Sparse word plus character n-grams beat a static embedding and structure flags** (+0.03 AUC) and read in 0.5 ms (L211).
- **A frozen small encoder lifted which-condition by +0.066 and topic by +0.054**; a cascade (linear always, encoder on about 1 in 3 items) keeps most of it at 9.3 ms mean (L289, L301, L316).
- **Training linear heads on the GPU was 620 times faster than scikit-learn lbfgs** at the same accuracy (703 s vs 1.1 s, L288).
- **Cap the encoder input by validation, not by the speed target**: 64 tokens cost nothing measurable and halved the tail (L309 to L312).
- **Write the prediction before the run and the stop rule before the loop** (L206 to L317): of 25 prediction notes, 15 score notes record at least one miss (counted from the ledger), and the misses were the useful part.
