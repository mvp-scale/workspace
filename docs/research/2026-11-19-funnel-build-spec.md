# Build spec: plan v2 steps 2 to 6 (landing in the trace, journal, landing v1, resource ledger v0, learn loop)

Author: lead designer `[F?]` (Fable 5.1; effort inherited, level unknown: `~/.claude/settings.json` has no `effortLevel`). 2026-11-19. Read-only on the repo. Writes only this file and `team/build_spec/`. CPU only; no services touched; no ledger writes; MM3 (hosted Jev) saw only our code and this spec, never article text.
Sources: plan v2 `docs/research/2026-11-19 Knowledge pipeline consolidation plan.md`; Opus review `team/opus_plan_review.md`; playbook 00 §2, §8, §9, §13, §18; the stage contract `projects/world-state/live_trace_schema.json` (live-trace-v1) and its code; ledger L2694 to L2732 (L2707 owner resource-ledger design, L2721 field-test bars, L2730 to L2732 step 1); my two checks in `team/build_spec/` (c1, c2; predictions in the script headers, scored in §9). MM3 run ids in §10. Anything else is my own reading and says so.

## 0. Words used once

| Word | Meaning here |
|---|---|
| Trace | One run of `live_trace.py`: `run.json`, `tail.json`, `chain.jsonl` (hash chain of article lines), `a/<seq>.json` (raw text and full stage output). Contract: `live_trace_schema.json`. |
| Replay set | The 2,739 traced queue articles (2,736 traced, 3 skipped) in `demo/mockups/structure-live/trace-demo/` (run `run-1795022165-5ce7bc`, live-trace-v1, no landing). |
| Landing | The IPTC Media Topic whose card (label + definition + parent path, embedded once with bge-small) is nearest to a text. Code: `pack_view.Landing`. Provenance Inferred. |
| Level 1 / level 2 (L1 / L2) | Top of the IPTC tree (17 codes) / its children. Always compared by `medtop:` code, never by name (plan v2 rule 1; table `specs/mnds_name_to_code_v1.json`). |
| Sentence vote | Each sentence of at least 40 characters lands on its own card; the L1 codes are counted. |
| Hub card | A card that attracts a disproportionate share of items (border dispute 4.2% of queue items, L2722). |
| Damping | Subtracting a share-based penalty from a hub card's cosine before the argmax. |
| Calibrated probability (p) | The chance the landing's L1 is right, from a logistic model fitted on gold; a cosine is not one (§4 of the playbook; check c2). |
| Abstain line | The p below which the decider's topic_node field abstains. |
| Decision object | The landing stage's `decision` value: EVIDENCE_ONLY, ANSWER_L1 or ABSTAIN. |
| Journal record | Per-article fields inside the article line: IDs, label version, duplicate key, independent-publisher count (§18.4, §18.8). |
| Copy / republished / generic title | Same story key from another publisher / from the same publisher again / a title that is a column name ("business daily"), so it is not a story key. |
| Independent publishers | Distinct `source` values carrying the same story key in one run. Not the per-article `independent_counter` stage (that counts amount and date runs inside one article). |
| Resource | One of the engine's 26 resources (`/workspace/exports/world-engine-ontology-rules_v2.json`, 7 groups), seeded per L2707. |
| Condition | One of the engine's 39 conditions, each with a `resource_id`, `up_means` and `half_life_ticks`. |
| Learn queue | Items whose topic_node outcome harvests `LABEL_QUEUE` (decider.py), waiting for a teacher read in IPTC codes. |
| Label version | `{iptc_release, cards_sha, table}`: which IPTC file, which card set and which name-to-code table produced a label (§18.8). |
| Owner gate | A step that waits for the owner's yes before any repo change or spend. |

Baselines on file (all by code): landing L1 0.561 on T28 (1,676) and 0.562 on fresh2 (1,352); L2 0.327 / 0.286 on code-matched items (L2731). Bars (L2721 plus plan v2): L1 >= 0.60, L2 >= 0.40, publisher sections >= 0.70 (reference map), share error <= 0.010, events 4 of 5, split-half >= 0.80 with no L2 node above 10%, safe abstain accuracy >= 0.80 at coverage >= 0.50, landing stage <= 20 ms per article.

## 1. Contract diff (one schema change, `live-trace-v1` to `live-trace-v2`, owner gate)

The schema says a builder who needs a change reports it and stops. This section is that report. Nothing below is edited until the owner says yes to v2.

### 1.1 New stage `topic_landing` (step 2; `out` must serialise under 700 characters: `run()` at `live_trace.py:81` replaces anything longer with a 560-character head, which would silently drop fields, so U7 checks the size on the fixture and the replay set; MM3-0691 asked who enforces the cap)

