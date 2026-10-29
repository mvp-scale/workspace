# 03 · Teacher labels

**Goal:** thousands of training labels at near-human quality, for dollars not weeks, with a known error profile.

## Rules

1. **CPU pass first, LLM second.** Rules, dictionaries, spaCy or regex propose candidates; the LLM accepts, rejects
   or fixes them. Never send raw corpora to an LLM as the first filter. Measured (T51–T54): CPU candidates alone passed 5/6
   layer gates; Haiku single pass 3/6 at $2.36 per 1,000 articles; CPU candidates + Haiku verify 6/6 at $0.75 per
   1,000; 1,000 articles labelled for $0.87 in ~22 minutes via the Batch API.
2. **Constrained output.** The LLM returns JSON that references candidate ids or character offsets, validated by
   code. Reject and retry malformed output; never hand-fix labels silently.
3. **Two model families, then consensus.** One closed (Claude Haiku via Batch API) and one open model run on your own
   GPU (Qwen-class on a local 3090/5090). Keep labels both agree on; send disagreements to review or drop them.
   The pair's agreement is itself the IAA proxy from chapter 02.
4. **Batch API + prompt caching** for the closed model; put the guideline and examples in the cached prefix. Log
   spend per job (`spend.jsonl`), with a $ cap on the task card.
5. **Active learning: test it, don't assume it.** Least-sure sampling (Shen et al. 2017) gave ENT +.009 over random
   with a 95% interval of [−.012, .028] in T62, so no measurable gain at our scale. Use random or stratified
   sampling by default; try uncertainty sampling only with a pre-set comparison against random.
6. **Short per-layer calls beat one long generation.** One 12k-token answer per article gave entity recall .37 and
   output loops; CPU candidates + short verify calls per layer passed 6/6 gates (L284, L293).
7. **Teacher labels are weak labels.** They train the student; they never replace the human gold used for gating.
8. **Licensing.** Check the provider terms for using outputs as training data. Kaggle's Model Proxy was evaluation-only
   for us; labels for training came from our own API keys or our own GPUs.

## Done when

Label pool with per-item provenance (which teacher, which prompt version), measured teacher-vs-teacher and
teacher-vs-gold agreement, and spend recorded against the cap.
