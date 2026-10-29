# Universal Knowledge Pipeline — Product Requirements & Engineering Specification

**Version:** 0.2 · **Date:** 2026-10-29 · **Status:** Proposed architecture + tested bounded reference implementation, revised with measured results from the world-engine news classifier (repo `world-engine-news-classifier`, ledger L1–L411)

**Product objective:** Convert arbitrary incoming information into **incremental, evidence-backed updates** to a persistent knowledge graph, supporting (a) world intelligence and (b) cumulative understanding, while minimizing GPU, LLM, and unnecessary graph growth.

**Scope of proof:** CPU-first normalization, canonical identity linking, limited event/assertion extraction, graph integration, lineage, review, and repeatable evaluation. **Not claimed:** general automatic semantics from arbitrary documents; >80% accuracy; accurate world-state forecasting; direct integration with the existing private repo.

### What changed in v0.2

v0.1 designed the pipeline from first principles. The news-classifier project has since built and measured stages 2–4
for English news. v0.2 keeps v0.1's architecture and vocabulary and changes it where measurements disagree:

1. **LLMs moved from runtime fallback to training-time teacher** (A, G2). The working path is LLM labels → small
   CPU student, not rules first with a per-item LLM fallback. Runtime LLM escalation remains for novelty only.
2. **One shared encoder with many heads**, not one model per task (A, D2, G1). Separate models each re-read the
   text; cost adds up per model. Rules and plugins keep the `Extractor` API, but learned extractors share one pass.
3. **Accuracy gates are tied to measured human agreement** (G3). A fixed ≥0.80 F1 is above what two careful
   annotators reach on some layers (event nouns: two LLM judge families agree at F1 .38, κ .27). Gate = 0.8 × IAA,
   judged on the lower 95% bound, with a frozen, hashed scorer.
4. **Real throughput numbers and a budget** (G3, new M). The "2–30 ms" figure was per 254-token model call, not per
   article. A typical article costs 228 ms wall / 0.68 vCPU-s today; 3,000–4,000 items/min needs ~40 vCPU or ~10×
   less work per item.
5. **Measured tool choices** (G1). GLiNER zero-shot, OpenVINO and spaCy-everywhere were benchmarked on our data;
   results replace the open "after benchmark" choices.
6. **Copyright-safe evidence** (B1, C). Public articles are publishers' copyright: store offsets and pointers,
   short quotes only, and never use article text in public outputs or model releases.
7. **New section L** maps every PRD stage to what already exists, its score, and the gap; **M** gives the per-stage
   time budget.

## A. Executive decisions

| Decision | Specification | Why |
|---|---|---|
| Universal interface | Every adapter emits `SourceEnvelope` + ordered `ContentBlock[]` | Independent of modality and channel |
| First-class knowledge | `Anchor`, `Event`, `Assertion`, `Evidence`, `Observation` | Supports both events and timeless technical knowledge |
| Strong join point | **Anchor ID**: persistent identity for entity, concept, capability, process, condition, resource, place | Independent of article, category, alias, or UI location |
| Ticker equivalent | **Track ID** = Anchor + measurable property + scope + definition/unit/method | Prevents mixing news volume and real-world state |
| Graph contract | RDF/Wikidata-inspired qualified statements, mapped to SQLite rows | Interoperable semantics without a new triple-store deployment |
| Processing strategy | Rules/metadata/FTS first; small CPU models for known tasks; LLM only for ambiguity/novelty | Optimize measurable cost/accuracy tradeoff |
| Learned extraction | **Distillation:** LLM teachers label offline (two model families + human-reviewed gold); a ~20M-parameter int8 ONNX student runs at inference | Measured: the student passes event-verb and trigger gates against a two-family LLM consensus, at 0 $/item and no GPU at inference (L, T61–T68) |
| Runtime shape | **One shared encoder pass per text window, many task heads** (spans, topic, POS, coreference merge) + cheap rules | Each extra standalone model multiplies per-item cost; the encoder is over half of article time |
| Quality gates | 0.8 × measured inter-annotator agreement per layer, lower 95% bound, frozen scorer (sha-pinned) | A target above human agreement can't be met or verified; a frozen scorer stops goalpost drift |
| Decision record | Append-only ledger: tasks with definition of done, stop rules, results, owner decisions | Every number on a dashboard traces to a run; reversals are visible |
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

