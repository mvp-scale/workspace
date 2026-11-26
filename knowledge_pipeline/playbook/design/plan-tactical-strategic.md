# Knowledge pipeline: tactical and strategic plan

Date 2026-11-24. Planning only (`[F]`, Fable 5.1; effort digit unknown, no `effortLevel` in settings). Read-only audit of code, data and ledger; nothing else was changed. Terms: `terminology.md`. Levels 0-11 and goals G1-G6 / S1-S4: `knowledge-breakdown-flow.md`. Every claim below names a file, a ledger line or a measurement taken today.

## 0. One-screen answer to the owner's question

"Is this pre-existing shaping that reuses across areas, or one example made to work?" Counted over the 53 components in section 1 (the factuality head is counted as shaping):

| Class | Count | Share | What it means |
|---|---|---|---|
| GENERAL (works for any source or area as is) | 24 | 45% | the algorithms and contracts: dedupe, fragments, dependency-rule assertions, NER and typing, syndication collapse, the ECB+-trained fact join, polarity/amount/date contradictions, clustering, grounding gate, goal templates, encoding rules, ledger ratchet |
| SHAPING (general idea, but parameters or data tuned on c1 + mix, or a data file that is news-only) | 16 | 30% | development thresholds (in-sample on 2 windows), identity guards, publisher-owner map, decay constant, IPTC seed, since-last-look cut, forward-statement regex, hindsight test at n=9 |
| ONE-EXAMPLE (built for news, c1 or mix only) | 13 | 25% | the news-queue reader as the only intake; war and health word lists inside code; the "Fiona" gate; per-area counter bars; requirement ids hardcoded in the generator and the question writer; the mock-up pages; the Macro Pulse heads (news taxonomy, below bar) |

Plain words: about half of what exists is reusable as it stands, and the shape (one file contract per level, each level a pure function on the one before, gates with pre-stated bars and an at-or-better ratchet) is the right shape for "any knowledge". The other half is not yet proven general: every quality number so far was measured on the same two staged windows the code was tuned on, and the only intake is the news queue. Nothing has been run on a second source type or an unseen area with frozen parameters. The one-example work is small in lines but sits in the places that would silently break on a new area: word lists in `claims_v1.py`, `g4_align.py`, `concepts_v0.py`; a gate that asserts a hippo; counter bars per area in `check-knowledge.py`. The recent work by the main session (developments v0, speakers, presentation process) is general in method and one-example in its tests and patches (`FWD_NOT` added for mix; D5 asserts Fiona).

Is it over-engineered? The 00 playbook plans Rust, Lean proofs, DenStream, a 100k-concept index and a human-knowledge model; none of that is needed to prove generality. The anti-list is in section 2.3.

## 1. Audit per level

Class: **G** general, **S** shaping, **1** one-example. Evidence is the file:function and what was read.

