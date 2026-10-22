# Acceptance criteria, revision 3 (proposal)

Date 2026-10-21. Status: **PROPOSAL, nothing in force.** Written for the owner's request that the criteria be 'better and refined'. No bar, `newsreader/bitmob/scorecard.py`, ledger entry, `data/suite*` file or running job was changed or touched for writing (data files were only read). The machine-readable copy is `data/scorecard/criteria_rev3_proposal.json`; it is not loaded by anything.

Method applied: `docs/research/2026-10-21 Acceptance criteria methodology (generic).md` (steps 1 to 8 here, step 9 in section 7, step 10 left to each round), the skill `.claude/skills/acceptance-criteria/SKILL.md` (template, levels, directions, bar rules). Inputs: the Fable review (verdict on the 50 rows, proposed 28, addendum), `scorecard.py`, the rev 2 draft, `exports/world-engine-ontology.yaml`, `probes/world-engine/classify.py` and `world_service2.py`, `data/scorecard/models_r2.json`, `data/suite_r2/*` and `data/suite/source_analysis.json` (there is no `data/suite_r2/source_analysis.json`; F-0072's file in `data/suite/` was used), ledger F-0020, F-0049, F-0072, D-0017, D-0022, D-0024. Numbers marked 'computed this session' were computed from those pinned files by the appendix script and are not yet ledger facts.

Owner decisions applied, not re-asked: grade against Jev (Clef cross-check, Opus tie-break, D-0024); finer topics allowed if they roll up (D-0022); countries outside the 100 allowed (D-0022); an outlet's home country is the default when no place is named (C9 resolved, `source_country.json`). **Still open, written with a placeholder:** OQ-1 the multi-country rule (CO-4), OQ-2 which scope labels the engine reads (SF-1, SF-G1, SF-G2).

## 0. Terms and the rules used

- **Reader**: the CPU program that reads a headline plus the first 250 characters of the description (D-0009). **Jev** is the hosted teacher whose labels are the reference (D-0024); **Clef** is the local cross-check; **Opus** breaks ties. **Engine** is the World engine that consumes the labels.
- **F**: the frozen test set, 11,997 stories from 125 outlets with Jev labels, never trained on (F-0072). **J**: 500 stories drawn at random from F, the set on which Jev, Clef and Opus are compared. **O51**: the F stories from the 51 outlets that have at least 60 stories in F (10,812 stories). Probe sets (`P-...`) are small named sets built to test one behaviour.
- **Baseline**: score of a trivial method. **Ceiling**: how often two competent judges (Jev and Clef) agree on the same items; a reader cannot sensibly be asked to beat it. **Tolerance**: how much reader error the engine absorbs before its output leaves its own run-to-run noise; measured for conditions only (F-0020).
- **Wilson bound**: the edge of what a true rate could be given n items (95%). 0 swaps in 30 items allows a true rate up to 11.4%; 0 of 120, 3.1%; 0 of 420, 0.9%.
- **Pass line** (method step 6.4, applied exactly): a 'share at least y' row passes when the Wilson lower bound clears y; an 'at most x' row passes when the upper bound is under x. Probe sizes below were chosen so that a reader sitting at the (provisional) ceiling can pass (formula in the appendix).
- **Per-outlet and per-topic floors**: floor(n) = pooled bar - 1.96 x sqrt(bar x (1 - bar) / n). A slice counts as failing only when it is below the pooled bar by more than sampling noise at its own n. With 44 to 51 slices, 4 or more falling below by chance has probability under 5% (binomial, p = 0.025), so the allowance is 3.
- **Gate vs graded** (step 8, applied exactly): a row a reader that reads nothing would pass is a **gate**. This moves every error-cap row ('at most x wrong claims') to the gate list, because a silent reader makes no wrong claims. A gate must pass for an area to be accepted but is not in the grade. **Graded** rows are the ones a bad reader can fail. This differs from the Fable set, which graded the caps (K-b, T-b, C-b); the cost is that false-alarm control lives in gates and in the tolerance run (CO-6, TY-7, RC-4, TP-5, CN-1, CN-4), where F-0020 puts it.
- **Grade rule**: area grade = graded rows passed / graded rows; overall = the lowest area grade (not the pooled count `scorecard.py` uses today); an area is done at 90% (owner, 2026-10-20) and only if all its gates and the cross-area gates pass.
- **Six directions**: the sources name left/right, up/down and sideways. I count six as: **L** left (source, data, labels), **R** right (the consumer), **U** up (area level), **D** down (slice), **SN** sideways to neighbours (near-miss look-alikes and the none case), **SE** sideways edits (invariance and flip).
- **Kinds**: graded / gate / informational. **Bar status**: *derived* = from a measurement or a stated definition with an id; *provisional* = carries a placeholder that a named measurement replaces; *open* = waiting on an owner question.

## 1. Summary tables (one per area)

Totals: 64 rows = 26 graded, 29 gate, 9 informational. Bars (graded and gate rows): derived 23, provisional 31, open 1. Informational rows carry no bar (SF-1 is informational with a placeholder bar, open).

| Area | Graded | Gate | Informational | Bars derived | Bars provisional | Bars open |
|---|---|---|---|---|---|---|
| Country | 6 | 7 | 1 | 4 | 8 | 1 |
| Story type | 7 | 3 | 2 | 2 | 8 | 0 |
| Recent (the gate the engine uses) | 4 | 3 | 0 | 3 | 4 | 0 |
| Scope and focus | 0 | 2 | 2 | 2 | 0 | 1 |
| Topic | 5 | 4 | 2 | 3 | 6 | 0 |
| Conditions | 4 | 6 | 2 | 6 | 4 | 0 |
| Cross-area gates | 0 | 4 | 0 | 3 | 1 | 0 |

### Country

| Id | Plain name | Level | Direction | Kind | Bar | Bar status | Replaces |
|---|---|---|---|---|---|---|---|
| CO-1 | Entry country agrees with Jev | model | U | graded | >= ceiling(CO) - 0.03 (provisional 0.89) | provisional: M1 | C1, C2 |
| CO-2 | Per-outlet entry-country floor | model | D | graded | <= 3 outlets | provisional: M1, M4 | new (Fable C-f) |
| CO-3 | Look-alike countries kept apart | model | SN | graded | >= ceiling(P-LA) - 0.03 (provisional 0.89) | provisional: M6 | C5 |
| CO-4 | Multi-country story picks the rule's country | model | SN | graded | >= ceiling(P-MULTI) - 0.05 | open: OQ-1, M6 | new (Fable C-c) |
| CO-5 | Swapping the country name moves the entry | model | SE | graded | >= Jev's own flip rate on P-FLIPC - 0.05 (provisional 0.90) | provisional: M5 | new |
| CO-6 | Engine output unmoved by the reader's entry | pipeline | R | graded | <= 1.0 | derived: F-0020 | new |
| CO-G1 | Source table complete | source | L | gate | >= 100% | derived: D-0015, C9 resolved | C7, C9 |
| CO-G2 | Country label reliable (alpha) | data | L | gate | >= 0.667 (accept 0.80) | derived: Krippendorff 2011 | new |
| CO-G3 | Label list holds the outlets' home countries | data | L | gate | <= 0 after relabel | derived: D-0022, F-0049 | new |
| CO-G4 | Wrong country, per 1,000 stories | model | R | gate | <= T_entry (from CO-6) | provisional: M8 | C2 |
| CO-G5 | Look-alike swaps | model | SN | gate | <= 0 of 420 (Wilson upper 0.9%) | provisional: M8 | C5 |
| CO-G6 | Ambiguous words give no false country | model | SN | gate | >= ceiling(P-AMB) - 0.03 (provisional 0.95) | provisional: M6 | C6 |
| CO-G7 | Countries outside the 100 not forced onto a neighbour | model | SN | gate | <= 0 of 100 (Wilson upper 3.7%) | provisional: M8 | C8 |
| CO-I1 | Per-region recall report | model | U | informational | no bar | n/a | C3, C4 |

### Story type

| Id | Plain name | Level | Direction | Kind | Bar | Bar status | Replaces |
|---|---|---|---|---|---|---|---|
| TY-1 | Weight class agrees with Jev | model | U | graded | >= ceiling(TY) - 0.03 (provisional 0.90) | provisional: M1 | T2 |
| TY-2 | Fact kept at full weight | model | R | graded | <= Jev-vs-Clef rate of the same error on J + 10 per 1,000 | provisional: M1, M8 | new (Fable T-c) |
| TY-3 | Tense flip moves fact to forecast | model | SE | graded | >= Jev's own flip rate on P-FLIPT - 0.05 (provisional 0.90) | provisional: M5 | T6 |
| TY-4 | Report quoting a forecast stays fact | model | SN | graded | >= ceiling(P-NEAR-T) - 0.03 | provisional: M6 | T5, T4 |
| TY-5 | Headline-only stories | model | D | graded | >= TY-1 bar - 0.05 (provisional 0.85) | provisional: M1 | T9 |
| TY-6 | Per-outlet weight-class floor | model | D | graded | <= 3 outlets | provisional: M1 | new (Fable T-f) |
| TY-7 | Engine output unmoved by the reader's class | pipeline | R | graded | <= 1.0 | derived: F-0020 | new |
| TY-G1 | F has headline-only stories like the live feed | source | L | gate | <= 0.05 | provisional: M0 | new |
| TY-G2 | Type labels reliable (alpha) | data | L | gate | >= 0.667 (accept 0.80) | derived: Krippendorff 2011, T-0011 | T1 |
| TY-G3 | Opinion read as fact, per 1,000 stories | model | R | gate | <= Jev-vs-Clef rate on J + 5 per 1,000 | provisional: M1, M8 | T7 |
| TY-I1 | AP per type label (progress) | model | U | informational | no bar | n/a | T2 (AP rows), T3, T8 |
| TY-I2 | Type weights are guesses | pipeline | R | informational | no bar | n/a | new |

### Recent (the gate the engine uses)

| Id | Plain name | Level | Direction | Kind | Bar | Bar status | Replaces |
|---|---|---|---|---|---|---|---|
| RC-1 | Recent cut agrees with Jev | model | U | graded | >= ceiling(RC) - 0.02 (provisional 0.97) | provisional: M1 | S2 (recent part) |
| RC-2 | Old events are not recent | model | SN | graded | >= ceiling(P-OLD) - 0.05 (provisional 0.90) | provisional: M6 | S4 |
| RC-3 | Date cue flips recent | model | SE | graded | >= Jev's flip rate on P-FLIPR - 0.05 (provisional 0.90) | provisional: M5 | new |
| RC-4 | Replay unmoved by the reader's gate | pipeline | R | graded | <= 1.0 | derived: F-0020 | new |
| RC-G1 | Fresh stories wrongly dropped | model | R | gate | <= T_drop (from RC-4) | provisional: M8 | S-a (Fable) |
| RC-G2 | Recent label reliable (alpha) | data | L | gate | >= 0.667 (accept 0.80) | derived: Krippendorff 2011 | S1 |
| RC-G3 | The date the labeller saw equals the date the reader sees | pipeline | L | gate | >= 100% | derived: D-0009, build_trainset.py:103 | new |

### Scope and focus

| Id | Plain name | Level | Direction | Kind | Bar | Bar status | Replaces |
|---|---|---|---|---|---|---|---|
| SF-1 | Labels the engine will read agree with Jev | model | U | informational | >= ceiling(L) - 0.03 | open: OQ-2, M1 | S2, S5, S6 |
| SF-G1 | Read scope labels reliable (alpha) | data | L | gate | >= 0.667 (accept 0.80) | derived: Krippendorff 2011, F-0049 | S1 |
| SF-G2 | Every graded scope label has a reader in the engine | pipeline | R | gate | <= 0 | derived: skill rule 6, D-0017 | S3, S9 |
| SF-I1 | Agreement per scope label (report) | model | D | informational | no bar | n/a | S7, S8 |

### Topic

| Id | Plain name | Level | Direction | Kind | Bar | Bar status | Replaces |
|---|---|---|---|---|---|---|---|
| TP-1 | Topic agrees with Jev | model | U | graded | >= ceiling(TP) - 0.05 (provisional 0.79) | provisional: M1 | P2 |
| TP-2 | Reader's topic blocks a condition Jev's allows | model | R | graded | <= Jev-vs-Clef rate on J + 20 per 1,000 | provisional: M1, M8 | P4, P7 (part) |
| TP-3 | Per-topic recall floor | model | D | graded | <= 3 topics | provisional: M1 | P3 |
| TP-4 | Per-outlet topic floor | model | D | graded | <= 3 outlets | provisional: M1 | new (Fable P-f) |
| TP-5 | Engine output unmoved by the reader's topic | pipeline | R | graded | <= 1.0 | derived: F-0020 | new |
| TP-G1 | Topic labels reliable (alpha) | data | L | gate | >= 0.667 (accept 0.80) | derived: Krippendorff 2011 | P1 |
| TP-G2 | Finer topics roll up to the 49 | data | L | gate | >= 100% | derived: D-0022 | new |
| TP-G3 | Non-news gets no extra moving topic | model | SN | gate | <= T_mask (from TP-5) | provisional: M8 | P7, S9 |
| TP-G4 | Typos and source prefixes do not change the topic | model | SE | gate | >= Jev's rate on the same edits - 0.02 (provisional 0.95) | provisional: M5 | new |
| TP-I1 | Named confusions each round | model | SN | informational | no bar | n/a | P4 |
| TP-I2 | 'Other' is not a dump (report) | model | D | informational | no bar | n/a | P5 |

### Conditions

| Id | Plain name | Level | Direction | Kind | Bar | Bar status | Replaces |
|---|---|---|---|---|---|---|---|
| CN-1 | Keys inside engine tolerance | pipeline | U | graded | >= all graded keys | derived: F-0020, S-0003 | K2, K7 |
| CN-2 | Direction flip | model | SE | graded | >= Jev's flip rate on P-FLIPK - 0.05 (provisional 0.90) | provisional: M5 | K4 |
| CN-3 | Strength is honest | model | U | graded | <= 0.10 | provisional: M8 | K8 |
| CN-4 | Engine output unmoved by the reader's readings | pipeline | R | graded | <= 1.0 | derived: F-0020 | K7 |
| CN-G1 | False alarms per key | model | R | gate | <= 2.5 per 1,000 (Wilson upper bound) | derived: F-0020 | K6, K5 |
| CN-G2 | Both directions fire on one story | model | SN | gate | <= Jev's rate (27.8 per 1,000) + 5 (provisional 32.80) | provisional: M8 | new (Fable K-c) |
| CN-G3 | Condition labels reliable (alpha) | data | L | gate | >= 0.667 (accept 0.80) | derived: Krippendorff 2011, F-0049 | K1 |
| CN-G4 | Enough positives to prove the tolerance | data | L | gate | >= 109 | derived: F-0020, Wilson arithmetic | K3 |
| CN-G5 | Non-news gets no reading | model | SN | gate | <= T_none (M8) | provisional: M8 | P7 |
| CN-G6 | Per-outlet false-alarm rate | model | D | gate | <= 3 outlets | derived: F-0020, F-0072 | new |
| CN-I1 | Mean AP per key (progress) | model | U | informational | no bar | n/a | K2 (AP bar) |
| CN-I2 | Per-item proof each round | data | D | informational | no bar | n/a | K9 |

### Cross-area gates

| Id | Plain name | Level | Direction | Kind | Bar | Bar status | Replaces |
|---|---|---|---|---|---|---|---|
| X-G1 | Speed | pipeline | R | gate | < 100 ms | derived: D-0007 | C10 |
| X-G2 | Regression | pipeline | R | gate | <= 0 | derived: Breck 2017, scorecard rule | C11, T10, S8, P10, K10 |
| X-G3 | Frozen set never trained on | data | L | gate | <= 0 | derived: F-0072, Datasheets (Gebru 2021) | new |
| X-G4 | Outlet mix covers the live feed | source | L | gate | <= 0 | provisional: M8 | new |

## 2. The six areas

### 2.1 Country

Engine use: the only use is the entry node, `COUNTRY:x` when x is one of the 100 in `countries_world100.csv`, else `WORLD:world` (`world_service2.py:166`, `:445`). One entry per story. Rule D-0015: a named country wins, else the outlet's home country, never both. Consumer cost is stated as low / medium / high.

**Element register (step 1)**

| Element | Definition | Read by / how | Cost of a miss | Cost of a false alarm | Alpha (n) | Status |
|---|---|---|---|---|---|---|
| named country (100) | the country the story is mainly about, named in the text | entry node COUNTRY:x | medium: the story spreads over the whole world | high: it moves the wrong population | not measured | graded (CO-1, CO-2, CO-3, CO-5) |
| global / no single country | no one country | entry WORLD:world | low | medium | not measured | graded inside CO-1 |
| country outside the 100 (irl, nzl, sgp, hkg, others) | own code kept (D-0022) | engine maps an unknown code to WORLD:world | low | medium | not measured | gate (CO-G7) |
| outlet home-country fallback | `source_country.json`, used only when no place is named; the 9 former 'check' outlets take their home country | entry when no country is named | medium | medium | n/a (table) | gate (CO-G1) |
| multi-country story | two or more countries named | engine takes one entry only | medium | medium | not measured | graded, rule OPEN (CO-4, OQ-1) |

**Coverage check (step 4): the six directions**

| Direction | Criteria | Reason if empty |
|---|---|---|
| left (source/data) | CO-G1, CO-G2, CO-G3 |  |
| right (consumer) | CO-6, CO-G4 |  |
| up (area) | CO-1, CO-I1 |  |
| down (slice) | CO-2 |  |
| sideways: near-miss / none | CO-3, CO-4, CO-G5, CO-G6, CO-G7 |  |
| sideways: invariance / flip | CO-5 |  |

Levels present: data, model, pipeline, source. Source-level rows shared by all areas: X-G4 (outlet mix covers the live feed); data-level: X-G3 (frozen set never trained on); pipeline: X-G1 (speed), X-G2 (regression).

**Criteria (step 7), one atomic sentence each**

- **CO-1 - Entry country agrees with Jev** (model, up, graded, bar provisional). On **F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist))**, **the country reader (script checker v2 or the trained model, whichever feeds the entry node)'s** **share of stories whose entry node (country id if one of the 100, else world) equals Jev's** for **all stories** is **>= ceiling(CO) - 0.03 (provisional 0.89)**, because **a reader above the ceiling copies one judge's noise and below the majority-class baseline (usa, 0.287 of F) the bar is empty**; it fails when **"Grenfell Tower residents raised concerns months before fire" is read as usa (the script, club probe set; reviewer: gbr) [real]**.
  Today: Not scorable yet. Trained model: 0.892 on a 16-class label set where 'other' (14.6% of F) carries no entry country, so not comparable to 100 countries. Script checker: named-country recall 0.882, precision 0.910 against a Sonnet reviewer, not Jev (F-0062). Bound: n = 11,997: half-width 0.006 at 0.89; pass when the Wilson lower bound is >= the bar. Replaced by: M1: Jev-vs-Clef entry-country agreement on J (ceiling). Stand-in 0.92 = Jev-Sonnet 46/50 (Wilson 0.81 to 0.97, F-0049). Derivation: F-0049, D-0024, D-0015. Nothing-reader test: fails it (so it is graded).
