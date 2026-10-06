# So what: backend and composer contract (draft, 2026-10-06)

This is the split between the server and the browser. The **backend** works out the story-level beats once per story and adds them to the request response as `impact.story`. That includes the two classifier answers. The **browser composer** builds the sentence for whatever the "So what for" dropdown points at (world, a country, a region or an audience) from `impact.story` plus numbers the response already carries. It does no extra request when the focus changes. All words come from three CSVs in `probes/persona/rules_v2/` (frames, lexicon and templates). The server serves them so the page holds no hard-coded phrases.

Rules: see `so-what-ontology.md`. Tests: `sowhat-golden.json` (22 stories, 44 cases).

---

## 1. Backend: `impact.story`

Added by `request_event`, after `C.severity` and the impact run, so the readings and `impact.places` exist.

```json
"story": {
  "version": 1,
  "certainty": {
    "kind": "happened",                     // happened | announced | pending | forecast | opinion | unclear | no_impact
    "modal": "",                            // "" | will | would | could | may ("" also for pending)
    "weight_type": "fact", "weight": 1.0,   // identify.weight (how much the story counts; does NOT decide the kind)
    "gate": {"happened": 0.98, "announced": 0.98, "opinion": 0.0, "forecast": 0.0, "recent": 0.92},
    "trace": "weight fact 1.0; gate happened 0.98, announced 0.98, opinion 0.0, forecast 0.0"
  },
  "frame": {
    "id": "relief", "p": 0.786,
    "runner_up": {"id": "boost", "p": 0.19},
    "probs": {"relief": 0.786, "boost": 0.19, "surge": 0.021, "...": 0.0},   // all 10, from Q1
    "state_moves": ["borrowing becomes cheaper or easier", "people spend more", "people buy more new things"],
    "question": "sowhat_frame",
    "trace": "frame choice: relief 0.79, runner-up boost 0.19"
  },
  "trigger": {
    "asked": true,                          // false when there are fewer than 2 readings (no question)
    "picks": [                              // 1 reading, or 2 when top p - runner-up p < 0.2
      {"dial": "borrowing_cost", "direction": "down", "basis": "reported", "mode": "reported",
       "strength": 0.996, "severity": "notable", "p": 0.982}
    ],
    "runner_up": {"dial": "private_debt", "p": 0.011},
    "probs": {"borrowing_cost": 0.982, "private_debt": 0.011, "housing_cost": 0.004, "...": 0.0},
    "question": "sowhat_trigger",
    "trace": "trigger choice: borrowing_cost 0.98, runner-up private_debt 0.01; borrowing_cost down: strength 0.996, reported, size notable"
  },
  "scale": {
    "tier": "Minor", "score": 20.4,         // = impact.significance (world row only)
    "trace": "Size 20.4 (Minor)"
  },
  "entry": {
    "id": "WORLD:world",                    // identify.entry
    "place": "world",                       // country (entry is a country row) | world (ask_country: whole world) | unresolved (ask_country: a part of the world, no country; identify.country 'global' with country_p null)
    "local": false,                         // entry is a country AND world max |peak| < 0.25 AND entry max |peak| >= 0.25
    "world_max": 1.30, "entry_max": 1.30    // largest |peak| over the 20 decisions at each row
  },
  "cost": {"questions": 2, "calls": 2, "ms": 640}
}
```

Notes:
- `certainty.kind` follows the ontology (section 1.2): from the gate: opinion >= 0.9 is opinion; happened < 0.5 is forecast when forecast > announced, otherwise announced; happened >= 0.5 is happened (pending when every reading is expected_pending). The backend computes it because it needs every reading's `mode`.
- `entry.place` follows ontology section 1.5b. The page falls back to the entry's row type when the field is missing (country row = country, otherwise world).
- Q2 offers reported readings first, then expected ones; a reading whose dial has no `impact_phrases` row is not offered.
- Frame `probs` and trigger `probs` carry the full distributions, so the hover can show "relief 79%, boost 19%" and the coherence guard can fall back to the runner-up.
- With `identify.counted` false, the backend still sends `story`, with `certainty.kind = "no_impact"`, `frame` from Q1 (it is usually ripple), and `trigger.picks = []`.
- `state_moves` is the exact moves line added to the Q1 state (see section 3), kept so the frame is reproducible.

