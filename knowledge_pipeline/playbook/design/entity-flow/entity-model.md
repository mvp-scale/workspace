# Entity model

Every entity type that flows through the pipeline, as exported in `entity-flow.schema.json`. Real field names are kept; the few renames are in the mapping table at the end. Numbers: **c1** = Fiona the hippo (34 articles), **mix** = Gulf strikes + energy (40 articles). Coverage is from `sample-c1.json` / `sample-mix.json` `meta.coverage` (made by `export-bundle.py` against the bench on 2026-11-23); counts quoted in "quality" lines come from the same bundles, or from a named existing report. All values are PROVISIONAL.

Terms: **fact** = one subject-predicate-object statement with every sentence that supports it. **Owner** = the company behind a publisher (two publishers of one owner count once). **Slot** = a fact formed by merging two or more near-identical raw facts. **Independent** = counted once per owner, with syndicated copies collapsed.

## Overview

| Entity | Count c1 / mix | Id scheme | Made by (stage) | Updated by |
|---|---|---|---|---|
| Publisher (with Owner) | 16 / 13 | feed name string | s0 | s8 (owner count) |
| Article | 34 / 40 | sha256 hex of the item (64 chars) + `seq` (order in the window) | s0 | s1, s4, s7 add read depth, labels, story kind |
| Fragment (claim) | 666 / 692 exported (capped, 25 per article) | `<article id first 12>:<index>` (bundle-assigned) | s3 | s5 (resolver, identity) |
| Fact | 562 / 753 | sha1(key)[:12], 12 hex chars | s8 | s9 (flags), s10 (read) |
| Entity / Concept | 38 / 65 | `<type>:<canonical name>`, e.g. `person:fiona`, `iso:SA`, `resource:primary_energy` | s5 (identity), s10 (card) | s10 per article replay |
| Resource row (an entity kind) | 3 / 20 | `resource:<name>` from `probes/persona/rules_v2/resources.csv` | s4 (per-article resource events), s10 | s10 |
| Capability (an entity kind) | 55 / 23 | `cap:<verb-object>`, e.g. `cap:affect-price` | s9 (`consolidate.capability_layer`) | s9 |
| Link (typed) | 44 / 75 | none in source; identity is (a, b, rel) | s10 | s10 |
| Contest pair | 0 / 6 | none in source; bundle assigns `c<n>`; sides are fact ids | s6 (edges), s9 (`contested_pairs`) | none |
| Change (triage verdict) | 34 / 40 (one per article) | `seq` (+ article id) | s10 | none |
| Timeline item | 217 / 350 (26 more cut in mix, cap 60 per concept) | none in source; identity is (concept, edge_id) | s11 | none |
| Certainty word / state / depth | on every concept: 38 / 65 | enum values, not entities | s10 | s10 |

Relations (one line each): Publisher 1-n Article; Publisher n-1 Owner; Article 1-n Fragment; Fragment n-n Fact (via `fact.evidence`); Fact n-1 Entity (via `anchor`); Fact 1-n Fact (slot members); Contest = pair of Facts; Link = pair of Entities with Facts as evidence; Timeline item n-1 Entity and n-1 Fact; Change n-1 Article and n-n Entity (`touched`). See the ER diagram in `process-flow.md`.

---

## Publisher (and Owner)

Meaning: the feed a story came through, and the company behind it. Owner is the unit of independence.

| Field | Type | Meaning | Example (real) |
|---|---|---|---|
| id | string | feed name as the queue labels it | `Guardian World` |
| owner | string | company behind the feed (`publisher-owners.json`); an unlisted feed is its own owner | `Guardian Media Group` |
| owner_listed | boolean | false when the feed is not in `publisher-owners.json` | `true` |
| cite | string or null | public ownership source line | "The Guardian and guardian.com editions are published by Guardian News & Media Ltd..." |
| articles | integer | articles of this feed in the window | 4 |