| # | Level | Component (file:function) | Class | Evidence |
|---|---|---|---|---|
| 0 | Intake | `live_trace.py:select_sql` + `ALLOW` (news queue sqlite, columns id/url/source/title/teaser/body/published) | **1** | the only reader; `QUEUE` path fixed; `READ_SQL` depth/reason from the queue; no adapter interface. Queue today: 50,575 items, 63 sources, 26,259 full / 24,316 teaser (read-only count) |
| 0 | Intake | `journal.py:story_keys, classify` (title sha, first-300-chars sha; first/copy/republished) | G | pure functions, no vocabulary |
| 0 | Intake | `build-knowledge-fixture.py` staged windows | **1** | `AREAS = [("c1", ...), ("mix", ...)]` hardcoded; ids from a scout file in a scratchpad; `raw-units.py:253 AREA_SHORT` names c1/mix |
| 1 | Fragments | `scan_gate.scan` (numbers, dates, units) | G | regex over `size_quantity.UNITS` |
| 1 | Fragments | `facts_lib` stated facts (amount, date, name, triple, validated against the text) | G | pre-registered validator L958; CaRB used as truth (0.565, L2989) |
| 1 | Fragments | `raw_core.units_for, sentence_table` | G | sentence spans and units; no vocabulary |
| 1 | Fragments | `analyze2.Reader.read_detail` windows + `expert1_v6b_student.pkl` | **1** | a news topic+story head decides which windows are read; MN-DS trained; below its bars (GO.md key numbers) |
| 2 | Assertions | `claims_v1.extract` (spaCy lg dependency rules: subject, verb, object, passive, copula, xcomp, measure, antecedent) | G | grammar rules only; who-did-it 0.9189 after the regression (L2992), 94%/93% earlier |
| 2 | Assertions | `claims_v1.py:148-155 HIT_V ATTACK_V BLOCK_V DENY_V DMG_N INCOMING_N` attribution slots (hit / attack / blocked / none) | **1** | war-reporting lexicon written for the Iran-Kuwait dispute (L2985, L2988); mix 6 pairs, c1 0 |
| 2 | Assertions | `raw_core.claims_v0` pronoun resolver (`_PRON`, nearest ORG) | S | general rule; fixed once for mix (L2967); appositives and cross-sentence pronouns still open (L2970) |
| 2 | Assertions | `claims_units.claims_v1` passes `topic`, `place` from news heads into every fragment | S | the fields ride along; a source without a topic head needs null handling, not new code |
| 3 | Entities | `raw_core.lg_ents` (spaCy NER) + `fewnerd_typing` (66 Few-NERD types) | G | public models, outside truth exists (Few-NERD) |
| 3 | Entities | `g4_align.Store` identity, `ident-v2` guards (surname, head noun, acronym; never two ISO codes) | S | general rules; measured only on c1/mix (mix 3 of 6 merges wrong, L2970; K4 wrong-merge controls 0); `TITLES` English honorifics |
| 3 | Entities | `g4_align.py:240-243 STATUS_VERB CARE_VERB CARE_OBJ DEAD_OBJ ALIVE_OBJ` | **1** | die / undergo care / alive: the Fiona story's status axis |
| 3 | Entities | `structure_pack.link_place` (GeoNames + WordNet) and the Wikidata cache (614 names) | S | general sources; cache built from a different name list (concept-delta-design 4.2: Fiona, Cincinnati Zoo, Saudi Arabia missing) |
| 4 | Corroboration | `consolidate.syndication_groups, independence, owner_of` (near-identical sentence Jaccard >= 0.7, one source per story root) | G | mechanism general |
| 4 | Corroboration | `consolidate.py:publisher-owners.json` | S | news owner map; a new source type needs its own owner facts (or each item is its own owner) |
| 4 | Corroboration | `fact_join.Scorer` (ECB+ trained GBM, e5-small-v2 features, thr 0.53) | G | outside truth ECB+ F1 0.5133 vs bar 0.49 (L2956, K8 e); baselines 0.351 / 0.440 |
| 4 | Corroboration | `consolidate.slot_merge` + `_gate` (status, direction, amount/date bucket, place, disjoint object) | S | gates general; status gate depends on the `STATUS_VERB` lexicon above |
| 4 | Corroboration | `g4_align.contradict_edges` kinds polarity / amount / date / direction (`UP`, `DOWN` verb sets) | G | general kinds; `UP`/`DOWN` are general English finance verbs |
| 4 | Corroboration | `g4_align.report_contradictions` kinds outcome / claim_vs_denial (`REPORT_PAIRS`) | **1** | rests on the war slot classes; proven on one mix dispute |
| 4 | Corroboration | `concepts_v0.py:708 NUM_RE` units (dead, killed, troops, missiles, drones, barrels, ships), `723-728 STATUS_GROUPS/STATUS_OBJ` | **1** | war and casualty vocabulary in a regex |
| 4 | Corroboration | `check-reinforced-precision.py` heuristic (subjects differ, self-loop, no shared token) | S | automatic, no outside truth; the builder wrote the flag rule (L2973 caveat) |
| 5 | Developments | `developments_v0._agglo, _group` (average-link clustering on headline + evidence + entity cosines, time decay) | G | algorithm general, deterministic, no model |
| 5 | Developments | `developments_v0.PARAMS` thr 0.04, tau 96 h, wc 0.5, hub 0.4 | S | 30-setting sweep scored against the builder's own reading on c1 and mix; "the choice is in-sample" (consolidation-method 3.2); purity 0.912 / 0.850 |
| 5 | Developments | qualify rule (2+ articles, 1+ full read), thin state | G | |
| 5 | Developments | `developments_v0.FWD, FWD_NOT, SAYER, ROLE, APPOS, CAUSE` regexes | S | general English; `FWD_NOT` ("without warning", "warning systems") is a patch for mix (L3001) |
| 5 | Developments | `check-developments.py` D5 "c1 has the Fiona death headline", `AREAS` default c1,mix | **1** | gate asserts a story |
| 5 | Developments | `concepts_v0.py:20 OPPOSE, :26 KIN` (strike, bomb, intercept, retaliate...) | **1** | war verbs decide the `opposes` relation and process concepts |
| 5 | Developments | `concepts_v0.py:16-19 SPEECH CAUSE PART ISA`, WordNet generic stoplist, `link_rel` | G | general English relation cues; WordNet polysemy rule |
| 5 | Developments | `concepts_v0.triage` verdicts (known / update / new_link / new_concept / conflict) + seeded control | G | rules general; compression 1.0:1 on the 464-article stream (bar 10:1 FAIL, L2987): coverage, not design |
| 6 | Change over time | `developments_v0` since-your-last-look (cut seq, new / corroborated / reinforced / word changed) | G | mechanism general; the cut is a seq, no stored viewer state |
| 6 | Change over time | development id = sha1 of member ids | **1** | defect, not a design: one more article changes the id (`notes.id_stable_across_windows` MISSING; L3000) |
| 6 | Change over time | `concepts_v0._windows, _hist_edges` history across windows; `slow_consolidate.decay` half-life 7 days | S | works only where sibling windows exist; constant untested |
| 6 | Change over time | `journal.py` durable record, `evolve.py` residual clusters (head-word baseline) | G | |
| 7 | Meaning | `educate.py TEMPLATES` answer (what it is / changing / why / known / uncertain / adjacent) | G | template over edges, no free text; "why it matters" is a list of relations, not meaning |
| 7 | Meaning | stated-cause sentences (`CAUSE` regex, unattributed) | S | 7 of 13 rated below 0.5 as a cause by Clef pre-screen (presentation-process 8.1); no accuracy |
| 8 | Projection | forward statements = `FWD` wording match + `sayer` speaker (claims v1 `attrs.speaker` else sentence) | S | mix 8 of 17, c1 3 of 12 named (L3001); factuality values Planned / Predicted exist (00:139) but are not on fragments |
| 8 | Projection | `factuality_story` head (MAVEN) | **1**-leaning S | AUC 0.67-0.76 vs bar 0.80 (GO.md); not attached to assertions |
| 9 | Relevance, rank | `developments_v0.MOVED_ORDER` (moved > single-source new > nothing) | G | an honest proxy, "not importance"; hindsight: moved-first 40% vs 27% persisted (L3002) |
| 9 | Relevance, rank | `gen.py:rank_key` bands (disputed+moved, moved, disputed, forward, unchanged) + `priorities.json` follow list | G | rule general; never tested against truth |
| 9 | Relevance, rank | Macro Pulse heads `area_function, domain_rollup, topic_landing, condition, place_student` | **1** | IPTC news taxonomy, MN-DS trained, below bars (top-1 0.571 vs 0.60; GO.md); not used by developments |
| 9 | Relevance, rank | hindsight test (`_remove/consume-mockups`, persisted after freeze AND persona list) | S | n = 9 mattered of 62, 1.3-day window, relevance list shared with ranking (L3002 caveats) |
| 10 | Reader state | default cut = last 25% of the window (`DEFAULT_CUT_SHARE`), `cut.options` | G | a stub: no stored last look per reader, no recall store |
| 10 | Reader state | owner marks (follow / ignore / marked-known) | design only | concept-delta-design 5; not built |
| 11 | Render | `goal-templates.json` (5 goals, 18 requirement rows, each a field path) | G | `_about`: "Domain-agnostic: every row is answered from a field the pipeline produces for ANY staged window" |
| 11 | Render | `type-encoding-rules.json` E1-E12 (type -> mark -> minimal text) | G | |
| 11 | Render | `gen.py:requirements` (lines 102-144) and `questions.py` (lines 35-88) | **1** | 18 requirement ids hardcoded as `if "MON-1" in page_rows` branches; adding a goal row to the JSON changes nothing until code is written. The per-requirement code is the "generator hardcoded" item |
| 11 | Render | `check-grounding.py` (every text node = verbatim data, label or field number) | G | 9/9 pages, 0 ungrounded (L3005) |
| 11 | Render | `index.html` Concepts / Build / Evidence / Developments views, area picker | S | bound to `AREA_SHORT` c1/mix; `textContent` rule held |
| 11 | Render | `_remove/consume-mockups` D1-D4 | **1** | static `window.DATA` of 6 fixed developments; a comparison, not a renderer |
| x | Gates | `check-knowledge.py` K1-K8 | S | structure general; K2 counter bars per area (`c1: reinforced > 0; mix: bridging > 0`, line 88) are one-example |
| x | Gates | `check-alignment.py` ratchet (at-or-better on built / runs / quality / value; `--accept`) | G | the right mechanism; rows read numbers from ledger lines by regex |
| x | Record | ledger PREDICTION then SCORE per round | G | held throughout T158 |