- **CO-2 - Per-outlet entry-country floor** (model, down, graded, bar provisional). On **O51 (n = 10,812; the F stories from the 51 outlets with at least 60 stories in F (F-0072); labelled by Jev (labels exist))**, **the country reader's** **count of outlets whose entry-country agreement with Jev is below floor(n) = CO-1 bar - 1.96*sqrt(bar*(1-bar)/n)** for **each outlet with at least 60 stories** is **<= 3 outlets**, because **an outlet at exactly the CO-1 bar falls under its floor by chance 2.5% of the time, so 4 or more of 51 happens by chance only 3.9% (binomial)**; it fails when **irishtimes.com scores 0.61 over 157 stories (floor about 0.84) [real]**.
  Today: F-0072 scores put 31 of 51 outlets under the floor, but 5 of them (irishtimes, breakingnews.ie, nzherald, channelnewsasia, straitstimes) were labelled when their home country was not in Jev's list, so this is not a reader result yet. Bound: outlet n 60 to 405: half-width 0.04 to 0.015. Replaced by: inherits CO-1 (M1); also needs the label-space fix CO-G3 (M4). Derivation: F-0072, CO-1. Nothing-reader test: fails it (so it is graded).
- **CO-3 - Look-alike countries kept apart** (model, sideways (neighbour), graded, bar provisional). On **P-LA (n = 420; 6 pairs x 70 (Niger/Nigeria, Sudan/South Sudan, DR Congo/Congo, North/South Korea, Guinea/Papua New Guinea, Dominica/Dominican Republic) mined by script from CC-News outside F and training, not by reader output; labelled by Jev (hosted; needs the owner's yes for new items), Clef (local), Opus on disagreements (D-0024))**, **the country reader's** **share given the story's own country (not its look-alike)** for **six look-alike pairs** is **>= ceiling(P-LA) - 0.03 (provisional 0.89)**, because **these pairs have a predictable cause and the ceiling must be measured on exactly these items (n = 420 so that a reader at 0.92 has a Wilson lower bound of 0.89)**; it fails when **"Nigeria: While Jonathan Keeps Mum, CBN Speaks On Controversial N13 Billion Seized From Lagos Apartment" is read as Niger (a real story from the existing look-alike probe; no failure observed, 0 of 30) [real story, hypothetical failure]**.
  Today: Existing probe: 0 swaps of 30 (Wilson upper 11%), too small for any claim (F-0062). Bound: n = 420. Replaced by: M6: Jev-vs-Clef agreement on P-LA; carried 0.89 from CO-1 until then. Derivation: D-0024, F-0049. Nothing-reader test: fails it (so it is graded).
- **CO-4 - Multi-country story picks the rule's country** (model, sideways (neighbour), graded, bar open). On **P-MULTI (n = 300; stories naming 2 or more in-list countries, mined by script from CC-News outside F; labelled by Jev (hosted; needs the owner's yes for new items), Clef (local), Opus on disagreements (D-0024))**, **the country reader's** **share whose entry country equals the country chosen by <RULE-OQ1>** for **stories naming two or more countries** is **>= ceiling(P-MULTI) - 0.05**, because **the engine takes exactly one entry country (world_service2.py:166) and the rule for choosing is undefined; the ceiling cannot be measured until a rule exists**; it fails when **"Vice President Pence Sends Warning To North Korea Amid Rising Tensions" (reviewer: kor, prk, usa) enters the engine at the wrong one of three [real story, hypothetical failure]**.
  Today: No rule, no measure. Multi-country stories exist in the reviewer sample (country-val items 3 and 5); D-0015 says 'countries' (plural). Bound: n = 300. Replaced by: OQ-1 (the owner's rule); then M6. Derivation: OQ-1, D-0015. Nothing-reader test: fails it (so it is graded).
- **CO-5 - Swapping the country name moves the entry** (model, sideways (edit), graded, bar provisional). On **P-FLIPC (n = 150; real F headlines naming exactly one in-list country, name replaced by another in-list country by script; label by construction; labelled by no labeller (labels by construction); 30 pairs spot-checked by hand)**, **the country reader's** **share of pairs where the entry country follows the substituted name** for **stories naming one in-list country** is **>= Jev's own flip rate on P-FLIPC - 0.05 (provisional 0.90)**, because **a reader that keys on topic words and not on the name cannot be right for the right reason; n = 150 gives a Wilson lower bound of 0.90 at an observed 0.95**; it fails when **"Floods displace 40,000 in Niger" becomes "...in Chad" and the reader still says Niger [invented]**.
  Today: not built. Bound: n = 150. Replaced by: M5: run Jev on the same 150 pairs (about $0.1). Derivation: CheckList DIR (skill section 3), D-0024. Nothing-reader test: fails it (so it is graded).
- **CO-6 - Engine output unmoved by the reader's entry** (pipeline, right, graded, bar derived). On **E-C (n = 1,000; random 1,000 of F replayed with the entry node taken from the reader; a new mode of sensitivity.py, CPU only; labelled by none; Jev's entry is the reference)**, **the country reader's** **ratio of the engine's output drift (reader's entry vs Jev's entry) to the engine's run-to-run noise** for **1,000 F stories replayed through sensitivity.py** is **<= 1.0**, because **F-0020 defines the engine's tolerance as drift inside its own noise (ratio 1.0 is the line; TPR .9 / FPR .0025 sits at 1.0004)**; it fails when **a reader that sends 5% of stories to a neighbour pushes the ratio to 1.3 (an invented figure; F-0020's real failing point for conditions is ratio 1.7) [invented]**.
  Today: not built. Bound: ratio, not a share. Derivation: F-0020. Nothing-reader test: fails it (so it is graded).
- **CO-G1 - Source table complete** (source, left, gate, bar derived). On **S-all (n = 188; all F outlets plus all live-queue feeds (F-0072); labelled by owner (one-off check))**, **the country pipeline's** **share of outlets and feeds with a row in source_country.json that the owner has confirmed** for **every outlet in F (125) and every live feed (63)** is **>= 100%**, because **the fallback has no other source; C9 is resolved (the 9 former 'check' outlets take their home country, 2026-10-20)**; it fails when **a new feed with no row in the table [invented]**.
  Today: Scorecard C9 = 1.0 for outlets in labelled sets; live feeds not checked. Bound: exact count. Derivation: D-0015, C9 resolved. Nothing-reader test: passes it (so it is a gate).
- **CO-G2 - Country label reliable (alpha)** (data, left, gate, bar derived). On **J (n = 500; seeded random draw from F; labelled by Jev (have), Clef (to run), Opus on disagreements (D-0024))**, **the labellers'** **Krippendorff alpha of the entry-country label between Jev and Clef** for **entry country** is **>= 0.667 (accept 0.80)**, because **a label judges cannot apply the same way measures noise; 0.667 is the lowest tolerated value**; it fails when **Jev codes the Irish Times story "Trade surplus down 9% as exports to Britain rebound" as deu [real]**.
  Today: not measured (Jev-Sonnet raw agreement 46/50 = 0.92). Bound: J: 500. Derivation: Krippendorff 2011. Nothing-reader test: passes it (so it is a gate).
- **CO-G3 - Label list holds the outlets' home countries** (data, left, gate, bar derived). On **O51-home (n = 5; the 5 O51 outlets with home irl/nzl/sgp (irishtimes, breakingnews.ie, nzherald, channelnewsasia, straitstimes); labelled by source_country.json)**, **the labellers'** **count of O51 outlets whose home country was missing from Jev's list when F was labelled** for **irl, nzl, sgp, hkg outlets** is **<= 0 after relabel**, because **D-0022 lets irl, nzl, sgp, hkg keep their own codes, so labels made without them cannot grade a reader that outputs them**; it fails when **irishtimes.com 'Providing Orkambi to CF sufferers will cost lives': Jev gbr, reader global [real]**.
  Today: 5 of 5 outlets affected. Bound: count. Derivation: D-0022, F-0049. Nothing-reader test: passes it (so it is a gate).
- **CO-G4 - Wrong country, per 1,000 stories** (model, right, gate, bar provisional). On **F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist))**, **the country reader's** **stories whose entry is a country other than Jev's (not a miss to world) per 1,000 stories** for **all stories** is **<= T_entry (from CO-6)**, because **a wrong country moves the wrong population while a miss only spreads the story over the world; each has its own bar**; it fails when **"Man United complete 35m signing of Victor Lindelof" is read as Angola (the script, real; reviewer: Sweden) [real]**.
  Today: Trained model: 65.4 per 1,000 stories (785 of 11,997; computed this session) name a different country from Jev; another 43 per 1,000 say global/other where Jev names one. Bound: n = 11,997: upper bound = observed + about 0.4 per 1,000. Replaced by: M8 (entry tolerance run); Fable's 30 per 1,000 had no derivation. Derivation: CO-6, F-0020. Nothing-reader test: passes it (so it is a gate).
