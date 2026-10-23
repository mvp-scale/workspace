# GO — session handoff

Written 2026-10-22 ~20:30. Overwritten at each handoff. Branch `world-engine-100-countries`, pushed to GitHub (mvp-scale/workspace).

## First reply of the new session
Read this file. Do NOT start any job until the user says so (the user asked for a clean stop). Check the two background results below (files, not agents: the agents from the old session cannot report to the new one). Then reply in at most 8 lines, opening with the shortcode (`~/.claude/CLAUDE.md`): (1) goal, (2) where we are, (3) the two background results if done, (4) what waits on the user.

## Goal
Run the World engine on a CPU reader (BitMob) instead of Clef on the GPU, matching Clef's contract (rows P-0016..P-0023, ledger). **A BitMob pass means BitMob alone.** Any result where Clef answers part of the work is a *fallback* that needs the user's approved exception; never call it a pass (memory: bitmob-alone-counts).

## Score now (BitMob alone, 2,000-story Clef answer key; Trainer page Models tab)
| Step | Best | Bar | |
|---|---|---|---|
| Topics | 95.5% (round 6) | 80% of topics | pass |
| Country | 90.5% (round 7, larger model) | 90% | pass |
| Severity | 79.8% (round 6) | 75% | pass |
| Read-or-skip | 81.1% | 90% | fail (8.9 short) |
| Conditions | catches 31.1% | catch 90% at <=0.1% false alarms | fail (58.9 short) |
| Expected impact | 62.1% (always-empty baseline 61.1%) | 75% | fail |
| So-what | not trained | user decides (keep Clef / template) | open |
| Whole engine | not run | needs engine restart | open |

## Why the three fail (diagnosed, free CPU; ledger F-0110, F-0111)
- Conditions: BitMob ranks condition answers well (AUC 0.989) but under-states rare strong yeses (-0.27 where Clef triggers; only 0.27% of answers trigger). Not brittleness (Clef +-0.10 noise still passes), not truncation. Labels plateaued: rounds 3/5/6 aimed 65%/79%/100% of Clef labels at conditions -> 18% / 31% / 31%; bigger encoder 24%. More labels will not fix it.
- Read-or-skip: happened/announced answers sit near their 0.5 cut on ~19% of stories; BitMob ±0.13 there.
- Expected impact: never targeted with labels (0% of Clef labels); BitMob under-triggers.
- Label targeting by round (all Clef-labelled train, 6,661): conditions 63%, random 23%, read-or-skip 10%, country 4%, topics/expected/severity 0%.

## Running at handoff (results land in files)
1. **Fallback test**: DONE (see above). (Kaggle kernels `coreygorman/bitmob-screenk-comb1`/`comb2`): output `data/kaggle/screen_comb*/out`, report `data/diag/combined_reader_2026-10-22.txt` (when written), scripts `newsreader/bitmob/reader/combined_*.py`. Report it ONLY as a fallback with BitMob-alone numbers beside it. Also settles a scorer discrepancy: variant B 98.2% (screen_real_analyse.py) vs 93.9% (screen_real_analyse_c.py) on the same answers.
2. **CPU checker**: DONE, failed (see above). (Was: the BitMob-alone fix): a small CPU cross-encoder that verifies BitMob's shortlist (story + one candidate question), trained on Kaggle from Clef labels; conditions first, then read-or-skip, expected impact. Report: `data/diag/cpu_checker_2026-10-22.txt` + a ledger fact; prediction on F-0110. If it does not move conditions meaningfully, stop and report (no more same-lever rounds).
Check: `source tools/kaggle.env; kaggle kernels list --mine --page-size 5`, `ls -t data/diag/`, `node tools/ledger.mjs show F-0110`.

## CPU checker result (DONE 2026-10-22, F-0113, report data/diag/cpu_checker_2026-10-22.txt) — FAILED on all three
BitMob + CPU cross-encoder checker (no Clef at serving), e5-small and e5-base, thresholds on tune only, 2,000 test: conditions 36.5% / 28.3% caught (bar 90%), gate 82.7% / 82.8% (bar 90%), expected 56.5% / 55.9% (bar 75%; worse than BitMob alone). Cuts false alarms but catches no more; bigger checker no better (capacity not the limit). Agent's untested reading: Clef's answers depend on the 20-question block each question sits in (Clef itself on bare questions caught only 36%), so a one-question reader learns a noisy target. Not tried: a checker that sees the question's block context. CPU 150 ms/story (small). Kaggle ~0.8 h; 22.4 h left. Per the user: stop same-lever work; decide direction with the user.

