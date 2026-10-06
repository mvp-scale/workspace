# rules_v2: merged World Engine ruleset (draft)

New files only. The live engine still reads `../rules/` (v1); nothing there was changed. Built from the five agent proposals plus `review.md` (punch-list items 1-13). Check it with `python3 ../validate_v2.py`.

## What v2 is
A deeper, cleaner graph: Story -> Topic -> Condition -> Person state -> Decision, plus a Condition -> Condition tie step and a resource vocabulary ("Lego bricks") that every condition points at.

## Counts
| layer | file | v2 | v1 |
|---|---|---|---|
| resources | resources.csv | 26 | 10 |
| conditions | dials.csv | 38 | 16 |
| topics | domains.csv | 48 + `other` | 13 + `other` |
| person states | elements.csv | 47 (20 traits, 8 derived, 19 moving states) | 15 |
| decisions | decisions.csv | 20 | 8 |

## Links (all hand-set guesses)
| type | file | count | cap |
|---|---|---|---|
| topic -> condition | `dials` column of domains.csv | 99 | <=3 per topic, primary first |
| condition -> condition | dial_ties.csv | 12 | <=12, <=1 outgoing per condition |
| condition -> moving state | grid.csv | 52 | <=4 per state |
| state -> decision | decision_weights.csv | 109 | 4-6 inputs per decision, <=4 decisions per state |
| topic -> resource | `resources` column | 0 hand links | derived from each condition's `resource_id` |
| **total** | | **272** | 375 |

**Every weight is a guess.** Weights use three levels with a sign: weak 0.2, medium 0.5, strong 0.8 (a `status` of `guess` until fitted). The reviewer's text said strong 0.9; the task brief said 0.8, which is used. A written reason (`why`, <=15 words) is present on every strong, negative, contested, cross-domain, tie and migration_flow link, and on every political-trait or religiosity weight. Identity-like links say so in `why`. Sign convention: the sign is the effect of the source going UP (a condition's `up_means` says what up is).

## How v2 differs from v1
- Topics route to conditions (v1 had no routing column); resources are derived, not hand-linked.
- Moving states link to conditions (not resources); traits and derived states are fixed and have no incoming links. Today's 15 trait links are retired; `price_attention` and `liquidity` become states.
- Id collisions fixed: resource `health_status` -> `population_health`; condition `debt_burden` -> `private_debt` (state keeps `debt_burden`); topic `minerals_materials` -> `mining_materials` (resource keeps it).
- `optimism` exists only as a person state. The old computed dial is retired and is **not a row** in dials.csv. The engine should keep the computed aggregate as a readout named `outlook` (shown as "Outlook (computed)"); it is not a node, has no grid links, and the circular optimism<-optimism link is deleted. `spending_confidence` merged into optimism.
- Merges and cuts: public_order -> state_capacity, free_time -> attention, burnout -> wellbeing, cooperativeness -> prosociality, three culture topics -> culture_leisure; skills_level, time_squeeze and adopt_tech cut; real_wages -> pay_growth; place_type -> car_dependence; borrow_repay -> borrow, save_invest -> invest, comply_rules -> break_rules.
- Added: resource `population`, condition `migration_flow`, decision inputs for study_train, stockpile_prepare, claim_support, break_rules, start_business, family_change.
- New engine step needed: condition -> condition ties (dial_ties.csv). If declined, cut the ten dead-end conditions.
- Additions to dials.csv columns: `resource_id`, `up_means`. `news_overload` keeps kind `media` (moved by story volume, no topic routes to it, by design).
- domains.csv keeps the legacy `state_classes` and `decisions` columns, empty (topics route to conditions only); `moves_what` now lists condition names.
- id_map.csv maps every v1 id (and the proposal-only ids that were renamed or cut) to its v2 ids; split topics need the 450 cached headlines reclassified, not relabelled.

## Not done here (review items 14-16)
Source verification, data migration (ledger v1 freeze, classifier questions, impact phrases), plain-language page fixes, and the engine change from joining topic->resource by name to by id.
