# Skill: designing probe questions for Jev-class decision models

An agent writing `noul`/`choice`/`score` questions against a Jev-class `/v1/systemone` model needs
this before it writes redundant/paraphrase probes for a decision — not just single questions.
Discovered from a live mistake: a probe worded "Is it safe to assume there is no X concern?" was
run alongside a direct probe "Does X show a failing grade?", the two disagreed, and the disagreement
got reported as **the model being inconsistent** — when the real problem was that the two questions
weren't asking about the same thing. One was a fact, grounded in the given context. The other was
an unanswerable opinion about risk tolerance that nothing in the context defines.

## The core rule

**Every question must have an answer that is directly verifiable from the given `state` alone.**
Nothing else. Not the model's judgment about risk, not what a hypothetical reader "should" believe,
not an assumption about context that was never provided. If two different people (or two different
models) can't in principle look at the same `state` and agree on the answer, the question is broken
— regardless of how confidently anything answers it.

This isn't an invented rule — it matches how `jevbench` (the benchmark harness these models are
measured against) is actually built. Its own reliability axis is explicitly "does the stated
probability mean anything, does it survive a rephrasing, does it keep to the schema"
(`jevbench/README.md`), and its paraphrase-pair mechanism (`jevbench/jevbench/metrics.py:123`,
`paraphrase_consistency()`) only counts a pair as valid when **both members share the identical
expected/gold label** — verified in advance, not assumed from wording. `jevbench/jevbench/tasks.py`
requires every task to carry a real `expected` value from a fixed `labels` set, and `validate()`
actively guards against the state accidentally containing the answer. The whole system is built
around one premise: a question is only meaningful if there's a fact of the matter it's checking.

## Red-flag words — if a probe's `instructions` contains one of these, stop and rewrite it

`assume`, `safe to`, `would`, `might`, `could`, `should`, `seems`, `likely`, `probably`, `in your
opinion`, `do you think`. Every one of these either (a) asks for a hypothetical/counterfactual
rather than the actual state, or (b) asks for a belief/risk-tolerance judgment that has no defined
answer given only the context provided. `context_quality_1` in tonight's Test 4
("would a failing quality grade be **especially concerning** here?") is itself a borderline case —
it's an explicit hypothetical, useful as its own signal, but must never be treated as a paraphrase
of a direct/factual probe, only as a distinct question in its own right.

## How to build a real paraphrase/inverse pair

1. Write the direct question first: a bare fact, phrased as a yes/no or pick-one about something
   literally present in the `state`. E.g. "Does the security position show grade F?"
2. Derive the inverse by direct logical negation of that same referent — not a fresh sentence that
   sounds like the opposite. E.g. the valid inverse of the above is "Does the security position show
   a grade other than F?" — same referent (the security position's grade), same verifiable fact,
   just negated. NOT "Is it safe to assume security is fine?" (different referent: a risk judgment,
   not the grade itself).
3. Before trusting a pair as a consistency check, ask: **do these two questions have the same
   correct answer, in principle, for every possible `state`, given only how they're worded?** If you
   have to imagine any additional context, opinion, or assumption to answer one of them, it's not a
   valid pair.

## Checklist before sending a probe set

- [ ] Every question's answer is fixed by the given `state` alone — no outside judgment required.
- [ ] No red-flag hedge words in any `instructions` string.
- [ ] Every "inverse"/paraphrase pair shares the same referent and would share the same gold label
      for any possible input — verified by inspection, not assumed from sounding opposite.
- [ ] Contextual/hypothetical questions (useful on their own) are never treated as consistency
      checks against a direct/factual question — they measure something different and should be
      reported as their own signal, not folded into an agreement/disagreement score.
- [ ] If a disagreement shows up between two supposedly-paired questions, the first suspect is the
      *question design*, not the model — check this before concluding the model is unreliable.