Totals: G 24, S 16 (incl. the factuality head), 1 13 (53; the one "design only" row is not counted).

## 2. Strategic plan: the shape of a pipeline that works for any knowledge

### 2.1 The minimal general architecture (what to keep, in one line each)

| Level | Contract (one file, one pure function) | Keep from today | Change |
|---|---|---|---|
| 0 | `items(source) -> source item {id, title, text, time or null, source, owner or null, read_depth, url}` | `journal.story_keys` dedupe | **new: adapter interface**; `live_trace.select_sql` becomes the news adapter; a second adapter proves S1 (2.4) |
| 1 | source item -> fragments (sentences, spans, numbers, dates) | `scan_gate`, `facts_lib`, `raw_core.units_for` | none |
| 2 | fragments -> assertions with evidence (subject, predicate, object, polarity, factuality, speaker) | `claims_v1.extract`, `claims_v0` resolver | lexicons out of code (2.3); factuality Planned / Predicted on the fragment |
| 3 | assertions -> entities with identity | spaCy + Few-NERD, `g4_align` ident-v2, GeoNames, Wikidata cache | status lexicon out; Wikidata cache built from the window's own names |
| 4 | assertions -> reinforced (independent owners), contradictions | `consolidate.independence`, `fact_join`, polarity / amount / date / direction kinds | owner map per source type (or item = its own owner); outcome / denial kinds become a loaded lexicon or go |
| 5 | assertions + items -> developments | `developments_v0` clustering + qualify rule | parameters frozen, then tested on an unseen window and on outside truth (ECB+ document groups) |
| 6 | developments across windows -> stable ids, stored history, since your last look | since-last-look mechanism, journal | **new: stable id rule + per-development history file** |
| 7 | development -> meaning for a reader goal | `educate` templates; quoted best-supported sentence | **new, owner decision**: grounded synthesis only if entailment-checked (2.5 D1); otherwise the quote stays |
| 8 | development -> forward statements with speaker and factuality | `FWD` + `sayer` | factuality from the fragment, not a regex; speaker from claims v1 on every fragment |
| 9 | developments -> ranking for a reader | `MOVED_ORDER`, `rank_key` bands, priorities file | **new: a ranking truth** (hindsight persistence on the live stream) before any ranking code |
| 10 | reader -> last look, recall | cut seq | **new, small**: a last-look record per reader key (file), nothing more |
| 11 | bundle x goal templates -> page | `goal-templates.json`, encoding rules, grounding gate | requirements interpreted from the JSON (field path + scope), no per-id code |

