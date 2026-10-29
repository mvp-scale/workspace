# Universal Knowledge Pipeline — Product Requirements & Engineering Specification

**Version:** 0.1 · **Date:** 2026-10-29 · **Status:** Proposed architecture + tested bounded reference implementation

**Product objective:** Convert arbitrary incoming information into **incremental, evidence-backed updates** to a persistent knowledge graph, supporting (a) world intelligence and (b) cumulative understanding, while minimizing GPU, LLM, and unnecessary graph growth.

**Scope of proof:** CPU-first normalization, canonical identity linking, limited event/assertion extraction, graph integration, lineage, review, and repeatable evaluation. **Not claimed:** general automatic semantics from arbitrary documents; >80% accuracy; accurate world-state forecasting; direct integration with the existing private repo.

## A. Executive decisions

| Decision | Specification | Why |
|---|---|---|
| Universal interface | Every adapter emits `SourceEnvelope` + ordered `ContentBlock[]` | Independent of modality and channel |
| First-class knowledge | `Anchor`, `Event`, `Assertion`, `Evidence`, `Observation` | Supports both events and timeless technical knowledge |
| Strong join point | **Anchor ID**: persistent identity for entity, concept, capability, process, condition, resource, place | Independent of article, category, alias, or UI location |
| Ticker equivalent | **Track ID** = Anchor + measurable property + scope + definition/unit/method | Prevents mixing news volume and real-world state |
| Graph contract | RDF/Wikidata-inspired qualified statements, mapped to SQLite rows | Interoperable semantics without a new triple-store deployment |
| Processing strategy | Rules/metadata/FTS first; small CPU models for known tasks; LLM only for ambiguity/novelty | Optimize measurable cost/accuracy tradeoff |
| World Engine | Downstream **simulation consumer** of qualified event/state records | Avoid equating a source's assertion with a world fact |
| Navigation | Configurable aggregations over Anchors/Tracks; not immutable ontological levels | The same knowledge appears in many views without duplication |
| Evidence | Every source-derived update requires a source span, provenance, and modality | Auditability and safe deduplication |
| Unknowns | Explicit abstain/review path | A system that cannot abstain will pollute the graph |

### Core vocabulary (fewest concepts with distinct responsibilities)

- **Anchor:** stable identity and definition (e.g., `capability:hybrid-search`, `org:repo-orbit`, `condition:electricity-supply`, `place:new-england`). Has aliases, types, and cross-taxonomy mappings. Its display name can change; ID cannot.
- **Event:** a particular occurrence; SEM-style participants, roles, place, event time, and evidence. Event identity is separate from the number of reports.
- **Assertion:** evidence-backed *subject → predicate → object/value* with modality, valid time, location, qualifiers, contradiction/support relationships, and processing provenance. Assertions may concern an event or an anchor.
- **Observation:** a timestamped value of a defined measurable property, with units and measurement method. SOSA-compatible; not automatically proof of causality.
- **Track:** stable entity+property+scope+measurement-definition joining observations over time (a precise ticker analogue).
- **Evidence:** immutable source segment or media reference supporting, disputing, or merely mentioning an assertion. Record origin/publisher and *independence cluster* separately.
- **View:** computed aggregation/query; Pulse, Area, Understanding, local/business lenses. Does **not** own independent copies of claims.

**Do not conflate:** `Anchor` ≠ `Tag`, `Event` ≠ `Article`, `Assertion` ≠ `Established fact`, `Report count` ≠ `World-state change`, `Model score` ≠ `Calibrated confidence`.

## B. Logical data flow and interfaces

