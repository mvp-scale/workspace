# Story type and "recent" definitions: what established schemes do (sources)

Date: 2026-10-21. Research only; no code, ledger or data changed. Every source below was opened in this session unless marked NOT VERIFIED. Quotes are short and copied from the fetched page or PDF text.

## 0. The problem, from our own files

- Judges see (probes/world-engine/classify.py, lines 26, 90): `News item (published <date>; today is <date>): <title>. <description>`. So publication date and today are given.
- The current question texts (exports/world-engine-ontology-rules_v2.json, lines 27077-27085) are one sentence each:
  - g|happened: "This story reports something that has already happened."
  - g|announced: "This story reports a decision, announcement or plan that has been made public."
  - g|opinion: "This story is mainly an opinion or commentary."
  - g|forecast: "This story is mainly a forecast or prediction about the future."
  - x|recent: "This story reports a development from the last few days."
- Agreement (F-0083, data/jury/J/agreement.json): happened alpha -0.245, announced 0.52, opinion 0.50, forecast 0.24, recent 0.44.
- Use in the engine: classify.type_weight (probes/world-engine/classify.py ~line 99): fact = (happened or announced >= .5) and opinion < .5 and forecast < .5 -> weight 1.0; forecast / opinion 0.3; unclear 0.5. The reading gate also needs x|recent >= .3 and scales dial movement by P(recent).
- Why the questions are hard to agree on, from the text alone: (1) "happened" and "announced" overlap (an announcement is something that happened); (2) no rule for reported speech, future tense, or who is speaking; (3) "mainly" has no threshold; (4) "last few days" has no number; (5) the four type labels are independent yes/no, so one story can legitimately get yes on all four.

## 1. Event factuality

### 1a. FactBank (Sauri and Pustejovsky 2009)
- Citation: Sauri, R. and Pustejovsky, J. (2009). FactBank: a corpus annotated with event factuality. Language Resources and Evaluation 43(3):227-268. DOI 10.1007/s10579-009-9089-9.
- Opened: LDC FactBank 1.0 readme, https://catalog.ldc.upenn.edu/docs/LDC2009T23/readme.pdf (the paper PDFs on brandeis.edu and ResearchGate would not open: certificate rejected / 403; the paper's own guideline text is NOT VERIFIED).
- Rule (readme): "Event factuality is not an inherent feature of events but a matter of perspective." Factuality is "assigned relative to the relevant sources at play", so the author's view and a quoted person's view are separate judgements. Values combine certainty (certain CT, probable PR, possible PS, underspecified U) with polarity (+, -, u): CT+, PR+, PS+, CT-, PR-, PS-, CTu, Uu (value list from the readme line 410 plus a search summary of the paper).
- Procedure (readme): "the annotation procedure was carefully designed and divided into basic, sequential annotation tasks", with "a battery of discriminatory tests" for telling values apart.
- Agreement: "kappa=0.81" (readme). The readme does not say which pairs or which value set the 0.81 covers.
- Application to headline + description: take the event in the headline and ask "according to the author, did it occur?" separately from "according to the quoted source". For "X said Y happened", the event Y gets the source's factuality, not the author's; the saying event itself is certain. Our single "happened" question merges these two sources, which is a likely reason for the negative alpha.

### 1b. UDS "It Happened" (White et al. 2016; Rudinger, White, Van Durme 2018)
- Citation: Rudinger, R., White, A. S., Van Durme, B. (2018). Neural models of factuality. NAACL-HLT, pp. 731-744. DOI 10.18653/v1/N18-1067. https://aclanthology.org/N18-1067.pdf (PDF text extracted locally). Protocol from White et al. 2016 (UDS-IH1); not opened separately.
- Question: HAPPENED is "whether or not, according to the author, the event has already happened or is currently happening", followed by CONFIDENCE "from 0-4". Annotators first answer UNDERSTANDABLE and PREDICATE (is the word an event or state); if no, the happened question is not shown.
- Rule for future: the paper notes the "annotation instructions to mark future events as not having happened" (so "will" gets the most negative mean factuality).
- Agreement: raw 0.84, "Cohen's kappa=0.66" on UDS-IH2 (two annotators per predicate, 20,580 predicates, 32 Mechanical Turk workers); 0.82 raw on UDS-IH1. One annotator excluded and 4,179 annotations removed for low agreement on HAPPENED.
- Application: this is the closest published match to our "happened" question, and its wording differs from ours in four ways: it says "according to the author"; it covers "already happened or is currently happening"; it states future = no; it pairs the yes/no with a 0-4 confidence. Even with those, kappa is 0.66 on short-sentence events, not on whole-story judgements. Our alpha of -0.245 is far below that.