Rule that makes it general: a level's code may read only its input file and public reference data (WordNet, GeoNames, Wikidata, ECB+...). No area name, story word, publisher name or event-class verb in code. Lexicons are data with provenance and a test that the general path works with the lexicon off.

### 2.2 The few genuinely new capabilities

| New | Why it is needed and not more | Size |
|---|---|---|
| Source adapter interface + one non-news adapter | S1 is unproven; today the news queue is the pipeline's only door | small (a loader; the chain's news heads abstain on non-news input and say so) |
| Stable development id + history | G1 "what changed" is impossible when the id changes with every article | small, deterministic (member-overlap rule) |
| Ranking truth and one rule that beats recency | S2 / S3: "which matters" has no judge today; the owner's principle is live news is the judge | medium: a repeatable hindsight test on whole windows |
| Meaning (grounded synthesis), only after D1 | G2 / G6; the quote-only rule is honest but scored 33% on "why it matters" questions nobody asked (presentation-process 8) | medium, and only with the entailment test built first |
| Identity index (scale) | identity p50 grew 595 ms -> 3,287 ms from the first 50 to the last 164 articles of a 464-article window (`runs-e2e-101/triage-stream-summary.json`); linear in store size, so a 10k-item day stalls | small-medium: a cosine index (the design doc measured 0.033 ms/query at 10k) |

### 2.3 Deliberately not built (anti-overengineering list)

