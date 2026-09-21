---
title: TypeSafe Jev — Hierarchical PII Localization & Standoff State
date: 2026-09-21
model: jev-1.13.0
tags:
  - typesafe
  - jev
  - pii-detection
  - standoff-annotation
  - faceted-indexing
  - prompt-structure
aliases:
  - Jev PII localization
  - Standoff state for Jev
status: experiment-log
---

# TypeSafe Jev — Hierarchical PII Localization & Standoff State

> [!summary]
> One text block in, many typed questions out (speculative fan-out), used to narrow *where* sensitive data sits inside unknown-shape text.
> Seven playground runs showed that the **shape of `state`** matters as much as the questions.
> Best result: **standoff layout**. Keyed paragraphs (text only) come first, then a separate annotation layer (entities + triples) that references them.
> Rule that fell out: **code owns structure, Jev owns meaning.**

---

## 1. Terms

Defined first; everything below refers back to these.

| Term | Meaning |
|---|---|
| Jev | TypeSafe's System One model. Takes `state` + typed questions, returns typed answers with probabilities. |
| State | The content being evaluated. May be a **string**, **JSON object**, or **array**. One state per request; every question sees all of it. |
| Noul | Yes/no question. Returns `noul` = P(yes). **No separate confidence field.** |
| Choice | Pick one option. Returns `choice`, per-option `probabilities` (sum to 1), and `confidence`. Max 255 options. |
| Score | Place on ordered levels. Returns `score`, `probabilities`, `confidence`. |
| Structured fields | `instructions`, Choice option descriptions, Score levels, and Noul `true`/`false` criteria all accept JSON (string, object, array, or null). |
| Speculative fan-out | Put every question you might need in one request; code ignores the irrelevant ones. Questions run in parallel. |
| Unit | A slice of text a question points at: document, paragraph, band (opening/middle/closing), sentence. |
| Phantom unit | A question about a unit that does not exist (e.g. "seventh paragraph" in a 6-paragraph text). |
| Mention vs. value | Text that *talks about* a data type ("a six-digit code") vs. text that *states* the value ("482731"). |
| Faceted indexing | Storing each answer as a facet on a node so later searches filter stored facets instead of re-running the model. |
| Adaptive refinement | Run the same question battery at each level; only recurse into units where a signal fired. |
| Standoff annotation | Annotations stored separately from the unmodified primary text, linked by IDs/offsets. Opposite of inline annotation. |

---

## 2. Core facts from the docs

- Output is **flat**: one typed answer per question. No nested/hierarchical output exists. Hierarchy is built in code by chaining or fanning out calls.
- Pricing (per SDE cascade cookbook, jev-1.12): **input tokens billed, output tokens free**. Extra questions add input tokens (their instructions/criteria), so they're cheap, not free. State is sent once per call.
- Choice probabilities always sum to 1, so a Choice alone can't say "none of these". Pair it with a Noul existence check.
- Documented localization patterns:
  - **Line-by-line search**: tag lines with IDs; Choice over IDs + Noul "does an answer exist".
  - **Hierarchical classification**: one Choice per tree level; greedy or beam search on probabilities.
  - **Pre-parsed value extraction**: regex finds candidates; Jev selects the span.
  - **SDE cascade**: per-field Noul battery, gate with `max` (any flag fires).

---

## 3. Question families used

| Family | Primitive | Example | Tells you |
|---|---|---|---|
| Presence | Noul | Any sensitive info in this text? | Gate |
| Type | Noul × N | Contains an email? phone? address? gov ID? DOB? OTP? | What (several at once) |
| Count | Score | None / One / Two or three / Four or more | How much |
| Band | Noul × 3 | In the opening / middle / closing part? | Rough where |
| Ordinal | Choice | Which sentence first contains it: 1st … later | Finer where |
| Unit presence | Noul × N | Does the *fifth paragraph* contain …? | Where, per unit |
| Phase | Choice per unit | untrusted / verifying / trusted / no_such_paragraph | Trust timeline |
| Discloser | Choice per unit | caller / customer / both / none | Who said it |
| Sequence | Noul | Disclosed before trust was established? | Cross-unit risk |
| Shape probe | Score | How many paragraphs? | Which unit questions to keep |

---

## 4. Experiment log

### Run 1 — single paragraph, PII in closing sentence

- State: one 5-sentence paragraph, phone + email in sentence 5.
- 13 questions · 798 input tokens · 132 ms.
- **All signals matched the answer key.** Bands: opening 0.05 / middle 0.19 / closing 0.99. Ordinal: "5th" @ 0.73.
- Soft: `count` split 0.60 "Two or three" / 0.40 "Four or more" (overcounting first names).

### Run 2 — four paragraphs, untagged string

- 14 questions · 889 input tokens · 144 ms.
- **All matched.** `paragraph_count` Four @ 0.89 — paragraph addressing works on raw text.
- Tightening the count definition in `instructions` moved the correct bucket 0.60 → 0.82.
- Generic `p2_pii` 0.85 vs. specific `p2_address` 0.99 → **specific beats generic**.

