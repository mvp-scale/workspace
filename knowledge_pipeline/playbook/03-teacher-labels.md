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

## CPU-first cascade before any LLM (owner method, adopted 2026-11-01; measured on 7,710 doubly-labelled items)

Why: an LLM labeller is a subjective decider with run-to-run variance (re-asking changes about 14 percent of Haiku's condition answers). Repeatable CPU layers give independent signals, a router that shrinks the questions, and features the student reuses later. Order: segment -> cheap layers -> fuse -> ask an LLM only about what is left.

| Layer | What it gives | Measured (agreement with the two-model consensus) |
|---|---|---|
| Probe library (generated from the guideline text, static embedding, per-probe z-score) | Is condition X present; routes 38 conditions to a shortlist | AUC 0.87-0.88 over 34 conditions; right condition in top 5 of 38 for 83 percent of agreed items (runs/embedprobe, runs/cosinelib) |
| Short probes (4-5 content words, no filler) | Same signal with 55 percent fewer probes | 0.870 vs 0.878 |
| Structure (spaCy: all entity types, reporting verbs and claimer, quotes, modals, hedges, negation, evidence words, numbers, places) | Story type, scope, claim/evidence presence | Story type balanced accuracy 0.64; forecast and opinion recall 0.68-0.70 |
| Change-word lexicon | Direction (up/down) | Balanced accuracy 0.69: up 0.82, down 0.56 |
| Extracted claim re-scored by the probes | Extra signal | +0.010 AUC (the claim is LLM-written) |
| Fusion: per-condition logistic regression, cross-validated | Combines layers | 0.905 vs 0.889 for the best single layer |

What did NOT work (do not retry as-is): the inverse or negated probe subtracted from the positive one (AUC 0.43-0.46, static embeddings encode topic not polarity); 5-word windows of the article (hurt routing); direction from up-minus-down embedding similarity (0.65, below the always-up 0.81); HDBSCAN on probe scores (73 percent noise); grouping the 38 conditions into 7 families (+0.026).
Rules: (1) Fuse with a learned stacked model, never a plain sum: signals are correlated, so gains add slowly (+0.005 to +0.01 per layer) and independent-signal arithmetic overcounts (Snorkel, arxiv 1711.10160). (2) Report per-class numbers and the majority baseline beside accuracy. (3) Prediction first, score after, lesson on the ledger. (4) Scores are against model consensus, so label noise is a ceiling; a small human gold is the only outside check. (5) Guard power words (up, down, more, less) by testing with and without them.
Professional pattern for the structure layer: sentence split, NER, event trigger plus realis (actual vs hypothetical), argument roles, claim span and claimer, entity linking (NewsClaims, arxiv 2112.08544). "Evidence" has no standard stage; attribution of a claim to its source is the nearest.

## Fingerprint store (why, not just what)
- **Idea:** keep, for every item and every output, the parts that were present (content-word lemmas, adjacent pairs, headline-only words, entity types and names, structure flags, source) beside the labels from every layer (Haiku, Sonnet, Clef, Jev, story type, topic). Mine across the whole collection, never one item.
- **Statistic:** 2x2 log-odds ratio of presence, +0.5 smoothing, z = ratio / standard error. Drop parts present in over 95% of items. **Always test the statistic on a part present in every item; it must score near zero.** A prior-smoothed log-odds on presence failed this test (L185).
- **Size:** the top-50 parts of "names a condition" repeat on an independent sample only 12% at 1,000 items, 42% at 5,000 and 52% at 12,000 (no plateau yet). Pool batches; promote a part to a rule only after it repeats on an independent sample.
- **Floor:** items with almost no significant parts (5 or fewer hits) are 15.6% of the field and carry a condition 4.6% of the time. Report coverage per output instead of forcing a value.
- **Code:** `projects/world-state/fingerprint_store.py`; store `runs/fingerprint/fingerprints.db` (git-ignored, publisher-derived).

## Label store, versions and what to pool (2026-11-04; ledger L643 to L649)
- **One store.** `projects/world-state/build_label_store.py` collects every `labels.jsonl` into `runs/label_store/` (180,889 rows, 50,354 items, by labeller, model and prompt version). Train from it, newest version first, one label per item. Before this, each experiment read its own folders and left out 10,000 version-2 Sonnet rows and 19,500 wave rows.
- **Pool across versions only where the versions agree.** Presence agrees between guideline versions at alpha 0.71 (v2 against v3b). Adding the 7,900 older wave rows lifted story and topic but cut presence recall at 80% precision from about 0.5 to about 0.4; train a field on the versions that define it the same way (`TA_PRES_MAX` in `train_all_sonnet.py`).
- **Weaker labellers add nothing at volume.** 46,700 Gemma pool labels did not move story or topic (L608 to L611); 10,800 Haiku rows lowered story from 0.920 to 0.903 (L649). A vote across different labellers does help presence (Gemma + Qwen 27B + Haiku, two of three: alpha 0.64 against 0.52 to 0.57 for any one; L646).
- **Pilot a yield before buying it.** A presence model with AUC 0.93 ranked the pool, yet its top 3,000 held 136 positives (4.5%), not the 450 to 650 forecast (L636).
- **Batch API.** The tool's cost cap uses the worst case, so a low cap trims a chunk to about 120 items; run 1,500 to 2,000 per batch with a spend check between, 15 to 30 minutes each, real cost about 0.0015 USD an item (L618, L634).
