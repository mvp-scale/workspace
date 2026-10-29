# Workstreams: the pipeline broken into packages

Each package has one owner (team or agent), a defined input and output, and a gate. Packages talk only through the
contracts in PRD v0.2 section B (`SourceEnvelope`, `SemanticCandidate`, `KnowledgeUpdate`). A team can build its
package against fixture files before the upstream package exists.

Status: **done** = measured and shipped for English news; **partial** = exists but misses part of the contract;
**open** = not started.

## Packages

| ID | Package | In → out | Status | Gate (how we know it works) | Playbook chapters |
|---|---|---|---|---|---|
| P0 | Evaluation kit | — → frozen scorer, gold sets, gate formula | partial: news scorer + 2 human / 11 silver articles | Scorer sha pinned; IAA measured per layer; 20–30 human-reviewed items per source type | 02, 06 |
| P1 | Adapters | channel payload → `SourceEnvelope` | open | ≥99% valid envelopes per format; idempotent re-ingest; no silent loss | — |
| P2 | Triage router | envelope → skip / metadata / topic / full | partial: topic router, top-3 recall .97 | Recall on "matters" items ≥ agreed floor; < 1 ms per item | 04, 07 |
| P3 | Segment | blocks → offset-stable spans and windows | partial: sentences, zones, 254-token windows | Offsets round-trip exactly | — |
| P4 | Classify (topic, intent) | spans → multi-label topic, intent/modality | partial: IPTC L1 .86, world topics .76–.80 | Macro F1 ≥ 0.8 × IAA, per-label check | 01–07 |
| P5 | Detect (spans) | spans → entity, event, time, quantity candidates | done (untyped) | Per-layer 0.8 × IAA, lower 95% bound | 01–07 |
| P5b | Detect: types, roles, modality, coreference | spans → typed entities, event roles, assertion fields, merged mentions | open (coref test passed) | Same as P5, per new head | 03–06 |
| P6 | Direction / impact | event + topic → up/down/unknown per World Engine condition | open | IAA first; "unknown" allowed and measured | 01–06 |
| P7 | Resolve (anchors) | mentions → anchor IDs or abstain | open | Precision ≥ .90, recall ≥ .80 on held-out; abstain otherwise | — |
| P8 | Reconcile (events across sources) | candidates vs graph → proposed update | open | Merge precision ≥ .95; false merge < 1% | — |
| P9 | Verify + write | proposed update → graph rows | open (TypeScript app owns the writer) | 100% evidence spans resolvable; atomic commits | — |
| P10 | Projections + World Engine adapter | graph → Pulse / Area / Understanding, condition deltas | open | Every displayed movement drills down to evidence | — |
| P11 | Runtime + speed | all heads → one CPU service, browser build | partial: Python 4×1 processes; browser demo | Items/s/vCPU against the owner's target; p95 latency | 07, 09 |

## Angles

How the teams named by the owner can attack this in parallel without blocking each other.

| Angle | Owns | First deliverable | Depends on |
|---|---|---|---|
| **World model** | P6, P10 (World Engine adapter), condition and track definitions | A labelled guideline for direction per condition, with 50 doubly-annotated examples and the measured agreement | P5 output (exists) |
| **Knowledge management** | P7, P8, P9, anchor schema | Anchor table + alias list for the top 500 entities in the news corpus; resolution precision on 200 held-out mentions | P5 output (exists) |
| **Ingestion** | P1, P2, P3 | `SourceEnvelope` adapters for RSS, email and Markdown with fixtures | none |
| **Model training** | P0, P4, P5, P5b, P11 | Student v3: one encoder, heads for spans + types + topic + POS, no spaCy | P0; GPU (Kaggle or local 3090/5090) |

## Order of work

1. P0 for every new source type before any model work on it (chapter 02). Cheap, and everything else is judged by it.
2. In parallel: P7 (biggest gap: nothing links mentions to IDs) and P5b (types and roles feed P7 and P6).
3. P6 only after its guideline reaches agreement; low agreement means the definition is the work item.
4. P2 and P11 together, against the owner's throughput target (PRD v0.2 section M).

Each package starts as a task card (`templates/task-card.md`) on the ledger with its definition of done and stop rule.