### Runs 3–7 — simulated inbound bank call

Text: 6 paragraphs. Customer gives name + ZIP to an unverified caller (¶1), refuses more (¶2), rep offers app + SMS verification (¶3), customer confirms app case number and reads OTP back (¶4), discloses DOB, address, SSN last 4 (¶5), account last 4 (¶6).

Same **36 questions** every run: shape probe, p1–p7 × {pii, phase, discloser}, 9 type Nouls, 5 risk questions. p7 is deliberately speculative (a phantom).

Only the **state layout** changed between runs 3–7.

| Run | State layout | Input tokens | Latency |
|---|---|---|---|
| 3 | String (one block) | 2,885 | 129 ms |
| 4 | Array (one item per paragraph) | 2,887 | 85 ms |
| 5 | Object, keys `first`…`sixth` matching question wording | 2,924 | 93 ms |
| 6 | Object + entities + triples **inline** in each paragraph | 4,078 | 110 ms |
| 7 | Object text + **standoff** annotation layer below | 4,208 | 91 ms |

#### Results

| Signal | Truth | 3 String | 4 Array | 5 Object | 6 Inline | 7 Standoff |
|---|---|---|---|---|---|---|
| paragraph_count | Six | 0.49 | Five 0.56 ❌ | 0.96 | 0.93 | 0.96 |
| p1 pii | yes | 0.62 | 0.52 | 0.64 | 0.49 ❌ | **0.74** |
| p3 pii (mention, no value) | no | 0.88 ❌ | 0.68 ❌ | 0.08 | 0.11 | 0.11 |
| p3 discloser | none | customer ❌ | none 0.63 | **0.88** | 0.70 | 0.68 |
| p4 phase | verifying | trusted ❌ | 0.65 | **0.96** | 0.82 | 0.90 |
| p7 pii (phantom) | n/a | 0.82 ❌ | 0.89 ❌ | 0.09 | 0.42 | **0.06** |
| p7 no_such_paragraph | yes | 0.28 ❌ | 0.34 ❌ | 0.93 | 0.85 | **1.00** |
| pii_before_trust | yes | 0.75 | 0.69 | 0.66 | **0.88** | 0.81 |
| caller_requests_credentials | yes | 0.85 | 0.80 | 0.78 | **0.88** | 0.79 |
| has_card_number | no | 0.38 | 0.41 | 0.28 | 0.29 | 0.33 |
| **p1–p6 correct (of 18)** | | 15 | 17 | 18 | 17 | 18 |
| **p1–p7 correct (of 21)** | | — | — | 21 | 20 | 21 |

Document-level type Nouls (name, account, gov ID, DOB, address, OTP present; phone, email absent) were correct in **every** run.

---

## 5. Findings

### 5.1 Shape
- Untagged text supports coarse localization (bands, paragraph ordinals), but **existence is weak**: phantom p7 was answered with confident content in the string and array runs.
- **Keyed object** fixed counting, existence, and boundary attribution in one move. Keys matched the question wording ("the fifth paragraph" → `fifth`).
  - Open confound: structure vs. lexical key match. See §8.
- Array helped boundaries but not existence, and hurt `paragraph_count` (question said "separated by blank lines"; arrays have none).

### 5.2 Annotations
- **Inline** entities + triples improved cross-paragraph questions (`pii_before_trust`, `caller_requests_credentials`) but hurt per-paragraph ones (p1 pii, p7 phantom, p3/p4 boundaries).
- **Standoff** kept per-paragraph accuracy at 21/21 and kept most of the sequence gain.

### 5.3 Confidence calibration
| Primitive | Behavior on misses |
|---|---|
| Choice / Score | `confidence` dropped (~0.5–0.6) on wrong answers → usable gate |
| Noul | No confidence field; wrong Nouls looked like strong yeses (p3 0.88, p7 0.82) |

### 5.4 Question wording
- Mention-vs-value confusion (¶3) is a **question** problem, not only a state problem. Fix: structured Noul criteria (`true` = actual value stated; `false` = a data type is mentioned without its value).
- `has_card_number` stayed ~0.3 across all layouts → question problem; needs criteria separating card from account.
- Definitions inside `instructions` work (count 0.60 → 0.82).

### 5.5 My errors, recorded
- Called the call a scam from `otp_read_to_caller` alone. The text showed a real out-of-band check (bank app displayed the matching case number). Needs its own question.
- Risk rule `pii > 0.7 AND phase = untrusted` would have missed p1 (0.62) and p3 (verifying). Better: `phase != trusted`, or any disclosure after a code read-back.
- Predictions for the array run were wrong on 4 of 4 signals; the inline-triples run was 1 of 3.
- One malformed triple (`["E1","discloses_to_caller","E1"]`) likely lowered p1 pii in run 6.

---

## 6. The pattern: standoff annotation

The winning layout (run 7) is an established NLP practice: **standoff annotation**.

