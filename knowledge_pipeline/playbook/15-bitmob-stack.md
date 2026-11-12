# 15 · The BitMob stack

**Goal:** one definition of the tools, models and router, and the order they run in, so the tools prove what the text proves, the models answer what is left, and the teacher labels only the rest. Owner naming and order, 2026-11-07. Chapter `00` is the architecture (gates G0 to G6, the cascade in section 4); this chapter defines the parts. Status and measured results are not kept here: see the BitMob page in the Console and the ledger.

## Definitions

| Term | Definition |
|---|---|
| **BitMob stack** | The tools, the models and the router, run in that order on every article. |
| **BitMob toolchain** | The set of BitMob tools, run in order on every article (owner, 2026-11-08). Replaces the umbrella name "Fact finder", which hid the individual tools. Every tool in it has a stated point and a measured answer to "does it add value"; a tool with no measure is listed as not measured. The live list with code files and measures is Act 1 of the Solver page. |
| **BitMob tools** | Command-line programs that find, tie down and check things in the text with fixed rules. They are not classifiers. Together they produce one evidence record per article. |
| **BitMob model** | A small CPU classifier that answers one question about the article. One model per head of `00` section 4. Its labels are weak. |
| **BitMob Router** | For each head, decides who answers (tools, a model, or the teacher) and whether the answer is given, given provisionally, or withheld. |
| **Evidence record** | The tools' output for one article: every item carries the tool, its version and an exact span of the cleaned text. |
| **Label strength** | `proved` (a tool fact that passed all four Validator checks), `rule` (a tool rule), `weak` (a model or a teacher). |

## Rules

1. **Tools first, on every article.** No model or teacher runs before the tools have produced the evidence record.
2. **A tool answer is proved only if it validated.** A fact that passes all four Validator checks answers its head with strength `proved`, and the teacher is not asked about it.
3. **A model is called only for a head the tools left open**, and only if a model exists for that head and the field gate admits it (chapter 13). Try the sparse head before the encoder (`00` section 4).
4. **The teacher labels only what is left**: heads with no tool answer and no admitted model, and answers the Decider withheld. Two model families; keep agreement, route splits with soft targets (chapters 03, 14).
5. **Every label is stored with its strength, its definition version and its publisher.** A teacher or model label is never marked `proved`.
6. **Retrain at every 10,000 articles.** The batch of stored labels retrains the focused models; each is scored on its outside anchor, with whole publishers, time ranges or events held out, and goes through the field gate (chapters 02, 06, 13).
7. **Definitions change by version, not by rewrite.** When an Area or Capability is split or merged, its children inherit the parent's label and old items re-map by id.
8. **Tool rules are written in a language-independent form and proved where they decide something.** The compiled target is Rust; Lean holds the rule (chapter 11). A Python version is a reference for a differential test, not the product.

## Gates in the stack

The gates are defined in `00` (section 1 diagram, section 2 table, section 5 data contract, section 6 pipeline sketch) and in the PRD (v0.2 section B interfaces, section D stages). The stack does not redefine them. Each tool below runs inside one gate and returns that gate's output in the contract's own fields.

| Gate | Job (`00` section 2) | Output contract | Escalates when | Tools that run in it |
|---|---|---|---|---|
| **G0 Normalize** | Source adapters, hashes, language heuristics, source and permission metadata. | Resident text and validated provenance: the PRD `SourceEnvelope` (B1) and the provenance record of `00` section 5. | Unsupported format or language. | Source and link capture, Boilerplate strip, Clean, Windows |
| **G1 Scan** | Fixed patterns, one pass over the text. | Word and span offsets, clause cues, entity candidates. | Unsupported structure; the raw source is kept. | Scan, Date resolver, Sentence splitter |
| **G2 Semantic solver** | Bounded predicate-role templates and local constraints over the scan. | Subject / predicate / object fragments and qualifiers: the `SemanticFragment` of `00` section 5 and the PRD `SemanticCandidate` (B2). | Ambiguous role assignment. | Parse, Fact extractors, Binder, Validator, Independent counter, Factuality tagger, Change lexicon, Place linker |
| **G3a / G3b Classify** | Rules, then a sparse model, then a compact encoder on unresolved heads. | `ClassifiedObservation` (`00` section 5): domains, areas, capabilities, model version, ontology version. Function, Condition and Novelty are recorded beside it (`00` section 4). | The Decider withholds the answer. | The BitMob models and the Router |
| **Journal** | Persist before any graph work. | Compact fragments plus evidence pointers. | | the evidence record is written here |

## Tools, in the order they are called