## 2. Classifier cost: 2 extra typed questions

| Name | Type | Options | Asked when | Why this one |
|---|---|---|---|---|
| `sowhat_frame` | choice | the 10 frames (`sowhat_frames.csv` probe_statement) | always | The only beat with no number behind it, and it picks the sentence skeleton. |
| `sowhat_trigger` | choice | the readings (2 to 6), worded with `impact_phrases.csv` | 2 or more readings | Reading strengths saturate (0.93 to 0.996 in the rate-cut story), so the main change cannot be ranked from them. Asking gave a pick of 0.9 or more in 15 of 20 stories. |

A `/v1/systemone` call takes one state, and the two questions were tested with different states (Q1 with the moves line, Q2 with the story only), so as tested this is **2 calls of 1 question each**. Both calls are short (one choice question each) and can run in parallel. Putting Q2 in Q1's state would make it 1 call, but that is untested. Measured on the 22 fixtures: 22 frame answers and 20 trigger answers, with no failures.

Not asked, and why: who is affected (the engine already measures it per row), the time shape (the engine's horizons), certainty (the gate already asks it), and the response (the engine's decision propensities).

## 3. Exact questions

State (same as `classify.py`):
```
News item (published {date}; today is {date}):
{title}. {description}
```
Q1 adds one line to its own copy of the state:
```
What our world model found, strongest first: {r1}; {r2}; people {d1}; people {d2}.
```
where r1 and r2 are the top two readings by |amount| in `impact_phrases.csv` wording, and d1 and d2 are the top two decisions at the entry row by |peak| (0.25 points or more) in `decision_phrases.csv` wording. When nothing qualifies, the line is `Our world model found no change.`

```json
{"sowhat_frame":   {"type": "choice", "instructions": "Which statement best describes the effect of this story on ordinary people?", "criteria": {"squeeze": "This story is about costs rising ...", "...": "..."}},
 "sowhat_trigger": {"type": "choice", "instructions": "Which of these changes is this story mainly about?", "criteria": {"borrowing_cost": "loans get cheaper or easier to get", "...": "..."}}}
```

## 4. Composer input (browser, per focus)

Everything below is already in the response or the rules; none of it requires a new request.

```js
compose({
  story,                         // impact.story (above)
  focus: "COUNTRY:can",          // S.focus
  rows,                          // read.rows: [{id, label, level: world|country|region|audience, parent, share}]
  places,                        // impact.places: {rowId: {decisionId: [now, next, later]}}  (every row id of read.rows)
  rank,                          // impact.rank: [{decision, reach, ...}]  (world reach per decision)
  readings,                      // identify.readings (needed for clause wording: dial, direction, basis)
  text,                          // the story text (variety rule: its length)
  rules: {frames, lexicon, templates},   // the three CSVs, served by /api/world-engine/rules?set=sowhat
  prev                           // the last headline shown on the page, or null (feed rule)
})
```

What the composer computes for each focus (all rules are in the ontology):

| Step | Uses |
|---|---|
| response row | focus, or `story.entry.id` when focus is world and `story.entry.local` |
| peaks per decision | `places[row][d]` → the value with the largest absolute size |
| themes (at most 2), degree words, modal | lexicon `decision`, `theme`, `degree`; `story.certainty.modal` |
| frame + coherence guard | `story.frame` (id, runner_up); spend + buy_new + subscribe + travel peaks |
| WHO contrast (countries only when `entry.place` is country, and the top country is twice the runner-up) | peaks of the lead decision for candidate rows; `rows[].share` (0.5% floor); lexicon `who`, `who_lead`, `ref`, `place`, `audience` |
| ARC | `places[row][lead]`; lexicon `arc` |
| SCALE | `story.scale.tier` and `rank[lead].reach` (world, not local) or the band of the focus lead |
| lead, template, line 2, budgets | ontology section 2; `sowhat_templates.csv` |

