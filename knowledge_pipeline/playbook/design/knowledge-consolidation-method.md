# Knowledge consolidation and navigation method

Status: research draft, 2026-11-23. PROVISIONAL like the data it reads. No pipeline code, page, gate or service was touched; no hosted call; no browser.
Inputs: the two bundles in `playbook/design/entity-flow/` (`sample-c1.json` = Fiona the hippo, 34 articles; `sample-mix.json` = Gulf strikes + energy, 40 articles), `entity-model.md`, the ladder review (`scratchpad/ladder/ladder-review.md`), `concept-delta-design.md`, playbook 00 section 10, and the external "Knowledge Navigator" prototype (read as data only, used as an example, not copied).
Every number below comes from a script in `SCR = /tmp/claude-0/-workspace/3ed8559b-0aa2-49c4-a429-a0452a913be2/scratchpad/consolidation/` and the output file named next to it. "Reader reading" = my own reading of article titles, used only to score purity; it is not independent ground truth (no human raters; this is one reader on two areas).

Terms (once): **article** = one news item. **Claim** = one pipeline fact (subject-predicate-object plus the sentences and owners behind it; the bundles call it `facts[]`). **Owner** = the company behind a publisher. **Corroborated** = claim backed by 2 or more independent owners. **Cast** = the named entities (country, person, organisation, place) a group of claims is about. **Development** = defined in section 1.

---

## 1. The method in one screen

**Levels (top to bottom).** The new unit is the development; the old unit (the entity card) moves beside it as a lens.

| Level | What it is | Size on c1 / mix | Collapses what |
|---|---|---|---|
| 0 Area | the staged query and window | 1 / 1 | nothing |
| **1 Development** | a group of articles about one event or storyline, plus the claims they carry | 5 / 5 (3 / 4 shown, rest "thin") | 34 / 40 articles into 5 / 5 (6.8x / 8.0x) |
| 2 Phase (optional) | the same grouping cut finer inside a development | 10 / 12 | steps of one storyline (care, then death) |
| 3 Claim | one joined fact with owners count and certainty word | 562 / 753 | repeated sentences into a support count; copies into one owner |
| 4 Evidence | the quoted sentence, owner, day, read depth, article link | 752 / 841 rows | nothing (always kept) |
| beside: Cast | entities and concepts as who/where chips, one page per entity | 35 / 45 cards | they are lenses on developments, never the unit |
| inside: Ladder | KNOW / FOLLOW / EXPECT is the layout of a development page | n/a | keeps the three-rung ladder, moves it down one level |

**What collapses.** Articles about the same event (one development). Repeated sentences and syndicated copies (a support count, one owner). Several contest pairs about one dispute (6 pairs, 7 sides, one Iran claim: one dispute). Developments with nothing new since the last look (one line, no detail).
**What expands.** A development that, since the last look, has (a) a new claim backed by 2 or more owners, (b) a new contest, (c) a new forward statement, (d) a new phase, or (e) a changed certainty word. Everything else stays one line.
**Navigation path.** Area strip (counts, "N developments moved since you last looked") -> list of 3 to 5 developments sorted by what moved, then recency -> development page (headline, certainty word, since-last-look delta, KNOW, FOLLOW, EXPECT, cast chips) -> claim -> evidence sentence -> article.
**No model text.** Every title is a quoted headline; every summary is a quoted sentence; causes and impacts are only shown when a source sentence states them, else "unassessed".

---

## 2. Formal definitions

### 2.1 Development (level 1)

| Part | Definition |
|---|---|
| Entity | a set of articles `M` (members) plus the on-story claims they carry |
| Rule (D3) | average-link agglomerative clustering of articles. `sim(i,j) = ((cos_title + cos_evidence_text)/2 + 0.5 * cos_cast) * exp(-gap_hours / 96)`; merge while `sim >= 0.04`. `cos_title`: TF-IDF on `articles[].title`. `cos_evidence_text`: TF-IDF on the article's own `facts[].evidence[].sentence`. `cos_cast`: IDF-weighted vector of typed fact endpoints (`iso:`, `person:`, `org:`, `place:`, `facility:`, `event:`, `product:`, `other:`, `substance:`) of claims with evidence in the article. Tokens or entities present in more than 40% of articles are dropped (hub rule). `gap_hours` from `articles[].published`. Code: `SCR/devbuild.py`, `SCR/grid.py`. |
| Qualifies as a development | 2 or more articles and at least 1 full read (`read_depth = full`). Otherwise it is **thin**: listed under "unplaced", not shown as a development. |
| On-story claim | a claim with an evidence sentence, from a member article, that shares 2 or more content words (3+ letters, not generic) with the union of member titles. A lexical proxy; known to leak (section 6). |
| Title | the member headline with the highest average title similarity to the others (the medoid). A quoted headline. |
| Best-supported quote | among on-story claims whose predicate is not `be`/`have`, the evidence sentence of the claim with most owners, then most member articles, then shortest; clean sentences only (35 to 260 characters, no markdown run-on). A second slot "latest corroborated quote" uses the same rule on claims first seen after the last look. |
| Certainty word | pipeline words reused at development level: owners of member articles 1 = single source, 2 = reported, 3+ = established; "disputed" when a contest pair touches a member article. Owners count, never article count. |
| Display fields | title, dates, article count, owner count, certainty word, quote(s), cast chips (top 6 named entities), counts of on-story claims and corroborated claims, teaser share, contests, since-last-look delta |
| Empty / uncertain | no clean quote -> show the headline only. No corroborated claim -> say "single source". All members teaser -> "thin, headline-level only". No contest -> "no dispute read" (not "no dispute"). Cast empty -> hide chips. |
| Identity | `dev:` + sha1 of the earliest member article id (first 10 hex). Not stable across windows (section 6). |