**Copyright and retention:** text from public publishers is their copyright. Store `content_blocks.text` only where licence/retention policy allows; otherwise store offsets + `content_hash` + `source_uri` and re-fetch on demand. Evidence quotes are short (≤ 1 sentence). Never publish corpus text, training windows, or model outputs that quote it on public sites, public datasets, or public model cards; training datasets stay private.

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

**Existing producer.** The shipped news classifier already emits a document in schema 2.0.0 (`zones`, `mentions`,
`entities`, `events` with `trigger` and `assertion{tense, polarity, realis, modality}`, plus empty `claims`,
`relations`, `attributions`, `conditions`) and a flat `layers` view (ENTITY, EVENT_VERB, EVENT_NOUN, triggers,
TIME, QUANTITY as `{start,end,text}`). Map it to `SemanticCandidate` rather than inventing a second format:
ENTITY mention → `anchor_mention`; event trigger → `event` (participants empty until a role head exists);
TIME/QUANTITY → `event_time` / `value`+`unit` of an `observation` candidate. Today `extractor.score` is null
(argmax decoding) and the assertion fields are defaults, so modality is **not** yet learned; see L.

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
| `content_blocks` | source ID, block ID, text (or pointer where licence forbids storage), offsets, page, speaker/time, media ref | Citation traceability; copyright policy in B1 |
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
| `model_runs` | extractor/version, model file sha, data version, scorer sha, latency, outcome, cost | Reproducibility and routing analysis; a run without a scorer sha can't gate |

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
| 3 Classify | spans → multi-label domain + intent/modality | IPTC/known vocabulary; keyword/TF-IDF baseline; **encoder head** (measured: IPTC L1 macro F1 .86 vs TF-IDF .79; 29 world topics .76–.80, top-3 router recall .97) | Unknown/low confidence → review or LLM |
| 4 Detect | spans → entity/event/claim/property candidates | **distilled student** (entity, event verb/noun, time, quantity spans; F1 .70–.94 by layer) + regex/date rules for time and quantity values | Unparsed negation, coreference, ambiguous roles → review queue → teacher labels → next student |
| 5 Resolve | candidates → anchor/event/track candidate IDs | exact aliases, FTS5 BM25, optional CPU embeddings, type checks | Unclear identity → abstain; never auto-merge by similarity alone |
| 6 Reconcile | candidate vs graph → proposed update | normalized subject/predicate/value, event fingerprints, support/dispute tests | Mismatched time, attribution, source dependence → review/LLM |
| 7 Verify | proposed update → accepted/hold | evidence offset checks, type constraints, modality checks, provenance, policy | Invalid → reject with reason; uncertain → hold |
| 8 Write | verified deltas → graph + audit | existing single writer transaction | Retry idempotently; no partial multi-table commits |
| 9 Project | changed graph atoms → macro/area/learning caches | incremental SQL aggregation | Derived cache rebuild; source graph remains authoritative |

**Triage before Detect (new requirement for throughput).** A sub-millisecond router (static embeddings or linear model) decides per item: skip, metadata-only, topic-only, or full extraction. Every skipped item saves the full ~0.7 vCPU-s. Router recall on items that matter is gated like any other stage.

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

Use **multiple extractors under the same API**, not one giant model: rules, multi-label classifier, relation templates, observation parser, and LLM fallback. **But learned extractors share one encoder:** a single forward pass per 254-token window feeds several heads (spans, topic, POS, coreference merge), exposed as separate `Extractor`s that read a shared `EncodedSource` cache. Adding a head costs milliseconds; adding a standalone model costs another full pass. Track a per-stage model version and cost.

**Runtime portability (measured).** The same int8 ONNX file runs in Python/ONNX Runtime on servers and in browsers via onnxruntime-web (live demo: one browser thread, ~100 ms for a short article). That makes a local-only path for private email/meeting sources possible without a server round trip. JavaScript runtimes use the same ORT engine, so they don't make server throughput faster.

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

### G1. Execution plan, updated with measured results

**Measured on our data** (Kaggle CPU, 4 vCPU Xeon 2.2 GHz; quality = frozen scorer on human-reviewed news; ledger L393, L407–L411):