| | Inline annotation | Standoff annotation |
|---|---|---|
| Where tags live | Inside the text | Separate layer, text untouched |
| Linking | Position in text | IDs and/or character offsets |
| This log | Run 6 | Run 7 |
| Effect on Jev | Bleed into neighbors, phantom returns | Clean units, sequence kept |

Reference standards:

| | brat standoff | W3C Web Annotation Data Model |
|---|---|---|
| Status | De facto NLP corpus format | W3C Recommendation (Feb 2017) |
| Units | Text-bound entities `T`, relations `R` | Annotation linking Body → Target |
| Anchoring | `ID TYPE START END TEXT` character offsets | Selectors (offset, XPath, …) |
| Serialization | `.txt` + `.ann` | JSON-LD |

Gap vs. brat: this layout anchors by paragraph key, not character offsets. Adding offsets would let code map any entity back to exact characters and make the layer reusable outside Jev.

---

## 7. Design rules

1. **Code owns structure.** Split at natural boundaries in code; key units with names the questions use; only ask about units that exist. Drop shape probes and phantom questions once structure is known.
2. **Jev owns meaning.** Presence, type, phase, owner, sequence.
3. **Standoff state.** Text layer first, annotation layer after, references pointing backward only.
4. **Specific over generic.** Gate on the max of type Nouls, not a vague "any PII".
5. **Noul per unit** for multi-hit detection; Choice picks a single winner.
6. **Gate Choice/Score on `confidence`**; cross-check high Nouls against sibling questions.
7. **Fan out greedily** in one call; output is free, input grows with each question.

### State template

```json
{
  "paragraphs": {
    "first": "…text…",
    "second": "…text…"
  },
  "annotations": {
    "note": "Extracted automatically; may be wrong. Paragraph text is authoritative.",
    "entities": {
      "E1": { "text": "…", "type": "PERSON", "value_stated": true, "first_seen": "first" }
    },
    "by_paragraph": {
      "first": {
        "mentions": ["E1"],
        "triples": [["E1", "discloses_to_caller", "\"full name\""]]
      }
    }
  }
}
```

### Question templates

```json
{
  "p1_pii":   { "type": "noul", "instructions": "Does the first paragraph contain sensitive personal or account information?" },
  "p1_phase": { "type": "choice",
                "instructions": "What trust state is the conversation in during the first paragraph?",
                "criteria": { "untrusted": "…", "verifying": "…", "trusted": "…" } },
  "pii_before_trust": { "type": "noul", "instructions": "Does the customer disclose sensitive information before confirming the caller is really the bank?" }
}
```

### Index record (faceted)

| Field | Example |
|---|---|
| path | `call42 / fifth` |
| level | paragraph |
| pii | 0.99 |
| phase | trusted |
| discloser | customer |
| types | DOB, address, gov ID partial |

---

## 8. Open questions / next tests

- [ ] **Key-name confound:** rerun standoff with keys `p1`…`p6` while questions still say "the fifth paragraph". Accuracy holds → structure did it; drops → lexical match did.
- [ ] **Anchoring:** plant one wrong triple (e.g. tag "six-digit code" as OTP in ¶3). If p3 pii jumps, Jev trusts annotations over text → NER quality is the ceiling.
- [ ] **Mention-vs-value criteria** on pii and discloser questions.
- [ ] **Card vs. account** structured criteria for `has_card_number`.
- [ ] **Out-of-band verification** question: confirmed through a channel the caller doesn't control?
- [ ] **Real vs. perceived trust:** did the verification actually prove the caller is the bank?
- [ ] **Depth:** 10–12 untagged paragraphs; where does ordinal addressing break?
- [ ] **Negatives:** order numbers, SKUs, version strings; false-positive rate.
- [ ] **Offsets:** add brat-style character offsets to the annotation layer.

---

## 9. Sources

- TypeSafe — [Advanced: structure](https://docs.typesafe.ai/primitives/advanced)
- TypeSafe — [State](https://docs.typesafe.ai/concepts/state)
- TypeSafe — [Speculative fan-out](https://docs.typesafe.ai/patterns/fan-out)
- TypeSafe — [Line-by-line search](https://docs.typesafe.ai/cookbooks/semantic_find)
- TypeSafe — [Hierarchical classification](https://docs.typesafe.ai/cookbooks/hierarchical_classification)
- TypeSafe — [SDE cascade](https://docs.typesafe.ai/cookbooks/sde_cascade)
- TypeSafe — [Pre-parsed value extraction](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook)
- TypeSafe — [Structure recovery](https://docs.typesafe.ai/cookbooks/autoformat)
- TypeSafe — [Self-consistency: nouls](https://docs.typesafe.ai/cookbooks/consistency_noul_cookbook)
- TypeSafe — [Docs index](https://docs.typesafe.ai/llms.txt)
- brat — [Standoff format](https://brat.nlplab.org/standoff.html)
- W3C — [Web Annotation Data Model](https://www.w3.org/TR/annotation-model/)