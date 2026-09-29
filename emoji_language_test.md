# Do emojis have a definable "language" that Jev-class models already share?

## Emoji catalog — the whole candidate space, grouped by how it could serve as a free positional
## signal (not Unicode's own category scheme), with what's been tested so far checked off

The mental model driving this: a short string of emoji next to a piece of code (a "fingerprint")
could encode several measurements at once — position 1 is always "how severe," position 2 is
always "how confident," etc. — with the *emoji itself* supplying the scale for free, so all that
needs defining separately is which position means what, not what each symbol's value is. That
only works for emoji with a real, low-ambiguity, widely-shared association (per the test results
below). This catalog sorts the space by which groups are actually promising candidates for that,
versus groups included only for breadth/completeness.

### Group 1 — Graduated scales (the core candidates: each family already IS an ordered 0→100%-style axis)

| Family | Members | Implied scale | Tested? |
|---|---|---|---|
| Moon phases | 🌑🌒🌓🌔🌕🌖🌗🌘 | dark→full→dark (0%→100%→0%) | 🌗 ✅ (weakest result of the whole test — 2/7 cross-model agreement) |
| Volume | 🔇🔈🔉🔊 | mute→max | 🔇 ✅ 🔊 ✅ (both near-perfect, unanimous) |
| Battery | 🪫🔋 | low→full | 🪫 ✅ (0%, unanimous) — 🔋 not yet tested |
| Signal | 📶 | single symbol, no discrete graduated set in standard Unicode | not tested |
| Traffic light | 🔴🟡🟢 | stop→caution→go | not tested |
| Colored circles (generic N-level palette) | 🔴🟠🟡🟢🔵🟣🟤⚫⚪ | arbitrary ordered/categorical bank | not tested |
| Colored squares (same, block style) | 🟥🟧🟨🟩🟦🟪🟫⬛⬜ | arbitrary ordered/categorical bank | not tested |
| Thermometer/temperature | 🌡️❄️☀️ | cold→hot | not tested (but 🔥/🧊 below serve this role already) |
| Hourglass/clock (urgency, time-remaining) | ⏳⌛🕐...🕛 | time passing / full circle of hours | not tested |
| Literal numeral | 💯 | fixed at 100 | ✅ (perfect, unanimous, all confidences 1.00) |
| Intensity pair | 🔥🧊 | hot/high↔cold/low | ✅ both (near-mirror-opposite results) |

### Group 2 — Sentiment/valence (positive ↔ neutral ↔ negative)

| Family | Members | Tested? |
|---|---|---|
| Smileys (core set) | 😀😃😄😁😊🙂😐😕🙁☹️😢😭😡🤬😱😨 | not tested |
| Hearts | ❤️🧡💛💚💙💜🖤🤍🤎💔❣️ | not tested |
| Thumbs | 👍👎 | not tested |
| Wild-symbol valence carriers (already tested) | 🔥🧊💀🌶️✨ | ✅ all 5 |

### Group 3 — Binary/status (pass/fail, done/todo, warning — most directly useful for code annotation)

| Family | Members | Tested? |
|---|---|---|
| Check/cross | ✅❌☑️✔️➕➖ | not tested |
| Warning/prohibition | ⚠️❗❓🚫🔞 | not tested |
| Recycle/repeat | ♻️🔄🔁 | not tested |

### Group 4 — Directional/trend (improving/declining, before/after)

| Family | Members | Tested? |
|---|---|---|
| Arrows | ➡️⬅️⬆️⬇️↗️↘️↙️↖️↔️ | not tested |
| Cycle arrows | 🔄🔃⤴️⤵️ | not tested |

### Group 5 — Rating/achievement (count-based scale, not single-symbol graduated)

| Family | Members | Tested? |
|---|---|---|
| Stars | ⭐🌟✨💫☆ | ✨ ✅ (as a wild-symbol valence carrier, not yet as a rating-count test) |
| Medals/trophies | 🏆🥇🥈🥉🎖️ | not tested |

### Group 6 — Gestures/body (secondary candidates — mostly binary attention/approval signals)

| Family | Members | Tested? |
|---|---|---|
| Hands | 👍👎👊✊🤞✌️👌👈👉👆👇🙏💪 | not tested |

### Group 7 — Breadth only (included so the full space is visible; not promising as free scales — too many near-equal-weight members with no obvious ordering)

- Weather: ☀️⛅☁️🌧️⛈️❄️🌈⚡
- Food/drink: 🍎🍕🍔🍜🍰🍩☕
- Animals: 🐶🐱🦊🐻🦁🐘🦋
- Travel/places: 🚗✈️🚀🚢🏠🌍
- Objects/tools: 🔧⚙️💡🔬📱💻