Coverage: owner listed for 16 of 16 (c1), 13 of 13 (mix). 16 feeds map to 14 owners (c1), 13 to 11 (mix). Quality: ownership is a public-record mapping kept by hand; a new feed is treated as independent until listed. Created by s0, read by s8. Nothing in the data says a publisher's country, language or audience (MISSING; an HNW presentation layer would want reach and region).

## Article

Meaning: one news item in the window, with how it was read and how it was labelled.

| Field | Type | Meaning | Example |
|---|---|---|---|
| id | string | sha256 hex | `e1b2f7d9b916b119...` |
| seq | integer | position in the window (arrival order) | 0 |
| publisher, title, url, published | string | queue fields; `published` is UTC ISO | `Straits Times`, `2026-11-18T01:35:00Z` |
| read_depth, read_reason, words | enum, string, int | `full` or `teaser`; why teaser (`robots`, `paywall_or_blocked`, `short_extract`); words read | `teaser`, `paywall_or_blocked`, 35 |
| story_kind, story_root | enum, object | journal: `first`, `copy`, `republished`; root = first article of the story | `republished`, `{id, title, publisher}` |
| area_top, story_type_top, place_top | list of {name, p} | classifier top guesses with probability | `culture_leisure` 0.674; `fact` 0.974 |
| iptc_l1, iptc_node, iptc_node_label | string | IPTC media topic code and label | `medtop:08000000` human interest |
| condition_present | boolean | the Conditions head fired | `false` |
| decider | object | per field: `ANSWER_PROVISIONAL`, `ABSTAIN_LOW_CONFIDENCE`, `ABSTAIN_NOT_ADMITTED` | `{"change": "ABSTAIN_NOT_ADMITTED", ...}` |
| resource_events | list | resources the article talks about: resource, group, talk, signed | `community_ties`, social, 0.1, 0.0 |
| sentences, claims_n, claims_v1_n, ms_fast, ms_slow, gaps | numbers, list | counts and timing; `gaps` lists flags such as `TOPIC_DISAGREE`, `NOT_ATTACHED` | |

Coverage c1 / mix: read_depth, story_kind, iptc_node, area_top, story_type_top, place_top all 34 of 34 / 40 of 40 (100%). Created s0; updated s1 (read), s4 (labels), s7 (story). Quality:
- Teaser-only reads: 13 of 34 (c1), 17 of 40 (mix): facts from these rest on a feed teaser, not the article (reasons: robots 4, paywall 5, short extract 4 in c1).
- Decider outcomes over all articles and fields: c1 102 abstain-not-admitted, 69 provisional answers, 33 low-confidence abstains; mix 120 / 93 / 27. Most fields do not answer.
- IPTC topic is inherited from the article for most facts (87% of c1 edges, 56% of mix, ladder-review 1.6) and splits one story (Fiona: "human mishap" and "celebrity").
- `story_kind` is a duplicate detector: c1 first 23, republished 8, copy 3; mix first 39, republished 1.

## Fragment (claim)

Meaning: one subject-predicate-object read from one sentence, with where it sits in the text. This is the "sentence/fragment" tier between article and fact.

| Field | Type | Meaning | Example |
|---|---|---|---|
| id | string | `<article12>:<i>` | `ce427ddf25be:1` |
| article_id, sentence_index, sentence | | where it was read | 0, "Cincinnati Zoo trying to shake loose Fiona the hippo after she swallowed a hat." |
| type | enum | `triple`, `partial_claim` (a side missing), `attribution` (said-by) | `triple` |
| subject, predicate, object, missing | string | surface text; `missing` names the absent side of a partial | `Cincinnati Zoo`, `to shake`, `loose Fiona`, null |
| spans | object | role -> [start, end] character offsets in the article | `{"subject": [0,14], "verb": [25,30], "object": [31,42]}` |
| fate | string | what the merge rule did: `merged`, `folded`, `partial`, `dropped: pronoun`, `dropped: function_word` | `merged` |
| factuality, negated, modal | | sentence level: `asserted`, negation, modal | `asserted`, false, false |
| resolved_from | object or null | pronoun resolver v0: `{pronoun, to, ner, span, sentences_back}` | `{"pronoun":"she","to":"Sophie",...}` |