| # | Tool | Gate | Takes | Gives | Rule |
|---|---|---|---|---|---|
| 1 | **Source and link capture** | G0 | the fetched page | `SourceEnvelope` fields: `source_uri`, `publisher_id`, `title`, `published_at`, `language`, `content_hash`, `media_type`, `blocks`; plus the description, the section, and every link anywhere in the page (in the text, images, outbound) with where it was found | Keep every link and its place. Metadata timestamps stay separate from event times (PRD B1). |
| 2 | **Boilerplate strip** | G0 | all articles of one publisher | the cleaned blocks; each removed line and its span, recorded as transformation history in the provenance | Remove a line that one publisher repeats in 5 or more of its own articles. A line repeated across different publishers is kept; it is usually a syndicated story. |
| 3 | **Clean** | G0 | blocks | clean text with stable offsets | Collapse white space and normalise; every later tool reads only this text and reports offsets into it. |
| 4 | **Windows** | G0 | clean text, headline | slices for the models | Cut into slices of 64 word pieces, the headline at the start of each, up to 12 slices. |
| 5 | **Scan** | G1 | clean text, article date | spots `[start, end, class]`, with the resolved value for dates | One pass of fixed patterns. Classes: quote, money, percent, quantity, date, attribution, negation, modal, change word, event word, capitalised name. Attribution, negation, modal, change and event are the clause and predicate cues of `00` G1; capitalised names are its entity candidates. |
| 6 | **Date resolver** | G1 | a date spot, article date | a calendar date, or a relation to the article date; this is the `event_time` of a `SemanticCandidate` | A weekday is its most recent occurrence on or before the article date. Yesterday, today, tomorrow are offsets. "Last, this, next" week, month or year stay relative. A month and day take the article's year, or the previous year if that would be over 30 days ahead. |
| 7 | **Sentence splitter** | G1 | clean text | sentence spans | End a sentence at . ! ? followed by a capital, digit or quote. |
| 8 | **Parse** | G2 | clean text | part of speech and sentence-tree position per word; entity types | External tool, not ours. |
| 9 | **Fact extractors** | G2 | spots, parse | facts (fields in the next table), each an observation, event-time or anchor-mention candidate | *Amount*: a number with currency, percent or magnitude, or a number word; years and dates excluded. *Date*: a resolved date spot. *Name*: a capitalised name. *Triple*: for each verb other than a speech verb, be, have or do, its subject and its object; needs a subject or an object. |
| 10 | **Binder** | G2 | a fact span, the parse | `noun` (what an amount counts) and `verb` (the verb that governs it) | From the span, walk up the tree past up to two function words to a noun; climb up to four steps to the nearest verb. |
| 11 | **Validator** | G2 | a fact | `checks` (four booleans) and `status`: stated, unbound or invalid | *Literal*: the span is exactly in the text. *Reads back*: the value recomputes from the span (a weekday names that day, a month matches, an amount is positive, a name starts with a capital). *Bound*: attached to a noun or verb (a triple needs subject and object). *One sentence*: inside one sentence. All four = stated; only binding missing = unbound; otherwise invalid. Stated means the text says it, not that it is true. |
| 12 | **Independent counter** | G2 | clean text | counts of amounts, dates and runs of capitalised words | A separate, simple rule, so extractor coverage is measured against something other than the extractor (the coverage check of PRD B, step 5). |
| 13 | **Factuality tagger** | G2 | each sentence, parse | one tag per sentence (mapping below) | First match wins: *question* (ends in ?); *reported* (speech verb or "according to"); *denied* (main verb negated); *request* (request verb, "should", "must", opening imperative); *decision* (past-tense decision verb with a subject); *planned* ("will", "shall", plan verb plus "to"); *predicted* ("may, might, could, would", forecast verb); *asserted* (other sentence with a verb); *unknown*. |
| 14 | **Change lexicon** | G2 | parse | `condition` (rising, falling, delayed, disrupted, expanded), `direction`, the changing thing, `negated` | Find change words, tie each to the subject or object that changes through the tree, record direction and negation. This is the predicate cue (increases / decreases) of a candidate. |
| 15 | **Place linker** | G2 | place entities, publisher address | `place_candidate` with a country and how it matched | First match wins: alias ("U.S.", "UK", "Britain"); country name; a region that belongs to one country; a city that exists in one country; a city whose country is named in the article; a city in the publisher's country; otherwise the largest city of that name. |

**A fact (output of 9, 10 and 11).**

| Field | Meaning |
|---|---|
| `kind` | amount, date, name or triple |
| `s`, `e`, `text` | exact span in the clean text, and its text |
| `value` | amount: a number; date: the resolved date; name: the name; triple: [subject, predicate lemma, object] |
| `unit` | amount: %, a currency, or empty |
| `noun`, `verb` | what it counts or is governed by (Binder) |
| `role` | name: its role in the sentence |
| `checks` | `literal`, `reads_back`, `bound`, `one_sentence` |
| `status` | stated, unbound or invalid (Validator) |

**Factuality mapping.** `00` section 5 has six values: Asserted, Reported, Planned, Predicted, Denied, Unknown. The tagger's asserted, reported, planned, predicted, denied and unknown map to them one to one. Request and decision map to the PRD B2 modality values of the same name. Question has no value in either contract.

