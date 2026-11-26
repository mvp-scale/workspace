# Reader-first briefing method

Date: 2026-11-23. Status: adopted as the method for the knowledge presentation layer; replaces designing from pipeline fields. Terms: `terminology.md`.

## Why this exists
Three presentation attempts failed the same way (ledger L3002, L3003): they started from the fields the pipeline produces, showed metadata instead of meaning, and were graded against a checklist written by the same author. The fix is a proven, reader-first method used where people must act on large volumes of information fast (air traffic control, military command, power-grid control) and adapted for executives by corporate intelligence.

## The method (four steps, in order)

| Step | Proven source | Question it answers | Output |
|---|---|---|---|
| 1. Elicit needs | Key Intelligence Topics (Herring 1999); KITs phrased as Key Intelligence Questions | What does this reader need to decide, be warned about, and watch? | KIT set per reader or role: decisions/actions, early warnings, key players |
| 2. Derive requirements | Goal-Directed Task Analysis (Endsley) | For each goal and decision, what must the reader know? | GDTA table: goal -> decisions -> SA requirements at L1 perceive, L2 comprehend, L3 project |
| 3. Design and write | SA-oriented design (Endsley); ICD 203 analytic tradecraft standards (DNI) | How is each requirement shown and written so it is fast and trustworthy? | Brief organised by the reader's goals; L2/L3 stated directly; every judgment with key sources, uncertainty, assumptions and change indicators |
| 4. Test the reader | SAGAT freeze-probe (Endsley; meta-analysis of 243 studies) | Does the reader actually know more after reading? | Score of reader answers to GDTA-derived queries, checked against the data |

### Rules that follow from the method
1. Never start from pipeline fields. Start from the KIT set; pipeline fields are inputs to requirements, never the layout.
2. Show L2 (what it means for the reader's goal) and L3 (what happens next, what to watch) directly. L1 metadata (owners, counts) is evidence on demand, not the headline.
3. Synthesis is allowed and required when it meets ICD 203: name the key sources, state uncertainty in fixed words, state assumptions, name the indicators that would change the judgment. Each synthesized sentence cites the assertions it rests on and passes an entailment check against them. This replaces the stricter "no model-written text" rule, which is not in playbook 00 (00 forbids unsupported statements only).
4. The test is never the author's design checklist. SAGAT queries come from the GDTA table; answers are scored against the data. Model judges (Jev, Clef) may pre-screen, never decide.
5. Flexible by construction: a new reader or role is a new KIT set; a new feed is a new source for existing requirements. Layout does not change per feed.

## What each step uses from the pipeline
| Pipeline part (canonical term) | Feeds step | As |
|---|---|---|
| Development (event thread) | 2, 3 | The unit a requirement is answered from |
| Assertion + evidence + owners | 3 | L1 facts and the citations behind every judgment |
| Contradiction | 3 | Uncertainty and "who disputes" in the judgment |
| Triage change / Since your last look | 2, 3 | What changed for the reader's requirement |
| Forward statements (EXPECT) | 2, 3 | L3 projection inputs and change indicators |
| Entities | 1, 2 | Key players named in the KIT set |
| Macro Pulse (missing) | 1, 2 | Ranking by the reader's goals; still to build |

## Order of work
1. KIT elicitation with the owner as stand-in executive (about 10 questions: decisions ahead, early warnings, players watched). No design before this.
2. GDTA table from the KIT answers.
3. One brief for one real day, written to ICD 203, every sentence cited and entailment-checked.
4. SAGAT-style test: owner reads, screen blanked, queries from the GDTA table, scored against the data. Then iterate.

## Limits
GDTA and SAGAT come from aviation, military and control rooms; applying them to executive briefings is an adaptation (KITs is the corporate form). Freeze-probe scores depend on recall and the freeze can disturb the task (Sarter and Woods 1995; de Winter et al. 2018). Step 1 needs real users; the owner is the stand-in until others exist.

## Sources
- Endsley, Determining SA requirements (GDTA): https://www.taylorfrancis.com/chapters/mono/10.1201/b11371-9/determining-sa-requirements-mica-endsley
- Endsley, NDIA slides (GDTA drives design, training, evaluation): https://ndia.dtic.mil/wp-content/uploads/2012/armaments/WednesdayEndsley.pdf
- GDTA in ship pilotage (2021): https://publications.polymtl.ca/6652/1/2021_Haffaci_Goal-directed_task_analysis_situation_awareness.pdf
- Herring, Key Intelligence Topics (summary): https://www.scribd.com/document/496120259/KIT
- KITs webinar slides: https://www.slideshare.net/slideshow/how-to-identify-user-needs-with-key-intelligence-topics/57561459
- KITs as Key Intelligence Questions (IACIS 2024): https://www.iacis.org/iis/2024/3_iis_2024_81-93.pdf
- SAGAT overview (SKYbrary): https://skybrary.aero/articles/situation-awareness-global-assessment-technique-sagat
- SAGAT meta-analysis (Human Factors 2019): https://journals.sagepub.com/doi/10.1177/0018720819875376
- Freeze-probe critique (de Winter et al. 2018): https://link.springer.com/article/10.1007/s10111-018-0527-6
- ICD 203 Analytic Standards (DNI): https://www.dni.gov/files/documents/ICD/ICD-203.pdf
