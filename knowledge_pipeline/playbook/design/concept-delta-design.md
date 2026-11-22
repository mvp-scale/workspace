# Concept-delta design: consume thousands of articles in minutes, show only what moved

Author: Fable designer `[F?]` (effort digit unknown: `~/.claude/settings.json` has no `effortLevel`). Date 2026-11-22. Scope: design and measurement only. No pipeline code, page or gate was edited. CPU only, no hosted calls, no downloads (three web pages were read for citations, nothing saved). Ledger task T158.

Every number marked **measured** was produced in this session on this box (i9-10900K, 10 cores / 20 threads, 62 GB RAM, 16 GB free, load average 1.5) with the scripts in this scratchpad (`bench_embed.py`, `bench_join.py`, `bench_blas2.py`) or read from the staged area traces `/workspace/demo/mockups/structure-live/area-{c1,mix}/trace/`. Everything else is marked **estimate** or **design**.

---

## 0. The core model in five lines

1. **Knowledge = concept cards + typed, directed, dated links between them.** A concept is a slow node (entity, resource, place, process type, capability). An event is fast evidence: a dated fact slot that moves a concept's direction or certainty, or adds / contradicts a link. Events are never nodes until they recur (playbook section 8: "an event is not automatically a taxonomy node"; section 9 promotion gates).
2. **Every article gets a triage verdict against the graph before anything expensive runs:** `known` (cheap, never shown) | `update` (moves a direction or certainty) | `new-link` | `new-concept` | `conflict`. The verdict is the Lean decider's change-or-abstain question asked per concept, not per article.
3. **Certainty comes from independent owners, time and contradictions**, computed with the rules the pipeline already has (owner-based independence in `consolidate.independence`, the 7-day half-life decay already in `consolidated.json`, `g4_align.contradict_edges`). Owner marks never enter certainty.
4. **A concept has a state** (gap / emerging / active / settled / contested) with mechanical transitions; `settled` is a claim about stability of the evidence, not about truth, and one independent owner cannot reopen it (two can; a contradiction always can).
5. **Throughput comes from a tiered cascade on the two clocks that exist:** the fast clock stops `known` articles at ~1 ms (journal) or ~250 ms (cheap read + concept match); the slow clock spends its ~1 s only on the delta sentences of the articles that passed; consolidation reuses the embeddings computed once.

---

## 1. The matured model

### 1.1 Concept card schema (design; slot sources named)

```
concept_card
  id            ours:<slug> | wd:Q... | iso:XX | resource:<id> | cap:<slug>      (G4 entity id, or the consolidate.py candidate id)
  label         canonical surface                                                (G4 alias cluster canon)
  kind          entity | place | resource | process | capability | event-type    (G4 type; resource from resources.csv; capability from consolidate.open_caps)
  what_it_is    {text, source: wikidata | wordnet | iptc | resources.csv | none, ref}   (wikidata_cache.resolve -> description; WordNet gloss; IPTC definition; resources.csv definition)
  purpose       {text, source, attributed_to}                                     (ONLY for agents and instruments; see 7.1, I disagree with a free 'goal' slot)
  direction     {sign: up|down|flat|unknown, magnitude 0..1, since, up_n, down_n, owners}   (direction_v1 story reads + Conditions head on resource edges; math in 1.4)
  drivers       [{concept, relation: causes, sub: immediate|contributing, certainty, since, evidence}]   (1.2; causal cue v0 edges exist in g4_align 'via')
  resources     [{resource, country, effect: draws|adds|damages|unknown, direction, V, dV, N, C, U}]   (resource edges + ledger_split ResourceState; playbook 10)
  related       [{concept, relation, direction, certainty, last_seen}]            (typed links, 1.2)
  state         gap | emerging | active | settled | contested                    (1.5)
  certainty     0..1 (1.4)                                                        (never from owner marks)
  coverage      {articles, owners, publishers, days, first_seen, last_seen, windows}   (consolidate strength / independent / days; playbook 10 'coverage and freshness apart from confidence')
  open_conflicts [{a, b, kind, earlier, later}]                                   (knowledge.json contested[])
  owner_mark    {mark: settled|follow|ignore|none, at, last_seen_by_owner}        (section 5; a separate file, never an input to certainty)
  gaps          [what_it_is missing | no direction | no driver | one owner only | stale > 2 windows]
```

Rule: every filled slot carries its pointer (edge id -> fragments {art, pub, sent}); an unfilled slot says why (`gaps`). This is the `educate.py` discipline (templates + refs, no free text) extended to a card.

### 1.2 Typed relation set (design, with the sets I checked)

Start from the eight relations the playbook already defines in section 9 (`is_a, part_of, enables, requires, related_to, same_as, supported_by, contradicts`). Keep all eight and their invariants. Add four, each justified against a public set I read this session:

| Relation | Direction / fields | Why this one | Source checked |
|---|---|---|---|
| `causes` | A -> B, `sub: immediate \| contributing`, certainty, since | The owner's "drivers". Wikidata splits cause into `has cause` P828 (underlying), `has immediate cause` P1478, `has contributing factor` P1479, inverse `has effect` P1542; we keep one relation with a `sub` flag so the extractor can abstain on the sub-type. ConceptNet `Causes` is the same idea between event terms. | wikidata.org/wiki/Property:P828 (read 2026-11-22); ConceptNet relations wiki (34 relations, read 2026-11-22) |
| `affects_resource` | concept -> resource:<id>, `country`, `direction`, `effect` | The owner's "resources it uses or impacts". This is the resource edge plus the Conditions head with direction (playbook 18.6), not a new mechanism. No public set has it; ConceptNet `UsedFor` is the nearest and is too lexical. | playbook 00 section 18.6; resources.csv (26 resources, draft v2) |
| `opposes` | A <-> B (symmetric), dated, owners | Conflict actors. Needed for the Gulf card: iso:SA / iso:IR / houthis / iso:US. The verb classes that fire it already exist as assertion predicates (strike, target, fight, destroy, intercept, threaten). ConceptNet `Antonym` is lexical and does not fit; CAMEO's conflict quad class is the right precedent (CAMEO is already in the integration plan, docs/research 2026-11-18). | consolidated.json mix edges; docs/research/2026-11-18 Reference sources |
| `precedes` | event-slot A -> event-slot B, days | Time order between two fact slots on one concept (care -> died). The time-aware status rule in `g4_align` already computes `order {earlier, later, days}`; naming it a relation lets the card show a timeline and stops timelines from being counted as conflicts. FrameNet has `Precedes` and `Subframe` between frames; ConceptNet has `HasSubevent / HasFirstSubevent / HasLastSubevent`. | en.wikipedia.org/wiki/FrameNet (9 frame relations, read 2026-11-22); ConceptNet wiki |

