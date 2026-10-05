# Local World State Engine v0.1

**Status:** Experimental MVP  
**Goal:** Build a reproducible, inspectable local simulation engine that converts real-world evidence into semantic measurements, maintains state across World → Country → Region → Segment → Person lenses, and estimates directional decisions without relying on an LLM to invent the underlying dynamics.

## 1. Product thesis

The system maintains a continuously changing numerical representation of the world.

Incoming evidence is converted into **typed semantic measurements** by Jev-class classifiers or local equivalents. Those measurements update an explicit state model. Relationships propagate changes between connected nodes. Decision models translate state into directional probabilities.

An AI agent may query, explain, or operate the engine, but **the agent is not the world model**.

The fundamental chain is:

```text
Evidence
   ↓
Semantic classification
   ↓
Structured events / measurements
   ↓
Node + relationship graph
   ↓
State estimation
   ↓
Decision estimation
   ↓
Future scenarios
   ↓
Observed reality
   ↓
Backtest / learning
```

Every output must be reproducible from:

```text
evidence
→ semantic measurements
→ state changes
→ relationship transfers
→ decision model
→ output
```

---

# 2. MVP objectives

The first version must prove six things:

1. A news article or structured observation can be converted into reusable semantic measurements.
2. Those measurements can modify an inspectable world state.
3. State can propagate through explicit relationships.
4. Any World, Country, Region, Segment, or Person node can be queried independently.
5. Decisions can be calculated from state rather than generated as prose.
6. The complete result can be replayed from the event ledger with the same outcome.

**The MVP does not need to prove accurate prediction of society.**

It proves the architecture required to eventually test that scientifically.

---

# 3. Core conceptual model

## 3.1 Five lenses

| Lens | Represents | Example |
|---|---|---|
| World | global environment / blocs / systems | Global economy |
| Country | sovereign/institutional environment | United States |
| Region | geographic/local environment | Massachusetts |
| Segment | cross-cutting demographic, behavioral, or industry group | Small manufacturers |
| Person | persona or actual modeled individual | Manufacturing owner |

These are **node types, not a rigid five-level tree**.

A segment may cross countries and regions.

A person can simultaneously connect to:

```text
Person
 ├── located_in → Massachusetts
 ├── citizen_of → United States
 ├── member_of → Small Business Owners
 └── member_of → Manufacturing
```

The UI may continue showing five levels because that representation is easy to understand.

Internally, it is a graph.

---

# 4. Canonical objects

The MVP requires these logical tables.

| Table | Purpose |
|---|---|
| `node` | Everything capable of having state |
| `edge` | Relationship between two nodes |
| `evidence` | Original article, statistic, report, etc. |
| `event` | Something inferred or directly observed to have happened |
| `measurement` | Semantic classifier outputs about an event |
| `variable_definition` | Definition of each state dimension |
| `state_value` | Current/historical latent state |
| `decision_definition` | A question/action that can be estimated |
| `decision_estimate` | Calculated decision state at a point in time |
| `outcome` | What subsequently happened |
| `model_version` | Exact classifier/model/configuration used |
| `trace` | Causal lineage between all above objects |

A graph database is **not required** for v0.1.

Implement the logical graph as normal tables in SQLite or DuckDB:

```text
node
edge(from_node, to_node, relationship_type, ...)
```

This keeps installation trivial while allowing migration to a graph engine later.

---

# 5. Node

```text
node
--------------------------------
node_id
node_type
name
description
attributes
created_at
valid_from
valid_to
```

`node_type`:

```text
WORLD
COUNTRY
REGION
SEGMENT
PERSON
```

Nodes may be real or modeled.

Examples:

```text
WORLD:world
COUNTRY:usa
REGION:massachusetts
SEGMENT:us-small-business
SEGMENT:manufacturing
PERSON:persona-small-manufacturer-01
```

---

# 6. Relationships

## 6.1 Edge structure

```text
edge
--------------------------------
edge_id
from_node
to_node
relationship_type

gain
lag
gate
slant
noise

confidence
source
model_version
valid_from
valid_to
```

Supported initial relationships:

```text
CONTAINS
LOCATED_IN
MEMBER_OF
INFLUENCES
DEPENDS_ON
CONNECTED_TO
REPRESENTS
```

The important rule becomes:

> **One-edge propagation, not one-level propagation.**

Each traversal produces its own trace.

Example:

```text
World.Economy
    ↓ INFLUENCES
USA.Economy
    ↓ INFLUENCES
Massachusetts.Economy
    ↓ EXPERIENCED_BY
SmallBusiness.Economy
    ↓ MEMBER_OF
Persona.FinancialCapacity
```

Another path can exist simultaneously:

```text
World.Technology
    ↓
SoftwareIndustry
    ↓
Persona
```

This solves the Segment problem without abandoning the five-level mental model.

---

# 7. State model

## 7.1 L0–L3 starter variables

These are **draft ontology**, configurable rather than hard-coded:

| ID | State |
|---|---|
| `economy` | economic/resource conditions |
| `institutions` | institutional capacity |
| `trust` | trust and legitimacy |
| `security` | safety/stability/risk |
| `cohesion` | social alignment/conflict |
| `constraint` | regulatory or structural pressure |
| `information` | information/attention environment |
| `technology` | technological/infrastructure condition |
| `access` | mobility/access/connectivity |
| `expectation` | expectations/confidence |

The engine must allow this ontology to be replaced or extended without database changes.

## 7.2 Person variables

The Person layer translates environmental conditions into behavioral states:

| ID | State |
|---|---|
| `capacity` | ability to act |
| `need` | perceived utility/need |
| `awareness` | knowledge of option |
| `trust` | confidence in actor/product/action |
| `risk` | perceived risk |
| `social` | social influence/proof |
| `friction` | difficulty of acting |
| `fit` | identity/value alignment |
| `urgency` | timing pressure |
| `intent` | readiness to act |

The Segment → Person mapping therefore becomes particularly important.

---

# 8. State storage

Do **not** store 100 independently controlled values for every 10×10 grid.

Store the underlying state.

```text
state_value
--------------------------------
node_id
variable_id
tick
value
uncertainty
model_version
trace_id
```

Suggested normalized scale:

```text
-1.0 = strongly negative / away
 0.0 = neutral
+1.0 = strongly positive / toward
```

The exact semantics belong to each variable definition.

---

# 9. The visible 10×10 state grid

The grid remains a primary UI.

Rows:

```text
10 state variables
```

Columns:

```text
Level
Trend
Acceleration
Duration
Breadth
Intensity
Certainty
Volatility
Salience
Carry-over
```

But these are **derived projections**.

For example:

```text
Level         = current latent value
Trend         = Δ state / time
Acceleration  = Δ trend / time
Duration      = time beyond threshold
Breadth       = proportion of evidence/nodes showing effect
Intensity     = aggregate event magnitude
Certainty     = state/model confidence
Volatility    = recent variance
Salience      = attention/evidence concentration
Carry-over    = estimated persistence
```

Therefore:

```text
10 underlying states
        ↓
historical state + observations
        ↓
10 × 10 human-readable grid
```

The grid is a **view**, not the model.

---

# 10. Evidence

Every external input becomes immutable evidence.

```text
evidence
--------------------------------
evidence_id
source_uri
source_type
publisher
published_at
observed_at
content_hash
raw_content
metadata
```

Examples:

```text
news
economic statistic
poll
earnings report
weather observation
government announcement
sensor/API measurement
survey
```

Evidence itself does not change state.

It produces semantic measurements.

---

# 11. Semantic measurement layer

This is where Jev or similar classifiers fit.

The classifier receives evidence and answers small, typed questions.

Example:

```text
TARGET LEVEL
country       .94
segment       .71
region        .08

AFFECTED VARIABLES
economy       -.73
trust         -.21
security      +.04
expectation   -.61

MAGNITUDE
0.68

BREADTH
0.44

DURATION
medium

SALIENCE
0.79

CLASSIFICATION CONFIDENCE
0.87
```

Canonical record:

```text
measurement
--------------------------------
measurement_id
event_id
classifier_id
schema_id
target_node
variable_id
direction
magnitude
breadth
duration
salience
confidence
raw_result
model_version
```

The classifier is therefore acting as a:

> **semantic sensor.**

It describes evidence.

It does **not** decide what the world will do.

---

# 12. Semantic drill-down

Classification should compound only when useful.

Example:

```text
ARTICLE
   ↓
cheap broad classification
   ↓
High economy impact detected
   ↓
economy-specific classifier
   ↓
manufacturing effect detected
   ↓
manufacturing-specific classifier
```

Each drill creates additional measurements attached to the same evidence/event.

Possible trigger:

```text
high impact
OR
low certainty
OR
important decision affected
OR
classification disagreement
```

The exact thresholds remain configuration until calibrated.

This allows Jev or local classifiers to progressively produce a rich semantic knowledge base without requiring every article to undergo expensive analysis.

---

# 13. Events

Multiple measurements describe a single event.

```text
event
--------------------------------
event_id
event_type
actor_node
target_node
occurred_at
observed_at
status
evidence_count
```

Example:

```text
event:
US announces semiconductor export restriction

measurements:
constraint      +0.81
economy         -0.32
technology      -0.41
expectation     -0.25
```

One event can affect many nodes.

---

# 14. State update engine

Conceptually:

```text
previous state
+ direct observations
+ incoming relationship effects
+ persistence
+ uncertainty
=
new state
```

A future mathematical form may be:

```text
x(t+1) =
A·x(t)
+ B·events(t)
+ Σ H(edge)·parent_state(t-lag)
+ error
```

But v0.1 must not pretend that guessed coefficients are learned truth.

Every coefficient carries:

```text
origin =
    DEFAULT
    HUMAN
    FITTED
    LEARNED
```

and:

```text
model_version
training_window
evaluation_score
```

The UI visibly distinguishes **uncalibrated** from **learned** relationships.

---

# 15. Relationship/channel behavior

Each edge may transform a signal using:

```text
gain
gate
lag
slant
noise
```

Conceptually:

```text
incoming signal
      ↓
     gate
      ↓
     gain
      ↓
receiving-node agenda/slant
      ↓
      lag
      ↓
uncertainty/noise
      ↓
outgoing measurement
```

Every resulting change retains:

```text
origin_event_id
source_node
edge_id
destination_node
model_version
```

Therefore any number displayed in the grid can be explained backward.

---

# 16. Decisions

A decision is a relationship between **state and possible action**.

Do not ask a generative model:

```text
"What will this group do?"
```

Instead define the question:

```text
decision_definition
--------------------------------
decision_id
name
target_node_types
output_type
horizon
schema
```

Examples:

```text
BUY
SELL
ADOPT
SWITCH
MOVE
TRAVEL
HIRE
INVEST
SHARE
DELAY
```

Different node types may load different decision libraries.

---

# 17. Decision model

For decision `d`:

```text
current state
      ↓
decision relationship model
      ↓
direction
propensity
stage
horizon
confidence
```

Output:

```text
decision: HIRE

direction: toward
propensity: .64
stage: building
horizon: 1–3 months
confidence: .72
```

The simplest transparent implementation can begin as:

```text
score =
intercept
+ Σ state_variable × relationship_weight
```

Later that relationship can be replaced by:

```text
logistic regression
gradient boosted trees
survival/hazard model
Bayesian model
neural model
online learner
```

The output contract stays unchanged.

---

# 18. The second 10×10 matrix

This gives the second visualization a very clear meaning.

### Decision × State Influence Matrix

Rows:

```text
10 decisions
```

Columns:

```text
10 state variables
```

Each cell represents:

> How strongly is this state currently contributing toward or away from this decision?

Example:

| | Economy | Trust | Risk | Technology | ... |
|---|---:|---:|---:|---:|---:|
| Buy | +.31 | +.12 | -.42 | +.08 | |
| Move | -.04 | -.18 | +.51 | .00 | |
| Hire | +.62 | +.05 | -.23 | +.17 | |
| Invest | +.47 | +.21 | -.38 | +.31 | |

Clicking a cell exposes its learned/manual relationship and supporting history.

This matrix is much more meaningful than another arbitrary collection of 100 state rules.

---

# 19. Explainability contract

Every visible result must support:

```text
WHY?
```

Example:

```text
Small Manufacturers
Hiring propensity: 0.64 ↑

Contributors
────────────────────────
Economy                 +0.18
Expectations            +0.14
Technology              +0.09
Regulatory constraint   -0.08
Risk                    -0.04
Other                   +0.02
```

Selecting `Economy +0.18` drills further:

```text
Economy +0.18
 ├─ +0.10 regional manufacturing output
 ├─ +0.07 national demand
 ├─ +0.04 technology investment
 └─ -0.03 energy-price event
```

And ultimately:

```text
source evidence
→ classifier result
→ event
→ state update
→ relationship
→ decision
```

No unexplained score is acceptable.

---

# 20. Time

Everything is temporal.

The UI requires an `AS OF` control:

```text
Past ←──────── NOW ────────→ Future
```

Past:

```text
historical reconstructed state
```

Now:

```text
estimated current state
```

Future:

```text
simulated state distribution
```

A scenario never overwrites real state.

It creates a branch:

```text
baseline
scenario-A
scenario-B
```

This allows:

> What changes if Massachusetts confidence falls 20%?

or:

> What happens if this proposed event occurs next month?

---

# 21. Scenario engine

The simulator accepts either:

```text
synthetic event
```

or:

```text
state perturbation
```

Then executes exactly the normal engine against an isolated branch.

Example:

```text
SIMULATION:
Oil price shock

World
 ↓
US
 ↓
Massachusetts
 ↘
  Transportation segment
 ↘
  Persona

compare against baseline
```

Run deterministic mode with a fixed seed.

Later support Monte Carlo:

```text
1,000 paths

P10
P50
P90
```

This produces ranges instead of pretending one future is certain.

---

# 22. Learning loop

The engine must preserve every prediction.

```text
prediction at T0
       ↓
real outcome at T1
       ↓
prediction error
       ↓
training record
       ↓
new model version
```

Historical replay must prevent future information leakage.

Models are evaluated on dates after their training period.

For problems where actions and rewards are observable, an online learner is appropriate. Vowpal Wabbit is specifically designed for fast online/interactive learning and supports contextual-bandit workflows where context, action, selection probability and reward are recorded.

Do not use reinforcement learning merely because the system contains agents; use it only where an actual reward signal exists.

---

# 23. Local MVP architecture

Recommended v0.1:

```text
Python
├── FastAPI
├── SQLite
├── Polars/Pandas
├── NumPy
├── scikit-learn
├── NetworkX
├── classifier adapters
│    ├── Jev
│    └── local classifier
├── simulation engine
└── React/Vite UI
```

No Kafka.

No Kubernetes.

No vector database required.

No Neo4j required.

No distributed agents required.

The complete MVP should run:

```text
docker compose up
```

or as one native application.

---

# 24. Classifier interface

The semantic layer is provider-independent.

```text
classify(
    input,
    schema,
    context
) → SemanticMeasurement[]
```

Adapters can include:

```text
Jev
local small classifier
fine-tuned transformer
rules
future classifier
```

All must return the same typed contract.

This prevents the world model from becoming dependent on any semantic-model vendor.

---

# 25. Agent interface

Expose the engine through six primary operations:

```text
ingest(evidence)

state(node, as_of)

explain(node, variable, as_of)

decisions(node, as_of)

simulate(change, node, horizon)

compare(scenario_a, scenario_b)
```

A seventh developer operation:

```text
backtest(model, date_range)
```

An autonomous agent should primarily **query these functions**, not manipulate database rows.

---

# 26. Standards direction

Design the contracts using **JSON Schema** so event, measurement, state, decision and simulation objects are typed and independently validatable. JSON Schema's current published specification is Draft 2020-12.

Expose the same operations later through **MCP**. MCP's current TypeScript SDK describes the protocol as an open standard for exposing resources, tools and prompts to AI applications; its stable v2 line implements the July 28, 2026 specification.

If the World State Engine later becomes an independently addressable agent, add **A2A** rather than inventing a private inter-agent protocol. Google introduced A2A for vendor/framework-independent agent interoperability, and the project subsequently moved under the Linux Foundation.

