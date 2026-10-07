# So what v2: backend and composer contract (draft, 2026-10-06)

The split stays as in v1 (`so-what-contract.md`): the backend works out story-level facts once per request; the browser composer builds the statement for any focus with no extra request. v2 needs **four new backend fields** and **no new classifier question**. Rules: `so-what-v2-design.md`. Tests: `sowhat-golden-v2.json` (33 cases).

Everything in v1's `impact.story` stays. `story.version` becomes 2.

---

## 1. Backend: what to add

### 1.1 `impact.if_true` (required for hedged stories)

What would happen if the story were true. Sent when `identify.weight.value < 1` (types forecast, opinion, unclear in `type_weights.csv`), absent otherwise.

How: in `request_event`, run the event branch a second time with every reading's amount divided by the type weight `w_` (equivalently, skip the `x["amount"] *= w_` step), keeping each reading's `mode_weight` and `size_mult` as they are, then pass it through the same `impact()` arithmetic (Now, Next, Later; rank; significance). Mode weights stay because "if the story is true" removes the doubt about the story, not the difference between a reported and an expected change.

```json
"if_true": {
  "type_weight_removed": 0.3,                       // identify.weight.value
  "method": "branch",                               // "branch" (required) or "linear" (fallback: places / weight; must say so)
  "places": {"WORLD:world": {"spend": [-1.43, -1.75, -0.91], "...": [0,0,0]}, "...": {}},   // same shape as impact.places, every row
  "rank": [{"decision": "spend", "reach": 99.4, "persistence": 0.52, "score": 41.0, "tier": "Notable"}],
  "significance": {"score": 38.2, "tier": "Notable", "top_decision": "spend"},
  "significance_rows": {"COUNTRY:can": {"score": 20.1, "tier": "Minor"}}       // as 1.2, on the if-true run
}
```

Cost: one more branch run plus the Next and Later runs for about half of all stories (in the 120-story set, 52 forecasts and opinions plus 8 announced stories at weight 0.3). Measured `impact.ms` today is the right yardstick; expect roughly double impact time for those stories, no classifier calls.

### 1.2 `impact.significance_rows` (required)