- **CO-G5 - Look-alike swaps** (model, sideways (neighbour), gate, bar provisional). On **P-LA (n = 420; 6 pairs x 70 (Niger/Nigeria, Sudan/South Sudan, DR Congo/Congo, North/South Korea, Guinea/Papua New Guinea, Dominica/Dominican Republic) mined by script from CC-News outside F and training, not by reader output; labelled by Jev (hosted; needs the owner's yes for new items), Clef (local), Opus on disagreements (D-0024))**, **the country reader's** **count of look-alike swaps** for **six look-alike pairs** is **<= 0 of 420 (Wilson upper 0.9%)**, because **0 of 30 (C5's pass) allows a true rate of up to 11%; 0 of 420 allows 0.9%**; it fails when **"Niger floods displace 40,000" read as Nigeria [invented]**.
  Today: 0 of 30 (upper 11%). Bound: 0 of 420: upper 0.9%. Replaced by: the tolerable swap rate comes from CO-6 (M8). Derivation: CO-6, F-0062. Nothing-reader test: passes it (so it is a gate).
- **CO-G6 - Ambiguous words give no false country** (model, sideways (neighbour), gate, bar provisional). On **P-AMB (n = 200; script-mined from CC-News outside F by the ambiguous word and club lists, not by reader output; labelled by Jev (hosted; needs the owner's yes for new items), Clef (local), Opus on disagreements (D-0024))**, **the country reader's** **share of stories given no country other than Jev's** for **Georgia, Jordan, Chad, turkey the bird, club and team names** is **>= ceiling(P-AMB) - 0.03 (provisional 0.95)**, because **clubs are the known failure mode (clean share 0.70, precision 0.53 at 30 probes)**; it fails when **"Man United complete 35m signing of Victor Lindelof" read as Angola (benfica -> ago) [real]**.
  Today: club clean 0.70, ambiguous clean 0.93 (30 probes each, F-0062). Bound: n = 200. Replaced by: M6; 0.95 is the old round value kept as a placeholder. Derivation: D-0024, F-0062. Nothing-reader test: passes it (so it is a gate).
- **CO-G7 - Countries outside the 100 not forced onto a neighbour** (model, sideways (neighbour), gate, bar provisional). On **P-OUT (n = 100; script-mined CC-News stories naming a country outside the 100, outside F; labelled by Jev (hosted; needs the owner's yes for new items), Clef (local), Opus on disagreements (D-0024))**, **the country reader's** **count of stories about a country outside the 100 given an in-list neighbour's code** for **irl, nzl, sgp, hkg and any other country the reader finds** is **<= 0 of 100 (Wilson upper 3.7%)**, because **D-0022 gives them their own codes; the engine maps a code outside its 100 to WORLD:world, so the reader must never name a wrong in-list country instead**; it fails when **"Georgian economic growth accelerates to 5 pct y/y in Q1" read as the US state or as a neighbour (a real story, reviewer: Georgia) [real story, hypothetical failure]**.
  Today: 11 of 14 off-list stories handled (F-0062). Bound: 0 of 100: upper 3.7%. Replaced by: tolerable rate from CO-6 (M8). Derivation: D-0022, world_service2.py:166. Nothing-reader test: passes it (so it is a gate).
- **CO-I1 - Per-region recall report** (model, up, informational, bar n/a). **CO-I1** (information, no bar): on J (n = 500; seeded random draw from F; labelled by Jev (have), Clef (to run), Opus on disagreements (D-0024)), the country reader gives entry-country agreement per UN region for regions; reported each round, never graded.
  Today: not built.

### 2.2 Story type

Engine use: the engine cuts each of the four probabilities at 0.5 and takes one weight class: fact (happened or announced, not opinion, not forecast) 1.0, forecast 0.3, opinion 0.3, unclear 0.5 (`classify.type_weight`, `type_weights.csv`; the three non-fact weights are marked 'guess'). Happened versus announced is not distinguished by the engine, so confusing those two costs nothing (this is why old T4 is dropped).

**Element register (step 1)**

| Element | Definition | Read by / how | Cost of a miss | Cost of a false alarm | Alpha (n) | Status |
|---|---|---|---|---|---|---|
| happened | reported as having happened | with announced: fact if neither opinion nor forecast | high: a fact at forecast weight keeps 30% of its effect | medium | not measured | graded via TY-1, TY-2 |
| announced | a plan or statement made | same class as happened | high | medium | not measured | graded via TY-1 |
| opinion | mainly commentary | weight 0.3; a story with opinion >= 0.5 is also dropped by the collect gate | high: an opinion at fact weight enters at 3.3 times | medium | not measured | graded via TY-1; gate TY-G3 |
| forecast | mainly a prediction | weight 0.3 | medium | high: 1,040 Jev-fact stories are read as forecast | not measured | graded via TY-1, TY-3, TY-4 |

**Coverage check (step 4): the six directions**

| Direction | Criteria | Reason if empty |
|---|---|---|
| left (source/data) | TY-G1, TY-G2 |  |
| right (consumer) | TY-2, TY-7, TY-G3, TY-I2 |  |
| up (area) | TY-1, TY-I1 |  |
| down (slice) | TY-5, TY-6 |  |
| sideways: near-miss / none | TY-4 |  |
| sideways: invariance / flip | TY-3 |  |

Levels present: data, model, pipeline, source. Source-level rows shared by all areas: X-G4 (outlet mix covers the live feed); data-level: X-G3 (frozen set never trained on); pipeline: X-G1 (speed), X-G2 (regression).

**Criteria (step 7), one atomic sentence each**

- **TY-1 - Weight class agrees with Jev** (model, up, graded, bar provisional). On **F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist))**, **the type reader's** **share of stories whose weight class (fact / forecast / opinion / unclear, each probability cut at 0.5, classify.type_weight) equals Jev's** for **all stories** is **>= ceiling(TY) - 0.03 (provisional 0.90)**, because **the weight class is all the engine takes from this area (fact 1.0, forecast 0.3, opinion 0.3, unclear 0.5)**; it fails when **"Booking opens for 60th Anniversary Dublin Theatre Festival" (breakingnews.ie): Jev fact, reader forecast (p 0.62) [real]**.
  Today: Ensemble 0.823 (Wilson 0.816 to 0.830); always-fact baseline 0.798 (0.791 to 0.805); computed this session on F. Bound: n = 11,997: half-width 0.007. Replaced by: M1: Jev-vs-Clef class agreement on J. No usable stand-in: Jev-Sonnet 0.71 per label (F-0049) covers 10 mixed labels and is below the always-fact baseline 0.798. 0.90 is Fable's value carried. Derivation: F-0049, D-0024. Nothing-reader test: fails it (so it is graded).
- **TY-2 - Fact kept at full weight** (model, right, graded, bar provisional). On **F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist))**, **the type reader's** **Jev-fact stories given any other class (weight below 1.0), per 1,000 stories** for **fact** is **<= Jev-vs-Clef rate of the same error on J + 10 per 1,000**, because **the engine multiplies a reading by the weight, so a fact read as forecast keeps 30% of its effect; a reader that outputs unclear for everything fails it**; it fails when **"James Tedesco returns to captain Kangaroos in Rugby League World Cup": Jev fact, reader forecast (p 0.74) [real]**.
  Today: 130.8 per 1,000 stories (1,569 of 11,997; Wilson 12.5% to 13.7%): 1,040 to forecast, 431 to opinion, 98 to unclear. Bound: n = 11,997; the claim 'at most x' needs the upper bound below x. Replaced by: M1 gives the judge-judge rate; M8 type run replaces the +10. Derivation: D-0024, F-0020 form. Nothing-reader test: fails it (so it is graded).
- **TY-3 - Tense flip moves fact to forecast** (model, sideways (edit), graded, bar provisional). On **P-FLIPT (n = 150; 150 pairs made by script from F headlines ("X raised rates" / "X will raise rates"), label by construction; labelled by no labeller (labels by construction); 30 pairs spot-checked by hand)**, **the type reader's** **share of pairs where the plain version stays fact and the 'will' version crosses 0.5 into forecast** for **fact vs forecast** is **>= Jev's own flip rate on P-FLIPT - 0.05 (provisional 0.90)**, because **crossing 0.5 is what the engine sees, so 'drops by half' (T6) is replaced by 'changes class'**; it fails when **"Fed raises rates" vs "Fed will raise rates" both read as fact [invented]**.
  Today: not built. Bound: n = 150. Replaced by: M5: Jev on the 150 pairs. Derivation: CheckList DIR, D-0024. Nothing-reader test: fails it (so it is graded).
- **TY-4 - Report quoting a forecast stays fact** (model, sideways (neighbour), graded, bar provisional). On **P-NEAR-T (n = 400; CC-News outside F, headline or description holds a prediction phrase (predicts, warns of more, expected to) while the main item happened; script-mined, then screened by Clef; labelled by Jev (hosted; needs the owner's yes for new items), Clef (local), Opus on disagreements (D-0024))**, **the type reader's** **share given the labellers' agreed weight class** for **fact stories that quote a prediction** is **>= ceiling(P-NEAR-T) - 0.03**, because **the biggest single confusion in F is fact read as forecast, so the near-miss set targets it**; it fails when **"Stock investors are ready to move on from the AI rout. Credit investors are not": Jev fact, reader forecast (p 0.66) [real]**.
  Today: not built; the existing F confusion is 1,040 such cases. Bound: n = 400. Replaced by: M6; no stand-in. Fact -> forecast is the largest measured error (1,040 of 9,571 Jev-fact stories). Derivation: D-0024. Nothing-reader test: fails it (so it is graded).
- **TY-5 - Headline-only stories** (model, down, graded, bar provisional). On **P-HEAD (n = 400; 400 random F stories with the description removed; headline-only relabelled; labelled by Jev (hosted; needs the owner's yes for new items), Clef (local), Opus on disagreements (D-0024))**, **the type reader's** **weight-class agreement with the labellers** for **stories with no description** is **>= TY-1 bar - 0.05 (provisional 0.85)**, because **live bank headlines carry no description, and F has none either (shortest description in testA is 60 characters)**; it fails when **"Pope highlights arms trade in Easter sermon" with the description removed is read as opinion [real headline, hypothetical failure]**.
  Today: not built; F cannot supply this slice. Bound: n = 400: half-width 0.03. Replaced by: follows TY-1 (M1); the 0.05 slice gap is carried from Fable's T-e. Derivation: TY-1, world_service2.py prepare_feed. Nothing-reader test: fails it (so it is graded).
- **TY-6 - Per-outlet weight-class floor** (model, down, graded, bar provisional). On **O51 (n = 10,812; the F stories from the 51 outlets with at least 60 stories in F (F-0072); labelled by Jev (labels exist))**, **the type reader's** **count of outlets whose class agreement is below floor(n) (TY-1 bar - 1.96*sqrt(bar(1-bar)/n))** for **each outlet with at least 60 stories** is **<= 3 outlets**, because **F-0072 shows type agreement varies by outlet; the 3-outlet allowance is the binomial chance count**; it fails when **npr.org scores 0.64 over 80 stories, bloomberg.com 0.72 over 64, cnbc.com 0.73 over 101 [real]**.
  Today: On testA only (44 outlets with n >= 60): 6 below a floor built on 0.82, 31 below one built on 0.90. Bound: outlet n 60 to 400. Replaced by: inherits TY-1 (M1). Derivation: F-0072, TY-1. Nothing-reader test: fails it (so it is graded).
- **TY-7 - Engine output unmoved by the reader's class** (pipeline, right, graded, bar derived). On **E-T (n = 1,000; random 1,000 of F replayed with the weight from the reader's class; labelled by none; Jev is the reference)**, **the type reader's** **ratio of engine output drift (reader's weight class vs Jev's) to run-to-run noise** for **1,000 F stories** is **<= 1.0**, because **tolerance is drift inside the engine's own noise (F-0020); the weights are 'guess' status in type_weights.csv, so this also tests how much they matter**; it fails when **a reader whose forecast errors move the engine's ratio to 1.7 (the F-0020 conditions failing point, used as an illustration) [invented]**.
  Today: not built. Bound: ratio. Derivation: F-0020. Nothing-reader test: fails it (so it is graded).
- **TY-G1 - F has headline-only stories like the live feed** (source, left, gate, bar provisional). On **F-vs-live (n = 7,702; F against the live queue (7,702 items, 63 feeds, F-0072); labelled by none)**, **the pool's** **absolute gap between the share of F stories and of live-feed items with description under 60 characters** for **description length** is **<= 0.05**, because **F's shortest description is 60 characters (testA, 9,997 stories) while ticker headlines have none**; it fails when **F share 0.00 vs a live feed whose items are mostly headline-only [invented]**.
  Today: F share 0 (min description 60 characters); live share not counted. Bound: counts. Replaced by: M0 counts the live share (the queue file is not readable from this session); 0.05 is a placeholder slice gap. Derivation: F-0072. Nothing-reader test: passes it (so it is a gate).
- **TY-G2 - Type labels reliable (alpha)** (data, left, gate, bar derived). On **J (n = 500; seeded random draw from F; labelled by Jev (have), Clef (to run), Opus on disagreements (D-0024))**, **the labellers'** **lowest Krippendorff alpha among happened, announced, opinion, forecast between Jev and Clef** for **four type labels** is **>= 0.667 (accept 0.80)**, because **below 0.667 the label is not reliably readable**; it fails when **Jev reads an explainer as opinion where Clef reads it as unclear [invented]**.
  Today: not measured (T-0011 not run). Bound: J: 500. Derivation: Krippendorff 2011, T-0011. Nothing-reader test: passes it (so it is a gate).
- **TY-G3 - Opinion read as fact, per 1,000 stories** (model, right, gate, bar provisional). On **F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist))**, **the type reader's** **Jev-opinion stories given class fact, per 1,000 stories** for **opinion** is **<= Jev-vs-Clef rate on J + 5 per 1,000**, because **the dearest direction: an opinion at fact weight enters at 3.3 times (1.0 vs 0.3)**; it fails when **"California Republicans hit rock bottom" (politico): Jev opinion, reader fact (p opinion 0.49) [real]**.
  Today: 8.5 per 1,000 stories (102; Wilson 0.7% to 1.0%). Bound: upper bound 1.0%. Replaced by: M1; M8 replaces the +5. Derivation: D-0024, F-0020 form. Nothing-reader test: passes it (so it is a gate).
- **TY-I1 - AP per type label (progress)** (model, up, informational, bar n/a). **TY-I1** (information, no bar): on F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist)), the type reader gives average precision for four labels; reported each round, never graded.
  Today: ensemble: happened 0.988, announced 0.948, opinion 0.807, forecast 0.750.
- **TY-I2 - Type weights are guesses** (pipeline, right, informational, bar n/a). **TY-I2** (information, no bar): on F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist)), the engine gives status of weights in type_weights.csv for forecast 0.3, opinion 0.3, unclear 0.5; reported each round, never graded.
  Today: the three non-fact weights are marked 'guess' in the file.