Rust pipeline (00 §6); Lean beyond the decider's 160 cases (00 §11); DenStream / micro-clusters (00 §9); a 100k-concept index before a 10k-item day runs; the human-knowledge model phases 1-3 (concept-delta-design, owner L2996: conceptual only); new typed relations beyond the 8 + 4; lanes and material / watch / background priorities (rejected, consolidation-method 3.8); map geometry; Macro Pulse tuple for every Area (coverage and freshness only where measured); per-reader interviews (goal templates cover any reader; priorities file optional); retraining the Macro Pulse heads for generality (they are a routing signal and a separate workstream); new pages (services.md rule); hosted labelling at scale; any model-written text without D1.

### 2.4 How generality is proven

| Proof | Setup | Outside truth | Pre-stated bar |
|---|---|---|---|
| P1 unseen staged window, frozen parameters | a third window picked by a rule (largest story-key cluster of the last 7 days whose Area is neither of c1 / mix), `PARAMS` untouched | none for purity (hand-read, reported) | every structural gate (D1-D8, K1-K8, grounding) passes with 0 code edits; compression >= 4; purity reported |
| P2 development grouping on outside truth | ECB+ documents (local, Apache-2.0: `fixtures/knowledge/ecbplus-join.json`, parquet) loaded as source items; gold = ECB+ sub-topic per document | ECB+ cross-document event clusters | pairwise F1 beats headline-TF-IDF-only by >= 0.05 at the frozen thr; re-tuning on the ECB+ train split moves F1 by <= 0.05 (small in-sample gap) |
| P3 second source type | Wikipedia current-events bullets (`data/anchors/current_events` snapshots, CC BY-SA, already fetched; different text shape: dated bullets with cited outlets) through a new adapter | the bullets' own cited outlets as owners | levels 2-11 run with 0 code edits outside the adapter; K3 evidence 100%; news-only stages abstain and are listed, never error |
| P4 scale | a 10k-item day replayed from the queue (14,227 items in the last 7 days) in <= 60-min chunks (`chain_windows.py`) | wall time | sustained >= 7 items/min end to end (10k/day) with identity p50 flat (+/- 20%) across chunks; today 13.7/min single process but identity grows linearly |
| P5 accuracy per level | section 2.6 | per level | ratchet rows; a drop exits 3 |

### 2.5 Decision points for the owner

| # | Decision | Default if silent |
|---|---|---|
| D1 | Meaning: allow entailment-checked synthesis (reader-first method rule 3) or keep "no model in the render path" (L2995)? The test (entailment harness with a shuffled-citation control) is built either way | quote-only stays; level 7 reported as a gap |
| D2 | Accept ECB+ document groups as the development truth and Wikipedia current events as the second source type | yes (both local, licensed, already in the repo) |
| D3 | Domain lexicons (war, casualty, health status) leave the code: moved to one provenance-tagged data file loaded by name, or deleted. Mix contested pairs may fall from 6 | move to data, keep loaded for news |
| D4 | Stable id rule: a development keeps its id when >= 50% of its earlier members are still in it (Jaccard on article ids) | yes |
| D5 | Ranking truth = persistence of reporting after a freeze on whole live windows (no persona list unless a priorities file exists) | yes |
| D6 | Scale target = 10k items/day sustained on this CPU box in <= 60-min chunks | yes |
| D7 | Commit the PROVISIONAL developments work (uncommitted since L3000) | wait |

### 2.6 How accuracy is decided per level

| Level | Outside truth | Bar (pre-stated) | Ratchet row |
|---|---|---|---|
| 2 | CaRB (`data/anchors/carb`) | F1 at or better than 0.565 | who-did-it + CaRB |
| 3 | Few-NERD types; K4 wrong-merge controls; Wikidata ids where resolvable | type accuracy reported; wrong merges 0 | g4_identity |
| 4 | ECB+ pairwise F1 >= 0.49 (met 0.5133); contradictions: K8 synthetic + true pairs on real windows | at or better | fact join, contested |
| 5 | ECB+ document groups (P2); purity hand-read on unseen window (reported) | P2 bar | new row |
| 6 | determinism + seeded reorder control (ids unchanged) | >= 90% ids kept across cuts, 0 collisions | new row |
| 7 | entailment harness (local Clef) with shuffled-citation control | control <= 0.2, real >= 0.9 | only after D1 |
| 8 | speaker hand-check sample (reported); factuality from fragment | named share reported, no bar yet | forward speakers |
| 9 | hindsight persistence on whole windows, Wilson CI | beats recency and random with non-overlapping CI on >= 2 windows | new row |
| 11 | grounding gate; non-circular question test (Jev/Clef pre-screen) | 0 ungrounded nodes; full-page >= headline control + chance | grounding |