| Option | Quality (entity overlap / exact F1) | Cost | Verdict |
|---|---|---|---|
| Distilled student v2 (19.2M, int8 ONNX) + spaCy rules | .88 / .73 | 514 ms/article on that box (228 ms on a faster one) | **Ship** |
| GLiNER bi-edge v2.0 (61M, zero-shot) | .72 / .34 (precision 1.0, recall .56) | 2.9× slower | Teacher / bootstrap only |
| GLiNER2 base (205M, zero-shot) | .70 / .34 | 13× slower | Teacher only |
| GLiNER small int8 ONNX | .36 / .18 | 3.3× slower | Reject: quantization broke it |
| Ettin-17M encoder, int8 | not trained yet | 0.57× our encoder per window | Candidate backbone for student v3 |
| OpenVINO vs ONNX Runtime | same outputs | no gain fp32; slower int8 without VNNI; can't load ORT-fused int8 | Drop unless target CPU has VNNI/AMX |
| spaCy lg as shipped / tagger-only / wink-nlp POS | — | 102 / 55 / 5.5 ms per article | Tagger-only now; remove spaCy in v3 |

Quality on two articles (168 entities) separates large gaps only.

**Execution plan by task:**

| Task | Baseline | Learned alternative | Do not use for |
|---|---|---|---|
| Source classification | metadata + IPTC lexical tags | fastText (multi-label), spaCy textcat, sklearn linear model | Novel causal claims |
| Known entity/capability mentions | aliases, EntityRuler, regex | distilled student span head (shipped); typed head next (actor/place/resource/topic, currently untyped) | Identity adjudication without retrieval |
| Bounded event trigger / roles | dependency/pattern templates | student trigger heads (verbs F1 .91, nouns .70); role head next | Open-world semantic events without abstention |
| Values/time/units | regex, unit library, date parser (shipped rules: TIME .97, QUANTITY .83) | student span head finds them (.94/.83); rules normalize values | Inferred numeric outcomes |
| Candidate retrieval | alias + SQLite FTS5 | small ONNX embedding model (CPU) | Automatic merge based on cosine alone |
| Relation typing | typed patterns + existing graph constraints | small supervised relation classifier | Unseen relationships without validation |
| Novelty/contradiction | normalized candidates + evidence compare | local NLI classifier; LLM on unresolved | Concluding truth from agreement between copied publishers |
| Concept discovery and explanation | no CPU promise | selective LLM with constrained schema | Unreviewed canonical merges |

**Tool selection rule:** start with a deterministic parser and an error profile. Add a learned model only where it improves a specific measured acceptance test at acceptable cost/latency. **Decided by benchmark:** no general NLP framework on the hot path long-term. spaCy stays in tagger-only mode until the student learns POS; winkNLP is 18× faster but its tag accuracy is unverified, so it is not adopted. Don't run spaCy, winkNLP and compromise on the same input.

### G2. Training-data pipeline

1. **Sampling:** stratified by `channel × language × domain × length × novelty × provenance × modality`; hold out publishers, time ranges, and entities to test generalization. Include negative and overlapping cases.
2. **Labels:** domain/topic multi-label; entity mentions with spans; resolved anchor IDs; event trigger and participants/roles; subject-predicate-object; modality/negation; time/scope; evidence span; integrate action (`reinforce/extend/contradict/new/hold`).
3. **Annotation source:** existing verified claim/quote pairs are *weak labels*, not ground truth. Human review adjudicates independently, including cases from the abstention queue. Preserve annotator agreement and disagreements.
4. **Dataset control:** immutable split manifests (`train/dev/test`), versioned ontology and source IDs, publisher-cluster decontamination; no same-event leak across splits.
5. **Train by distillation (the measured path):**
   - Write the annotation guideline first; measure agreement between two LLM judge families and against human gold.
     Low agreement (κ < .4) means the definition is unclear: fix the guideline before labelling at scale
     (evidence: LLM-assisted guideline rewrites lifted human agreement .59 → .84, Bibal et al. 2025).
   - Teacher labels: run two model families (e.g. Haiku + Qwen) on the training pool; keep their consensus, route
     disagreements to review.
   - Student: fine-tune a small encoder with one head per layer, int8-quantize, check quantized vs fp32 agreement
     on dev before touching the test set, then score once on gold with the frozen scorer.
   - Compare against the zero-model lexical baseline and against each teacher alone.