### 2.3 Recent (the gate the engine uses)

Engine use: `gate_ok` needs recent >= 0.3 (with happened or announced >= 0.5 and opinion < 0.5). It is consumed by the stage-1 collect of the saved news ledger (`world_service2.py:105`, also `audience.py`, `demo.py`). The live request path (`:166` on) and the ticker path (`prepare_feed`) use `type_weight` and do not drop on recent, so Fable's 'the single most expensive error' holds for the saved-ledger replay only. In `classify.read` recent also scales each reading's amount, but the service recomputes the amount without it.

**Element register (step 1)**

| Element | Definition | Read by / how | Cost of a miss | Cost of a false alarm | Alpha (n) | Status |
|---|---|---|---|---|---|---|
| recent (x|recent) | the story is about something current | cut at 0.3 in the collect gate | high: the event is deleted from the replay, no partial credit | low | not measured (T-0011 not run) | graded (RC-1 to RC-4), gates RC-G1 to RC-G3 |

**Coverage check (step 4): the six directions**

| Direction | Criteria | Reason if empty |
|---|---|---|
| left (source/data) | RC-G2, RC-G3 |  |
| right (consumer) | RC-4, RC-G1 |  |
| up (area) | RC-1 |  |
| down (slice) | - | a per-outlet slice would hold about 5 not-recent stories per 100; the slice that matters (date cue type) is P-OLD / P-FLIPR |
| sideways: near-miss / none | RC-2 |  |
| sideways: invariance / flip | RC-3 |  |

Levels present: data, model, pipeline. Source-level rows shared by all areas: X-G4 (outlet mix covers the live feed); data-level: X-G3 (frozen set never trained on); pipeline: X-G1 (speed), X-G2 (regression).

**Criteria (step 7), one atomic sentence each**

- **RC-1 - Recent cut agrees with Jev** (model, up, graded, bar provisional). On **R-set (n = 9,997; the testA stories with Jev scores in data/trainset/testA.jsonl (481 have recent < 0.3); labelled by Jev (labels exist))**, **the recent reader (none exists yet)'s** **share of stories where (reader recent >= 0.3) equals (Jev recent >= 0.3)** for **recent** is **>= ceiling(RC) - 0.02 (provisional 0.97)**, because **a story below 0.3 is dropped from the saved-ledger replay (classify.py:61, world_service2.py:105); always-recent already scores 0.952, so the bar must sit above that**; it fails when **"Stocks in focus on 20 March 2018" (economictimes, Jev recent 0.24) read as current [real story, hypothetical failure]**.
  Today: Baseline 0.952; no recent reader is trained (the suite covers type, topic, country, conditions only). Bound: n = 9,997: half-width 0.004. Replaced by: M1 plus P-OLD enrichment (J holds only about 24 not-recent stories); 0.97 is Fable's S-a value carried; baseline always-recent = 0.952. Derivation: D-0024. Nothing-reader test: fails it (so it is graded).
