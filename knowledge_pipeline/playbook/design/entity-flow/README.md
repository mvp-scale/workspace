# Entity-flow bundle

A tool-neutral description of the knowledge pipeline as a process (13 stages, 3 clocks) and the entities that flow through it, plus a portable JSON bundle of two real areas. It is the data model a presentation layer can be built on; it says nothing about presentation. Everything is PROVISIONAL (the pipeline marks its own output so).

| File | What |
|---|---|
| `process-flow.md` | stages in order, per-stage in/out types, module, clock, timing, status; Mermaid flowchart and ER diagram |
| `entity-model.md` | every entity: id scheme, fields with real examples, relations, creator/updater stage, coverage on c1 and mix, quality issues, field-name mapping |
| `entity-flow.schema.json` | JSON Schema 2020-12 of the bundle |
| `export-bundle.py` | builds a bundle from the running bench (read-only GETs, stdlib only) |
| `validate-samples.py` | schema check (needs `jsonschema`; `python3` has 4.26.0) plus id-reference checks |
| `sample-c1.json`, `sample-mix.json` | bundles for the two staged areas (1.4 MB and 1.7 MB) |

## Regenerate

```
cd /workspace/knowledge_pipeline/playbook/design/entity-flow
python3 export-bundle.py c1        # or mix, or any key from GET :18770/api/raw/areas
python3 export-bundle.py mix --max-bytes 2000000
python3 validate-samples.py
```
Needs the bench at `http://127.0.0.1:18770` (override with `--base`). About 10 s per area. The bundle is cut to the size cap by capping fragments (25 per article) and timeline lines (60 per concept); what was dropped is in `meta.dropped`. No hosted calls, no writes outside the folder.

## Solid, partial, missing

- **Solid (built, data on every row):** publisher and owner, article with read depth and labels, fact with evidence sentences and independent-owner count, per-article triage (one change per article), dated timeline lines, per-area counters and growth.
- **Partial:** fragments (two unaligned claim lists; capped), entities (typing errors; synthesised `did` text broken; drivers are mostly time order), links (about half or more are resource co-occurrence), contests (6 pairs, one event, in mix only; none in c1), classification (several heads not attached).
- **Missing:** Macro Pulse `(V, dV, N, C, U)` with coverage and freshness (only raw inputs exist), story/thread entity, processing timestamp, source intake metadata (tenant, language, hash), ontology evolution output (`evolved.json` not exported), a typed effect on resource links, direction.

## Questions a presentation layer can answer

| Question | Answered by | Caveat |
|---|---|---|
| What changed since time T? | `changes[]` with `articles[].published` (filter on seq or day); `facts[].first_day`; `meta.growth` (cumulative per seq) | time is article publish day, not processing time; `facts[].is_new` is always true in one window |
| What did each new article add? | `changes[].verdict`, `change_text`, `touched`, `concept_changes[]` | 29 of 34 c1 articles are plain updates |
| How many independent owners back a fact? | `facts[].independent_owners`, `independent_sources[]`, `collapsed_copies`; owners via `publishers[].owner` | 93% of facts have one owner |
| Which facts are well backed? | `facts[].is_reinforced` (2 or more owners), `entities[].certainty_word` | 38 (c1) / 40 (mix) reinforced |
| Who disputes whom? | `contests[]` (`sides[].speakers`, `quote`, `outcome`, `targets`); `entities[].state = contested`, `opponents[]` | mix only; one event |
| What happened to X, in order? | `timeline[]` by `concept`, sorted by `day`, `seq`; `entities[].did[]` | `did.text` is unreliable, use `sentence` |
| Why did it happen? | `entities[].drivers[]` with `marker`; `facts[]` with predicate `cause`, evidence sentences | mostly time order; treat as weak |
| What is it connected to? | `links[]` (`rel`, `owners`, `certainty`); `entities[].related` | `affects_resource` is co-occurrence |
| Which resources are touched, how hard? | `articles[].resource_events` (talk, signed); links with a `resource:` end; `entities[kind=resource]` | direction is null |
| Where did it come from, can I trust the read? | `articles[].read_depth`, `read_reason`; `publishers[]`; `facts[].evidence[]` | teaser-only on 13 of 34 (c1), 17 of 40 (mix) |
| What do we not know? | `entities[].gaps`, `slot_fill` (`cant`), `meta.coverage`, `articles[].decider` abstains | |
| How is the area moving as a whole? | `meta.growth`, `meta.counters`, `meta.yield`, `meta.funnel` | not yet a Pulse tuple |
| What can be drilled into next? | `entities[].related`, `capabilities` (`bridging`, `areas`), `links[]` | |
| How fast was it read? | `meta.timing`, `articles[].ms_fast`, `ms_slow` | fast p50 420 / 303 ms per article, slow clock about 1.1 / 1.2 s |

Every coverage figure in these files comes from `meta.coverage` in the samples (computed by `export-bundle.py` against the bench on 2026-11-23) or from the named existing report `scratchpad/ladder/ladder-review.md`.