6. **Calibrate routing:** validation threshold by task/type; select operating points with high precision and explicit abstention. Calibration scores are not the source's factual reliability.
7. **Active learning:** prioritize samples where models disagree, unresolved cross-links are frequent, or predicted impact is high. Human accepts/rejects candidate; feed back into next dataset version.
8. **Promote:** shadow-mode evaluation → canary writer rules → production. Roll back by model version and event ledger.
9. **Record:** each training or evaluation run is a ledger task with a definition of done and a stop rule written before it runs (e.g. "stop after 2 variants if neither beats baseline on dev"). No result is reported without its model sha, data manifest and scorer sha.

### G3. Gate metrics and acceptance

**Accuracy targets are proposed product requirements, not observed scores.** Assess separately for English news and for each subsequent source/language; do not pool easy RSS with hard OCR.

**How a target is set (v0.2):** gate = 0.8 × inter-annotator agreement (IAA) for that layer on that source type,
and the candidate passes only if the **lower bound of its 95% bootstrap interval** (resampling articles) clears the
gate. Where IAA hasn't been measured, the fixed targets below are provisional. Where IAA is low, the gate can't be
judged and the guideline is the work item. Measured example: event verbs/triggers pass with lower bounds .87–.96
against gates .54–.75; event nouns fail (.33 vs .65) because the two judge families agree only at .38.

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
| Cost / throughput | p50/p95 stage latency, items/sec/vCPU, RAM, CPU cost/item | Goal 3,000–4,000 items/min (50–67/s). Measured today: 0.68 vCPU-s and 228 ms wall per typical article (30 ms per 254-token model call); 4.8–5.9 articles/s on 4 vCPU. Budget per stage in M; owner to fix vCPU count and $/million items |
| LLM escalation | share of items/spans, $ per accepted update, quality improvement | Decrease cost at matched quality; track by domain and source |

**Do not report a single “80% extraction accuracy” number.** A system could have 95% NER but low claim recall and bad event identity merging. Evaluate complete graph updates as end-to-end outcomes as well.

### G4. Proposed production benchmark protocol

- Staged gold: start with **20–30 fully human-reviewed items** to measure IAA and set gates (our first 2 human-checked + 11 silver articles were enough to find large gaps, not small ones), then grow to the pilot.
- Minimum pilot: 200–500 *human-reviewed* mixed items; include hard positives, negations, quoted claims, duplicate syndicated coverage, correction articles, mixed-company technical documents, internal source visibility.
- Separate **holdout**: 20–30% by event/publisher/time cluster (not random sentences from one story).
- Test variants: `existing`, `CPU exact+rules`, `CPU distilled student`, `CPU+embeddings`, `CPU+selective LLM`, `full LLM comparator`, and a **multi-LLM consensus ruler** (two model families) as the scalable reference between human gold rounds.
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
| 3. CPU extractors | multi-label taxonomy, entities, bounded event/statement templates | Per-task F1/latency measured; retraining reproducible. **English news: largely done** (topic encoder; student v2 spans). Remaining: entity types, roles, modality, coreference merge head, student v3 without spaCy |
| 4. Hybrid reconciliation | targeted LLM escalation, provenance/contradiction checks, atomic graph write | Decrease cost per correct delta versus full LLM without worsening false merges |
| 5. UI + World | dynamic Pulse/Area/Understanding, condition adapter, temporal tracks | Drill down from every displayed movement to evidence; source-count ≠ impact |

**Already learned, so reorder:** Sprint 0's gold set and frozen scorer exist for news; Sprint 3 exists for news spans. The highest-value next work is Sprint 2 (anchor resolution: nothing links mentions to IDs yet) and the event-noun guideline fix. GPU is needed only for training students (local RTX 3090/5090 by default; Kaggle 30 h/week, RunPod or Google credits for bursts), never for inference.

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
9. **Unclear definitions look like model error.** Low scores on a layer can be a guideline problem (event nouns). Check judge-vs-judge agreement before spending GPU on a better model.
10. **Small gold sets.** 2–11 checked articles separate large gaps only; report intervals, not point scores.
11. **Throughput gap.** Present cost is ~10× the per-machine goal; the levers are triage, one shared encoder, a smaller backbone, and removing spaCy, not a faster runtime.
12. **Model release.** Weights trained on publisher text are shipped in a public browser demo; confirm this is acceptable before a public model card or redistribution.

## L. Overlap map: this PRD vs what the news-classifier project already built

Scores are overlap F1 on 11 human-checked English news articles (model-only unless noted), frozen scorer sha ffefe369.