## 3. Tactical plan: six rounds, each <= 1 hour of compute

Order: cheap deterministic first, generality proofs early, the uncertain levels (7, 9) only with their test built first. Every round: PREDICTION line in the ledger before, SCORE after, ratchet run, no hosted calls, no browser, CPU only, PID-verified stop.

| Round | Step | Files touched | Gate and pass bar | Outside truth | Reuses | Explicitly not |
|---|---|---|---|---|---|---|
| **A. Unseen window, frozen parameters** (P1) | pick window `u1` by the rule in 2.4 from the queue (30-60 articles, last 7 days); build with `build-knowledge-fixture.py --only u1` (the `AREAS` list becomes a parameter); build `area-u1`; run developments with `PARAMS` untouched | `simulation/build-knowledge-fixture.py` (AREAS from areas.json), `simulation/check-developments.py` (D5 becomes "the area's own known-case headline from areas.json, skipped when none"), `fixtures/knowledge/areas.json` | check-developments D1-D8 PASS on u1 with 0 edits to `developments_v0.py`; K1-K8 PASS; compression >= 4; purity hand-read and reported | none (hand-read purity is not truth; that is round B) | whole chain, fixture builder, gates | no parameter change, no new page; ~10 min compute (chain ~0.35 s/article, slow ~3 s/article) |
| **B. Development truth on ECB+** (P2) | load ECB+ test topics as source items (title = first sentence, time = null so decay = 1); run `developments_v0._group` at frozen `PARAMS`; score pairwise P/R/F1 and purity against gold sub-topic; baselines headline-TF-IDF only, single link; then re-tune on the train split and report the gap | new `simulation/check-developments-ecb.py`; new fixture `fixtures/knowledge/ecbplus-docs.json` (built from the local parquet); `developments_v0.py` only if time = null breaks (`_ts`) | F1 >= headline-only + 0.05 at frozen thr; in-sample gap <= 0.05; deterministic | ECB+ gold event clusters (Apache-2.0, local) | `fact_join.py` fixture code, `_agglo` | no change to `PARAMS` in production from this round; seconds of compute |
| **C. Second source type** (P3) | adapter `items_current_events(snapshot_dir)` -> source items; run fast chain stages + `slow_clock` + `slow_consolidate` + developments on one snapshot day set; `gen.py` page + grounding gate | new `projects/world-state/source_adapters.py` (news = `live_trace.select_sql`, current-events = new); `build-knowledge-fixture.py` takes `--adapter`; `check-knowledge.py --area ce1` | 0 code edits outside the adapter and the fixture builder; K1, K3, K6, K7, K8 PASS; K2 counters reported (bars are per source now, not per area); grounding 0 ungrounded; news-only stages listed as abstain | the bullets' cited outlets as owners (reinforced = 2+ outlets) | everything from level 1 down | not: a new page; not: training any head; <= 30 min compute |
| **D. Stable ids + history** (level 6) | id rule D4; `history/<id>.json` per development (window, articles, owners, certainty word, assertions, forward statements); replay `runs-e2e-101` at cuts 25 / 50 / 75 / 100% and check id survival | `developments_v0.py` (id and history), `check-developments.py` D9 | >= 90% of developments with >= 2 articles keep their id at the next cut when >= 50% members persist; 0 collisions; seeded article-order shuffle -> same ids; two builds equal | none needed (identity of our own objects); seeded control | since-last-look code | not: a reader store beyond the cut (level 10 stays a stub); ~5 min compute |
| **E. Lexicons out of code** (D3; levels 2-4) | one file `lexicons.json` {class: words, provenance (WordNet synset / FrameNet frame)} loaded by name; general path (polarity / amount / date / direction) runs with lexicons off; grep test "no word set of these classes in code" | `claims_v1.py` (HIT_V ...), `g4_align.py` (STATUS_*, CARE_*, *_OBJ, REPORT_PAIRS), `concepts_v0.py` (OPPOSE, KIN, NUM_RE units, STATUS_GROUPS), `check-parts.py` (grep test) | ratchet 0 regressions on c1 / mix with lexicons on (mix contested >= 6 pairs, who-did-it >= 0.9189, CaRB >= 0.565); with lexicons off every gate still PASS and counts reported; u1 / ECB / ce1 gates unchanged | CaRB, ECB+ (unchanged numbers) | all gates from A-C | not: new contradiction kinds; not: deleting the news lexicon; ~10 min compute (gates) |
| **F. Ranking truth first** (level 9; D5) | one more 40-min stream window (`chain_windows.py`, card + heartbeat, <= 60 min); freeze both windows at 60%; score moved-first, owners, recency, random, size by persistence after the freeze over ALL developments (not 9), Wilson CI | new `simulation/check-ranking-hindsight.py`; no ranking code change | a rule counts only if it beats recency and random with non-overlapping CI on both windows; else "no ranking signal yet" is the recorded result | future reporting in the live stream (live news is the judge) | `developments_v0` cut, `rank_key` bands | not: a persona list; not: Macro Pulse heads; not: any change to `MOVED_ORDER` or `rank_key` until the test says so; <= 60 min compute |