```text
RSS / HTTP / Email / Slack / File / Meeting / Transcript / API / Media
       │   source-specific adapters, auth, source timestamps, ACLs
       ▼
SourceEnvelope + ContentBlocks (text, table, timestamped transcript, image ref)
       │
       ├─ 0. dedupe / fetch / metadata / security / retention
       ├─ 1. segment blocks + preserve offsets
       ├─ 2. cheap tags and known candidates (CPU)
       ├─ 3. detect bounded events, assertions, observations (CPU)
       ├─ 4. link to existing Anchors / Events / Tracks (FTS + candidates)
       ├─ 5. check novelty, attribution, contradiction, evidence coverage
       ├─ 6. escalate uncertain candidates, not entire source (LLM optional)
       └─ 7. verify and commit via existing single writer
       ▼
       Persistent Graph + Evidence + Temporal Observations
       ├─ World Engine adapter: qualified condition deltas / scenarios
       ├─ Index projections: global / local / resources / capabilities
       └─ Knowledge projections: explanations / comparisons / gaps
```

**A pipeline is a logical stage contract, not a mandate for one service per box.** Preserve the existing TypeScript orchestrator and graph writer. Initially, Python/spaCy/Docling can be invoked only as a bounded worker for tasks that justify a language/runtime boundary.

### B1. `SourceEnvelope` v1 — one object per input

```json
{
  "source_id": "rss:publisher-id:article-guid",
  "channel": "rss|web|email|chat|file|meeting|repo|audio|video|api",
  "source_uri": "https://... | mail:... | internal:...",
  "publisher_id": "org:publisher",
  "author_ids": [],
  "sender_id": null,
  "title": "...",
  "published_at": "2026-10-28T14:00:00Z",
  "received_at": "2026-10-28T14:01:00Z",
  "event_time_hint": null,
  "language": "en",
  "content_hash": "sha256:...",
  "media_type": "text/html",
  "visibility": "public|internal|private|restricted",
  "access_policy_id": "acl:...",
  "parser": {"name":"docling|html|imap|...","version":"..."},
  "blocks": [
    {"block_id":"b0","type":"heading|paragraph|table|transcript|image-ref",
     "text":"...","start":0,"end":123,"page":null,"speaker":null,
     "start_time_ms":null,"end_time_ms":null,"original_ref":"..."}
  ]
}
```

**Rules:** metadata timestamps remain distinct from event/observation timestamps. Preserve original content or a retrievable pointer; never replace tables, speech turns, or locations with an unrecoverable flat summary. Nested attachments and document versions get their own source IDs joined by `attached_to` / `supersedes`. Re-ingestion of an identical source ID and content hash is idempotent; a different hash requires a new source version.

### B2. `SemanticCandidate` v1 — output from cheap/learned extraction

```json
{
 "candidate_id": "cand:...", "kind":"anchor_mention|event|assertion|observation|question|action",
 "subject_candidate":"a:energy-supply", "predicate":"decreases",
 "object_candidate":null, "value":200, "unit":"MW",
 "place_candidate":"a:new-england", "event_time":"2026-10-28",
 "modality":"reported|observed|forecast|possible|opinion|decision|request|negated",
 "evidence":{"source_id":"rss-001","block_id":"b1","start":0,"end":96,"quote":"..."},
 "extractor":{"name":"rule.outage.v1","version":"0.1","score":null},
 "resolution":{"anchor_id":null,"status":"pending","candidates":[]}
}
```

Extractor confidence, source trust, corroboration, and world-state certainty are four **different** fields. A statement can have high extraction confidence but poor factual support.

### B3. `KnowledgeUpdate` v1 — writer's only input

```json
{
 "operation":"reinforce|extend|contradict|create|hold|reject",
 "target_type":"anchor|event|assertion|observation|track",
 "target_id":"...", "candidate_id":"...", "evidence_ids":["..."],
 "validator":"rule|small_model|llm|human", "status":"proposed|accepted|disputed",
 "reason_code":"exact_match|same_event|new_property|contradiction|unknown_identity|..."
}
```

**Never permit** a model to write graph rows directly. `verify` enforces schema, type, evidence span, access control, contradiction policy, and ontology versions. The existing single writer performs atomic commits and refreshes materialized views.