What I deliberately leave out of the main session's proposal: a separate `uses / capable-of` relation. The Capability node (`cap:affect-price`, `cap:destroy-missile`) already is the uses link (concept -> capability placement, `consolidate.edge_cap_labels`), and ConceptNet `CapableOf` is a lexical commonsense relation, not something a news reader can ground. `depends_on` = playbook `requires`; do not add a synonym.

Event-centric precedent: EventKG (Gottschalk and Demidova, arXiv 1804.04526, abstract read 2026-11-22: 690k events, 2.3M temporal relations) makes events first-class nodes with time stamps. We do the opposite on purpose: events are evidence until promotion, because the owner's goal is "get the core concept quickly and move on", and a node per event is what makes a graph unreadable at 2000 articles a window. The compression ratio in section 4 measures whether that choice holds.

### 1.3 Concept versus event (design)

| | Concept | Event (fact slot) |
|---|---|---|
| Lifetime | windows to years | one window, decays (half-life 7 days, PROVISIONAL rule already in consolidated.json) |
| Where it lives today | G4 entity (`ent`), IPTC node, resource id, capability | assertion slot after `consolidate.slot_merge` (fact_join, ECB+ F1 0.506) |
| Created by | section 9 promotion (>= 3 owners, >= 2 windows: `consolidate.MIN_PUBLISHERS / MIN_WINDOWS`), or a seed (IPTC, resources.csv, Wikidata hit) | every article, cheaply |
| Changes | state, direction, certainty, links | never; it is immutable evidence |
| Shown | as a card | only inside a delta item or a card's timeline |

Promotion of an event-type to a concept (for example "Houthi missile attack on Riyadh" -> "Houthi-Saudi conflict") follows section 9 unchanged: recurrence across windows and owners. The Wikipedia current-events anchors (`/workspace/data/anchors/current_events/`, CC BY-SA 4.0; 2026-11-19 lists "Houthi-Saudi conflict" and "2026 Strait of Hormuz crisis" as named items) are the outside truth for whether such a concept exists on a day, see section 4.

### 1.4 Certainty and direction math (design; constants PROVISIONAL)

Inputs per link or per direction claim, all already computed by the pipeline:
- `S_k` = set of independent sources for side k (`consolidate.independence`: one source per story root or near-identical sentence, named by owner via `publisher-owners.json`).
- `age(s)` days since the source's day; `w(s) = 0.5 ^ (age / 7)` (the existing decay rule).
- Support `sup_k = sum over s in S_k of w(s)`.

Link certainty (for `causes`, `opposes`, `affects_resource`, `is_a` ...):
```
cert = sup_for / (sup_for + sup_against + 1)
```
The `+1` is a one-source prior: one fresh owner gives 0.5, three give 0.75, three plus one fresh contradiction give 0.6. `sup_against` is the decayed support of contradiction edges (`g4_align.contradict_edges`, kinds polarity / amount / status / direction) on the same key.

Direction of a concept (or of a resource edge):
```
up = sum of w over up reads;  down = sum of w over down reads   (direction_v1 story reads; Conditions head on resource edges)
sign = up > down ? up : down > up ? down : flat;  magnitude = |up - down| / (up + down + 1)
```
A direction with `up + down < 2` (fewer than two fresh independent owners) is reported as `unknown`, matching the decider's `TOO_FEW_ITEMS` marker.

Mapping to the playbook 10 pulse `(V, dV, N, C, U)`: `V` = |S|, `dV` = V this window minus the window before, `N` = share of this concept's links first seen this window, `C` = number of open contradiction pairs, `U` = 1 - cert. Coverage and freshness are reported beside, never folded in.

Why not a learned calibrator: there are no human labels (rule) and the outside truths we have (ECB+, current events, resource snapshots) say *whether* something happened, not *how certain* a reader should be. The constants (prior 1, half-life 7 d, two-owner floor) are therefore stated as guesses and section 4.6 says how a replay against current-events anchors can move them.

### 1.5 Concept states and transitions (design)

| State | Enter when | Leave when |
|---|---|---|
| `gap` | referenced by >= 1 assertion, no `what_it_is` and fewer than 2 owners | a definition resolves (Wikidata / WordNet / IPTC) or 2 owners -> `emerging` |
| `emerging` | seen in 1 window, or 2 owners | >= 3 owners in a window -> `active`; 2 windows without a second owner -> stays, decays |
| `active` | >= 3 independent owners and (a link first seen, a direction change, or dV != 0) in the current window | 2 consecutive windows with no new link, no direction change and no open conflict -> `settled`; a conflict with >= 1 independent owner each side -> `contested` |
| `settled` | as above, or owner mark `settled` (display only, see 5) | a delta of class `update` / `new-link` with >= 2 independent owners reopens -> `active`; any `conflict` reopens -> `contested`; one owner alone does not reopen (it is recorded as `emerging` evidence on the card) |
| `contested` | an open contradiction pair with >= 1 independent owner on each side | the later side reaches cert >= 0.75 and the earlier side's support decays below 1 -> `active` (the pair stays on the card as history) |

All thresholds reuse `consolidate.py` constants (`MIN_PUBLISHERS = 3`, `MIN_WINDOWS = 2`, `WINDOW_DAYS = 7`). "Contested never fired on real data" (ledger L2962, L2963): the transition table does not fix that; round 3 in section 6 does (attribution slots so that "coalition says X" versus "Houthis say Y" becomes an opposes-with-claims pair, not a polarity contradiction).

### 1.6 The per-article triage verdict (design; the decider question)

For each article, after tier 1 (section 2) has mapped its entities to concepts and its sentences to existing fact slots:

| Verdict | Test | Decider mapping | Cost after verdict | Shown |
|---|---|---|---|---|
| `known` | every entity maps to a known concept; every sentence's nearest fact slot is within tau and from a *different* owner already counted, or the same story root | nothing proposed; journal only | 0 | never (counted in compression) |
| `update` | known concept, nearest slot matches, but owner is new or the direction read differs | STATED_FACT proposal; `validated` becomes true at >= 2 owners -> `ANSWER`, else `ANSWER_PROVISIONAL` | slow clock on the delta sentences only | if on a followed concept or 2+ owners |
| `new-link` | two known concepts, no existing edge between them | proposal on the link | claims + identity on delta sentences | yes |
| `new-concept` | an entity with no concept match and no Wikidata / WordNet hit | G5 candidate (section 9 `Accumulating`) | identity on the new entity | yes, as "candidate", never as a node |
| `conflict` | a contradiction edge against an existing slot | `contradicts` edge, concept -> `contested` | full slow clock on the article | always, ranked first |

`known` is the only verdict that skips work, so its error is the one that matters: a `known` article that would have produced an `update`, `new-link` or `conflict` under the full path is a **hidden change**. Section 4.1 measures that directly.

---

## 2. Throughput architecture: 1000s of articles in minutes on this box

### 2.1 Measured current costs (this session)

Fast chain (`live_trace.py`, from the 74 staged chain lines, c1 + mix; one process, THREADS=4):

| Gate | Stage | p50 ms | p90 ms | runs on | note |
|---|---|---|---|---|---|
| | **whole line** | **334** | **748** | 74/74 | mean 352; articles p50 2010 chars (~335 words, 13 sentences), p90 4784 chars |
| G3a | topic_landing | 150 | 223 | 41/74 | the one costly fast stage; abstains on 33 |
| G5 | structure_pack | 22 | 221 | 74 | heavy tail |
| G3a | windows (reader) | 45 | 57 | 74 | |
| G2 | facts | 24 | 64 | 74 | |
| G3a | place_student | 22 | 27 | 41 | |
| G1 | place_linker | 18 | 40 | 65 | |
| G3a | condition | 17 | 17 | 50 | |
| G2 | ner_fewnerd | 14.5 | 31 | 74 | |
| G4 | journal_durable + story keys | ~0 | ~0 | 74 | sha1 of title / first 300 chars |
| G2/G4 | claims_v1, identity_g4, contradictions | deferred to the slow clock | | | |

Slow clock (`slow_run.json`, sequential, one id at a time, model load 15-16 s):

| Part | c1 p50 / p90 ms | mix p50 / p90 ms | what it is |
|---|---|---|---|
| claims (claims_v1, lg parse) | 33 / 64 | 22 / 75 | cheap |
| build_rec | 122 / 234 | 97 / 252 | raw_core record |
| heads (function_p, factuality_p per sentence) | 421 / 955 | 327 / 1065 | the biggest part |
| identity_g4 | 340 / 768 | 434 / 778 | grows with the store (2.3) |
| contradictions | 0.3 / 0.5 | 0.5 / 0.8 | |
| **total per article** | **986 / 2029** | **881 / 2202** | 54 s for 34 ids; 59 s for 40 ids |

Consolidation (`slow_consolidate.py`, c1): 46 s per 34-article window; the fact join re-embeds every mention (measured below).

Micro-benchmarks (`/workspace/models/embed-zs/.venv/bin/python`, offline, CPU):

| Item | Measured | Notes |
|---|---|---|
| e5-small-v2 sentence embedding, 4 threads | 175-186 sentences/s (5.4-5.7 ms each) | 841 real fragment sentences, mean 162 chars; batch 16-64 best |
| same, 10 threads | 205-223 sentences/s | +20% for 2.5x threads: use processes, not threads |
| e5-small-v2 short texts (event words) | 1,414-1,590 texts/s | |
| model load | 0.3 s (warm cache) | the 15 s slow-clock load is spaCy lg + heads, not e5 |
| cosine top-5 match, 256 queries vs 10k concepts, torch f32, 4 threads | 6.9 ms matmul + 1.7 ms topk = **0.033 ms/query** | |
| same vs 100k concepts | 70 ms / 256 = **0.27 ms/query** | fits a 100k-concept index in memory (150 MB) |
| **numpy OpenBLAS in that venv, 4 threads** | **658 ms** for the same 10k matmul; 1 thread 20 ms | a venv mis-configuration: `scipy-openblas` with threads > 1 is ~30x slower than single-thread and ~100x slower than torch here. Anything in the pipeline doing `q @ idx.T` in numpy with OMP threads set is paying this today. Fix: `OPENBLAS_NUM_THREADS=1` or torch for the matmul. |
| fact_join: embed 3 texts per mention | 33.9 ms/mention (300 mentions, cold cache) | 10 s of the 46 s consolidation is re-embedding sentences the chain could have embedded once |
| fact_join `Scorer.prob` per pair (Python) | 145 pairs/s (6.9 ms/pair) | per-pair Python feature code |
| fact_join `cluster()` one anchor group | n=20: 40 ms (190 pairs); n=60: 40 ms (1770 pairs) | the vectorised path is fine: ~23 us/pair |

### 2.2 The cascade (design) with per-tier budget

Target: 2000 articles in < 5 min wall = 6.7 articles/s = **150 ms wall per article**. With 8 worker processes (10 physical cores, 2 kept for the services) that is **1.2 s CPU per article** end to end, including consolidation.

