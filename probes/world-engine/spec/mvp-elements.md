# World engine MVP: the elements (draft, 2026-10-05)

Purpose: one clean picture of what the engine is made of, so we can see the complexity before adding any. Status tags: **exists**, **partial**, **missing**. Every number in the engine is a guess until a feeder replaces it with data.

## The whole thing in three parts

```
 A. FEEDERS                    B. WORLD MODEL                       C. USER PASS
 (gather and keep current)     (what exists, how it moves)          (ask, run, read)

 state feeder     ─┐
 resource feeder  ─┤           nodes  : level, state, resource,      ask   : what it is  +  what you want to know
 relation feeder  ─┼──────────▶        decision, input               break : input becomes entities touched
 population feeder─┤           edges  : reads, writes, draws,         run   : propagate, then decide
 news feeder      ─┤                   couples, inherits, decays      read  : any layer, any perspective
 outcome feeder   ─┘           rules  : one row per decision
```

Feeders change slowly and run on their own schedule. The user pass is instant and never changes the model.

## B. The elements

| # | Element | One line | Example | Today |
|---|---|---|---|---|
| 1 | **Level** | where something sits in the world | world, country, region, segment, person | partial: no state or city tier; regions are metro/town/rural |
| 2 | **State** | how a thing stands now: a baseline plus ten facets (level, trend, duration, ...; see Facets below) | trust in institutions, prices, job security | exists: 15 dials, 15 person states. Missing: values and stance states |
| 3 | **Resource** | a stock with limits that flows in and out | attention, trust, capital, skills, energy, compute, legitimacy | missing |
| 4 | **Decision** | a rule that reads states and resources and gives a likelihood | adopt, regulate, trust, back, spend | partial: 8 consumer decisions, hand-weighted. Missing: stance and policy decisions |
| 5 | **Input** | what the user passes in, broken into the entities it touches | a leader's statement, an event, an offer | partial: event or offer only, one text box |

Topics (AI, quantum, a fertiliser) are only tags on an input. They never get elements of their own.

## B. The relations (edges)

Each relation has a **sign** (up or down), a **weight**, a **delay**, and **evidence** (source and confidence).

| Relation | From → to | Meaning |
|---|---|---|
| reads | state or resource → decision | the decision looks at it |
| writes | decision → state or resource | the decision changes it, after a delay |
| draws / feeds | decision ↔ resource | uses up or builds a stock |
| couples | resource ↔ resource | they move together or against each other |
| inherits | level → level below | a layer passes its change down (and, to be built, a weighted sum back up) |
| decays | state or resource → baseline | fades at a rate set by the event's class |

Step order, fixed: read levels, decisions evaluate, effects are written (with delays), stocks update, everything decays.

## One graph or two?

My recommendation: **one set of nodes, two families of edges, run in order**, not two databases.
- **Structure edges** (couples, inherits, decays, draws) pass change along. This is mostly addition and multiplication, so it compiles to a sparse table and runs fast.
- **Choice rules** (reads, writes) are one row per decision: its inputs, weights, a threshold, and what it writes. This is where thresholds and caps live.
- A decision with several inputs is just a row listing them. No RDF and no reification are needed. Keep the data as plain tables (nodes, edges, rules), triple-shaped so it can be exported later.

## A. The feeders (separate pipes)

Each pipe collects one kind of thing, keeps it current, and writes to one table. Better data in a pipe sharpens that part of the model without touching the others.

| Feeder | Collects | Writes to | Today |
|---|---|---|---|
| State | public indices per country and level | state baselines | partial: US only, read by hand |
| Resource | current level of each resource class and what moves it (deep research, then tracked) | resource stocks, couples | missing |
| Relation | how things relate, with a source for each link | edges and decision rules | partial: hand-set, no evidence column |
| Population | who lives where and how they differ (census-style microdata) | people and audiences | partial: 100,000 simulated people |
| News | headlines and one-line descriptions from feeds | inputs | partial: three NPR feeds, 27 items |
| Outcome | real series after each event, to test against | the backtest | missing |

## C. The user pass

1. **Ask** with two parts: what it is (kind, who, where, content) and what you want to know (yes/no, choice, or score).
2. **Break down**: yes/no questions place the input on states, resources and decisions. The evidence for each reading stays visible.
3. **Run**: propagate through structure edges, then decide.
4. **Read**: one map, any layer; click a number for the rule and the strongest paths behind it.

## Breadcrumb (illustration only, not engine output)

