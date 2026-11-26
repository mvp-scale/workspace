# Presentation process: from knowledge to a page a leader can read fast and keep

Date: 2026-11-24. Status: built and tested on three staged windows (see section 8); PROVISIONAL. Terms: `terminology.md` (no new terms coined; "remember-line", "status line", "situation strip" and "recall first" are block names, listed in section 9). Rule tables: `goal-templates.json`, `type-encoding-rules.json` (rendered: `type-encoding-rules.md`). Citations: `sources.md`. Code and outputs: `/workspace/_remove/presentation-process/`.

This is a process, not a page. It takes any developments bundle (`/api/raw/developments` shape, any staged window, any subject) and produces, without a person in the loop: a requirement table, a rendered page, a grounding report and a scored reader test. The owner's role is the timed check in step 6 and the priorities file, both optional.

## 1. The process in one screen

| Step | Block | Input | Output | Code |
|---|---|---|---|---|
| 1 | **Derive requirements** | developments bundle x `goal-templates.json` (monitor / decide / explain / anticipate / retain), optional `priorities.json` | requirement table: one row per (requirement, development) or per page, each `answerable` or `gap: <reason>` | `gen.py requirements()` |
| 2 | **Type and encode** | each requirement's information type | the mark and the minimal text from `type-encoding-rules.json` E1-E12 | `gen.py card()` |
| 3 | **Synthesize safely** | fields and quotes only | remember-line (verbatim best-supported sentence), status line (fixed slots), ICD 203 confidence word, gap lines | `gen.py`, rules S1-S7 |
| 4 | **Compose** | ranked developments | overview (counts + situation strip) -> recall-first block -> up to 8 full cards -> compact lines -> thin collapsed -> method footer | `gen.py render()`, rules C1-C6 |
| 5 | **Gate** | rendered page + grounding registry + data | PASS only if every text node is verbatim data, a fixed label or a field number; Clef entailment pre-screen listed, not gating | `check-grounding.py` |
| 6 | **Test, non-circular** | requirement table x data -> questions; screenshots only | accuracy per information type for the design, the text-only ablation, the raw-headline control (and any hand-written brief), by a model reader (Jev, Clef) and by the owner (timed check, delayed recall) | `questions.py`, `shoot.js`, `judge.py`, `owner-check.html` |

Run order for a new area: `gen.py` -> `questions.py` -> `shoot.js` x3 -> `check-grounding.py --clef` -> `judge.py` per condition -> `owner-check.html`. Nothing in the chain reads the design to write the test: `questions.py` reads `requirements.json` (goal templates x data) and `data.json` only, draws its pool of developments by a data rule (the 8 largest by articles, then owners) and never reads the page, the rank order or the full-card cut. An independent adversarial review (Haiku, 2026-11-24) found the first version leaking the renderer's rank into the pool and a "which development leads the page" question; both were removed before the final numbers.

## 2. Step 1: requirements derived from the knowledge, not from an interview

Goal-Directed Task Analysis (Endsley) asks: goal -> decision -> what must be known at L1 (perceive), L2 (comprehend), L3 (project). The previous method made this a per-reader interview, which is not repeatable. Here the goals are five fixed templates that hold for any reader of any feed, and the requirements are instantiated against whatever the data holds:

- **monitor** (Do I need to look now?): change per development and per page, new-assertion count, certainty-word change.
- **decide** (Can I act on it?): certainty word, independent owners, who disagrees and about what.
- **explain** (Who, where, when, why?): people/organisations, places, stated cause, first day and span, shared entities with other developments.
- **anticipate** (What do I watch?): forward statements with speaker, developments with none, count with any.
- **retain** (What do I keep?): one-line state per development, the leading development and its rank reason.

A row is `answerable` when the field holds a value, else `gap` with the reason in the fixed form "no X read in N articles". The table is written out (`out/<area>/requirements.md`) so the gaps are visible before any design decision. Per-reader priorities (`{"follow": ["iso:SA"], ...}`) are an override: a followed entity moves its development to the top of its ranking band and fills the "for you" slot with "touches followed: ..."; without a file the slot says "not assessed (no reader priorities given)". The process never waits for the file.

Why these five and not an open list: Endsley's three SA levels map onto them (L1 monitor/explain, L2 decide, L3 anticipate); KITs (Herring) name the same three families (decisions, early warning, key players); the TAC update-summarization task is "monitor". "Retain" is the one addition, justified by the owner's target (retention) and the testing-effect literature.

