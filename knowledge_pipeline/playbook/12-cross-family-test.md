# 12 · Cross-family test: one test, any model

**Goal:** the same test, run on a model from Anthropic, OpenAI, Google, TypeSafe or a local file, returns a score that can be compared. Written 2026-11-04 after an audit found the presence comparison unfair in five ways (ledger L674, L675).

## The bundle (frozen before any model runs, sha256 recorded)
1. **Items:** the full text of each item, selected without any rater's output.
2. **Instruction text:** one file (guideline, layers, examples). Every family gets this text, word for word.
3. **Output contract:** one JSON schema. Where a family supports schema-constrained output (Anthropic `output_config`, OpenAI `response_format`, Gemini `responseSchema`, vLLM `guided_json`) use it for all that do; list any family that cannot.
4. **Decoding contract:** temperature 0, same max tokens, reasoning off or the same declared budget.
5. **Scorer:** one script, one alpha formula, one bootstrap.

## Adapters carry the content, they do not change it
| Family | Carrier |
|---|---|
| Anthropic | system = instruction text, user = item, schema, temperature 0 |
| OpenAI | system message, user message, strict json_schema, temperature 0, seed (adapter to build; no key on this machine) |
| Google | system_instruction, contents, responseSchema, temperature 0 (adapter to build; no key on this machine) |
| Local (vLLM) | chat template, guided_json, temperature 0, thinking off |
| Jev (typed questions) | the same instruction text in `instructions`, the full item in `state`, one closing yes/no sentence; P(yes) at 0.5 and also AUC |

## Fairness rules (each one failed at least once on 2026-11-03/04)
- **F1 Same content.** No per-model rewording. The wrapper sentence a carrier needs (Jev) is logged. *Failed:* Jev got a shorter question I wrote, with an exclusion that is not in the guideline, and only 450 characters (15% of items were cut). Alpha 0.411 then, 0.668 with the same instructions.
- **F2 Blind selection.** Nothing a rater said may choose the items. If the set is enriched, use a certainty stratum plus a weighted sample and report population-weighted numbers. *Failed:* the 600 items were chosen using Sonnet v2 and Gemma output; Gemma read 0.523 and 0.590 once weighted.
- **F3 Same decoding.** *Failed:* Sonnet ran at the API default temperature with a schema; Gemma and Qwen at temperature 0 without one.
- **F4 Every rater gets a same-rater control.** A temperature-0 rerun is deterministic and proves nothing, so reshuffle the item order and add a meaning-preserving paraphrase of the instructions. *Failed:* only Sonnet had a rerun, so its 0.954 sat beside cross-model figures.
- **F5 No reference model.** Report every pairwise alpha (alpha is symmetric) and a panel alpha with intervals. "Agreement with Sonnet" is a product statement, not a validity test.
- **F6 Equal development budget.** The instruction text is frozen before the first scored run. It was developed with Sonnet and Haiku (L499 to L527); tuning on one family favours it. Record the history, and test on items not used to tune.
- **F7 Leakage.** Hash-check items against examples and tuning sets.
- **F8 Pre-register** the verdict rule, thresholds and sample before running; disclose the run order.
- **F9 Invariance suite.** Matched items that change one element (forecast, plan, warning, single small event) run on every rater.
- **F10 Run card per rater:** model id and version, date, settings, parse failures, spend.

## Verdict for a field
Panel alpha and the share of pairs at or above 0.667 (Krippendorff's tentative band). Clear needs the panel at 0.80 or more. A field whose panel interval straddles 0.667 is reported as borderline, not as valid or invalid.

## Status of the presence test against this protocol (2026-11-04)
Met: F1 for Gemma, Qwen and the second Jev run; F5; F9 (suite M, 144 items). Partly: F2 (design weights, not blind). Not met: F3, F4 for non-Sonnet raters, F6, and OpenAI and Google (no keys, no adapters).