## 5. Composer output

```json
{
  "headline": "Loans get cheaper: people open their wallets and invest a bit more.",
  "line2": "Builds, then eases. A minor shift that reaches nearly everyone.",
  "template": "RL-T", "lead": "trigger", "frame": "relief",
  "spans": [
    {"line": 1, "start": 0,  "end": 17, "beat": "trigger"},
    {"line": 1, "start": 26, "end": 66, "beat": "response"},
    {"line": 2, "start": 0,  "end": 19, "beat": "arc"},
    {"line": 2, "start": 20, "end": 63, "beat": "scale"}
  ],
  "beats": [
    {"kind": "trigger",   "icon": "condition", "text": "loans get cheaper", "trace": "trigger choice: borrowing_cost 0.98, runner-up private_debt 0.01; borrowing_cost down: strength 0.996, reported, size notable"},
    {"kind": "certainty", "icon": "now",       "text": "happened", "trace": "weight fact 1.0; gate happened 0.98, announced 0.98, opinion 0.0, forecast 0.0"},
    {"kind": "frame",     "icon": "topic",     "text": "relief", "trace": "frame choice: relief 0.79, runner-up boost 0.19; response sense up (+2.18)"},
    {"kind": "response",  "icon": "spend",     "text": "open their wallets and invest a bit more", "trace": "spending: spend +1.30, buy_new +0.88; money: invest +0.61 (peak pts at World)"},
    {"kind": "arc",       "icon": "next",      "text": "Builds, then eases.", "trace": "spend at World: now +0.97, next +1.30, later +0.72; peak next; keeps 55%"},
    {"kind": "scale",     "icon": "tier2",     "text": "A minor shift that reaches nearly everyone.", "trace": "Size 20.4 (Minor); spend reach 99.4% at Next"},
    {"kind": "who",       "icon": "group",     "text": "Big-city high earners react a bit less than most people.", "trace": "spend: Higher-income, tech-comfortable, big-city +0.80 vs world +1.30 (x0.62)"}
  ],
  "shrink": []
}
```

- `spans` uses character offsets (end exclusive) into `headline` (line 1) or `line2` (line 2). Hovering a span shows that beat's trace. Spans cover only text that a beat filled; template words ("feel the squeeze", "Only") are not spans. The `{Who_lead}` span is the whole filled phrase, and the frame noun inside it is a `frame` span.
- `beats` lists every beat that was computed, including those not shown (like `who` above), so the "How it was made" tab can show what was left out and why.
- Icons use the page's `IC` set. trigger: `condition`. certainty: happened `now`, announced and pending `next`, forecast `eye`, opinion `share`, unclear `dot`. frame: `topic`. response: the icon of the theme's top decision (`ICON_RULES`). arc: jolt `now`, builds `next`, fades and sticks `later`. scale: `tier1` to `tier5` (Negligible to Historic; or band small `tier2`, clear `tier3`, big `tier4`, huge `tier5`). who: `place` for a country or region, `group` for an audience.
- Quiet forms return `headline`, an empty `line2`, `lead: "quiet"`, and beats holding whatever exists (certainty, trigger, response "none" with the largest move in its trace).

## 6. What changes on the page (for the build agent, not done here)
- `paintCard`: replace the three `u.head.textContent = ...` branches with `compose(...)`, and render the spans as `<span data-beat>` with titles. Keep `textContent`; never use innerHTML.
- Retire `joinNice` and the `likelier to` skeleton for events. The offer mode keeps its own line.
- The "How it was made" tab: list `beats` with icon, text and trace.
- Serve the three CSVs (frames, lexicon, templates) next to the existing `map.phrases`.