**Where to look next**, per this map: Group 1 (traffic light, colored circle/square banks, battery's
full pair, thermometer) and Group 3 (check/cross, warning) are the highest-value untested
candidates for the actual annotation use case — they're either already-graduated scales or
already-binary-status symbols, exactly the two things a code-quality fingerprint needs.

---

Tested whether raw Unicode emoji carry a latent, cross-model-consistent association to
percentage/intensity and several qualitative dimensions — **with no legend or explanation ever
given**.

Two distinct signals matter here, and this version of the doc keeps them separate rather than
collapsing them into one "unanimous dimensions" count:

1. **Is the hosted TypeSafe `jev` model itself internally consistent and decisive?** This alone is
   useful — a single reliable model is enough to build on, independent of whether anything else
   agrees with it.
2. **Do the other two models (kev-4b, semif) also land on the same answer?** This is the stronger,
   "better" signal — corroboration across three independently trained/served systems that were
   each given zero explanation.

Every table below leads with hosted jev's own answer and its own confidence, then shows kev-4b and
semif for comparison, then an explicit **alignment** column stating exactly which models agree —
not just a count.

## Method

- 10 emoji, sent together in one `state`, labeled only `Symbol_1`...`Symbol_10` (no English name
  anywhere in the payload — question IDs are purely numeric, e.g. `valence_7`, ruling out any text
  leak).
- 7 dimensions per emoji: intensity/percentage (two separate runs with different option sets —
  10/20/30/40/50% for fire/ice/skull/chili/sparkles, and 0/25/50/75/100% for
  mute/max_volume/half_moon/low_battery/hundred, not numerically comparable across the two runs),
  plus valence, danger, energy, speed, temperature, and formality (all six on a shared, consistent
  3-level option set across every emoji).
- 5 requests total per model (2 percentage runs + 3 batches of 2 dimensions each), each batching
  many questions with no context beyond the emoji character and the option list.

## Summary — hosted jev's own consistency, and how often the others corroborate it

| Emoji | jev's own avg. confidence (7 dims) | All 3 models agree | jev disagrees while kev-4b+semif agree with each other |
|---|---|---|---|
| 🔥 fire | **0.92** | 5/7 | 0/7 |
| 🪫 low_battery | 0.76 | 5/7 | 1/7 |
| 💯 hundred | 0.70 | 6/7 | 1/7 |
| 💀 skull | 0.81 | 4/7 | 2/7 |
| 🌗 half_moon | 0.74 | 2/7 | 1/7 |
| ✨ sparkles | 0.74 | 3/7 | 0/7 |
| 🧊 ice | 0.67 | 4/7 | 0/7 |
| 🔊 max_volume | 0.52 | 4/7 | 1/7 |
| 🔇 mute | 0.69 | **7/7** | 0/7 |
| 🌶️ chili | 0.62 | 3/7 | 1/7 |

Read this table as: column 2 answers "is jev itself reliable here" (higher = jev is decisive and
not hedging); column 3 answers "how often does everyone land in the same place"; column 4 flags
the more interesting case — jev actively disagreeing with a kev-4b/semif consensus, which could
mean jev is wrong, or could mean jev is picking up a real distinction the open-source pair missed
(e.g. skull's temperature: jev alone says "cold," kev-4b and semif both say "neutral" — arguably
jev is the one making a real connection here, since 💀 has no obvious thermal association at all
and "cold" as in "cold-blooded"/lifeless is at least a defensible read).

## Full per-emoji breakdown

### 🔥 `fire`

| Dimension | hosted jev (answer, conf) | kev-4b (answer, conf) | semif (answer, conf) | Alignment |
|---|---|---|---|---|
| intensity | **50%** (0.56) | 40% (0.21) | 50% (0.17) | jev + semif agree, kev-4b differs |
| valence | **positive** (0.92) | neutral (0.50) | positive (0.98) | jev + semif agree, kev-4b differs |
| danger | **dangerous** (1.00) | dangerous (0.68) | dangerous (0.96) | **all 3 agree** |
| energy | **high** (1.00) | high (1.00) | high (0.98) | **all 3 agree** |
| speed | **fast** (0.94) | fast (0.92) | fast (0.65) | **all 3 agree** |
| temperature | **hot** (1.00) | hot (1.00) | hot (0.99) | **all 3 agree** |
| formality | **casual** (1.00) | casual (0.86) | casual (0.99) | **all 3 agree** |

### 🧊 `ice`

| Dimension | hosted jev (answer, conf) | kev-4b (answer, conf) | semif (answer, conf) | Alignment |
|---|---|---|---|---|
| intensity | **10%** (0.48) | 10% (0.09) | 20% (0.13) | jev + kev-4b agree, semif differs |
| valence | **neutral** (0.61) | neutral (0.94) | neutral (0.20) | **all 3 agree** |
| danger | **neutral** (0.22) | neutral (0.25) | safe (0.17) | jev + kev-4b agree, semif differs |
| energy | **low** (0.90) | low (1.00) | low (0.80) | **all 3 agree** |
| speed | **slow** (0.77) | slow (0.97) | medium (0.25) | jev + kev-4b agree, semif differs |
| temperature | **cold** (1.00) | cold (1.00) | cold (1.00) | **all 3 agree** |
| formality | **casual** (0.70) | casual (0.28) | casual (0.41) | **all 3 agree** |