A world leader's statement on a general-purpose technology:

```
Input: leader statement (world level)
├─ draws   Resource: attention                      (+, fast decay)
├─ writes  State: trust in institutions / companies (±, slow decay)
└─ reads by Decisions
   ├─ regulate or permit   ← state: trust, resource: legitimacy
   │     └─ writes → State: policy stance (country level, next step)
   ├─ adopt or hold off    ← state: trust, resource: capital, compute
   │     └─ draws  → Resource: compute, energy   ── couples ── capital
   └─ back or oppose       ← audience lean on risk vs benefit
inherits: world → country → region → segment → person (each hop has a delay)
```

## Facets: the depth I left out of the table above

A state is not one number. In `persona/model-v2.md` each state has ten **facets** (draft, ours, "a guess"): level (distance from neutral), trend, acceleration, duration, breadth (how many it reaches), intensity, certainty, volatility, salience (how much people care), carry-over. A decision's stage (calm, building, imminent) is a threshold rule on level, trend, duration, breadth and certainty. The engine today uses only level plus decay, which is a likely reason its stage thresholds failed (everything read "imminent").

## Your 10x10 grids, mapped

Your mental model and the graph are the same thing at two zoom levels. The graph is the sparse version; the grids are its blocks.

| Your grid | In the graph | Compiled form |
|---|---|---|
| State: 10 variables x 10 facets | a state node carries 10 facet values | array [node, facet] |
| Decision: 10 decisions x the state grid | a decision's `reads` weights over (state, facet) cells | matrix [decision, (state, facet)] |
| Resource: 10 resources x 10 facets (assumed) | a resource node with facets plus stock, cap, set point | array [node, facet] |
| Effects: decisions onto resources and state | `writes` and `draws` weights | matrices [(resource or state, facet), decision] |
| Inheritance, one 10x10 per level hop | `inherits` edges, each a channel | one matrix per level pair |

**The consolidation you sensed:** a *cell* is (node, facet). Every block above is a slice of one big sparse matrix over all cells. 3 grids x 100 cells is 300 cells per level node; model-v2 already counts about 900 state-cell rules plus the matrices to calibrate.

## Definitions (the fields each thing must have)

| Thing | Fields |
|---|---|
| **Node** | id, kind (state, decision, resource, input), level, parent, facets[10], baseline, scale, status, source |
| **Facet** | one of the ten above; a column of every state and resource |
| **Edge** | from (node, facet), to (node, facet), kind, sign, weight, delay, moderated_by, status, source, confidence |
| **Channel** (every level hop) | gain, lag, noise, slant, gate, plus the receiving node's agenda vector (what it amplifies or mutes) |
| **Decision rule** | inputs [(node, facet, weight)], bias, threshold; outputs stage (calm, building, imminent) and direction; writes [(target, weight, delay)] |
| **Resource** | stock, cap, set point, restoring rate, inflow, outflow, plus facets |
| **Input (shock)** | id, entry node, readings [(node, facet, amount)], size, reach, persistence class |
| **Person and audience** | traits (15 today), cluster, salience, lean on each abstract dimension |
| **Status** | guess, fit or real, with a source; carried by every number |

## What the first version of this file missed

1. **Facets** (the second dimension of your grids). The biggest gap.
2. **Channel distortion**: five numbers per hop plus an agenda vector, not just a weight and a delay.
3. **Stage and direction** as decision outputs, driven by facets.
4. **Moderators**: `rules/grid.csv` already has a `moderated_by` column (for example, price attention is stronger when liquidity is low).
5. **Status on every number** (guess, fit, real) and its source.
6. **Resource limits**: cap, set point, restoring rate.
7. **Siblings and roll-up**: links between neighbouring nodes, and a weighted upward total (both listed as gaps in model-v2).
8. **Baseline** as an element: what neutral is for every state.

## Complexity today (known counts only)

15 states (dials), 15 person states, 8 decisions, 10 offer factors, 144 reading questions, 8 countries x 3 settlement types, 8 audiences. Facets in the engine: 1 of 10. MVP target from the reviewers: about 300 entities in total, as plain tables.

## Open decisions

1. Resources: a tier in each level, a lens across levels, or both (I lean both).
2. The first list of abstract states, resources and decisions (a draft catalog for you to edit).
3. The unit of a tick (suggested: one simulated hour from publish time).
4. Neutral for offers: the world average (my default).
5. Whether the first prototype is the 30-entity trust-ripple graph run next to the current engine.