## 3. Step 2: the type -> encoding rule table (the core block)

Summary (full table with citations in `type-encoding-rules.md`):

| Type | Mark | Minimal text |
|---|---|---|
| change | rank first + one reserved hue dot + rings on post-cut days | "+N new since <day>" / "nothing new since <day>" |
| magnitude | dots <= 5, bar on a common scale above 5; never area or colour alone | the number and unit |
| time | dot per day on ONE shared day axis (small multiples), cut as a rule | "<first>-<last>, N days" |
| entity | chip, shape by kind (circle person, square org); names not counts | the label |
| place | diamond chip in its own "where" row; map only with coordinates | the label |
| relation-cause | left-to-right arrow carrying the connective (because / led to = causes; after = precedes) | the quoted sentence |
| connection | identical chip repeated across cards + "also in N"; matrix lens above 20 developments | "also in <development>" |
| contradiction | two equal columns, speaker bold, disputed dimension named between | both quotes |
| certainty | lightness ramp of one hue + the word always; disputed in the reserved hue | "<word> . confidence low/moderate/high" |
| forward | dashed "ahead" box, speaker first, factuality tag, no likelihood word | "<speaker> said: <quote>"; "likelihood not assessed" |
| gap | muted italic line in the slot, never empty, never hidden | "no X read in N articles" |
| synthesis | bold remember-line + status line in fixed slots; recall-first block | <= 25 words; cites assertion ids |

Three colours are reserved and mean one thing each on every page: accent = new since the last look; magenta = disputed; a neutral lightness ramp = certainty. Everything else is ink. Each mark sits next to its own words (spatial contiguity), so no value needs a legend; the legend lists only the three reserved colours.

## 4. Step 3: synthesis that cannot say what the sources did not

Only two kinds of composed text exist (S1): the remember-line, which is the development's best-supported source sentence verbatim (falls back to the quoted headline when no sentence qualified), and the status line, whose slots are filled from typed fields (certainty word, owner count, new-assertion count and cut day, certainty change, rank reason). Every line carries the assertion ids it rests on in the grounding registry. ICD 203 is applied where it fits and not stretched: analytic **confidence** maps from sourcing only (single source = low, reported = moderate, established = high, disputed = disputed/low), **likelihood** words are never emitted because the data has no probability basis, and the slot says so. "Why it matters to you" is produced only from a priorities file and then only as "touches followed: ...". Model-written prose is not in the render path (ledger L2995); a model (local Clef) reads the finished page only as a pre-screen (S4).

The gate (`check-grounding.py`) checks two things on every build: every registered verbatim string exists in the data file, and every text node on the page decomposes into registered strings, field numbers and the fixed vocabulary. All nine pages built here pass with zero ungrounded nodes.

## 5. Step 4: composition at any scale

The same grammar from one development to thousands: a header with three counts and the **situation strip** (one small square per development in rank order: accent = moved, magenta ring = disputed, mid-grey = forward statement only, light = unchanged), a collapsed **recall first** block with last visit's lines, at most 8 **full cards**, then one **compact line** per remaining development carrying the same four marks (change dot, certainty chip, owner dots, mini time strip on the same day axis), then thin developments collapsed, then the method footer with the pipeline's own gap notes. Full cards share one block order (remember-line, status, time, who, where, disputed, cause, ahead, since, for you, evidence on demand) so the eye learns the layout once. At 96 developments (stream) the page is 8.3k px tall and the first screen still carries the whole overview: 33 of 96 moved, 0 disputed, 62 with a forward statement, 43 thin.

Retention aids: the remember-line is the first and largest text of each card; the recall-first block lists, for the leading developments, the line and certainty word as they stood at the cut ("then reported; now established"), to be read before the new material (retrieval practice); the owner check has a delayed-recall step.

## 6. Step 5-6: the test and why it is not circular

Questions are generated by `questions.py` from the requirement table and the data: for each requirement row, a question, the data answer, three distractors drawn from the same page's other developments and a "cannot tell from the page" option. The encoding rules are never read by the question generator; the same question file is put to every condition. Conditions per area: **design** (the process), **text** (same generator, same content and order, no marks: isolates the encoding), **headlines** (every article title with publisher and day: the control the old page was), and for mix the owner's **hand-written brief** (`demo/mockups/knowledge-raw/executive-brief.html`). Scopes: first screen only (1440x900) and full page (first screen + tiles). Readers: hosted Jev 1.14.0 reading the PNGs (pre-screen), local Clef on the first screen (second reader), the owner through `owner-check.html` (timed read, blanked screen, same questions, then delayed recall). Model readers pre-screen; the owner decides.