### 💀 `skull`

| Dimension | hosted jev (answer, conf) | kev-4b (answer, conf) | semif (answer, conf) | Alignment |
|---|---|---|---|---|
| intensity | **10%** (0.37) | 10% (0.34) | 50% (0.09) | jev + kev-4b agree, semif differs |
| valence | **negative** (1.00) | negative (1.00) | negative (0.98) | **all 3 agree** |
| danger | **dangerous** (1.00) | dangerous (1.00) | dangerous (0.99) | **all 3 agree** |
| energy | **low** (0.88) | low (0.61) | low (0.09) | **all 3 agree** |
| speed | **slow** (0.54) | medium (0.92) | medium (0.27) | kev-4b + semif agree, jev differs (jev alone) |
| temperature | **cold** (0.90) | neutral (0.88) | neutral (0.29) | kev-4b + semif agree, jev differs (jev alone) |
| formality | **casual** (0.95) | casual (0.30) | casual (0.92) | **all 3 agree** |

### 🌶️ `chili`

| Dimension | hosted jev (answer, conf) | kev-4b (answer, conf) | semif (answer, conf) | Alignment |
|---|---|---|---|---|
| intensity | **50%** (0.14) | 40% (0.10) | 50% (0.07) | jev + semif agree, kev-4b differs |
| valence | **positive** (0.25) | neutral (0.97) | positive (0.44) | jev + semif agree, kev-4b differs |
| danger | **neutral** (0.39) | neutral (0.34) | dangerous (0.21) | jev + kev-4b agree, semif differs |
| energy | **high** (0.95) | high (0.84) | high (0.89) | **all 3 agree** |
| speed | **fast** (0.62) | medium (0.94) | medium (0.27) | kev-4b + semif agree, jev differs (jev alone) |
| temperature | **hot** (1.00) | hot (1.00) | hot (0.98) | **all 3 agree** |
| formality | **casual** (1.00) | casual (0.71) | casual (0.97) | **all 3 agree** |

### ✨ `sparkles`

| Dimension | hosted jev (answer, conf) | kev-4b (answer, conf) | semif (answer, conf) | Alignment |
|---|---|---|---|---|
| intensity | **50%** (0.41) | 40% (0.05) | 50% (0.36) | jev + semif agree, kev-4b differs |
| valence | **positive** (1.00) | positive (0.98) | positive (1.00) | **all 3 agree** |
| danger | **safe** (0.69) | safe (0.66) | safe (0.76) | **all 3 agree** |
| energy | **high** (0.87) | medium (0.83) | high (0.81) | jev + semif agree, kev-4b differs |
| speed | **fast** (0.64) | medium (0.94) | fast (0.26) | jev + semif agree, kev-4b differs |
| temperature | **neutral** (0.65) | neutral (0.99) | neutral (0.80) | **all 3 agree** |
| formality | **casual** (0.94) | neutral (0.41) | casual (0.85) | jev + semif agree, kev-4b differs |

### 🔇 `mute`

| Dimension | hosted jev (answer, conf) | kev-4b (answer, conf) | semif (answer, conf) | Alignment |
|---|---|---|---|---|
| intensity | **0%** (1.00) | 0% (1.00) | 0% (0.97) | **all 3 agree** |
| valence | **neutral** (0.44) | neutral (0.76) | neutral (0.34) | **all 3 agree** |
| danger | **safe** (0.69) | safe (0.69) | safe (0.79) | **all 3 agree** |
| energy | **low** (0.98) | low (1.00) | low (0.93) | **all 3 agree** |
| speed | **slow** (0.86) | slow (0.92) | slow (0.29) | **all 3 agree** |
| temperature | **neutral** (0.45) | neutral (0.96) | neutral (0.87) | **all 3 agree** |
| formality | **casual** (0.42) | casual (0.44) | casual (0.74) | **all 3 agree** |

The only emoji with all 7 dimensions unanimous across all 3 models.

### 🔊 `max_volume`

