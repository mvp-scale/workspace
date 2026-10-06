# So what: what it is made of (draft, 2026-10-06)

The "so what" is the one sentence under a story that says what changes for people. Today it is one template, `Worldwide, people are likelier to X, Y and Z.`, with three pre-written decision phrases dropped in. It reads scripted because every story gets the same skeleton, and because three phrases joined by commas carry no focus.

This spec breaks a so-what into **beats**. A beat is one piece of meaning that comes from numbers the engine already produced. Each beat has a short text and a trace, and the trace is shown on hover. A **frame** is the shape of the effect (squeeze, relief, scare...). The classifier picks the frame, and the frame picks the sentence skeleton. The **lead beat** is the strongest beat and goes first. So the sentence shape changes from story to story because the numbers differ, not because we rotate wording.

Files:
- `rules_v2/sowhat_frames.csv`: the 10 frames and the classifier statement for each.
- `rules_v2/sowhat_lexicon.csv`: every word we use (20 decisions, 39 conditions, themes, degree, tier, band, reach, certainty, arc, who, place and audience names).
- `rules_v2/sowhat_templates.csv`: 48 templates, 4 for each of the 10 frames and for the plain fallback, plus 4 quiet forms.
- `spec/so-what-contract.md`: the JSON the backend adds, and what the browser composer takes and returns.
- `spec/sowhat-golden.md` and `.json`: 22 stories with 44 expected outputs (the composer's unit tests).
- `spec/sowhat-fixtures/01..22.json`: the real engine responses used as test inputs.

Hard rules (from the owner):
1. **No invented facts.** Every phrase traces to a number the engine or the classifier produced. The words are ours, the facts are the engine's.
2. **Hedge by certainty.** The tense comes from the story type: happened, announced, forecast or opinion.
3. **Plain, lean, concrete.** Use only our vocabulary: topics, conditions, person states, decisions, resources, groups and places.

Terms used below:
- **Points** means points of likelihood. +1.3 points means the chance that a person takes that decision is 1.3 percentage points higher than in a control run with no event.
- **Peak** is the largest change (positive or negative) across Now, Next and Later, the three horizons of `impact.places[row][decision]`.
- **Focus** is the row chosen in the "So what for" dropdown: the world, a country, a region of a country, or an audience.

---

## 1. The beats

| Beat | What it says | Source numbers | Required? |
|---|---|---|---|
| **TRIGGER** | What changed, in everyday words ("loans get cheaper") | `identify.readings` (dial, direction, basis) + classifier question 2 (trigger pick) | Required whenever a reading exists |
| **CERTAINTY** | Did it happen, is it announced, a forecast, an opinion? Sets the tense and the hedge | `identify.gate` (opinion, forecast, announced, happened), reading `mode` | Required (always sets the tense; shown in words only when the story is not plain news) |
| **RESPONSE** | What people do: at most two themes, one verb phrase each, with a direction | focus row peaks, `impact.places[focus][decision]` | Required when any decision moves 0.25 points or more at the focus; otherwise the quiet form is used |
| **SCALE** | How big: Size tier and reach (world), or a size band (other focus) | `impact.significance.tier`, `impact.rank[d].reach`; for a non-world focus, the band of the focus lead move | Optional (lead or line 2) |
| **WHO** | The place or group whose result differs most. A contrast, not a repeat of the average | peak of the lead decision for every row vs its reference row | Optional (lead or line 2) |
| **ARC** | The shape over time: a jolt that fades, builds, fades slowly, or sticks | Now, Next and Later of the lead decision at the focus | Optional (line 2) |
| **FRAME** | The shape of the effect, which picks the template family | classifier question 1 (frame pick) + coherence guard | Required (falls back to `plain`) |

### 1.1 TRIGGER
- **Candidates:** `identify.readings`, both reported and expected, up to 6 by |amount|.
- **Pick:** classifier question 2 (section 3). If only one reading exists, that reading is used and no question is asked.
- **Second reading:** added only when the top pick beats the runner-up by less than 0.2 in probability. Both are joined with "and", so the trigger never lists more than two.
- **Words:** `sowhat_lexicon.csv` kind `condition` gives a noun plus a verb per direction (`down`/`up` agree with the noun; `down_bare`/`up_bare` follow a modal verb such as "will"). Examples: borrowing_cost down = "loans get cheaper"; war_terror up = "armed conflict escalates".
- **Tense:** if the story has a modal (section 1.2), the trigger uses noun + modal + bare verb ("jobs would get less secure"). Otherwise a reported reading is in the plain present ("loans get cheaper"), and an expected reading takes "should" ("social divides should deepen"), because the engine expects that change but the story does not report it.
- **Trace:** `trigger choice: borrowing_cost 0.98, runner-up private_debt 0.01; borrowing_cost down: strength 0.996, reported, size notable`.
- Evidence attributes (`identify.evidence`, for example "layoffs", "outbreak") are shown in the trace only. Writing them into the sentence would be sharper, but it needs about 80 more lexicon rows (see section 8).

### 1.2 CERTAINTY
The kind comes from the **gate** (what the story is), never from `weight.type` (how much the engine counts it). Checks run in this order, first match wins; `sowhat_story.certainty` and `deriveStory` in `sowhat.js` use the same order. Evidence: over 46 real stories, every future-facing story has `happened` <= 0.22 and every story that happened has `happened` >= 0.91, so 0.5 splits them cleanly.

| Order | Kind | Rule | Modal | Words |
|---|---|---|---|---|
| 0 | no_impact | `identify.counted` = false | none | quiet form NO-X |
| 1 | opinion | `gate.opinion` >= 0.9 | could | leads: "One writer's view; if it catches on," / "An opinion piece; if enough people agree," |
| 2 | forecast | `gate.happened` < 0.5 and `gate.forecast` > `gate.announced` | would | leads: "If the forecast is right," / "If this forecast comes true," |
| 2 | announced | `gate.happened` < 0.5 otherwise | will | line 2: "Not in effect yet." |
| 3 | pending | `gate.happened` >= 0.5 and every reading is `expected_pending` | none (plain present for the event); the readings say "should" | line 2: "Effects not felt yet." |
| 3 | happened | `gate.happened` >= 0.5 otherwise | none (plain present) | none |

The `unclear` kind ("may") is no longer produced by the gate (its lexicon row stays for stories typed unclear by other callers). Examples: a council vote (happened 0.97) is news even with a forecast cue; an op-ed (opinion 1.0) is an opinion; a UN famine warning (announced 0.94, forecast 0.99, happened 0.03) is a forecast; a company saying it will cut jobs (announced 0.99, forecast 0.83) and a tax rise (announced 0.99, forecast 0.46) are announced; a recession warning (opinion 0.71, forecast 0.99, announced 0.12) is a forecast, not an opinion. The approved vaccine (golden 13) happened; only its effects are pending, so the event stays plain present, the reading says "should" and line 2 says "Effects not felt yet." Never "will" for a pending effect.

Forecast, opinion and unclear always **lead**. Readers must know first that the story is not reported news. The engine has already cut these stories to 0.3 or 0.5 weight (`type_weights.csv`). The hedge says the same thing in words.

### 1.3 RESPONSE
Inputs are the peak values of all 20 decisions at the response row. That is the focus row, except for a local story at world focus, where it is the entry row (section 1.5).
1. Keep decisions whose |peak| is 0.25 points or more (MIN_MOVE).
2. Group them into **themes** (lexicon kind `theme`): spending (spend, buy_new, subscribe), switching, money (invest, borrow), travel, home_family (move, family_change), work (change_work, study_train, start_business), voice (share, vote, protest), protection (health_action, stockpile_prepare), support (claim_support, donate_volunteer), rules (break_rules).
3. Each theme's size is the |peak| of its top member, and its sign is that member's sign. **Verb:** if at least two members share the top member's sign and the second is at least half the first, use the theme verb ("open their wallets"). Otherwise use the top member's own verb ("invest more").
4. **Degree** comes from the theme size. Under 0.75 points: "a bit" / "a little". From 0.75 to 3: no word. 3 or more: "far" / "sharply". It fills `{deg}` (before a comparative: "spend far less") or `{degp}` (after a verb: "cut back sharply").
5. Rank the themes by size. Theme 1 is always shown. Theme 2 is shown only if it is at least 0.4 times theme 1. So there are **never more than two**, and often only one, which keeps the focus.
6. The modal from CERTAINTY goes in front of theme 1 only: "people will cut back and apply for aid".

### 1.4 SCALE
- **World focus:** the tier word from `impact.significance.tier` (Negligible = tiny, Minor = minor, Notable = notable, Major = major, Historic = historic), plus reach from `impact.rank[lead].reach` (90% or more = nearly everyone, 60 to 90% = most people, 40 to 60% = about half of people, 20 to 40% = a large minority, 5 to 20% = a small minority, under 5% = very few people). The tier matches the Size badge, so the sentence and the badge agree.
- **Any other focus, or a local story:** a band on the focus lead |peak| with cut points 0.25, 1, 3 and 8 (small, clear, big, huge). These are the cut points the page's older Size badge used. They are needed because `significance` exists only for the world row.
- **Salience** (how strongly it competes to lead): Major or Historic, or big or huge = 1.0 (leads when nothing outranks it); Notable 0.7; clear 0.5; Minor 0.4; small 0.3; Negligible 0.2. In **line 2** a tiny move always shows its size: when the world tier is Negligible or the focus band is small, the scale fragment is given salience 1.0 (so it is shown ahead of the arc), because a confident headline over a 0.3-point move must not hide how small it is.

### 1.5 WHO (contrast)
Everything is measured on the **lead decision** (the decision with the largest |peak| at the response row), using peaks.
- **Local story:** the entry is a country (`identify.entry`), the world's largest move is under 0.25 and the entry's largest is 0.25 or more. At world focus this **always leads**: "Only Kenya feels this squeeze", "Ukraine takes this scare almost alone", "This rift stays in Brazil". Line 2 adds "Elsewhere, barely a ripple." When the entry country is the focus, it goes to line 2 instead: "Barely felt outside Kenya."
- **Candidates at world focus:** countries with population share 0.5% or more (Peru's towns at 0.0% share must not win), and the 8 audiences. **Country focus:** the country against the world, plus each of its three regions against the country. **Audience or region focus:** the row against the world.
- **Ratio** r = row peak / reference peak. The bands (lexicon kind `who`): 2.5 or more = "about n times as much" (above 5, "many times"); 1.75 to 2.5 = "about twice"; 1.25 to 1.75 = "more than"; 0.8 to 1.25 = "about like" (normally not shown); 0.6 to 0.8 = "a bit less than"; 0.35 to 0.6 = "about half as much as"; 0 to 0.35 = "far less than"; negative = "the other way from" (only when both moves are 0.25 or more).
- **Salience** = |ln r|, capped at ln 10. It is halved when r < 1, because where an effect concentrates matters more than who is spared. Opposite sign = 2. Local = 9 at world focus, 0.9 elsewhere.
- **WHO leads** at world focus when the case is local, or when salience >= ln 2 and the kind is twice, n times or opposite. At another focus it leads only when the contrast is a sub-row (a region against its country). The focus against the world never leads there, because the headline would then repeat the world one; it goes to line 2 without a subject ("About half as much as most people.").

### 1.5b Honesty about place (rule A)
The engine's entry (`identify.entry`) says where the story is. `identify.country` and `country_p` (ask_country's answer) say how sure it is. Three cases, called `story.entry.place`:
- **country**: the entry is a real country row. WHO may be composed.
- **world**: ask_country chose the whole world (country `global` with a probability). The story is about the world, no country is special, so no country is named as WHO (audiences still may be: they differ by who people are, not where they live).
- **unresolved**: ask_country named a part of the world and no country in it (`global` with no probability: the EU, Ireland, "the Gulf", two countries, a country with no row). The engine applied the event to the world anchors, so every country moves about equally and the "hardest hit" place is noise (review: Rwanda, Sweden, Cameroon). The so-what then says nothing about where: the plain family (PL-T, or PL-C when hedged), no WHO, no "Only X", no reach claim ("reaches most people"), and line 2 gives the size word only ("A minor shift.").

Even for a real country entry that is not local, a country is named as WHO only when its change on the lead decision is **at least twice the next country's** (same cut as the "twice" WHO band). Reason: below that the ranking is between near-equal rows, and naming one would report noise as a finding. Audience candidates are not subject to this rule. The threshold is not tuned to any story; it is the existing salience cut (ln 2).

### 1.6 ARC
Uses the lead decision at the response row: v = (Now, Next, Later). The horizons are 3, 50 and 240 ticks. What one tick means is still an open question in the engine, so the arc words name no calendar time.
| Arc | Rule | Words (line 2) | Salience |
|---|---|---|---|
| builds | peak after Now and |Next| >= 1.25 x |Now|, keeps under 60% by Later | "Builds, then eases." | 0.8 |
| builds_sticks | as above, keeps 60% or more | "Builds and stays." | 0.8 |
| sticks | keeps 60% or more by Later | "Sticks around." | 0.6 |
| jolt | peak at Now, keeps under 35% | "A quick jolt that fades." | 0.6 |
| fades | anything else | "Fades slowly." | 0.3 |

"Keeps" means Later divided by peak, clipped to the range 0 to 1, as in `impact.rank[].persistence`.

### 1.7 FRAME
One typed choice question asks for it (section 3). The 10 frames:
| Frame | Definition | Sense needed |
|---|---|---|
| squeeze | Costs rise or income gets less secure, so people have less room and tighten up. | not up |
| relief | Costs fall or pressure eases, so people have more room and loosen up. | not down |
| scare | A threat to health or safety, so people protect themselves and pull back from going out. | not up |
| blow | A sudden hit to one place, company or industry that falls hardest on the people there. | not up |
| shake-up | A change in how things work (a new tool, rule or broken service) that pushes people to switch or adapt. | any |
| surge | Something climbs fast (home or share prices, demand, arrivals) and people pile in or scramble. | any |
| freeze | Uncertainty, more than cost, makes people wait: big decisions get put off. | not up |
| rift | Politics, unfairness or conflict between groups, so people take sides and speak up. | any |
| boost | A gain (a cure, an investment, better services) that makes life easier or safer. | not down |
| ripple | A story people hear about that changes little in daily life. | any |

**Coherence guard.** The frame must not contradict the response. Sense = spend + buy_new + subscribe + travel peaks at the response row: -0.25 or less is down, +0.25 or more is up, anything else is flat. If the top frame breaks its "sense needed" rule, the runner-up is used if it passes. Otherwise the `plain` family is used. This check runs in the browser for each focus, because one story can be a squeeze in one country and flat in another.

---

## 2. Order, budgets and line 2

**Lead beat**, checked in this order (the first match wins):
1. no_impact, or no decision moves 0.25 points or more at the focus → **quiet** form (section 2.1)
2. certainty is forecast, opinion or unclear → **CERTAINTY**
3. WHO leads (rules in section 1.5) → **WHO**
4. SCALE salience is 1.0 → **SCALE** (relief at a non-world focus falls back to TRIGGER, because RL-S needs reach)
5. otherwise → **TRIGGER**

The template is (frame, lead) → `sowhat_templates.csv`. RESPONSE is in every non-quiet template, and TRIGGER is in every template except NO-X and NO-O.

**Line 2** holds up to two fragments from the beats that did not lead, highest salience first, and only those with salience 0.3 or more:
- "Elsewhere, barely a ripple." or "Little changes elsewhere." (local story at world focus, 1.0; the variant is chosen by a hash of the headline, never at random; not shown under the ripple frame, because RP-W already says "even there the change is small")
- "Not in effect yet." (announced) or "Effects not felt yet." (pending), 0.95
- the scale fragment for a tiny move (1.0, see section 1.4)
- the ARC, SCALE and WHO fragments with the saliences above (WHO capped at 0.95)

**Budgets:** headline at most 22 words, one sentence. Line 2 at most 14 words in at most two short sentences. If the headline is over budget: (1) drop the second trigger reading (keeping the reported reading over an expected one), then (2) drop response theme 2, then (3) for a hedged story use the shorter hedge variant, then (4) use the plain family template. The quiet forms use the same budget: drop the second trigger, the shorter hedge, then the plain sentence "No decision moves enough to matter." The golden file records each step in `shrink`; no headline exceeds 22 words in any test.

**Banned patterns:**
- Comma lists of more than two items. Two items join with "and", never "X, Y and Z".
- The `likelier to X, Y and Z` skeleton. The new templates never use "likelier".
- The same opener across stories. Openers vary by frame, by lead and by the variety rules below.
- False precision. No decimals in prose. Ratios round to "about twice", "about n times", or "many times" above 5. Reach and size are words. Exact numbers live only in the hover trace.
- Calendar time ("next month", "for weeks"). The engine has no calendar for its horizons.
- Any word that names a fact not in the trace: no actors, no amounts, no causes that are not a reading.

**Variety rules** (fixed and testable):
- The certainty hedge has two variants: (frame offset + story text length) mod 2. The offset is 0 for squeeze, scare, shake_up, freeze, boost and plain, and 1 for the rest.
- The local WHO lead has three variants: (frame offset + story text length) mod 3. The offset is 0 for squeeze, freeze and plain; 1 for scare, surge, relief and boost; 2 for blow, shake_up, rift and ripple.
- **Feed rule** (browser only, not in the golden tests): if the previous so-what shown on the page starts with the same first three words, flip the variant. Two job-loss stories in a row with the same frame, certainty and trigger show why this rule is needed (golden 15 is announced since the certainty rule, so it no longer shares an opener with 20; the feed-rule test uses 20).

### 2.1 Quiet forms (the honest "nothing to say")
| Case | Template | Example |
|---|---|---|
| `identify.counted` false | NO-X | "Nothing to say: this story moves none of the things we track." |
| counted, but nothing reaches 0.25 at the focus | NO-Q (RP-S when the frame is ripple) | "New digital tools spread, but no decision moves enough to matter." |
| opinion with nothing at the focus | NO-O | "An opinion piece: on our numbers no one changes what they do." |
| forecast or unclear with nothing at the focus | NO-F | "If the forecast is right, ... but no decision moves enough to matter." |
| a country the story never reaches | NO-Q with `{for_subj}` | "Housing costs rise, but no decision moves enough to matter for people in India." |

---

## 3. The classifier's part: two typed questions

Winnow answers typed questions with probabilities and never writes prose. Both questions use the same state as `classify.py` (`News item (published ...; today is ...):\n<title>. <description>`). They are asked after `C.severity`, so the readings and the moves are already known. As tested they use two different states, which means 2 short calls that can run in parallel (see the contract).

**Q1 `sowhat_frame`** (choice, 10 options)
- instructions: "Which statement best describes the effect of this story on ordinary people?"
- criteria: `sowhat_frames.csv` `probe_statement` for each frame id.
- The state has one extra line: `What our world model found, strongest first: <up to 2 readings in impact_phrases wording>; people <up to 2 decision phrases at the entry row, |peak| >= 0.25>.` Or, when nothing moved: `Our world model found no change.`

**Q2 `sowhat_trigger`** (choice, 2 to 6 options; skipped when there are fewer than 2 readings; reported readings are offered first, expected ones after them; a reading whose dial has no `impact_phrases` row is left out)
- instructions: "Which of these changes is this story mainly about?"
- criteria: reading dial id → `impact_phrases.csv` wording for its direction.
- State: the story text only.

**Why these two:**
- **Frame** is the only beat with no number behind it today, and it decides the sentence skeleton. Everything else (scale, who, arc, response) is arithmetic the engine already does.
- **Trigger** fixes a real weakness. Reading strengths saturate: in the rate-cut story all five readings score 0.93 to 0.996, so ranking by strength or amount is noise, and severity and the expected weight then pick the "main" change. Asking directly gave a pick of 0.9 or more in 15 of the 20 multi-reading stories (borrowing_cost 0.98, health_risk 0.98, war_terror 1.00, disruption 0.97...). The top pick beat the runner-up by 0.38 or more in 19 of 20. The one close case (bank collapse: market swings 0.52 against asset values 0.44) is exactly where naming two readings is right.
- **Not asked:** who is affected (the engine measures this better than a reading of the text could), the arc (the engine's horizons), and certainty (the gate already asks it).

**Measured during design** (22 fixtures, Winnow-12B on :8091, file `sowhat-golden.json` → `story`):
- Confidence is similar either way: the top frame scores 0.75 or more in 16 of 22 stories with the moves line and in 17 of 22 with text only.
- The two versions disagree on 8 stories (06, 07, 10, 11, 12, 15, 17, 19). Text only reads the news (Ford closing → blow 0.96, Kenya drought → blow 0.80, school cuts → blow 0.81, Brazil election → shake-up 0.88). With the moves line, the frame follows what the engine says people do (squeeze, squeeze, squeeze, rift).
- **We use the moves line.** A frame that contradicts the response (a "relief" headline over "people cut back") is worse than a less vivid frame. The guard handles the rest.

---

## 4. Slots used by the templates

| Slot | Meaning |
|---|---|
| `{Trigger}` / `{trigger}` | trigger clause (1 or 2 readings), capitalised or not |
| `{subj}` | focus subject: "people", "people in Kenya", "people in rural India", "people in cities in the United States", or an audience short name ("big-city high earners") |
| `{there}` | "people there" (WHO place is a country or region) or "they" (an audience) |
| `{resp}` | modal + theme 1 verb ("will cut back") |
| `{resp2}` | " and " + theme 2 verb, or empty |
| `{mod_}` | modal + space, or empty (for fixed verbs in templates: "will feel the squeeze") |
| `{lands}` | "lands" / modal + " land" |
| `{Who_lead}` | lexicon `who_lead` text with `{place}`, `{frame}` and `{s}` filled in |
| `{scale}` | tier word (world) or band word (other focus) |
| `{band}` | band word (used by RP-W) |
| `{reach}` | reach words (world only; RL-S) |
| `{Hedge}` | certainty opener, variant by the variety rule |
| `{for_subj}` | empty at world focus, " for " + subj otherwise |
| `{frame}` | frame noun from sowhat_frames.csv (inside `{Who_lead}`) |

Subject names: countries whose names start with "United ", "Netherlands", "Philippines" or "Democratic Republic" take "the". Regions are "cities in X", "towns in X", "rural X" (or "the rural United States"). Audiences use the 8 short names in the lexicon, with this fallback: the label in lower case, commas dropped, plus " people".

---

## 5. Worked example: rate cut, world focus (fixture 01)
| Beat | Text | Trace |
|---|---|---|
| TRIGGER | loans get cheaper | trigger choice borrowing_cost 0.98; strength 0.996, reported, size notable |
| CERTAINTY | happened | weight fact 1.0; happened 0.98 |
| FRAME | relief | relief 0.79, boost 0.19; sense up (+2.18) |
| RESPONSE | open their wallets and invest a bit more | spending: spend +1.30, buy_new +0.88; money: invest +0.61 |
| ARC | Builds, then eases. | spend now +0.97, next +1.30, later +0.72 |
| SCALE | A minor shift that reaches nearly everyone. | Size 20.4 Minor; reach 99.4% |
| WHO | (not shown: big-city high earners at x0.62, salience 0.24) | |

Lead = TRIGGER (no WHO or SCALE strong enough), template RL-T:
> **Loans get cheaper: people open their wallets and invest a bit more.** Builds, then eases. A minor shift that reaches nearly everyone.

Old: *Worldwide, people are likelier to spend more, buy more new things and stay where they live.*

---

## 6. What the composer must never do
- Choose a decision or a place that is not in the numbers, or drop the top one because it looks odd. School cuts → "brush off official rules" is what the guessed weights produce, and the sentence must say it. The fix belongs in `decision_weights.csv`, not here.
- Use the Now column alone. Peaks are used so that a move that builds (rate cut, oil) is not undersold.
- Name a region or country with a share under 0.5% as the world's WHO.
- Name a country as WHO when the story's entry is the world or an unresolved place, or when the top country is not at least twice the runner-up (section 1.5b).

## 7. Weak spots (honest)
- **The Size tier is world-only.** Local stories (Canada housing, Kenya drought, Ukraine) always score Negligible on the badge, while the focus band says "big shift there". The sentence handles it with the local WHO lead and "Elsewhere, barely a ripple", but the badge will look contradictory until significance is also computed for the entry row.
- **Engine side effects reach the headline.** Data breach → "brush off official rules and put off health care". Vaccine → "ease off on precautions" (the engine lowers health actions when health risk falls, although the vaccine itself is a health action). These are faithful to the numbers. They are not good so-whats.
- **Small numbers.** War in Ukraine moves Ukraine by about 1 point and the world by nothing. Brazil's election moves Brazil by 0.4. The sentences are honest but cannot be sharp.
- **Repeated openers** within one frame, certainty and trigger (two job-loss squeezes). Only the feed rule fixes this.
- **Country focus close to the world** (the United States in the school-cut story) gives a headline that differs from the world one only in its subject. That is honest, but flat.
- **A place the engine cannot place** (Mexico, whose region the classifier calls North America, and Turkey, which it often puts in the Middle East; see `sowhat-review.md`, After fixes) now gets the plain place-free sentence, which still says "people" move. Fixing the placement is upstream.
- **All words are guesses**, like the rest of rules_v2. The frame probes were tested once, on 22 stories written by us. The next step is labelled stories.

## 8. Not done (next)
- Evidence-attribute triggers (about 80 lexicon rows: "layoffs hit", "an outbreak spreads"). Sharper, but more to check.
- Per-row significance, so that SCALE uses the same scale at every focus.
- A JS composer with these golden files as tests (`spec/sowhat-golden.json`).
