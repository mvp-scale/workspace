# Terminology: the one vocabulary for the knowledge pipeline

Status: audit, 2026-11-23, read-only (`[F?]`, Fable 5.1; effort digit unknown, `~/.claude/settings.json` has no `effortLevel`). No code, page, gate, schema or service was changed; this file is the only output. Every anchor is `file:line` as read today.

Rule of precedence used: (1) playbook `00-knowledge-pipeline-v1.md` (00), (2) other playbook chapters and README/LESSONS, (3) names in code, API fields and the page, (4) outside standards 00 or `docs/research/2026-11-18 Reference sources` already cite (IPTC, Wikidata, CAMEO, SKOS, ICD 203, TAC update summarization, Endsley). A code or field name is never renamed here; prose is brought to the code's word or to 00's.

Owner complaint, restated as what the audit found: six documents written in 48 hours each re-named the same five things (the unit of knowledge, the grouping of articles, the change since a look, the disagreement, and how much we know), and three of them numbered their own levels and rounds from 1. Section 2 counts the names; section 3 restates the latest method with none of the new ones.

---

## 1. Canonical glossary

Columns: **canonical term** (use this word); **definition**; **defined first** (the anchor); **code / field** (the name in files and APIs, kept as is); **synonyms in use** with verdict: *alias* = allowed only in the stated scope, *replace* = write the canonical term instead, *retire* = stop using.

### 1.1 Stage and clock