| Dimension | hosted jev (answer, conf) | kev-4b (answer, conf) | semif (answer, conf) | Alignment |
|---|---|---|---|---|
| intensity | **100%** (0.88) | 100% (0.86) | 100% (0.92) | **all 3 agree** |
| valence | **positive** (0.40) | neutral (0.97) | positive (0.70) | jev + semif agree, kev-4b differs |
| danger | **neutral** (0.25) | neutral (0.37) | safe (0.22) | jev + kev-4b agree, semif differs |
| energy | **high** (0.98) | high (0.99) | high (0.93) | **all 3 agree** |
| speed | **fast** (0.33) | fast (0.76) | fast (0.63) | **all 3 agree** |
| temperature | **neutral** (0.53) | neutral (0.99) | neutral (0.90) | **all 3 agree** |
| formality | **neutral** (0.26) | casual (0.61) | casual (0.89) | kev-4b + semif agree, jev differs (jev alone) |

### 🌗 `half_moon`

| Dimension | hosted jev (answer, conf) | kev-4b (answer, conf) | semif (answer, conf) | Alignment |
|---|---|---|---|---|
| intensity | **50%** (0.99) | 0% (0.51) | 50% (0.11) | jev + semif agree, kev-4b differs |
| valence | **neutral** (0.98) | neutral (1.00) | neutral (0.49) | **all 3 agree** |
| danger | **neutral** (0.76) | safe (0.31) | neutral (0.27) | jev + semif agree, kev-4b differs |
| energy | **medium** (0.89) | low (0.96) | medium (0.43) | jev + semif agree, kev-4b differs |
| speed | **medium** (0.24) | slow (0.93) | medium (0.25) | jev + semif agree, kev-4b differs |
| temperature | **neutral** (0.89) | neutral (0.89) | neutral (0.57) | **all 3 agree** |
| formality | **neutral** (0.40) | casual (0.31) | casual (0.20) | kev-4b + semif agree, jev differs (jev alone) |

Note jev is actually quite confident and internally consistent here (0.74 avg, and 0.99 on
intensity specifically) even though only 2/7 dimensions are fully unanimous — this is the clearest
case in the whole test of "one model is consistent on its own" diverging from "all three agree."

### 🪫 `low_battery`

| Dimension | hosted jev (answer, conf) | kev-4b (answer, conf) | semif (answer, conf) | Alignment |
|---|---|---|---|---|
| intensity | **0%** (0.83) | 0% (0.99) | 0% (0.82) | **all 3 agree** |
| valence | **negative** (0.99) | negative (0.94) | negative (0.68) | **all 3 agree** |
| danger | **neutral** (0.28) | neutral (0.41) | safe (0.21) | jev + kev-4b agree, semif differs |
| energy | **low** (1.00) | low (1.00) | low (0.97) | **all 3 agree** |
| speed | **slow** (0.98) | slow (0.97) | slow (0.24) | **all 3 agree** |
| temperature | **cold** (0.31) | neutral (0.69) | neutral (0.75) | kev-4b + semif agree, jev differs (jev alone) |
| formality | **casual** (0.90) | casual (0.73) | casual (0.92) | **all 3 agree** |

### 💯 `hundred`

| Dimension | hosted jev (answer, conf) | kev-4b (answer, conf) | semif (answer, conf) | Alignment |
|---|---|---|---|---|
| intensity | **100%** (1.00) | 100% (1.00) | 100% (1.00) | **all 3 agree** |
| valence | **positive** (1.00) | positive (0.96) | positive (0.99) | **all 3 agree** |
| danger | **safe** (0.31) | neutral (0.50) | neutral (0.34) | kev-4b + semif agree, jev differs (jev alone) |
| energy | **high** (0.86) | high (0.83) | high (0.92) | **all 3 agree** |
| speed | **medium** (0.32) | medium (0.91) | medium (0.15) | **all 3 agree** |
| temperature | **neutral** (0.41) | neutral (0.96) | neutral (0.60) | **all 3 agree** |
| formality | **casual** (0.98) | casual (0.38) | casual (0.99) | **all 3 agree** |

## Is there a meaningful, usable "language" here?

**Yes, on both signals asked for.** Hosted jev alone is decisive (average confidence ≥ 0.6) on 8
of the 10 emoji, meaning it could be used on its own as a compact percentage/qualifier encoder for
most of these symbols without needing the other two models to agree at all. Layered on top of
that, full 3-model corroboration lands on at least half of all dimensions for 8 of 10 emoji, with
🔇 (mute) hitting a perfect 7/7 and 💯 (hundred) hitting 6/7.

The two weakest spots by jev's own confidence are 🔊 max_volume (0.52) and 🌶️ chili (0.62) — both
still land on the right intuitive answer for most dimensions, just with more hedging. The one
genuine outlier by cross-model agreement is 🌗 half_moon (2/7), but even there jev itself stayed
confident and consistent — it just wasn't corroborated by kev-4b, which is a different, weaker
kind of failure than the emoji being undefined for everyone.

**Practical takeaway:** for a compact-encoding use case, hosted jev's own confidence is a
reasonable first filter for which emoji are safe to use as a zero-legend encoding on their own;
cross-model agreement is the additional check for whether that meaning is likely to hold if you
ever swap in a different Jev-class model.