Baselines give the measure: the chance baseline is computed per question file (1/options averaged: 0.22-0.24 here, because yes/no questions have three options); the headline control is what the pipeline replaced; the text ablation shows what the marks add on top of the content and order. Known limits of the model test, kept on purpose: a model reading pixels answers lookup questions (a label, a quote, a number) as well as comprehension questions, so a high full-page score says "the page states it", not "a person grasps it fast"; speed and retention are the owner's timed check and delayed recall; the first-screen scope is harsh by design (one full card fits at 1440x900) and is reported as such.

## 7. How to run it on a new area

```
cd /workspace/_remove/presentation-process
curl -s 'http://127.0.0.1:18770/api/raw/developments?src=area:<key>' -o out/<key>/data.json   # or developments_v0.build(trace, name)
python3 gen.py <key> out/<key>/data.json [--label "..."] [--priorities p.json]
python3 questions.py <key>; for m in design text headlines; do node shoot.js out/<key>/$m.html out/<key>/$m; done
python3 check-grounding.py <key> --clef
python3 judge.py <key> design out/<key>/design --clef; python3 judge.py <key> design out/<key>/design --full   # and text, headlines
```

## 8. Results and honest failures

Results per area and condition: `/workspace/_remove/presentation-process/results.md` (numbers written there after the judge batch; the final reply quotes them).

Failures found by running the process, not by reading it:
1. **Cause slot is weak.** E6 renders the first sentence that contains a causal connective. The Clef pre-screen rated 7 of 13 such sentences below 0.5 for "states a cause" (c1: "a huge fan of Fiona because she likes underdogs"; stream: a factory fire "causing panic"). The pipeline's own note says attributed cause is MISSING; the process can only show the gap honestly, it cannot fill it.
2. **Roundup articles poison developments.** In the stream, "While You Were Sleeping: 5 stories" and a Lula/India cricket item were merged into one development, so its remember-line and evidence disagree (Clef 0.27). A presentation process cannot repair clustering; it exposes it (the remember-line and the evidence sit together).
3. **Remember-lines can be bad sentences.** "Live updates: Celtics look to bounce back vs." is a verbatim but cut headline. Verbatim is safe, not always good; a sentence-quality rule (complete clause, no live-blog prefix) belongs in the pipeline's summary pick.
4. **No place geometry.** E5 asks for a map when coordinates exist; the data has ISO codes and place names only, so "where" stays a chip row.
5. **No likelihood.** ICD 203 estimative words need a probability basis; none exists, so the ahead box prints "likelihood not assessed". The process is honest here, but a leader asking "how likely" gets no answer.
6. **First screen holds one full card at 1440x900.** Overview and the strip fit; the second card does not. Questions about developments 2-8 are answered only in the full-page scope. A denser card or a two-column layout is a design choice the test can now measure.
7. **Model readers are a pre-screen.** Jev and Clef answer typed questions from pixels; they do not retain anything. The retention claim rests on the owner's delayed-recall step, which has not been run.
8. **Disputed is rare.** Only mix has a contradiction with named speakers; c1 and the stream have none, so E8 is tested once.
9. **Found by the adversarial review and fixed:** the cause row printed "because" when no connective matched (now "stated reason", no arrow); "disputed" rendered for contradictions without named speakers on both sides (now a gap line "contradiction read, but not both sides named"); the recall block could fall back to a post-cut sentence (now omitted); gap lines carried unverified counts (now registered numbers); subject words sat in the gate vocabulary (removed; a CLI label is recorded apart); the gate did not check that a quote came from the assertion it cites (now an id-level check, 0 mismatches on 9 pages).
10. **Found by the review and not fixed, on record:** "confidence from sourcing: high" is ICD 203's confidence scale applied to owner counts only, a narrower basis than the directive's (which also weighs source quality); hub entities ("United States" in 21 developments) make "how it connects" a count, not a link, and the matrix lens (E7 at scale) is specified but not built; the judge reads hosted Jev by default (allowed for this test by the owner; `--clef` adds the free local reader).

## 9. Terms used

All canonical (terminology.md): development, assertion, evidence, publisher owner, reinforced, certainty word, contradiction, forward statement, gap, since your last look, ranking, owner mark (priorities). Block names introduced by this process, not knowledge terms: remember-line (E12), status line (E12), situation strip (C1), recall first (E12), compact line (C2). None replaces an existing term.
