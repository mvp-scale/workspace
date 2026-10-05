# Audience (spec v0.1, draft 2026-10-04)

**What it is.** A classifier-shaped service. You hand it something (an idea, a message, an article) and a question; it answers from OUR data (the world state and the population), not from a language model's general knowledge. The answer comes back at five levels, with the exact snapshot it was computed from.

Status: the take-up decision runs today (`audience.py`, `engine.py`). Everything marked [not built] is a design, not code.

## 1. The path of one request
1. **Feed.** Simulated or real, news flows into the ledger (evidence -> classifier readings -> events). Not part of the request; it just keeps the world state current.
2. **Request arrives.** `{state: <item>, questions: {...}, as_of, nodes}`. Same shape as the local classifier: a state, typed questions.
3. **Read the item.** The local classifier answers a small fixed set of yes/no questions about the item (cost, setup effort, ID or photo needed, strangers, time, who it targets, novelty). These are the item's readings.
4. **Take the snapshot.** The world state at `as_of` (default now) is loaded; every person's effective traits are computed from their own base traits plus the world's effect on them.
5. **Evaluate the decision.** For each question, the registered decision model gives every person a probability (see section 4).
6. **Roll up.** Probabilities are averaged by node: world, country, region, segment, and the person-level spread.
7. **Explain.** What the world's current state changed, how typical the answer is among ideas we have already scored, and whether the item is unlike anything the model was fitted on.
8. **Return** the typed answer plus the snapshot ids. The request and response are written to the ledger so the answer can be replayed.

## 2. Inputs
| Input | Meaning | Status |
|---|---|---|
| `state` | the item: text, plus optional facts (price, audience, place) | works for text |
| `questions` | typed questions: `noul` (yes/no), `choice` (pick one option), `rank` (order several items), `score` (1 to 5 rating) | noul, choice, rank run; score [not built] |
| `as_of` | a time or tick; default now | now only |
| `branch` | `observed` or a scenario id (never changes observed state) | scenario branch exists in the demo |
| `nodes` | which levels or nodes to report | all five levels |
| world state | read from the ledger, never passed in | works |
| population | persons as rows (traits, region, segment memberships) | 50,000 to 500,000 |
| decision registry | which decisions exist and how they are computed | one decision [not built beyond take-up] |

## 3. Outputs
Each answer is typed like the classifier's:
- **noul**: `noul` = mean probability, plus per level: by node, worst and best node, and the person-level spread (share saying yes, 10th and 90th percentile).
- **choice**: probability per option plus 'none' (placeholder weight), overall and per region and segment.
- **rank**: the ordered list, mean take-up per item, the share of people preferring each pair, the order per region and segment, and whether the order is the same everywhere.
- **score**: a distribution over 1 to 5 [not built].
Every answer also carries:
- `percentile_among_known_ideas`: where this answer sits among the 39 ideas already scored, per level. This gives a scale: raw take-up is low for almost everything, so 0.20 means little without it.
- `levels_above_typical`: how many of the five levels sit at or above the median known idea (0 to 5). This is the "past five in all cases" view.
- `world_effect`: the answer in the current world minus the answer in a neutral world.
- `extrapolation_flag`: true when the item is unlike every idea the model was fitted on (our earlier test failed on new kinds of idea, so treat flagged answers as low confidence).
- `snapshot`: world tick and digest, population size and seed, run seed, hash of the rules tables, classifier and decision-model versions, creation time.

## 4. The decision engine
A decision is registered once and evaluated generically.
```
decision_definition: id, question wording, mode (offer or event), output type, horizon,
                     state weights, item attributes it reads, interaction source, calibration status
logit(person, item) = intercept + sum(state weight x person state)         # state side (rules/decision_weights.csv)
                                + sum(item weight x item reading)          # item side
                                + sum(interaction x state x reading)       # fitted
```
- **Offer mode** (the item is something to take up): decisions like take-up, share, object, switch.
- **Event mode** (the item is a world change): how the eight state decisions move against a neutral world.
- Today: the take-up decision's interaction term is a ridge model fitted to 39 ideas x 400 people (the labels are language-model answers about generated people, not real people). The eight state decisions exist as hand-set weights.
- Each decision carries its calibration status: GUESS, FITTED or LEARNED.

## 5. The five levels
v0 limits (stated plainly): `world` and `country` are the same roll-up of the same people, because there are no world-level or country-level decision tables yet. Region and segment differ by who is in them. The person level is the spread across individuals. Level-specific decisions (a government or a segment acting as one) are [not built].

## 6. Example (real output, 50,000 people, world at tick 39, digest 1a0f3965942b)
Item: Neighbour Loop at $12 a month with an app and an ID photo.
```
take_up  noul 0.199   (neutral world 0.212; the current world lowers it by 0.012)
  world 0.199 | country 0.199 | regions 0.196 to 0.202 | segments: age_young 0.330, income_high 0.229,
  income_low 0.151, age_senior 0.074 | person: 13% yes (10th to 90th percentile 0.009 to 0.578)
  percentile among known ideas: about 0.26 at world, country, region and segment; 0.31 at person
  levels_above_typical: 0 of 5
which_version (free by text, paid app, free app, none): free_sms 0.674, free_app 0.196, paid_app 0.064, none 0.066
rank_candidates: neighbour_loop_free_sms 0.629, gardenway 0.099, nightfall 0.017; same order at every region and segment
extrapolation_flag: false (this item is one of the fitted ideas, so the flag is uninformative here)
elapsed 1.3 s (one local-classifier call plus arithmetic)
```

## 7. Known gaps
- Only take-up is a real decision; 'like', 'share', 'object', 'score' are not yet defined or fitted.
- The percentile for region and segment uses the mean across nodes, which hides spread (segments range 0.074 to 0.330).
- The 'none' weight in choice is a fixed placeholder.
- Fitted on language-model answers about generated people, then applied to world-modified traits.
- No real-people check. The example item was in the fitting set, so it proves the contract, not the accuracy.

## 8. Open decisions
1. Which decisions to register first (take-up exists; candidates: like as a 1 to 5 score, share, object, switch, pay at a price).
2. Define 'clears' by a fixed threshold, by percentile among known ideas (current), or by a stated goal supplied in the request.
3. Whether world and country later get their own decisions (policy-like), and what those would be.