Instrument semantic calls, simulations, model execution and agent queries with **OpenTelemetry**. OpenTelemetry explicitly standardizes semantic naming across traces, metrics, logs and events and now includes GenAI-oriented observability conventions.

This gives a natural future architecture:

```text
             AGENTS
          A2A / MCP
              │
              ▼
       WORLD STATE ENGINE
              │
 ┌────────────┼────────────┐
 │            │            │
State      Decisions   Simulation
 │            │            │
 └────────────┼────────────┘
              │
       Knowledge Graph
              │
       Event / Evidence
              │
       Semantic Sensors
       Jev / Local Models
```

The industry-facing abstraction therefore isn't:

> another AI agent with a giant prompt.

It is:

> **a typed state service that agents can observe, query, simulate and learn from.**

---

# 27. Primary user experience

The main screen contains four synchronized views.

### State

```text
[World] [US] [Massachusetts] [Manufacturing] [Persona]

┌────────────── 10 × 10 STATE GRID ────────────────┐
│                                                  │
│ Economy                                          │
│ Trust                                            │
│ Security                                         │
│ ...                                              │
└──────────────────────────────────────────────────┘
```

### Relationships

```text
World
  │
 USA ───────── Manufacturing
  │                │
Massachusetts ─────┤
                   │
                 Persona
```

### Decisions

```text
┌────────── DECISION × STATE MATRIX ──────────┐
│ Hire                                         │
│ Buy                                          │
│ Invest                                       │
│ Move                                         │
│ ...                                          │
└──────────────────────────────────────────────┘
```

### Timeline

```text
2024 ───── 2025 ───── 2026 ──●── 2027
                             NOW
```

Everything displayed must be clickable to reveal provenance.

---

# 28. MVP demo

One demonstration should be sufficient.

Configure:

```text
1 World
1 Country
1 Region
2 Segments
2 Personas

10 state variables
5–10 decision types
100–500 historical/current evidence items
```

Run:

```text
Evidence
   ↓
Jev/local semantic classification
   ↓
Event ledger
   ↓
State update
   ↓
Relationship propagation
   ↓
Decision estimates
   ↓
10×10 visualizations
```

Then inject one hypothetical event and show the difference between:

```text
BASELINE
vs
SCENARIO
```

Every changed cell must trace back to the injected event and propagation path.

That proves the architecture.

---

# 29. Success criteria

v0.1 succeeds when:

```text
✓ Same event + same state + same model version = same result

✓ Every state value can identify its contributing evidence

✓ Every propagated value exposes the path it traveled

✓ Every decision exposes its contributing state variables

✓ Any point in history can be replayed

✓ Scenario state never contaminates observed state

✓ Semantic classifier can be swapped without changing the engine

✓ State/decision model can be swapped without changing the UI

✓ No LLM-generated prose is required to calculate state or decisions
```

Predictive accuracy is explicitly **not** an MVP exit criterion.

That becomes the next stage.

---

# 30. Development path

```text
V0.1
Evidence → semantic measurements → state → decisions → visualization

V0.2
Historical replay + backtesting

V0.3
Fit state-transition and relationship coefficients

V0.4
Local classifiers trained from accumulated semantic measurements

V0.5
Monte Carlo uncertainty + scenario ranges

V0.6
Online learning from observed outcomes

V0.7
MCP state/simulation server

V0.8
A2A autonomous World State Agent

V1
Empirically calibrated domain model
```

The architecture should allow a domain model to become highly accurate without claiming that the entire world model is equally accurate.

---

# 31. Core design principle

The system is not attempting to make an AI **imagine the world**.

It is attempting to maintain:

```text
OBSERVED WORLD
      +
SEMANTIC MEASUREMENTS
      +
LEARNED RELATIONSHIPS
      +
UNCERTAINTY
      =
CURRENT ESTIMATED STATE
```

and:

```text
CURRENT STATE
      +
POSSIBLE CHANGE
      +
LEARNED DYNAMICS
      =
DISTRIBUTION OF FUTURE STATES
```

The 10×10 grids make that world legible to people.

The graph makes it structurally correct.

The event ledger makes it reproducible.

The classifiers make unstructured reality measurable.

Machine learning progressively replaces guessed relationships with learned relationships.

That combination is the product.