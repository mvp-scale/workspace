# So what v2: hooks, register, one anchor figure (design, 2026-10-06)

**What this is.** A redesign of the so-what sentence so that any three statements sound different, the strong stories get a strong lead, small stories say they are small, forecasts say what would happen if they came true, and a statement carries at most one number, only when that number matters. It keeps every v1 rule about facts (`so-what-ontology.md`: no invented facts, hedge by certainty, our vocabulary only) and changes how the sentence is put together.

**What it is measured against.** The baseline is `sowhat-diversity.md` (v1 composer, 120 new stories, world focus). Every "measured" figure below comes from a reference implementation of these rules (a scratchpad Python script, not repo code) run on the same 120 engine responses, with two backend fields estimated (the if-true numbers by linear scaling, the place tier by the Size formula with regions standing in for reach; section 14). They are design evidence, not a test of the shipped composer; the harness will re-measure the real one against the targets in section 13.

| | v1 baseline (world, n=119) | v2 measured (world, n=120) |
|---|---|---|
| top three-word opener share | 13.5% ("An opinion piece:") | 3.3% |
| distinct three-word openers per 100 stories | 38 | 68 |
| stories in a quiet form, excluding true no-impact | 47% | 37% |
| random triples sharing any five-word run | 37.5% | 7.0% |
| same-frame triples sharing any five-word run | 60.3% | 13.9% |
| statements with a number | 0 | 17 (14%), every one passing the significance test |
| digits not traceable to the anchor | n/a | 0 |
| composer nulls | 1 (s106, frame id `plain`) | 0 |
| outputs with a stock tail ("Elsewhere, barely a ripple", "A tiny shift that reaches", "Fades slowly", "no decision moves enough to matter") | 17% to 41% by phrase | 0 |

At all three foci (360 outputs: world, hardest-hit country or audience, a second audience) the triple figures are 8.4% (random) and 19.3% (same frame), against 38.1% and 62.9% for v1.