Coverage (after the cap) c1 / mix: subject 96.7% / 99.0%, predicate 100% / 100%, object 96.7% / 98.0%, spans 100%, factuality 100%. Created s3; updated s5. Quality:
- Exported fragments are capped at 25 per article (triples first); 2273 (c1) and 1912 (mix) were dropped (`meta.dropped`). The full list is in the bench record.
- Two claim lists exist per article and are not aligned: the v0 funnel (`claims`, has spans and sentence index, many duplicates and partials) and claims v1 (`slow.claims.items`, has negation, modality, passive, `said_by`, no sentence index or span). The bundle exports the v0 list. Attribution and modality of v1 are therefore NOT on the fragment (PARTIAL).
- Link from fact evidence to fragment: 31.8% (c1) and 39.8% (mix) of evidence rows resolve to an exported fragment; the rest are cut by the cap, or the fact sentence is a title plus body run-on that the match does not hit.
- Pronoun-subject claims dropped: 60 (c1), 20 (mix).

## Fact (edge, slot)

Meaning: a statement the pipeline believes the sources made, with the sentences that carry it and how many independent owners that is. Source name: `knowledge.edges` (edge, assertion).

| Field | Type | Meaning | Example |
|---|---|---|---|
| id | string | sha1(key)[:12] | `01f2172069bd` |
| subject, predicate, object | string | typed subject id, lemma, object id or text; object can be null | `concept:tissue fold`, `digest`, `concept:food` |
| kind | string | always `assertion` in these windows | |
| anchor | string | entity id the fact is formed under (slots merge inside one anchor) | `concept:hat` |
| strength = independent_owners | integer | distinct owners after collapsing syndicated copies | 3 |
| collapsed_copies | integer | copies folded away (same story root or near-identical sentence, Jaccard >= 0.70 on 8+ tokens) | 1 |
| independent_sources | list | per owner or publisher: articles, fragment count, copies, `how` (`single fragment`, `story root`, `near-identical sentence`) | |
| evidence | list | {article_id, publisher, sentence, day, fragment_id} | "Those multiple chambers, tissue folds, ..." (Boston Globe) |
| first_day, last_day, days | string | from the evidence articles' `published` | `2026-11-19` |
| slot | object or null | when raw keys merged: `n`, `merged_how`, `min_pair_prob`, `members[{edge, key, predicate, object, fragments_n}]` | `org:iea | say in | concept:its flagship annual world energy outlook` + 1 more |
| is_new, is_reinforced, in_contest | boolean | membership of the knowledge counters | |

Coverage c1 / mix: dated 562 of 562 / 753 of 753; with slot 36 (6.4%) / 52 (6.9%); two or more independent owners 38 (6.8%) / 40 (5.3%); in a contest 0 / 7 (0.9%). Created s8; flags s9. Quality:
- 93% of facts rest on one owner (524 of 562 in c1, 713 of 753 in mix). `is_new` is true for every fact (562 of 562, 753 of 753): within one window it carries no signal.
- 420 of 562 (c1) and 529 of 753 (mix) are anchored on a generic `concept:` id, not a named entity; common predicates are `be` (72 / 61), `say`, `have`.
- Object is null on 32 (c1) and 33 (mix) facts.
- Slot merge is PROVISIONAL (e5-small-v2 scorer, threshold 0.530; hard gates removed 188 candidate pairs in c1, 514 in mix; `meta.join`).
- Causes sit inside object strings (the one real cause in c1, edge `8d924accd79f`, is a `say` fact anchored on `concept:cincinnati zoo`; ladder-review 1.4).

## Entity / Concept

Meaning: a node of the graph with a card: who or what it is, what it did, what drives it, what it relates to. Source name: `concepts` (concept), with G4 identity merged in.