| PRD stage / object | What exists | Measured | Gap to PRD |
|---|---|---|---|
| 0 Adapter / `SourceEnvelope` | Article text in; `article_id`, `doc_date`; zones from sentence split | — | No envelope, channels, ACLs, blocks with page/speaker; build per B1 |
| 1 Triage | Topic router (top-3 recall .97) | — | Dedupe, near-dup, skip router for throughput (D) |
| 2 Segment | Sentence split + zones; 254-token windows, stride 192 | — | Map windows/zones to `content_blocks` |
| 3 Classify | Topic encoder: IPTC L1 and 29 world topics | IPTC L1 macro F1 .86 (TF-IDF .79); world topics .76–.80 | Merge into the shared encoder as a head; intent/modality not built |
| 4 Detect: anchor mentions | Student ENTITY span head | .88 overlap / .73 exact | Untyped (actor/place/resource/topic all 0); no aliases |
| 4 Detect: events | EVENT_VERB, EVENT_NOUN heads → triggers | verbs .91, nouns .70, triggers .79; vs consensus ruler: verbs/triggers pass gates, nouns fail | No participants/roles, no event type, no modality (defaults) |
| 4 Detect: observations | TIME, QUANTITY (rules in ship, student spans) | rules .97/.83; student .94/.83 | Values not normalized into Track/Observation rows |
| Coreference | Haiku coreference labels test (T68 B) | passed trigger-F1 test | Needs merge head + 1,000-article labels (~$0.4) |
| 5 Resolve / anchors | — | — | **Biggest gap:** no anchor IDs, aliases, FTS5, Wikidata/Mordecai place linking |
| 6 Reconcile / events across sources | — | — | Event fingerprints, clustering, novelty: not started |
| Direction (World Engine `direction`) | Survey only: PLOVER/Goldstein/POLECAT (licences unchecked) | — | Build: direction head trained from teacher labels |
| 7–8 Verify / Write | Ledger (append-only, checked) for project decisions | — | Graph writer is the TypeScript app's; not connected |
| `model_runs` / lineage | Kaggle kernels with frozen sha checks; ledger tasks with DoD | frozen-sha checks in each gate kernel | Port fields to `model_runs` |
| Evaluation | E-silver (11), human gold (2), multi-LLM consensus (205), frozen scorer, 0.8×IAA gates | see above | Grow human gold to 20–30, include email/non-news |
| Runtime | `we_classifier.py` (Python, 4 processes); browser ONNX demo | 4.8–5.9 articles/s on 4 vCPU | ~10× short of goal per machine (M) |

## M. Throughput budget (English news, per typical article)

Goal: 3,000–4,000 items/min. On a 4-vCPU box that is 50–67 items/s, about 60–80 vCPU-ms per item.

| Stage | Today (measured, wall ms) | v0.2 plan | How |
|---|---|---|---|
| Triage router | — | ~1 | static-embedding/linear skip; every skip saves the rest |
| Encoder (student) | 128 | ~55–75 | Ettin-17M backbone (0.57× per window), batching, 2–4 layers |
| spaCy | 57 | 0 | tagger-only now (−47 ms); student learns POS in v3 |
| Time/quantity rules | 19 | ~10 | regex only, on student spans |
| Assemble | 20 | ~10 | drop schema-doc building on the hot path |
| **Total** | **~228 ms, 0.68 vCPU-s** | **~80–100 ms** before triage | ≈2.5–3× from engineering; the rest from triage skip rate and machines |

**Decision needed (owner):** target hardware (vCPU count), $/million items, and per-layer quality floors. The
project ledger still records ≥10 articles/s; the stated goal is 50–67/s.

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
- Guideline rewriting and annotator agreement (Bibal et al., CoMeDi 2025): https://preview.aclanthology.org/setup/2025.comedi-1.13
- ONNX Runtime Web: https://onnxruntime.ai/docs/tutorials/web/
- GLiNER: https://github.com/urchade/GLiNER · Ettin encoders: https://huggingface.co/jhu-clsp
- Wikidata statement model: https://www.wikidata.org/wiki/Wikidata:Data_model
- SKOS, PROV-O, SOSA: https://www.w3.org/TR/skos-reference/ , https://www.w3.org/TR/prov-o/ , https://www.w3.org/TR/vocab-ssn/