| Field | Type | Meaning | Written by |
|---|---|---|---|
| `name` | "topic_landing" | Sits after `domain_rollup`, before `structure_pack` (so the pack can test its words against the landing's L1 code) | step 2 |
| `gate` | "G3a" | A classifier over a fixed label space (playbook §4), not an ontology change | step 2 |
| `kind` | "model" | | step 2 |
| `version` | string | `"landing-v0; bge-small-en-v1.5; medtop <dateReleased>; cards <16 hex>; alias=off; seq256; text[:2000]"`. `cards` = sha256 over the card strings in card order. Step 4 writes `landing-v1; ...; calib <16 hex of specs/landing_calibration_v1.json>` | step 2 / 4 |
| `provenance` | "Inferred" | Always | step 2 |
| `out.best` | `{qcode, layer, score, margin}` | Nearest card: code, depth (1 = top), cosine, cosine minus second best | step 2 |
| `out.top3` | `[[qcode, score] x3]` | | step 2 |
| `out.l1_code` | "medtop:NNNNNNNN" | L1 code of `best` | step 2 |
| `out.l1_agree3` | int 1 to 3 | How many of the 3 best cards share `l1_code` | step 2 |
| `out.vote` | `[[l1_code, n_sentences] x <=3]` or `[]` | Sentence vote by L1 code; `[]` when no sentence has 40 characters | step 2 |
| `out.n_sent` | int | Sentences landed (at most 25) | step 2 |
| `out.agrees_rollup` | bool or null | `l1_code == l1_code(domain_rollup top)` through `pack_view.l1_code` (a code join). Null when the roll-up did not run. Reference only: the roll-up is the legacy 49-to-17 map | step 2 |
| `out.decision` | "EVIDENCE_ONLY" / "ANSWER_L1" / "ABSTAIN" | v0 writes EVIDENCE_ONLY on every ran item. v1 writes ANSWER_L1 when `p >= line`, else ABSTAIN | step 2 / 4 |
| `out.p` | float or null | Calibrated probability that `l1_code` is right. Null in v0 | step 4 |
| `out.damped` | bool | Whether damping changed `best` (v1) | step 4 |
| `n` | int | 1 + `n_sent` | step 2 |
| `stages_full.topic_landing` | object | `article`: 5 nodes as `Landing.node` (qcode, label, layer, path, path_codes, definition, siblings, children, wikidata, score); `sentences`: up to 12 nodes with `n_sentences` and 3 example sentences (160 characters each); `features` (v1): the vector the calibrator saw | step 2 / 4 |

`pack_view.Landing.node` gains `path_codes: [qcode...]` (so the page and the journal never join on labels) and `Landing.land` gains a `vote_by_code` result; `Landing.__init__` accepts an existing encoder (`emb=`) so `live_trace.Chain` does not load bge-small twice. Three rules fixed by MM3-0690 (class on `pack_view.py:97-128`, gate fail, split): (a) cards are built in `sorted(pack.node)` qcode order, not dict iteration order, and `cards_sha` is the sha256 over the card strings in that order (Q2, p 0.82 that the order was unpinned); (b) after step 2 the pack stage no longer embeds anything (its bge call only produced the removed `l1_guess`), so `Chain.bge` is owned by the landing at `max_seq_length 256` and no caller switches the sequence length per call (Q5, p 0.59 that per-call switching would change other callers' results); (c) retired IPTC nodes are filtered out of the card set in `__init__` (today's line 108), so `land()` can never return a retired node; the spec states this instead of assuming it (Q7, p 0.20).

### 1.2 Changed stage `structure_pack`

| Field | Change |
|---|---|
| `out.l1_guess`, `out.guess_top3` | Removed (they were the 17-top-level-card landing, 0.425 in L2719, and the two remaining label joins flagged by `check_id_joins.py`) |
| `out.in_topic` | Kept; now counted against `topic_landing.out.l1_code` (code join). Null when the landing did not run |
| `out.l1_code_used` | New: the code the pack filtered by (same as the landing's), so the page can say which |
| `note` in `stage_names` | "WordNet placement of the article's words on the IPTC tree; the topic guess moved to topic_landing" |

### 1.3 New decider field `topic_node` (step 4; no rule change)

`decider.py` is unchanged (its rules are the Lean rules, `rust_decider/vectors.txt`, 160 vectors). The field table `runs/pulse/field_table.json` gains `"topic_node": {"marker": 2}` (BELOW_BAR, because L1 0.56 is under the 0.60 bar). The proposal is `Proposal(Source.TRAINED_HEAD, p, True, l1_code, "landing-v1")`, `conf_permille = int(1000 * p)`, threshold = the abstain line in permille (from the calibration spec, not `Analyzer.thr`). Outcomes therefore: `ABSTAIN_LOW_CONFIDENCE` (harvest LABEL_QUEUE: the learn queue) or `ANSWER_PROVISIONAL` (harvest DISCARD) until the marker reaches MEETS. The legacy `topic` field stays (every head stays on).

### 1.4 New article-line fields (step 3; all inside `line`, so the chain hashes them)

| Field | Type | Meaning |
|---|---|---|
| `journal.label_version` | `{iptc_release, cards, table}` | From the landing version string and `mnds_name_to_code_v1.json` |
| `journal.ids.topic` | `{best, l1, l2, top3: []}` qcodes | L2 is null for a layer-1 landing |
| `journal.ids.places` | `[ISO-2 country...]` | From `place_linker.out.top_countries` (GeoNames codes already) |
| `journal.ids.names` | `[string...]` (up to 20) | From the `facts` stage names. Strings until step 7 (Wikidata) gives IDs; marked `"names_id_space": "string"` |
| `journal.story_key` | `{title: sha1 or null, prefix: sha1 or null}` | Title key only when the normalised title has >= 5 words and is not generic; prefix key = sha1 of the first 300 normalised body characters when the body has >= 100 |
| `journal.dup` | `{kind, of_seq}` | kind in `first`, `copy`, `republished`, `generic_title`, `no_key` (see §2.3); `of_seq` = seq of the first item with that key in this run |
| `journal.publishers` | int | Independent publishers for this story key so far in this run (1 for a first) |
| `journal.permission` | "public-news" | G0 source/permission field, fixed for the queue (§18, G0) |

### 1.5 `run.json` additions

| Field | Meaning |
|---|---|
| `version` | "live-trace-v2" |
| `label_version` | `{iptc_release, cards, table, calibration}` (calibration null before step 4) |
| `journal` | `{first, copy, republished, generic_title, no_key, independent_items, l2_nodes: [{code, label, items, publishers}] top 50 by independent items}` |
| `stages.topic_landing` | Counts by state and p50/p90 as for every stage (from `live_gaps.aggregate`, no code change) |
| `decider.topic_node` | Outcome counts (automatic) |
| `gap_rules` | Includes the new codes below |

### 1.6 Gap codes (`live_gaps.py`)

| Code | Rule | Kind |
|---|---|---|
| `TOPIC_DISAGREE` | Now `topic_landing.l1_code != l1_code(domain_rollup top)`; the text says "reference: the roll-up is the legacy map" | Reference (kept, relabelled) |
| `LANDING_SPLIT` | Article `l1_code` differs from the sentence vote's top L1 code when the vote has >= 3 sentences | New design's own disagreement |
| `LANDING_WEAK` | v0: `best.score < 0.58` (bottom quarter of absolute scores, run A). v1: `decision == ABSTAIN` | New |
| `SYNDICATED` | `journal.dup.kind in (copy, republished)` | New (§18.4) |
| `UNPLACED_HIGH` | Unchanged | |

### 1.7 Backward compatibility

| Reader | v1 traces (replay set, fixture today) | v2 traces |
|---|---|---|
| `demo/mockups/structure-live/index.html` | Must keep working: it reads `pk.l1_guess` (lines 220, 283, 317, 369) and `stages_full.structure_pack.placed_spans` (446, 543). Rule: `var L = stage("topic_landing")`; when absent, the old text path runs unchanged | Shows the landing row: best path, L1, vote, decision, p; the TOPIC_DISAGREE sentence says "reference" |
| `live_gaps.aggregate` / `per_article_gaps` | Pure functions over lines; new rules are guarded by `if S.get("topic_landing")`, so v1 lines produce the old gaps | New gaps |
| `verify_trace.py` | Unchanged checks (chain, seq, sha1, allowlist). Adds: `version` in run.json must be v1 or v2; v2 lines must have `journal` | |
| `fixture/` | Regenerated by `fixture/make_fixture.py` as v2 with six articles: clean, teaser-only, error stage, not_attached, syndicated copy (same title and prefix as the clean one, other source), landing abstain (v1 shape with p 0.31). The v1 fixture is kept as `fixture-v1/` so the fallback path has a test | |
| `simulation/index.html` 8c | Already reads `pack.landing` from the bench; gains the code fields and the resource panel (step 5) | |

## 2. State tables

### 2.1 Stage `topic_landing` (per article)

| State | Trigger | Written (`out`, `why`) | Page shows | Next |
|---|---|---|---|---|
| ran | Text >= 40 characters (every traced line); cards loaded | `best, top3, l1_code, l1_agree3, vote, n_sent, agrees_rollup, decision` (+ `p, damped` in v1) | Row: path of `best`, L1 label with code, vote, decision chip | `structure_pack` filters by `l1_code`; decider `topic_node` (v1); journal ids |
| ran, no vote | Ran, but no sentence has 40 characters (teaser-only, list pages) | `vote: [], n_sent: 0`; `why: "no sentence of 40 characters"` on a ran stage (allowed: `why` is a short reason) | Vote cell "none (short text)" | `LANDING_SPLIT` cannot fire; p uses the article features only (c2 shows these reach 0.735 at half coverage) |
| empty | Cannot occur for a traced line: the runner skips lines under 40 characters before any stage | Never written | | Documented so the aggregate's empty count reads 0 by design |
| abstain | v1 only: `p < line` | `decision: ABSTAIN, p`; `why: "p 0.31 below the line 0.70"` | Chip "abstain", gap `LANDING_WEAK` | Decider `topic_node` ABSTAIN_LOW_CONFIDENCE, harvest LABEL_QUEUE: learn queue |
| error | Exception inside `Landing.land` (for example a card matrix shape mismatch after a partial file write) | `state error, out null, why "<Type>: <message[:200]>"` (the `run()` wrapper already does this) | Red chip, gap `STAGE_ERROR` | Downstream: `structure_pack.in_topic` null; journal `ids.topic` null; the line is still chained |
| timeout | Defined by the contract; the runner has no watchdog and never produces it today | Not produced. Over 2,000 ms the stage gets `slow: true` and appears in `run.slow_stages` | "slow" marker | Honest note in the schema: `timeout` stays reserved; a watchdog is not in steps 2 to 6 |
| not_attached | Cards failed to build at start-up (IPTC file missing or unreadable) and the operator set `ALLOW_NO_LANDING=1` | `Chain.__init__` catches the failure, sets `self.landing = None` and adds `topic_landing` to `self.NA` with why "source pack_view.Landing: medtop.json unreadable: <error>" | Row "NOT BUILT" with the reason; run banner "degraded: no landing" | Every other stage runs; `TOPIC_DISAGREE`, `LANDING_*` cannot fire; `journal.ids.topic` is null; `NOT_ATTACHED` gap counts 5 stages |
| refused to start | Same failure without `ALLOW_NO_LANDING=1` (the default). MM3-0695 rated an hour-long trace without its main head critical (p 0.72), so the default is fail-fast | `run.json` with `state: error`, `why: "topic_landing could not build: <error>"`, no chain line | "run refused: no landing" | Operator fixes the file or opts into degraded mode |

### 2.2 Decision object and decider field `topic_node` (step 4)

| Decision | p | Decider outcome (marker BELOW_BAR) | Harvest | Page | Resource ledger uses it? |
|---|---|---|---|---|---|
| EVIDENCE_ONLY | null (v0) | Field absent in v0 | none | "evidence only" | Yes, as talked-about only (count), weight 0.5 |
| ANSWER_L1 | >= line | ANSWER_PROVISIONAL | DISCARD | "provisional answer" | Yes, full weight |
| ABSTAIN | < line | ABSTAIN_LOW_CONFIDENCE | LABEL_QUEUE | "abstain", gap LANDING_WEAK | Count only, weight 0.25; never a direction |
| (any) | n/a | ANSWER | TRAINING_LABEL never (source is TRAINED_HEAD) | | Only after the marker moves to MEETS, which needs L1 >= 0.60 on MN-DS by code: an owner decision after the bar is met |

The line: the smallest p at which running accuracy on T28 stays >= 0.80, re-checked on fresh2; c2 says this is p 0.70 today and covers 13.8% of fresh2 (running accuracy 0.80). Written into `specs/landing_calibration_v1.json` with the features, coefficients, fit set and date; the file is in `model_sha`.

### 2.3 Journal record (step 3)

| `dup.kind` | Trigger | Written | Page | Next |
|---|---|---|---|---|
| first | Neither key seen in this run | `publishers: 1, of_seq: null` | nothing special | Index entry created |
| copy | A key seen from another `source` | `of_seq: <first seq>`, `publishers` = distinct sources for that key so far | Gap `SYNDICATED`; row says "copy of #<seq> (<source>)" | Resource ledger: the story's weight is not added again; `publishers` rises on the first item's key |
| republished | A key seen from the same `source` | `of_seq`, `publishers` unchanged | Gap `SYNDICATED` | Counted 0 for items and publishers |
| generic_title | Title key disabled (under 5 words, or the same title from the same source with 3 different prefix keys so far: "business daily", "tech life", c1) | `story_key.title: null`, prefix key used alone | Note "title is a column name" | Dedup by prefix only |
| no_key | No body of 100 characters and a short title | Both keys null; `publishers: 1` | Note "no story key" | Treated as its own story; counted once |
| (skipped line) | `state: skipped` | No `journal` object | | |

Independent counts live per run (the chain is per run); the day table of step 5 sums over runs by key, and says so.

### 2.4 Resource ledger v0 (step 5; per resource, computed on the sim page from the bench results)

| State | Trigger | Shown | Next |
|---|---|---|---|
| untouched | No item reached the resource in this stream | Grey row, "no mention yet" | |
| warming | Reached by < 5 independent items | Value and count, muted | |
| talked about | >= 5 independent items, no direction | Value, items, publishers, top L2 topics feeding it | |
| moving up / moving down | Condition head answered with a direction on an item that reaches this resource through a condition link; the signed step dominates | Arrow with direction mapped through `up_means` ("strain" means up is bad for the resource; the page says this in words) | |
| conflicted | Both directions within the window with neither above two thirds of the signed mass | "disputed", both counts | |
| decaying | No touch for longer than the condition's half-life | Faded value | Falls to warming, then untouched when under 0.05 |
| not linked | An L2 topic reached by items but no link to any condition | Listed under "topics with no resource link" with counts; candidates for an add-only link (`ours:`, guess) | Owner Q4 still open: stays a list |

Step sizes (L2707 wording, L2708 settings, one place `simulation/index.html` as a constant table shown on the page): talked about +0.2 x function weight (fact 1.0, forecast 0.5, opinion 0.3, unclear 0.5) split over the resources reached; stated positive or negative (Condition present with direction) +-1.0; substantial change (Condition size "large") x2 with direction; decay per independent-item tick k = 0.5^(1/half_life_ticks) with the engine's half-lives; copies and republished items add nothing. Every link is "guess" (the engine marks them so).

### 2.5 Learn queue (step 6)

| State | Trigger | Written | Next |
|---|---|---|---|
| queued | `topic_node` harvest LABEL_QUEUE in a trace, or a replay-set item below the line | Row in `data/newsreader/labels/learn_queue.jsonl`: `{id, text_sha1, label_version, p, l1_code, when}` (no text: the text is in the queue by id) | sampled |
| sampled | Picked for a teacher round: seeded, at most N per round, split by source and day (§13) | `round` id | labelled or rejected |
| labelled | Teacher returned an active IPTC code (L1 then L2 by code, "none fits" allowed) | `{teacher, model_version, l1_code, l2_code, label_version, cost_usd}` | trained or held_out |
| rejected | Teacher said none fits, or returned a code not in the active set for `label_version` | reason | Stays out of training; counted per round |
| trained | Used in a student round | `student_round` | |
| held_out | Reserved by source split for scoring the student; never trained | | |
| expired | A new IPTC release (`iptc_release` differs): the label is re-mapped by code; a retired code becomes rejected with reason "retired in <release>" | | |
| pilot | The first 500 MN-DS T28 items (gold by code), not queue items: measures the teacher before any queue spend | | Stop rule: teacher L1 <= landing 0.561 means stop (plan v2 step 6) |

### 2.6 Run-level states and degraded paths

| Situation | What happens | Written | Page | Next |
|---|---|---|---|---|
| No body text (teaser only) | Landing on title + teaser; usually no vote | `input.has_body false`; gap `TEASER_ONLY`; `vote []` | "short text" | p lower by the length feature (coefficient -0.288 on log length, c2) |
| Model file missing at start (bge-small HF cache, place pickle, v6b pickle) | `Chain()` raises; the runner exits before `run.json` exists | Nothing, today | "no run.json" | Change in step 2: wrap `Chain()` in `main()` so `run.json` is written with `state: error, why: "<Type>: <message>"` and exit 1. For the IPTC file alone: not_attached path of §2.1 |
| Model file changes during the run | `hash_sets` every 5 min differs | `state: drift_stop`, `drift: [paths]` | Banner "stopped: code or model changed", listing `drift` paths | New run needs a new PAGE_DIR (the runner refuses to append) |
| IPTC release changes (new `medtop.json`) during a run | The same drift path wins: the file is in the code hash, so `drift_stop` within 5 min with `drift: [".../medtop.json"]`; the banner names the IPTC file (MM3-0693 asked which path wins) | As above | "stopped: the IPTC file changed" | Before the next run: `python3 mnds_codes.py` rebuilds the name-to-code table (`iptc_release` inside it); the card set and `cards` sha change; codes are kept across renames, retired nodes drop out of the cards; later runs carry the new `label_version`, old lines keep theirs; journal and labels compare by code, so old records stay valid; `expired` rule in §2.5 |
| Embedding slow (CPU contention, long article) | Stage ms over 2,000 | `slow: true`, `run.slow_stages` | Marker | Bar check in §4 (landing stage p50 <= 20 ms) decides whether the vote escalates only on `l1_agree3 < 3` |
| Empty landing | Cannot occur once cards exist: the argmax over 1,059 cards always returns one; zero cards is the refused-to-start or not_attached row | Nothing (by design) | Nothing | Stated so the `empty` count of this stage reads 0 by design (MM3-0692 flagged the blank cells) |
| Duplicate or syndicated article | Traced fully; journal `dup.kind` copy or republished; `SYNDICATED` gap | `journal.dup {kind, of_seq}`, `journal.publishers` on the first item's key | Row note "copy of #<seq> from <source>"; the run's `journal` counts | Not added to independent counts or ledger weights; still lands and still goes to the learn queue if it abstains (one teacher read per story key: the queue dedups by key) |
| Queue backlog | Rows are read in `ready_at` order, 25 at a time, selecting only the allowlisted columns (`id, url, source, title, teaser, body, published, ready_at`; `category, region, country, story` are never read, MM3-0694); nothing is skipped; `counts.backlog_ready` and `queue_lag_p50_s` rise | counts | "lag" and the backlog count | The 1-hour cap ends the run with the backlog recorded; the next run starts at its own START (items between runs are not traced: say so on the page) |
| Stale derived values (the one flag MM3 raised on every story: silent failure p 0.66 to 0.77, MM3-0695; 0.54 to 0.71, MM3-0692 to 0694) | A page or panel shows a number computed from an older run, label version or seq | Every derived object carries `as_of: {run_id, seq, label_version}`: `run.journal`, the resource panel rows, the calibration spec. `run.json` already carries `now_epoch` | Page and panel print "as of article #n, run <id>, labels <iptc_release>/<cards[:8]>" and grey out when `now_epoch` is older than 60 s on a running run | A `label_version` that differs from the run's marks the row `stale: true`; the page says so in words |
| Decider abstains on everything (line too high after a release) | `decider.topic_node` all ABSTAIN | counts | | Learn queue fills; the round cap (§5) limits spend |
| Page opened on a v1 trace | Fallback path | | Old text | |

## 3. Files touched, and what must not change

| Step | File : function | Change |
|---|---|---|
| 2 | `projects/world-state/live_trace_schema.json` | v2 as in §1 (owner gate) |
| 2 | `live_trace.py : Chain.__init__` | `self.bge.max_seq_length = 256` (the pack stage no longer embeds); `from pack_view import Landing; self.landing = Landing(self.pack, alias=False, emb=self.bge)` in a try; on failure `self.landing = None` and, only when `ALLOW_NO_LANDING=1`, `self.NA["topic_landing"] = ("G3a", "...")`, else raise so `main()` writes the refused-to-start `run.json`. Remove `self.L1names`, `self.L1E`. Versions dict gets `topic_landing` |
| 2 | `live_trace.py : Chain.trace` | New `def landing()` (needs `ff` for the spaCy doc; `need("ff")` as `pack()` does) run before `pack()`; `pack()` loses `sc/order/guess` and takes its L1 code from `ctx["l1_code"]` only (null when the landing did not run); the `run()` wrapper already turns any exception into `state: error` (MM3-0691 Q1, p 0.14 that one escapes), so no new try is needed inside the stage functions; `self.NA` loop unchanged |
| 2 | `live_trace.py : hash_sets` | Adds `pack_view.py`, `mnds_codes.py`, `specs/mnds_name_to_code_v1.json` to the code set (they now shape the trace) |
| 2 | `live_trace.py : main` | `Chain()` inside the try; `run.json` carries `version`, `label_version` |
| 2 | `pack_view.py : Landing.__init__ / node / land` | `emb=` parameter, `path_codes`, `vote_by_code`, `cards_sha` attribute |
| 2 | `live_gaps.py : RULES, per_article_gaps` | §1.6 |
| 2 | `verify_trace.py : check` | Version check; v2 lines need `journal` (step 3) |
| 2 | `demo/mockups/structure-live/index.html` | Landing row; fallback; ORDER gets `topic_landing`; TOPIC_DISAGREE text |
| 2 | `demo/mockups/structure-live/trace/fixture/make_fixture.py` | Six v2 articles; v1 copy kept |
| 2 | `check_id_joins.py` | `live_trace.py` moves from PENDING to CHECKED; `pack_view.py` stays CHECKED |
| 3 | `live_trace.py : Chain.trace` + a small `journal.py` (new, pure functions: `story_keys(title, body)`, `classify(key_index, keys, source)`) | §1.4; `main()` keeps `key_index` in memory and writes `run.journal` |
| 3 | `live_gaps.py : aggregate` | `journal` block of §1.5 |
| 4 | `specs/landing_calibration_v1.json` (new), `runs/pulse/field_table.json` (+`topic_node`), `live_trace.py : landing(), decider()` | §1.1 v1 fields, §1.3. The decider loop (`for k, p in props.items(): mk = self.FT[k]["marker"]`) takes any field that has a field-table entry, so the sixth field needs the entry or it is a KeyError (U8 checks); the path marker BELOW_BAR + source TRAINED_HEAD is the one the legacy `topic` field already walks, so no new Lean path (MM3-0691 Q9 was unsure at 0.42; this is my reading of lines 186-192, and U2 proves the rules untouched) |
| 4 | `team/build_spec/c2_calibration.py` becomes `projects/world-state/landing_calibrate.py` | Fit on T28, score on fresh2, write the spec file; prediction line in the header |
| 5 | `specs/iptc_condition_v0.json` (new) | For each engine condition: the IPTC codes that talk about it. v0 is derived: engine `topic_condition` (49 legacy topics) through `topic_to_iptc_v1.json` (Area to L1 name) through `mnds_name_to_code_v1.json` (name to code). Every row `status: "derived from the engine's guess, reference"`; L2 refinements are add-only rows with `status: "ours, guess"` and a `changeNote` |
| 5 | `simulation/server.py : run_article` | Returns `landing.article[].path_codes` (comes with the pack_view change) and the condition fields already present; no new endpoint |
| 5 | `simulation/index.html` | `#s_ledger` div under `#s_tally`; `renderLedger()` in `streamLoop` after `renderTally()`; constants table; `textContent` only |
| 5 | `knowledge_pipeline/services.md` | The sim bench row mentions the ledger panel (no new page) |
| 6 | `projects/world-state/learn_queue.py` (new): `enqueue(trace folder)`, `sample(round)`, `pilot(500 T28 ids)`, `teach(round)` through the existing hosted wiring (`jev_wire.py`, to be checked, not assumed), `train(round)` (T145 TF-IDF+SGD recipe, L1 codes), `score(round)` on fresh2 by code | §2.5 |

Must not change: `decider.py` and `lean/Decide.lean` (`check_against_lean()` must still return 160); every stage that runs today keeps running (`windows, scan_dates, facts, independent_counter, tags_bundles, span_rules, place_linker, area_function, domain_rollup, condition, place_student, capability_list, structure_pack, decider` and the four not_attached rows stay listed); the legacy `topic` decider field; the `columns_allowlist` and the anti-cheat list; the chain line format (`seq, prev, sha, line`); no new page (`services.md` rule); `medtop.json` is never written; the replay set folder `trace-demo/` is never rewritten (new runs go to a new PAGE_DIR).

## 4. Tests (command, pre-registered prediction)

All from `/workspace/knowledge_pipeline/projects/world-state` with `PY=/workspace/models/embed-zs/.venv/bin/python` unless stated. Each prediction goes on the ledger before the run; the owner session writes it.

| # | Check | Command | Prediction (before the run) |
|---|---|---|---|
| U1 | Compiles; no label joins | `python3 -m py_compile live_trace.py pack_view.py live_gaps.py journal.py && python3 check_id_joins.py` | exit 0, "pending (step 2): 0" |
| U2 | Decider untouched | `$PY -c "import decider; print(decider.check_against_lean())"` | 160 |
| U3 | Fixture v2 verifies; v1 fixture still verifies | `$PY verify_trace.py /workspace/demo/mockups/structure-live/trace/fixture && $PY verify_trace.py .../fixture-v1` | both PASS; the v2 fixture has gaps SYNDICATED on #4 and LANDING_WEAK on #5 |
| U4 | Gap rules on fixture lines | `$PY -c "import json,live_gaps as G; [print(l['seq'], G.per_article_gaps(l)) for l in json.load(open('.../fixture/tail.json'))]"` | #0 NOT_ATTACHED only; #1 TEASER_ONLY, FACTS_ZERO; #4 SYNDICATED; #5 LANDING_WEAK |
| U5 | Page fallback | Open `structure-live/index.html?base=trace-demo/` (v1) and `?fixture=1` (v2) headless (curl of the data files; the page itself in a headless browser if the owner wants) | v1: old text path, 0 console errors; v2: landing row present |
| U6 | Journal keys | `$PY -c "import journal; print(journal.story_keys('Business daily', 'x'*50), journal.story_keys('Democrat Hakeem Jeffries is nominated to become House speaker, a historic first', body))"` | first: title null (under 5 words), prefix null (body under 100); second: both keys |
| U7 | Landing `out` never hits the `run()` truncation | `$PY -c "import json,glob; print(max(len(json.dumps(json.load(open(f))['article_line']...topic_landing.out)) for f in glob.glob('<folder>/a/*.json')))"` on the v2 fixture and the first v2 trace | Maximum under 700 characters (my estimate 350 to 450); zero stages with `out.truncated` |
| U8 | Field table and Lean path for `topic_node` | `$PY -c "import json; print(json.load(open('runs/pulse/field_table.json'))['topic_node'])"` and `grep -c '^2 1 ' rust_decider/vectors.txt` | `{"marker": 2}`; the vector file already holds marker-2, source-1 cases (count > 0), so the field adds no untested path |
| U9 | Card order and label version are reproducible | `$PY -c "import spacy; from structure_pack import Pack; from pack_view import Landing; print(Landing(Pack(spacy.blank('en')), alias=False).cards_sha)"` twice in fresh processes | Identical 64-hex value both times |
| R1 | Offline landing replay, deterministic | `$PY team/build_spec/replay_landing.py /workspace/demo/mockups/structure-live/trace-demo out.json` twice; compares sha256 of the outputs; also writes L1 distribution, vote agreement, hub shares | Identical sha both runs; L1 agrees with the legacy roll-up top (by code) on 30 to 40% of items (today's TOPIC_DISAGREE is 74.5% with the 17-card method); `LANDING_SPLIT` on 25 to 40%; largest L1 share under 25%; runtime under 10 min |
| R2 | Two-process replay through the runner (existing check) | `$PY verify_trace.py <new v2 trace folder> --replay 50` | PASS (state, n, out equal; `topic_landing` included) |
| R3 | Non-landing stages unchanged against the replay set | `$PY team/build_spec/compare_stages.py trace-demo <new folder>` on the same 200 queue ids (`--replay-run`) | state and n equal on >= 99.5% of (item, stage) pairs for the 14 running stages; the only differences are in `structure_pack.out` (fields removed) |
| L1 | Landing stage latency | `$PY live_trace.py --time 60` | `topic_landing` p50 25 to 45 ms at seq 256 on text[:2000] with a full vote (misses the 20 ms bar); total p50 rises from 75 to 100 to 130 ms, p90 under 450. If missed: v1 escalates the vote only when `l1_agree3 < 3` and re-times; predicted p50 then 15 to 25 ms |
| M1 | Right topic by code (L2721) | `$PY /tmp/.../scratchpad/step1/rescore.py out.json` (v0 = step 1 numbers; v1 with damping and vote) | v0 0.561 / 0.562 L1 (no change by construction); v1 L1 0.565 to 0.585 on fresh2 (c2: damping +0.009; vote UNMEASURED), L2 0.29 to 0.33; both bars still FAIL |
| M2 | Publisher sections (reference map) | `$PY /tmp/.../scratchpad/field/field_test.py out.json` re-run on **body text** from the replay set (not title + teaser) | 0.35 to 0.45 (from 0.295); FAIL the 0.70 bar; science/tech stays the worst section |
| M3 | Events | Needs a dated outside events list (download, owner yes). Smoke only: Halloween and the 11-03 vote on the queue | Unchanged until the list exists: 1 of 2 |
| M4 | Trends | `field_test.py` M4 block, plus the resource-level split-half (`team/build_spec/ledger_split.py` over the replay set in 12 windows) | L2 split-half median >= 0.80 (0.856 known); no L2 node above 10% (election 8.3% known); resource-level split-half 0.5 to 0.7 whole-stream, under 0.5 per window (L2709 pattern), so "trends" at resource level is not shown yet |
| S1 | Share error | `blocker_check.py` (b) block re-run with the v1 landing | 0.028 to 0.033 (from 0.033); FAIL the 0.010 bar; the lever is accuracy, not calibration |
| A1 | Safe abstain | `landing_calibrate.py` (fit T28, score fresh2) | Measured in c2 for the v0 features: 0.735 at coverage 0.50, 0.138 coverage at 0.80 (FAIL). v1 adds the vote features: 0.74 to 0.78 at 0.50 (still FAIL); coverage at 0.80 rises to 0.15 to 0.25 |
| P1 | Jev-in-IPTC pilot (owner yes) | `$PY learn_queue.py --pilot 500 --dry-run` prints token count and cost first; then the run | Teacher L1 by code 0.70 to 0.80, L2 0.40 to 0.50 on 500 T28 items; cost 0.03 to 0.08 USD; "none fits" on under 5% |
| P2 | Student round 1 | `$PY learn_queue.py --train 1 --score fresh2` | Student trained on 2,000 to 4,000 teacher-labelled queue rows (source and day split): L1 0.58 to 0.62 on fresh2 (bar: +3 points over 0.562 per round); if the pilot missed, this does not run |

## 5. Resources and owner gates

| Step | CPU | Money | Human | Gate |
|---|---|---|---|---|
| 2 | Under 1 h total: code 1.5 h of my time, R1 under 10 min, L1 2 min, one 10-minute live trial run (new PAGE_DIR) | 0 | 0 | **Owner yes to schema v2 (§1)** before any edit |
| 3 | Under 30 min (replay the 2,736 texts offline for keys) | 0 | 0 | None (inside the v2 yes) |
| 4 | Two rounds of under 10 min each (embedding T28 + fresh2 takes 48 s, c2) | 0 | 0 | None. Stop rule: two flat rounds (under +0.5 point) |
| 5 | Client side; `ledger_split.py` under 5 min | 0 | 0 | R7 panel wording (L2707) is a placeholder quoting the owner's words until approved; Q4 promotion stays open (no `ours:` promotion); **dated events list download needs a yes** (M3) |
| 6 | Pilot: 500 hosted calls; rounds: TF-IDF training under 3 min | **Pilot about 0.03 to 0.08 USD (printed before the run); needs the owner's yes and which cap applies (2.5 or 10 USD)**; each later round states its cost first | 0 | Stop rule: pilot L1 <= 0.561 |
| 7 (not in this spec) | | | | Wikidata request for names (larger than the pending 1,307-ID one) needs a yes; until then `journal.ids.names` are strings |

Also open: MAVEN scoring-only yes; CheckThat licence (CC BY-NC-SA, L810) unresolved, so Function stays as it is.

## 6. Rollback

| Step | Rollback | What survives |
|---|---|---|
| 2 | `git checkout` of the six files; schema back to v1; new runs write v1 again | Any v2 trace folder stays valid and verifiable (its lines carry their own version); the replay set was never touched |
| 3 | Stop writing `journal`; `verify_trace` accepts v2 lines without it when `run.version` is "live-trace-v2-nojournal" (one line) | Chains already written are immutable and still verify |
| 4 | Delete `specs/landing_calibration_v1.json`: the stage falls back to v0 (`decision EVIDENCE_ONLY, p null`), the decider field `topic_node` is not proposed; remove the field-table entry | Lean rules were never touched |
| 5 | Remove the `#s_ledger` div and `renderLedger`; delete `specs/iptc_condition_v0.json` | No server state |
| 6 | Labels live in `learn_queue.jsonl` with their version; a student is a pickle that nothing loads until registered (add-model skill end to end, memory rule) | Spend is sunk; the labels remain as a dated, versioned asset |

## 7. Build order, time, first action

| Order | Build | My estimate | Done when |
|---|---|---|---|
| 0 | Owner reads §1 and says yes or no to `live-trace-v2` | owner | A ledger decision line |
| 1 | While waiting: `team/build_spec/replay_landing.py` (R1) and `compare_stages.py` (R3) written and R1 run on the replay set (read-only; no repo change) | 1 h | R1 prediction scored |
| 2 | Step 2: pack_view, live_trace, live_gaps, schema, fixture, page, verify; U1 to U5, L1, R2, R3; one 10-minute live run in a new PAGE_DIR | 3 h | All U pass; R3 >= 99.5%; L1 scored |
| 3 | Step 3: journal.py, trace fields, run aggregates; U6; re-run R1 for keys | 2 h | Copies in the replay set = 6 (c1) found by the runner's index |
| 4 | Step 4 round 1: calibrator with vote features, damping, line, decider field; M1, A1, S1 | 2 h + 2 rounds under 10 min | Predictions scored; bars reported as they fall |
| 5 | Step 5: `iptc_condition_v0.json`, panel, `ledger_split.py`; M4 | 3 h | Panel shows the 26 resources with states; split-half numbers on the page |
| 6 | Step 6: pilot dry-run (cost line), owner yes, pilot, then round 1 if the stop rule allows | 1 h + rounds | P1, P2 scored |

First concrete action: hand §1 of this file to the owner as the stage-contract report (the schema demands it), and in the same hour write and run `team/build_spec/replay_landing.py` over `trace-demo/a/*.json` with the R1 prediction on the ledger: no repo change, no gate.

## 8. What this spec does not do

No single best landing as the topic answer (decision object + p instead); no cosine margin as confidence (c2: raw cosine 0.604 at half coverage); no student trained on landing labels as a second opinion; no Wikidata aliases on cards; no merging of trees or writes to `medtop.json`; no WordNet domains as topics; no human raters; no new page; no two embedding jobs at once; no judging against legacy except where labelled reference (`TOPIC_DISAGREE`, the publisher-section map, `iptc_condition_v0` derivation).

## 9. My two checks (scripts and JSON in `team/build_spec/`)

| Check | Prediction (in the header) | Result | Verdict | Consequence in this spec |
|---|---|---|---|---|
| c1 syndication census on the replay set (`c1_dedup_census.py`, 0.9 s) | Copies across sources 2 to 5%; same text 1%; republished 1 to 3%; prefix adds 1 to 2 points | Copies 6 of 2,736 (0.22%); same text_sha1 0; republished 7; prefix alone 1; title alone 5; title hits column names ("business daily", "tech life", "what in the world") | Copies MISSED high (far fewer); republished MISSED low; generic-title problem not predicted | Dedup is a correctness guard, not a big count effect, on this stream; the key rule gains `generic_title` (§2.3); independent counts matter more on the 41k-item queue (168 titles across sources, 341 rows, my own read-only count) |
| c2 calibrated abstain (`c2_calibration.py`, 48 s encode; fit T28, score fresh2) | AUROC 0.70 to 0.78; accuracy at coverage 0.50 0.68 to 0.75 (FAIL 0.80); at 0.25 0.75 to 0.82; raw cosine at 0.50 0.60 to 0.65; damping within +-0.01 | AUROC 0.741; 0.735 at 0.50; 0.763 at 0.25; raw 0.604; damping +0.009 (0.562 to 0.571); coverage at the 0.80 bar 0.138; calibration is honest (p 0.7 to 0.8 bin: observed 0.789) | All five HIT | Step 4 cannot reach the safe-abstain bar from internal features; the line is set where accuracy holds 0.80 (p 0.70, 14% coverage) and the spec says so; the vote features are the one unmeasured internal lever (A1 prediction); the bar's real lever is the teacher (step 6) |

## 10. MM3 (hosted Jev through the mm3 tool; it saw only our code lines and this spec's design, never article text; the task allowed these calls)

Procedure: `mm3 agent`, `agent probe`, `agent loop`, `agent class`, `agent delegate`, `agent verdict` read first; `template loop` and `template class` edited, dry-run, then run. Three Haiku helpers `[H1]` ran one request each under the delegate card; every id below was checked with `mm3 view` (all six exist, dated 2026-11-20, state open). Budget after the runs: 4.998 USD of 5.00 left (MM3-0695 notes).

| Run | Who | Verb, subject | Gate, consensus | What it said | What changed in this spec |
|---|---|---|---|---|---|
| MM3-0695 | me | `loop` on the five steps, two stories each (file `team/build_spec/mm3_loop_steps.yaml`) | fail; goal unsure p 0.53; every story routes `none-fits` at p 0.56 to 0.68; `not-attached-path` risk-level critical p 0.72; silent-failure probe (Q8) 0.66 to 0.77 on all 10 stories | Loop reads no files, so the "does the story name the fields" answers (p 0.25 to 0.39) measure the question wording, not the spec: weak evidence, reported as such. Two signals are real: an hour-long trace without its main head is critical, and nothing in the design said how a stale value is caught | §2.1 refused-to-start row (fail-fast default, `ALLOW_NO_LANDING=1` opt-in); §2.6 stale-values row (`as_of` on every derived object, page wording) |
| MM3-0691 | helper A | `class` on `live_trace.py:32-55, 75-84, 154-197` against §1.1 to 1.3 | fail; split; escalate. correctness pass (exception escape 0.14; `ctx["ff"]` read without `need` 0.23; dangling `l1_guess` reader 0.28); design fail (pack() picks L1 itself 0.94: the thing the change removes); design-risk fail (Landing raise kills `Chain.__init__` 0.88: the thing the change wraps; sixth decider field unsure 0.42); route build-as-specified 0.91; scope missing 0.75 | The code as it stands fails the goal for exactly the two reasons the change exists; the unsettled points were the `out` cap's enforcer and the decider loop's acceptance of a sixth field | §1.1 title: cap is 700 characters enforced by `run()` line 81, U7 added; §3 step 4 row: field-table entry required, same Lean path as `topic`, U8 added; §3 step 2 rows: `pack()` takes L1 from `ctx["l1_code"]` only, `self.landing = None` on failure |
| MM3-0690 | helper B | `class` on `pack_view.py:97-128, 8-11` (+ `structure_pack.py:9-42`) against the §1.1 Landing changes | fail; split; escalate. correctness fail (card order from unordered iteration 0.82; no 2000-character cap 0.02; `node()` KeyError 0.08); design fail (loads bge itself 0.96; per-call `max_seq_length` affects other callers 0.59; hard to test without bge 0.81); design-risk unsure (retired node returned 0.20; `emb=None` breaks line 131 0.26; `cards_sha` differs across runs 0.61); route build-as-specified 0.71; scope partial 0.42 | Card order and encoder sharing were unpinned | §1.1 note: cards in sorted qcode order, `cards_sha` over that order (U9 added); `Chain.bge` owned by the landing at 256, no per-call switching; retired filter stated |
| MM3-0692, 0693, 0694 | helper C | `loop` on the §2.6 degraded paths (8 parts, 20 stories, split in three runs because quick depth caps a layer at 10 items) | all fail; goal unsure p 0.36 / 0.44 / 0.40; silent-failure probe 0.54 to 0.71 the strongest flag; owner probe 0.07 to 0.15 everywhere | Same caveat as MM3-0695 (no file evidence). Helper C's own reading: blank cells in the Empty landing and Duplicate rows; the backlog row should state the allowlist; IPTC release and drift_stop both fire on the code hash, say which wins | §2.6: both rows filled; allowlist named in the backlog row; IPTC-release row says the drift path wins and what the banner names |

Splits recorded, not resolved: MM3-0690 and MM3-0691 are split verdicts with `escalate: true`; their route answers (build-as-specified 0.71 and 0.91) are not read as clean passes because the scope probes said partial and missing. The drills MM3 proposed (`drill --parent MM3-0691 --from design`, `--parent MM3-0690 --from correctness`) were not run: the flagged items are the planned changes themselves, and the spec now pins the two unpinned points. Not covered by MM3: step 5's `iptc_condition_v0.json` derivation and step 6's teacher wiring (no code exists yet; a `class` run belongs to the build, after the owner's yes).
