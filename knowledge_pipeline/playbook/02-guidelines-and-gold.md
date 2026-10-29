# 02 · Guidelines and gold

**Goal:** a written definition humans apply consistently, a measured agreement level, and a frozen test set. This is
the cheapest step and the one that decides whether everything after it can be judged.

## Rules

1. **Write the guideline before labelling anything.** Include positive and negative examples, boundary rules
   (does "the dockworkers' strike" or just "strike" count?), and what to do when unsure.
2. **Measure agreement (IAA) early, on 30–50 items marked by two annotators.** Use F1 between annotators for spans
   and κ for categories. Two different LLM families (e.g. Claude Haiku and Qwen) are a cheap first proxy; humans
   confirm on a subset.
3. **Low agreement is a definition problem, not a model problem.** If κ < 0.4, rewrite the guideline and re-measure
   before training. Our event-noun layer had judge agreement .38 (κ .27) and failed its gate, while event verbs
   (judge F1 .85) passed easily. LLM-assisted guideline rewrites have lifted human agreement from .59 to .84
   (Bibal et al., CoMeDi 2025).
4. **Gold in stages.** 2 human-checked items find big errors; 11 silver items gated our first student; 20–30 fully
   human-reviewed items per source type are needed to separate small differences; 200–500 for a production pilot.
   Include hard cases: negation, quotes, numbers inside names, non-news text.
5. **Freeze and hash.** The scorer and gold files get a sha recorded in the task card. Any change to either is a new
   version with a new sha; old results are not compared across versions.
6. **Hold out by cluster**, not by random sentence: different publishers, time ranges and events in test than in
   training. Remove near-duplicates across splits.
7. **Keep source text private.** Gold built from publisher articles stays in private storage; public pages show
   numbers only.

## Done when

Guideline v1 exists; IAA per layer is recorded with the items used; gold and scorer are frozen with shas; the gate
per layer (0.8 × IAA) is written on the task card. Our news gates, for scale: entity .739, event noun .65, event
verb .754, triggers .703, time .717, quantity .80 (overlap F1, L294).
