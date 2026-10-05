# Ontology v1 (draft): state, events, decisions, scopes

REVIEW NOTE (2026-10-04): the owner judged this a patchwork. Each cited piece is real, but they come from unrelated fields (environmental reporting, event coding, sensor networks, business rules) and the assembly (deviation scopes, lattice, routing, triggers) is ours, not an established framework. The better frame is a state-space model: a hidden world state per level, a transition model, an observation model (stories are noisy evidence), online filtering to update the estimate, and decisions as a policy over the estimated state. Treat the sections below as bookkeeping vocabulary only until rewritten around that frame.

Purpose: a contained, abstract definition of the world model, reusing existing vocabularies where they exist. Status tags: [checked] = found in a source this session; [memory] = from general knowledge, unverified; [ours] = our own choice. Nothing here has been tested beyond the toy engine.

## The one separation: pressure -> state -> response
Events (pressures) change state. State is a set of numbers. Decisions (responses) read state and never write it, except through new events they cause. This is the structure of the DPSIR framework (drivers, pressures, state, impact, response), developed by the European Environment Agency in 1999 on top of the OECD's Pressure-State-Response framework of 1993 [checked: Wikipedia and EPA/BAFU summaries of DPSIR].

## Entities (shared across every level)
| Entity | Meaning | Fields | Borrowed from |
|---|---|---|---|
| Scope node | a place or a segment that holds state | id, parent, axis (geo or segment), type (world, country, state, region, age band, industry...) | geography and segment code lists (ISO country codes, regions) [memory] |
| Dial (property) | one measurable condition | id, definition, kind (condition, media, outcome), half-life | SOSA ObservableProperty [checked] |
| State value | a dial's value at a scope node and time | scope, dial, value (a deviation from the parent node, around 1), time, window features (count, rate, acceleration) | SOSA Observation of a property on a feature of interest [checked] |
| Event | something that happened or was announced | id, time, actor 1, action type, actor 2, location, intensity, source, confidence, provenance (real or simulated) | CAMEO "Actor 1 does Action on Actor 2" with location, date and a -10 to +10 Goldstein scale (conflict to cooperation); CAMEO+ adds nine non-conflict domains (crime, economy, corporate action, technology, infrastructure, environment, health, demography, information) [checked in GDELT Cloud documentation] |
| Trigger | a rule on state or windows that creates a derived event | id, condition (partition, order, pattern, window), derived event, delay (one tick), cooldown | event-condition-action rules [memory]; pattern clause: SQL row pattern recognition, MATCH_RECOGNIZE [checked] |
| Persona | one person | id, memberships (one node per axis), traits, states | ours |
| Decision | a choice a persona or node can make | id, scope level it applies to | DMN decision requirements [checked] |
| Decision table | the rule that maps state to a choice | inputs (state values), weights or thresholds, output (probability) | DMN decision tables, current version 1.5 (Aug 2024), XML interchange [checked] |
| Provenance link | why a value changed | change id -> event ids and trigger ids | PROV-O, which SOSA observations align with [checked] |

## Levels
- Two axes: geography (world, country, state, local) and segment (demographic, industry). A persona belongs to one node on each axis [ours].
- Each node stores only its DEVIATION from its parent, so a person's effective dial = world x country deviation x state deviation x segment deviations. This stops one event being counted at several levels [ours].
- Not the same table everywhere: every node uses the same dial ids, but nodes can hold different subsets, and decision tables can differ by level (persons decide to buy or move; higher nodes hold state only in v1) [ours].

## Event routing
An event carries actors, location and type. The routing table maps those fields to scope nodes and a relevance weight (a conflict reaches the actors' countries fully, their allies partly, others by distance or salience) [ours].

## What each part reads and writes
- Classifier: reads text; writes an Event (actors, action, location, type) and its dial readings.
- Routing: reads the Event; writes state deviations at the nodes it reaches.
- Triggers: read windows over state; write derived Events (one tick later).
- Decision tables: read effective state; write action probabilities. They never write state.
- Ledger: every write above, with provenance.

## Not covered or unverified
Whether CAMEO and GDELT are freely reusable (the source I read was a commercial GDELT Cloud page); the JDL data-fusion levels and Endsley's situational awareness, both candidates for the 'levels of understanding' idea [memory]; how to calibrate any of it against real outcomes.