| Field | Type | Meaning | Example |
|---|---|---|---|
| id, label, kind | | `person` `org` `place` `entity` `concept` `resource` `process` (`capability` separate) | `person:fiona`, `Fiona`, `person` |
| depth | L1 / L2 / L3 | how deep the card goes | `L3` |
| state | enum | `active`, `emerging`, `gap`, `settled`, `contested` | `active` |
| certainty (number), certainty_word | | decayed independent-owner support / (support + contradictions + 1); word: `established`, `reported`, `single source`, `disputed` | 0.921, `established` |
| owners, facts, first_seq, last_seq, in_graph_from_seq | integers | support and first/last article | 13, 42, 0, 33, 0 |
| what_it_is | object or null | definition and source (Wikidata, WordNet, IPTC, resources.csv) | Iran: "country in Western Asia" |
| slot_fill | object | card slot -> `today`, `partly`, `cant` | `{"what_it_is":"cant","drivers":"today"}` |
| did | list | synthesised line: verb, objects, days, outlets, edge_ids, cited sentence | "undergo care, Nov 18-19", 5 outlets |
| drivers | list | clause after `after / because / due to`, with marker and certainty | "after swallowing a knit hat" (marker `after`) |
| resources, related, allies, opponents, disputed, gaps | lists | typed neighbours and honest gaps | |
| edge_ids | list | fact ids | 42 ids |
| g4 | object or null | G4 identity: type, canon, aliases, iptc_path, iptc_how, geo | `facility:cincinnati zoo`, aliases `Cincinnati Zoo's` |

Coverage c1 (38) / mix (65), concepts only: certainty word 100% / 100%; `did` 68.4% / 44.6%; `what_it_is` 26.3% / 44.6%; `related` 42.1% / 40.0%; `resources` 42.1% / 30.8%; `drivers` 39.5% / 20.0%; `opponents` 0% / 10.8%; `disputed` 0% / 7.7%; G4 identity 92.1% / 64.6%. Kinds: c1 person 21, place 5, concept 4, org 3, resource 3, entity 2; mix resource 20, place 19, person 15, org 6, entity 3, process 1, concept 1. States: c1 active 17, gap 13, emerging 8; mix settled 19, gap 16, emerging 14, active 11, contested 5. Created s5 (identity) then s10 (card); updated by the s10 per-article replay. Quality:
- **Type wrong**: ids come from the entity typer; Fiona (a hippo) and `person:hat` are typed `person`; Cincinnati Zoo exists as both place and org ids (ladder-review 1.3).
- **Synthesised `did` text broken** on some lines ("carry out Yemen", "fall enclosure"); the cited `sentence` on the same line is correct. Lines read by 2+ outlets: 7 of 49 (c1), 8 of 55 (mix).
- **Cause mis-anchored**: 34 of 38 drivers in c1 (15 of 22 in mix) are `after`/`following` (time order, not cause); 16 drivers have no target concept in both areas; the real cause in c1 sits on the Zoo card, not Fiona's.
- `direction` is empty in practice (c1 0 rows, mix 2; ladder-review 1.4). `what_it_is` missing on named places (Saudi Arabia, Yemen, Bahrain, Kuwait).
- `iptc_how` on the G4 identity: article-topic 23, sentence 9 (c1) - inherited from the article more often than read from the sentence.

### Resource row (entity kind `resource`)