Files (all new; the v1 files are untouched):
- `probes/persona/rules_v2/sowhat2_frames.csv` (11 rows: the 10 frames plus `plain`)
- `probes/persona/rules_v2/sowhat2_hooks.csv` (86 hook rows in 9 families; v2.1 added WL11 to WL13, v2.2 IF06 to IF09)
- `probes/persona/rules_v2/sowhat2_templates.csv` (109 rows: 46 bodies, 57 quiet forms, 6 UNRESOLVED_PLACE forms; v2.1 added B14, B15, B36 to B38, QF12 to QF14, v2.2 B16 to B18 and UP01 to UP06)
- `probes/persona/rules_v2/sowhat2_lexicon.csv` (499 phrasing rows, v2.1 added 12 arc wordings, v2.2 added 3 l2_who "alone" rows, 16 hook_open rows and 24 trace rows (the hover words); v1 `sowhat_lexicon.csv` is still read for conditions, places, audiences and the WHO ratio bands)
- `spec/so-what-v2-contract.md` (what the backend adds, what the composer takes and returns)
- `spec/sowhat-golden-v2.json` and `.md` (33 cases, the composer's unit tests)

---

## 1. Terms

- **Points**: percentage points of likelihood against a control run with no event. +3 points on "cut spending" means that, out of every 100 people, about 3 more cut spending than in the run without the story. This is why the anchor figure is worded "out of every 100 people".
- **Peak**: the largest of Now, Next and Later for one decision at one row (`impact.places[row][decision]`).
- **Focus**: the row picked in the "So what for" dropdown (world, country, region, audience). **Response row**: the focus, except a local story at world focus, where it is the entry country (v1 rule).
- **Hook**: the short lead of the headline, the part before the first colon or comma that the body hangs on. A hook comes from a **family** (what kind of lead it is), and each family has several **phrasings**.
- **Body**: the rest of the headline, from `sowhat2_templates.csv`. A body fits a hook by its **join** (how the hook ends).
- **Register**: how loud the words are, from the effect's size at the place: **stark**, **plain** or **hushed** (section 4).
- **If-true numbers**: for a story the engine counts at reduced weight (forecast, opinion, unclear, and announced stories counted under 1.0), the same run with the story counted in full (section 5).
- **Anchor**: the one number a statement may carry (section 8).
- **Seed**: an integer that fixes every wording choice for a story (section 3).

## 2. How a statement is built

One pass, in this order. Every step is a rule on numbers the response already has, or on the new backend fields in the contract.

1. **Certainty** from `story.certainty` (v1 rule, unchanged). Call a story **hedged** when it is forecast, opinion or unclear, or announced with `identify.weight < 1` (key `announced_w`). Modal: forecast `would`, opinion `could`, unclear `may`, announced `will`, pending none.
2. **Numbers used**: the if-true places for a hedged story with weight under 1, otherwise `impact.places`.
3. **Local test** on the numbers used (v1 definition: entry is a country, world max |peak| < 0.25, entry max >= 0.25). Response row as in section 1.
4. **Themes** at the response row (v1 rules: at most two, theme verb when two members agree). No theme reaches 0.25 points: go to the **quiet branch** (section 9).
5. **WHO** candidates and lead test (v1 rules: local leads; otherwise a sub-row at x2, many times or opposite with salience >= ln 2; a country only when it is twice the runner-up; never a country when the entry is world or unresolved). When a WHO row leads at world focus and the story is not local, the response row becomes that row (v1).
6. **Frame and guards.** Start from `story.frame.id` (`plain` now has a row). It fails when it breaks the v1 sense rule (spend + buy_new + subscribe + travel) **or** when a shown theme is in the frame's `bars_themes` (for example scare bars `protection-`: no "ease off on precautions" under a scare). On failure use the runner-up if it passes both, else `plain`. Unresolved place: `plain`. **Fit**: frame words (`{frame}`, `{frame_vp}`) may be used only when theme 1 with its sign is in the frame's `fits_themes` (`plain` never fits). **Valence** of the story: the frame's `valence`, or for frames marked `any`, the response sense (down = bad, up = good, flat = any).
7. **Register** (section 4).
8. **Contrast partner** (section 6, CONTRAST), **stake**, **turn**, **arc** (v1 arc kinds).
9. **Anchor** (section 8).
10. **Family order** (section 6): the first family in the order with at least one eligible hook leads.
11. **Hook** pick, then **body** pick, then **slot fills** (verbs, degree words, subject, anchor wording), each by the seed (section 3).
12. **Budget**: headline at most 22 words, shrink steps in a fixed order (section 11).
13. **Line 2**: only when it adds the anchor, a contrast or an arc the headline lacks (section 10).
14. **Feed rule** (section 12, browser only).

## 3. The seed and how choices are made

- `seed` is a composer input. Default: `djb2(story text)` (the v1 hash: h = 5381; h = ((h x 33) xor charCode) as an unsigned 32-bit integer), written as a decimal string. The backend may send `story.seed` (contract) so the page and tests agree even if the displayed text differs.
- Every choice is a **slot**. `pick(slot, candidates) = candidates[djb2(seed + "|" + slot) mod len(candidates)]`. Slots are independent, so changing one table never reshuffles the others.
- Candidate order: hooks and templates sorted by `id` (plain string order); a hook row with `{Hedge}` or `{hedge_tail}` first **expands** into one candidate per eligible lexicon row (in lexicon file order, ids `IF01.0`, `IF01.1`, ...), so each hedge phrasing has the same chance as any other hook. Lexicon candidates in file order, after the filters for that slot.
- Slot names (the golden file logs index and count for each): `hook`, `body`, `there`, `vp`, `verb:<decision>:<sign>`, `theme:<theme>:<sign>`, `deg:<theme-or-decision>:<small|large>:<deg|degp>` (one per theme, so two themes never repeat the same degree word by construction), `anchor`, `anchor_l2`, `soft_tail`, `quiet`, `l2_arc`, `l2_contrast`, `l2_who`, `l2_pending`; the feed rule uses `hook#2`.
- The same story with the same seed always reads the same, at every focus. Changing the focus changes the numbers, so it may change the family, but a choice made under the same slot and the same candidate list stays the same.

## 4. Register: stark, plain, hushed

The classifier's frame says **what kind** of effect it is. The register says **how loud** to say it. It comes from the Size tier at the place the sentence speaks for, not from the world:

| Place the statement speaks for | Tier used |
|---|---|
| world focus, story not local | `impact.significance.tier` (for a hedged story: the if-true tier) |
| world focus, local story | the entry country's tier, `impact.significance_rows[entry].tier` |
| any other focus | that row's tier, `impact.significance_rows[row].tier` |

Tier to register: Negligible = **hushed**; Minor, Notable = **plain**; Major, Historic = **stark**. A hedged or pending story is capped at **plain** (a conditional is never stark).

Why: the Size bands are about the world average, so a story that moves Brazil by 3 points reads Negligible at world (107 of 119 baseline stories were Negligible). The entry's own tier says how big it is for the people it reaches. In the reference run the local stories at world focus came out plain (Brazil, Kenya, Chile, Japan) instead of "tiny".

How the register changes the words (each rule is a column or filter in the tables):

| | stark | plain | hushed |
|---|---|---|---|
| families allowed to lead | all, and SCALE (only stark) | all but SCALE | all but SCALE, STAKE and TURN (a small effect's shape and stakes are noise) |
| frame noun `{frame}` | `noun` ("squeeze") | `noun` | `noun_hushed` ("mild squeeze", "faint ripple") |
| frame verb `{frame_vp}` | `vp_stark` ("feel a hard squeeze") | `vp_plain` ("feel the pinch") | `vp_hushed` ("feel a slight pinch") |
| hooks | rows tagged stark ("A major squeeze:", "Hard to miss:", "Nearly everyone feels this:") | untagged rows | rows tagged hushed ("..., and a small number of people respond:", "...; the effect is slight:") plus untagged rows |
| verbs | rows tagged `stark|plain` allowed ("take to the streets", "flout official rules") | same | those rows excluded |
| size word | not required | not required | **required**: the headline must contain a word from lexicon `soft`; if it does not, `{soft_tail}` adds one (", if only slightly") |
| line 2 arc | allowed | allowed | never (the shape of a tiny move is not worth a line) |

The degree words never follow the register: "sharply" or "far" still needs 3 points or more on that theme (v1 cut points 0.75 and 3). So a stark statement is never louder than its numbers, and a hushed one never hides a 2-point move. Since v2.1 the degree word also agrees with the printed figure (section 17.1).

## 5. Forecasts speak about what would happen if they came true

The engine counts a forecast or an opinion at weight 0.3 (`type_weights.csv`), so its effects are scaled down, and in v1 72% of forecasts went quiet ("no decision moves enough to matter"). But the weight is a doubt discount, not the size of the effect: the engine can say what the story would do if it were true.

Rule: for a hedged story with `identify.weight < 1`, every number the composer reads (places, local test, themes, register, anchor) comes from `impact.if_true` (contract: the same run with type weight 1.0). The words say it is conditional: the hook is an IF hook (a hedge first, or a trigger with its modal in the first four words followed by a hedge tail), the trigger and theme 1 carry the modal, and an anchor is worded "would". A happened story counted at reduced weight (s103: happened 0.3) keeps the weighted numbers: it is not hedged, so it must not be inflated.

Effect in the reference run: of the 52 forecast and opinion stories, 30 now say what would change if true (e.g. wheat failure: "Prices would rise, forecasters say: if so, for every 100 people, about 6 more would cut spending than otherwise."), and 22 stay quiet because even in full they move less than 0.25 points. Those 22 say so ("Even if the forecast holds, ...", "A forecast that ...; even in full, it would leave choices almost untouched.").

## 6. The hook generator

### 6.1 Families, in the order they are tried

| # | Family | Leads when (numeric test) | Phrasings | Example (golden) |
|---|---|---|---|---|
| 1 | **IF** (hedge, if-true) | hedged or pending | per certainty: forecast 13, opinion 12, unclear 10, pending 10, announced_w 8 (7 or 6 hedge openers + tails + trigger forms) | "Prices would rise, forecasters say: if so, ..." (G20) |
| 2 | **WHO_LOCAL** | local story at world focus | 10 | "Only Kenya feels this:" (G13) |
| 2 | **WHO_MOST** | v1 WHO lead, kind x2 or many times | 9 (valence-tagged: "bear the brunt" bad only, "gain the most" good only) | "India reacts most:" (G05) |
| 2 | **WHO_OPP** | v1 WHO lead, kind opposite | 6 | "{Place} bucks the trend:" |
| 3 | **CONTRAST** ("X, but Y") | a partner reading exists (below) | 7 | "Prices will rise, yet government budgets will get breathing room:" (G08) |
| 4 | **SCALE** | register stark | 8 (reach-gated ones need reach >= 90% or >= 60% at world focus) | "No small shift:" (G11) |
| 5 | **STAKE** | a shown theme's top decision has stakes >= 4 (`decision_stakes.csv`: change_work, move, study_train, family_change, start_business, borrow) and moves 0.75 points or more; register not hushed | 7 | "This reaches choices that are hard to undo:" (G09) |
| 6 | **TURN** | register not hushed, and either **turn_shift** (a different theme leads at Later than at Now, both >= 0.25) or **builds** (v1 arc builds or builds_sticks) | 6 shift + 7 builds | "Not one effect but two:" (G07), "Not felt all at once:" (G01) |
| 7 | **TRIGGER** | always (the default) | 14 (6 hushed-only) | "Prices rise, and people have less to spare:" (G31) |
| q | **QUIET_*** and **NOTHING** | quiet branch (section 9) | 6 to 13 per case | "Factories would produce more on this forecast, though too faintly to change what people do." (G18) |

Why these families, and why in this order:
- **IF first**: the reader must know before anything else that the story is not reported news (v1 hard rule 2). The if-true numbers are the only honest way for a forecast to say something.
- **WHO next**: a local story told at world focus is mainly a statement about where (v1 rule, measured: 17 of 120).
- **CONTRAST** before scale: a mixed story told as one-sided is wrong, not just flat (review r17 Nigeria). The partner is found from numbers, so no classifier question is needed.
- **SCALE** only when stark: a big hook on a small number overclaims.
- **STAKE** before TURN: hard-to-undo choices (moving, job change, borrowing) matter more than the timing.
- **TURN** is the owner's "now B is the issue", defined on the engine's horizons: what people do first is not what they do later (F07 school cuts: first they cut back, later they brush off rules). The topical version ("the story is about A, the real issue is B") was rejected: it would spotlight the guessed-weight side effects the review flagged ("stick to the rules" after a gene-therapy trial) as if they were the point.
- **TRIGGER** is the default: the change itself, phrased 14 ways ("{Trigger}:", "As {trigger},", "{Trigger}, which means", "{Trigger}, leaving", "{Trigger}, and {subj} {frame_vp}:", ...).
- A family with no eligible hook (every row fails a compatibility rule) is skipped and the next family is tried.

**Contrast partner (numeric).** Valence of a reading: lexicon `valence` says whether "up" is good, bad or neutral for ordinary people (from the v1 notes). The lead pick is the reported trigger pick (`keep_one`, v1). A partner is another reading with the opposite valence, reported or one of the trigger picks, not `news_overload` (it measures the news flow, not people's conditions), with |amount| at least half the lead pick's (comparable weight, so a trace reading cannot flip the story). Among partners take the highest trigger probability (`story.trigger.probs`), then the larger |amount|. When a partner exists the trigger shows only the lead pick; the "but" clause carries the other side, and the body states the **net** response ("on balance, ..."). In the reference run 9 world stories had a partner: 2 led with CONTRAST, 3 used it in a WHO body ("..., but ...; on balance, ..."), and 4 carried it in line 2 because the contrast body did not fit the budget or the WHO body was picked before it.

### 6.2 Link compatibility (which parts may join)

Hook rows carry `join`, `trigger_in_hook`, `certainty`, `register`, `valence`, `needs` and `frames`; body rows carry `families`, `join`, `trigger_in_hook`, `needs`, `certainty`, `register`. A part is eligible only if every listed condition holds.

| Family | Frames | Certainty | Register | Direction / valence | Place |
|---|---|---|---|---|---|
| IF | any | forecast, opinion, unclear, announced_w, pending (rows say which) | hushed, plain | any | local hedged stories take the local bodies ("..., and Argentina will feel it almost alone:") |
| WHO_LOCAL | frame-word rows need fit | happened, announced, pending | any | any | entry is a country and the story is local |
| WHO_MOST / WHO_OPP | frame-word rows need fit | happened, announced, pending | "bear the brunt" plain/stark only | "hit hardest", "brunt" bad only; "gain the most" good only | geo rows ("Strongest in") for countries and regions, "Strongest among" for audiences |
| CONTRAST | any | happened, announced, pending | any | partner has the opposite valence | any |
| SCALE | "A {tier} {frame}" rows need fit | happened, announced, pending | stark | any | reach rows only at world focus with a resolved place |
| STAKE, TURN | any | happened, announced, pending | plain, stark | any | any |
| TRIGGER | frame-verb rows need fit; causal joins ("so", "Because") only for causal frames (squeeze, scare, blow, freeze) | happened, announced | any (6 rows hushed only) | any | any |

Slot-level rules (each is enforced by a column or by the composer):
- **L1 frame words need fit.** `{frame}` and `{frame_vp}` only when theme 1 fits the frame (`fits_themes`). So "Only Germany feels this surge: ... push back in public" is allowed (surge fits voice+), "This scare stays in Sudan: ... push back in public" is not; the frame-free row is used instead ("Only Sudan feels this:").
- **L2 frame bars.** A frame whose `bars_themes` contains a shown theme fails the guard (scare bars protection-; relief, boost, squeeze, freeze, blow bar the spending sign they contradict). The lexicon row `theme,protection,down` "ease off on precautions" and "relax their guard" also carry `frames_not = scare|blow`.
- **L3 modal agreement.** The modal sits on the trigger and on theme 1 only; theme 2 and line 2 never repeat it except anchor wording in a hedged story ("would cut spending"). Joins that need a bare verb ("{Trigger}, leaving people to ...", "nudging people slightly:") require no modal (`needs=no_modal`).
- **L4 "as" needs a plain trigger.** "As {trigger}," and "as {trigger}, ..." only when the trigger is plain present (no modal, no "should"): never "as prices will fall" (`needs=plain_trigger`).
- **L5 no inner "and" twice.** A verb row flagged `and` ("protest and strike", "buy shares and funds") as theme 1 suppresses theme 2; theme 2 never uses a flagged row.
- **L6 place honesty.** "Only", "alone", "stays in" only for a local story; never a country name when the entry is world or unresolved (v1 rule A).
- **L7 valence words.** "hit hardest", "bear the brunt" need a bad story; "gain the most" a good one; "There is an upside too" / "There is a cost too" in line 2 must match the partner's valence.
- **L8 one frame noun per statement** (the hook is the only place it appears; line 2 has no frame words).
- **L9 one number per statement** (section 8).
- **L10 hushed needs a soft word** (section 4).
- **L11 TURN bodies.** A turn_shift hook takes only the two-horizon bodies ("at first people tighten their belts, later they brush off official rules"); a builds hook takes ordinary bodies.
- **L12 contrast bodies.** When a partner exists and the lead family is WHO or IF, the "but ...; on balance, ..." bodies are preferred.
- **L13 subject.** After a WHO hook the body subject is `{there}` ("people there", "residents", "those living there", "they" for an audience), never the place again.

### 6.3 Bodies and joins

A hook ends in one of six joins, and a body must declare the same join and agree on whether the hook already holds the trigger: `colon` ("Only Kenya feels this:"), `comma` ("If the forecast holds,"), `bare` ("{Trigger}, which means"), `to` ("{Trigger}, leaving"), `they` ("{Trigger}, and people feel the pinch:" → "they {resp}"), `ifso` ("{Trigger}, one writer argues:" → "if so, ..."). Body preference, first non-empty set wins, then the seed picks within it: (1) anchor bodies when the anchor goes in the headline; (2) contrast bodies (L12); (3) local bodies for a hedged local story; (4) two-horizon bodies for a turn_shift hook; (5) the rest. Counting hook phrasings times the bodies that fit them (anchor bodies left out), each family has 17 to 78 distinct skeletons (TRIGGER 17, CONTRAST 21, WHO_OPP 24, STAKE 28, SCALE 32, WHO_MOST 36, WHO_LOCAL 38, IF about 47 for a forecast, TURN 78), against one per frame and lead in v1; verb, degree and subject choices multiply these further.

## 7. The classifier: no new question

Recommendation: **keep the two existing typed questions** (`sowhat_frame`, `sowhat_trigger`) and add none. The budget allows 2 extra questions per story in total, and both are already used.

- Every new family fires on a number the engine already has: IF on the gate and the if-true run, WHO on peaks, CONTRAST on reading valence plus Q2's distribution, SCALE on the tier, STAKE on the stakes table, TURN on the horizons.
- The candidates considered were a "mixed story?" question (replaced by the valence partner test, which found every deliberately mixed story where the engine produced two opposite reported readings) and a "human stake" or "what is the real issue" question (rejected: it has no number behind it, it would invite framings the engine cannot back, and it would cost a third call).
- What a question would buy in variety is small: in the reference run variety comes from hook and body choice (top opener 3.3%, triple overlap 7%), not from more semantic categories.
- One cheap change is worth testing, not adopting yet: asking Q2 inside Q1's call (1 call instead of 2, as the v1 contract notes). It saves latency, not questions.

## 8. The anchor figure: at most one number

**Candidates** (only numbers the engine already gives, or the new if-true run):

| Id | What | Source | Shown as |
|---|---|---|---|
| A1 | lead decision's peak points at the response row | `places[row][lead]` | "about 5 more in every 100 people cut spending than without it" |
| A4 | the same, in the if-true run (hedged stories) | `if_true.places[row][lead]` | "for every 100 people, about 6 more would cut spending than otherwise" |
| A3 | how many times the world's change the row's change is, same decision | row peak / world peak | "India: some 5 times the average worldwide." |
| (reach) | share of people moved by 0.5 points or more | `rank[].reach` | **never a digit**: reach counts anyone moved by half a point, so "96% of people" would read as "96% of people cut back". It stays as words in the SCALE hooks ("Nearly everyone feels this"). |

**Choice rule** (first that passes; a statement shows one or none):
1. A hedged story: only A4 may show. The weighted numbers of a forecast are never printed, because "1 in 100" for a story counted at 0.3 is neither the true-case size nor a fact.
2. WHO_MOST leads at world focus: A3, if it passes.
3. A1 (A4 for hedged), if it passes.
4. Any other focus: A3 for the focus against the world (line 2), if it passes.
5. Otherwise no number.

**Significance tests** (thresholds and reasons):
- **A1, A4: |peak| >= 2.0 points.** (i) The decision weights behind every move are hand-set guesses; at 2 points or more the rounded figure (2, 3, ...) is off by at most 25%, below 2 a "1 in 100" can be anything from 0.5 to 1.5. (ii) It is twice the "clear" band floor (1 point) used since v1. (iii) It keeps numbers rare (14% of the 120 statements), as the owner asked: one strong emphasis, not data everywhere.
- **A3: ratio >= 3, the world's own peak >= 0.25 points, and the row's >= 1 point.** Below 3 the v1 words ("about twice", "more than") already say it. A world peak under 0.25 makes the ratio noise (for a local story it is roughly one over the country's population share, a fact about population, not about the story), so local stories never show A3.
- No number is shown for a quiet statement (by definition nothing reached 0.25).

**Unit and bands (v2.1, sections 17.1 and 17.2).** The unit is "N in every 100"; near 5 it is "1 in every 20" and near 10 "1 in every 10". A hushed statement shows no figure.

**Rounding, wording, misreading.** Points: round half up to a whole number under 10, to the nearest 5 from 10. Ratios: whole number 3 to 10, "more than 10 times" above. Always "about", "roughly", "some" or "or so" before it, never decimals. Every phrasing names what it is measured against: points say "than without it", "than without this news", "than otherwise" or "who otherwise would not" (the no-event run); A3 says "the world average" or "the average worldwide". The anchor uses the lead decision's own non-comparative act verb (lexicon `act`: "cut spending", "get a health check"), never a theme verb, so the number belongs to exactly one decision, and it replaces the degree word (no "cut back sharply, about 7 in 100").

**Placement.** In the headline when an anchor body fits the 22-word budget, otherwise in line 2 (anchor first). If even line 2 cannot hold it (16 words when it is line 2's only fragment), the statement has no number and the beat records `dropped: line 2 budget` (0 of 120 in the reference run).

**Spans and trace.** The anchor is its own beat, `kind: "anchor"`, with a span over the whole anchor phrase (number, group, verb, comparison). Trace: `A1: spend -7.46 pts at World (peak at Next), vs the no-event control run; shown as 7 (round half up); threshold 2.0`. For A3: `A3: spend India -7.13 vs World -1.31 (x5.44); shown as 5; thresholds ratio 3, world 0.25, row 1`.

## 9. The quiet branch, redesigned

The "nothing to say" sentence now exists only for stories that truly move nothing. Every other quiet story says what it is about (the trigger) and why it is quiet, in one of several forms chosen by the seed:

| Case | Test | Forms | Example |
|---|---|---|---|
| NOTHING | `identify.counted` false and a topic is known (`story.topic`, placement p >= 0.5, not `other`) | 6 | "A crime and policing item with no effect we can measure." |
| QUIET_VAGUE | counted false, no usable topic (the vague stories) | 6 | "Without a clear change to track, there is no effect to report." |
| QUIET_FORECAST | hedged forecast, unclear or announced_w whose **if-true** numbers still stay under 0.25 | 11 | "Taking the forecast at face value, skills and schooling would slip; even then, habits would hold." |
| QUIET_OPINION | opinion, if-true still under 0.25 | 6 | "One writer's case that the news flow could get lighter; even if right, choices would barely shift." |
| QUIET_NOTABLE | happened or pending, trigger severity major or severe, nothing reaches 0.25 | 6 | "Big news, small footprint: ..., and choices barely move." |
| QUIET_SMALL | any other counted story with nothing at the focus | 13 (8 present, 5 announced) | "Supply lines should clog up, though too faintly to change what people do." |
| QUIET_ELSEWHERE | local story, focus is another country or an audience | 6 | "Armed conflict escalates in Ukraine; people in Germany carry on much as before." (G32) |

Rules: forms at a non-world focus name the focus (`{for_subj}` or `{qsubj}`, never "people ... for people in X"); the quiet budget drops the second trigger, then takes the shortest form of the same case; no number; no line 2. In the reference run no quiet sentence appeared more than twice in 120 stories (v1: the opinion sentence 16 times).

## 10. Line 2

Optional, at most two fragments, at most 14 words (16 when the anchor is its only fragment). A fragment is added only when the headline lacks it, in this order:
1. **anchor** (when it did not fit the headline);
2. **contrast**: the partner reading, if the headline does not contain it ("There is a cost too: government budgets come under strain."), or, at a non-world focus, the WHO band against the world (lexicon `l2_who`, words only: "Well above what most people do.");
3. **arc**: builds, builds and stays, sticks or jolt, never "fades", never in a hushed statement, never after a TURN hook (lexicon `l2_arc`, 4 phrasings each);
4. **pending** ("The effects are still to come."), only if the headline has no pending hedge.

Retired: "Elsewhere, barely a ripple." and "Little changes elsewhere." (the WHO hook already says it), every scale tail ("A tiny shift that reaches ...", "A small shift there": the register and the anchor carry size now), "Fades slowly.", "Not in effect yet." (the modal "will" says it). In the reference run 90 of 120 statements (75%) have no line 2.

## 11. Budgets and shrink order

Headline <= 22 words, one sentence. Steps, each recorded in `shrink`: (1) drop the second trigger pick (keep the reported one); (2) drop theme 2; (3) move the anchor to line 2 (re-pick among non-anchor bodies with the same slot); (4) for hushed, the shortest soft tail; (5) the shortest eligible body (all bodies of the family and join, no preference); (6) the shortest hook and its shortest body. No headline in the 360 reference outputs is over 22 words.

## 12. Feed rule (browser only, not in the golden tests)

If the previous statement on the page starts with the same three words, re-pick the hook with slot `hook#2` (then `hook#3`), keeping everything else. Same as v1 in purpose; with hooks spread this evenly it fires rarely.

## 13. Targets the harness will measure

Measured on the 120 diversity stories at world focus unless marked; "measured" is the reference implementation (section 14 caveats).

| Target | Commit | Baseline | Measured |
|---|---|---|---|
| top three-word opener share | <= 5% | 13.5% | 3.3% |
| distinct three-word openers per 100 stories | >= 60 | 38 | 68 |
| hook evenness: within any family with >= 10 uses, top hook share | <= 30% | n/a (one skeleton per frame and lead) | 15% to 25% |
| top body share (all statements) | <= 15% | 16% (top template) | 12.5% |
| quiet forms, excluding true no-impact (NOTHING, QUIET_VAGUE) | <= 40% | 47% | 37% |
| quiet forms (non-vague) that contain the trigger clause | 100% | NO-O never did | 100% |
| repeats of any one quiet sentence | <= 3 | 16 | 2 |
| random triples sharing any five-word run | <= 15% | 37.5% | 7.0% (all foci 8.4%) |
| same-frame triples sharing any five-word run | <= 25% | 60.3% | 13.9% (all foci 19.3%) |
| statements with an anchor figure | 10% to 20% | 0 | 14.2% (17; 8 in the headline) |
| anchors that pass their significance test | 100% | n/a | 100% |
| digits not equal to the anchor's shown value | 0 | 0 | 0 |
| numbers per statement | <= 1 | 0 | <= 1 |
| hushed headlines with a soft word | 100% | n/a | 100% |
| stock tails (the four retired phrases) | 0 | 17% to 41% | 0 |
| headline words | <= 22 | <= 22 | <= 22 |
| composer nulls | 0 | 1 | 0 |
| golden v2 cases reproduced exactly (headline, line 2, family, hook, body, register, anchor) | 33 of 33 | n/a | 33 of 33 (reference) |

## 14. Weak spots (honest)

- **Two inputs are estimated in the reference run.** If-true numbers were taken as places / weight (linear); the real if-true run (contract) will differ a little, because propensities are a sigmoid and effects interact. The place tier used regions as a stand-in for per-person reach. The golden file carries both as explicit test inputs, marked as estimates, so the composer tests do not depend on them; the backend numbers will move some registers and anchors once they exist.
- **Numbers that cannot support a sharp so-what stay soft.** 44 of 120 stories are still quiet because the engine moves nothing by 0.25 points even when counted in full (Sweden's AI assistant, Italy's birth rate, a Dutch chemical leak). That is the honest answer, now said in varied words.
- **Engine side effects still reach the headline.** "people relax their guard and take more trips" after a malaria vaccine (G10), "brush off official rules" after a data breach: faithful to the guessed decision weights, not good so-whats. The fix stays in `decision_weights.csv`, on evidence.
- **The anchor unit repeats on purpose.** "in every 100 people" is the most repeated four-word phrase (16 of 120): one fixed unit lets readers learn how to read our numbers. Four phrasings with different word order keep it from forming the same five-word run in most pairs.
- **Valence is ours.** The good/bad direction of each condition comes from the v1 notes; asset values are neutral (good for holders only), so a share-price story never gets a contrast partner from them.
- **Contrast partners follow the readings.** Egypt's wage rise with fuel-subsidy cuts gets "government budgets come under strain" as its other side, because the engine read fiscal strain more strongly than prices.
- **Hook phrasings are ours and untested on readers.** Variety is measured; whether a reader prefers "Not felt all at once:" to "This one builds:" is not.
- **The 120 stories were written by us** (`sowhat-diversity.md`); about a third are forecasts or opinions by design, which inflates the IF family's share.

## 15. Before and after (world focus)

| Story | v1 | v2 |
|---|---|---|
| Forecasters warn worldwide wheat harvests may fail (forecast, weight 0.3) | If the forecast is right, prices would rise, and people would cut back. / A minor shift that reaches nearly everyone. Fades slowly. | **Prices would rise, forecasters say: if so, for every 100 people, about 6 more would cut spending than otherwise.** |
| Oil prices spiked 20% after attacks on tankers in the Gulf | Fuel and power costs rise, and people spend far less. / A major shift. Builds, then eases. | **No small shift: fuel and power costs rise, and about 7 in every 100 people cut spending who otherwise would not.** / Slow to start, stronger later, then easing. |
| Commentators argue a dip in food and fuel prices might help (opinion, nothing even if true) | An opinion piece: on our numbers no one changes what they do. | **Even granting the writer the point, prices could fall, yet people would barely change course.** |
| Egypt: wage rise for civil servants alongside fuel subsidy cuts (mixed, local) | Egypt takes this squeeze almost alone: wages grow faster, so people there cut back and shop around. / Elsewhere, barely a ripple. A quick jolt that fades. | **Egypt takes this squeeze almost alone: wages grow faster, but government budgets come under strain; on balance, those living there cut back.** / Sharp at first, then mostly gone. |
| Three squeezes in one frame (Brazil, Japan, Spain) | Only Brazil feels this squeeze: ... / Japan takes this squeeze almost alone: ... / Spain takes this squeeze almost alone: ... (each with "Elsewhere, barely a ripple." or "Little changes elsewhere.") | **This squeeze stays in Brazil: ...** / **Felt in Japan, hardly anywhere else: ...** / **Spain carries this one alone: ...** (G23 to G25) |

## 16. Table schemas and slots

**`sowhat2_frames.csv`**: `id, name, noun, noun_hushed, valence (good|bad|any), sense_needed, causal (yes: "so" and "Because" joins allowed), fits_themes (theme+sign list, or any), bars_themes (theme+sign that fail the guard), vp_plain, vp_hushed, vp_stark (frame verb phrases, ";"-separated), definition, probe_statement, classifier_option, status`. `plain` is a row with empty verb phrases and `classifier_option = no`.

**`sowhat2_hooks.csv`**: `id, family, text, join (colon|comma|bare|to|they|ifso), trigger_in_hook (0|1), certainty ("|" list; announced_w = announced at weight < 1), register, valence, needs, frames, note`. `needs` values: `fit, causal, no_modal, plain_trigger, local, who_more, who_opp, partner, stake, turn_shift, builds, builds_fades, reach90, reach60, world_focus, geo, audience`.

**`sowhat2_templates.csv`**: `id, families ("|" list), join (none for quiet forms), trigger_in_hook, needs (the hook values plus anchor), certainty, register, template, note`.

**`sowhat2_lexicon.csv`** (long format, one phrasing per row): `kind, id, sign, text, register, frames_not, flags, note`. Kinds: `decision` (160: 4 per decision and direction; flags `deg` has a degree slot, `and` has an inner "and"/"or"), `act` (40: the anchor's non-comparative verb), `theme` (60: 3 per theme and direction), `degree` (12: 3 per degree word and position), `valence` (39; flag `no_partner`), `hedge` (32: 6 or 7 per certainty), `hedge_tail` (18), `there` (4), `soft` (14), `soft_tail` (4), `anchor` (7), `anchor_l2` (7), `stake` (6), `l2_arc` (16), `l2_pending` (4), `l2_contrast` (5), `l2_who` (18), `tier_word` (4). Still read from v1 `sowhat_lexicon.csv`: `condition` (trigger clauses), `place`, `audience`, `ref`, `who` (ratio bands).

**Slots**

| Slot | Filled with |
|---|---|
| `{Trigger}` `{trigger}` | trigger clause (v1 `clause()`, with the modal when the certainty has one, "should" for an expected reading); one pick when a partner exists |
| `{trigger2}` | the partner's clause, same tense rules |
| `{subj}` | "people", "people in X", or the audience name (response row) |
| `{there}` | lexicon `there` pick for a place ("people there", "residents", "those living there"), "they" for an audience |
| `{qsubj}` `{focus_subj}` | the focus row's subject (quiet forms) |
| `{for_subj}` | empty at world focus, " for " + subject otherwise |
| `{entry_place}` | the entry country's name (QUIET_ELSEWHERE) |
| `{resp}` `{resp2}` | modal + theme 1 verb; " and " + theme 2 verb (no modal) or empty |
| `{now_resp}` `{later_resp}` | the leading theme's verb at Now (with modal) and at Later |
| `{anchor}` | lexicon `anchor` pick with `{n}`, `{grp}` (the subject, or the `{there}` form after a WHO hook), `{mod_}`, `{act}` |
| `{Place}` `{place}` `{s}` `{is}` | WHO row name (v1 place names); "s"/"is" for a place, ""/"are" for an audience |
| `{frame}` `{Frame_cap}` | `noun`, or `noun_hushed` when hushed |
| `{frame_vp}` | pick from `vp_<register>` |
| `{tier}` | lexicon `tier_word` for the place tier |
| `{Stake_cap}` | lexicon `stake` noun of the stake decision |
| `{Hedge}` `{hedge_tail}` | the expanded hedge row (section 3) |
| `{mod_}` `{does}` `{feels}` | modal + space; modal or "does"; modal + " feel" or "feels" |
| `{soft_tail}` | lexicon `soft_tail` pick, only when hushed and no soft word is present yet |
| `{topic}` | `story.topic.name` in lower case |


---

## 17. v2.1 (harness-2 follow-ups, 2026-10-06)

Everything below changes wording or choice, not a fact rule. Where it moves a golden case, `sowhat-golden-v2.md` lists the case and the rule.

**17.1 Degree word and figure agree.** The degree word comes from the theme's size (3 points or more is "large", under 0.75 "small"), the figure from the lead decision's peak, so they could disagree: "rein in spending sharply ... roughly 3 in every 100". Bands, on the shown figure n (extra people per 100):
- **n under 5: no loud degree word** (sharply, markedly, a lot, far, much). Fewer than 1 person in 20 changes what they do, so a loud word overclaims. The theme reads at mid size (no degree word).
- **n 5 or more: no soft degree word** (a bit, a little, slightly, a touch). One person in 20 or more is not slight.
- Between: words from the theme size as before. The test is on the figure that is *printed* (headline or line 2); a figure that is dropped for budget changes nothing already composed (the composer reads the candidate figure, so the words stay on the safe side).
- Multiples (A3) and statements with no figure keep the v1 degree rule.
- **A hushed statement never shows a figure** (a small effect is said small; "if only slightly" beside "7 in every 100" would contradict itself).

**17.2 The unit.** Only where the figure supports it: raw value within half a point of 5 (4.5 to under 5.5) reads "about 1 in every 20" (same four phrasings, `100` replaced by `20` and `{n}` by 1); within one point of 10 (9 to under 11) "about 1 in every 10"; every other value "N in every 100". The figure is then two digit runs, [n, unit]: the contract check is "one figure", and `anchor.figure` is `{n, unit}`. The "than without it / than otherwise / who otherwise would not" wording (measured against the no-event run) stays, and the hover trace still says so. A hedged "who otherwise would not" agrees with its modal (could: "who otherwise could not").

**17.3 Even choice among compatible hook rows.** Why IF01 was 75% of IF: not a filter, the pick. Design section 3 expanded a hedge row into one candidate per phrasing, so IF01 (7 phrasings) was 7 of 13 candidates for a forecast and, with the fallback to the first workable hook, more still. Now the hook ROW is picked evenly among the compatible rows (slot `hook`: forecast 4 rows, opinion 3, announced at weight 2, unclear 2, pending 2) and then its phrasing (slot `hook:phr`). Rows with one phrasing are unchanged.

**17.4 Rotation.** "Almost alone" came from the single hedged-local body B34 (and WL02, WL06). Added hooks WL11 to WL13, hedged-local bodies B36 to B38 (comma) and B14, B15 (colon; B13 reworded without the "elsewhere" clause and its second modal). Added three arc wordings per arc kind (7 each; "Short-lived." became "The effect is short-lived."), forecast quiet forms QF12 to QF14, and QF03 now ends "little would change" (the old ending, "habits would hold", read oddly after "budgets would come under strain").

**17.5 Consequence words need a response that agrees with the trigger (`coherent`).** Root cause of "Supply lines clog up, leaving people to spend more" and "As soon as it starts, pollution levels will fall: people ... rein in spending". The lead trigger's valence (lexicon `valence`) against the direction of the response (spending sense, or the lead theme when the sense is flat): bad trigger with a rise, or good trigger with a fall, is **incoherent**. Hooks and bodies that assert a consequence or a frame (in turn, so, because, which means, leaving, as ..., any row needing `fit`, TR07, TR11, TR12) carry `needs = coherent`. An incoherent response is introduced "on our numbers," (a model result, not a stated cause) unless the body already says "on balance"; it is dropped first when the headline is over budget (shrink step "dropped 'on our numbers'"). The line 2 contrast opener "Against that," is gone: the partner is the opposite valence, not an answer to the headline.

**17.6 Quiet forms.** Two triggers joined by "and" are not placed before another "and" in the same form (s051): the lead trigger alone is used.

**17.7 Budget.** A statement is never null for the word budget: after the shrink steps, names are shortened (DR Congo, US, the last two words of an audience name), then the subject is "people" (shrink steps "short place name", "plain subject"; the quiet branch has the same two).

**17.8 Families that never led in the real set** (STAKE, WHO_MOST, WHO_OPP, SCALE) all fire under the rules; the unit tests build their inputs (golden cases G09, G05, G03; WHO_OPP from G05 with an audience moving the other way). No family had to be removed.


## 18. v2.2 (independent review follow-ups, 2026-10-06)

**18.1 A world value under 0.25 is never a denominator (review C1).** `ratio(row, ref)` used to turn a world value of exactly 0 into "far less" and print "Well below the average" for the one country that moves. Rule: when the reference moves less than 0.25 points, there is nothing to compare with. If the row moves 0.25 or more the kind is `alone` (salience ln 10, so it passes the ln 2 test; `l2_who` rows "Almost no one else is affected." / "Hardly anyone else moves." / "The rest of the world barely moves."); if neither moves, `same` (nothing said). A real "below the world" still reads as below. As a WHO lead (kind `alone` counts like "many times") it never makes a "times the average" claim, because A3 needs a world value of 0.25.

**18.2 The anchor hover is plain words, kept in the lexicon table.** `sowhat2_lexicon.csv` kind `trace` holds the sentences (`anchor_pts`, `anchor_hedge`, `anchor_fraction`, `anchor_multiple`, `none_small`, `none_hushed`, `none_unresolved`, `none_budget`, `none_partner`, `none_other`, and the words for forecast, opinion, uncertain story and announcement). The hover says: a model estimate, not a count; in our simulated population about {n} more people in every {unit} would {act} in the run with this story than in the same run without it; the largest gap across Now, Next and Later, reached at {checkpoint}; Next is roughly a month after the news if one model step is a day, and that time scale is our guess; it rests on hand-set decision weights; a figure is shown only when the gap is at least 2 in 100. For a hedged story: "This assumes the forecast comes true. Counted as a forecast, the engine gives it 0.3 of that weight." For 1 in 20 and 1 in 10: "(4.8 in 100, shown as 1 in 20)." A statement with no figure says why in words. The technical line (rule id, signed points, rounding, threshold) follows under "Details:". The missing space ("theno-event") is gone and a test scans every trace string of every output for typos, doubled spaces and leftover placeholders. Verb agreement after 1: "about 1 in every 20 people cuts spending" (the act verb takes an "s"; with a modal it stays bare).

**18.3 The other side of a mixed story is the last thing dropped.** "Shortest body" now chooses among the partner bodies when the story has a partner; two new shrink steps: "another hook that fits" (a hook picked evenly among those that fit, before the shortest one is forced; this also stops CT01 winning every long CONTRAST statement) and, last of all, "other side to line 2" (the partner leaves the headline for line 2). In line 2, when the figure and the other side cannot both fit, the other side stays and the figure goes (the hover says "the second line is kept for the other side of the story").

**18.4 A place that is not in our model (`story.place_status` "unresolved").** The statement does not speak for anyone: family `UNRESOLVED_PLACE`, six forms that say in plain words that the place is not in our model ("The place in this story is not in our model; {trigger}, but we cannot say who is affected."), no response, no figure, no who-beat, register "hedged", frame plain, never a place name. The trigger keeps its modal for a hedged story. The `place` beat carries `story.place_trace`. A missing field, "single" and "worldwide" leave today's behaviour (golden cases stay valid). A story with no trigger pick cannot be said and returns null.

**18.5 Even choice, second pass.** IF hook rows grew from 4 to 9 for a forecast (IF06 to IF09, the new rows expand into four openers each, `hook_open` lexicon rows); a hedged announced story had only two rows, so IF01 took half. Colon bodies for hooks that already hold the trigger grew from B11 to B11 and B16 to B18, so B11 no longer carries them all (top body share 15.8% fell to 7.5% on the 120). A plural region ("cities in India") takes a plural verb.