### 1c. TimeML event classes
- Opened: TimeML spec draft 1.1b, https://xml.coverpages.org/TimeMLSpec11b-20040419.html ; TimeBank 1.2 documentation, https://catalog.ldc.upenn.edu/docs/LDC2006T08/timebank.html . The 1.2.1 annotation guidelines (Sauri et al. 2006) did not open; class definitions are NOT VERIFIED beyond the examples.
- Rule: "class ::= 'OCCURRENCE' | 'PERCEPTION' | 'REPORTING' | 'ASPECTUAL' | 'STATE' | 'I_STATE' | 'I_ACTION'". Examples on the page: I_ACTION "denied" in "Bill denied that John taught on Monday"; I_STATE "wants" in "Bill wants to teach on Monday"; OCCURRENCE "taught". Reporting and intensional events introduce subordinated events (SLINK).
- Agreement: none reported on the TimeBank page ("a high level of annotator agreement" is stated without a number).
- Application: TimeML separates the saying/promising/planning event (REPORTING, I_ACTION) from the event it embeds. Our "announced" mixes both: "announces plan to X" is an I_ACTION whose embedded event is not realised. A rule is needed for which event the label is about.

## 2. News genre and text type

### 2a. IPTC NewsCodes Genre vocabulary
- Opened: https://cv.iptc.org/newscodes/genre/Opinion , /Analysis , /Forecast , /Current (each page's English definition field).
- Opinion: "Editorial comment that reflects the views of the author" (modified 2010-12-15).
- Analysis: "Data and conclusions drawn by a journalist who has conducted in depth research for a story".
- Forecast: "Opinion as to the outcome of a future event" (not retired; modified Dec 2010).
- Current: "Content about events taking place at the time of the report".
- Agreement: none (a vocabulary, not an annotation study).
- Application: IPTC treats forecast as a kind of opinion about a future outcome, not a separate axis. Analysis is a separate genre from opinion: conclusions from research versus views of the author. Our schema has no analysis label, so analysis pieces fall to whichever of opinion/happened a judge picks.

### 2b. SemEval-2023 Task 3, subtask 1 (genre)
- Citation: Piskorski, Stefanovitch, Da San Martino, Nakov (2023). SemEval-2023 Task 3: Detecting the Category, the Framing, and the Persuasion Techniques in Online News. https://aclanthology.org/2023.semeval-1.317.pdf (opened as PDF text).
- Rule: article is "(a) an opinion piece, (b) aims at objective news reporting, or (c) is satirical", a single choice per article (multi-class, not independent yes/no). Satire footnote: "a factually incorrect article, with the intent not to deceive, but rather to call out, ridicule, or expose".
- Agreement: Krippendorff alpha 0.342 before consolidation (below the 0.667 threshold the paper cites); top-half annotators 0.415, bottom half 0.250; 0.588 for the Italian pair of curators. Final labels came from curator consolidation of at least two annotators.
- Application: even with full articles, a 3-way opinion/reporting/satire choice by trained annotators has low raw alpha. This is the realistic ceiling for the opinion label from headline + description: expect well under 0.67 without curation, and use adjudicated labels rather than raw single-judge labels as ground truth.

### 2c. Forecast / prediction as a claim type
- Opened: Goldin, Wigderson, Rabinovich, Wintner (2025). An Annotation Scheme for Factuality and its Application to Parliamentary Proceedings. arXiv 2509.26406 (PDF text), appendix quoting Konstantinovskiy et al. (2021).
- Rule: "Prediction: Hypothetical claims about the future", example "school funding will have fallen by 5% in real terms by 2019". It sits beside a separate type "Quantity in the past or present" and "Current laws or rules of operation" (rules and changes), so a stated rule change is not a prediction.
- Agreement: mean pairwise kappa 0.58 on the check-worthiness feature (3 annotators, 65 sentences); full three-way agreement was low on several layers.
- Application: a forecast is defined by future time plus uncertainty ("hypothetical"). A scheduled or decided future event ("parliament will vote Tuesday") is not a hypothetical claim; it is a plan.
- Not opened: no dedicated forecast-vs-news genre study was found. The claim that forecast needs its own rule beyond tense is my reading, not a source finding.

## 3. Temporal: event time relative to publication

