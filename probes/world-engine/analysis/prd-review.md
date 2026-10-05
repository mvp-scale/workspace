# Review of the ChatGPT PRD "Local World State Engine v0.1" (2026-10-04)

Rule for outside inputs: each claim is marked ADOPT, ADAPT or SKIP with a reason. Source tags: [checked] seen in a source this session; [memory] unverified; [ours] our own choice.

## 1. What matches what we already agreed
| PRD | Our discussion | Verdict |
|---|---|---|
| Evidence -> event -> measurement -> state -> decision -> outcome, each with a trace and a model version | JSONL ledger, event ids, provenance | ADOPT. Adds `outcome` and `model_version`, which we lacked for backtests. |
| Classifier is a "semantic sensor" that answers typed questions and never decides | Local classifier reads headlines into dial readings | ADOPT. |
| Cheap broad classification first, drill down only when useful | Two-step screen (about 20 questions, then groups) | ADOPT. |
| Edge channel: gain, lag, gate, slant, noise | Level-to-level distortion channel | ADOPT. Same five numbers. |
| State stored as latent values with uncertainty and history; the 10 x 10 grid is a derived VIEW (level, trend, acceleration, duration, breadth, intensity, certainty, volatility, salience, carry-over computed from history) | We described the grid as the state itself | ADOPT. Better than storing 100 independent cells: 10 states to calibrate, not 100. The facets we guessed become computed formulas. |
| Decision x state matrix shows how much each state currently pushes a decision toward or away; score = intercept + sum(state x weight), later swappable for a fitted model | Decision matrix with weights | ADOPT. The contributions add up exactly on the logit scale, which gives the "why" breakdown. |
| Every coefficient tagged DEFAULT, HUMAN, FITTED or LEARNED, with model version, training window, score | Our guess / contested / checked tags | ADOPT. Formalises ours. |
| Scenarios run on an isolated branch and never touch observed state | Ledger forks | ADOPT. |
| Time control (as of), deterministic seed, later Monte Carlo ranges | Seeded ensembles | ADOPT. |
| Historical replay without future leakage; evaluate only after the training period | Backtest on past shocks | ADOPT. |

## 2. Where we should differ
1. **Graph with one-edge propagation, not a rigid one-layer-down tree.** Segments and industries cross countries and regions, so nodes plus edges is more honest. Keep the five-level view for the UI and for explanation. ADAPT: edges follow the lens order by default (world, country, region, segment, person), with explicit cross-links for segments.
2. **The PRD's 10 state variables are more abstract than ours** (economy, institutions, trust, security, cohesion, constraint, information, technology, access, expectation). "Economy" lumps prices, jobs, housing and financial conditions, which are separate real series and separate headlines. ADAPT: keep our concrete variables as the measured layer and map them up into the PRD's ten as groupings. The PRD says the ontology must be replaceable, so this fits. It also has no health variable, and no policy dial (ConsumerSim has policy classes).
3. **PRD person states mix world effects with the offer itself.** Need, awareness, fit, friction and intent depend on the product or message being shown, not only on the world. ADAPT: keep persona traits and states as the base, and compute need, fit, friction, risk and capacity as per-decision readouts from persona x stimulus x world.
4. **Persons as graph nodes does not scale to 100,000.** ADAPT: a handful of nodes and edges for world, country, region and segments; persons as array rows with membership columns, and no per-person edges.
5. **Agenda per node.** The PRD has slant on edges and a receiving-node agenda only in passing. ADAPT: give every node an agenda vector (which variables it amplifies or suppresses), so two countries pass on the same event differently.
6. **No real-data anchor.** The PRD has an `outcome` table but names no series. ADAPT: first backtest target is a consumer-confidence series (the ConsumerSim precedent), with world variables fed from published monthly series.
7. **Product stack (FastAPI, SQLite, React, Docker) is more than v1 needs.** SKIP for now: files (CSV rules, JSONL ledgers) plus the numpy engine; DuckDB for queries if needed.

## 3. Standards the PRD names (checked)
- JSON Schema: Draft 2020-12 is the current published specification [checked: json-schema.org].
- MCP: the 2026-07-28 specification shipped on 28 July 2026, described by its maintainers as the largest revision; it removed sessions [checked: protocol blog and press summaries].
- A2A: hosted by the Linux Foundation; at its one-year mark in April 2026 it had more than 150 supporting organisations [checked: Linux Foundation press release].
- OpenTelemetry semantic conventions and Vowpal Wabbit contextual bandits: [memory] not verified.
- Our own additions that fit: bitemporal records (event time vs observed time) [memory]; PROV-O for the trace [checked earlier].
All of these are direction for v0.7 and later. None is needed for the base version.

## 4. Mapping the PRD's variables to ours (draft)
| PRD state | Our concrete variables |
|---|---|
| economy | prices, housing cost, energy and fuel, financial conditions, job security |
| institutions, trust | trust in institutions |
| security | crime, war and terror |
| cohesion | community, social division |
| information | news overload (media measure) |
| technology | technology pace |
| access | disruption of routines (partial) |
| expectation | outlook (computed outcome) |
| constraint (regulatory) | none yet |
| (none) | health risk |

| PRD person state | Our counterpart |
|---|---|
| capacity | liquidity, financial stress, time pressure |
| risk | loss aversion, safety concern |
| trust | institutional trust (plus brand trust, not yet) |
| social | social ease (plus social proof, not yet) |
| need, awareness, fit, friction, urgency | readouts of persona x stimulus, not persona states |
| intent | the decision output |

## 5. Proposed base version one (aligned with both)
Tables (logical, stored as CSV and JSONL): evidence, event, measurement, node, edge, variable_definition, state_value (value, uncertainty, origin tag), decision_definition, decision_weight, decision_estimate, trace, model_version. `outcome` added at v0.2.
Engine: ledger -> classifier adapter -> measurements -> state update along edges with channel (gain, lag, gate, slant, noise, seeded) -> persona readouts -> decision estimates with contribution breakdown -> two 10 x 10 views (state view, decision x state matrix).
Demo: 1 world, 3 countries, 2 regions, 3 segments, persons as arrays; scripted three-country escalation; baseline vs scenario; every changed cell traces to its event and path.
Acceptance (PRD list plus ours): same input and seed give the same output; every value lists its evidence and path; every decision lists its state contributions; scenarios never change observed state; the classifier is swappable; duplicate reports count once; the noise channel changes outcomes visibly versus a no-noise run.

## 6. Open decisions for the owner
1. Store 10 underlying states and derive the 10 x 10 grid (recommended), or store all 100.
2. Concrete variables (ours) mapped up to the PRD's ten (recommended), or the PRD's abstract ten as the measured layer.
3. One-edge propagation on a graph (recommended) or strictly one level down.
