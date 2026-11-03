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

## Done when

Gate report (`../templates/gate-report.md`) filled, with scorer sha, intervals, and a verdict per criterion.