## C. Canonical graph schema (minimum practical form)

| Table / entity | Minimum fields / uniqueness | Operational note |
|---|---|---|
| `sources` | source ID, channel, URI, hash, title, sender/publisher, timestamps, ACL | Protect private emails/meetings |
| `content_blocks` | source ID, block ID, text, offsets, page, speaker/time, media ref | Citation traceability |
| `anchors` | immutable ID, kind, label, definition, status, ontology version | Stable strong nodes; no global name-only IDs |
| `anchor_aliases` | normalized alias, language, anchor ID, source, confidence | Candidate retrieval; ambiguous aliases allowed |
| `anchor_edges` | src, predicate, dst, valid time, evidence, status | `broader`, `part_of`, `implements`, `depends_on`; typed constraints |
| `events` | ID, type, participant/role links, time, place, status | One verified event may have many source reports; tentative cross-source matches stay provisional |
| `assertions` | ID, subject, predicate, object/value, qualifiers, modality, valid time | Claims independent of sources |
| `evidence` | assertion/event ID, source block/span, stance, originating speaker/publisher | Multiple references to one claim |
| `tracks` | ID, anchor, property, scope, unit, measurement definition | Stable monitored dimension; do not invent values |
| `observations` | track ID, observation time, value, unit, method, original evidence | Real series separate from model projections |
| `views` | ID, query/rules, user scope, ontology version | No copied prose summaries |
| `review_queue` | candidate, reason, ranked matches, source evidence, triage status | Training-label production channel |
| `model_runs` | extractor/version, data version, latency, outcome, cost | Reproducibility and routing analysis |

**Indexes:** `anchor_aliases(alias)`, SQLite FTS5 on canonical labels/definitions, event fingerprint candidates, evidence by claim/source, tracks by `(anchor_id,property,scope,method)`, observations by `(track_id,event_time)`. Optional vector index only if lexical candidate recall is insufficient.

**Identity and merging:** canonical IDs are not a concatenation of human labels. Merge creates aliases and `merged_into` redirection; retain old source/citation IDs. Multi-domain membership uses edges, not duplicate anchors. Unknown concepts enter as provisional nodes **only after validation**; otherwise remain candidates.

### C1. Three UI projections over the same graph

| Projection | Query | Meaning |
|---|---|---|
| **Macro / Pulse** | `View → related Tracks/Events → qualified aggregates` | What's changing, where? Separate report volume, observations, and inferred risks |
| **Area** | `Anchor → connected events/relations/conditions/capabilities` | Drivers, dependencies, impacted entities, competitive implementations |
| **Understanding** | `Anchor → claims grouped by facet → evidence, comparisons, gaps` | Mechanism, boundaries, what differs, what is contradicted |

**Resource, condition, place, topic, person-state, audience, process** are graph types or configurable view dimensions—not six obligatory levels for every source.

## D. Pipeline stage specifications

| Stage | Input → output | Default CPU method | Failure / escalation |
|---|---|---|---|
| 0 Adapter | channel payload → `SourceEnvelope` | HTTP/RSS/email/Slack/file parsers; Docling for documents | Unsupported media → queued; never silently flatten/delete |
| 1 Triage | envelope → accepted/duplicate/quarantined | content hash, URL canonicalization, MIME signature, near-dup fingerprints | Invalid ACL, oversized, corrupt, prompt-injection text flagged as data |
| 2 Segment | blocks → stable spans | headings, tables, sentences, speaker turns, offsets | Poor extraction → fallback parser / review |
| 3 Classify | spans → multi-label domain + intent/modality | IPTC/known vocabulary; keyword baselines, fastText/textcat | Unknown/low confidence → review or LLM |
| 4 Detect | spans → entity/event/claim/property candidates | dictionary, NER, regex quantities/units, trigger-frame patterns | Unparsed negation, coreference, ambiguous roles → LLM |
| 5 Resolve | candidates → anchor/event/track candidate IDs | exact aliases, FTS5 BM25, optional CPU embeddings, type checks | Unclear identity → abstain; never auto-merge by similarity alone |
| 6 Reconcile | candidate vs graph → proposed update | normalized subject/predicate/value, event fingerprints, support/dispute tests | Mismatched time, attribution, source dependence → review/LLM |
| 7 Verify | proposed update → accepted/hold | evidence offset checks, type constraints, modality checks, provenance, policy | Invalid → reject with reason; uncertain → hold |
| 8 Write | verified deltas → graph + audit | existing single writer transaction | Retry idempotently; no partial multi-table commits |
| 9 Project | changed graph atoms → macro/area/learning caches | incremental SQL aggregation | Derived cache rebuild; source graph remains authoritative |