### 2.2 Phase (level 2)

Same rule, cut at `sim >= 0.08` (nested inside the development because average-link merges are monotone). Shown only inside a development page as the "steps" list. Same qualify and empty rules.

### 2.3 Claim (level 3) and evidence (level 4)

| Part | Definition |
|---|---|
| Claim | `facts[]` row (id, subject, predicate, object, `independent_owners`, `collapsed_copies`, `evidence[]`, `first_day`, `days`, `in_contest`) |
| Display | one line: the best evidence sentence, owners count, certainty word, first and last day |
| Collapse | repeats are a support count (`independent_owners`, `evidence` length); copies are already folded by the pipeline (`collapsed_copies`) |
| Evidence | `evidence[]`: sentence, `publisher` (owner via `publishers[]`), `day`, `article_id`, article `read_depth` and `url` |
| Empty / uncertain | teaser-only evidence is labelled "teaser read"; a claim with one owner is "single source" even when many articles repeat it |

### 2.4 Change since last look (a delta, not a level)

`K` = the last article seen (a cut on `seq` or a day boundary on `published`). For a development: `before` = members with `seq <= K`, `after` = members with `seq > K`.

| Delta item | Rule | Source fields |
|---|---|---|
| new articles | count of `after` members | `articles[].seq` |
| new claims | on-story claims whose earliest evidence article has `seq > K` | `facts[].evidence[].article_id` |
| new and corroborated | new claims with `independent_owners >= 2` now | `facts[].independent_owners` |
| reinforced | claims with 1 owner at `K` and 2 or more now (owners recomputed from evidence up to `K`) | `evidence[].publisher`, `publishers[].owner` |
| new contest | contest pair whose later side first appears after `K` | `contests[].sides[].edge_id`, evidence |
| new forward statement | on-story evidence sentence matching will/would/could/may/expected to/warn/threaten/plan, first seen after `K` | `evidence[].sentence` (regex, unattributed) |
| phase word change | predicate family by `first_day` (for example `undergo` then `die`) | `facts[].predicate`, `first_day` |

### 2.5 Priority and relevance (computable proxies, named honestly)

| Proxy | Rule | Not claimed |
|---|---|---|
| **new and corroborated or contested** (stands in for "material") | `after` members exist and (a new claim has 2 or more owners now, or a contest first appears after `K`) | it is not importance; it says "new and more than one owner backs it" |
| **new, single-source** (stands in for "watch") | `after` members exist with new claims, none corroborated | new is not important; one owner is not confirmed |
| **no new article** (stands in for "background") | no member after `K` | not "unimportant" |
| **direct** to a focus entity | focus is a typed endpoint of an on-story claim and its name is in a member headline | |
| **connected** | focus is an endpoint of an on-story claim, not in any headline (or the reverse) | |
| **context** | neither | |

Rule from the prototype kept as a gate: new does not equal material; many articles do not equal many owners; co-occurrence is not cause.

---

## 3. Measurements

### 3.1 Which fields carry the "same story" signal (pair test)

`SCR/signals.py` -> `signals.out`. Area under the curve (AUC; 0.5 = no signal, 1.0 = perfect) for telling two articles of the same reader-labelled thread from two of different threads.

| Signal | c1 | mix |
|---|---|---|
| named fact endpoints (cast) | 0.541 | 0.622 |
| all fact endpoints | 0.537 | 0.712 |
| headline words | 0.663 | 0.757 |
| evidence-sentence words | 0.571 | 0.740 |
| headline + sentences, time-decayed (tau 96 h) | 0.671 | 0.809 |