| Tier | Runs | What it decides | CPU per article (measured parts) | Share stopping here | Clock |
|---|---|---|---|---|---|
| **T0 normalise + journal** | always | sha of title and first 300 chars -> `copy` / `republished` (journal.py) | ~1 ms | **measured** c1 3/34 = 9% copies, mix 0/40 (curated fixtures); live-feed share unknown (trace-demo once showed 37 republished before the mirror rule) -> **estimate 10-25%** on a live window, measure in round 1 | fast |
| **T1 cheap read + concept match** | survivors of T0 | windows 45 + fewnerd 15 + place 18 + facts 24 + condition 17 + sentence embeddings 13 x 5.5 = 72 + concept match 13 x 0.3 = 4 + topic_landing 150 on 55% | **~280 ms** (measured parts; topic_landing is the one to make conditional on a non-known verdict) | **unknown today**; needed >= 40% for the 5-min bar with comfort (2.4). Hypothesis: in a focused window (one Area, many publishers) most articles after the first day are `known` or `update` | fast |
| **T2 extraction on delta sentences** | articles with verdict != known | claims_v1 33 + build_rec 120 + identity on *new* entities only (today 340-434 for all) + heads on *delta* sentences only (today 330-420 for all) + contradictions 0.5 | today ~1.0 s; **estimate 0.45 s** when heads and identity run only on the ~30% of sentences / entities that are deltas | all survivors | slow (per id, parallel) |
| **T3 consolidation per window** | once per window, batched | slot merge (fact_join cluster, embeddings **reused from T1**), independence, states, certainty, cards, delta list | today 46 s / 34 articles = 1.35 s per article; **estimate 0.1-0.2 s** per article once embeddings are cached and anchor groups are clustered with `cluster()` not `prob()` | | slow (batch) |

### 2.3 Projection (estimate built from the measured numbers)

| Scenario | CPU s per article | 8 workers, 2000 articles | Meets < 5 min? |
|---|---|---|---|
| Today, sequential, one process (fast 0.35 + slow 0.99 + consolidation 1.35) | 2.7 | 1 process: 90 min | no (and breaks the 60-min cap) |
| Today's code, 8 processes, nothing else | 2.7 | 11.2 min | no |
| + embeddings computed once (T3 drops to ~0.15) + numpy BLAS fix | 1.5 | 6.3 min | no, close |
| + heads and identity only on delta sentences / new entities (T2 0.45) | 0.95 | 4.0 min | yes, no `known` stop needed |
| + T0 stops 15%, T1 stops 40% of the rest (T2 on 51%) | 0.28 + 0.51 x 0.45 + 0.15 = 0.66 | 2.8 min | yes, with margin; cold first window ~4 min |

Expected share by tier at steady state (estimate): T0 15%, T1 35%, T2 50% of articles; shown to the owner: `conflict` + `update` on followed concepts + `new-link` + `new-concept` = **estimate 5-10% of articles**, i.e. a 10:1 to 20:1 compression (section 4.4 measures it).

### 2.4 What must change to hit 2000 in < 5 min

1. **Parallel workers.** `slow_clock.py` runs one id at a time; `live_trace.py` is one process with THREADS=4 (and threads buy little: 10 threads gave +20% on e5). A pool of 8 processes, each loading models once (15 s), partitioned by story root so one story's identity work lands in one worker. Memory: e5 ~130 MB + spaCy lg ~600 MB + heads per worker, ~1 GB x 8 = 8 GB of the 16 GB free: fits, no headroom for a 16-worker pool.
2. **Embed once, reuse everywhere.** T1 embeds every sentence (72 ms per article) and writes the vectors to the trace; `fact_join.Scorer.embed` and the `similar v0` step read them instead of re-encoding (saves ~10 s per 34-article window today, more at scale). The e5 vectors become the concept-match index too.
3. **Heads and identity on deltas only.** The two biggest slow-clock parts (heads 330-420 ms, identity 340-434 ms) run on every sentence and every entity; the triage verdict says which sentences and entities are new.
4. **Fix the identity scan.** `g4_align.py:957` loops over every stored vector in Python (`for (pa, paid, pv) in S.vec`) per article; `S.vec` is 757 entries after 34 articles (22 per article), so at 2000 articles it is ~44k entries scanned per new vector: seconds per article. Replace with one torch matmul against a (n, 384) matrix (measured 0.27 ms per query at 100k rows). This is the one change without which no amount of parallelism holds the budget.
5. **Fix the OpenBLAS threading in the venv** (`OPENBLAS_NUM_THREADS=1` or torch for matmuls): measured 30x.

### 2.5 What cannot be had, and why

- **The first window is the slowest.** When the graph is empty every article is `new-concept`; T1 stops nothing and T2 runs on everything: ~4 min for 2000 articles with changes 1-4, ~6 min without the delta restriction. "Minutes" holds only after the graph has a day of the Area in it.
- **No fewer than ~0.45 s CPU per delta article** with today's parts: the lg parse (33 ms) is cheap, but `build_rec` (120 ms) and the per-sentence heads are Python; moving them below 100 ms means the Rust path of playbook section 6, which is not built. Not needed for the 5-min bar, so not proposed now.
- **The 60-minute cap** stays: at 2.8-4 min per 2000 articles a window of 20-30k articles is the ceiling of one unattended run; larger backlogs are chunked.
- **Accuracy does not scale with throughput.** Fact join F1 0.506 (ECB+), agent grounding 89.5% / 74.4%, no measured link precision: at 2000 articles the same error rates produce 10x more wrong links. Section 4 puts bars on that before section 6 round 4 turns the speed on.
- **No GPU** (rule; and none is needed: e5 at 200 sentences/s on 4 threads is enough).

---

## 3. Mapping onto the playbook (extend, never recreate)

