# 06 · Evaluate and gate

**Goal:** a pass/fail decision that would survive a sceptical reviewer.

## Rules

1. **Gate = 0.8 × IAA per layer**, from chapter 02. A run passes only if every gated layer passes.
2. **Judge the lower bound.** Bootstrap the score by resampling items (not sentences); the lower end of the 95%
   interval must clear the gate. On 2–11 items the interval is wide: report it rather than a point score.
3. **Both exact and overlap F1** for spans. Overlap shows whether the model finds the thing; exact shows whether
   boundaries follow the guideline.
4. **A consensus ruler between human rounds.** When human gold is small, score against the agreement of two LLM
   families on a larger pool (205 articles in T68). Only layers where the judges agree well can be ruled this way;
   report judge-vs-judge agreement next to the student's score.
5. **Compare against baselines** on the same scorer: a zero-model lexical baseline, each teacher alone, and the
   previous student.
6. **Score once.** After the gold score is out, changes require a new task, a new pick on dev, and a new single
   score. No tuning against gold.
7. **Check your harness against itself.** Run identical inputs through the scorer to confirm a perfect score, and
   check that ignore regions or filters apply only where intended (we once inflated per-judge scores to .999 by
   applying ignore regions to the wrong comparison).
8. **Weight a skewed vote sample back to the stream** before quoting any presence or precision figure (here: Haiku-negative items x6.9). Unweighted
   numbers overstated precision of a "present" commit (0.93 vs 0.81) and understated agreement (0.81 vs 0.89).
9. **Never average in the teacher you trained on.** Score a model only against teachers that were not in its training label; label the rest "circular benefit".
10. **Check every export against its source** on 200 items (cosine 0.9999 or more) and every length cap on a validation slice, not on test.
11. **Pre-register the replacement rule.** Before comparing a candidate with the current choice, write the rule that decides
    (for example: higher agreement on 2 of 3 fields, within 0.05 on the third, 0 to 1 parse failures) and log it. Then apply it as
    written: one strong field does not outweigh a failed rule. Compare agreement with a guess baseline, and score only items dated
    after the training cutoff.

12. **The baseline is the registered version's own score file, named and cited.** Never "the baseline" without the model: on 2026-11-03/04 a distilled leaf head (story 0.906, topic 0.786) stood in for the registered student (0.919, 0.79, `runs/pulse/end2end_v6b-student_devq.json`) and fifteen rounds looked like gains that were not (ledger L652, L653).
13. **Measure the ceiling before training.** Rerun the answer key (Sonnet) on the same items and score it against itself, per field (about 1,600 labels, 2.5 USD in 2026-11). That number is the most any reader can score as "agreement with Sonnet" (story 0.99, topic 0.98, presence alpha 0.94, size 0.91 to 0.94, L619). Bar rule for the Pulse (owner, L621): 0.80 x that ceiling, written down before scoring. The Engine page keeps its own verdict, the Ready rule (GO.md, L492 to L495); report both and say which surface each belongs to.
14. **Compare curves, not points, for rare fields.** Two readers at different cut-offs are not different readers: production found 24.9% of real presence cases at precision 0.917, my head 22.2% at 0.90, and their AUCs were 0.928 and 0.927 (L654). Report recall at fixed precision and AUC; say the operating point when quoting a rate.
15. **A rule with counts gets a Lean check.** `projects/world-state/lean/PresenceReady.lean` derives the exact error budget of the Ready rule (1,804 of 1,997 agreements; 149 false alarms at 177 of 221 found) and corrected a hand figure that was wrong by a factor of 2.4 (L662). Plant three bugs and see them caught before trusting a proof file.
16. **Noise floor.** Presence alpha moves +-0.03 between identical reruns (L635). A gain smaller than that, or inside the baseline's 95% interval, is "no gain". Anything chosen on the evaluation items (a vote, a reader per question, a weight) is labelled optimistic.

## Done when

Gate report (`../templates/gate-report.md`) filled, with scorer sha, intervals, and a verdict per criterion.