**Escalation is candidate-scoped** (`span + relevant anchors + conflicting assertions`), not default full-document LLM processing. For sensitive sources, local-only policies can forbid remote escalation entirely.

### D1. Document parsing decision

| Input class | First choice | Escalation |
|---|---|---|
| RSS/HTML/news | structured JSON-LD, feed fields, lightweight HTML extraction | Docling if useful; never OCR normal HTML |
| TXT/Markdown/notes/Slack/email | native text + metadata and conversation/thread boundaries | none for basic extraction |
| Native DOCX/PPTX/office | Docling CPU + structured blocks | complex/unreadable pages to stronger parser |
| Text PDFs | native text extraction; Docling CPU for layout/tables | table/layout fidelity check |
| Scanned PDFs/images | Tesseract/RapidOCR CPU with sampled quality check | Nemotron Parse / GPU VLM only on poor-quality, valuable files |
| Audio/video | ASR/OCR/scene references → transcript blocks with timestamps | GPU/ASR where cost/quality warrants; semantic core unchanged |

**Verified:** Docling supports CPU device/threads and Docling JSON/Markdown output; OCR should be disabled for digital files when not needed. NVIDIA's Nemotron Parse deployment is GPU-oriented, so it is a fallback, not a CPU baseline. Implementation must pin tested versions; this reference does not install them. Sources: https://docling.org/formats , https://docling.org/config-generator/ , https://github.com/docling-project/docling/blob/main/docs/getting_started/installation.md , https://docs.nvidia.com/nim/ingestion/parse/latest/overview.html .

### D2. Extractor plugin API (TypeScript orchestration, Python optional)

```typescript
type SourceEnvelope = {source_id:string; channel:string; visibility:string; blocks:ContentBlock[]; /* metadata */};
type ContentBlock = {block_id:string; type:string; text:string; start:number; end:number; /* location */};
type SemanticCandidate = {kind:string; subject_candidate?:string; predicate?:string;
  object_candidate?:string; value?:string|number; modality:string;
  evidence:{source_id:string; block_id:string; start:number; end:number};
  extractor:{name:string; version:string; score?:number};};
interface Extractor { extract(source:SourceEnvelope, candidates:AnchorCandidate[]): Promise<SemanticCandidate[]>; }
interface Resolver { resolve(candidates:SemanticCandidate[]): Promise<ResolutionDecision[]>; }
interface GraphWriter { commit(updates:KnowledgeUpdate[]): Promise<CommitReceipt[]>; }
```

Use **multiple extractors under the same API**, not one giant model: rules, small NER, multi-label classifier, relation templates, observation parser, and LLM fallback. Track a per-stage model version and cost.

## E. Concrete integration examples (synthetic)

### E1. Two news feeds describe one outage

```
Source 1: Northlight Utility reported a 200 MW outage in New England on Oct 28.
Source 2: Same outage reported by another publisher.
Anchor: org:northlight-utility
Anchor: place:new-england
Event: outage / actor=Northlight Utility / date=2026-10-28 / place=New England
Evidence: [Source 1, Source 2]
Status: reported; independence requires publisher/syndication check
Track: electricity-supply / New England (NO observation produced automatically)
World Engine: proposed candidate impact only, pending measured change/validation
```