- **RC-2 - Old events are not recent** (model, sideways (neighbour), graded, bar provisional). On **P-OLD (n = 150; script-mined CC-News outside F by phrases ("years after", "in 2015", "anniversary"), not reader output; labelled by Jev (hosted; needs the owner's yes for new items), Clef (local), Opus on disagreements (D-0024))**, **the recent reader's** **share given recent < 0.3 among items the labellers agree are not recent** for **anniversaries, retrospectives, old trials, dated references** is **>= ceiling(P-OLD) - 0.05 (provisional 0.90)**, because **n = 150 gives a Wilson lower bound of 0.90 at an observed 0.95**; it fails when **"Ten years after the crash, what changed" read as current [invented]**.
  Today: not built. Bound: n = 150. Replaced by: M6; 0.90 is old S4's value carried. Derivation: D-0024. Nothing-reader test: fails it (so it is graded).
- **RC-3 - Date cue flips recent** (model, sideways (edit), graded, bar provisional). On **P-FLIPR (n = 150; 150 F headlines with "in 2015" or "ten years ago" added by script; label by construction; labelled by no labeller (labels by construction); 30 pairs spot-checked by hand)**, **the recent reader's** **share of pairs where the dated version falls below 0.3 and the plain version stays at or above it** for **explicit old date** is **>= Jev's flip rate on P-FLIPR - 0.05 (provisional 0.90)**, because **the reader must read the date cue, not the topic**; it fails when **"Court hears fraud case" and "Court hears 2015 fraud case" both read as current [invented]**.
  Today: not built. Bound: n = 150. Replaced by: M5. Derivation: CheckList DIR, D-0024. Nothing-reader test: fails it (so it is graded).
- **RC-4 - Replay unmoved by the reader's gate** (pipeline, right, graded, bar derived). On **E-R (n = 1,000; the saved news ledger, stage-1 collect (world_service2.py:105); labelled by none; Jev's gate is the reference)**, **the recent reader's** **ratio of drift in the saved-ledger replay (events kept under the reader's gate vs Jev's gate) to run-to-run noise** for **the collect stage** is **<= 1.0**, because **only the replay drops on recent; the request and ticker paths use type weights and never drop**; it fails when **a reader that drops 3% extra events moves the replay's ratio above 1 (invented) [invented]**.
  Today: not built. Bound: ratio. Derivation: F-0020. Nothing-reader test: fails it (so it is graded).
- **RC-G1 - Fresh stories wrongly dropped** (model, right, gate, bar provisional). On **R-set (n = 9,997; the testA stories with Jev scores in data/trainset/testA.jsonl (481 have recent < 0.3); labelled by Jev (labels exist))**, **the recent reader's** **Jev-recent stories with reader recent < 0.3, per 1,000 stories** for **recent** is **<= T_drop (from RC-4)**, because **a wrong 'no' deletes the event from the replay with no partial credit**; it fails when **"Court hears 2015 fraud case" (the hearing is now) read as old [invented]**.
  Today: no reader. Bound: n = 9,997. Replaced by: M8; Fable's 10 per 1,000 was a placeholder. Derivation: RC-4. Nothing-reader test: passes it (so it is a gate).
- **RC-G2 - Recent label reliable (alpha)** (data, left, gate, bar derived). On **J (n = 500; seeded random draw from F; labelled by Jev (have), Clef (to run), Opus on disagreements (D-0024))**, **the labellers'** **Krippendorff alpha of recent < 0.3 between Jev and Clef** for **recent** is **>= 0.667 (accept 0.80)**, because **below 0.667 the cut is noise**; it fails when **Jev gives an anniversary feature 0.35 and Clef 0.20 [invented]**.
  Today: not measured. Bound: J. Derivation: Krippendorff 2011. Nothing-reader test: passes it (so it is a gate).
- **RC-G3 - The date the labeller saw equals the date the reader sees** (pipeline, left, gate, bar derived). On **label-calls (n = 19,997; build_trainset.py:103 sets published = today = the story's day for every call; labelled by code read)**, **the labelling script's** **share of labelled F stories where published = today in the prompt** for **recent** is **>= 100%**, because **the reader sees headline plus 250 characters and no date, so 'recent' must come from text cues alone**; it fails when **a labelling run where today is 2026 and the story is from 2018 (all stories would be not recent) [invented]**.
  Today: true in code (line 103); not audited row by row. Bound: exact. Derivation: D-0009, build_trainset.py:103. Nothing-reader test: passes it (so it is a gate).

### 2.4 Scope and focus

Engine use: nothing reads national, local or new. us_focus and foreign_focus set an entry in `classify.read` (`:62`) but the live paths override it with the country answer (`:166`, `:445`). By D-0017 a label that no code reads is not graded. Jev rates in 19,997 labelled stories (>= 0.5): national 0.374, local 0.249, new 0.890, us_focus 0.284, foreign_focus 0.379.

**Element register (step 1)**

| Element | Definition | Read by / how | Cost of a miss | Cost of a false alarm | Alpha (n) | Status |
|---|---|---|---|---|---|---|
| national | national scale of the story | not read | none | none | not measured | informational until OQ-2 |
| local | local scale | not read | none | none | not measured | informational until OQ-2 |
| new | new development | not read | none | none | not measured | informational until OQ-2 |
| us_focus / foreign_focus | mainly about the US / another country | entry in classify.read, overridden on live paths | none today | none today | not measured | dropped from grading; computed from the country answer if ever needed |

**Coverage check (step 4): the six directions**

| Direction | Criteria | Reason if empty |
|---|---|---|
| left (source/data) | SF-G1 |  |
| right (consumer) | SF-G2 |  |
| up (area) | SF-1 | SF-1 is a placeholder (informational) until OQ-2 |
| down (slice) | SF-I1 |  |
| sideways: near-miss / none | - | no label is graded until OQ-2 names the labels the engine reads; the neighbour set is built after that |
| sideways: invariance / flip | - | same reason as SN; invariance and flip sets follow OQ-2 |

Levels present: data, model, pipeline. Source-level rows shared by all areas: X-G4 (outlet mix covers the live feed); data-level: X-G3 (frozen set never trained on); pipeline: X-G1 (speed), X-G2 (regression).

**Criteria (step 7), one atomic sentence each**

- **SF-1 - Labels the engine will read agree with Jev** (model, up, informational, bar open). On **J (n = 500; seeded random draw from F; labelled by Jev (have), Clef (to run), Opus on disagreements (D-0024))**, **the scope reader's** **share where the reader's <LABEL> >= 0.5 equals Jev's** for **each label in <READ_SET-OQ2>** is **>= ceiling(L) - 0.03**, because **D-0017 makes the engine's outputs the target, so a label is graded only if a code line reads it**; it fails when **"For 18 Hours, Cabbie Sat Dead in Front Seat" (Jev local 0.86) read as national [real story, hypothetical failure]**.
  Today: No reader trained. Jev rates (labelled stories): national 0.374, local 0.249, new 0.890, us_focus 0.284, foreign_focus 0.379. Bound: J. Replaced by: OQ-2 (which labels), then M1. Derivation: OQ-2, D-0017.
- **SF-G1 - Read scope labels reliable (alpha)** (data, left, gate, bar derived). On **J (n = 500; seeded random draw from F; labelled by Jev (have), Clef (to run), Opus on disagreements (D-0024))**, **the labellers'** **Krippendorff alpha of each label in <READ_SET-OQ2> between Jev and Clef** for **read labels** is **>= 0.667 (accept 0.80)**, because **below 0.667 the label is noise**; it fails when **Jev local, Sonnet national on a council story [invented]**.
  Today: not measured. Bound: J. Derivation: Krippendorff 2011, F-0049. Nothing-reader test: passes it (so it is a gate).
- **SF-G2 - Every graded scope label has a reader in the engine** (pipeline, right, gate, bar derived). On **code-read (n = 5; s|national, s|local, s|new, x|us_focus, x|foreign_focus searched in classify.py, engine*.py, world_service2.py, intake.py; labelled by code read)**, **the engine code's** **count of <READ_SET-OQ2> labels with no consuming code line** for **read labels** is **<= 0**, because **nothing is graded that no consumer reads**; it fails when **s|local is parsed but no line uses it [real]**.
  Today: national, local, new: no consumer. us_focus and foreign_focus: classify.py:62 sets an entry, but the live paths override it with the country answer (world_service2.py:166, 445). Bound: count. Derivation: skill rule 6, D-0017. Nothing-reader test: passes it (so it is a gate).
- **SF-I1 - Agreement per scope label (report)** (model, down, informational, bar n/a). **SF-I1** (information, no bar): on J (n = 500; seeded random draw from F; labelled by Jev (have), Clef (to run), Opus on disagreements (D-0024)), the scope reader gives agreement with Jev per label for five labels; reported each round, never graded.
  Today: no reader.

### 2.5 Topic

Engine use: one main topic per story. It limits which conditions the engine may infer for the expected-impact readings (`world_service2.py:166-176`, `:435-436`; the `moves:` list per topic in the ontology). Reported readings are not masked. 'other' has no moves list, so it allows nothing. D-0022: finer labels are allowed and rolled up to the 49 before scoring.

**Element register (step 1)**

| Element | Definition | Read by / how | Cost of a miss | Cost of a false alarm | Alpha (n) | Status |
|---|---|---|---|---|---|---|
| each of 49 topics | the story's main subject (ontology `topics:`) | moves list: conditions it may move | high when the wrong topic blocks a condition Jev's topic allows | medium when it allows one Jev's does not | not measured (Jev-Sonnet raw 42/50) | graded (TP-1 to TP-4) |
| other | none of the 49 | no moves | medium | low | not measured | report (TP-I2) |
| finer topics (D-0022) | reader's own finer labels, rolled up | mapped before scoring | n/a | n/a | n/a | gate (TP-G2) |

**Coverage check (step 4): the six directions**

| Direction | Criteria | Reason if empty |
|---|---|---|
| left (source/data) | TP-G1, TP-G2 |  |
| right (consumer) | TP-2, TP-5 |  |
| up (area) | TP-1 |  |
| down (slice) | TP-3, TP-4, TP-I2 |  |
| sideways: near-miss / none | TP-G3, TP-I1 |  |
| sideways: invariance / flip | TP-G4 |  |

Levels present: data, model, pipeline. Source-level rows shared by all areas: X-G4 (outlet mix covers the live feed); data-level: X-G3 (frozen set never trained on); pipeline: X-G1 (speed), X-G2 (regression).

**Criteria (step 7), one atomic sentence each**

- **TP-1 - Topic agrees with Jev** (model, up, graded, bar provisional). On **F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist))**, **the topic reader's** **share of stories whose main topic (after roll-up of finer labels to the 49, D-0022) equals Jev's** for **all stories** is **>= ceiling(TP) - 0.05 (provisional 0.79)**, because **above the ceiling the reader copies Jev's noise; the old 0.85 sat above the only measured ceiling**; it fails when **"Whoever wins the argument over wages growth will likely win the next election" (theguardian): Jev work_labour, reader elections_politics [real]**.
  Today: Ensemble 0.795 (Wilson 0.787 to 0.802) against a provisional 0.79; TF-IDF baseline 0.678; majority topic 0.218. Bound: n = 11,997: half-width 0.007. Replaced by: M1: Jev-vs-Clef topic agreement on J. Stand-in 0.84 = Jev-Sonnet 42/50 (Wilson 0.72 to 0.92, F-0049). Derivation: F-0049, D-0022, D-0024. Nothing-reader test: fails it (so it is graded).
- **TP-2 - Reader's topic blocks a condition Jev's allows** (model, right, graded, bar provisional). On **F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist))**, **the topic reader's** **stories where the reader's topic lacks, in its moves list, at least one condition Jev's topic allows, per 1,000 stories** for **topic -> allowed conditions** is **<= Jev-vs-Clef rate on J + 20 per 1,000**, because **the topic limits which conditions the engine may infer from a story (expected impact path); a reader that answers 'other' (no moves) blocks everything**; it fails when **"Kimberley inquest witness slams cashless welfare card, links program to youth suicides" (abc.net.au): Jev social_welfare_poverty (inequality, food_insecurity, private_debt), reader mental_health_substances (mental_distress) blocks all three [real]**.
  Today: 191.7 per 1,000 stories (2,300 of 11,997; Wilson 18.5% to 19.9%). Of 2,463 wrong-topic stories only 27 have identical moves lists, so a wrong topic is almost never free. Bound: n = 11,997. Replaced by: M1 gives the judge-judge rate; M8 topic-mask run replaces the +20. Derivation: D-0024, world_service2.py:166-176, 435-436. Nothing-reader test: fails it (so it is graded).
- **TP-3 - Per-topic recall floor** (model, down, graded, bar provisional). On **F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist))**, **the topic reader's** **count of topics with at least 30 Jev positives whose recall is below floor(n) = TP-1 bar - 1.96*sqrt(bar(1-bar)/n)** for **each topic** is **<= 3 topics**, because **pooled accuracy hides small topics (accuracy 0.757 but per-topic F1 0.675 for e5tfidf); 4 or more of 46 below their floors by chance has probability 2.8%**; it fails when **family_demographics: recall 0.15 over 55 stories ("Ashley Madison survey reveals the most unfaithful professions" read as civil_rights_discrimination) [real]**.
  Today: 20 of 46 topics below floor (ensemble); lowest: family_demographics 0.15, social_welfare_poverty 0.22, consumer_retail 0.36, labour_disputes 0.40, governance_corruption 0.45. Bound: topic n 30 to 560. Replaced by: inherits TP-1 (M1). Derivation: TP-1, F-0072. Nothing-reader test: fails it (so it is graded).
- **TP-4 - Per-outlet topic floor** (model, down, graded, bar provisional). On **O51 (n = 10,812; the F stories from the 51 outlets with at least 60 stories in F (F-0072); labelled by Jev (labels exist))**, **the topic reader's** **count of outlets whose topic agreement is below floor(n)** for **each outlet with at least 60 stories** is **<= 3 outlets**, because **topic agreement runs 0.63 to 0.86 by outlet**; it fails when **nbcnews.com scores 0.63 over 231 stories [real]**.
  Today: 17 of 51 outlets below floor (e5tfidf scores, F-0072). Bound: outlet n 60 to 405. Replaced by: inherits TP-1 (M1). Derivation: F-0072, TP-1. Nothing-reader test: fails it (so it is graded).
- **TP-5 - Engine output unmoved by the reader's topic** (pipeline, right, graded, bar derived). On **E-P (n = 1,000; random 1,000 of F replayed with the allowed-conditions set from the reader's topic; labelled by none; Jev is the reference)**, **the topic reader's** **ratio of engine output drift (reader's topic mask vs Jev's) to run-to-run noise** for **1,000 F stories** is **<= 1.0**, because **tolerance is drift inside the engine's own noise**; it fails when **a topic confusion that blocks job_security readings moves the ratio above 1 (invented) [invented]**.
  Today: not built. Bound: ratio. Derivation: F-0020. Nothing-reader test: fails it (so it is graded).
- **TP-G1 - Topic labels reliable (alpha)** (data, left, gate, bar derived). On **J (n = 500; seeded random draw from F; labelled by Jev (have), Clef (to run), Opus on disagreements (D-0024))**, **the labellers'** **lowest Krippendorff alpha over the 49 topics between Jev and Clef** for **each topic** is **>= 0.667 (accept 0.80)**, because **below 0.667 the topic is noise**; it fails when **Jev says governance_corruption, Clef elections_politics (the largest confusion in F, 48 stories) [real]**.
  Today: not measured (Jev-Sonnet raw 42/50). Bound: J. Derivation: Krippendorff 2011. Nothing-reader test: passes it (so it is a gate).
- **TP-G2 - Finer topics roll up to the 49** (data, left, gate, bar derived). On **rollup (the reader's own fine label list (not yet written); labelled by the mapping file)**, **the roll-up map's** **share of the reader's finer labels with a pinned mapping to one of the 49** for **fine labels** is **>= 100%**, because **D-0022 allows fine labels only if they map back, and says the mapping must be pinned before it is used**; it fails when **a fine label 'rugby' with no parent [invented]**.
  Today: no mapping written. Bound: exact. Derivation: D-0022. Nothing-reader test: passes it (so it is a gate).
- **TP-G3 - Non-news gets no extra moving topic** (model, sideways (neighbour), gate, bar provisional). On **P-NONNEWS (n = 200; CC-News outside F mined by section and feed, not by reader output; labelled by Jev (hosted; needs the owner's yes for new items), Clef (local), Opus on disagreements (D-0024))**, **the topic reader's** **non-news items given a topic whose moves list holds a condition Jev's topic does not, per 1,000** for **sport results, recipes, listings, shopping** is **<= T_mask (from TP-5)**, because **a recipe read as inflation can move prices in the engine**; it fails when **"Earn your stars (and stripes) with these classic diner recipes for US Independence Day" (irishtimes, Jev culture_leisure) read as consumer_retail (moves prices) [real story, hypothetical failure]**.
  Today: not built. Bound: n = 200. Replaced by: M8; Fable's 20 per 1,000 was a placeholder. Derivation: TP-5. Nothing-reader test: passes it (so it is a gate).
- **TP-G4 - Typos and source prefixes do not change the topic** (model, sideways (edit), gate, bar provisional). On **P-INV (n = 200; 200 F stories with a typo or a 'Reuters -' prefix added by script; label unchanged by construction; labelled by no labeller (labels by construction); 30 items spot-checked by hand)**, **the topic reader's** **share of edited stories keeping their topic** for **all topics** is **>= Jev's rate on the same edits - 0.02 (provisional 0.95)**, because **irrelevant edits must leave the label alone; a reader that always says one topic also passes, hence a gate**; it fails when **adding 'Reuters -' moves a trade story to business_corporate [invented]**.
  Today: not built. Bound: n = 200. Replaced by: M5. Derivation: CheckList INV. Nothing-reader test: passes it (so it is a gate).
- **TP-I1 - Named confusions each round** (model, sideways (neighbour), informational, bar n/a). **TP-I1** (information, no bar): on F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist)), the topic reader gives five largest off-diagonal cells of the F confusion table for topic pairs; reported each round, never graded.
  Today: governance_corruption read as elections_politics 48; terrorism_violence as crime_policing 42; courts_rulings as crime_policing 36; elections_politics as governance_corruption 35; markets_investment as business_corporate 31.
- **TP-I2 - 'Other' is not a dump (report)** (model, down, informational, bar n/a). **TP-I2** (information, no bar): on F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist)), the topic reader gives 'other' rate and recall for other; reported each round, never graded.
  Today: Jev uses 'other' for 0.5% of F (57 stories); the reader for 0.03% (4); recall 2 of 57. Old bar 'other <= 10%' was never close.