**Contract fields the Python prototypes do not fill yet.** Entity and predicate ids in a fragment (subject, object and predicate are text until the Anchor layer exists); `polarity` (denied is the only negation signal); `tenant_id`, `document_id`, `source_id`; `content_hash`, `language`, visibility and access policy, `received_at`; block structure (the article is one block of text); an extractor score; the link list has no field in B1.

## Toolchain rules (added 2026-11-08 after MM3-0002)

1. **Every tool has a point.** One line saying what question it answers and what goes in and out.
2. **Every tool has a measured test of value.** Compare the answer with the tool switched off, or against an outside answer (a public dataset). Passing our own checks is not truth. Until it is measured, the tool is listed as not measured and the page says so.
3. **The live path uses every tool that adds value.** A tool that adds value but is not live needs a recorded reason and a date to wire it in.
4. **Adding a tool:** add its row (point, definition, test) and run its test before it is wired in. **Retiring a tool:** if its test shows no gain, or another tool covers the same job, merge or remove it and record the result on the ledger.
5. **The live list and the measures are on the Solver page** (Act 1), built from the code and the result files.

## Models

All six read the evidence record and the slices, answer one question, and may abstain. Domain, Area and Capability fill the `domains`, `areas` and `capabilities` of the `ClassifiedObservation` (`00` section 5); Function, Condition and Novelty are the other heads of `00` section 4.

| Model | Question | Answer | Trained from | Judged against |
|---|---|---|---|---|
| **BitMob Domain** | What broad sector is this about? | two best guesses among the topics, rolled up to the broad classes | teacher labels (v6b); public human labels (sparse) | public human topic labels |
| **BitMob Function** | What is this item doing? | fact, opinion, forecast or unclear | teacher labels | an outside fact-versus-opinion set (judge not yet chosen) |
| **BitMob Condition** | What is changing, and which way? | change type (rising, falling, delayed, disrupted, expanded) with direction | teacher labels, plus tool change words | an outside set (none found) |
| **BitMob Area** | Which seeded or accepted Area? | one or more Areas | anchors and the evidence record | not defined yet |
| **BitMob Capability** | Which known Capability, or candidate association? | capability ids | verb-object phrases that recur across Areas | not defined yet |
| **BitMob Novelty** | Known, emerging or unsupported? | a routing signal; it never changes the ontology on its own | evidence compared with stored evidence | not defined yet |

A model version is tagged, for example BitMob Domain v6b (one shared network that also answers Function and Condition) and BitMob Domain sparse (hashed words).

## The Router

For each head of each article, in this order:
1. **Tools:** if a stated fact answers the head, take it (`proved`).
2. **Model:** else if a model exists and the field gate admits it, call it.
3. **Decider:** returns exactly one outcome from the source, validation, confidence and the field gate's marker.

| Outcome | When | Training data |
|---|---|---|
| Abstain, not admitted | the field gate marks the head not admissible | needs an outside judge |
| Abstain, too few | the gate marks too few items | needs more items |
| Abstain, not validated | a stated fact failed its checks | label queue |
| Abstain, low confidence | a trained head under the confidence bar | label queue |
| Abstain, gates disagree | a trained head where the checks disagree | label queue |
| Answer, provisional | the gate marks the head below the bar | not kept as a label |
| Answer | the gate marks the head as meeting the bar | a stated fact becomes a training label; a trained head's answer is not kept |

4. **Teacher:** labels the label queue and every head that has no tool answer and no admitted model.

## Proof

| Claim | File |
|---|---|
| Order: tools, then model, then teacher; a validated tool answer is never sent to the teacher; only tool-validated answers are `proved`; retrain at each 10,000 | `lean/BitMobFlow.lean` |
| The Decider's outcomes and training-data codes, replayed in Rust | `lean/Decide.lean`, `rust_decider/vectors.txt` |
| Agreement routing of teacher labels | `lean/Routing.lean` |
| Enough data to train a head | `lean/TrainReady.lean` |
| A Pulse field is done | `lean/PulseDone.lean` |

Bound (chapter 11): Lean proves the rules are consistent. It does not prove the code follows them, that a model is accurate, or that a label is true; those need a differential test, an outside anchor and the field gate.

## Done when

Every tool has a compiled implementation that matches its Lean-checked rule on a differential test; the Router decides before a model runs; stored labels reach the retrain job every 10,000 articles; each retrain writes a scored result to the ledger.

## Where the prototypes live (`projects/world-state/`)

Today's Python stand-ins, listed once. Their names are historical.

| Role | File |
|---|---|
| Whole chain prototype | `analyze2.py` |
| Scan, Date resolver | `scan_gate.py` |
| Fact extractors, Binder, Validator, Independent counter | `facts_lib.py` |
| Evidence record | `extract.py` |
| Decider (Python reference; Rust in `rust_pulse/`) | `decider.py` |
