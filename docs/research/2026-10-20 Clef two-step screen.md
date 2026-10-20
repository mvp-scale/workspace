# Clef two-step screen: design and pass bars (fixed before running)

Date: 2026-10-20. Ledger: T-0009. Context: vLLM NVFP4 Clef reaches 38.8 stories/min; the vLLM pass is near the card's compute limit (F-0045), so 60/min needs fewer tokens per story. Adopted earlier as "Two-step screen" (`probes/world-engine/analysis/prd-review.md`), never built.

## Design

- **Step 1, one call per story (88 questions):** the engine's 10 story-type, scope and focus questions, plus one screening question per condition key (78 = 39 conditions x up/down). Each screening question is built from that key's own attribute definitions in the ontology: "Does the story report any of: <definition 1>; <definition 2>; ...?"
- **Step 2, only for keys flagged in step 1** (screen probability >= 0.20, set low to protect recall): the key's full attribute questions, both engine wordings, 20 per call, exactly as the engine asks them today.
- **Readings** come from the engine's own rule (`classify.read`) on the step-2 answers; unflagged keys count as absent.
- **Model and engine:** alpha-x-ai Clef-Flash NVFP4 on vLLM 0.30 (F-0043, F-0044), head pipelined.

## Evaluation (100 random stories + up to 60 stories enriched for rare keys)

Changes after MM3-0480 (risks q7 0.83, q8 0.83):
- **Silent misses (q7):** each screening question names the key's attributes and their definitions; recall is reported **per key**, and every missed positive is listed with its screen probability.
- **Rare keys (q8):** besides 100 random stories, up to 60 stories are added that the existing llama.cpp labels mark positive for keys with < 5 positives in the random set; recall is reported with a Wilson 95% interval, and separately for the random set (unbiased) and the enriched set (rare-key coverage).

- Reference A: the full 328-question battery, same model and engine, 20 per call.
- Reference B: the same battery on bf16 Clef-Flash (quality anchor), on the first 20 stories (F-0044).

## Pass bars

1. **Recall of the screen:** >= 95% of the condition keys present in reference A are flagged in step 1.
2. **Readings:** stories with identical readings to reference A >= 85 of 100.
3. **Speed:** >= 60 stories/min.
4. **Quality anchor:** on the 20 bf16 stories, identical readings to bf16 >= 15 of 20 (today 16 of 20).

If 1 or 2 fails, lower the screen threshold once (0.10) and re-measure; if it still fails, the screen is not adopted.
