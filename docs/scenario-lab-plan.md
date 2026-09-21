# Scenario lab plan

Status as of 2026-09-22. "Done" is committed; everything else is proposed and waits on the decisions at the end.

## Done
- Set list shows names only, grouped by family; item and class counts moved to a tooltip (fe85242).
- Overview is a numberless 7-step heat map with a scale, all 15 sets on screen, numbers in tooltips (8363c83).

## Layout
1. Flip the overview: models across the top (nine short codes), sets down as rows under family headings. Rows expand in place: per-model accuracy with intervals, calibration, confusion split, and the items sorted by model disagreement.
2. Family header strip is now empty (labels were truncated). Restore labels or remove the strip.
3. Colour is relative to chance, so low-chance sets (Fallacies 13%, Dark patterns 14%) look greener at equal accuracy. Show it or normalise it.

## More sets
4. New sets through the existing pipeline: seeded `probes/v2/build_*.py` -> `.jsonl` + `.md` (source, licence, label caveats). Families: security, conversation flow, reasoning, looping, subtext, fraud. Candidates: PII (Gretel), support escalation (ABCD), prosocial safety (ProsocialDialog), toxicity, negotiation, contract clauses. Before building: confirm outbound access to Hugging Face and GitHub; record each licence.
5. Private sets from the user's own labelled data (a few dozen items is enough).

## Structures that make sets harder
6. Batch performance: one state, 5/10/20/40/80/160 questions. Record total and per-answer latency, accuracy as the batch grows, and the context or question-count limit. Local models first; the hosted model only with approval. Known ceilings: demo server 400 items, Beam 32 questions, Laya state+question 512 tokens.
7. Cascade (routing): cheap model first, stronger model on uncertain items. Measure accuracy against share escalated.
8. Funnel (Monte Carlo): atomic questions, sample each answer from its probability, combine by a rule, report a forecast with an interval and which atoms drive it. Needs correlation handling, calibrated atoms and labelled outcomes.
9. Decompose and loop: ask about the whole, split, recurse into high-scoring pieces (words, sentences, turns for looping). Keep the whole-text score next to the pieces. Compare with leave-one-out.
10. Incremental state: read only new words per verdict versus re-reading the window.
11. Hierarchy: cheap gate questions, fine questions only when the gate opens.
12. Time: onset, escalation, detection lag, false alarms per minute.
13. Every claim gets a baseline (generative LLM or single-question classifier) on the same items: tokens, latency, accuracy with intervals. Some structures may show no gain.

## Blind grading
14. Repeatable blind run: fixed seed, stratified draws, sealed key, n of 60 to 100 per set, grades revealed afterwards, Run button in the lab. A 12-item trial on KEV4B scored 7/12 (too small to conclude anything).

## Lineup and benchmark
15. Sync jevbench (upstream is at least 8 commits ahead, up to v1.3.0, which changes scoring); check whether stored results can be re-scored.
16. Update SemIf/OpenJev (CPU backend, EXL3, temperature calibration upstream).
17. Candidates: Winnow-12B Q8, reflex 4B, Open-Jev 2B/9B, djev, rerankers. GPU is nearly full, so this is a lineup decision.
18. Report which model actually answered.

## Decisions needed
- First area: fraud escalation (data exists, saving easy to measure), conversation flow, or looping/decomposition.
- Overview orientation (item 1).
- Set groups and the per-set template (the "set pattern"), to fix before building.