Meaning: a world resource from `resources.csv` (energy, food, water, minerals, labour, money, community ties...), linked to the entities that affect it. Coverage: 3 of 38 (c1), 20 of 65 (mix). Per-article exposure is in `articles[].resource_events` (48 events in c1, 384 in mix: resource, group, talk, signed). Created s4, linked s10. Quality: the `affects_resource` link is co-occurrence only (the code's own note: "a typed effect is not read"); the `direction` of a resource is null throughout. Resource edge ids are not among the exported facts (see "Known gaps").

### Capability (entity kind `capability`)

Meaning: a recurring verb-object pattern (`cap:affect-price`) seen across areas; `bridging` when used by two or more areas. Fields: id, label, areas, bridging. c1 55 (bridging 10), mix 23 (bridging 2). Created s9. Quality: ids are lemma pairs ("appear com", "blow habitat") with no definition; `funnel.capabilities` says 55 but the window's own counts say 5 for c1 (`source.counts.capabilities`): two different counts of the same layer, not reconciled.

## Link (typed)

Meaning: a relation between two entities, with the facts that support it.

| Field | Meaning | Example |
|---|---|---|
| a, b | entity ids | `person:fiona`, `resource:community_ties` |
| rel | `affects_resource`, `related`, `opposes`, `is_a`, `part_of` | `affects_resource` |
| certainty, owners, n | support | 0.912, 13, 9 |
| edge_ids | fact ids | 9 ids |
| direction, note | direction when read; provenance note | "PROVISIONAL co-occurrence: ... a typed effect is not read" |

Counts c1 / mix: 44 / 75. By rel: c1 affects_resource 32, related 8, is_a 4; mix affects_resource 40, related 20, opposes 6, is_a 5, part_of 4. Two or more owners: 34 of 44 (77.3%) / 53 of 75 (70.7%). Single owner: 10 / 22. `causes` is not an emitted link rel in these windows (drivers stay on the card). Created and updated by s10. Quality: 73% (c1) and 53% (mix) are resource co-occurrence, not a stated relation.

## Contest pair

Meaning: two facts that disagree, both kept. Source name: `knowledge.contested`.

| Field | Meaning | Example |
|---|---|---|
| id | bundle-assigned `c<n>` | `c0` |
| a, b | fact ids | `4dc6b927eff5`, `53b05c73bd71` |
| kind | actual values here: `outcome` (5), `claim_vs_denial` (1); the schema doc also lists polarity, amount, status, direction | `claim_vs_denial` |
| label, note, status, reversal, targets | text, `PROVISIONAL`, true when a later report reverses an earlier one | "Kuwaiti authorities: report none vs Iran: say hit" |
| earlier, later | {edge, day} | day `2026-11-18` |
| sides | per side: edge_id, day, said, outcome, quote, speakers | quote "it hit US-linked military targets in Kuwait and Bahrain", speaker `iso:IR` |

Coverage: c1 0 pairs; mix 6 pairs, all dated 2026-11-18, one event (Iran strikes vs Kuwait and Bahrain reports) (ladder-review 1.3). Created s6 / s9, never updated. Quality: contested facts are 7 of 753 in mix (0.9%); `card.disputed` on concepts renders the first fragment sentence, not the side's quote, so use `sides[].quote` (ladder-review 1.4). The c1 story has a real status reversal (Fiona alive under care, then died) but `contested` is empty: the status-reversal rule found no pair (0 of 562).

## Change (triage verdict)

Meaning: what one article did to the graph, replayed in arrival order. Source name: `triage`.

| Field | Meaning | Example |
|---|---|---|
| seq, article_id, publisher | which article | 5, `ce427d...`, `Phys.org` |
| verdict | `new_concept`, `update`, `conflict`, `new_link`, `known` | `new_concept` |
| concept | the concept the verdict is about | `person:fiona` |
| counts, facts, unmapped, graph_before | verdict mix of this article's facts; concepts in graph before it | `{"update":3,"new_concept":2}`, 5, 2, 14 |
| change_kind, change_text, change_concept, change_edge_ids | the headline change and its sentence | "Cincinnati Zoo trying to shake loose Fiona the hippo after she swallowed a hat." |
| touched, concept_changes | all concepts touched, and per concept kind/text/publisher/edge ids | |

Coverage: one row per article (34 of 34, 40 of 40). Verdict counts c1: new_concept 29, update 4, conflict 1; mix: new_concept 31, update 5, conflict 3, new_link 1. Created s10, never updated. Quality: the verdict word and the `change_kind` can differ for one article (c1: change_kind update 29, new_concept 4, conflict 1); 29 of 34 c1 articles moved no depth rung (ladder-review section 2). "Since time T" is answerable by article `published` or `seq`, not by clock time of processing (no processing timestamp is exported).

## Timeline item

Meaning: one dated fact line of a concept from the deep pass. Source name: `deep.timeline`.

| Field | Meaning | Example |
|---|---|---|
| concept | entity id | `concept:flower` |
| seq, day | article order, UTC day | 15, `2026-11-19` |
| text | the fact's sentence | "Cincinnati Zoo's famed Fiona the hippo dies days after eating a visitor's hat." |
| edge_id | fact id | `45447b2e542e` |
| publishers | feeds | `["Straits Times"]` |

Coverage: 35 of 35 non-resource concepts (c1) and 45 of 45 (mix) have a timeline; 217 / 350 items exported (mix: 26 cut by the cap of 60 per concept). Created s11. Quality: the dated lines are real; the same deep response also carries `subconcepts`, `accounts`, `history`, `open_questions` which are NOT exported because they are noisy (ladder-review 1.4, 1.7): "Do accounts disagree?" answers yes for any speech fact; history matches across windows by surface name (United States in c1 pulls 40 Gulf lines).

## Certainty word, state, depth (enums on the concept)

| Enum | Values | Meaning |
|---|---|---|
| certainty_word | established, reported, single source, disputed | by owner count in the bundles: established 3 or more owners (3-14), reported 2, single source 1, disputed has contradictions (4-10 owners in mix) |
| state | active, emerging, gap, settled, contested | settled = 3 or more owners and nothing new on the last day of the window |
| depth | L1, L2, L3 | how much of the card could be filled; in these windows only L1 and L3 occur: c1 L3 35, L1 3; mix L3 45, L1 20 (the 20 L1 are the resource rows) |

Counts: c1 established 17, single source 14, reported 7; mix established 30, single source 18, reported 12, disputed 5.

---

## Field mapping (source name -> bundle name)

| Source (endpoint field) | Bundle |
|---|---|
| `knowledge.edges{id: {...}}` | `facts[]` (key becomes `id`) |
| edge `fragments[{art, pub, sent}]` | `fact.evidence[{article_id, publisher, sentence, day, fragment_id}]` |
| edge `independent.n` | `fact.independent_owners`; `independent.collapsed` -> `collapsed_copies`; `independent.sources[].pub` -> `owner_or_publisher` |
| `knowledge.contested[]` | `contests[]`; `sides{edgeid: {...}}` becomes `sides[{edge_id, ...}]`; `id` added |
| `concepts.concepts[]` | `entities[]`; `card.*` flattened onto the entity; `card.new` not exported (equals `changes`) |
| `knowledge.capabilities[]` | `entities[]` with `kind: "capability"` |
| `concepts.triage[]` (`art`, `pub`) | `changes[]` (`article_id`, `publisher`); `concept_changes{}` becomes a list |
| `deep.timeline[]` (`pubs`) | `timeline[]` (`publishers`, `concept` added) |
| sample `claims[]` (`value`, `sent_text`, `sentence`) | `fragments[]` (`object`, `sentence`, `sentence_index`) |
| sample `read`, `story`, `p`, `codes`, `decider`, `world.events` | flattened on `articles[]` |
| `/api/raw/areas` + `knowledge` counters, `funnel`, `yield`, `growth`, `join`, `answer` | `meta.*` |
| `publisher-owners.json` | `publishers[]` |

## Known gaps in the export (so a presentation layer does not assume them)

1. Resource-linked edge ids (8 unique ids in c1, 80 in mix) do not resolve to a fact: resource-state edges are not in `/api/raw/knowledge` edges (validated by `validate-samples.py`).
2. Fragments capped at 25 per article; fact evidence matches 32% / 40% to an exported fragment.
3. No processing timestamp on any entity; time is article `published` day (UTC) only.
4. No coordinates or country on places beyond `iso:` ids and the article's `place_top`.
5. Claims v1 attributes (negation, modality, speaker) are not attached to fragments; only the per-edge speaker list in contest sides exists.
6. No story/thread entity (story roots are duplicate clusters; ladder-review 1.6). Only one `process:` concept in mix, none in c1.