The Size score and tier for **every row**, with the same formula as `impact.significance` (`0.7 x top score + 0.3 x mean of top 3`, each decision's score from size, reach, persistence, stakes), except that **reach is measured over that row's own people** (share of the row's people moved by 0.5 points or more at Next). This is what lets a local story read plain or stark at the place it happens instead of "tiny" against the world average, and it lets the Size badge agree with the sentence at every focus.

```json
"significance_rows": {"WORLD:world": {"score": 2.4, "tier": "Negligible"}, "COUNTRY:bra": {"score": 38.0, "tier": "Notable"}, "AUDIENCE:4": {"score": 5.1, "tier": "Negligible"}, "...": {}}
```

Size: 409 rows x about 40 bytes. The world row must equal `impact.significance`.

### 1.3 `story.topic` (required)

The top tagged placement from `identify.placement`, for the no-impact forms ("A crime and policing item with no effect we can measure.").

```json
"topic": {"id": "crime_policing", "name": "Crime and policing", "p": 0.99}      // null when nothing is tagged
```

The composer uses it only when `p >= 0.5` and `id != "other"`.

### 1.4 `story.seed` (optional)

`djb2(title + ". " + description)` as an unsigned integer, so the page and the tests use the same seed even if the page shows a trimmed text. Absent: the composer hashes the text it is given.

### 1.4b `story.place_status` (required)

Whether the story has a place we can name, from the numbers `ask_country` already computes (new `classify.ask_country_detailed`; `ask_country` itself returns what it always did). No threshold or question changed.

```json
"place_status": "unresolved",     // "single" | "worldwide" | "unresolved"
"place_trace": "region step chose Europe & Central Asia (GLOBAL 0.105), country step answered other_here (0.992): a place with no row, or several countries; entry stays the world row",
"place": {"path": "region", "region_choice": "Europe & Central Asia", "global_p": 0.105, "other_here_p": 0.992}
```

- `single`: the entry is a country row.
- `worldwide`: the region step chose GLOBAL (`global_p`), or no country in the chosen part was singled out.
- `unresolved`: the region step did not choose GLOBAL and the country step answered `other_here` (a place with no row such as Malta or Iceland, or a story naming several countries). The entry stays the world row (no place is invented); the composer must not speak for everyone.
- `other_here_p` is the country step's own probability (null when that step did not run); `global_p` is the region step's GLOBAL probability. Present with `story.version` 2 only.

### 1.5 Fixes to existing fields

- `story.frame.id` must be a row of `sowhat2_frames.csv`; `plain` now has one (it was the s106 null).
- `story.trigger.probs` must be the full Q2 distribution (already sent; the contrast partner uses it).
- `identify.readings[]` must keep `amount`, `basis`, `mode` (already sent; the partner test compares amounts).

### 1.6 Not added, and why

- No new classifier question (design section 7). The two existing questions stay as they are.
- No reach field per row beyond `significance_rows`: the composer never prints reach as a number.
- No multiple-of-world field: the composer computes it from `places` (row peak / world peak, same decision).

## 2. Composer input

```js
compose({
  story,            // impact.story (v2: + topic, + seed)
  focus,            // "WORLD:world" | "COUNTRY:can" | "REGION:usa-rural" | "AUDIENCE:4"
  rows,             // read.rows: [{id, label, level, parent, share}]
  places,           // impact.places
  rank,             // impact.rank
  significance_rows,// impact.significance_rows
  if_true,          // impact.if_true or null
  readings,         // identify.readings
  weight,           // identify.weight.value
  text,             // story text (seed fallback)
  seed,             // optional; overrides story.seed and the text hash
  rules: {frames, hooks, templates, lexicon, lexicon_v1},   // sowhat2_frames, sowhat2_hooks, sowhat2_templates, sowhat2_lexicon, sowhat_lexicon (conditions, places, audiences, who bands)
  prev              // last statement shown on the page, or null (feed rule)
})
```

The five CSVs are served next to the v1 ones (`/api/world-engine/rules?set=sowhat2`).

## 3. Composer output

This is golden case G11 (fixture 14, oil spike after tanker attacks in the Gulf), with its real numbers. Beat traces are abbreviated where marked.

```json
{
  "headline": "No small shift: fuel and power costs rise, and about 7 in every 100 people cut spending who otherwise would not.",
  "line2": "Slow to start, stronger later, then easing.",
  "family": "SCALE", "hook": "SC07", "body": "B05", "register": "stark", "frame": "plain",
  "seed": "799990468",
  "spans": [
    {"line": 1, "start": 0,  "end": 14, "beat": "hook"},
    {"line": 1, "start": 16, "end": 41, "beat": "trigger"},
    {"line": 1, "start": 47, "end": 111, "beat": "anchor"},
    {"line": 2, "start": 0,  "end": 43, "beat": "arc"}
  ],
  "beats": [
    {"kind": "trigger",  "icon": "condition", "text": "fuel and power costs rise", "trace": "trigger choice: energy_fuel 0.99, runner-up prices 0.01"},
    {"kind": "certainty","icon": "now",       "text": "happened", "trace": "weight fact 1.0; gate happened ..."},
    {"kind": "frame",    "icon": "topic",     "text": "shift", "trace": "frame choice: squeeze 0.99, runner-up surge 0.005; place unresolved (the Gulf), plain used"},
    {"kind": "register", "icon": "tier4",     "text": "stark", "trace": "World tier Major (score 53.8) -> stark"},
    {"kind": "response", "icon": "spend",     "text": "cut spending", "trace": "spending: spend -6.82, buy_new -3.23, subscribe -2.05 (peak pts at World); theme 1 uses the decision act verb because the anchor is in the headline"},
    {"kind": "anchor",   "icon": "number",    "text": "about 7 in every 100 people cut spending who otherwise would not",
     "value": -6.82, "shown": 7, "rule": "A1", "trace": "A1: spend -6.82 pts at World (peak at Next), vs the no-event control run; shown as 7 (round half up); threshold 2.0"},
    {"kind": "arc",      "icon": "next",      "text": "Slow to start, stronger later, then easing.", "trace": "spend at World: now -4.26, next -6.82, later -3.03; peak next; keeps 44%"},
    {"kind": "contrast", "icon": "condition", "text": null, "trace": "no reported reading of the opposite valence"},
    {"kind": "stake",    "icon": "dot",       "text": null, "trace": "no shown theme with stakes >= 4 and 0.75 pts"},
    {"kind": "turn",     "icon": "later",     "text": null, "trace": "spending leads at Now and at Later"}
  ],
  "picks": [{"slot": "hook", "index": 1, "of": 3}, {"slot": "body", "index": 0, "of": 2}, {"slot": "anchor", "index": 1, "of": 4}, {"slot": "l2_arc", "index": 1, "of": 4}],
  "shrink": []
}
```

- **New beat kinds**: `hook` (the hook's own words, so the hover can say which family and why it led), `anchor` (section 8 of the design; carries `value`, `shown`, `rule`), `contrast` (the partner reading), `stake`, `turn`, `register`, `topic` (no-impact only). Every computed beat is listed, shown or not, with a trace that says why (v1 practice).
- **Spans**: the anchor span covers the whole anchor phrase (number, group, verb, comparison). Template words are not spans. Spans never overlap.
- **picks**: every seeded choice, as index of candidates; lets a test find the first slot where a composer diverges.
- **Quiet output**: `family` is the quiet case (`QUIET_SMALL`, `QUIET_FORECAST`, ...), `hook` null, `body` the form id, `register` null, `line2` empty, no anchor; beats include `response: none` with the largest move in its trace.
- Never null for a valid story: an unknown frame id falls back to `plain`; a story with no picks and `counted` true uses the QUIET forms with the topic.

## 4. Checks the composer runs on itself (and the tests assert)

- At most one figure per statement, no `%`. The figure is "N in every 100" (digit runs [N, 100] where N is the anchor's `shown`), or "1 in every 20" or "1 in every 10" when the value supports it (design 17.2); `anchor.figure` is `{n, unit}`, and the digit runs of the statement are exactly [n, unit]. A multiple (A3) is one digit run, `shown`.
- A loud degree word never sits beside a figure under 5 in 100, a soft one never beside 5 or more (design 17.1); a hushed statement has no figure.
- Headline <= 22 words; line 2 <= 14 words, or <= 16 when the anchor is its only fragment.
- Hushed register: the headline contains a lexicon `soft` word.
- v1 `banned()` patterns (comma lists, "likelier", decimals, calendar time) still pass.
- None of the retired stock phrases appear ("Elsewhere, barely a ripple", "Little changes elsewhere", "A tiny shift that reaches", "Fades slowly", "no decision moves enough to matter").

## 5. Page changes (for the build agent, not done here)

- Load the five CSVs; call the v2 composer; render spans with `textContent`, the anchor span with emphasis.
- The Size badge for a non-world focus or a local story reads `significance_rows[row]`, so it matches the register.
- "How it was made" lists the new beats, including the anchor's rule and threshold and, for a statement with no number, why none passed.


## 6. v2.1 additions to the composer output and input

- `anchor.figure`: `{n, unit}` (unit 100, 20 or 10; null for a multiple). `anchor.kind` is `pts`, `if_true_pts` (hedged) or `multiple`.
- Tables: hooks gain `needs = coherent` (design 17.5); `lexicon_v1` is still sent next to the v2 lexicon.
- The optional `ctx.debug` object receives `reason: "budget"` when the composer returns null for the word budget (it no longer does; the fuzz test asserts so).
- Slots in `picks`: `hook` (row) and `hook:phr` (phrasing) for the IF rows.

- `story.place_status` ("single" | "worldwide" | "unresolved") and `story.place_trace` (the backend adds them): "unresolved" gives family `UNRESOLVED_PLACE` (design 18.4); a missing field is today's behaviour. The anchor beat's `trace` is plain words with the technical line after "Details:" (design 18.2). `register` is `"hedged"` for an unresolved place.
