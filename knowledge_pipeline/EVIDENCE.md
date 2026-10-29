# Evidence appendix: what each cited ledger and task ID says

The playbook, PRD, acceptance list, technique review and templates cite ledger lines (`L294`) and tasks (`T61`)
from this repo's `ledger.jsonl`. This page gives each cited ID one row: the finding and its numbers, with no
article text. That way a reader in another repo can follow a citation without the ledger.
It was built by grepping `knowledge_pipeline/` for `L\d+` and `T\d+` and then looking each ID up in `ledger.jsonl`.

**Not ledger IDs:** `L12` (in "MiniLM-L12", a model name) and `T4` (the NVIDIA T4 GPU on Kaggle). **Planned
tasks with no ledger lines yet:** `T70` (example card `agentic/examples/T70-student-v3.card.json`, student v3) and
`T71` (proposed in TECHNIQUE_REVIEW.md, an intermediate-model card).

**Terms.** *E-silver*: the frozen 11-article evaluation set (`esilver.json`, sha `ea728dcb`), scored by frozen
`score.py` `ffefe369` and `score_v2.py` `fba6ac95`. *Layers*: ENTITY (ENT), EVENT_NOUN (EN), EVENT_VERB (EV),
triggers (trig), TIME, QUANTITY (QTY). *Gate*: per-layer overlap-F1 floor of 0.8 × inter-annotator agreement:
ENT .739, EN .65, EV .754, trig .703, TIME .717, QTY .80. "6/6" means every layer passed. *MN-DS*: the public
news corpus used as the unlabelled pool (10,025 eligible articles after exclusions). *Student*: the 19.2M-parameter
4-layer encoder. *S5*: the reference CPU benchmark machine.

## Teacher labels

### T39: teacher dry run on the 11 E-silver articles (open LLMs on Kaggle)

| ID | Finding | Cited in |
|---|---|---|
| T39 | Task L198. First attempts (a1/a2) crashed, then ran 4.2 h with no predictions (T4 shared-memory limit plus prefix caching). Attempt v3 passed the gate with 32B-AWQ (L293). The first verdict failed on two literal misses (L294); the retry passed (L297 done, L298 verdict). | playbook/10 |
| L284 | Restart plan: CPU candidates (voters, spaCy/NER spans, noun lexicon), then short per-layer LLM verify-and-type calls instead of one 12k-token generation. Aimed at low recall (ENT R 0.37) and looping. 14B-AWQ and 32B-AWQ ran in parallel on the same 11 articles. | playbook/03 |
| L293 | v3 result (2×T4, vLLM 0.10.2, guided JSON), overlap F1. 32B-AWQ: ENT .866, EN .676, EV .936, trig .787, TIME .933, QTY .938, 6/6 (exact 5/6; EN exact .147). 14B-AWQ: 3/6. CPU candidates alone: .798/.459/.885/.732/.968/.833, 5/6. Span validity 1.0. Throughput: 32B 39 articles/GPU-h (25 GPU-h per 1,000), 14B 82 articles/GPU-h (12 GPU-h). With the v2 upstream pass: 178 and 55 GPU-h per 1,000. Used 3.7 GPU-h. | playbook/03 |
| L294 | Evaluator verdict **fail** even though the gate passed. It re-pulled all 3 kernel outputs: the reports were byte-identical and the frozen shas printed and matched. Two literal misses: the output path was not the specified folder, and there were no hours for the full 10,917-article pool (the constant was hard-coded at 10,275). Rates imply ~277 GPU-h (layers only) or ~1,944 GPU-h (with the upstream pass). | playbook/02 |

### T40: teacher labels at scale on MN-DS (32B on Kaggle)

| ID | Finding | Cited in |
|---|---|---|
| T40 | Task L199. Labelled 219 of 10,025 eligible articles in one week before the quota ran out (block L304). Dropped for T54 (L317): Haiku passed the gate at about $0.75 per 1,000 articles, against about 36 GPU-h per 1,000 for the 32B. The 219 labels were kept as an agreement check. | playbook/10 |
| L299 | Start: 32B-AWQ on gated layers, a CPU prep kernel per 500-article chunk, resumable GPU kernels. Quota at start: 17.84 h used, 12.16 h left. Plan: ~8.4 GPU-h, keep 3 h in reserve. | playbook/10 |
| L303 | Chunk c000 session 1 completed in 4.06 h but labelled only 96/500 articles (1,920/9,127 requests). 48,630 spans, 0 bad offsets, span-valid .982 after repair, 148 parse failures, ~26 articles per session-hour. 4.12 h of quota left, so no more sessions that week. | playbook/10 |

### T48: teacher prompt v2