### 2.6 Conditions

Engine use: 39 conditions x up/down = 78 keys (the suite trains 52 and scores 48). A reading exists when exactly one direction's mean attribute probability is >= 0.65; both directions = conflict = the dial is dropped; strength = the largest probability; amount = +/-0.10 x strength x type weight (`classify.read`, `sensitivity.py`). Tolerance measured (F-0020). The 16 'key keys' of S-0003 are the keys that matter most (list not pinned in a file).

**Element register (step 1)**

| Element | Definition | Read by / how | Cost of a miss | Cost of a false alarm | Alpha (n) | Status |
|---|---|---|---|---|---|---|
| each condition|direction key | a condition pushed up or down (ontology `conditions:`) | reading at 0.65, strength = probability | high: the reading is lost | medium to high: a false reading moves the world | not measured (overlap Jev-Sonnet 0.41, Jev-Haiku 0.34, F-0049) | graded on key keys (CN-1) |
| conflict (both directions) | one dial fires up and down | dial dropped | medium | medium | n/a | gate (CN-G2) |

**Coverage check (step 4): the six directions**

| Direction | Criteria | Reason if empty |
|---|---|---|
| left (source/data) | CN-G3, CN-G4 |  |
| right (consumer) | CN-4, CN-G1 |  |
| up (area) | CN-1, CN-3, CN-I1 |  |
| down (slice) | CN-G6, CN-I2 |  |
| sideways: near-miss / none | CN-G2, CN-G5 |  |
| sideways: invariance / flip | CN-2 |  |

Levels present: data, model, pipeline. Source-level rows shared by all areas: X-G4 (outlet mix covers the live feed); data-level: X-G3 (frozen set never trained on); pipeline: X-G1 (speed), X-G2 (regression).

**Criteria (step 7), one atomic sentence each**

- **CN-1 - Keys inside engine tolerance** (pipeline, up, graded, bar derived). On **F + P-KEY (n = 11,997; F, plus Jev positives found by any method (kept out of the random statistics) until a key has at least 109 positives; labelled by Jev (labels exist))**, **the condition reader's** **count of graded keys whose (TPR, FPR) at the engine's 0.65 cut against Jev lies inside the F-0020 region (TPR Wilson lower >= 0.95 with FPR Wilson upper <= 0.0025, or TPR lower >= 0.90 with FPR upper <= 0.001)** for **the 16 key keys of S-0003 first, then the rest** is **>= all graded keys**, because **F-0020 measured that the engine stays inside its run-to-run noise at TPR 0.95 with FPR up to 0.0025, or TPR 0.90 with FPR 0.001**; it fails when **"TSX ticks up higher while loonie edges lower on U.S. holiday" (thestar): Jev asset_values|up, reader p 0.64, just under the 0.65 cut; asset_values|up recall is 0.688 at its K6 threshold (k6k8.json) [real]**.
  Today: 0 of 52 keys inside at 0.65 (ensemble, raw probabilities; computed this session); best TPR 0.87 at 12.0 false alarms per 1,000 (asset_values|up). Only 21 of 52 keys have 73 or more F positives, the least with which even a perfect TPR can prove 0.95. Bound: TPR 0.95 needs 73 positives with 0 misses (109 with 1); 0.90 needs 35 (53). Derivation: F-0020, S-0003. Nothing-reader test: fails it (so it is graded).
- **CN-2 - Direction flip** (model, sideways (edit), graded, bar provisional). On **P-FLIPK (n = 320; 16 key keys x 20 pairs made by script from F ("rents rose" / "rents fell"), label by construction; labelled by no labeller (labels by construction); 40 pairs spot-checked by hand)**, **the condition reader's** **share of pairs where the wrong direction falls below 0.65 and the right one rises above it** for **the 16 key keys, up and down** is **>= Jev's flip rate on P-FLIPK - 0.05 (provisional 0.90)**, because **the engine acts on direction and sees only the 0.65 cut (classify.read)**; it fails when **"Rents fall for first time in a decade" still reads housing_cost|up [invented]**.
  Today: not built. Bound: n = 320: half-width 0.03. Replaced by: M5. Derivation: CheckList DIR, F-0020. Nothing-reader test: fails it (so it is graded).
- **CN-3 - Strength is honest** (model, up, graded, bar provisional). On **F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist))**, **the condition reader's** **largest gap between stated probability and observed true share over the bands 0.65-0.8, 0.8-0.9, 0.9-1.0 (a band with fewer than 100 readings counts as failed)** for **all readings at or above 0.65** is **<= 0.10**, because **the probability becomes the reading's strength (amount = 0.10 x strength), so calibration matters from 0.65 up, not at one point**; it fails when **readings stated at 0.9 are true 0.76 of the time (1,495 predictions, k6k8.json) [real]**.
  Today: raw ensemble: bands 0.7 true 0.34, 0.8 true 0.525, 0.9 true 0.76; after isotonic calibration the 0.9 band is 0.80 (F-0068). Bound: top band n = 1,495: half-width 0.022. Replaced by: M8 strength run: perturb strength by +/- d and find where the engine leaves its noise. Derivation: Breck 2017, classify.read. Nothing-reader test: fails it (so it is graded).
- **CN-4 - Engine output unmoved by the reader's readings** (pipeline, right, graded, bar derived). On **E-K (n = 1,000; random 1,000 of F replayed through sensitivity.py with the reader's actual readings instead of synthetic error; labelled by none; Jev is the reference)**, **the condition reader's** **ratio of engine output drift (reader's readings vs Jev's) to run-to-run noise** for **the 16 key keys** is **<= 1.0**, because **F-0020: ratio 1.0 is the line; TPR .8 / FPR .005 fails at 1.7 (clustered 2.3)**; it fails when **a reader at TPR 0.8 and FPR 0.005 gives ratio 1.7 [real]**.
  Today: not built. Bound: ratio. Derivation: F-0020. Nothing-reader test: fails it (so it is graded).
- **CN-G1 - False alarms per key** (model, right, gate, bar derived). On **F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist))**, **the condition reader's** **stories lacking the key where the reader is at or above 0.65, per 1,000 such stories** for **each key** is **<= 2.5 per 1,000 (Wilson upper bound)**, because **F-0020: FPR up to 0.0025 at TPR 0.95**; it fails when **"Tech stocks wobble in U.S.; some investors worry party is ending" (reuters): asset_values|up at p 0.84 (a fall) [real]**.
  Today: 32 of 52 keys at or under 2.5 per 1,000 at the raw 0.65 cut (point values); K6 counts 17 to 19 of 48 at tuned thresholds (F-0068). Bound: 19 of 11,900 -> upper 0.25%. Derivation: F-0020. Nothing-reader test: passes it (so it is a gate).
- **CN-G2 - Both directions fire on one story** (model, sideways (neighbour), gate, bar provisional). On **F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist))**, **the condition reader's** **stories where one dial has both directions at or above 0.65, per 1,000 stories** for **dials with both directions** is **<= Jev's rate (27.8 per 1,000) + 5 (provisional 32.80)**, because **a conflict silently drops the dial from the engine**; it fails when **"prices rose then fell" fires prices|up and prices|down [invented]**.
  Today: reader 18.7 per 1,000 (224 stories; Wilson 1.6% to 2.1%); Jev 27.8 per 1,000 (2.78% of 19,997 labelled stories). Bound: n = 11,997. Replaced by: M8 conflict run replaces the +5. Derivation: classify.read (conflict drops the dial), data/trainset conflicts field. Nothing-reader test: passes it (so it is a gate).
- **CN-G3 - Condition labels reliable (alpha)** (data, left, gate, bar derived). On **J + P-KEY (n = 500; J plus Jev positives for graded keys found by any method, kept out of the random statistics; labelled by Jev (have), Clef (to run), Opus on disagreements (D-0024))**, **the labellers'** **Krippendorff alpha per graded key between Jev and Clef** for **each graded key** is **>= 0.667 (accept 0.80)**, because **overlap Jev-Sonnet 0.41 and Jev-Haiku 0.34 (F-0049) is overlap, not alpha, and says many keys may not be readable**; it fails when **Jev reads a passing mention as housing_cost|up, Clef does not [invented]**.
  Today: not measured (T-0011 not run). Bound: per key. Derivation: Krippendorff 2011, F-0049. Nothing-reader test: passes it (so it is a gate).
- **CN-G4 - Enough positives to prove the tolerance** (data, left, gate, bar derived). On **F + P-KEY (n = 11,997; F, plus Jev positives found by any method (kept out of the random statistics) until a key has at least 109 positives; labelled by Jev (labels exist))**, **the test set's** **Jev positives per graded key** for **each graded key** is **>= 109**, because **73 positives with no miss, or 109 with one, are the least that put the lower bound at 0.95 (35 and 53 for 0.90)**; it fails when **biodiversity_loss|up has 10 positives in F [real]**.
  Today: 21 of 52 keys have 73 or more, 13 have 150 or more, 10 have fewer than 30. Bound: Wilson arithmetic. Derivation: F-0020, Wilson arithmetic. Nothing-reader test: passes it (so it is a gate).
- **CN-G5 - Non-news gets no reading** (model, sideways (neighbour), gate, bar provisional). On **P-NONNEWS (n = 200; CC-News outside F mined by section and feed, not by reader output; labelled by Jev (hosted; needs the owner's yes for new items), Clef (local), Opus on disagreements (D-0024))**, **the condition reader's** **non-news items with any reading, per 1,000** for **sport results, recipes, listings, shopping** is **<= T_none (M8)**, because **F-0020's false-alarm limit is per key, so the any-key rate for non-news has to be set from the run**; it fails when **"10 best air fryers under $100" reads prices|up [invented]**.
  Today: not built. Bound: n = 200. Replaced by: M8; Fable's 20 per 1,000 (P7) was a placeholder. Derivation: F-0020. Nothing-reader test: passes it (so it is a gate).
- **CN-G6 - Per-outlet false-alarm rate** (model, down, gate, bar derived). On **O51 (n = 10,812; the F stories from the 51 outlets with at least 60 stories in F (F-0072); labelled by Jev (labels exist))**, **the condition reader's** **count of outlets whose micro false-alarm rate over all keys exceeds 2.5 per 1,000 key-story pairs** for **each outlet with at least 60 stories** is **<= 3 outlets**, because **the 2.5 per 1,000 limit applies to any slice the engine reads**; it fails when **in.reuters.com: 8.0 per 1,000 over 87 stories [real]**.
  Today: 43 of 44 testA outlets above 2.5 at the raw 0.65 cut (overall micro rate 4.5 per 1,000). Bound: outlet n 60 to 400. Derivation: F-0020, F-0072. Nothing-reader test: passes it (so it is a gate).
- **CN-I1 - Mean AP per key (progress)** (model, up, informational, bar n/a). **CN-I1** (information, no bar): on F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist)), the condition reader gives average precision for all keys; reported each round, never graded.
  Today: ensemble mean AP 0.461 over 52 keys (models_r2), 0.482 over 48 (F-0058); 4 keys at or above 0.70.
- **CN-I2 - Per-item proof each round** (data, down, informational, bar n/a). **CN-I2** (information, no bar): on F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist)), a reviewer gives false alarms given a cause (input lacks it / codebook / model) for 20 false alarms from F; reported each round, never graded.
  Today: not built.

