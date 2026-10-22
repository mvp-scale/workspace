# GO — session handoff

Written 2026-10-20 evening. Overwritten at each handoff.

## First reply of the new session
Read this file, run `node tools/ledger.mjs board` and `node tools/ledger.mjs score | head -8` (not the full miss list: tokens), skim `.claude/skills/ontology-trainer/SKILL.md`. Check the suite jobs (below). Then reply in at most 8 lines, opening with the model/effort shortcode (`~/.claude/CLAUDE.md`, digit from `$CLAUDE_EFFORT`): (1) goal, (2) where we are, (3) next step and its forecasts, (4) waiting on the user. After the user confirms, chain in-method steps without asking again (D-0006, memory "no ceremony").

## The user's view: Trainer live
`http://localhost:8100/mockups/trainer/` (one screen, tabs, click anything for its evidence). It reads `demo/mockups/trainer/live.json` + `ledger.json`, built by `newsreader/bitmob/progress.py build` (runs on every job event and after every Bash/Write/Edit via the PostToolUse hook in `.claude/settings.json`). Per-model grid from `newsreader/bitmob/suite_card.py` -> `data/scorecard/models.json`. "Needs you" list: `data/progress/needs-you.json` (edit it when a user decision opens or closes).
- Every job MUST post events: `from progress import event; event("<model>:<area>", "training|scoring|done|failed", msg, pid=os.getpid(), win=True on results)`, or CLI `progress.py event <job> <state> "<msg>" --pid N [--win]`. A job that runs without events is invisible to the user: not allowed.
- Proof status on the page is checked, not stated: file pins re-hashed vs the ledger. 65 validated, 17 weak (proven but a pin changed or no evidence), 93 unproven.

## Running at handoff (background, nohup, each `timeout 3000`)
Suite jobs `newsreader/bitmob/suite.py <model> [areas]`, logs `data/suite/logs/`, results `data/suite/<model>/<area>.json|.npz`: e5tfidf (all areas), potion_ft (conditions left), setfit (type pilot), e5ft (type pilot, ~30 min/area at 5 threads). Check: `pgrep -af suite.py`, or the page. Done: tfidf, e5, potion (all 4 areas); potion_ft type/topic/country.

## Pipeline (one iteration; repeat)
1. **Predict**: ledger forecast per run (`predict <task> "..." --p`), tagged [source]/[harness]/[structure]/[model].
2. **Train in parallel**: every candidate x every area, same train (night1-train + round1 + round2) and frozen test (night1 held-out + testA, Jev labels) via `suite.py`; split the 20 cores (THREADS env); each job < 50 min.
3. **Score**: per-model card (suite_card) + acceptance card (`scorecard.py`, fingerprint must stay `017dc4c3784a`); both show on the page.
4. **Verify**: MM3 on the write-up before any keep/drop decision (`tools/mm3local` + `tools/mm3hosted class <yaml>`, 2 runs; splits recorded, not resolved). Budget 15 of 500 runs: only the user can raise it.
5. **Decide with a reason**: every model or reader dropped/kept gets a ledger decision with its evidence (F-0070 found three drops with no reason: never again).
6. **Next round**: 1,000 stories (500 random, 500 aimed at failing criteria: `round_select.py`), label with Jev (~$0.5), back to 2. A criterion with no stable trend after 3 rounds -> Opus investigator, then the user (D-0013).

## Next steps, in order (gap list F-0070, task T-0025, forecasts R-0117..R-0120 waiting)
1. Finish the suite: when the running jobs end, score R-0117..R-0120; run setfit and e5ft on the other areas (or record why not, e.g. time), build the ensemble (e5tfidf + e5ft, 50/50) for every area as a `data/suite/ensemble/` model.
2. Honest card: mark C5 (30 probes, bar >= 20 per pair = 120), C7 (dev stand-in), C9 (9 'check' sources undecided) not passed, with a ledger note; split calibration and threshold sets (MM3-0486/0487 q13) and re-measure K6/K8.
3. Re-prove or retract the 17 weak items (page Ledger tab, filter weak).
4. T-0011 definition check (skill step 1b, skipped before scaling): codebook per condition inside the question text; Jev + Sonnet `[S2]` + Haiku `[H1]` on pilot50; score R-0064..R-0068.
5. Criteria rev 3 from MM3-0484/0485 points; user approves; then the jury test set (skill step 4).
6. Country checker v3 (club names, small cities, Georgia the state), confirmed on a NEW fresh set with 120 look-alike probes.

## Where things stand
- Acceptance card 5/50 (of which C5/C7/C9 are generous: honest ~2-3). Best per area so far vs Jev: type e5 frozen (T2 2/4, AP 0.822); topic potion fine-tuned 0.725 (bar 0.85); country e5 0.805 (no per-model bar; script v2 recall 0.88 vs 0.97, F-0062); conditions ensemble 0.482 mean AP, 4 of 48 keys >= 0.70 (F-0058), K6 19/48, K8 0.80 (F-0068).
- Drift audit F-0070 (MM3-0486/0487): SetFit/model2vec never trained, areas not retrained, retirements unrecorded; route both "fill gaps then continue".

## Rules that bind
- CLAUDE.md, memory, `~/.claude/CLAUDE.md` (shortcode on every model action; cheapest tier; flag big fan-outs first).
- Every claim cites a ledger item, a pinned file + command, or an MM3 id. Predict before, score after. No job over 1 hour unattended.
- Tokens: send job output to logs and `tail`/`grep`; `ledger show <id>` instead of listing whole kinds; scorecard prints are ~2.5k tokens.
- Stopping services: give the user `! ./service.sh stop <name> -y`.

## Waiting on the user
Sport topic; countries outside the 100; the 9 'check' sources; Clef or Jev as the engine target (D-0017); MM3 run budget.