Reading: entity cast alone (today's organising field) is the weakest signal; 74.7% / 70.3% of claims are anchored on a generic `concept:` id, 93.2% / 94.7% of claims have one owner (`m3_sameness.out`). Headlines and sentences carry the thread. The reader labels for c1 are coarse (care and death are one thread, `SCR/gold.py`).

### 3.2 Development build: three rules compared

`SCR/analysis.py` -> `analysis_levels.out/.json`. "Placed" = on-story claims in groups of 2 or more articles, share of all claims. Purity = share of articles whose group's majority reader-thread matches theirs.

| Area | Rule | Groups (of 2+ articles) | Articles per group | Articles in 2+ groups | Claims placed | Purity | Pair precision / recall |
|---|---|---|---|---|---|---|---|
| c1 | R1 shared joined claim (union) | 4 (1) | 8.5 | 91.2% | 71.0% | 0.765 | 0.572 / 0.896 |
| c1 | R2 named-cast cosine | 16 (5) | 2.1 | 67.6% | 43.8% | 0.882 | 0.768 / 0.145 |
| c1 | **R3 title+text+cast+time (chosen)** | **5 (3)** | **6.8** | **94.1%** | **59.4%** | **0.912** | **0.792 / 0.882** |
| c1 | R3 fine cut (phases) | 10 (5) | 3.4 | 85.3% | 48.0% | 0.912 | 0.757 / 0.273 |
| mix | R1 | 10 (3) | 4.0 | 82.5% | 79.5% | 0.825 | 0.586 / 0.773 |
| mix | R2 | 18 (7) | 2.2 | 72.5% | 64.3% | 0.925 | 0.866 / 0.227 |
| mix | **R3 (chosen)** | **5 (5)** | **8.0** | **100%** | **78.0%** | **0.850** | **0.828 / 0.604** |
| mix | R3 fine cut (phases) | 12 (8) | 3.3 | 90.0% | 67.2% | 0.950 | 0.955 / 0.329 |

- R1 (join only) chains: one group of 31 of 34 (c1) and 26 of 40 (mix), because only 112 / 66 claims are seen in 2 or more articles. Joins are too sparse to define a thread and too chained to separate one.
- R2 (entity-first) leaves 11 of 16 / 11 of 18 groups as single articles.
- Parameters came from a 30-setting sweep (`SCR/grid.py` -> `grid.out`) scored on these same two areas against my own reading: the choice is in-sample. Looser cut (thr 0.03) gives 4 / 4 groups with purity 0.824 / 0.850; tighter gives more singletons.
- With the qualify rule (2+ articles and 1+ full read): c1 3 developments hold 32 of 34 articles (purity 0.906, claims placed 59.4%); mix 4 developments hold 35 of 40 (purity 0.914, claims placed 76.8%) (`final_extra.out`).

### 3.3 The developments, with purity read by hand

`SCR/analysis2.py` -> `analysis2.out`. "Quote" = best-supported quoted sentence.

**c1, Fiona** (0 of 3 developments mix unrelated stories; D0 holds 3 stragglers)

| Development | Articles / owners / days | Headline (medoid) | Quote | Purity by reading |
|---|---|---|---|---|
| D0 | 26 / 13 / Nov 18 to 20 | "Cincinnati Zoo's famed Fiona the hippo dies days after eating a visitor's hat" | "The zoo said Monday that Fiona was undergoing care around the clock after swallowing the hat more than a week ago." Boston.com, Nov 19, 4 owners, 8 articles | one story (care -> death), with 3 aftermath stragglers (seq 25 Harambe retrospective, 27 mourning, 32 "could anyone face charges") |
| D1 | 3 / 3 / Nov 20 to 21 | "Fiona the hippo's death gives parents a chance to teach kids about grief" | "Remembering Fiona through drawings, photographs, favorite videos or stories about her life can also provide comfort..." Straits Times, 1 owner | pure (aftermath: grief, photos, blame) |
| D2 | 3 / 2 / Nov 20 | "Exam shows that hat Fiona the hippo ate was deep into her small intestine" | "The hat Fiona ate ... was so far into her digestive system that no supportive care could have saved her, the zoo said in a statement." Boston Globe, 4 owners | pure (necropsy: the stated cause) |
| thin | 1 + 1 (both teaser) | MassLive "Zoo uses unusual tool..."; Wired "How does a hat kill a hippo?" | none corroborated | unplaced |

**mix, Gulf strikes + energy** (1 of 4 developments mixes unrelated stories; one more thin group is a grab-bag)

| Development | Articles / owners / days | Headline (medoid) | Quote | Purity by reading |
|---|---|---|---|---|
| D0 Saudi vs Houthis | 15 / 5 / Nov 18 to 21 | "Saudi Arabia says it intercepts three Houthi missiles targeting Riyadh" | "The attacks are the latest in weeks of strikes by the Yemeni armed group targeting Saudi military, civilian and oil infrastructure." Al Jazeera, Nov 18, 2 owners, 4 articles | pure, 15 of 15 |
| D1 Iran strikes Nov 18 | 11 / 8 / Nov 18 to 19, **disputed** (6 contest pairs) | "Gulf nations on alert after U.S. strikes Iranian island" | "U.S. fighter jets struck an Islamic Revolutionary Guard Corps missile launch site on Qeshm Island, according to an American official." Japan Times, 3 owners. Dispute: Iran "it hit US-linked military targets in Kuwait and Bahrain" vs Kuwait "did not report any damage" | **mixed**: 8 articles on the strikes + 3 on the IEA "largest threat to energy security" story (seq 22, 23, 29). The phase cut separates them |
| D2 UK energy bills | 5 / 2 / Nov 18 | "Typical energy bill forecast to go up by 443 pounds a year from January as inflation rate rises again" | Bank of England spokesperson: "The conflict in the Middle East has caused energy prices and inflation to rise in recent months..." Guardian Business, 2 owners | pure |
| D4 Saudi war outlook | 4 / 3 / Nov 18 to 21 | "Saudi Arabia preparing for war against Yemen's Houthis to last well into 2027" | "Saudis preparing for Yemen campaign to last well into 2027." Japan Times | same war as D0, different phase (preparing vs Houthis target Riyadh); split of one story |
| D3 thin | 5, all teaser, 12 claims | Al Jazeera "Iran war live" blogs, IEA chief, Hormuz shipping | one headline only | **grab-bag**, correctly held back by the qualify rule |

Answers to the owner's test cases (mix): Iran strikes Nov 18 disputed = D1 (found, with IEA articles attached). Hormuz = no development of its own: the two Hormuz-shipping articles (seq 18, 26) fall in the thin group and the IEA articles in D1. Houthi threat to Shuqaiq = not a development; it is a change inside D0 (forward statements at seq 32 and 34, delta 3 below). The phase cut keeps the Shuqaiq articles (32, 34, 37, 38) inside a 9-article "coalition vs Houthis" phase, so it is not isolated at either cut. Gulf collapses to 4 sensible groups holding 35 of 40 articles, with one impure and one split. c1 collapses to care -> death in one development (D0) plus necropsy and aftermath.

### 3.4 Hierarchy comparison (question 1)

`SCR/analysis.py`, `analysis3.py` -> `analysis3.out`. Gold = reader threads (c1: 3, mix: 4; section 3.2).

| Hierarchy | Top-level items to scan c1 / mix | Mixing of threads inside a top-level item | Repeats collapsed | Verdict |
|---|---|---|---|---|
| Article-first (feed) | 34 / 40 | none (but nothing grouped) | none | no consolidation |
| Claim-first | 562 / 753 | n/a | 1.09 and 1.08 raw items per claim; 19.9% / 8.8% of claims seen in 2+ articles | too many, too little joined |
| **Entity-first (old street map)** | 35 / 45 cards (21 / 23 with 3+ articles) | 17 of 21 cards (81%) / 10 of 23 (43%) touch 2+ reader threads; share of the card's articles in its top thread 0.715 / 0.815 (weighted); worst card `iso:IR`: 21 articles over 5 threads, top share 0.38 | claims on 2+ cards: 13 (2.3%) / 47 (6.2%) | hubs mix stories; 35 to 45 items |
| **Development-first (prototype)** | 5 / 5 (3 / 4 qualify) | article purity 0.912 / 0.850 | 6.8x / 8.0x | best on every column; needs a build rule and a thin state |
| Ladder-on-development (chosen) | same as development-first | same | same, plus KNOW/FOLLOW/EXPECT inside | the ladder survives as the page layout, one level down |

Coverage is not the entity-first problem (one hub card covers 80% of a thread: `analysis_levels.out`, `cards_for_80pct`). Mixing and count are. A single thread is reached through 1 to 3 developments (Saudi-Houthi war: 21 articles over 3 developments, 2 for 80%).

**Chosen hierarchy:** Area -> Development -> (Phase) -> Claim -> Evidence, with Cast as a lens and the Ladder as the development page layout. Reasons: it collapses the most (6.8x / 8.0x vs none), it mixes threads least (0.912 / 0.850 vs 0.715 / 0.815 for cards), and it does not depend on the weakest field (entity typing: 420 of 562 c1 claims are anchored on a generic concept id).

### 3.5 Compression of sameness (question 3)

`SCR/m3_sameness.py` -> `m3_sameness.out`; sentences in `analysis3.out`.

| Measure | c1 | mix |
|---|---|---|
| raw claims -> joined claims | 615 -> 562 (merge rate 8.6%) | 811 -> 753 (7.2%) |
| evidence rows per claim | 1.34 | 1.12 |
| claims with 1 owner | 524 of 562 (93.2%) | 713 of 753 (94.7%) |
| claims seen in 2+ articles | 112 (19.9%) | 66 (8.8%) |
| syndicated copies already folded | 111 copies in 79 claims | 19 copies in 18 claims |
| article-claim links that repeat an earlier article's claim | 187 of 749 (25.0%) | 79 of 832 (9.5%) |
| articles adding no first-seen claim | 1 of 34 | 1 of 40 |
| headline near-duplicates (word overlap 0.6+) | 9 pairs | 1 pair |
| distinct on-story sentences -> sentence clusters (overlap 0.6+) | 243 -> 204 (1.19x), 21 clusters with 2+ owners | 330 -> 313 (1.05x), 11 clusters with 2+ owners |
| articles -> developments | 34 -> 5 (6.8x) | 40 -> 5 (8.0x) |
| contest pairs -> disputes | 0 | 6 pairs, 7 sides, one Iran claim used in 5 pairs: 1 dispute |
| triage: plain updates | 29 of 34 | 32 of 40 (change_kind) |

Reading: sameness at claim and sentence level is small (1.05x to 1.19x); the real repetition is the same event told in different words, and it collapses only at the development level. Claim-level novelty is overstated: 15 of 16 c1 articles after the day cut and all 9 mix articles carry at least one "first-seen" claim, so "has a new claim" alone cannot mean "adds something". Repeats collapse to a support count only where the pipeline joined them (7% of claims). `story_kind` is `republished` on all 34 / 40 articles in the bundles although `entity-model.md` lists first 23 / republished 8 / copy 3 for c1: a documentation mismatch, not used here.

### 3.6 Change and new: three real before -> after deltas (question 4)

`SCR/deltas.py` -> `deltas.out`. Last look = end of 2026-11-19 UTC (c1 after seq 17, mix after seq 30), fixed before measuring; delta 2 uses an article cut.

| Delta | Before | After | Source |
|---|---|---|---|
| 1. c1 D0 Fiona: status care -> died | 17 articles, 9 owners; claims with predicate `undergo` first appear Nov 18 (4) and Nov 19 (3); best quote "undergoing care around the clock" | 9 more articles (all 9 headlines carry a death word), 13 owners now; predicate `die` first appears Nov 19 (3) and Nov 20 (4); 87 new on-story claims, 9 reinforced from 1 owner to 2+; latest corroborated quote "has died aged nine after swallowing a visitor's knit hat" (Times of India, 3 owners) | `facts[].predicate`, `first_day`, evidence |
| 2. mix D1 Iran-US: dispute appears | after article 0 (Straits Times): 1 contest pair (Iran "hit" vs Bahrain "intercepted") in the same article | by article 8 (BBC World, triage verdict `conflict`) 4 more pairs (Kuwait, Bahrain denials), by article 13 the last; dev certainty word `disputed`, 8 owners | `contests[]`, `changes[].verdict` |
| 3. mix D0 Saudi vs Houthis: threats escalate | 9 articles; 6 forward-statement sentences | 6 more articles; 12 forward statements (airlines told to avoid Saudi airspace, Red Sea ports as "targets", "would target a power station at Shuqaiq", Straits Times seq 34); 83 new on-story claims, 8 corroborated (for example Public Investment Fund tower damaged, 2 owners); 7 reinforced | `evidence[].sentence`, `independent_owners` |

Limits: c1 seq 4 (NBC Boston, published Nov 19 04:55) already says "has died" while 6 later articles still say "care", so article timestamps and titles can disagree (a republish or updated page); the `undergo` then `die` ordering by claim `first_day` is consistent. The pipeline's own contest rule found 0 pairs in c1 although the status reversal exists (`entity-model.md`); the reversal is visible only through predicates and headlines.

### 3.7 Meaning, evidence, direction and the rest (question 5)

`SCR/analysis3.py` -> `analysis3.out` (`dim`), `resources.out`. Counts are developments (c1 5 / mix 5 at the default cut).

| Dimension | Field that supports it | Coverage c1 / mix | Show when absent |
|---|---|---|---|
| Meaning (what happened) | medoid headline + best quoted sentence | quote on 4 of 5 / 5 of 5 | headline only |
| Evidence strength | `independent_owners`, `evidence[]`, article `read_depth` | corroborated claim on 2 of 5 / 5 of 5; teaser-only developments 2 / 1; teaser share of articles 38.2% / 42.5% | "single source", "teaser read" |
| Disagreement | `contests[]` (`sides[].quote`, `speakers`) | 0 of 5 / 1 of 5 (one event) | "no dispute read" |
| Time and steps (FOLLOW) | `first_day`, `days`, `timeline[]` | claims on 2+ days: 3 of 5 / 4 of 5 | "one day only" |
| Forward statement (EXPECT) | evidence sentence regex, unattributed | 3 of 5 / 5 of 5 | "no forward statement read"; speaker attribution is PARTIAL (only contest sides carry speakers) |
| Stated cause | evidence sentence with because/due to/in response to/caused/led to (regex) | 2 of 5 / 4 of 5 | "cause unassessed" |
| Direction (up/down) | `entities[].direction`, `links[].direction` | 1 entity, 0 links per area | "direction unassessed" |
| Impact on resources | `articles[].resource_events` | 0 events in both bundles (`entity-model.md` says 48 / 384; not reproduced) | "impact unassessed" |
| Data quality of the read | `articles[].gaps`, `decider` abstains, `read_reason` | on every article | show teaser share |

Priority and relevance (proxies of 2.5), `phases.out`:

| Count | c1 dev (5) | c1 phase (10) | mix dev (5) | mix phase (12) |
|---|---|---|---|---|
| new and corroborated or contested | 2 | 2 | 2 | 2 |
| new, single-source | 2 | 5 | 1 | 2 |
| no new article | 1 | 3 | 2 | 8 |
| certainty word: established / reported / single source / disputed | 2 / 1 / 2 / 0 | 3 / 2 / 5 / 0 | 3 / 1 / 0 / 1 | 1 / 5 / 5 / 1 |

Relevance, focus `iso:SA` (mix dev): direct 3, connected 1, context 1; focus `iso:IR`: direct 2, connected 2, context 1; focus `iso:GB`: direct 1, context 4. c1 focus `person:fiona`: direct 3, connected 1, context 1. With 5 developments per area these distributions are tiny; they show the proxies can be computed, not that they are calibrated.

### 3.8 Lanes (question 6)

`SCR/analysis3.py` -> `analysis3.out` (`lanes`). Normalised mutual information (NMI; 0 = unrelated, 1 = identical) between a candidate lane label and the reader threads; "inside" = share of a development's articles that carry its most common lane value.

| Candidate lane field | Distinct values c1 / mix | NMI c1 / mix | Consistent inside developments c1 / mix | Coverage |
|---|---|---|---|---|
| IPTC level 1 (`iptc_l1`) | 3 / 3 | 0.117 / 0.344 | 0.941 / 0.675 | 100% |
| IPTC node (`iptc_node_label`) | 6 / 12 | 0.143 / 0.518 | 0.559 / 0.450 | 100% |
| classifier area head (`area_top`[0]) | 6 / 3 | 0.429 / 0.509 | 0.882 / 0.875 | 100% |
| place head (`place_top`[0]) | 3 / 2 | 0.165 / 0.449 | 0.853 / 1.000 | 100% |
| dominant country in the article's claims | 4 / 6 | 0.165 / 0.698 | 0.735 / 0.700 | 32.4% / 92.5% |
| our developments (reference) | 5 / 5 | 0.645 / 0.726 | 1.0 / 1.0 | 100% |

c1: the area head says `culture_leisure` for 29 of 34 articles, IPTC splits one Fiona development into "human mishap" 14 and "celebrity" 9. mix: the area head separates war (32 of 40) from inflation and energy; IPTC labels give 12 values for 40 articles. **Recommendation: reject lanes as a structural level.** A lane would hold 1 development in c1 and 1 to 3 in mix; no field beats the developments themselves. Keep the area head as an optional filter chip (consistent inside developments, 0.875 to 0.882) and the dominant-country field only where it exists. Lanes become worth testing when one view holds several areas (not testable with 2 areas).

### 3.9 Where the ladder and the old page sections go (question 7)

| Old part | New place | Evidence |
|---|---|---|
| Status / capability view | Area strip: counts of developments by proxy tier, teaser share, thin count | per-area `meta.counters`, 3.7 |
| "Since you were last here" | the delta of 2.4, computed per development; unchanged developments collapse to one line | 3.6 |
| Street map (concepts + typed links) | **Cast** lens: one page per entity, listing the developments it appears in; links shown with their basis (`related`, `opposes`; `affects_resource` is co-occurrence) | 3.4: cards mix threads, so cards cannot be the top level |
| Go deep | claim and evidence levels, plus the entity timeline and `deep` fields already measured as usable | ladder review 1.7 |
| KNOW / FOLLOW / EXPECT | development page layout. KNOW = headline, cast, best quote, certainty word. FOLLOW = steps by day (phases, `first_day`), disputes before storylines. EXPECT = forward statements with the speaker when read, "none read" otherwise | 3.7: FOLLOW 3 of 5 / 4 of 5; EXPECT regex 3 / 5 |

Cross-development relations: 6 of 10 mix pairs (and 3 of 10 c1 pairs) share 2 or more named actors (`projection.out`), driven by hub actors (Iran, Saudi Arabia); only `shares_actor` and `precedes` (by time) are derivable; any causal relation is MISSING.

---

## 4. Supported now, PARTIAL, MISSING

| Item | Status | Basis | Cheapest path |
|---|---|---|---|
| Development grouping (article level) | **Supported** | 3.2: purity 0.912 / 0.850, 6.8x / 8.0x | none; add the thin state |
| Claims placed on a development | **PARTIAL** | 59.4% / 78.0% on-story by lexical proxy; articles carry off-story claims (c1 seq 4: 20 sentences, 4 pass the filter, 3 of them about Pete Rose; `checks.out`) | a sentence-to-development relevance check (rule-based on cast overlap first) |
| Phase split (care vs death) | **PARTIAL** | the two large c1 phases at thr 0.08 (11 and 10 articles) both mix care and death headlines (`phases_members.out`); predicate family by day works (`undergo` -> `die`) | a status-predicate list (`die`, `undergo`, `recover`) read from `facts[].predicate` |
| Certainty word per development | Supported | owners of member articles | none |
| Since-last-look delta | Supported with a cut | 3.6 | store `K` per viewer |
| Corroborated or contested "new" tier | Supported | 2.5, 3.7 | none |
| Stable development id across windows | **MISSING** | id is a hash of the earliest member; a new earlier article changes it | match new groups to old by member overlap (above 50%) and keep the old id |
| Meaning text beyond a quote | MISSING by design | no model text allowed | none; show the quote |
| Cause and impact path | **MISSING** | stated cause sentences exist for 2 of 5 / 4 of 5 developments by regex, unattributed, often mis-anchored (ladder review 1.4) | an attributed cause rule: causal marker + speaker + both endpoints in cast |
| Forward statement with speaker | **PARTIAL** | speakers exist only on contest sides; claims v1 attributes are not on fragments (`entity-model.md`) | attach claims-v1 `said_by` to evidence rows |
| Direction (up/down) | MISSING | 1 entity, 0 links | none soon; show "unassessed" |
| Resource impact | MISSING in the bundles | 0 resource events exported | re-export with world events, or drop |
| Lanes | Rejected (3.8) | NMI below developments | none |
| Priority "material / watch / background" | **PARTIAL** | proxies only | calibrate with a decision-maker test on real readers (owner rule: no human labels for truth; use as UX test only) |
| Processing timestamp | MISSING | only `published` | add `seen_at` when an article enters the window |
| Teaser handling | Supported | teaser share per development | none |

---

## 5. The "development" projection (JSON)

Prototype field names are reused where they fit (`id`, `lane`, `title`, `priority`, `relevance`, `document_cluster_count`, `delta`, `summary`, `meaning`, `impact_hypothesis`, `uncertainty`, `related_development_ids`, `evidence`). Real instance for mix D0 in `SCR/projection-example.json`.

```json
{
  "id": "dev:35fd2a296e",
  "area": "mix",
  "lane": null,
  "title": "Saudi Arabia says it intercepts three Houthi missiles targeting Riyadh",
  "type": null,
  "priority_proxy": "new + corroborated/contested",
  "relevance": {"iso:SA": "direct"},
  "document_cluster_count": 15,
  "owner_count": 5,
  "certainty_word": "established",
  "delta": {"since": "end of 2026-11-19", "articles_before": 9, "articles_after": 6,
            "new_claims": 83, "new_claims_corroborated": 8, "reinforced": 7, "new_contests": []},
  "summary": "<best-supported quoted sentence>",
  "meaning": null,
  "impact_hypothesis": [],
  "uncertainty": {"teaser_articles": 3, "of": 15, "contests": [], "single_owner_claim_share": 0.886},
  "related_development_ids": [],
  "evidence": [{"quote": "...", "owner": "Al Jazeera", "published": "2026-11-18", "independent_owners": 2}]
}
```

| Projection field | Prototype field | Entity-flow source | Derivable? |
|---|---|---|---|
| `id` | `id` | sha1 of earliest member `articles[].id` | yes; unstable across windows |
| `area` | (none) | `meta.area` | yes |
| `lane` | `lane` | none | **no** (3.8); optional `articles[].area_top[0]` chip |
| `title` | `title` | medoid `articles[].title` | yes (quoted headline) |
| `type` | `type` | none | no (a type list would be invented) |
| `priority_proxy` | `priority` | `evidence[].article_id` + `seq`, `independent_owners`, `contests[]` | yes, as proxy only; prototype's "material" not claimed |
| `relevance` | `relevance` | typed fact endpoints vs focus + headlines | yes (needs a focus entity) |
| `document_cluster_count` | `document_cluster_count` | member count | yes (counts articles, not owners) |
| `owner_count`, `certainty_word` | (none) | `publishers[].owner`, member `publisher` | yes |
| `delta` | `delta.before/after` | `articles[].seq`, `facts[].evidence`, `contests[]`, `facts[].predicate` | yes, as counts and quoted lines; free-text before/after states are not generated |
| `summary` | `summary` | best `facts[].evidence[].sentence` | yes (quote) |
| `meaning` | `meaning` | none | **no** (no model text); null |
| `impact_hypothesis` | `impact_hypothesis` | none (`direction` null, `affects_resource` co-occurrence) | **no**; empty, "unassessed" |
| `uncertainty` | `uncertainty` (string) | `read_depth`, `contests[]`, `independent_owners`, `decider` | yes (as numbers; a string is built from templates) |
| `related_development_ids` | same | shared typed cast between developments | partial: `shares_actor` only |
| `evidence[]` | `evidence[]` | `facts[].evidence[]` + `publishers[]` + `articles[].url`, `read_depth` | yes |
| `relations[]` (typed, with status) | `relations[]` | none beyond `shares_actor` / `precedes` | partial; causal types MISSING |

---

## 6. Risks and honest limits

| Risk | Detail |
|---|---|
| Tiny sample, in-sample choice | two areas, 34 and 40 articles; parameters picked from a 30-setting sweep on the same areas; reader labels are one person's reading of titles. Purity numbers are indicative, not validated |
| Gold is coarse | c1 care and death are labelled one thread; under a fine reading (care / death / cause / aftermath) article purity at the default cut is 0.647 (pair precision 0.411, recall 0.866) against 0.912 coarse (`checks.out`): the development does not separate care from death, which is the job of phases and the predicate-by-day step |
| Merged stories | mix D1 joins the Qeshm strikes with the IEA energy-security story (3 of 11 articles); mix D3 is a teaser-only grab-bag; D0 and D4 split one war. Counts: 1 of 4 shown developments mixes unrelated stories (mix), 0 of 3 (c1) |
| Teaser reads | 13 of 34 / 17 of 40 articles are teaser-only; text signals there are headline-level. A quiet development may only mean teaser-only coverage |
| Off-story claims | pages carry other stories (c1 seq 4 has 38 claims, mostly about Pete Rose; seq 33 has 74, many about other topics). The on-story proxy leaks: for seq 4, 4 of 20 sentences pass, 3 of them off-story (shared words such as "world", "star", "media") |
| "New" is inflated | 15 of 16 post-cut c1 articles carry a first-seen claim; use corroboration, contests and forward statements, not "has a new claim" |
| Repeated is not corroborated | 93.2% / 94.7% of claims have one owner; many articles in a development do not mean many owners (c1 D0: 26 articles, 13 owners; mix D2: 5 articles, 2 owners) |
| Co-occurrence is not cause | `affects_resource` links are co-occurrence; stated-cause regex hits are unattributed and sometimes about a different event (Harambe 2016 in the Fiona development) |
| Timestamps | `published` is the first-seen date; seq 4 shows a title newer than its date. Delta ordering depends on it |
| Id stability | development ids change when an earlier article joins; stable identity needs overlap matching |
| All-clear under partial coverage | "no new article" and "no dispute read" must carry the teaser share; not "nothing happened" |
| Not human-tested | no user test of the navigation; the prototype's own validation plan (list vs map, omissions, recall) still applies |

---

## 7. Comparison

| | Old page | Ladder (KNOW/FOLLOW/EXPECT) | Prototype (Knowledge Navigator) | This method |
|---|---|---|---|---|
| Unit | concept (entity card) | concept | development (thread, stable id) | development built from existing fields |
| Top-level count | 35 to 45 cards | 35 to 45 | a handful per focus | 5 per area (3 to 4 shown, rest thin) |
| Mixing of threads in a top item | 0.715 / 0.815 article share in top thread | same as cards | not measured | purity 0.912 / 0.850 |
| What is new | triage verdict per article (29 of 34 plain updates) | rung moves (29 of 34 moved none) | delta before/after vs baseline | counts: new corroborated claims, contests, forward statements, phase word |
| Certainty | word per concept | word per line | confidence number kept secondary | owners-based word per development |
| Meaning / impact | shown from drivers (34 of 38 are time order) | cause rung mostly empty | summary, meaning, impact hypothesis (written) | quote only; cause and impact "unassessed" unless stated |
| Lanes | none | none | 6 hand-set lanes for the demo data | rejected: no field beats the developments (NMI 3.8) |
| Priority | none | none | material / watch / background (decision) | three computable proxies, named by what they measure |
| Safety gates | partial | certainty word per line | seven gates | adopted: novelty is not materiality, repeated is not corroborated, co-occurrence is not cause, qualify all-clear under teaser share |
| Depends on | entity typing (weak) | entity typing | a development builder (not in our data) | headline and sentence text, owners, contests, time (all in the bundles) |

## Files

Scripts and outputs in `SCR` = `/tmp/claude-0/-workspace/3ed8559b-0aa2-49c4-a429-a0452a913be2/scratchpad/consolidation/`: `common.py`, `gold.py` (reader labels), `devbuild.py` (rules R1 to R3), `signals.py` -> `signals.out`, `grid.py` -> `grid.out`, `sweep.py` -> `sweep.out`, `devs.py` -> `devs.out`, `m3_sameness.py` -> `m3_sameness.out/.json`, `analysis.py` -> `analysis_levels.out/.json`, `analysis2.py` -> `analysis2.out`, `devrecords.json`, `analysis3.py` -> `analysis3.out/.json`, `deltas.py` -> `deltas.out`, `phases.py` -> `phases.out`, `phases_members.out`, `final_extra.out`, `after_articles.out`, `resources.out`, `projection.out`, `projection-example.json`, `checks.out`.