Gated on D1 (not scheduled): **G. Meaning test first** — entailment harness (local Clef) of candidate synthesized lines against their cited assertions with a shuffled-citation control (bar control <= 0.2, real >= 0.9); only then a synthesis slot in `gen.py`. Also after A-F: the identity index for P4 (measure first in round A/C: identity ms per article as the store grows, already in `check-triage-stream S5`).

What the rounds do not touch: `decider.py` / `lean/`, `live_trace.py` stage code, the Macro Pulse heads, the console pages, the news queue, any hosted model.

## 4. Files read for this plan

`playbook/design/knowledge-breakdown-flow.md`, `terminology.md`, `knowledge-consolidation-method.md` (3.2, 3.3, 4), `concept-delta-design.md` (2.1, 4), `reader-first-briefing-method.md`, `presentation-process/presentation-process.md`, `goal-templates.json`; `projects/world-state/developments_v0.py`, `concepts_v0.py`, `claims_v1.py`, `claims_units.py`, `raw_core.py`, `g4_align.py`, `consolidate.py`, `slow_consolidate.py`, `fact_join.py`, `live_trace.py`, `journal.py`, `evolve.py`, `educate.py`, `KNOWLEDGE_SCHEMA.md`; `simulation/raw-units.py`, `build-knowledge-fixture.py`, `check-developments.py`, `check-concepts.py`, `check-knowledge.py`, `check-alignment.py`, `check-reinforced-precision.py`, `check-agent-grounding.py`, `check-triage-stream.py`, `check-truth.py`, `fixtures/knowledge/areas.json`; `/workspace/_remove/presentation-process/gen.py`, `questions.py`, `results.md`; `/workspace/_remove/consume-mockups/spec.md`, `results.md`; ledger L2946-L3005; `demo/mockups/structure-live/runs-e2e-101/window.json`, `triage-stream-summary.json`; news queue counts (read-only sqlite); `data/anchors/` listing; HF cache listing.

## 5. Alignment to playbook 00 and MM3 check (added 2026-11-24)

| Level (breakdown flow) | 00 stage / section it belongs to |
|---|---|
| 0-1 Intake, fragments | G0 read; G1 spans |
| 2 Assertions | G2 facts, claims |
| 3 Entities | G2 entity types; G4 identity |
| 4 Corroboration, contradiction | G4 assertions, contradictions; §8 knowledge model |
| 5 Developments | G5 evolution (story roots, promotion) |
| 6 Change over time | §1 journal; §18 two clocks |
| 7 Meaning | G6 educate; §10 "what it is / why it matters" |
| 8 Projection | §10 "what is changing / uncertain" |
| 9 Relevance and rank | §10 Macro Pulse |
| 10 Reader state | §1 journal (reader cut) |
| 11 Render | §10 output contract (educator) |

No level replaces a 00 stage; each round extends the stage named above.

MM3-0756 (hosted Jev, class, quick) on this plan + 00 §1-2: goal 0.87 pass, route "proceed" 0.95, consensus SPLIT, risk medium.
Weak points it raised, now standing rules for every round:
- Frozen parameters on unseen data in EVERY round, not only round A (q1 0.45).
- Each round names its 00 stage (table above) (q4 0.46, q5 0.35).
- A gate can pass while an unseen area fails (q9 0.80): every round's gate also runs on the unseen window from round A.
