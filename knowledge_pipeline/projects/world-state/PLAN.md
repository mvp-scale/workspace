# World-state CPU reader: the whole plan

Written 2026-10-29. Revised at the end of every phase (see "End-of-phase update routine"). Terms:
**teacher** = the LLM that writes training labels (Claude Haiku 5.5). **student** = the small CPU model we train.
**gold** = items labelled by people, used as the answer key. **IAA** (inter-annotator agreement) = how often two
independent labellers agree; it sets the bar, because a model cannot be judged more exactly than people agree.
**gate** = pass line per layer = 0.8 × IAA, judged on the low end of a 95% interval (ACCEPTANCE M1).
**layer** = one output: TOPIC (49), STORY_TYPE (4), CONDITIONS (38 conditions × up/down), LEVEL (5 sizes).

## The plan on one page

**Who writes the missing code, and when.** About 13 new `pipeline.py` stages and a pseudo-span adapter do not exist yet. Claude writes each one at the start of the phase that needs it, with unit tests and an MM3 check on the code, and shows it to the owner before the phase's card runs. Nothing paid runs on unwritten or unchecked code.

Flow: freeze → guideline + human gold → agreement → qualify teacher → free CPU triage → (candidates, only if
needed) → pilot 1,000 → bulk (capped) → export to Kaggle → train student → score once → speed → ship decision.

**How the names fit (added 2026-10-30).** A **phase** and a **ledger task** are the same thing with two names: P3 is T4 in the ledger and the viewer (the ledger needs T-numbers and started at T1, so a task number is its phase number plus one). A **card** is the separate budget form for a phase that spends money or GPU time (`cards/T02.json`); the "T01", "T02" next to a phase below are card files, not ledger tasks. T14 is the wave loop, an extra task that belongs to no single phase.

| Phase | Ledger task | Owner | Cost ($ / Kaggle GPU-h) | Exit gate | Status |
|---|---|---|---|---|---|
| P0 Freeze, cards, targets | T1 | Claude; owner signs targets | 0 / 0 | R1, R3, S1 decision line | ready |
| P1 Guideline v2 + human gold | T2 | Owner + 1 person; Claude drafts | 0 / 0 (~5 person-h) | D3, D1 (human subset) | needs owner |
| P2 Agreement (IAA), card T01 | T3 | Claude | ≤ 1 / 0 | D1, D2 | not started |
| P3 Teacher qualification, T02 | T4 | Claude | 0 / 0 (reuses P2) | D4, D5 | not started |
| P4 Free CPU triage, T03 | T5 | Claude | 0 / 0 | D3 overlap check | not started |
| P5 Candidates (verify mode) | none (conditional) | Claude | 0 / 0 | skip unless P3 fails CONDITIONS | conditional |
| P6 Pilot 1,000, T04 | T6 | Claude; owner approves $ | ≤ 1.5 / 0 | R2, R5, D6 | not started |
| P7 Bulk, T05 (+ Sonnet slice T06) | T7, T8 (vote) | Claude; owner approves $ | ≤ 20 (+ ≤ 25) / 0 | R5, D6 | not started |
| P8 Export to Kaggle, T07 | T9 | Claude | 0 / 0 | D3 split manifest, R3 | not started |
| P9 Train student, T08 | T10 | Claude | 0 / ≤ 3 | M3, M4, M6, M8 | not started |
| P10 Score once, T09 | T11 | Claude + evaluator | 0 / 0 | M1, M2, R6 | not started |
| P11 Speed, T10 | T12 | Claude | 0 / 0 (local CPU) | M5 | not started |
| P12 Ship decision, T11 | T13 | Owner | 0 / 0 | M7, M9 | not started |