### 2.7 Cross-area gates

- **X-G1 - Speed** (pipeline, gate, bar derived). On **F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist))**, **all readers together's** **median ms per story on CPU** for **all areas** is **< 100 ms**, because **the CPU reader must be fast enough to replace Clef at 6 s a story**; it fails when **a reader set that takes 140 ms per story [invented]**. Today: country script 10.8 ms (F-0050), e5 fine-tuned 15.9 ms; the set is not timed together. Derivation: D-0007.
- **X-G2 - Regression** (pipeline, gate, bar derived). On **F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist))**, **all readers'** **graded criteria whose value fell below the bar by more than its 95% Wilson interval since the last accepted round** for **every accepted graded criterion** is **<= 0**, because **a rule applied to the other rows, not a row of its own**; it fails when **an accepted topic floor that drops two topics after a retrain [invented]**. Today: no rounds counted yet. Derivation: Breck 2017, scorecard rule.
- **X-G3 - Frozen set never trained on** (data, gate, bar derived). On **F (n = 11,997; frozen test set, night1 held-out 2,000 + testA 9,997, never trained on, 125 outlets (F-0072); labelled by Jev (labels exist))**, **the data pipeline's** **count of F story ids or normalised headlines found in any training file** for **F** is **<= 0**, because **a leaked test story measures memory**; it fails when **a testA story also present in night1 [invented]**. Today: not measured here (training in progress, files left alone). Derivation: F-0072, Datasheets (Gebru 2021).
- **X-G4 - Outlet mix covers the live feed** (source, gate, bar provisional). On **queue-vs-F (n = 7,702; live queue (7,702 items, 63 feeds, F-0072) against F; labelled by none)**, **the pool's** **count of outlets or feeds holding at least 1% of the live queue with fewer than 60 stories in F** for **outlets and feeds** is **<= 0**, because **60 stories is where a per-outlet floor can first be tested**; it fails when **a feed with 400 live items and 12 stories in F [invented]**. Today: not counted (feed names differ from F outlet names). Derivation: F-0072, CO-2 floor formula.

## 3. Bars: measured numbers, and what fixes the rest

Only measured baselines, ceilings and F-0020 are used. Where a ceiling is unmeasured the bar reads 'ceiling - x (provisional N)' and N is the best stand-in or a carried value (marked).