**Value:** one provisional event cluster, not two article-level events; evidence retained; identity confirmation required; no invented amount of actual regional change beyond the reported 200-MW outage.

### E2. Repository + meeting + vendor email

```
README: Repo Orbit implements hybrid search.
Anchor: capability:hybrid-search
Anchor: software:repo-orbit
Assertion: repo-orbit --implements--> hybrid-search
README: Hybrid search combines keyword search and vector search.
Assertions: hybrid-search --combines--> keyword-search; vector-search
Meeting: Team Atlas selected Repo Orbit for a pilot.
Assertion: team-atlas --selected--> repo-orbit [decision, time, internal visibility]
Vendor email: "latency is 25ms" → vendor-attributed assertion (NOT measured benchmark)
```

**Value:** one reusable capability explanation; many implementations, adoption decisions, claims, and measured comparisons can accumulate without generating duplicate repository summaries.

### E3. Volcano report (negative/hedged language)

```
Source: "Volcanic ash may disrupt aviation; duration uncertain."
Anchor: phenomenon:volcanic-ash
Anchor: sector:aviation
Assertion: volcanic-ash --may_disrupt--> aviation [possible]
No eruption event recorded; no confirmed disruption; no 4-week duration invented.
```

### E4. User email and meeting commitment

```
Email: "I predict that electricity supply will recover next month."
Assertion: electricity-supply --expected_to_recover--> [forecast, temporal qualifier]
Meeting: "Action: benchmark vector search recall."
Candidate: task / action item with assignee and deadline UNKNOWN → review or action extractor
No state change and no completed work implied.
```

## F. Existing ontology reuse: boundary between standards and real content

| Resource | Load / use | Direct computational benefit | Not provided |
|---|---|---|---|
| IPTC Media Topics | Seed **news** category labels/hierarchy, aliases and mappings | Multi-label CPU classifier target, macro category rollups | Processes, causal effects, all technical capabilities |
| Wikidata | External IDs/aliases, `instance of`, `subclass of`, selected properties | Entity linking and candidate disambiguation; don't mirror full Wikidata | Claims from private docs, complete world mechanism |
| SKOS | Represent label, alias, broader, narrower, related, mapping edges | Multi-parent concept alignment and interoperability | Actual concepts without importing a vocabulary |
| SEM | Event/actor/place/time/role shape | Consistent event fingerprints, repeated-event matching | Non-event knowledge and evidence certainty |
| Wikidata statement pattern | Claim with qualifiers, references, rank | Reconcile time/context-qualified facts instead of overwriting them | Extraction and truth adjudication |
| SOSA | Observation, property, feature, result/time | Comparable Track series and measurement provenance | Automatic causal explanation |
| PROV-O | Agent, activity, entity, wasDerivedFrom | Processing lineage, source/citation trail | Meaning and correctness |

Only import the subset that improves one measurable operation. No RDF migration required at v0.1. Source references: https://iptc.org/standards/media-topics/ , https://www.wikidata.org/wiki/Wikidata:Data_model , https://www.w3.org/TR/skos-reference/ , https://www.w3.org/TR/prov-o/ , https://www.w3.org/TR/vocab-ssn/ .

## G. Models: CPU-first routing, training, evaluation

### G1. Candidate execution plan (not benchmark claims)

