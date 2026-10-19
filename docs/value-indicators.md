# Value indicators and anti-myopia protocol (pre-registered 2026-10-18, before any of the attacks below are run)

Purpose: say in advance what "it worked" means, so results cannot be argued into success afterwards, and so each attack is tried broadly enough
that a "no" means something. Changes to this file after a result is seen are listed under Deviations, with the reason.

## Primary indicator (the one number every attack is judged on)
R@9 = share of reference-positive (story, atom) pairs found, at no more than 9 false positives per 100 test stories, pooled over the 44 current
atoms (data/mm3-train/route-current.json), on the fixed test split (id hash % 5 == 0, 486 stories), scored where the reference is clear.
Operating point per atom is chosen on training stories only; one shift applied to all atoms traces the curve (newsreader/bitmob/proof_bootstrap.py).
Baselines (Clef-agreed reference, cross-fitted, proof/bootstrap.json): single Glance head 0.320 [0.216, 0.387]; all-agree jury 0.359 [0.304, 0.426].

## Secondary indicators
R@4 (same, <= 4 false positives); CPU ms per story (one thread); GPU calls at run time (must stay 0); share of atoms with R@9 >= 0.6 ("usable atoms").
CR@9 = the same measure at condition level (a condition counts as found when any of its atoms is found; reference = any of its atoms positive):
the World engine moves conditions, so an atom gain that does not reach CR@9 is not value. An attack only WORKS if CR@9 does not fall.

## What counts as value (an attack "works")
- WORKS: R@9 rises by >= 0.03 over the best baseline, with the 95% bootstrap interval of the difference (300 story resamples) excluding zero, and
  CPU cost within 2x of that baseline (or a stated reason it is worth more).
- PROMISING: rises by >= 0.03 but the interval includes zero -> rerun with a second formulation or more data before any claim.
- NO GAIN: interval includes zero and the point estimate is below +0.03 -> UNPROVEN, not failed, unless all eight items of docs/proof-standard.md hold.
- WORSE: interval excludes zero below zero -> report as worse in that form only.
Value of a success = (gain in R@9) x (atoms it applies to) / (CPU ms added). Cost of GPU at run time is infinite: any run-time GPU call disqualifies.

## Reference (what "right" means)
R1 Clef-agreed (both wordings yes / both no). R2 teacher jury: pairs where Clef and a second local model of a different family agree. R3 the user's
hand check (when available) is the final referee. Every result is reported against R1, and against R2 once it exists; R3 overrides both.

## Anti-myopia protocol (applies to every attack)
1. At least two formulations of the idea, written down before running; at least one idea from outside the current family of methods.
2. Same split, same operating-point rule, same metric for every option; baselines rerun in the same script.
3. Every claim has a results file, a command and a 95% interval. A single run with no interval is reported as "PROMISING" or "UNPROVEN" at most.
4. Before calling any result: list what was not tried, and run the MM3 proof check (docs/proof-standard.md) on its dossier.
5. Drift guard: the test split, the 44 atoms and this file do not change during the attacks; any change goes under Deviations.
6. Sycophancy guard: a result is reported with its interval even when it is bad news; an attack that fails is not rerun with new settings until
   the reason is written down first.

## Attacks, in order, each with its pre-registered formulations
A1 One shared model across atoms. Formulations: (a) pair model: score (story, atom) with [story vector, atom question vector, their product];
   (b) multi-task network: one shared hidden layer on the story vector, one output per atom; (c) per-atom head blended with the pooled score.
   Outside idea: (d) nearest labelled stories (k-NN on the story vector) with per-atom vote, pooled across atoms by similarity.
A2 A better reference. Formulations: (a) teacher jury with a second local model of a different family on the evidence batteries; (b) agreement of
   Clef across its own batteries (first battery states/concrete vs evidence atoms) as a coherence filter. Measure: does the CPU model trained on
   jury-agreed labels score higher against R2 than the one trained on Clef alone? Does the CPU disagree with Clef mostly where the jury does?
A3 Intervals for the open verdicts (Grammar, Locate, chunks, teasers, fine-tune) with the same split and metric.
A4 Decomposition per sentence, judged against R2 (and R3 when it exists). Formulations (written before running): B-sent = support-v1 building
   blocks must co-occur in one sentence (story-trained heads applied per sentence, rule AND = lowest, story = best sentence); B-sent relaxed =
   consumer prices = price & up, energy prices = energy & price & up, per sentence. Measure: average precision minus the direct head, 95% interval.
A5 Fine-tune with all stories and a learning curve (25 / 50 / 100%).

## Deviations
- R2 (teacher jury with Winnow-12B) withdrawn at the user's instruction: Winnow is legacy and the goal is to relieve the GPU. The partial Winnow labels (3 of 7 batteries, test stories) were deleted unused; Winnow stopped, voice restored. A2 continues with R1b (Clef coherence, no GPU) and R3 (the user's hand check) only. The A4 R2 column is void.
- After A3 (not applied retroactively): R@9 on 486 test stories has a 95% interval of about +/-0.08 and is unstable (a maximum over a coarse grid of shifts; some point values sit outside their own bootstrap means). Gains of +0.02 to +0.05 cannot be resolved. Next round adds, as a secondary measure, pooled average precision (threshold-free) and a power estimate; R@9 stays primary for this round.
- A1 run 1: scorer bug (condition level and usable atoms used the strictest point under the cap, not the R@9 point); fixed in value_eval.py, all options re-scored from saved scores. Atom-level R@9 was not affected.
- A1a' with atom intercepts scored 0.039: the stated reason was wrong; cause unexplained; reported as WORSE in this form.
- A1b multi-task PROMISING (+0.035, interval includes zero): planned second formulation before any claim: inputs Glance full + Glance lead + Scholar lead, 5 seeds averaged.
- A1a pair model scored 0.047: reason written before rerun: one pooled logistic has no per-atom baseline, so rare atoms never pass their training cut-offs. Rerun with a one-hot atom id added to the pair features (atom intercepts).
- Before any attack ran: added CR@9 (condition level) after MM3-0004 flagged that an atom-level gain could leave the World engine with nothing.
