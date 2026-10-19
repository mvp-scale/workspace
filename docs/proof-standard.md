# Proof standard for "does not work" verdicts (2026-10-18)
A failure is PROVEN only if all eight hold; otherwise the verdict is UNPROVEN (not failed).
1. Claim: exact statement and scope (atoms, stories, split).
2. Test fixed in advance: method and bar written before the result (file).
3. Receipt: the number comes from a results file (path + key) and a command reproduces it.
4. Fair comparison: same stories, same operating point (equal false positives) as the baseline.
5. Beyond noise: a 95% bootstrap interval on the difference that excludes zero.
6. Second approach: at least one other way of using the idea was tried, with its result.
7. Measured cause: the explanation has a number behind it.
8. Untried options listed.
Each dossier (data/mm3-train/proof/dossiers/) is then checked by MM3 (local Clef) for myopia, ignored options, assumption errors, noise, receipts and cause.

## Result (2026-10-18): MM3-0003 (local Clef, 10 dossiers, 200 questions) + the eight-item checklist
MM3 category gates (fail = a problem found): ignored options FAIL in 9 of 10; assumptions FAIL in 5 (F03, F06, F07, F08, F09); noise FAIL in 5
(F01, F04, F05, F06, F09); cause FAIL in 5 (F04-F08); myopia FAIL in 3 (F05, F08, F10). Narrowness: "quite narrow" is the top answer for 6 of 10.
MM3's own summary verdict ("proven failure" for F01-F03, F05, F06 at p 0.34-0.60) contradicts its specific checks (e.g. F01: noise FAIL), so the
specific checks are used, not the summary verdict (Clef is not logically consistent across questions; see F06).
| dossier | interval excludes 0 | 2nd approach | measured cause | verdict |
|---|---|---|---|---|
| F01 Sieve as voter | no (-0.078..+0.036) | yes | partly | UNPROVEN |
| F02 Grammar | none | yes | yes | UNPROVEN |
| F03 Locate | none | yes | no | UNPROVEN |
| F04 learned combiner | no (Glance+Scholar); yes (tier 1) | yes | partly | UNPROVEN (tier 1 worse, cause not measured) |
| F05 fine-tuned e5 | none | weak | no | UNPROVEN |
| F06 decomposition | yes for consumer and energy prices | yes | yes (26%) | PROVEN, narrowly: this story-level rule vs Clef's labels. "Decomposition fails" is UNPROVEN |
| F07 chunk scoring | none | yes | no | UNPROVEN |
| F08 teasers | none, different splits | no | partly | UNPROVEN |
| F09 jury 9x | retraction holds | - | yes | RETRACTED |
| F10 round 1 methods | none, old labels | no | no | UNPROVEN on current labels |

## Round 2 (2026-10-18): MM3-0006 on 9 dossiers (data/mm3-train/proof/round2/)
Receipts now mostly PASS (named files, intervals). Still FAIL: ignored options 9 of 9, myopia 7 of 9, cause 5, noise 6; narrowness "quite narrow"
8 of 9; MM3's verdict "unproven" 8 of 9 (R05 "proven failure" at 0.52 contradicts its own noise FAIL, so it is read as unproven).
Proven this round (interval excludes zero, CPU only): Scholar adds value in the jury (R@9 -0.045 without it, -0.077..-0.016; macro AP -0.061,
-0.090..-0.033); Echo decides same-event (AUC 0.891, 0.838..0.942); Echo + titles beats Echo (+0.043, +0.010..+0.079); jury + multi-task beats the
single head (R@9 +0.070, +0.017..+0.147; macro AP +0.033, +0.007..+0.062) but not the jury.
Systemic pattern MM3 keeps flagging: one setting per formulation, Clef as the only reference, and engine tweaks smaller than the test can resolve.

## Process v2 (to stop the drift)
1. Power first: before comparing options, compute the smallest difference the test can resolve (macro AP ~0.03, R@9 ~0.065 on 486 stories). If the
   expected gain is smaller, do not run the comparison; grow the test set or the reference instead.
2. Each formulation gets at least three settings of its main knob (e.g. size, k, epochs), chosen before running; report the best on training
   folds only.
3. Reference audit before claims: a result only stands against a reference whose own error is measured (R3, the user's hand check, is the only
   one left that is not Clef).
4. Every dossier gets the MM3 proof scan before it is reported; its specific checks, not its summary verdict, decide.
5. Engines are not tuned further until the data and the reference grow: the learning curve (A5) and the noise floor say that is where the gain is.
6. Two reviewers: every MM3 verdict check runs on local Clef and on hosted Jev (jev-1.13.0, user-approved for checks of our own write-ups only,
   never article text; MM3 budget cap applies). Both runs are cited; when they disagree, the split is reported, not resolved by picking the one that
   agrees with the author. First comparison (MM3-0006 vs MM3-0009): category gates identical on 35 of 54, Jev stricter where they differ; decisions
   MM3-0007/0010 agree (1a + 1b), MM3-0008/0011 split (2a vs 2a + 2c). Cost about $0.001.
