# 01 · Frame the task

**Goal of this step:** one sentence per decision the model makes, and numbers for what "good enough" and "fast
enough" mean, written down before any data work.

## Rules

1. **One question per head.** "Which words name an event, as a verb?" is a head. "Understand the article" is not.
   Small models are good at narrow, well-defined questions; break broad goals into several heads that share one encoder.
2. **Pick the output shape that fits the question.**

   | Question type | Output | Example |
   |---|---|---|
   | Which span? | BIO tags per token | entities, event triggers, times, amounts |
   | Which category? | multi-label sigmoid over a fixed list | IPTC topics, world topics |
   | Which direction / state? | small softmax incl. "unknown" | up / down / unknown per condition |
   | Are these the same? | pair score or merge tag | coreference, event clustering |

3. **Write the product target as numbers** (owner decision): items per minute, target hardware (vCPU count, CPU
   type), $ per million items, and a quality floor per head. Convert to a per-item budget:
   `vCPU-ms per item = 60,000 × vCPUs / items per minute`. Example: 3,500/min on 4 vCPU → ~69 vCPU-ms per item.
   Our first student needed 680, which is how we knew early that speed work was needed (PRD v0.2 section M).
4. **Say what the model will not do** (abstain cases, out-of-scope inputs) so evaluation can count them.
5. **Reuse before building.** Check for an existing vocabulary and dataset first (IPTC Media Topics + MN-DS for
   news topics, PLOVER/POLECAT for event direction, Wikidata for identities). Check licences before relying on them.

## Done when

The task card lists each head's question and output shape, the per-item budget, and the quality floor, and the
owner has signed off on the targets (a `decision` line on the ledger).
