# Knowledge pipeline: consolidation plan (v2)

2026-11-19. v2 folds in an independent Opus review (`scratchpad/team/opus_plan_review.md`, findings spot-checked). Evidence: `knowledge_pipeline/.ledger` L2694–L2728. Structure: playbook 00 (G0–G6, §8, §9, §13, §18). Shown on the sim page: http://localhost:8100/docs/notes/sim

## The point
**Read → extract → mini knowledge graph (with sources) → decide fast → weak spots retrain BitMob → read better.**
The graph feeds the **resource ledger** (owner design, L2707). Topics map to resources. Each resource moves by a small step when it's talked about, a larger step when it's stated positive or negative, and a multiplier with direction when there's a substantial change. Each step decays over time. The seed is the engine's 26 resources; the list grows from our ontology.

## Rules
1. **One ID space.** Topics are IPTC codes, names are Wikidata IDs, places are GeoNames IDs. Never join on a label string. MN-DS gold labels are names only, so a versioned name→code table is built first.
2. **Published trees are the backbone; our additions are add-only.** Our nodes live in an `ours:` namespace, are marked *Inferred*, and stay *Provisional* until the promotion test (Q4, L2707) is settled.
3. **Every answer is an evidence set:** node IDs, score, source span, label version (§18.8).
4. **Judged on outside truth only.** Anything hand-made or legacy is labelled *reference*: the 49→17 roll-up behind the trace's `TOPIC_DISAGREE` gap, and the publisher-section map in M2. Licences: CheckThat is non-commercial; MN-DS and MAVEN are scoring only.
5. **Scope never shrinks.** Every head stays ON: Domain, Area, Function, Condition, Capability, Novelty, Place, Time, Factuality, Claims.
6. **Each round:** a prediction before it runs, a score after. One CPU embedding job at a time, under 1 hour. Train and test are split by source and by time (§13).

## The loop, stage by stage (new design, measured)

| Stage (gate) | What it puts in the graph | Measured now | Weak spot | Feeds back by |
|---|---|---|---|---|
| **Read** (G0–G1) | Text, source, time, hash | Replay set: median 311 characters (300 articles). Live trace: body on 149 of 154 items, median 667 characters | Short headline-and-teaser items | Land the body when it's there |
| **Extract** (G2) | Names, places, dates, amounts, triples, roles, verb → event noun | Places: 13,278 of 18,564 linked; two tools agree 98.8% (agreement, not accuracy). Triples: CaRB F1 0.402 | Names untyped; roles loose | Wikidata typing; triple errors go to the hard-example bucket |
| **Classify** (G3) | Topic landing (IPTC code, path, top 3, decision), Function, Factuality, Condition | Landing, top level: 0.562 on MN-DS fresh2 (1,352, includes politics). Live agreement with publisher sections: 0.295 (hand map, reference). **The trace still uses top-level-only cards** (0.425 setting) | Catch-all topics; short text; no calibrated probability | Hard cases go to targeted teacher reads in IPTC codes |
| **Graph** (G4) | Observation → IDs; dedup; independent-publisher count; topic ↔ name links | Topic–name links on 40,724 articles (border dispute ← Trump 167, Russia 161, Ukraine 154, Iran 120). The trace's `independent_counter` exists but isn't used | No name identity; no journal | Unresolved names go to the Wikidata hub |
| **Resource ledger** (G5 / Macro Pulse) | Resource state over time: count, direction, decay, linked names | Trends agree between two halves of the sources: 0.856. Halloween caught, election not. Topic share mean absolute error 0.033 | Shares not accurate enough; conditions not wired in | Repeated off-tree landings become `ours:` candidates |
| **Decide** | Answer / evidence only / abstain / ask the teacher | Decider rules verified in Lean (160 test vectors). The landing gives a cosine score, not a probability | No calibration; margin is a poor gate (0.595 at half coverage) | Abstained items go to the learn queue |
| **Learn** | Training rows with provenance and label version | A student trained on landing labels (0.533 on fresh2) only copies the landing, so it isn't an independent second opinion | Teacher-in-IPTC-codes never measured | This is the loop |

## Bars (field test L2721 plus review additions)

| Need | Measure | Bar | Now |
|---|---|---|---|
| Right topic | MN-DS **by code**, all items | Level 1 ≥ 0.60; level 2 ≥ 0.40 | To re-baseline (0.562 at level 1 on fresh2) |
| Right on live news | Publisher sections (reference map) | ≥ 0.70 | 0.295 |
| Topic shares | Mean absolute share error per Domain, simulated days | ≤ 0.010 | 0.033 |
| Catches events | Change-from-baseline peak on ≥ 5 dated events | ≥ 4 of 5 within ±1 day | 1 of 2 |
| Trends you can trust | Source halves agree; no **level-2** node above 10% of items | ≥ 0.80; none | 0.856; election 8.3% |
| Safe abstain | Accuracy of answered items at the decision line | ≥ 0.80 at ≥ 50% coverage | Not built |
| Cost | Per-article CPU time; cost per learn round | ≤ 20 ms; stated before each round | About 10 ms; — |

## Build order

| # | Build | Resources | Done when | Stop rule |
|---|---|---|---|---|
| 1 | **IDs:** versioned MN-DS name→code table; re-score topics on all items by code; correct L2720 | CPU, about 1 h | Zero label-string joins (check script); M1 re-baselined | — |
| 2 | **Landing into the trace:** replace the top-level-only cards in `live_trace.py`, then re-run M2 with body text | CPU, under 1 h. **Changes the stage contract (needs your OK)** | Trace carries the landing decision object; M2 re-scored | — |
| 3 | **Journal on `chain.jsonl`** (already hash-chained per article): add IDs, label version, dedup and independent-publisher counts | CPU | Replay of 2,739 articles reproduces; syndicated copies counted once | — |
| 4 | **Landing v1:** sentence vote, catch-all damping, a calibrated probability for the decider, an abstain line | CPU rounds under 10 min | Bars: right topic, shares, abstain | Two flat rounds |
| 5 | **Resource ledger v0** on the sim page: topics → the engine's 26 resources, step sizes and decay per L2707, level-2 trends | CPU | Bars: events, trends, shares | — |
| 6 | **Learn loop:** pilot first, Jev answering in IPTC codes on 500 MN-DS items, then targeted reads on hard cases, retrain, re-score | **Hosted Jev: about $0.05 for the pilot (needs your yes)** | +3 points per round | Pilot below the landing → stop |
| 7 | **Names hub:** Wikidata IDs for names; typing and identity | **A Wikidata request larger than the pending 1,307-ID one (needs your yes)** | Bar set when the request is sized | — |

## Needs your yes
1. **Stage-contract change:** put the landing into the trace (step 2).
2. **Jev pilot spend** (step 6), and which spend cap applies: 2.5 or 10 USD.
3. **The Wikidata request** for names (step 7). It's larger than the one pending.
4. **MAVEN, scoring only.**
5. **Resource-ledger panel wording** (R7, L2707) and the promotion test for `ours:` nodes (Q4).
6. **This plan replaces the stale GO.md block.**

## Not doing
- Single best landing as the answer, or cosine margin as confidence.
- A student trained on landing labels presented as an independent check.
- Wikidata alternative names on the cards.
- Merging the published trees.
- WordNet topic domains as topics.
- The "shared name + group" link as same-story evidence (embeddings beat it, L2717).
- Judging new work against legacy components.
- Two CPU embedding jobs at once.