| Canonical | Definition | Defined first | Code / field | Synonyms in use, verdict |
|---|---|---|---|---|
| **G0–G6** | The seven stage gates: normalise, scan, semantic solver, classify (a/b), align, evolve, educate. | 00:24-31, 00:48-57 | `live_trace.py` stages, `g4_align.py`, `evolve.py`, `educate.py` | `s0–s12` process-flow.md:88-102 — *alias* (sub-stages), each row must name its G gate (today only s5 does); `T0–T3` tiers concept-delta-design.md:175-180 — *replace* with "G0–G3 on the fast clock / G4–G5 on the slow clock"; "stations" navigator handoff:77 — *retire*. |
| **fast clock / slow clock** | Fast = per-article G0–G3 plus journal append (600 ms budget). Slow = G4–G5, run after the article and at window checkpoints. | 00:42, 00:550 (18.3) | `live_trace.py`, `slow_clock.py` (per article), `slow_consolidate.py` (per window) | "three clocks" entity-flow/README.md:3, process-flow.md:5-13 — *replace* with "two clocks; the slow clock has a per-article pass and a per-window pass"; "deep pass, on demand" process-flow.md:101 — *alias* (a read, not a clock). |
| **window** | The batch of articles one slow-clock consolidation covers; checkpoint unit. | 00:550 ("every 10k articles"); `consolidate.py:20` `WINDOW_DAYS` | `<trace>/slow_consolidate/`, `knowledge.json` `window` | "trace folder" — *alias* (where a window's files live). |
| **staged window** | One owner-staged query window on the bench (c1 Fiona, mix Gulf): a window chosen by hand. | `raw-units.py:258-268` (`area_dir`, `areas()`, `areas.json`); first called "area" in L2975 | bench key `area:c1`, bundle `meta.area` | "area / interest area / staged area" consolidation-method.md:17, ladder-review.md:97, brief-mockup.html:175 — **replace**: it collides with the ontology **Area** (00:30, 00:281). "window" is 00's and the code's word; "staged" is already the docs' word (ladder-review.md:97). The bench key stays `area:` (code). |
| **journal; story root; story kind** | Journal = the durable per-article record (G4 dedupe). Story root = the first article of a duplicate cluster (same title key or body prefix). Story kind = first / copy / republished / generic_title / no_key. | 00:28, 00:206, 00:537; `journal.py:2-3,8` | `journal.story_keys`, `classify`, `story_root`, `story_kind` | "story" alone, "stories" (`consolidate.py:124 Stories`) — *alias* only in "story root / story kind / story type"; never for a development (see 1.2). "thread = concept x story root" path-forward-plan.md:9, L2998 — **replace**: a story root is a syndication cluster (process-flow.md:95, ladder-review.md:95), so that formula yields one thread per article. |
| **story type** | Macro Pulse head value (fact, opinion, ...). | 00:109 ("content function"), 00:549 | `story_type_top`, `area_function` stage | "function / content function" 00:109, `function_p` — *alias* (head name). |

### 1.2 Units of knowledge (00 section 8 order, top down)

| Canonical | Definition | Defined first | Code / field | Synonyms in use, verdict |
|---|---|---|---|---|
| **article** | One news item in a window. Its immutable journal record is the **observation** (00:244). | 00:244; entity-model.md:42 | `articles[]`, `observations` (`slow_consolidate.py:5-6`) | "document" navigator schema (`document_cluster_count`) — *replace* with article count; "item" queue code — *alias* (queue only). |
| **development** | A group of articles about one dated event or sequence of events, with the assertions they carry. The thing "What is changing" lists. | 00:331 ("Dated developments and trends"); first built contract consolidation-method.md:34-47 | none yet (entity-model.md:240: "No story/thread entity"); bundle gap | "storyline" story-design.md:52,71; brief-mockup.html:176,362 — *replace*. "thread / story thread / story-thread scope" path-forward-plan.md:9, ladder-review.md:97,143,214, concept-delta-design.md:399, L2997 — *replace*. "event cluster / concept x event cluster" concept-delta-design.md:399 — *replace*. "process:" concept `concepts_v0.py:402` — *not the same*: a verb-pattern cluster of actors, keep its own name. "dispute" as a grouping consolidation-method.md:185 — *replace* with contradiction (1.3). "document cluster" navigator — *replace*. |
| **timeline** | The dated assertions of one node or development, grouped by day. | 00:331 ("trends"), 00:29 ("Temporal state"); `concepts_v0.py:943` `deep.timeline` | `timeline[]`, bundle Timeline item entity-model.md:190 | "phase (level 2)" consolidation-method.md:19,49-51 — **retire**: same clustering at a tighter cut; the owner-visible thing is the timeline by day. "steps / dated steps" ladder-review.md:127, brief-mockup.html:140 — *replace* with "timeline by day" (step also means rung in the mock-up and pipeline step on the page, index.html:145). |
| **assertion** | One subject–predicate–object statement the sources made, with its evidence and its independent-owner count; the merge target of G4. | 00:245; `KNOWLEDGE_SCHEMA.md:17-21` (`edges`) | `knowledge.edges`, `consolidate.py` kind `assertion`, bundle `facts[]` | "edge" — *alias* (graph/storage word; keep `edge_ids`). "fact" entity-model.md:87, bundle `facts[]` — *alias* as a field name only; prose says assertion. "slot" `KNOWLEDGE_SCHEMA.md:21`, entity-model.md:5 — *alias*, narrowly: an assertion formed by merging two or more raw keys (`fact_join`). "claim" consolidation-method.md:7,20,57; story-design.md throughout — **replace**: in code "claims" is the G2 record (`claims_v0`, `claims_v1`, `claims_funnel`), so one word covers two layers. "statement" `educate.py:4` — *alias* (an assertion rendered in an answer). "stated fact" `facts_lib`, process-flow.md:92 — *not the same*: a G2 amount/date/name extraction. |
| **fragment** | The G2 record read from one sentence: subject, predicate, object, spans, factuality, polarity. | 00:143-154 `SemanticFragment` | `claims_v0` units, `claims_v1.extract`, bundle `fragments[]` (entity-model.md:66) | "claim" (`claims_units.py:39-48`, entity-model.md:66 "Fragment (claim)") — *alias* only as the module/stage name (`claims v1`); prose says fragment. "unit" `claims_units.py` — *alias* (code). |
| **evidence** | The sentence, publisher, article and day behind an assertion; always kept. | 00:28 ("evidence pointers"), 00:323 `supported_by`, 00:351 | `edges[].fragments[{art,pub,sent}]` (`KNOWLEDGE_SCHEMA.md:18`), bundle `fact.evidence[]`, page view Evidence (index.html:720) | `fragments` as the edge field — *alias* (field name; it means evidence rows, not G2 fragments: the collision is in the schema, note it, do not rename today). "Go deep" index.html:624 — *alias* (the page action that opens evidence and the timeline). |
| **publisher; publisher owner** | Publisher = the feed an article came through. Publisher owner = the company behind it; the unit of independence. | 00:304 ("independent evidence diversity"), 00:551; `consolidate.py:8-9,249-257` | `publisher`, `publisher-owners.json`, `independent_owners`, `strength` | "outlet(s)" brief-mockup.html:188,206,259,342-351, ladder-review.md:66 — **replace** with "owners" or "publishers" (the mock-up's "13 outlets" is the owner count). "source" `consolidate.independence` "sources" — *alias* (one source per syndication group). "owner" alone — *ambiguous*: in these docs it also means the human owner ("owner marks", "owner decision"); write "publisher owner" when counting, "the owner" for the person. |
| **reinforced** | An assertion with 2 or more independent publisher owners. | `KNOWLEDGE_SCHEMA.md:13`; `consolidate.py:8-9` | `counters.reinforced`, `is_reinforced` | "corroborated" consolidation-method.md:7,26,71 — *replace*. "multi-publisher" ledger L2949 — *alias* (older). |

### 1.3 Nodes, concepts and disagreement

| Canonical | Definition | Defined first | Code / field | Synonyms in use, verdict |
|---|---|---|---|---|
| **node** | Any vertex of the typed graph: an entity or a concept. | 00:248 ("taxonomy node"), 00:281 ("typed directed graph") | bundle `entities[]` with `kind` enum (schema:106) | Umbrella word only. |
| **entity** | A named thing with an identity (person, org, place, facility, product), resolved at G2/G4. | 00:26, 00:134, 00:248 ("same name vs same entity") | `g4_align.Store.ent`, ids `person:`, `org:`, `iso:`, `facility:` | "concept" for `person:fiona`, `iso:IR` — `concepts_v0.py` (module, `/api/raw/concepts`, Concepts view index.html:720), concept-delta-design.md:11, ladder-review.md:5 — *alias* only as the route, module and view names; **prose says entity**. This is the root drift: 00 §8 reserves "concept" for the reusable ontology node and names Acme an entity. "cast" consolidation-method.md:7,22 — **retire**: it is "the entities of a development" (bundle `entities[]`). "anchor" `consolidate.py:270` — *alias* (the subject identity assertions are merged under). |
| **concept** | A reusable ontology node: Domain, Area, Subarea, Capability, Resource, or a promoted candidate (`ours:`). | 00:246, 00:281, 00:553 | `consolidate.candidates`, `capability_layer`, `resource:`, `cap:`, `ours:` | "ontology node" — *alias*. Bundle `kind` values `resource`, `capability`, `process` are concept kinds, not entity kinds (entity-model.md:138,142): say so, keep the enum. |
| **Domain / Area / Capability / Resource** | The seeded ontology, a typed graph not a tree. Area is an ontology node and a classifier head. | 00:281 (§9), 00:107-111 heads, 00:552-553 (18.5-18.6) | `domain_rollup`, `area_function`, `capability_list`, `resources.csv` | "topic" — *alias* only for the IPTC media topic (`topic_landing`, `iptc_node`, docs/research/2026-11-18:17), never for Area or for a staged window. "lane" navigator schema:13, consolidation-method.md:229-242,289 — **retire** (rejected by the method itself; drop the `lane` field). "domain" also = IPTC level 1 in `iptc_l1` — *alias*, say "IPTC level 1". |
| **relation** (typed link) | A typed, dated, evidenced link between two nodes. The eight of 00 plus four extensions. | 00:315-324 (`is_a part_of enables requires related_to same_as supported_by contradicts`); concept-delta-design.md:46-53 (`causes affects_resource opposes precedes`) | `links[].rel`, `g4_align.py:46 VIAS`, `concepts_v0.link_rel` | "link" — *alias* (bundle field). "related" (`concepts_v0`) = 00 `related_to` — *alias*, note it is co-occurrence until typed. `depends_on`, `uses`, `mentioned_with`, `affects`, `enables` navigator handoff:69 — `enables` and `requires` already exist; the rest *retire*. |
| **contradiction** | An edge between two assertions that cannot both hold (kinds polarity, amount, status, direction, outcome, claim_vs_denial); both kept. | 00:29, 00:55, 00:324 (`contradicts`, "Preserve both claims"); `g4_align.py:272-274,302,346-348` | `contradict_edges`, `knowledge.contested[]` (`KNOWLEDGE_SCHEMA.md:22`) | "contested" — *alias* with a fixed role: the counter (`counters.contested`) and the card state of a node with an open contradiction (1.4). "contest / contest pair" entity-model.md:160, schema `contests[]` — *replace* in prose with "contradiction (pair)"; the bundle field can be renamed in schema 0.2. "dispute / disputed" — *alias* with a fixed role: `disputed` is the certainty word on a line whose contradiction has named speakers on both sides (owner rule L2997, concept-delta-design.md:401); "dispute" as a noun *replace* with contradiction. "conflict" — *alias* with a fixed role: the triage verdict value (`concepts_v0.py:777`) and Pulse `C` (00:343). "wording differs" story-design.md:88 — *replace* with "contradiction, unattributed (not shown as disputed)". |

### 1.4 Attributes on a node, assertion or line

| Canonical | Definition | Defined first | Code / field | Synonyms in use, verdict |
|---|---|---|---|---|
| **certainty word** | One of four words from the independent-owner count: single source (1), reported (2), established (3+, certainty >= 0.6), disputed (named-speaker contradiction). | `concepts_v0.py:225-230` (`sureness`), index.html:598 | `certainty_word` (schema:108) | "sureness" — *alias* (function name). "epistemic state / epistemic word / confidence-in-sourcing word / evidence state" story-design.md:77-93,102 — *replace*. "status" navigator schema:34 (`observed reported supported hypothesis unassessed`) — *retire*. "STANDS" story-design.md:66 — *retire*. Kent / ICD 203 words (story-design.md:22-23) — *reference only*; the doc itself shows they are event probabilities, not source support. Extra words in story-design.md:83-91 map elsewhere: "not observed / not read" = a **gap** (`card.gaps`, 00:334); "stale" = **freshness** (00:343); "established absent" = certainty word on a negative-polarity assertion; "direction" = the Conditions direction (below). **Collision to record**: "reported" is also a factuality value (00:140 `Reported`, index.html:360). Always qualify: "certainty word reported (2 owners)" vs "factuality reported (attributed speech)". |
| **certainty** (number) | Decayed independent-owner support over support plus contradictions plus one. | concept-delta-design.md:78-82; `concepts_v0.py:445` | `certainty` | 00:337 asks for the pulse tuple, "not a single aggregated certainty number": present `(V, dV, N, C, U)` plus coverage and freshness as the contract (00:343-344) and `certainty` as a derived display value. |
| **Pulse tuple, coverage, freshness** | `(V, dV, N, C, U)` per Area and time; coverage and freshness reported apart. | 00:339-344 | `ledger_split.ResourceState` (resources only); missing for Areas (process-flow.md:102) | "uncertainty" (navigator string) — *replace* with gaps + coverage. |
| **factuality** | Asserted, Reported, Planned, Predicted, Denied, Unknown, per fragment. | 00:139-141 | `factuality`, `negated`, `modal` (schema:84) | "forward statement" consolidation-method.md:74, ladder-review.md:33 — *alias*: an assertion whose factuality is Predicted or Planned, with a speaker. "modal/future sentence" — *replace* with forward statement. |
| **direction** | Up / down / flat on an assertion or resource, from the Conditions head; needs an object and 2 owners. | 00:110 ("with direction"), 00:553 | `direction`, `directions`, card slot `effect` (`concepts_v0.py:327`) | "effect" — *alias* (slot name v1); prose says direction. "impact / impact_hypothesis" navigator schema:31 — **retire** (no model text). |
| **causes** | A stated, attributed cause between two nodes; `precedes` is time order; `after` is never a cause. | concept-delta-design.md:50,53 (checked against Wikidata P828/P1478/P1479, FrameNet Precedes); owner rule L2995 | `links[].rel = causes`; connective words `because` / `after` (`concepts_v0.py:24 CAUSE_MARK`) | "driver(s)" `concepts_v0.py:273` — *alias*: the card slot listing `causes` edges that point at this node; a driver with marker `after` is a `precedes`, not a driver. "WHY / Mechanism / SO / Consequence" story-design.md:64-65 — *retire*. "because / after / but" connectives — *keep*, mapped: because = causes (attributed), after = precedes, but = contradiction. |
| **card state** | gap / emerging / active / settled / contested: how live the evidence on a node is. | concept-delta-design.md:97-105; `concepts_v0.py:651-654` | `state` (schema:107), `CSTATE` index.html:562 | **Collision**: 00:289-298 has another "state" machine for ontology nodes (Unaligned, Accumulating, Candidate, Validated, Promoted, Archived), unbuilt (`consolidate.py:427` "promotion: none"). Write "card state" and "promotion state"; never bare "state". "emerging" is also a Novelty head value (00:112): qualify. "settled" as an owner mark concept-delta-design.md:252-257 — *replace* with "marked known" (the doc's own word at :389); "settled" as "no open forward statement" ladder-review.md:128,176, brief-mockup.html:150,286-291 — *replace* with that phrase. |
| **promotion state** | 00's lifecycle of a candidate concept. | 00:289-298 | `evolve.py` RESIDUAL / PROVISIONAL (slow_consolidate.py:9) | see card state. |
| **novelty** | Head output Known / emerging / unsupported; a routing signal, never ontology invention. | 00:112, 00:554 | `novelty` head (not attached), triage `new_concept` | `new_concept` verdict — *alias*: "novelty: unsupported, to the review queue". `is_new` (bundle) — *flag*: always true inside one window (entity-model.md:106); do not use. |
| **gap** | A card slot the data cannot fill, with the reason. | 00:334 ("Gaps, contradictions, stale coverage") | `card.gaps`, `slot_fill` `cant` | "not read / not observed / not established" story-design.md:84-85, brief-mockup.html:233 — *alias*: the rendered form of a gap; always "no X read in N articles", never "no X". |
| **triage change; verdict** | What one article did to the graph: a verdict per article (known / update / new_link / new_concept / conflict) and one change line per touched node. | concept-delta-design.md:111-119; `concepts_v0.py:706-707,777,842` | `triage[]`, `verdict`, `change_kind`, `change_text`, `concept_changes` (bundle `changes[]`) | "knowledge change" story-design.md:50-55,116 — *replace*. "delta / delta item / delta list / delta view" concept-delta-design.md title,260,276; consolidation-method.md:63-75; navigator `delta` — *replace* with "triage changes since K" (K = the last-look cut). "what article k added" index.html Build view — *alias* (page label). Spelling: the design writes `new-link` / `new-concept`; code is `new_link` / `new_concept` (schema:137): use the code spelling. |
| **since your last look** | The triage changes with `first_seen` after the viewer's last look; unchanged lines collapse. The TAC 2008 update-summary task. | index.html:633 (page label); story-design.md:39 (TAC) | page section; `last_seen_by_owner` (design) | "update summary" — *reference*. "delta" — *replace* (above). |
| **ranking** | Order of triage changes shown: conflict > update on a followed node > new_link > new_concept > other update. | concept-delta-design.md:260 | none | "priority material / watch / background" navigator schema:25, consolidation-method.md:77-83 — **retire** (the method's own proxies are counts; name them by what they count). "relevance direct / connected / context" consolidation-method.md:84-86 — *keep, optional*: a focus lens, nothing in 00 or code names it; justified as new. |
| **owner mark** | follow / ignore / marked-known, per node; steers ranking only, never certainty. | concept-delta-design.md:252-262, :385-395 | `owner-marks.json` (design) | "settled" mark — *replace* with marked-known. "level: concept / relation / system" :389 — *replace* with "scope". |

### 1.5 Depth and presentation

| Canonical | Definition | Defined first | Code / field | Synonyms in use, verdict |
|---|---|---|---|---|
| **knowledge depth** | How much is known about a node or development: 00's growth axis "more evidence, mechanisms, exceptions, time trends and understanding within existing concepts". | 00:285 | none (ladder-review.md:91: "depth does not exist anywhere yet") | "ladder" ladder-review.md title — *alias* (the test that measures depth). "level(s) 0-4" consolidation-method.md:15-23 — **retire**: those are containment (staged window > development > assertion > evidence), not depth; write them as nesting, unnumbered. "tier" — *replace* (see G0-G6). "layer" — *alias* only for 00 §8's three layers (observation, assertion, concept; `slow_consolidate.py:5`). |
| **rung: KNOW / FOLLOW / EXPECT** | The three measured values of knowledge depth, in 00 §10 reading order: KNOW = what it is + what is known; FOLLOW = what is changing + why it matters + what remains uncertain; EXPECT = the forward statements. | ladder-review.md:121-136, :226 (mapping to 00:328-335) | mock-up only (brief-mockup.html:128-152) | "step / highest step" brief-mockup.html:87,120,191 — *replace* with rung / highest rung reached. "frontier" ladder-review.md:5,54,131; beat NEXT "Frontier" story-design.md:67; render shape "gap -> frontier" L2995 — **retire** (three meanings): write "highest rung reached". Candidate rungs "L0-L4" ladder-review.md:26-33 — *replace* by their names (Named, Happened, Storyline, Explained, Expect): the L-numbers collide with the zoom levels below. "name only" brief-mockup.html:189 vs "named only" ladder-review.md:131 — one spelling: named only. |
| **zoom level L0–L3** | How much of a node is on screen: L0 street map, L1 card, L2 structure, L3 deep. A view setting, not knowledge depth. | `concepts_v0.py:2`; index.html:663 ("zoom level L0") | `depth` field (`concepts_v0.py:685,942`; schema:107; entity-model.md:210) | `depth` as this field — *alias* (field name); prose says zoom level, so "depth" is free for knowledge depth. |
| **answer** | 00 §10's six sections for one Area, Capability or node: what it is / what is changing / why it matters / what is known / what remains uncertain / adjacent. Templates over evidence, no free text. | 00:328-335; `educate.py:4,19,147` | `knowledge.answer`, `TEMPLATES` | "card" `concepts_v0.py:687`, page — *alias*: the answer rendered for one node (keep). "brief" story-design.md, path-forward-plan.md:11, brief-mockup-v1 — *alias*: the answer rendered for one staged window; its sections are §10's, not new ones. "LEAD / STORYLINE / WHERE IT STANDS / WHAT TO WATCH" story-design.md:70-73 — **retire**: lead = top-ranked triage change; storyline = timeline; where it stands = what is known + uncertain; watch = forward statements. "beats ANCHOR / CHANGE / WHY / SO / STANDS / NEXT" story-design.md:56-68 — **retire** (ladder-review.md:226 already folds them). "render table" (comparison / chain / before-after / timeline / card / frontier) L2995 — *alias* for line shapes, with "frontier" replaced by "gap". "summary / meaning" navigator — *retire* (summary = best-supported evidence sentence; meaning = model text, forbidden). |
| **views: Concepts, Build, Evidence; Street map; Go deep; What is this?** | The page's existing surfaces. | index.html:720, :663, :624, :769; L2977 | `data-view=concepts|build|evidence` | Keep as page names; "Concepts" shows entity cards (1.3). "Playback by knowledge change" story-design.md:116 — *replace* with "Build view by triage change". "entity pages / cast lens" consolidation-method.md:250 — *replace* with "entity card". |
| **rounds** | Work items are ledger tasks (T###) and round cards (16-the-working-loop.md:14). | playbook 16:7-14 | `kit/live/round_cards/` | "R1–R6" concept-delta-design.md:270-277, "S1–S4" story-design.md:295-298, "R1–R5" path-forward-plan.md:7-13 — **collision**: two different R1s in one week (ladder-review.md:143 and brief-mockup.html:176 cite "R1" meaning path-forward's). Name rounds by content and task id, never by a bare letter-number. |

---

## 2. Drift table

### 2.1 Per document: terms introduced or redefined

| Document | Term introduced / redefined (anchor) | Conflicts with | Replacement |
|---|---|---|---|
| concept-delta-design.md | "concept" = any card-bearing node incl. `iso:XX`, `wd:Q` (:11, :25) | 00:246-248 entity vs concept | entity (card); concept only for `resource: cap: ours:` |
| | "event = fast evidence / fact slot" (:11, :61-67) | 00:245 assertion; slot = merged only | assertion |
| | tiers T0–T3 (:175-180) | G0–G6 | G-stage + clock |
| | state gap/emerging/active/settled/contested (:14, :97-105) | 00:289-298 promotion state; 00:112 Novelty "emerging" | card state (qualified) |
| | owner mark `settled` (:252-257) | card state settled | marked-known |
| | "delta view / delta item" (:260, :276, :282) | triage change (code) | triage changes since K; "Since your last look" |
| | rounds R1–R6 (:270-277) | path-forward R1–R5 | task ids / names |
| | `new-link`, `new-concept` (:12, :115-116) | code `new_link`, `new_concept` | code spelling |
| | human-knowledge "level: concept/relation/system" (:389) | level = zoom, rung, containment | scope |
| | "story-thread scope", "concept x event cluster" (:399) | development | development |
| | certainty as one number (:78-82) | 00:337 "not a single aggregated certainty number" | pulse tuple + coverage + freshness as the contract; certainty derived |
| entity-flow/README.md, process-flow.md | "13 stages, 3 clocks" (README:3; process-flow:5-13) | 00:42, 00:550 two clocks; G0–G6 | two clocks (per-article and per-window slow passes); s-rows carry G labels |
| | "story/thread entity missing" (README:28; entity-model:240) | development (00:331) | development |
| entity-model.md, schema | "Fragment (claim)" (:66) | fragment vs claims module | fragment |
| | "Fact (edge, slot)" (:87), `facts[]` | assertion | assertion (field `facts[]` kept) |
| | "Entity / Concept" one section (:112); `kind` mixes entity and concept kinds (:138,142; schema:106) | 00 §8 | node; entity kinds vs concept kinds named |
| | "Contest pair", `contests[]` (:160; schema:7,123) | contradiction (00:324, g4_align) | contradiction pair; rename field in schema 0.2 |
| | "Change (triage verdict)", `changes[]` (:175) | — | triage change (ok; note the name) |
| | `depth` L1–L3 = card fill (:210) | knowledge depth (00:285) | zoom level |
| | `is_new` always true (:106) | novelty / triage | drop from prose |
| knowledge-consolidation-method.md | Claim = `facts[]` row (:7, :20, :57) | assertion; claims module | assertion |
| | Cast (:7, :22, :250) | entities | entities of the development |
| | Development (:18, :34-47) | — (00:331) | keep; say "built contract for 00's development" |
| | Phase, level 2 (:19, :49-51) | timeline by day | retire |
| | Levels 0–4 (:15-23) | zoom L0–L3; rungs | unnumbered nesting |
| | "0 Area = the staged query and window" (:17) | ontology Area | staged window |
| | development certainty word from member-article owners (:44) | code certainty word is per assertion | say "development certainty word (owners of member articles)" or take the best assertion's word |
| | corroborated (:7, :26, :71) | reinforced | reinforced |
| | "since-last-look delta" (:63-75) | triage change | triage changes since K |
| | priority proxies, lanes, `lane: null` (:77-83, :229-242, :289) | ranking; lanes rejected | ranking; drop `lane` |
| | "contest pairs -> disputes" (:185) | contradiction | contradiction pairs |
| | projection fields `meaning`, `impact_hypothesis`, `document_cluster_count` (:283-326) | no model text; articles | drop / articles |
| knowledge-story-design.md | "knowledge change" (:50-55, :116) | triage change | triage change |
| | beats ANCHOR/CHANGE/WHY/SO/STANDS/NEXT (:56-68) | 00 §10 sections | retire |
| | LEAD/STORYLINE/WHERE IT STANDS/WHAT TO WATCH (:70-73) | 00 §10 | retire (mapping in 1.5) |
| | epistemic words incl. not observed, wording differs, established absent, stale (:77-93) | certainty word (4 values), gap, freshness, factuality | certainty word + gap + freshness |
| | "evidence state" colour channel (:102) | certainty word | certainty word |
| | rounds S1–S4 (:295-298) | R-rounds | task ids |
| path-forward-plan.md | thread = concept x story root (:9) | journal story root = duplicate cluster | development (needs its own build rule) |
| | story threads, thread card (:9) | development | development, development card |
| | R1–R5 (:7-13) | concept-delta R1–R6 | task ids |
| | "Honest words" (:10) | certainty word | certainty words |
| | Brief LEAD/STORYLINE/STANDS/WATCH (:11) | 00 §10 | answer per staged window |
| ladder-review.md | concept = any node (:5) | entity | entity (node) |
| | fact / edge (:5) | assertion | assertion |
| | frontier (:5, :54, :131) | highest rung reached | highest rung reached |
| | candidate rungs L0–L4 (:26-33) | zoom L0–L3 | named rungs |
| | storyline (:30, :127) | timeline | timeline by day |
| | threads / story threads (:97, :143, :214) | development | development |
| | "settled" = no forward statement (:128, :176, :186) | card state | "no open forward statement" |
| | outlets (:66 and tables) | publisher owners | owners |
| | "deed lines" (:127, :216) | `did` slot | did (slot name) / assertions as subject |
| | "topic above the concept is the area" (:97, :133) | ontology Area, IPTC topic | staged window; IPTC node as hint |
| brief-mockup.html | "three steps / highest step" (:87, :120, :191) | rung | rung / highest rung reached |
| | "Concept ladder", "topic -> concept -> evidence" (:173-177) | entity; staged window | entity ladder; staged window -> entity -> evidence |
| | "storylines when R1 adds them" (:176, :362) | development; R1 collision | developments; task id |
| | "settled" (:150, :286-291) | card state | no open forward statement |
| | "outlets" (:188, :206, :259, :342-351) | owners | owners |
| | "name only" (:189) | "named only" (ladder-review) | named only |
| | "mixed stories, split pending" (:179, :198) | development | "hub: several developments" |
| brief-mockup-v1-backup.html | "Knowledge brief", lead -> storyline -> where it stands -> watch, "Five states of information", "Hub split into threads" | 00 §10; development | superseded by the ladder mock-up; archive, do not cite |
| navigator (external, data only) | development (:7, :46) | — | matches 00:331; keep |
| | lane (:38-41; schema:13) | — | retire |
| | priority material/watch/background (schema:25) | ranking | ranking |
| | relevance direct/connected/context (schema:26) | — | optional, new, non-conflicting |
| | delta.before/after (schema:29) | triage changes since K | triage changes since K |
| | summary, meaning, impact_hypothesis (schema:27,30,31) | no model text | best-supported evidence sentence; drop meaning/impact |
| | relations.status observed/reported/supported/hypothesis/unassessed (schema:34) | certainty word; factuality | certainty word; "unassessed" = gap |
| | uncertainty (string) (schema:32) | gaps + coverage | gaps + coverage |
| ledger L2952–L2998 | "concept layer", "cards", "threads" (L2997), "concept x story root" (L2998), "delta list" (L2977) | as above | notes stand as history; the correction is L2998's formula (story root is a duplicate cluster) |

### 2.2 How many names each core concept has today

Counted across 00, code, page, the six recent docs and the navigator example. "Distinct names" = different words used for the same referent, not role-fixed aliases.

| Core concept | Canonical | Distinct names today | The names |
|---|---|---|---|
| Unit of knowledge | assertion | 6 | assertion, edge, fact, slot, claim, statement |
| Sentence-level record | fragment | 3 | fragment, claim, unit |
| Evidence row | evidence | 3 | evidence, fragments (edge field), sentence/fragment_id |
| Named node | entity | 6 | entity, concept, node, card, cast, anchor |
| Article grouping | development | 9 | development, story, storyline, thread, story thread, event cluster, document cluster, process (concept), dispute (as grouping) |
| Change since a look | triage change / since your last look | 8 | triage verdict, change, concept_change, knowledge change, delta, update, what article k added, is_new |
| Disagreement | contradiction | 7 | contradiction, contested, contest, dispute, disputed, conflict, wording differs |
| How sure | certainty word | 8 | certainty word, sureness, epistemic word/state, confidence word, evidence state, status, STANDS, Kent/ICD words |
| Node lifecycle | card state / promotion state | 5 | state (two machines), status, mark, settled (three meanings) |
| How much is known | knowledge depth / rung | 9 | depth, level, rung, layer, step, tier, zoom level, frontier, L-numbers (two numberings) |
| Grouping axis | Area / staged window / topic | 7 | Area, area (staged), interest area, topic, lane, domain, IPTC node |
| Why | causes / precedes / direction | 10 | driver, cause, causes, because, after, WHY, mechanism, SO/consequence, effect, impact |
| Presentation | answer (card, brief) | 8 | answer, card, brief, section, beat, rung, view, render shape |
| Independence unit | publisher owner | 5 | publisher, feed, source, owner, outlet |
| Work item | ledger task / round card | 3 numberings | R1–R6, S1–S4, R1–R5 (R1 used twice) |

---

## 3. The one model in existing words

The latest method (knowledge-consolidation-method.md section 1: area > development > phase > claim > evidence, cast beside, ladder inside) restated with only the terms above:

**Nesting.** A **staged window** (bench `area:c1`, `area:mix`) holds **developments** (00 §10's "dated developments"): each is a group of articles about one event, with the **assertions** they carry (`knowledge.edges`; bundle `facts[]`), and under each assertion its **evidence** rows (`fragments[{art,pub,sent}]`; bundle `fact.evidence[]`) with publisher, publisher owner and day. Inside a development the assertions ordered by day are its **timeline** (`deep.timeline`); no further level is named. Repeats collapse by the rules that exist: syndication to one source (`consolidate.independence`), raw keys to one slot (`fact_join`), and an assertion's weight is its **reinforced** count of independent **publisher owners**.

**Beside.** The **entities** of the development (bundle `entities[]`: `iso:`, `person:`, `org:`, `facility:`) are shown as chips; each opens its **card**, which is 00 §10's **answer** for that node. **Concepts** proper (Area, Capability, Resource, promoted `ours:`) sit above as the ontology the development is routed to; a development is not a concept until 00 §9 promotion makes it one.

**Inside.** A development page is read at three **rungs** of **knowledge depth** (00:285), which are 00 §10's sections in reading order: KNOW (what it is, what is known: name, kind, the assertions with their **certainty word**), FOLLOW (what is changing, why it matters, what remains uncertain: the timeline by day, `causes` relations as attributed causes, `precedes` as order, open **contradictions** as `but` lines with the word **disputed** only when both sides have speakers, **gaps** as "no X read in N articles"), EXPECT (the forward statements: assertions with factuality Predicted or Planned and a speaker; "no open forward statement" when none). Every line carries its certainty word and opens its evidence. Adjacent nodes are the typed **relations**.

**Change.** What moved is the set of **triage changes** (`concepts_v0.triage`: verdict per article, change line per node) with `first_seen` after the viewer's cut K, shown under **Since your last look**, ranked conflict > update on a followed node > new_link > new_concept > other update; unchanged developments collapse to one line. Owner marks (follow / ignore / marked-known) move ranking only. Coverage (teaser share) and freshness are printed beside, per 00:343-344.

**New versus renamed.**

| Level in the method | Verdict | Why |
|---|---|---|
| Area (level 0) | renaming, wrong | It is the staged window; 00's Area is an ontology node and a head. |
| Development (level 1) | 00's word, genuinely new as a built unit | 00:331 names it and gives it no contract; code has none (entity-model.md:240). It is not the journal's story root (a duplicate cluster), not concepts_v0's `process:` (a verb-pattern actor cluster), not concept-delta's "event" (one assertion slot). The build rule (title + sentence + entity cosine, time decay, qualify rule) is new and in-sample. |
| Phase (level 2) | renaming | The timeline grouped by day at a tighter cut; the method itself calls it optional. |
| Claim (level 3) | renaming | 00's assertion (`knowledge.edges`), already named three ways. |
| Evidence (level 4) | existing | 00:28 and the edge's `fragments[]`. |
| Cast (beside) | renaming | The entities of the development; `entities[]` exists. |
| Ladder (inside) | new reading order, old axis | Knowledge depth is 00:285; the three rungs and their field tests are new; they are 00 §10's sections re-cut by how much a reader can retain. |
| Certainty word per development | redefinition | Same four words, computed from member-article owners instead of per assertion; must say which. |
| Since-last-look delta | existing | The triage changes after a cut; TAC update summary; page label exists. |
| Priority / lane / relevance | external | lane rejected; priority is the ranking; relevance is the one genuinely new, non-conflicting term and is optional. |

So of the seven levels in the method, two are genuinely new in substance (development as a built unit; the rung tests), one is an existing thing under a wrong name (Area), and four are renamings of things 00 or the code already named.

---

## 4. Edit instructions (not applied)

Format: file; old text -> new text. Line numbers as read today.

**playbook/design/knowledge-consolidation-method.md**
1. :7 "Claim = one pipeline fact ... the bundles call it `facts[]`" -> "Assertion (00 §8) = one subject-predicate-object statement with its evidence and owner count; `knowledge.edges`, bundle `facts[]`". Replace "claim(s)" with "assertion(s)" throughout (:20, :41-45, :57-61, :70-72, :110-121, :160, :174-188, :262-264).
2. :7, :22, :45, :250 "Cast" -> "entities (of the development)"; "cast chips" -> "entity chips".
3. :7 "Corroborated" and :26, :71, :81 "corroborated" -> "reinforced (2 or more independent publisher owners)".
4. :15-23 drop the level numbers 0-4; write the nesting "staged window > development > assertion > evidence; entities beside; rungs inside".
5. :17 "0 Area | the staged query and window" -> "staged window (bench key `area:`) | the owner-staged query and window"; every "area" meaning c1/mix (:4, :106, :126, :151, :167, :204, :227, :242, :248, :288) -> "staged window". Keep "Area" only where the ontology head is meant (:237 `area_top`).
6. :19, :49-51, :75, :117, :121, :220-225, :264 "phase" -> "timeline by day" (or delete the level).
7. :44 "Certainty word | pipeline words reused at development level: owners of member articles" -> add "(development certainty word; differs from the per-assertion word in `certainty_word`)".
8. :63-75 "Change since last look (a delta, not a level)" -> "Triage changes since K (not a level)"; "delta item" -> "change"; "since-last-look delta" (:27, :45, :249, :266) -> "changes since last look".
9. :77-88 "Priority and relevance" -> "Ranking and relevance"; :81-83 drop "stands in for material / watch / background"; keep the counting labels.
10. :185 "contest pairs -> disputes" -> "contradiction pairs -> contradictions"; :210 "Disagreement | `contests[]`" -> "Contradiction | `contested[]` (bundle `contests[]`)"; :25 "contest pairs" -> "contradiction pairs".
11. :229-242, :283, :289, :312 remove `lane` from the projection and the sentence "Prototype field names are reused where they fit (`lane`, `priority`, ...)" -> list only `id`, `title`, `relevance`, `evidence`.
12. :292 `"priority_proxy"` -> `"ranking"`; :300 `"meaning": null` and :301 `"impact_hypothesis": []` -> delete; :295 `"document_cluster_count"` -> `"articles"`.
13. :13 "the old unit (the entity card) moves beside it as a lens" -> "the entity card moves beside it"; :161, :353 "Entity-first (old street map)" keep, but "concept (entity card)" -> "entity card".

**playbook/design/concept-delta-design.md**
14. :11 "Knowledge = concept cards + typed, directed, dated links" -> "Knowledge = cards on nodes (entities and concepts) + typed, directed, dated relations"; :11 "A concept is a slow node (entity, resource, place, process type, capability)" -> "A node is an entity (person, org, place, facility) or a concept (resource, capability, process type, promoted candidate)"; :24 `concept_card` -> `node_card` (prose only; code field `card` unchanged).
15. :12, :111-117 `new-link`, `new-concept` -> `new_link`, `new_concept`.
16. :14, :97-105 "A concept has a state" -> "A node has a card state"; add one line: "distinct from the 00 §9 promotion state (Unaligned ... Archived)".
17. :175-180 tiers "T0 ... T3" -> "G0 + journal (fast) / G1-G3a (fast) / G2-G4 on changed sentences (slow, per article) / G4-G5 consolidation (slow, per window)"; update :190-192, :223 accordingly.
18. :252-257, :38 owner mark `settled` -> `marked-known`; :389 "level: concept | relation | system" -> "scope: concept | relation | system".
19. :260, :276, :282-294 "delta item / delta view / delta list" -> "triage change / Since your last look"; title "show only what moved" stays.
20. :270-277 "R1 ... R6" -> round names with their ledger task ids (R1 = T158-measure-triage, etc.); :272 keep "name the new one `triage_verdict.py`".
21. :399 "story-thread scope ... concept x event cluster ... card is per thread" -> "development scope ... card is per development (00:331)".
22. :91 keep; add after :82: "00:337 asks for the pulse tuple, not one certainty number: `certainty` is a display field derived from (V, C, U)".

**playbook/design/entity-flow/README.md, process-flow.md, entity-model.md, entity-flow.schema.json (prose and descriptions only)**
23. README:3 "13 stages, 3 clocks" -> "13 sub-stages of G0-G6, two clocks (the slow clock has a per-article and a per-window pass)"; process-flow:5 "(the code has three, the playbook names two)" -> "two clocks; the slow clock runs twice"; :13 likewise.
24. process-flow:88-102 add the G gate to each row's Stage name (s0 G0, s1-s2 G1, s3 G2, s4 G3a/b, s7 G4 journal, s5-s6 G4, s8-s9 G4, s10-s11 G5/G6, s12 G6).
25. README:28, entity-model:240, process-flow:95 "story/thread entity" / "not threads" -> "development (00:331)".
26. entity-model:66 "Fragment (claim)" -> "Fragment (G2 record; produced by the claims v0/v1 stage)"; :5 "fact = one subject-predicate-object statement" -> "assertion (bundle `facts[]`) = ..."; :87 "Fact (edge, slot)" -> "Assertion (bundle `facts[]`; `knowledge.edges`; a slot when merged)".
27. entity-model:112 "Entity / Concept" -> "Node: entity (person, org, place, facility) or concept (resource, capability, process)"; :138, :142 "an entity kind" -> "a concept kind"; schema:103 description likewise.
28. entity-model:160 "Contest pair" -> "Contradiction pair"; :19 likewise; schema:123-128 description "a pair of fact ids that disagree" -> "a contradiction edge between two assertions"; in schema 0.2 rename `contests` -> `contradictions` (not now).
29. entity-model:204-210 "depth | L1, L2, L3 | how much of the card could be filled" -> "zoom level (field `depth`) | L1, L2, L3 | how much of the card the deep pass filled; not knowledge depth".
30. entity-model:106, README:34 keep the `is_new` warning; add "do not use `is_new` for change".

**scratchpad/knowledge-story-design.md** (if kept as a record; else mark superseded by the ladder review at its head)
31. :1 add "Superseded in vocabulary by playbook/design/terminology.md: beats and LEAD/STORYLINE/STANDS/WATCH are 00 §10 sections; see ladder-review.md section 6".
32. :50-55, :116 "knowledge change" -> "triage change (`triage[].concept_changes` row)".
33. :77-93 "Epistemic state vocabulary" -> "Certainty words and gaps": keep the four certainty words; "not observed" -> "gap ('no X read in N articles')"; "wording differs" -> "contradiction, unattributed (not shown as disputed)"; "established absent" -> "reported, negative polarity"; "stale" -> "freshness"; "direction" -> "direction (Conditions head)".
34. :102 "Colour | evidence state only" -> "Colour | certainty word only".
35. :295-298 "S1 ... S4" -> names + task ids.

**scratchpad/path-forward-plan.md**
36. :9 "thread = concept x story root (journal keys exist)" -> "development = group of articles about one event (build rule in knowledge-consolidation-method.md 2.1); a story root is a duplicate cluster, not a thread"; "story threads", "thread card" -> "developments", "development card".
37. :7-13 "R1 ... R5" -> names + task ids (avoid the concept-delta R-numbers); :11 "Brief (story spine) ... LEAD, STORYLINE, STANDS, WATCH" -> "Answer per staged window (00 §10 sections; KNOW / FOLLOW / EXPECT order)".
38. :10 "Honest words" -> "Certainty words".

**scratchpad/ladder/ladder-review.md**
39. :5 "concept = a node of the graph (a typed entity ...)" -> "entity (node) = ..."; "fact / edge" -> "assertion (edge)"; "frontier = the highest rung a concept has reached" -> "highest rung reached".
40. :26-33, :54-61 "L0 Named ... L4 Expect" -> "Named, Happened, Storyline, Explained, Expect" (no L-numbers); :30 "Storyline" rung -> "Timeline".
41. :97, :133 "the only honest topic is the area the owner staged" -> "the only honest grouping is the staged window".
42. :97, :143, :214 "threads / story threads / concept x story thread" -> "developments"; :143 "moving to the thread (concept x story thread)" -> "moving to the development".
43. :128, :176, :186 "settled" -> "no open forward statement".
44. :66 and tables "outlets" -> "owners".
45. :127, :216 "deed lines" -> "`did` lines (assertions with the entity as subject)".

**demo/mockups/knowledge-raw/brief-mockup.html** (static mock-up text; the page rule "no new pages" is untouched)
46. :6 title "Knowledge Ladder Mockup" keep; :87 "climbs three steps" -> "three rungs"; :125 "The steps" -> "The rungs"; :189, :191 "How far each concept has climbed / Highest step" -> "Highest rung reached"; :175-177 "Concept ladder", "one row per concept" -> "Entity ladder", "one row per entity"; :173 "topic -> concept -> evidence" -> "staged window -> entity -> evidence".
47. :176, :362 "moves to storylines when R1 adds them" / "No storylines yet ... until R1 splits hubs into storylines" -> "moves to developments when they are built".
48. :150, :286-291 "settled" -> "no open forward statement".
49. :188, :206, :259, :304, :342-351 "outlets" -> "owners"; :189 "name only" -> "named only"; :179, :198 "mixed stories, split pending" -> "hub: several developments, split pending".
50. brief-mockup-v1-backup.html: leave in the scratchpad; do not cite it.

**ledger**
51. Add one note on T158 citing this file: "vocabulary fixed to terminology.md; L2998's 'thread = concept x story root' is withdrawn (a story root is a duplicate cluster); development per 00:331".

**Code and schema (owner decision, not in this audit's scope)**: the `concepts` module/route/view naming entities; `edges[].fragments` meaning evidence rows while `fragments[]` means G2 records in the bundle; the certainty word `reported` sharing a value with factuality `reported`; `depth` meaning zoom level; bundle `contests[]`. Each is a rename with a migration, so it is listed, not instructed.