| Task | Baseline | Learned alternative | Do not use for |
|---|---|---|---|
| Source classification | metadata + IPTC lexical tags | fastText (multi-label), spaCy textcat, sklearn linear model | Novel causal claims |
| Known entity/capability mentions | aliases, spaCy EntityRuler, regex | spaCy NER, GLiNER CPU/ONNX when justified | Identity adjudication without retrieval |
| Bounded event trigger / roles | dependency/pattern templates | spaCy trained SpanCat/NER + role classifier | Open-world semantic events without abstention |
| Values/time/units | regex, unit library, date parser | targeted sequence tagging when needed | Inferred numeric outcomes |
| Candidate retrieval | alias + SQLite FTS5 | small ONNX embedding model (CPU) | Automatic merge based on cosine alone |
| Relation typing | typed patterns + existing graph constraints | small supervised relation classifier | Unseen relationships without validation |
| Novelty/contradiction | normalized candidates + evidence compare | local NLI classifier; LLM on unresolved | Concluding truth from agreement between copied publishers |
| Concept discovery and explanation | no CPU promise | selective LLM with constrained schema | Unreviewed canonical merges |

**Tool selection rule:** start with a deterministic parser and an error profile. Add a learned model only where it improves a specific measured acceptance test at acceptable cost/latency. Choose **one** fast NLP framework as the primary runtime after benchmark: spaCy (Python and training infrastructure) versus winkNLP (Node-native throughput). Avoid running spaCy, winkNLP, and compromise on every input.

### G2. Training-data pipeline

1. **Sampling:** stratified by `channel × language × domain × length × novelty × provenance × modality`; hold out publishers, time ranges, and entities to test generalization. Include negative and overlapping cases.
2. **Labels:** domain/topic multi-label; entity mentions with spans; resolved anchor IDs; event trigger and participants/roles; subject-predicate-object; modality/negation; time/scope; evidence span; integrate action (`reinforce/extend/contradict/new/hold`).
3. **Annotation source:** existing verified claim/quote pairs are *weak labels*, not ground truth. Human review adjudicates independently, including cases from the abstention queue. Preserve annotator agreement and disagreements.
4. **Dataset control:** immutable split manifests (`train/dev/test`), versioned ontology and source IDs, publisher-cluster decontamination; no same-event leak across splits.
5. **Train:** fastText for domain multi-label; spaCy span/NER for entities and events; linear relation/mode classifiers; optional small ONNX encoder for candidate ranking. Compare to zero-model lexical baseline.
6. **Calibrate routing:** validation threshold by task/type; select operating points with high precision and explicit abstention. Calibration scores are not the source's factual reliability.
7. **Active learning:** prioritize samples where models disagree, unresolved cross-links are frequent, or predicted impact is high. Human accepts/rejects candidate; feed back into next dataset version.
8. **Promote:** shadow-mode evaluation → canary writer rules → production. Roll back by model version and event ledger.

### G3. Gate metrics and acceptance

**Accuracy targets are proposed product requirements, not observed scores.** Assess separately for English news and for each subsequent source/language; do not pool easy RSS with hard OCR.

| Gate | Required measure | Initial target / block |
|---|---|---|
| Structural intake | metadata completeness, content-block fidelity | ≥99% valid envelopes on supported formats; zero silent losses |
| Source traceability | every committed update has resolvable evidence span/media pointer | **100%** or block write |
| Known-anchor linking | Precision, recall, F1; ambiguous alias resolution | Precision ≥0.90 and recall ≥0.80 on held-out items; abstain otherwise |
| Domain classification | multi-label micro/macro F1, per-category confusion | F1 ≥0.80; minor labels examined individually |
| Event extraction | trigger + actor + time/place role-level F1 | ≥0.80 on held-out explicitly in-scope event families |
| Assertion relation extraction | exact subject/predicate/object + modality correctness | ≥0.80 F1 on supported predicates; false assertions blocked |
| Cross-source event clustering | pairwise precision/recall and event B-cubed | Precision ≥0.95 before automatic merge |
| Novelty decisions | false-merge rate, missed-new-claim rate, contradictions | No automatic merges below verified threshold; target false-merge <1% |
| State measurement | valid unit/time/scope/method, observational provenance | 100% complete for accepted observations |
| Cost / throughput | p50/p95 stage latency, items/sec/core, RAM, CPU cost/item | Benchmark against actual existing 2–30ms fast classifier; no claimed budget yet |
| LLM escalation | share of items/spans, $ per accepted update, quality improvement | Decrease cost at matched quality; track by domain and source |