| Quantity | Value | Source |
|---|---|---|
| Engine tolerance, conditions | pass at TPR 0.95 with FPR up to 0.0025, or TPR 0.90 with FPR 0.001; TPR 0.8 / FPR 0.005 fails at 1.7x (2.3x clustered) | F-0020 |
| Jev-Sonnet agreement, topic | 42 of 50 = 0.84 (Wilson 0.715 to 0.917) | F-0049 |
| Jev-Sonnet agreement, country | 46 of 50 = 0.92 (Wilson 0.812 to 0.968) | F-0049 |
| Jev-Sonnet agreement, type/scope/focus | 0.71 per label over 10 mixed labels (144 of 500 disagree); below the always-fact baseline, so unusable as a type ceiling | F-0049 |
| Condition overlap | Jev-Sonnet 0.41, Jev-Haiku 0.34, Sonnet-Haiku 0.70 (overlap, not alpha) | F-0049 |
| Jev-Clef agreement, any area | not measured (task M1) | D-0024 |
| Topic baselines vs Jev | majority topic 0.218; TF-IDF 0.678; e5 0.718; e5+TF-IDF 0.765; ensemble 0.795 (Wilson 0.787 to 0.802) | `data/scorecard/models_r2.json`; ensemble computed this session on F |
| Country baselines vs Jev (16-class label set) | majority (usa) 0.287; ensemble 0.892; the 'other' bucket is 14.6% of F | computed this session; `models_r2.json` |
| Type class agreement vs Jev, F | always-fact 0.798 (0.791 to 0.805); ensemble 0.823 (0.816 to 0.830) | computed this session |
| Type errors, F | fact -> non-fact 1,569 (130.8 per 1,000 stories); opinion -> fact 102 (8.5 per 1,000) | computed this session |
| Recent, Jev | 4.8% of 19,997 labelled stories below 0.3; always-recent agreement 0.952 | `data/trainset/*.jsonl`, computed this session |
| Topic mask, F | 2,300 stories (191.7 per 1,000) where the reader's topic blocks a condition Jev's allows; 27 of 2,463 wrong-topic stories have identical moves lists | computed this session |
| Conditions at the 0.65 cut, F | 0 of 52 keys inside the F-0020 region; best TPR 0.87; 32 of 52 keys at or under 2.5 false alarms per 1,000; 21 of 52 keys have 73 or more positives | computed this session |
| Conflicts | reader 18.7 per 1,000 stories; Jev 27.8 per 1,000 | computed this session; `data/trainset` conflicts field |
| Per-outlet spread (F-0072) | topic 0.63 to 0.86, country 0.61 to 0.93, type hamming 0.79 to 0.93, conditions micro AP 0.37 to 0.70 | F-0072 |
| Country reviewer ceiling | not computable: `review-a.jsonl` covers stories 0 to 149 and `review-b.jsonl` stories 150 to 299, so no story was labelled by both | checked this session (Fable's review said they were 'never compared') |

**Bars by status**

- **Derived (a measurement, a stated definition or a convention, with its id): 23.** CO-6; CO-G1; CO-G2; CO-G3; TY-7; TY-G2; RC-4; RC-G2; RC-G3; SF-G1; SF-G2; TP-5; TP-G1; TP-G2; CN-1; CN-4; CN-G1; CN-G3; CN-G4; CN-G6; X-G1; X-G2; X-G3
- **Provisional (the measurement that replaces the placeholder is named): 31.** CO-1 (M1); CO-2 (M1, M4); CO-3 (M6); CO-5 (M5); CO-G4 (M8); CO-G5 (M8); CO-G6 (M6); CO-G7 (M8); TY-1 (M1); TY-2 (M1, M8); TY-3 (M5); TY-4 (M6); TY-5 (M1); TY-6 (M1); TY-G1 (M0); TY-G3 (M1, M8); RC-1 (M1); RC-2 (M6); RC-3 (M5); RC-G1 (M8); TP-1 (M1); TP-2 (M1, M8); TP-3 (M1); TP-4 (M1); TP-G3 (M8); TP-G4 (M5); CN-2 (M5); CN-3 (M8); CN-G2 (M8); CN-G5 (M8); X-G4 (M8)
- **Open (owner question): 2.** CO-4 (OQ-1, M6); SF-1 (OQ-2, M1)

## 4. Mapping: the old 50 rows

| Old | Old name | Decision | Rev 3 | Reason |
|---|---|---|---|---|
| C1 | Named countries found (recall >= 0.97) | change | CO-1 | unit becomes the engine's entry country vs Jev; the 0.97 had no reason |
| C2 | No false country (precision >= 0.97) | change | CO-G4 | error cap moved to a gate, counted per 1,000 stories, bar from the entry tolerance run |
| C3 | Every one of the 100 when named | drop | CO-I1 | 2,000 labelled stories for a screen no bar can be derived for; per-region report instead |
| C4 | Name, demonym, city, region | drop | CO-I1 | demonym 0.978 and city 0.943 already pass; strata reported inside CO-1 |
| C5 | Look-alikes never swapped (0 of 30) | change | CO-3, CO-G5 | size raised to 420; recall row graded, swap count gated; 0 of 30 allowed up to 11% |
| C6 | Ambiguous words go to review | change | CO-G6 | the checker has no review queue; measured as no false country, 200 items |
| C7 | Fallback matches the outlet table | drop | CO-G1 | true by construction; table coverage kept as a gate |
| C8 | Off-list places never forced | change | CO-G7 | D-0022 gave irl/nzl/sgp/hkg their own codes; set to 100 items |
| C9 | Source table complete | change | CO-G1 | resolved (home-country default); stays a gate |
| C10 | Speed < 20 ms | change | X-G1 | a requirement across all areas (100 ms, D-0007) |
| C11 | Regression | change | X-G2 | a rule applied to other rows |
| T1 | Codebook agreement | change | TY-G2 | gate with Krippendorff cut-offs and rarest-label sizing |
| T2 | Per-type AP | change | TY-1, TY-I1 | engine unit is the weight class at 0.5, not AP; AP kept as progress |
| T3 | Opinion from URL or feed | drop | - | measures a URL rule, not the reader |
| T4 | Announced vs happened on plan words | drop | - | the engine treats both as fact, so the confusion costs nothing |
| T5 | Forecast vs report of a forecast | change | TY-4 | the largest measured error (fact read as forecast); near-miss set of 400 |
| T6 | Flip test (drops by half) | change | TY-3 | crossing 0.5 is what the engine sees |
| T7 | False alarms on non-news | drop | - | undefined under the codebook; 'unclear' is the none outcome (covered by TY-1) |
| T8 | Calibration at 0.9 | drop | - | the cut is 0.5; TY-1 covers it |
| T9 | Headline-only cases | change | TY-5 | F has no headline-only stories, so the slice is built by removing descriptions |
| T10 | Regression | change | X-G2 | rule |
| S1 | Codebook agreement | change | SF-G1, RC-G2 | gate, for the labels that stay |
| S2 | Each label AP >= 0.85 | change | RC-1, SF-1 | recent graded in the engine's unit; national/local/new informational until OQ-2 |
| S3 | US/foreign focus consistent with country rule | drop | SF-G2 | consistent by construction and on an overridden path |
| S4 | Old events not recent | change | RC-2 | kept, n = 150, bar from ceiling |
| S5 | Local places read as local | change | SF-1 | informational until OQ-2 |
| S6 | National markers read as national | change | SF-1 | informational until OQ-2 |
| S7 | Calibration | drop | - | no consumer reads a scope probability |
| S8 | Regression | change | X-G2 | rule |
| S9 | No scope for non-news | drop | TP-G3, CN-G5 | no scope is read; non-news covered by topic and condition gates |
| P1 | Codebook agreement | change | TP-G1 | gate, rare topics enriched |
| P2 | Overall accuracy >= 0.85 | change | TP-1 | bar from ceiling - 0.05; 0.85 sat above the only measured ceiling |
| P3 | Every topic recall >= 0.70 (keyword-mined) | change | TP-3 | scored on F, not mined; floor from sampling noise |
| P4 | Confusable pairs | change | TP-2, TP-I1 | cost-aware (moves lists) and named from the confusion table |
| P5 | 'Other' not a dump | drop | TP-I2 | Jev uses 'other' for 0.5%; reported |
| P6 | Section hint agrees with text | drop | - | measures feed metadata, not the reader |
| P7 | Non-news not given an economic topic | change | TP-G3 | gate, moves-aware |
| P8 | Calibration | drop | - | the engine takes one topic, not its probability |
| P9 | Top-2 contains the topic | drop | - | not consumed |
| P10 | Regression | change | X-G2 | rule |
| K1 | Codebook agreement per key | change | CN-G3 | gate; juror overlap is not alpha |
| K2 | Per-key AP >= 0.70 | change | CN-1, CN-I1 | AP has no known relation to F-0020; kept as progress |
| K3 | Enough positives (30) | change | CN-G4 | raised to 109, the number a 0.95 TPR claim needs |
| K4 | Direction never swapped | change | CN-2 | crossing 0.65, 320 pairs |
| K5 | Passing mention does not count | drop | CN-G1 | a passing mention is a false alarm already counted there |
| K6 | False alarms <= 2.5 per 1,000 | change | CN-G1, CN-1 | kept and derived (F-0020); now a gate because a silent reader passes it, and half of CN-1 |
| K7 | Engine tolerance | change | CN-4, CN-1 | promoted to the main graded rows |
| K8 | Calibration at 0.9 | change | CN-3 | bands from 0.65, with a minimum count |
| K9 | Per-item proof | change | CN-I2 | process, not graded: a silent reader has no false alarms to explain |
| K10 | Regression | change | X-G2 | rule |

Of 50: keep 0, change 35, drop 15. None is kept unchanged: even K6 changed kind (gate) and every bar now carries a derivation id or is marked provisional.

## 5. Measurement plan, in the order that unlocks most bars first

Rates used: local Clef about 64 stories per minute (D-0024, F-0047), so 500 stories take about 8 minutes; hosted Jev about $0.5 per 1,000 stories (GO.md figure quoted in Fable's review, not re-checked); Opus about $10 to $25 for 500 short calls (Fable's estimate, not confirmed). Nothing below runs unattended over 1 hour. A training round is running now: Clef runs wait for it, and hosted calls and the code change in M8 wait for the owner's yes.

| # | Measurement | Size | Labeller | Time | Cost | Unlocks |
|---|---|---|---|---|---|---|
| M0 | Pin the 16 key-key list from S-0003; count the live queue's description lengths and outlet shares | - | none | 30 min | none | TY-G1, X-G4, CN-1 scope |
| M1 | Clef labels on J; Jev-Clef agreement per area (ceilings); Jev test-retest on J | 500 | Clef local; Jev re-ask | about 10 min Clef + 5 min; Jev about $0.25 | about $0.25 | CO-1, CO-2, CO-G2, TY-1, TY-2, TY-5, TY-6, TY-G2, TY-G3, TP-1, TP-2, TP-3, TP-4, TP-G1, RC-1, RC-G2, CN-G3 (partial) = 17 bars |
| M2 | Opus tie-break on the J disagreements (about 250 items: topic, type, country, recent) | about 250 | Opus | 1 hour | $5 to $12 (Fable's rate) | makes J the gold set for M1 |
| M3 | Clef on the 16 key keys' positives plus 1,000 negatives; Jev-Clef alpha per key | about 3,400 | Clef local | about 53 min, run in two chunks | none | CN-G3, CN-G4, CN-1 (proof) |
| M4 | Relabel F stories from irl/nzl/sgp/hkg outlets with the extended country list | about 1,000 | Jev (hosted) | 20 min | about $0.5 | CO-2, CO-G3, CO-1 |
| M5 | Script-made pairs and edits: P-FLIPC 150, P-FLIPT 150, P-FLIPR 150, P-FLIPK 320, P-INV 200; Jev on all 970 for its own flip rate | 970 | none (labels by construction); Jev/Clef for the reference rate | 3 to 4 hours build, 15 min Clef | about $0.5 | CO-5, TY-3, RC-3, CN-2, TP-G4 |
| M6 | Probe sets that need labels: P-LA 420, P-AMB 200, P-OUT 100, P-NEAR-T 400, P-HEAD 400, P-OLD 150, P-NONNEWS 200 (P-MULTI 300 after OQ-1) | 1,870 (+300) | Jev + Clef; Opus on disagreements | about 30 min Clef; 1 day of mining and checks | about $1 + Opus $3 to $6 | CO-3, CO-G5, CO-G6, CO-G7, CO-4, TY-4, TY-5, RC-2, TP-G3, CN-G5 |
| M7 | Alpha with enrichment for rare labels (rare topics, forecast/opinion, not-recent, rare keys) | about 1,500 | Jev + Clef + Opus (human raters only if the owner wants them) | half a day | about $5 | all six alpha gates |
| M8 | Tolerance runs: four new modes of `sensitivity.py` (entry, type class, recent drop, topic mask) plus a strength run and a conflict run, CPU only; one Step-1-sized run each, chunked under 1 hour | 1,000 stories each | none | about one day in total | none (CPU) | CO-6, TY-7, RC-4, TP-5, CN-4 (5 graded rows) and replaces the placeholders in CO-G4, CO-G5, CO-G7, TY-2, TY-G3, TP-2, TP-G3, RC-G1, CN-G2, CN-G5, CN-3, X-G4 (12 bars) |

Order by bars unlocked: M1 (17) with M2, then M8 (17 including replacements), M6 (10), M5 (5), M3 (3), M4 (3), M7 (6 alpha gates), with M0 first because it is free. M8 is placed after M1 because its replacements need the judge-judge rates M1 produces.

**Approvals this plan needs (not decisions, just yes/no):** hosted Jev on new items with article text (M4, M5, M6, M7); Opus spend (M2, M6, M7); a change to a probe script `sensitivity.py`, not the engine (M8); Clef GPU time once the training round ends.

## 6. Open owner questions

- **OQ-1, the multi-country rule (CO-4).** Today the engine takes one entry country and nothing says which of several named countries wins. Candidate rules to choose from: the first named in the headline; the country the verb acts on; the most-mentioned; or 'world' whenever two or more are named. Until a rule exists, CO-4 cannot be measured and its ceiling cannot be set.
- **OQ-2, which scope labels the engine reads (SF-1, SF-G1, SF-G2).** Nothing reads national, local or new, and us/foreign focus is overridden by the country answer. Either name the labels the engine will read (they then get a consumer-based bar) or confirm they stay informational.

## 7. Skill section 6 checklist, run on this set

| # | Item | Result | Detail |
|---|---|---|---|
| 1 | Every row has all template fields, one number, one failing example | FAIL | 9 informational rows (CO-I1, TY-I1, TY-I2, SF-1, SF-I1, TP-I1, TP-I2, CN-I1, CN-I2) have no bar and no example by design; CO-4 and SF-1 are written with placeholders (OQ-1, OQ-2). Among graded and gate rows, complete except for these placeholder bars: none missing. 26 of 55 failing examples are invented and marked (CO-5, CO-6, CO-G1, CO-G5, TY-3, TY-7, TY-G1, TY-G2, RC-2, RC-3, RC-4, RC-G1, RC-G2, RC-G3, SF-G1, TP-5, TP-G2, TP-G4, CN-2, CN-G2, CN-G3, CN-G5, X-G1, X-G2, X-G3, X-G4); 6 are real stories with a hypothetical failure. Suggested reading of the item: 'every graded or gate row'. |
| 2 | Every bar has a derivation id; round numbers marked provisional | PASS with note | 31 provisional bars each name the measurement that replaces them; carried values (0.90, 0.95, 0.97, +5, +10, +20, 0.05 slice gap) are my placeholders or Fable's and are labelled as such. |
| 3 | Every bar is in the consumer's unit; no AP where the consumer cuts at a threshold | PASS | AP survives only in informational rows (TY-I1, CN-I1). |
| 4 | Each area has rows at all four levels and each direction has a criterion or a written reason | FAIL (scope) | Scope has no graded model row and no neighbour or edit rows until OQ-2; recent's D direction has a written reason. The source level is carried by shared X-G4 for recent, scope, topic and conditions, not by an area-specific row. |
| 5 | Each element has a slice floor, a flip or invariance test, a false-alarm rate, a none case | FAIL | Per element (not per area): no per-country floor (CO-I1 only, because F labels 16 country classes); no flip or invariance for the 62 non-key condition keys or for 47 of 49 topics (only the 16 key keys have CN-2; TP-G4 is area-wide); the story-type area has no none case (written reason: every story gets a class, 'unclear' is the none outcome). |
| 6 | Probe set sizes support the claim (Wilson bound printed); no '0 swaps' on n < 100 | FAIL for CN-1 on 31 of 52 keys; PASS elsewhere | 31 keys have fewer than 73 positives in F, too few to prove TPR 0.95 even with no miss; they need enrichment (M3/M7) or stay unscored. Alpha samples for rare labels are not yet sized exactly (M7). Look-alike, flip and near-miss sets were sized by the formula in the appendix. |
| 7 | No row passes for a reader that reads nothing; gates outside the grade | PASS with note | All graded rows were checked by reasoning: a silent reader (world / unclear / no readings) fails CO-1, CO-2, CO-3, CO-5, TY-1 to TY-6, RC-1 to RC-3, TP-1 to TP-4, CN-1 to CN-3. The five tolerance rows (CO-6, TY-7, RC-4, TP-5, CN-4) cannot be confirmed until M8 runs; a silent reader deletes every condition reading, so CN-4 should fail it, the others are unproven. |
| 8 | Reference labels: labeller named, agreement measured, not made from text the reader does not see | FAIL | Labellers are named, and the labelling input equals the reader input (`label_input` equals `input` for all 9,997 testA rows; the prompt date equals the story day, `build_trainset.py:103`). Agreement is not measured for any area: all six alpha gates wait on M1/M3/M7. |
| 9 | Nothing graded that no consumer reads | PASS | Scope labels are informational until OQ-2; us/foreign focus, T3, T4, P9, S-rows with no consumer are dropped. The recent rows are graded for the saved-ledger replay only, which is a real consumer. |
| 10 | Held by an MM3 verdict (local and hosted), splits reported, before the bar is used | NOT DONE | This is a proposal; no MM3 run was made for it. Run `tools/mm3local` and `tools/mm3hosted` on the document (hosted sees only this write-up, not article text) before any bar moves, as the skill and the Fable review require. |

Items failing or not done: 6 of 10 (1, 4, 5, 6, 8, 10). The pooled graded-row count is 26; the lowest-area grade would be reported by the scorecard once these rows are loaded.

## 8. What differs from the Fable set, and facts that came out of reading the data

- Error caps are gates, not graded rows, because a silent reader passes them (method step 8). Fable's K-b, T-b, T-c, C-b were graded; T-c was kept graded here as TY-2, redefined as 'fact kept at full weight' so a silent reader fails it.
- Pooled bars are measured on F (n = 11,997, bound within 0.007) and ceilings on J, not both on J: with J's n = 500 the bound is 0.027 wide, which would have forced the bar above the ceiling.
- The country ceiling cannot come from the two reviewer files: `review-a` and `review-b` label disjoint stories (0 to 149 and 150 to 299).
- 'Recent' drops stories only in the saved-ledger replay; the live request and ticker paths use type weights and never drop.
- F has no story with a description under 60 characters, so Fable's T-e ('J stories with a short description') has no items; TY-5 builds the slice instead.
- Jev's country list lacked Ireland, New Zealand and Singapore when F was labelled, so the per-outlet country floor cannot be scored for 5 of 51 outlets until M4.
- A wrong topic is almost never harmless: only 27 of 2,463 wrong-topic stories share a moves list with Jev's topic, so the 'same moves list costs nothing' relief is small.
- The type weight class is barely above its trivial baseline today (0.823 vs always-fact 0.798) while fact -> forecast is 1,040 of 9,571 Jev-fact stories; the Jev-Sonnet 0.71 'ceiling' is below the baseline and cannot be used.
- TPR 0.95 can be proven (Wilson lower bound) on only 21 of 52 keys with the positives F holds.
- F-0049's Jev-Sonnet figures are n = 50, so their Wilson intervals (topic 0.72 to 0.92, country 0.81 to 0.97) are wider than the margins used in the bars; every 'ceiling - x' bar here is therefore provisional.

## Appendix: reproduce the computed numbers

Run with `/workspace/kev/.venv/bin/python` (read-only on `data/`). The `Y`/`P` arrays are `data/suite_r2/ensemble/<area>.npz`; rows 2000 onward align with `data/trainset/testA.jsonl` (checked: type labels match on all 9,997 rows).

```python
import numpy as np, math, yaml
D='/workspace/data/suite_r2/ensemble/'
def wil(k,n,z=1.96):
    p=k/n; d=1+z*z/n; c=p+z*z/(2*n); h=z*math.sqrt(max(p*(1-p)/n+z*z/(4*n*n),0)); return (c-h)/d,(c+h)/d
def cls(h,a,o,f):  # classify.type_weight classes at 0.5
    if (h>=.5 or a>=.5) and o<.5 and f<.5: return 'fact'
    return 'forecast' if f>=.5 else 'opinion' if o>=.5 else 'unclear'
z=np.load(D+'type.npz',allow_pickle=True); P,Y=z['P'],z['Y']
rc=[cls(*p) for p in P]; jc=[cls(*y) for y in Y]
agree=sum(a==b for a,b in zip(rc,jc)); print(agree/len(P), wil(agree,len(P)))          # 0.823
print(sum(b=='fact' for b in jc)/len(P))                                                # always-fact 0.798
z=np.load(D+'topic.npz',allow_pickle=True); P,Y,K=z['P'],z['Y'],[str(k) for k in z['keys']]
mv={k:set(v['moves']) for k,v in yaml.safe_load(open('/workspace/exports/world-engine-ontology.yaml'))['topics'].items()}
blocked=sum(1 for a,b in zip(Y.argmax(1),P.argmax(1)) if mv.get(K[a],set())-mv.get(K[b],set()))  # 2300
z=np.load(D+'conditions.npz',allow_pickle=True); P,Y,K=z['P'],z['Y'],[str(k) for k in z['keys']]
Pb,Yb=P>=.65,Y>=.5; pos=Yb.sum(0); tpr=(Pb&Yb).sum(0)/np.maximum(pos,1); fpr=(Pb&~Yb).sum(0)/(len(P)-pos)
inside=[k for i,k in enumerate(K) if (tpr[i]>=.95 and fpr[i]<=.0025) or (tpr[i]>=.90 and fpr[i]<=.001)]   # []
def nreq(ceil,bar):  # smallest n where a reader at the ceiling has Wilson lower >= bar
    n=20
    while wil(round(ceil*n),n)[0]<bar: n+=1
    return n
print(nreq(.92,.89), nreq(.95,.90))   # 393 (-> P-LA 420), 127 (-> 150 pairs)
```

Not in the ledger: these are session computations. If the owner accepts the direction, record them as facts (`ledger add fact`) with this appendix as the command.