## Fallback test result (DONE 2026-10-22, F-0112, report data/diag/combined_reader_2026-10-22.txt) — needs Clef, NOT a pass
300 test stories, real Clef on Kaggle: gate 96.0%, conditions caught 98.3% at 0.026% false alarms, expected 83.3% (all with Clef); topics/country/severity are BitMob-only (country needs the round-7 model). Clef time 13.7 s/story = 32% of the ask phase, 23% of the whole engine Clef path. Same stories, BitMob alone: gate 86.0% / conditions 24.4% / expected 57.0-61.7% (fail). Scorer discrepancy settled (N-0036): 98.2% = the reader's number, 93.9% = a stricter floor. watch.sh pre-flight bug fixed (${1:-}). Kaggle ~1.0 GPU h; 23.1 h left.

## Verified fallback evidence (not passes)
Conditions, BitMob shortlist + Clef asked the usual 20-question blocks holding it (real Clef, Kaggle, 298 stories): 98.2% caught, 0.026% false alarms, ~24% of full-battery Clef time. Bare shortlisted questions fail (64%); +3/+7 neighbours fail (75%/78%) (R-0175 wrong). Read-or-skip / expected fallbacks are simulations only.

## Done today (committed and pushed)
- Clef Flash Fast (CLF9F4, vLLM NVFP4) onboarded on every surface; accepted D-0045 (MMLU 91.9 vs Q4 91.7; one 80-item set -5 pts). Image Lab acceptance paused by the user; speed/memory (vram) not measured (needs voice paused). add-model skill has a "Done means" 10-surface table + MM3 touchpoint map.
- Pages list registered models as "not run yet"; heat maps sorted by accuracy; Image Lab lists only `vision: true` models.
- Benchmark results versioned: `tools/run_versions.py`, archive `data/run-versions/` (Jev 1.13.0 archived; Jev 1.14.0 run: +0.4 MMLU, cost $0.29).
- Latent lab rebuilt as a 9-section story with expectations first and a version stamp (`/api/version`); training walkthrough `/mockups/vector-walkthrough.html` updated; Trainer Models tab: one number per cell, BitMob-alone pass/gap, fallback column.
- .gitignore blocks model weights/binaries by type; `checkpoints/`, picker libraries/data/cache out of git.
- Kaggle: this project uses coreygorman's API token by path (`tools/kaggle.env`: `KAGGLE_API_TOKEN=/root/.kaggle/coreygorman.token`, mode 600; never print it). The user has two Kaggle accounts (coreygorman = this project, gtrash = other). watch.sh pre-flights the account and treats login gaps as a pause (C-0014, T-0026; open: account in run ledger, login status on Trainer page).

## Test-set quality (self-rating vs our own research, 12/25)
Reference ceiling not measured (Clef vs Clef), baselines not checked before bars, too few cases per condition (~5 in 2,000), no planned slices, integrity good. Fixes proposed (not started): Clef self-agreement on 300 stories (~1 Kaggle h), per-step baselines (free), an enriched slice for rare conditions + borderline read-or-skip, a datasheet.

## Waiting on the user
1. Start nothing until told.
2. Engine restart for the whole-engine check (resets world state); can be combined with 3.
3. Engine reads with Clef Flash Fast (~5x less GPU per story).
4. So-what summary: keep Clef or a template.
5. Earlier open offers: training guide refresh (+HTML), Latent lab "better pipeline" build, World engine live feed back on (it is off since labelling).

## State of resources at handoff
5090: idle (Clef Q4 :8018 up, voice up, World engine up with live feed off). Kaggle: ~24 GPU h left this week (account coreygorman). Jev: $9.95 of $10 (no spend planned). Today: 5090 ~6 h, Kaggle ~3 h, money $0.29.

## Rules that bind (memory + CLAUDE.md)
Shortcode on every model action. Kaggle first; local 5090 only with the user's yes. Never rm (move aside); no rm with variables. Commit only when asked (the user has asked to check in this branch's work). No hosted calls without asking. No job over 1 h unattended. Never drive the user's Chrome (headless only). Free, in-plan CPU/Kaggle work: start it, don't ask (but this handoff says: wait). Plain language, exec style, one number per cell on pages.
