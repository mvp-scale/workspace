TARGET STATE: THE KNOWLEDGE PIPELINE AS ONE RECORD (2026-11-14, v2)
===================================================================

What it is
  A static page that shows the pipeline as ONE layered knowledge record per article (extracted once,
  reused by every later stage and by the next article), instead of twelve parallel per-output chains.
  It replaces the v1 page of 2026-11-13 (backup: the session scratchpad, target_state_v2_backup/).
  Nothing here runs a model. It is not the live bench (simulation/index.html).

Sections
  1. The record: eight layers (L0 text and metadata, L1 tokens and sentences, L2 mentions, L3 linked
     entities, L4 relations and events, L5 claims, L6 article profile, L7 cross-article graph). Each
     layer: written once by (named elements), holds, read by, built and tested; compare view adds today.
  2. The reuse matrix: producer layer x consumer output (Domain, Area, Subarea, Capability, Function,
     Condition, Claims, Evidence, Place, Time, Novelty, engine keys, G4, G5/G6).
  3. The cross-article loop: the eight journal tables, what grows them, what they feed next.
  4. Every output derived from the layers: reads, derivation rule, test, the four golden stories
     (TARGET = specification; TODAY = stored values, compare view).
  5. The cascade with early exit, and the BitTools as labelling functions for the Fuser.
  6. Measured tests per layer (set, metric, pass bar, scoring-only flag).
  7. Build order, eight steps, free vs owner's yes.
  8. Cut or merged from the previous page (compare view only).
  9. Owner decisions.  10. Patterns used and what does not fit a CPU, no-LLM target.
  Click any element name for its point, definition and measure (and today's status in compare view).

Two views (buttons under the title)
  Target state (default): the finished system in the present tense; no status labels.
  Compare with today: status badges (works, partly, not built), TODAY values, today's notes, section 8.

How to open it
  http://localhost:8100/mockups/target-state/index.html (the console). Also opens from the file
  (data.js). No external libraries, no network, no hosted calls, no new port. Light and dark theme follow
  the system; the header button overrides. Works at phone width. textContent/createElement only.

What is real and what is target
  TODAY values are read from data.js (unchanged from v1): projects/world-state/runs/pulse/golden/
  articles.jsonl (topic and story probabilities, facts with status, scan spots, windows) and
  specs/topic_to_iptc_v1.json. Stored today values exist for Domain, Area, Function, Condition (change
  spots), Claims (triples), Evidence (quote spots) and Time (date spots); Subarea, Capability, Place,
  Novelty and the engine keys have no stored value and say so.
  TARGET values are the hand-written specification kept from v1; percentages are illustrative blends.
  Element definitions, line references and ledger ids are in the registry inside index.html and in the
  design report (scratchpad fable_knowledge_pipeline_design.md). UNVERIFIED marks an unchecked claim.
  Proposed new elements (dashed chips): Knowledge record, Entity linker, Near-duplicate cache; each has
  a point, a definition and a measure.

Files
  index.html   the page (inline CSS and JS; the design data is inline)
  data.json    the four stories, TODAY and TARGET (unchanged from v1; generator in the scratchpad)
  data.js      the same data as a script (window.TARGET_DATA)
  README.txt   this file
  Check: scratchpad check_v2.cjs (jsdom: zero JS errors, every chip defined, target view has no
  'not built', compare view restores status).

Files read to build it
  knowledge_pipeline/playbook/00-knowledge-pipeline-v1.md (sections 1-5, 8, 9, 14, 18), 15-bitmob-stack.md
  projects/world-state/analyze2.py, facts_lib.py, scan_gate.py, extract.py, spo_chains.py, decider.py,
    expert1_runtime.py, t209_triage_state_text.py, t226_g4_event.py, t230_tiers.py, t233_knn_norm.py
  knowledge_pipeline/simulation/server.py; newsreader/bitmob/reader/engine_reader.py;
    probes/world-engine/classify.py; exports/world-engine-ontology-rules_v2.json
  knowledge_pipeline/.ledger/ledger.jsonl L2455-L2530; the two earlier review notes in the scratchpad