| Playbook element | Where the design sits | Change kind |
|---|---|---|
| G0 normalise | T0 | none |
| G1 scan, G2 entities/facts, G3a classify | T1 (existing fast stages) | add: sentence embeddings written to the trace line (one new stage behind an `LT_V4_EMBED` flag, like the other v4 stages), concept-match out block, `triage` verdict in `line.decider` as a seventh field beside change / size / story_type / topic / topic_node / traits |
| G3b deeper classify | T2 heads, restricted to delta sentences | the restriction is a filter on inputs; the heads are not retrained |
| journal (G4 dedupe) | T0 | none |
| G4 align: identity, evidence, contradictions | T2 identity on new entities; T3 independence and certainty | identity scan replaced by matmul (2.4.4); certainty math (1.4) is a new output next to `strength`, not a replacement |
| G5 ontology: candidates, promotion gates | `new-concept` verdict feeds section 9 `Accumulating`; states (1.5) are per concept, promotion stays as is | add the state field to `consolidated.json` concepts; nothing promotes without the existing gates |
| G6 educate | cards (1.1) and the delta view are `educate.py` templates over `consolidated.json` + `knowledge.json` + `resource_state.json` | extend `TEMPLATES`; still no free text |
| Two clocks (section 18.3) | fast = T0 + T1; slow = T2 per id + T3 per window | the slow clock gains a skip list (ids with verdict `known`) and a worker pool |
| Duplicates are counts (18.4) | T0 + `consolidate.independence` | none |
| Resources (18.6) | `affects_resource` = the resource edge + Conditions direction + ResourceState (V, dV, N, C, U) | the card reads them; no new resource mechanism |
| Novelty is a routing signal (18.7) | `new-concept` routes to the candidate queue, never creates a node | none; the AUROC 0.51 novelty proxy is replaced by the concept-match miss (an entity with no match and no Wikidata / WordNet hit), which is a lookup, not a model |
| Lean decider | the triage verdict is `decide()` per concept with marker from owner counts (`TOO_FEW_ITEMS` under 2 owners) and `validated` = >= 2 independent owners | `decider.py` and `lean/` untouched; a new caller |
| Macro Pulse (section 10) | card = what it is / what is changing / why / known / uncertain / adjacent, one to one | none |

Files that would be touched (none touched in this session): `live_trace_v4.py` (embed + triage stages), `slow_clock.py` (skip list, pool), `g4_align.py` (line 957 scan), `consolidate.py` (states, certainty, relation typing), `slow_consolidate.py` (cards, delta list), `educate.py` (templates), `fact_join.py` (read cached vectors), `simulation/raw-units.py` Knowledge step (delta view, marks), `KNOWLEDGE_SCHEMA.md`, `simulation/check-knowledge.py` (new K rows). No new page (rule: services.md, stop adding pages).

---

## 4. Measurement plan with outside truth (no human labels)