**Money ($190 Anthropic credit).** Planned $61.5: P2 $1, P6 $1.5, P7 bulk $20, P7 Sonnet slice $25 (only if
needed), one guideline re-label round $10, hosted evaluator tokens $4. **Reserve $128.5**, locked until an owner
decision line releases it. **Kaggle GPU:** 19.66 h left until the reset at 2026-10-31 00:00 UTC, shared with the
older project. This project caps itself at 3 GPU-h total and 4 GPU-h per week, and checks the quota page before
every push. **Time:** no job runs unattended over 1 hour; every run has a stop armed at launch.

## Layers (what the finished service is, 2026-10-29)

| Layer | What it does | Built from |
|---|---|---|
| L0 Intake | Takes an article: headline and description now, body later | news queue; bodies tested on 1,000 items after the first model |
| L1 Extraction | Entities, dates, numbers, change-verbs, who-did-what, in milliseconds | compromise, wink-nlp, spaCy, and the owner's relationship engine when shared; also proposes cues and votes at labelling time |
| L2 Reader | One CPU model answers many questions in one pass: topic, story type, conditions with direction, size. Target: all questions under 50 ms per item on one thread | shared small encoder with a head per question |
| L3 Impact | Conditions → people's states → decisions → places | the World engine's existing arithmetic |
| L4 Learning loop | Teachers label (Claude, Jev, Clef), agreement sets the bar, students retrain, this plan is revised each phase | P1 to P12 below |

The model does not take L1 output as input in the first version (a later variant, three seeds). The finished service returns L1 structure plus L2 labels.

## Blockers (living list; update at the end of every phase)