**Do not report a single “80% extraction accuracy” number.** A system could have 95% NER but low claim recall and bad event identity merging. Evaluate complete graph updates as end-to-end outcomes as well.

### G4. Proposed production benchmark protocol

- Minimum pilot: 200–500 *human-reviewed* mixed items; include hard positives, negations, quoted claims, duplicate syndicated coverage, correction articles, mixed-company technical documents, internal source visibility.
- Separate **holdout**: 20–30% by event/publisher/time cluster (not random sentences from one story).
- Test variants: `existing`, `CPU exact+rules`, `CPU trained`, `CPU+embeddings`, `CPU+selective LLM`, `full LLM comparator`.
- Report `source conversion failure`, `stage recall`, `graph delta precision`, `end-to-end useful update`, `false merge`, `novel gap identification`, p50/p95 latency, RSS, energy if measured, API calls, $/item, $/correct graph update.
- Review every proposed high-impact condition change and every automatic new ontology type before accepting promotion.

## H. World Engine integration — precise contract

Existing model: 48 world topics + `other`, 39 conditions, 47 person states, 20 decisions, 26 resources, place/audience projections. Its link coefficients and half-lives are currently **hand-set and unvalidated**; its outputs are simulations. Source: the user's `World engine: the ontology and how information flows through it`, dated 2026-10-29.

Writer emits only validated structured facts to an adapter:

```json
{
 "world_input_id":"...", "event_id":"...", "anchor_id":"condition:energy-cost-supply",
 "place_id":"place:new-england", "direction":"up|down|unknown",
 "observation_ids":[], "source_assertion_ids":["..."],
 "support_status":"observed|reported|predicted|disputed",
 "size":null, "unit":null, "time":"...", "quality_flags":["unmeasured_impact"]
}
```

- `unknown` direction must not be coerced to `up`.
- A reported outage does not establish a numerical regional supply change.
- Source assertion, observed measurements, simulated impact, and user prediction remain separate records/series.
- World conditions may map many-to-many to external IPTC topics and internal knowledge anchors.
- Audience and person-state outputs are scenario/interpretation projections, not observed population reactions.
- Pulse displays at least three distinguishable indicators: **report activity**, **validated observations**, and **modeled risk/scenario**. Calibration begins only when historical observation series exist.

## I. Implementation sequence, deliverables, and stop conditions

| Sprint | Build | Test / exit |
|---|---|---|
| 0. Instrument | Baseline existing processing stages, annotate 200–500 samples, freeze evaluation schema | Can reproduce current graph updates and measure failure/latency |
| 1. Universal envelope | Adapters emit blocks+metadata+ACLs; Docling CPU trial; source IDs/hash | Source import is idempotent, block offsets complete, parsing losses visible |
| 2. Anchor resolution | aliases, FTS5 candidates, one-hop graph priors, event fingerprints | Held-out link precision ≥0.90 or abstain; no unreviewed new IDs |
| 3. CPU extractors | multi-label taxonomy, entities, bounded event/statement templates | Per-task F1/latency measured; retraining reproducible |
| 4. Hybrid reconciliation | targeted LLM escalation, provenance/contradiction checks, atomic graph write | Decrease cost per correct delta versus full LLM without worsening false merges |
| 5. UI + World | dynamic Pulse/Area/Understanding, condition adapter, temporal tracks | Drill down from every displayed movement to evidence; source-count ≠ impact |

**Do not start** GPU migration, a new graph database, full ontology ingestion, 100k-person model calibration, or large-scale fine-tuning before these acceptance gates justify them.

## J. Reference implementation provided