| # | What | How (outside truth or reference computation) | Pass bar (pre-registered, PROVISIONAL) |
|---|---|---|---|
| 4.1 | **Hidden change rate** (known must never hide a real change) | Replay a window twice: reference = full path on every article; test = cascade. For every article the cascade marked `known`, count the reference's outputs it would have produced: a slot reaching >= 2 owners for the first time, a new link, a contradiction. Hidden change rate = such articles / known articles. Run on c1, mix, and the first live 2000-article window. Seeded control: inject 20 known articles with one swapped number or negation; all 20 must leave `known`. | hidden change rate <= 5%; missed contradictions = 0; 20/20 seeded changes caught |
| 4.2 | **Concept-card fill rate** | Top 30 concepts by owners per Area: share of cards with `what_it_is` filled from Wikidata / WordNet / IPTC / resources.csv; with `direction != unknown`; with >= 1 driver; with >= 1 resource link. Today (measured): Wikidata cache holds Iran (Q794) and Houthi (Q3042087) but not Fiona, Cincinnati Zoo, Saudi Arabia, Yemen, Qatar: the cache was built from a different plan (top-20 names of the runs/g4 stores). | `what_it_is` >= 70% for entity concepts; direction >= 50% of `active` concepts; >= 1 driver on >= 30% |
| 4.3 | **Link precision** | `is_a` / `part_of` between two Wikidata-resolvable concepts: compare with Wikidata P31 / P279 / P361 from the cache (cache has 614 names; extend the frozen plan, network under `--fetch` only with the owner's yes). `opposes`: compare with the current-events anchors (two parties named in one "Armed conflicts" bullet on the same day) for the 2026-11-19 window. `causes`: **no outside truth available**; report consistency only (no A causes B and B causes A; no cause edge with a single owner shown as a driver) and MM3 local Clef agreement labelled as agreement, not accuracy. | is_a / part_of precision >= 0.8 on resolvable pairs; opposes precision >= 0.8 vs current events on conflict days; causes: consistency 100%, accuracy "unmeasured" on the card |
| 4.4 | **Compression ratio** | articles in window / delta items shown (conflict + update on followed + new-link + new-concept) and the share by verdict | >= 10:1 on a 2000-article window; `known` share reported, never hidden |
| 4.5 | **Time-to-delta** | wall time from `ready_at` to the delta item being in `knowledge.json`, at 2000 articles per 5 min offered load (replay from the queue with `TIME_IDS`) | p90 <= 5 min; model load excluded, written separately |
| 4.6 | **State and certainty sanity** | Concept state changes on the current-events days: an `active` or `contested` transition for a concept named in a current-events bullet that day (recall), and no `settled -> active` reopen without >= 2 owners (rule check). Certainty: cert of links that current events confirm vs links they do not mention (should separate; AUROC reported, no bar until a baseline exists) | reopen rule violations = 0; recall of named current-event concepts >= 0.6 on the 2026-11-19 window |
| 4.7 | **Throughput** | 2000-article replay, 8 workers, this box, services up | wall < 5 min after the first window; < 7 min cold; CPU per article by tier reported |

Every bar goes into `simulation/check-knowledge.py` as a K row with the existing ratchet (`status-prev.json`, exit 3 on any drop). A prediction line goes to the ledger before each run (rule).

---

## 5. Owner interaction: marks steer attention, never truth

Marks: `settled`, `follow`, `ignore`, per concept, stored in one JSON beside the area (`owner-marks.json`: concept id, mark, at, `last_seen_by_owner`). They are never read by `consolidate.py`, `g4_align.py` or the certainty math; `check-knowledge` asserts that `knowledge.json` sha256 is identical with and without the marks file.

| Mark | Processing effect (allowed) | Display effect | What it does NOT do |
|---|---|---|---|
| `follow` | a `known` verdict on a followed concept is downgraded to `update` when the owner is new, so the slow clock runs on it (more work, never less) | its deltas rank second, after conflicts | raise certainty |
| `settled` | none on truth; T2 still runs on deltas | `update` items with < 2 owners are folded into the card's "since you looked" count, not listed; `conflict` always listed | stop a conflict from showing; change state (state can be `settled` by evidence or marked by owner; the card shows which) |
| `ignore` | articles whose only deltas touch ignored concepts stop at T1 (budget), but are journaled and counted | hidden from the delta view; a `conflict` on an ignored concept is still listed once | delete anything |

"Since your last look": every delta item carries `first_seen`; the view ranks `conflict` > `update on followed` > `new-link` > `new-concept` > `update elsewhere` and filters `first_seen > last_seen_by_owner` per concept. Clicking a card updates `last_seen_by_owner` only.

Directional marks (the owner's "it could be directional"): a mark can carry `direction_expected: up | down`. It is not truth either: it only makes a delta whose measured direction disagrees rank as a `conflict` for display. The disagreement is logged as an attention event, not a contradiction edge.

---

## 6. Build order (rounds, bars, files, builders) and the static mock-up

Builders: Sonnet for code, Haiku for timing and replay runs, MM3 (local Clef) on each round's write-up. Opus / Fable only on owner ask (rule). Each round opens a ledger task, carries a prediction, and ends with its K row in `check-knowledge.py`.

| Round | Builds | Bar (measured before close) | Files |
|---|---|---|---|
| **R1 Measure first** | offline triage verdicts over the two staged traces (reference = full path, which exists); hidden-change check 4.1 with the 20 seeded articles; identity scaling test (slow clock on 34 vs 74 ids, p50 identity_ms); BLAS fix verified | 4.1 numbers exist for c1 and mix; identity p50 at 74 ids / p50 at 34 ids reported; numpy matmul <= 2x torch | new `simulation/check-triage.py`; `slow_consolidate.py` writes a `triage` block to `knowledge.json`; `KNOWLEDGE_SCHEMA.md`. (`projects/world-state/triage.py` is an older conditions-triage script; name the new one `triage_verdict.py`) |
| **R2 Cards v0** | concept cards from `consolidated.json` + `wikidata_cache` + resource state, as `educate.py` templates; Knowledge step shows the two cards below (words first, static) | fill rate 4.2 measured on top-30 per area; Wikidata plan extended to G4 canon names (fetch needs owner yes) | `educate.py`, `wikidata_cache.py --plan`, `simulation/raw-units.py` Knowledge step |
| **R3 Typed links, states, real contested** | predicate lemma -> relation type table (opposes / causes / precedes / affects_resource) in `consolidate.py`; state machine 1.5; certainty 1.4; attribution slots so "X says A" vs "Y says B" becomes an opposes pair with claims (the mix dispute, L2962) | 4.3 is_a / part_of >= 0.8; opposes >= 0.8 vs current events on 2026-11-19; contested >= 1 real pair on mix with a!=b and both sides attributed; reopen-rule violations 0 | `consolidate.py`, `g4_align.py` (relation `via` kinds), `slow_consolidate.py`, `check-knowledge.py` K9-K11 |
| **R4 Throughput** | embed stage + cached vectors; identity matmul (line 957); heads and identity on deltas; 8-worker slow clock with skip list; fact_join reads cached vectors | 4.7 wall < 5 min warm on a 2000-article replay; 4.1 holds (<= 5%, 0 missed conflicts) on that window; `knowledge.json` sha equal across worker counts (determinism) | `live_trace_v4.py`, `slow_clock.py`, `g4_align.py`, `fact_join.py`, `consolidate.py` |
| **R5 Delta view + marks** | "since your last look" list, ranking, marks file, directional marks | 4.4 >= 10:1; marks leave `knowledge.json` sha unchanged; 4.5 p90 <= 5 min | `simulation/raw-units.py`, `educate.py`, `owner-marks.json`, `check-raw-complete.py` |
| **R6 Calibrate (optional)** | certainty vs current-events anchors over the whole 2025-01 to 2026-11 anchor set (23 days) | 4.6 reported; constants moved only if AUROC improves on held-out days | `consolidate.py` constants, `check-knowledge.py` |

### 6.1 Static words mock-up: the delta view (filled from the real mix and c1 data, as of 2026-11-21)

```
SINCE YOUR LAST LOOK (2026-11-20 18:00)          74 articles read . 3 copies dropped . 8 items below      [compression 74 : 8]

[conflict]   none open                                                   (contested pairs: 0 in both areas; see 7.3)

[update]     Saudi Arabia <-opposes-> Houthis    strength 2 -> 2, new day 2026-11-21     Al Jazeera, Straits Times
             "iso:SA | fight | yemen iran aligned houthis" now on 3 days (18, 19, 20) + "destroyed three ballistic missile | fire toward | iso:SA" (21)
[update]     Coalition destroys drone             new slot, 2 owners, 2026-11-21                Al Jazeera, France 24
[new-link]   Iran --targets--> United States      2 owners, 2026-11-18 (first seen this window)   BBC World, Straits Times
[new-link]   United States --strikes--> Revolutionary Guard missile site   3 owners                BBC World, Boston Globe, Japan Times
[new-concept] "Public Investment Fund Tower" (Riyadh)  1 owner today; current events 2026-11-19 names it   -> candidate, not a node
[update]     Fiona (hippo)  state: active -> settled?  last new fact 2026-11-20 (died); 15 owners; no change on 21   -> 1 window quiet, needs 2
[gap]        "coalition" (concept) has 2 edges with 2 owners each and no what_it_is: Saudi-led coalition? not resolved
```

Each line is a template over edge ids (educate.py style); nothing above is free text except the bracket labels.

### 6.2 Concept card: Gulf conflict (mix area, 40 articles, 13 publishers)

| Slot | Content from the real data | Status today |
|---|---|---|
| id / label | no concept node exists for "Gulf conflict"; the data has iso:SA, iso:IR, iso:US, iso:YE, iso:QA, `concept:houthis`, `person:yemen iran aligned houthis` (a mistyped identity), `concept:coalition`. IPTC placement: medtop:16000000 conflict, war and peace (57 edges), medtop:20000056 armed conflict (53), medtop:20000055 terrorist bombings (162), medtop:20000078 disarmament (99) | **can't-yet**: the card needs a promoted `ours:` concept or a Wikidata anchor; current events 2026-11-19 names "Houthi-Saudi conflict" and "2026 Strait of Hormuz crisis" (CC BY-SA 4.0), so the anchor exists outside, not inside |
| what_it_is | Wikidata cache: Iran = Q794 "country in Western Asia", Houthi = Q3042087 "Yemeni Islamist organization"; Saudi Arabia, Yemen, Qatar not cached | **partly** (2 of 5 parties) |
| purpose / goal | attributed only: "houthis | threaten | port" (2 owners), "houthis | claim | previously claimed attacks on the east west pipeline" (2 owners); no stated goal slot | **partly**, as attributed claims; a free goal slot would be invention (7.1) |
| direction | decider change proposals: up 26, down 1, none 13 over the 40 articles, all `ABSTAIN_NOT_ADMITTED` (not validated); assertion volume by day 130 / 63 / 36 / 22 (18 -> 21 Nov) | **partly**: an escalation read exists but is not admitted; V falls across the window |
| drivers (causes) | "concept:attack | cause | concept:a fire on board" (2 owners) is the only `cause` predicate; "war | begin with | iso:US" (2 owners) | **can't-yet** as typed drivers; raw predicates only |
| opposes | iso:IR -> iso:US target (2), iso:US -> Revolutionary Guard site strike (3), iso:SA -> iso:YE strike (2), iso:YE -> iso:SA target (2), iso:SA fight houthis (2, 3 days), coalition intercept / destroy drones (2 each) | **can-fill-today** (the verb class table is the only missing piece) |
| affects_resource | resource edges (attention counts): IR primary_energy 8, supply_networks 8, state_capacity 8, public_finances 8; SA primary_energy 4, public_finances 4, supply_networks 4; ResourceState IR primary_energy 2026-11-18: V 7, N 1.0, U 0.71, C 0 | **partly**: attention and V exist; effect sign (draws / damages) and direction do not |
| related | cap:affect-price, cap:raise-rate bridge energy_power x inflation_prices (2 articles, flipped Area order, L2962); "Energy bills in Great Britain forecast to rise by 26%" is in the same area | **partly**, and the bridge rests on 2 articles |
| state | active (>= 3 owners, new links this window); contested 0 although L2962 found a real dispute | active (**partly**: contested machinery does not fire) |
| certainty (1.4) | US strike on Revolutionary Guard site: 3 owners, 1 day old -> cert 3x0.9 / (2.7 + 0 + 1) = 0.73; SA fight houthis: 2 owners over 3 days -> ~0.64 | **can-fill-today** once the formula is in `consolidate.py` |
| coverage | 40 articles, 13 publishers, 4 days, 1 window; 225 edges touch the parties, 201 of them single-publisher | **can-fill-today** |
| gaps | no what_it_is for SA / YE / QA; `person:yemen iran aligned houthis` should be `org`; `iso:IR | say on | None` (object None, 2 owners) | shown |

### 6.3 Concept card: Fiona (c1 area, 34 articles, 16 publishers)

| Slot | Content from the real data | Status today |
|---|---|---|
| id / label | `person:fiona` (type wrong: she is an animal; Few-NERD has no animal type mapped) ; IPTC: human mishap medtop:20000503 (271 edges), celebrity medtop:20000505 (159) | **partly** (type) |
| what_it_is | Wikidata cache: "Fiona" and "Fiona the hippo" not cached; in-graph: `person:fiona | be | concept:hippo` (3 owners: CBC, MassLive, NBC Boston) | **partly**: a 3-owner in-graph definition, no outside anchor |
| purpose / goal | not applicable to an animal; "became a celebrity" (4 owners) is a role, not a goal | **can't / should not** (7.1) |
| direction | decider: down 15, up 12, none 7, all not admitted; timeline undergo care (18, 19; 3 owners) -> die (20; 3 owners) -> necropsy (19-20; 3 owners) | **partly**: the `precedes` relation would state it; today the status rule only says "not a contradiction" |
| drivers | "hat | get into | fiona enclosure" (3), "hat | pas through | her system" (3), "ultrasound | show | some bunching of her intestine" (3), necropsy statement "hat ... caught in the middle of her small intestine causing her death" (3 owners) | **partly**: the cause sits in an object string, not a typed `causes` edge |
| opposes | none | n/a |
| affects_resource | community_ties US 11 / WORLD 9, population US 11 / WORLD 9: attention counts only | **partly**, and the mapping is doubtful (a zoo animal's death is not a population resource) |
| related | Harambe (2 owners, "be gorilla"), Cincinnati Zoo (facility and concept, not merged), zoo spokesperson Michelle Curley (4 owners) | **partly**: two Cincinnati Zoo ids |
| state | by rule: active on 20 Nov (3 new 3-owner slots), quiet on 21 -> settled after 2 quiet windows; 71 edges touch Fiona, 63 single-publisher | **can-fill-today** |
| certainty | die: 3 owners, 1 day -> 0.73; become celebrity: 4 owners over 3 days -> ~0.75 | **can-fill-today** |
| coverage | 34 articles, 16 publishers (3 wire copies collapsed; 121 fragment copies collapsed), 4 days | **can-fill-today** |

---

## 7. Risks, and where I disagree

### 7.1 With the owner: a free "goal / purpose" slot on every card is a trap
Goal is a property of agents (people, organisations, policies) and of instruments ("a pipeline is for moving oil"). A conflict, a hippo or a resource has no goal; filling the slot anyway means either invented text (forbidden: no made-up outputs) or a party's stated aim presented as the concept's. Proposal: the slot exists only for `kind in {entity: org/person, capability}` and holds *attributed* claims ("Houthis threaten port", 2 owners), with the attribution shown. For everything else the card shows `drivers` and `direction`, which is what the owner actually uses to decide whether to go down the path.

### 7.2 With the owner: "mark confidence of what we know" cannot become truth
The owner's "I could click areas to mark confidence of what we know / don't know so information doesn't keep getting rebuilt" is right about the rebuild problem and wrong if the mark feeds certainty (rule: no human labels as truth). Section 5 gives the owner budget and ranking control (follow / settled / ignore, directional expectation) and a sha-equality check that proves the marks never touch `knowledge.json`. A `settled` mark that hid a conflict would be the worst failure of this design; conflicts always show.

### 7.3 With the main session: "contested never fired" is a design gap, not a data gap
Two staged areas, 74 articles, 0 contested pairs, while a human read (L2962) found a real dispute on mix. The polarity / amount / status rules compare *our* normalised keys; news disputes are attributed ("Houthis say X", "coalition says Y"). Without attribution slots the contested state in 1.5 will keep reading 0, and the delta view's top rank stays empty. R3 puts attribution slots before throughput on purpose.

### 7.4 With the main session: the typed relation set should not add `uses / capable-of` or `depends-on`
Capability nodes already are the uses link, and `requires` already exists (playbook 9). Adding synonyms splits evidence across two edge types and makes every precision measurement smaller. Keep the playbook eight, add four (1.2).

### 7.5 With the main session: `novelty proxy AUROC 0.51` should not be carried into the cascade
A coin flip as a routing signal costs work and hides nothing good. `new-concept` here is a lookup miss (no concept match, no Wikidata / WordNet hit), which is deterministic and auditable. The novelty model stays "no outside truth" (L2791) and out of the path.

### 7.6 Risks in the throughput plan
- **The `known` share is a hypothesis.** If a live window stops < 20% at T1, the bar still holds (2.3 row 4: 4.0 min without any T1 stop) but only with the delta restriction and the identity fix. R1 measures the share before R4 spends on it.
- **Hidden changes.** The cheap test (entity match + sentence-to-slot cosine) can miss a changed number or a negation inside an otherwise known sentence (e5 cosines barely move on negation). Mitigation in 1.6: the `facts` stage (amount / date, 24 ms, already in T1) must agree with the matched slot's amount bucket, and any sentence with a negation spot (scan_dates `negation` count) never counts as known. 4.1's seeded control tests exactly this.
- **Identity scaling** (`g4_align.py:957`): unmeasured beyond 40 articles; the R1 34-vs-74 test is small and may not show it. The fix is cheap and should land regardless.
- **Memory.** 8 workers x ~1 GB on 16 GB free with Clef and the services up. If Clef is loaded, 6 workers; the bar moves to ~3.7 min warm (2.3 row 5 x 8/6).
- **Determinism across workers.** `knowledge.json` sha256 equality is a current gate; partitioning by story root keeps per-story order, but cross-story edge ids must not depend on arrival order (they are content hashes today: fine, verify in R4).
- **Accuracy multiplies.** Fact-join F1 0.506 and 3/6 wrong merges on mix (L2962) at 40 articles become hundreds of wrong links at 2000. The compression ratio will look good while the links are wrong; 4.3 must be met before 4.4 is celebrated.
- **Wikidata fetches need the owner's yes** (network) and the frozen plan was built from other stores; card fill rate 4.2 is capped at today's 614 cached names until then.

---

## Appendix: scripts and inputs used (all read-only on the project)

- `/tmp/claude-0/-workspace/3ed8559b-0aa2-49c4-a429-a0452a913be2/scratchpad/bench_embed.py` (e5 throughput, cosine lookup), `bench_join.py` (fact_join), `bench_blas2.py` (BLAS / torch).
- Traces: `/workspace/demo/mockups/structure-live/area-c1/trace/` and `area-mix/trace/` (chain.jsonl, slow_run.json, slow_consolidate/{knowledge,consolidated,resource_state}.json).
- Ledger lines L2950-L2973; L2791 (novelty AUROC 0.51); L2962 (Fable review: wrong-agent edges, real dispute).
- Playbook `/workspace/knowledge_pipeline/playbook/00-knowledge-pipeline-v1.md` sections 1, 2, 8, 9, 10, 13, 18.
- Web pages read 2026-11-22 (no files saved): github.com/commonsense/conceptnet5/wiki/Relations; wikidata.org/wiki/Property:P828; en.wikipedia.org/wiki/FrameNet; arxiv.org/abs/1804.04526 (EventKG). The official FrameNet frame-relations page did not render (app shell only).

---

## 8. MM3 verdict on this design (MM3-0736, loop, quick, 10 stories, 118 questions, request `mm3-concept-delta-loop.yaml`)

Gate **fail**; goal p 0.36 (unsure). No story passed. The loop verb reads no files, so every answer below is about the design as named in the request, not about the text of this document (own reading of the verb's rules).

| Signal | MM3 numbers | My reading |
|---|---|---|
| `done` fails on all 10 stories | q3 "measurable pass bar before code" 0.18-0.28; q4 "extends an existing stage" 0.25-0.67 (best: t2-delta-only 0.67, settled-mark 0.55) | The bars in sections 4 and 6 were invisible to the check. Not evidence they are wrong; evidence that each must land as a `check-knowledge.py` K row before any round closes. |
| Hidden-change risk on every story | q6 "could a known article hide a real change with no check catching it" 0.61-0.75; a clear miss (>= 0.70) on t2-delta-only 0.74, identity-matmul 0.72, hidden-change-rate 0.75, link-precision 0.74, settled-mark 0.74 | MM3 agrees with 7.6: the `known` verdict is the design's single point of failure. This is why R1 (measure 4.1 with seeded changes) comes before R4 (speed), and why `conflict` can never be hidden by any mark. |
| Parts are coupled | q2 "can be measured before the other parts finish": model 0.51, cascade 0.32, measurement 0.34, marks 0.29 (fail) | Agree: the rounds are sequential, not parallel; measurement needs the cascade's verdicts and marks need the view. |
| Owner mark / single publisher moving truth | q7 0.35-0.51 (unsure, never a clear miss) | The sha-equality check in section 5 is the test that settles this; it is cheap and belongs in R1, not R5. |
| Route | `none-fits` top on 7 of 10 stories (p 0.48-0.54), `build-now` on certainty-formula 0.46 and t1-concept-match 0.46 | Unsure everywhere; with no file evidence the check cannot say build-now. Not a redesign signal. |

What changes because of MM3-0736: (a) the `knowledge.json` sha-equality test for owner marks moves from R5 to R1; (b) every pass bar in section 4 is listed as a named K row in R1's deliverable so the next MM3 run (a `class` on `check-knowledge.py` once it exists) has file evidence; (c) the seeded-change control in 4.1 is extended from 20 to 50 articles covering negation, swapped amount, swapped date, swapped agent and reversed status (the five contradiction kinds). `next:` from MM3 is a drill on measurement/hidden-change-rate; not run (one MM3 call was the brief).