| ID | Finding | Cited in |
|---|---|---|
| T48 | Attempt 1 failed (L269): the 14B model itself wrote 0/91 claim rows and 0/125 unused-entity rows; the 100% coverage came only from rule backfill. The retry added an effects pass with closed lists and one repair turn. That gave 91/91 claims and 123/123 unused entities written by the model, 0 backfill. Verdict pass (L281). The 7B model was unusable. | playbook/10 |

### T51: Claude Haiku batch teacher test

| ID | Finding | Cited in |
|---|---|---|
| T51 | Haiku (Batches, pass 1 only) on E-silver: ENT .711, EN .600, EV .816, trig .712, TIME .903, QTY .774, so 3/6 gates. Weak on recall (ENT R .57, EN R .47). Cost $0.026 total, $2.36 per 1,000 articles (prices unconfirmed). Verdict pass (L309) as a test; not a 32B replacement as-is. | playbook/03 |

### T54: Haiku v3 labels 1,000 MN-DS articles

| ID | Finding | Cited in |
|---|---|---|
| T54 | 4 batches × 250: 2,000/2,000 requests succeeded, parse OK 2,000/2,000, span validity .9905. Overlap with the 219 32B labels: ENT .843, EN .587, EV .934, trig .848, TIME .885, QTY .881. Spend $0.865 per 1,000 articles. Excluded E-silver, gold_test and hold-out publishers. Labels went to a private Kaggle dataset. Verdict pass 5/5 (L322). | playbook/03 |

### T62: active learning round 1

| ID | Finding | Cited in |
|---|---|---|
| T62 | Pool 9,025. Picked the 1,000 least-sure articles (mean token entropy) plus 1,000 random (1,888 unique), labelled by Haiku for $1.42. Retrained student, E-silver overlap ENT/EN/EV: base .882/.697/.901, +least-sure .874/.697/.910, +random .865/.716/.900. Least-sure minus random, 95% bootstrap: every interval includes 0, and neither set beat the base. Verdict pass (L373). | playbook/03, playbook/10 |
| L349 | Owner asked to keep looping. Round-3 Haiku spend capped at $2.50 (T62) plus $0.50 (T63), within the $100 autonomy cap. About 3 Kaggle GPU-h left that week, so GPU work stayed small. | playbook/10 |

### T63: event-noun teacher prompt fix

| ID | Finding | Cited in |
|---|---|---|
| T63 | Target: +.03 EN overlap. Prompt n1: +.013 against the same-day control (run noise .053), verdict fail (L362). Prompt n2: mean .745 (sd .020) against v3 at .734 (sd .034), +.011, or +.027 against same-day controls. Verdict fail (L366). The target was about 1 noun of 32 references, below run noise. | playbook/10 |

### T68: pass-1 ruler and trigger precision

| ID | Finding | Cited in |
|---|---|---|
| T68 | Task L402 (owner: 3 h, use the Kaggle budget). (A) A CPU word-list relabel of ENTITY to EVENT_NOUN was rejected: spurious spans went from 14 to 70–99 and every interval was below 0 (L403). (B) Haiku event-coreference merges on noun triggers raised trigger overlap from .793 to .826 on E-silver and from .771 to .787 on dev, for $0.009 (L404). (C) Two-judge consensus ruler (L407, L408). Definition of done: 1 met, 2 not met (nouns), 3 met on consensus only. | playbook/06, playbook/10, PRD |
| L405 | The first push of the 32B judge kernel did not register, because the old `kaggle_run.sh` hid push errors. Re-pushed and ran within the 3.18 GPU-h left. Coreference productization deferred: it needs Haiku labels on 1,000 articles (~$0.4) and a student merge output. | playbook/10 |
| L407 | Qwen2.5-32B judge answered 759/759 EVENT requests on 205 articles. Haiku vs Qwen per candidate: verbs agree .887 (kappa .51), nouns agree .768 (kappa .27). Ruler = both judges say yes (9,100 spans). Only one non-Claude judge was available, because the second was blocked by phone verification (403). | PRD |
| L408 | (Not cited directly; supports T68.) Student v2 against the consensus ruler, lower 95% bound: EV overlap .961, triggers .878, both pass. EN .333 < .65 fails, but the judges agree only .376 on nouns, so the ruler can't confirm the noun gate. Trigger precision .808. | |
| L409 | Fixed consensus bugs: per-judge pairs that ignored split regions had made Haiku vs Qwen read .999. `kaggle_run.sh` now requires "successfully pushed", exits on dropped sources, and waits for queued/running. Two judge sessions overlapped and used 31.87 of 30 GPU-h, leaving none until reset. | playbook/10 |

## Student model, quantization, ship

### T55: CPU student v1 on 1,000 labels

