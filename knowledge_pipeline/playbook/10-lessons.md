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

## What worked and should be copied

- Frozen scorer and gold with shas printed in every run log; evaluators re-pulled outputs and matched byte for byte.
- Gates at 0.8 × IAA, judged on the bootstrap lower bound.
- CPU candidates + LLM verification: 6/6 gates at $0.75 per 1,000 articles.
- One pipeline kernel instead of many: 340 s → 72 s per batch.
- 4 processes × 1 thread: 5.94 vs 3.46 articles/s, identical output.
- A two-family consensus ruler on 205 articles: intervals 5.6× narrower than on 11 silver articles.
- Measuring correlation between signal sources before combining them (0.49–0.59 meant double counting).