- Opened: TimeML 1.1b draft (above). Rule: events are placed relative to a document time by temporal links; `relType` values are "'BEFORE' | 'AFTER' | 'INCLUDES' | 'IS_INCLUDED' | 'DURING' | 'SIMULTANEOUS' | 'IAFTER' | 'IBEFORE' ..." and the document timestamp is a TIMEX3 with `functionInDocument="CREATION_TIME"`. TimeBank documentation: relative expressions such as "today" are resolved by anchoring to the document creation time, and "the creation-versus-publication time distinction" is listed there as future work.
- Agreement: no figure on the pages opened (TLINK agreement numbers NOT VERIFIED).
- Application: TimeML never asks "is the event recent". It asks for the ordered relation of event time to document time, and for the event time as an anchored date. For our input, `published` is the document time, so "recent" can be defined as a computed relation (event time within N days before publication) instead of a gut sense of "last few days". Note also that our judges are told "today", which is not the document time; the old "last few days" is ambiguous between publication and today.

## 4. Codebook practice

- Source found but only as secondary summaries; the originals were NOT OPENED: MacQueen, McLellan, Kay, Milstein (1998), Codebook development for team-based qualitative analysis, Cultural Anthropology Methods 10(2). A course slide deck citing it (https://www.eecs.tufts.edu/~asuh/files/coding_short.pdf, only seen in search results) lists the parts of a code entry: label, brief description, full description, when to use, when not to use, examples.
- A secondary content-analysis guide says low reliability can come from "poor operational definitions with unclear coding categories and poor coder training", that categories should be "mutually exclusive and exhaustive", that coders should code a subsample independently and revise the scheme on disagreement, and that alpha >= 0.80 is conventional with 0.667-0.79 allowing tentative conclusions (search summary; Krippendorff's book NOT VERIFIED).
- In the sources I did open, the schemes that reach kappa 0.66-0.81 (FactBank, UDS) do it with (a) a source-relative question, (b) staged simple questions before hard ones, (c) explicit rules for future and modal cases, and (d) removal of outlier annotators. None of these reports an include/exclude/example effect as a controlled measurement, so "examples raise agreement" is supported only by general guidance here, not by an experiment I could cite.

## 5. Summary of what the sources agree on

1. Factuality is relative to a source. Ask about the author, treat quoted claims separately (FactBank, UDS).
2. Future events are "not happened" (UDS rule) or a distinct modality (FactBank PR/PS), never merged with happened.
3. Forecast = opinion/hypothesis about a future outcome (IPTC, Konstantinovskiy). A decided or scheduled future event is a plan, not a forecast.
4. Genre is a single choice among exclusive types (SemEval T3), and even that has raw alpha 0.34.
5. Time is relation to the publication timestamp, not a feel for "recent" (TimeML).

## 6. Proposed codebook (for headline + description, judged as the author of the text)

Unit: the main event of the headline, plus the description. Source: the publisher's voice unless a person is quoted. Publication date is given; "today" is not used for any label.

### Step A. Genre (one choice, replaces opinion)
- REPORT: the text states what occurred, was decided, or was said, in the publisher's voice. Includes press releases rewritten as news.
- ANALYSIS: the text gives conclusions or interpretation drawn by the publisher from evidence ("why", "what it means", "explainer"), with no personal stance. (IPTC Analysis.)
- OPINION: the text states the author's or a named columnist's view or recommendation ("should", "must", evaluative words). (IPTC Opinion.)
- Decision rules: a quoted person's opinion inside a news report is still REPORT (the publisher reports that the person said it). Headline words "Opinion:", "Editorial", "Column", "Analysis:" decide the label. If both a fact and an evaluation are present, choose the main verb of the headline.

### Step B. Time of the main event relative to publication (one choice)
- DONE: occurred before or at publication, or is in progress at publication. (UDS "already happened or currently happening".)
- SCHEDULED: decided or announced, set for a later time. Includes "will" with a named agent and a decision ("will raise rates from May").
- PREDICTED: stated as likely or possible by someone, not decided ("could", "may", "expected to", "analysts see").
- NONE: no event (pure commentary).
- Decision rules: use the verb tense plus modality, not the topic. Present perfect "has announced" is DONE for the announcing event. "X said Y will happen": see Step C.

### Step C. Speech-act layer (replaces announced)
- Ask two things: (1) did the announcing/saying happen? Almost always yes if the text says "said/announced". (2) What is the embedded event's status per Step B?
- "Announced" becomes a flag, SPEECH = yes when the main verb is a reporting or intensional verb (said, announced, plans, promised, denied; TimeML REPORTING and I_ACTION). It does not mean the embedded event happened.

### Step D. Recent (computed, not asked)
- Ask the judge only for the event date (or "unknown"); the code computes days between event date and `published`. recent = event date within 3 days before publication or later, using the same 3 days across all stories (value to be set by a decision, not by this document).
- If the text has no event date and the verb is past tense with "today / yesterday / this morning", use the publication date.

### Definitions with what counts / what does not / one example

| Label | Counts | Does not count | Example |
|---|---|---|---|
| happened (Step B = DONE, Step A = REPORT) | A completed or ongoing event stated as fact by the publisher: a vote, strike, attack, price change, a statement actually made | Plans, promises, predicted outcomes; events only claimed by a quoted party and doubted | "Parliament passes budget by 12 votes" |
| announced (SPEECH flag, Step B = SCHEDULED or the saying itself) | Official statement of a decision, plan or policy; the statement is the news | The embedded event as if it occurred; rumours; opinions | "Bank to raise rates from May, governor says" |
| opinion (Step A = OPINION) | Editorial, column, commentary stating the author's view | Quoted opinions inside a news report; analysis | "Why the rate rise is a mistake" |
| forecast (Step B = PREDICTED) | Likely/possible future outcome stated by a source, projections, estimates, "could", "expected to" | Scheduled events with a named decision; past results; plans | "Analysts expect inflation to hit 5% by autumn" |
| recent (Step D) | Event date within the cutoff before publication | Old events retold; background | "Floods hit the north on Sunday" (published Monday) |

### Hard cases
- "X said Y happened" ("Minister says talks collapsed"): Step A = REPORT; saying = DONE; Y = DONE per publisher unless the text signals doubt ("claims", "alleges") in which case Y is reported as source-claimed and not counted as happened by the author. Label happened = yes only when the publisher's voice presents Y as fact.
- Future-tense announcement ("Firm will cut 500 jobs, CEO says"): SPEECH yes; embedded event SCHEDULED, not happened, not forecast.
- Analysis piece ("What the rate cut means for mortgages"): ANALYSIS, not opinion unless it recommends; event status NONE or DONE for the cited event.
- Mixed headline ("Shares fall 5% as investors fear recession"): the fall is DONE, the fear is attributed; label by the main clause (DONE, REPORT).
- Question headlines ("Is the economy heading for recession?"): OPINION or ANALYSIS by description; Step B = PREDICTED; never happened.
- Negated / unrealised ("Strike called off"): the calling off is DONE; the strike is not happened.

## 7. Structure change

- What the evidence supports: SemEval T3 uses a single choice among genre classes; UDS asks one happened question plus a separate confidence 0-4; FactBank stores certainty and polarity as two parts. None of the schemes uses four overlapping independent yes/no questions for genre and time at once.
- Proposed: replace the four independent types by two single-choice questions (genre: REPORT / ANALYSIS / OPINION; event status: DONE / SCHEDULED / PREDICTED / NONE), plus a SPEECH flag, and compute recent from an event date. This is my design, not a published scheme; it should be piloted on the existing jury data before adoption.
- What it would change for the engine (probes/world-engine/classify.py, type_weight):
  - The gate "(happened or announced) and not opinion and not forecast" becomes "genre = REPORT and status in {DONE, SCHEDULED}" (fact, 1.0); ANALYSIS and PREDICTED/OPINION map to the lower weights. Today 'announced' covers both a statement that happened and a plan, so the engine currently gives full weight to a plan; under the new structure SCHEDULED could keep full weight or get its own weight (a decision for the engine owner, since it changes outputs).
  - The 'unclear' bucket (0.5) now arises only when a choice has low margin, not when two independent yes/no answers happen to both be low.
  - A factuality scale (UDS-style -3..3, or FactBank certainty) could replace DONE/SCHEDULED/PREDICTED with a number; I do not recommend it first, because UDS scales needed a confidence follow-up and still reached kappa 0.66 at the event level.
  - recent: becomes a number of days instead of a probability, so the dial scaling by P(recent) in classify.py would need a mapping (for example full strength inside the cutoff, decaying after).
  - Reader labels and the 328-question set would need relabelling and a new alpha baseline before the CPU reader is retrained.

## 8. What was not verified

- FactBank LRE 2009 paper full text and TimeML 1.2.1 guidelines (host certificate / 403 / 404).
- MacQueen et al. 1998 and Krippendorff's book (secondary summaries only).
- Any published study of "recent" as a label or of forecast vs news genre.
- IPTC "Preview", "Interview", "Result" and other genre definitions beyond the four opened.

## Sources opened
- https://catalog.ldc.upenn.edu/docs/LDC2009T23/readme.pdf
- https://aclanthology.org/N18-1067.pdf
- https://aclanthology.org/2023.semeval-1.317.pdf
- https://arxiv.org/pdf/2509.26406
- https://cv.iptc.org/newscodes/genre/Opinion , /Analysis , /Forecast , /Current
- https://xml.coverpages.org/TimeMLSpec11b-20040419.html
- https://catalog.ldc.upenn.edu/docs/LDC2006T08/timebank.html