| ID | Finding | Cited in |
|---|---|---|
| T55 | all-MiniLM-L12-v2 cut to 4 layers (19.2M params), 5 BIO heads, 256-token windows. 8 min on a T4. Learning curve n250/n500/n1000: n1000 gave ENT .860, EN .716, EV .906, trig .790, TIME .938, QTY .811 (6/6). The system with CPU TIME/QTY rules was 6/6 in fp32 and int8. int8 latency p50 24.6 ms, p99 34.0 ms per 256-token window (4 threads). Verdict pass after retry (L329). | playbook/10 |
| L325 | First verdict **fail 4/5** on a literal miss: the curve stopped at 900 items, not 1,000. Kernel outputs were re-pulled and matched; the frozen shas matched; no API spend; no text, labels or models in git. | TECHNIQUE_REVIEW |

### T56: student v2, overlapping entities

| ID | Finding | Cited in |
|---|---|---|
| T56 | A second ENTITY BIO channel cut dropped overlapping entity spans from 14,885 to 640 (of 97,284). E-silver v2 fp32: ENT .882, EN .697, EV .901, trig .790, TIME .938, QTY .833 (6/6). int8: 6/6, p50 24.3 ms, p99 36.7 ms. The v1 control reproduced T55 exactly. Training kernel took 8.5 min. Verdict pass (L343). Watch item: int8 EN fell against v1 int8. | playbook/10 |

### T61: int8 without the accuracy loss

| ID | Finding | Cited in |
|---|---|---|
| T61 | 9 int8 options against fp32 (ENT .882). Per-tensor int8 lost ENT (.842). The per-channel pick (D1) was chosen after looking at E-silver, so it was eval-set selection; verdict fail (L368). Retry: the pick rule was fixed on dev before scoring. Chose int8 QKV/attention with fp32 MatMul: max layer drop .0007, system 6/6. p50 29.8 ms, p99 44.4 ms (70.8 MB, sha `2bade18d`). Speed gain over fp32 (32.0 ms) was small. Verdict pass (L375). | playbook/05, playbook/10, PRD |

### T65: shipped classifier as one CPU service

| ID | Finding | Cited in |
|---|---|---|
| T65 | Task L379. Packaged the int8 student and the CPU TIME/QTY rules as one entry point, with a clean-environment Kaggle CPU test (L382). No done line, because the worker was stopped (L390). The result was recorded as L393. | playbook/09 |
| L393 | Criteria c1, c2 and c4 passed. c3 speed **failed**: 3.05 articles/s, p99 1.57 s (target ≥ 10/s, ≤ 1 s). E-silver 6/6, identical to T61. Routed to the speed stage. | PRD |

### T67: event nouns and triggers, diagnose and fix cheaply

| ID | Finding | Cited in |
|---|---|---|
| T67 | Kaggle CPU runs at $0. The student tagged the noun head while gold marked the phrase. Parser-free rule F1t raised EN exact on E-silver from .121 to .545, and on dev from .302 to .443 (the dev interval includes 0). spaCy cost 78 ms per article as shipped, +15 ms with the tagger (F1t), +54 ms with the parser. The owner chose to ship F1t (L401). Shipped v2 kept 6/6 gates and ran at 4.82 articles/s end to end with 4 workers. | playbook/09, TECHNIQUE_REVIEW |

### T69: alternatives benchmark (alt-bench v1)

| ID | Finding | Cited in |
|---|---|---|
| T69 | No task line in the ledger; the result is L411. | playbook/04, TECHNIQUE_REVIEW |
| L411 | Kaggle CPU (4 vCPU Xeon, no VNNI). ENT on 2 E-silver articles, student exact .728 / overlap .882. Best GLiNER (bi-edge v2.0): .336/.718, 2.9× slower. GLiNER2-base: .699 overlap, 13× slower. GLiNER-small int8 dropped to .361. No zero-shot model replaces the student; GLiNER is useful as a teacher only. OpenVINO gave no fp32 gain, was worse in int8 without VNNI, and can't load the ORT-fused int8. Ettin-17M int8: 44 ms per window (0.57× the student; quality untested). Ettin-32M was slower. spaCy: 51–102 ms per article. wink-nlp POS: 5.5 ms. | PRD, README |

## Process (no single task)

| ID | Finding | Cited in |
|---|---|---|
| L390 | Wave W15 run stopped by the owner at ~34M context tokens against a 6M cap. None of T64–T66 passed. Causes: briefs gave pointers instead of exact paths (workers took 52–64 turns), whole-file reads grew context from 38k to 130k per turn, and the token cap was advisory only. Fix: exact paths, range reads, a hard cap at launch, and retries that reuse committed artifacts. | ACCEPTANCE |