Archive: `knowledge_pipeline_poc.zip` (Python standard library + SQLite; no network; synthetic fixtures). Includes:

- `normalize_file.py`: optional native TXT/Markdown/HTML/EML adapter; Docling CPU path for documents (not installed/tested here).
- `cpu_pipeline.py`: sources → anchor mentions → one provisional outage-event cluster → statements → evidence and review queue.
- `config/anchors.json`: 12 explicit seed anchor IDs.
- `fixtures/inputs.jsonl`: six synthetic RSS, repo, meeting, email, and document examples.
- `tests/test_pipeline.py`: ten automated tests of idempotency, provenance spans, event/evidence de-duplication, modalities, bounded linking, unknown handling.
- `outputs/demo.sqlite`: observed example result from the executed script.

**Actual executed reference output:** 6 sources; 12 seeded anchors; 19 anchor mentions; 1 provisional event candidate linked to 2 different source records; 6 assertions; 8 unresolved sentences queued for review; 10/10 implementation integrity tests passed. This validates **data flow/invariants on synthetic examples only**, not extraction accuracy or CPU throughput on real feeds.

Run from extracted archive:

```bash
python3 cpu_pipeline.py --db outputs/demo.sqlite --input fixtures/inputs.jsonl
python3 cpu_pipeline.py --db outputs/demo.sqlite --show
python3 normalize_file.py my_notes.md --output fixtures/local.jsonl
python3 -m unittest discover -s tests -v
```

**Integration boundary:** the POC consumes already-normalized text, not raw PDFs or Slack APIs; Docling and Nemotron paths are designed but not installed or performance-tested here. Real adapter wiring requires access to the existing repository and machine profile. The reference is a working spike and migration target, **not a drop-in production replacement**.

## K. Open technical risks / decisions

1. **Current graph alignment:** existing `app/novelty.ts`, `app/merge.ts`, `tagger-meaning.ts` may already outperform an isolated baseline; benchmark before replacement.
2. **Multiple claims in one sentence:** sentence segmentation is not extraction; support span-level labels and multi-candidate emissions.
3. **Independent corroboration:** article count and publisher count are insufficient if articles syndicate the same source.
4. **Ambiguous topics and labels:** multiple domains and synonyms; use identifier-based mapping and `unknown` state.
5. **Multilingual/global coverage:** language-specific test sets and model routing; no English-only metric passes as global readiness.
6. **Privacy:** individual email/Slack permissions propagated to all derived evidence and materialized views; private data never used for general model training without authorization.
7. **Graph evolution:** novel types are provisional, ontology versions are maintained, merges are reversible, and aggregation avoids double-counting.
8. **Source security:** fetched or pasted text is untrusted. Extract instructions as data, do not execute them or let them override pipeline policy.

### Official technical references

- Docling supported formats and CPU configuration: https://docling.org/formats and https://docling.org/config-generator/
- Docling structured export: https://github.com/docling-project/docling/blob/main/docs/v2.md
- NVIDIA Nemotron Parse serving: https://docs.nvidia.com/nim/ingestion/parse/latest/overview.html
- spaCy rule matching: https://spacy.io/usage/rule-based-matching
- winkNLP: https://github.com/winkjs/wink-nlp
- fastText supervised text classification: https://github.com/facebookresearch/fastText/blob/main/docs/supervised-tutorial.md
- Sentence Transformers ONNX CPU inference: https://www.sbert.net/docs/sentence_transformer/usage/efficiency.html
- SQLite FTS5 / BM25: https://www.sqlite.org/fts5.html
- IPTC Media Topics: https://iptc.org/standards/media-topics/
- Wikidata statement model: https://www.wikidata.org/wiki/Wikidata:Data_model
- SKOS, PROV-O, SOSA: https://www.w3.org/TR/skos-reference/ , https://www.w3.org/TR/prov-o/ , https://www.w3.org/TR/vocab-ssn/