| # | Blocker | Blocks | Who clears it | Status |
|---|---|---|---|---|
| 1 | Answers to the 8 owner decisions (the bar change, #4, matters most) | starting P0 | Owner | open |
| 2 | ~~People to confirm the provisional bar~~ | none | none | dropped 2026-10-31: owner removed human gold for good; the bar stays layered agreement, reported as agreement, never accuracy |
| 3 | Workspace monthly spend limit not set in the Console | any paid phase (P2, P6, P7) | Owner | closed 2026-10-30: $100 monthly limit confirmed in Console (owner screenshot), $0.00 spent |
| 4 | About 13 pipeline stages and a pseudo-span adapter are unwritten | each phase's card | Claude writes each at the start of its phase, shows it, MM3-checks it | open |
| 5 | Gold is small for rare conditions (about 5 positives each in the 2,000) | a clear pass or fail on CONDITIONS at P10 | Decide at P1: pool the conditions or rate more items | risk |
| 6 | Console agents cannot see our files; no hand-off is designed | using the evaluator and teacher agents (not batch labelling) | Claude designs and tests it with synthetic data in P0 | open |
| 7 | The launch hook misses `python pipeline.py pilot/bulk`; the card checker skips schema checks | enforcing "no card, no spend" | Claude: each paid stage runs the card checker itself | workaround |
| 8 | Four stored keys (TypeSafe, R2, Context7, ngrok) have hosts the sandbox cannot reach; Kaggle is shared with BitMob | nothing today | Owner, if wanted | parked |

## Contradictions resolved (from the reviews, each checked against the source)

1. **Gate before bulk.** CONTEXT ran the teacher batch (E) before the gate (F). Now: P2 IAA → P3 D4 → P6 → P7
   (kit/teacher/README.md: "Bulk only after teacher_gate.json says PASS").
2. **Sonnet slice vs a Haiku-only spec.** Sonnet is the same family as Haiku, so it is not the second family. It is
   step 3 of the kit's teacher order: used only on a layer Haiku fails at P3, after Sonnet itself passes D4 on the
   same gold. Its own spec file (`specs/world_state_v1_sonnet.json`), never a silent model swap.
3. **Abstain / unknown.** The spec had no "unknown" for conditions (5 levels, minor to extreme). Guideline v2 adds
   direction `unclear` and level `unknown`. The student never trains on them as positives; the scorer counts them.
4. **Kaggle first, not local GPU.** The kit says local 5090 first (agentic/README.md:75); the owner rule wins.
   Student training runs on Kaggle T4 (`kaggle-gpu`); the local GPU is not used. No new Clef runs are needed:
   Clef labels for the 300 and the 2,000 already exist.
5. **Evaluator and teacher from different families.** The answer key (the "ruler") is human gold, never Haiku
   output (D5). Clef (a Cloudflare model, demo/models.json:16) is the second model family for CONDITIONS. The
   evaluator agent only re-runs scripts and checks numbers (R6); it never judges labels, so being Claude is allowed.
   Code checks use MM3 with local Clef only (no hosted Jev).
6. **Test items used for the teacher.** Qualifying a teacher on gold is the kit's D4, but qualify.py:9 forbids the
   student's final test split. So gold has two disjoint parts: **gold-Q** (50 items from the 300, for IAA and D4)
   and **gold-T** (100 items from the other 1,700 of the frozen 2,000, used once at P10). No item from the 2,000
   or its near-duplicates ever enters training.
7. **Our "gold" was Clef-labelled.** The frozen 2,000 are Clef answers, not human ones (D3 fails). P1 adds people.
   Clef numbers stay as a secondary readout ("agrees with Clef"), never as the gate.
8. **Launch hook does not see `python pipeline.py pilot/bulk`** (pre_launch.mjs:17-27). Every new paid stage runs
   `check_card.mjs` itself and refuses on a FAIL; we also prefix paid commands with `CARD=cards/T0x.json`.
9. **qualify.py and compare.py score spans only.** Our labels are categories. Adapter: each label becomes a
   pseudo-span (start 0, end 1, label `cond:direction` etc.), so the kit's scorers run unchanged.

## TECHNIQUE_REVIEW items: adopt or not, and when

- #3 one encoder, all heads: **adopt in P9** (one multi-label head over topic, story type, condition:direction).
- #5 Ettin-17M backbone: **adopt in P9** as the second variant beside MiniLM-4L.
- #2 label far more: **test in P9** with a learning curve (25/50/100% of the pool). T62 found 1,000 extra labels
  did not help (EVIDENCE.md:60), so more labels is not assumed.
- #1 two-stage soft-label distillation: **defer**. Only after P10, only if the learning curve still rises and a
  layer fails; new card with its own bar. Labels, not the model, were the limit (LESSONS_LEARNED D, F-0133).
- #4 static-embedding triage tier at runtime: **no**. Items are ~57 tokens, one window; little to save, recall risk.
- SetFit for the rarest conditions: **after P10**, only for conditions with too few positives.

## Phases

### P0 · Freeze, cards, targets (no card: no compute or spend)
- Goal: every input pinned by sha; targets signed; new pipeline stages written and checked.
- Entry: this plan approved.
- Steps: `python pipeline.py status`; `python pipeline.py spec`; `python pipeline.py dry 1000`. Add stages to
  pipeline.py: `freeze`, `goldsheet`, `iaa`, `qualify`, `triage`, `sample`, `label --items F --cap USD --yes`
  (passes `--max-wait 3600`, `--chunk 5000`), `export`, `baseline`, `train`, `score`, `speed`, `ship`. Each paid
  stage calls check_card first. Run `python pipeline.py freeze` → `runs/p0/freeze.json` (sha8 of pool, pilot300,
  test 2,000, spec, kit scorers). Start the project ledger:
  `node ../../kit/ops/ledger/ledger.mjs append ledger.jsonl '{"kind":"task",...}'`, one task line per card.
- Exit: `runs/p0/freeze.json`; MM3 (local Clef) verdict on the new stages; owner decision line on targets (R1, S1).
- Caps: $0, 0 GPU-h, 1.5M agent tokens. Stop: MM3 fails twice on the same stage → owner. Rollback: git revert.
- Predict: "new stages pass MM3 on the first or second try". Score: number of MM3 rounds.
- Learn: whether the kit's scorers take our pseudo-span adapter without changes.

### P1 · Guideline v2 and human gold (no card: people, no compute)
- Updated 2026-10-29 (owner decision 2): models stand in for people. Gold-Q is rated by three model raters from different families (Haiku, Clef, Jev). The gate is 0.8 × their pairwise agreement and is marked PROVISIONAL in every report. Two people confirm a sample of 50 before P12 ships anything. This is a recorded exception to D3 (human-reviewed gold); the owner decision line is this bullet.
- Goal: a guideline people apply the same way, and a human answer key.
- Entry: P0 exit; owner yes on raters (decision 2).
- Steps: Claude edits `specs/make_spec.py` → v2 (adds `unclear`/`unknown`, boundary and negative examples, prompt
  version `ws-v2`). `python pipeline.py goldsheet` writes two blind sheets: gold-Q (25 random + 25 with a Clef
  reading, from the 300) and gold-T (50 random + 50 Clef-positive spread over rare conditions, from the other
  1,700). Rater A and rater B both label gold-Q blind; rater A labels gold-T, rater B checks 30 of them.
  Disagreements adjudicated → `gold/q50.jsonl`, `gold/t100.jsonl`, sha recorded.
- Exit: both gold files frozen with sha; human IAA per layer on gold-Q in `runs/p1/iaa_human.json` (D1, D3).
- Caps: $0, 0 GPU-h, ~5 person-h, 1M tokens. Stop: a rater needs > 2 min per item → cut gold-T to 60.
- Rollback: gold is versioned; a change is a new sha, old results are not compared across versions.
- Predict: human κ TOPIC ≥ 0.6, STORY_TYPE 0.4-0.6, CONDITIONS pooled F1 0.4-0.6, LEVEL < 0.4. Score: iaa_human.json.
- Learn: whether the condition definitions are clear enough to train on at all.

### P2 · Agreement between two model families (card T01)
- Goal: a larger, cheaper agreement measure on CONDITIONS (Haiku vs Clef on 300) beside the human one.
- Entry: P1 exit; spec v2 frozen; owner approves ≤ $1.
- Steps: `python pipeline.py smoke` (3 items) → `CARD=cards/T01.json python pipeline.py pilot --yes` (300, Batch
  API) → `python pipeline.py compare` → `python pipeline.py iaa` (agreement.py on human A/B, Haiku/Clef).
- Exit: `runs/p2/iaa.json`; D2 verdict per layer (≥ 0.6 go, 0.4-0.6 go with review, < 0.4 fix the guideline).
- Caps: $1, 0 GPU-h, 1M tokens. Stop: any layer κ < 0.4 → back to P1 (max 3 guideline rounds, then owner).
- Rollback: labels kept in `runs/pilot/`; a new spec version means a new run folder.
- Predict: Haiku-vs-Clef CONDITIONS F1 0.35-0.50 (a guess; Clef depends on question context, GO.md:43).
  Score: iaa.json ALL F1.
- Added 2026-10-29: Jev (TypeSafe) joins as a third voter, a different family from both Claude and Clef. First a smoke on 3 synthetic items (no publisher text) to prove it can answer a typed yes/no for 'does this text say <condition> goes <up/down>'. Real items only after owner decision 9, with a spend cap.
- Learn: whether Clef or Jev is usable as a cheap second family, or only people can rule CONDITIONS.

### P3 · Teacher qualification on gold, before any bulk (card T02)
- Goal: prove Haiku clears the student's own gate on every layer it labels (D4).
- Entry: P2 exit. No new spend: gold-Q items were in the P2 run.
- Steps: `python pipeline.py qualify` (Haiku labels on gold-Q vs `gold/q50.jsonl`, gates from iaa_human.json, via
  kit/eval/gate.py).
- Exit: `runs/p3/teacher_gate.json` PASS on every layer Haiku will label (D4); ruler config shows no Haiku (D5).
- Caps: $0, 0 GPU-h, 0.5M tokens. Stop: a layer fails → that layer goes to P5 or the Sonnet route (T06), never bulk.
- Rollback: none needed (read-only scoring).
- Predict: TOPIC and STORY_TYPE pass; CONDITIONS lower bound below the gate (50 items give a wide interval).
  Score: teacher_gate.json lo vs gate per layer.
- Added 2026-10-29: Jev and the cue voter (P4) are each scored against `gold/q50.jsonl` with the same gate. A voter that fails is not used to filter labels at P7.
- Learn: which layers the teacher can be trusted on, and which voters can check it.

### P4 · Free CPU triage (card T03)
- Goal: clean pool, then a sample that gives rare conditions enough examples.
- Entry: P0 exit (can run beside P1-P3).
- Steps: `python pipeline.py triage`: A exact + MinHash dedupe inside the pool and against all 2,000 test items;
  B rules filter (length, language, non-news); C score every item with the existing CPU classifier (:8020) and
  fill a quota per condition. `python pipeline.py sample 1000 --mix quota:500,random:500` → `data/pilot1000.jsonl`.
- Exit: `runs/p4/triage.json` with counts per step and 0 near-duplicates with test (D3).
- Caps: $0, 0 GPU-h, 0.5 CPU-h, 1M tokens. Stop: dedupe removes > 30% → check the shingle setting before continuing.
- Rollback: the raw pool is untouched; triage writes new files only.
- Comparison set in advance (playbook 03 rule 5): quota must give ≥ 1.5× the teacher-labelled positives of random
  on the 19 rarest conditions, scored at P6. Otherwise bulk uses random sampling.
- Predict: quota ≥ 2× random on the rare conditions. Score: P6 yield report.
- Added 2026-10-29: cue extraction with spaCy (Python, available in `models/embed-zs`) and compromise / wink-nlp (JavaScript, not installed here yet): entities, numbers and change-verbs (rises, falls, cut, ban, surge). Written per item to `data/cues.jsonl`. Used to stratify the sample and as a rules voter on direction. Never an input to the student and not run at serving time (the kit measured spaCy at 57 of 228 ms).
- Learn: whether the old reader's scores help find rare conditions, and whether cues beat chance on direction.

### P5 · Candidates in verify mode (conditional; no card unless triggered)
- Not justified now: verify mode is built for spans, and Haiku cost is not the constraint ($3-31 for the whole
  pool, LESSONS_LEARNED E). Trigger: P3 fails CONDITIONS. Then: classifier top-5 conditions as candidates, Haiku
  verifies with `max_add` 2, re-qualify on gold-Q. New card T05b written then.

### P6 · Pilot 1,000 (card T04)
- Goal: prove the bulk path end to end and score the quota-vs-random check.
- Entry: P3 PASS on the layers to label; P4 exit; owner approves ≤ $1.5.
- Steps: `python pipeline.py dry 1000`; `CARD=cards/T04.json python pipeline.py label --items data/pilot1000.jsonl
  --cap 1.5 --yes`; `python pipeline.py status`.
- Exit: `runs/pilot1000/yield.json` (rejects, cache reads > 0, $/1,000, positives per condition, quota vs random,
  `unclear` rate); every row carries teacher, prompt version, date (D6); spend ≤ cap (R5).
- Caps: $1.5, 0 GPU-h, 0.5M tokens. Stop: reject rate > 5% or cache reads = 0 → stop, fix, re-smoke.
- Rollback: discard the run folder; nothing downstream reads it until P7.
- Predict: rejects ≤ 2%, ≤ $0.10 per 1,000 expected. Score: yield.json.
- Learn: real cost per 1,000 and how many positives a condition gets per 1,000 items.

### P7 · Bulk with a cap (card T05; Sonnet slice T06 only if P3 failed a layer)
- Goal: about 25,000 labelled items.
- Entry: P6 exit; owner approves the cap.
- Steps: `CARD=cards/T05.json python pipeline.py label --items data/bulk25k.jsonl --cap 20 --yes`, in 5 chunks of
  5,000; each chunk attended, spend checked before the next. Sonnet slice (if triggered): qualify Sonnet on gold-Q
  first, then `CARD=cards/T06.json python pipeline.py label --spec specs/world_state_v1_sonnet.json --items
  data/slice1500.jsonl --cap 25 --yes`.
- Added 2026-10-29: after labelling, Jev (and the cue voter, if it passed P3) vote on each label. Keep a label when at least 2 of the available voters agree; send disagreements to a small review slice. Clef counts only where it already labelled the item.
- Exit: `runs/bulk25k/` labels + spend log; ≥ 30 positives for ≥ 25 of 38 conditions; spend ≤ cap.
- Caps: $20 (+ $25), 0 GPU-h, 1M tokens. Stop: cap hit, or a chunk's reject rate > 5%.
- Rollback: chunks are independent; drop a bad chunk and re-run it.
- Predict: 25-30 of 38 conditions reach 30 positives. Score: count in the run summary.
- Learn: which conditions stay too rare to train even after quota sampling.

### P8 · Export to Kaggle (card T07)
- Goal: a private Kaggle dataset `kp-world-state-v1` the trainer can read.
- Steps: `python pipeline.py export` → train/dev split by publisher and date (dev = latest month, other
  publishers), test ids and near-duplicates removed, `labels` as `topic:x`, `story:x`, `cond:dir`; then
  `sh ../../kit/ops/kaggle_dataset.sh` with the `kp-` name, private.
- Exit: `runs/p8/manifest.json` (shas, counts, overlap = 0) (D3, R3). Caps: $0, 0 GPU-h, 0.5 CPU-h, 1M tokens.
- Stop: any test id found in train → stop. Rollback: delete the dataset version (not the name).
- Predict: overlap 0, dev ≥ 2,000 items. Learn: whether the date/publisher split leaves enough rare positives in dev.

### P9 · Train the student (card T08)
- Goal: the best small model, picked on dev only.
- Entry: P8 exit; quota checked; selection rule logged on the ledger before training (M3).
- Steps: `python pipeline.py baseline` (TF-IDF + logistic regression, local CPU, $0). `python pipeline.py train
  --smoke`; then `CARD=cards/T08.json python pipeline.py train` → two kernels via kit/ops/kaggle_run.sh, one per
  backbone (MiniLM-4L, Ettin-17M), 3 seeds each, each kernel ≤ 1 h; one learning-curve kernel (25/50/100%).
  Read the loss curves first. Export fp32 + int8, tokenizer parity.
- Exit: `runs/p9/` with dev curves, `selection_rule.json`, `export_report.json` (int8 drop ≤ 0.01, M4),
  `tokenizer_parity.json` (100%, M6), seed sd and the M8 verdict.
- Caps: $0, 3 GPU-h, 1 CPU-h, 2M tokens. Stop: 2 variants without a dev gain over the baseline → stop and report.
- Rollback: keep the previous dataset version; nothing ships from this phase.
- Predict: best variant beats the lexical baseline on dev CONDITIONS by ≥ 2 × seed sd (about 2 points noise);
  Ettin vs MiniLM "no difference". Score: compare report.
- Learn: model limit or label limit (learning curve slope).

### P10 · Score once against the frozen test (card T09)
- Goal: one honest pass/fail per layer.
- Entry: P9 exit; thresholds fixed on dev at the bar's operating point before any test score (M3).
- Steps: `python pipeline.py score` on `gold/t100.jsonl` (human; gate) and on the Clef 2,000 (secondary readout,
  catch rate at 0.1% false alarms, comparable to the old 42% / 49%). Evaluator re-runs and must match exactly (R6).
- Exit: `runs/p10/gate_report.md` (templates/gate-report.md): lower bound ≥ 0.8 × human IAA per layer (M1); beats
  baseline and the old reader with non-overlapping intervals or says "no change" (M2).
- Caps: $0, 0 GPU-h, 0.5 CPU-h, 1M tokens. Stop: score once; any change needs a new card and a new dev pick.
- Rollback: none; the result is recorded as is.
- Predict (p 0.6): TOPIC and STORY_TYPE pass their gates; CONDITIONS lower bound stays below 0.8 × human IAA. On the Clef 2,000 the CONDITIONS catch lands within ±3 points of the old reader (42% at the strict point, 49% at 0.1% false alarms). Score: gate report per layer.
- Learn: which layers can ship now and which go back to P1 (definition) or P7 (more labels).

### P11 · Speed (card T10)
- Steps: `python pipeline.py speed` (kit/student/bench.py, 1,000 pool items, fixed seed, 4 processes × 1 thread,
  local CPU, CPU flags recorded). Exit: `runs/p11/speed_report.json` with the four numbers of playbook 07 and
  $ per million items (M5). Caps: 0.5 CPU-h, 0.5M tokens.
- Stop: p95 over the budget → record the biggest stage and the top lever from playbook 07; no tuning in this phase, the owner decides. Rollback: none (measurement only).
- Predict: p50 ≤ 15 ms per item, well inside 80 vCPU-ms. Learn: whether speed is a non-issue for 57-token items.

### P12 · Ship decision (card T11)
- Steps: `python pipeline.py ship` (kit/student/ship_check.py, clean venv, byte-identical, M7); fill
  templates/model-card.md (M9); owner decision line on scope (which layers ship, private only).
- Exit: `runs/p12/ship_log.json` + owner line. Stop: M7 fails → fix pins, never ship. Caps: $0, 0 GPU-h, 0.5 CPU-h. Rollback: withdraw the model file and its card; nothing else depends on them.
- Predict (p 0.6): exactly 2 of the 4 layers (TOPIC, STORY_TYPE) are cleared to ship. Learn: P1-P7 program measures from the ledger (stage S8).

## End-of-phase update routine (run at the end of every phase; this is the self-improvement loop)

1. **Score the prediction.** Ledger `result` line: predicted vs measured, with the evidence file.
2. **Record the result.** Ledger `verdict` line (pass/fail per exit gate); update the card's input shas.
3. **Evaluator check.** A fresh agent re-runs the scoring command and matches the numbers (R6), on gating phases.
4. **MM3 check** (local Clef only) on any new or changed code, with `where:` pointing at the code. Cite the MM3 id.
5. **Revise this plan.** Edit the next phases (caps, predictions, order) and add a dated line under "Change log".
   A phase that missed its prediction by a wide margin gets its next prediction widened, not dropped.
6. **Lessons.** Append to LESSONS_LEARNED.md (date, what happened, rule, status `open`).
7. **Confidence pass.** Run the same nine MM3 questions on every phase still ahead (same wording, `where:` on the phase text), add the scores as a new pass in `mm3_scores.json`, run `view.py`, refresh the dashboard. The trend row shows whether the plan is getting more or less certain.
8. **Budget line.** $ and GPU-h spent so far vs the plan and the reserve.
9. **Owner sign-off.** One line: go to the next phase, change it, or stop. Paid phases never start without it.

## Owner decisions (answered 2026-10-29; "assumed" = my default, tell me if wrong)

1. Budget: $61.5 planned, $128.5 locked until released. Answered.
2. Raters: models stand in for people for now; people confirm a sample before P12. Answered.
3. Speed: all questions under 50 ms per item on one CPU thread (kit throughput check: 3,000 items/min on 4 vCPU). From owner's message.
4. Bar: gate = 0.8 × agreement; the 90% catch number is reported, not gating. Answered.
5. Scope: claim stays a teacher-only field; size trained only if agreement ≥ 0.4. Assumed.
6. Kaggle: this project ≤ 3 GPU-h total, ≤ 4 per week. Assumed.
7. New pipeline stages are written phase by phase, shown first, MM3-checked. Assumed.
8. Licence (D6): record that Anthropic terms allow training an internal classifier on Haiku output. Assumed; the note is still to be written.
9. Hosted Jev may see headline + description, in stages: 3 synthetic items, then 50 gold, then the pool. Answered.
10. Extractors run as a separate serving layer, not as model input in v1. Answered.
11. Full article bodies: test on 1,000 items after the first model. Answered.
12. The owner's relationship engine: owner shares it when ready; it is added as an extractor and a voter. Answered.
13. Success: topic and story type first; conditions are tried and a miss there is a finding. Assumed.

## How this plan maps to PRD v0.2 (compared 2026-10-31; this plan was not derived top-down from the PRD)

| PRD v0.2 | In this plan | Match |
|---|---|---|
| Distil from LLM teachers into a small shared encoder with many heads (A, G2) | Haiku + Sonnet teachers, one encoder, a head per output | Aligned |
| Gate = 0.8 x agreement, lower 95% bound, frozen scorer by sha (A, G3) | Same rule, same scorer pinning | Aligned |
| Ledger tasks with definition of done and stop rule (G2.9) | Same | Aligned |
| Triage router before extraction (D) | The Haiku gate: reads 15% of items, finds 61% of condition-bearing ones | Aligned |
| Two teacher families plus human gold (G2.5) | Haiku and Sonnet are one vendor; Jev and Clef (a second vendor) not yet voters; no human gold | **Weaker** |
| Stage 1-2: dedupe, near-duplicates, segment with offsets | Pool dedupe and test near-duplicates only; headline + description, no segmentation | Partial |
| Evidence span on every update, 100% traceable (A, G3) | No evidence output | **Missing** |
| Anchors: a condition is an Anchor with a measurable Track (A, C) | A condition is a label out of 38, with direction and size | **Different** |
| Events, assertions, observations, resolved anchor IDs (B2, D4-5) | Article-level labels and one free-text claim; no event or anchor linking | **Missing** (PRD names anchor resolution as the highest-value next work) |
| Modality, time, scope, intent labels (G2.2) | Planned only as the trait layer (D14, specs/traits_v0.json) | Planned |
| Active learning on model disagreement (G2.7) | Haiku/Sonnet disagreement kept as soft labels (D14) | Planned |
| Pulse / Area / Understanding as computed views (C1) | None; L3 Impact uses the World engine arithmetic | Out of scope here |

Reading: this plan is a vertical slice of PRD stage 3 (classify) and part of stage 4 (detect). Next derivations: add an evidence-span output, define each condition as an Anchor with a Track, make a second vendor a voter, and carry the PRD sprint numbers on the phases.

## Change log

- 2026-10-29 · v1 of this plan, from the four reviews (REVIEW_OF_REVIEWS.md) and the kit.
- 2026-10-29 (post-plan check, MM3-0539): added numeric predictions for P10 and P12, stop and rollback for P11 and P12, and the 'who writes the missing code' note. MM3 verdict: fix first (0.57), goal 0.77, owner control 0.83 to 0.94. Open: gold set may be too small for CONDITIONS (plan flags it); several predictions are guesses.
- 2026-10-29 · Added Jev as a third voter (P2, P3, P7), cue extraction with spaCy / compromise / wink as a labelling-time proposer and rules voter (P4), and owner decision 9. Reason: owner asked for a double check by TypeSafe and asked where the NLP tools belong.
- 2026-10-29 · Owner interview: added the layers table, moved human raters to before P12 (provisional model-set bar), recorded 13 decisions. Reason: owner wanted expectations set and the plan reviewed by questions.
- 2026-10-30 · MM3 confidence pass 1 on all 13 phases (MM3-0540 to MM3-0552): overall 58 of 100; clarity 76, safety 71, evidence 26. Added the confidence step to the end-of-phase routine.

## Definition of done v2 (2026-10-31, owner direction L199, L204, L205)
No human gold. Layered agreement, reported as agreement. Full text and per-field bars in `specs/expert_contract_v1.md`. Measured so far (L212, student vs Sonnet on later unseen items): story type at teacher level (0.913 vs 0.923); topic and condition presence are the gaps.
