# Call monitor: requirements (v2)

Written after review of the first four mock-ups. Audience: leadership demo, then real users on a live call. Every requirement has a number or a check, and `tools/measure.py` measures the automatable ones.

## Principles

1. **A signal is a level over time, not an event.** Something detected does not flash and vanish. It rises, holds while the person can still act on it, then fades. The user can always answer "what is it, how high, since when, is it going up or down".
2. **People react slowly.** The design budget for a human reaction is 30 seconds. Nothing the user may need to act on leaves the screen sooner, and it stays in the log after it cools.
3. **Everything moves continuously.** No element jumps. New text glides in, the transcript glides up, levels ease, charts scroll with time. Only transform and opacity animate.
4. **The eye has one place to rest.** Transcript is primary. The side panel is secondary: what is happening now (levels, state, timers) and what happened recently (rolling chart, flagged moments).
5. **Nothing is colour-only.** Every colour also has a code, a label or a glyph. Colour is assigned to the watch item and never repainted.
6. **Honest about what is real.** The mock-ups are scripted. Any tag or score is marked MOCK until it comes from a model.

## Definitions

- **Signal**: one watch item (short code, plain-language prompt, colour slot). Max 6 at once; a 7th is refused with a message, never a generated colour.
- **Level**: 0 to 1, what Jev returns as a probability. Displayed smoothed.
- **Act line**: level 0.65, the point at which a signal counts as "high".
- **Fire**: a checkpoint result that puts a signal at or above its prior peak.
- **States**: Live (fired in the last 4 s), Holding (4 to 30 s), Fading (over 30 s, still above 0.2), Quiet.
- **Hold**: after a fire, the level decays at most 25% over 30 s, then falls with a 12 s time constant. The moment card counts down the same 30 s.
- **Sim second**: one second of the call at 1x playback; timers follow the call clock, not the wall clock.

## Measurable outcomes

| # | Requirement | Target | How checked |
|---|---|---|---|
| R1 | Frame pacing during playback (1x and 4x) | p95 frame time at most 20 ms; at most 1% of frames over 33 ms | measure.py |
| R2 | No layout jumps | Cumulative layout shift at most 0.01 over a 45 s run | measure.py (PerformanceObserver) |
| R3 | Smooth glide | Largest single-frame displacement of the transcript at most 12 px at 1x; no frame over 40 px | measure.py (glide hook) |
| R4 | Time to first text | At most 300 ms from Play | measure.py |
| R5 | Hold | Every flagged moment stays visible at least 30 sim seconds (or to the end of the run) | measure.py (flag dwell) |
| R6 | Rolling history | Chart shows at least the last 60 sim seconds, scrolling continuously with the clock | inspection + screenshot |
| R7 | Legible state | Every signal row shows state text and, while at or above the act line, "high for m:ss" | DOM check |
| R8 | Dynamic watch list | Adding an item mid-call appears within one frame, without layout shift and without restarting playback | measure.py adds one and re-reads CLS |
| R9 | No colour-only meaning | Every colour carries a code or label; categorical palette validated with the dataviz validator | validator + inspection |
| R10 | Both themes and phones | Light and dark render; no horizontal scroll at 400 px width | screenshots, scrollWidth |
| R11 | Motion hygiene | Only transform and opacity animate; reduced-motion disables animation | CSS review |
| R12 | Honesty | MOCK banner on every page; no network requests other than fonts | measure.py request count |

## Baseline (v1, before this rework; 45 s at 2x and 20 s at 1x, headless Chromium 1440x900)

Frame pacing was fine (p95 16.7 ms) because the pages are light. The jumpiness was layout: cumulative layout shift 0.104 on the call cockpit, 0.085 on the pipeline lab (20 s), 0.012 on live captions, plus a 30 px single-frame scroll snap on live captions. There was no hold model at all: a flagged phrase was a static tag, with no level, state, age or history.

## Results (v2, headless Chromium 1440x900; 40 s at 1x and 45 s at 4x per page)

| Page | Speed | p95 frame ms | Frames over 33 ms | CLS | Largest glide step | First word | Flags shorter than 30 s | CLS from adding a watch item |
|---|---|---|---|---|---|---|---|---|
| 1 Live captions | 1x / 4x | 16.8 / 16.7 | 0% / 0% | 0.0001 / 0.0008 | 0 / 4.1 px | 113 / 64 ms | none | 0.0 |
| 2 Call cockpit | 1x / 4x | 16.8 / 16.8 | 0% / 0% | 0.0003 / 0.0012 | 0 / 4.9 px | 123 / 61 ms | none | 0.0002 |
| 3 Intake board | 1x / 4x | 16.7 / 16.7 | 0% / 0% | 0.0001 / 0.0001 | 1.6 / 3.9 px | 110 / 57 ms | none | 0.0001 |
| 4 Pipeline lab | 1x / 4x | 16.7 / 16.7 | 0% / 0% | 0 / 0 | 3.4 / 4.0 px | 119 / 67 ms | not applicable | no editor on this page |

All pages: no horizontal scroll at 400 px, zero non-font network requests, no script errors, light and dark render. Palette: first five slots of the dataviz reference palette plus violet as slot six, validated in light and dark (all checks pass; the light-mode contrast warning for aqua, yellow and magenta is covered by the relief rule: every series has a code, a legend entry and a numeric readout).

What these numbers do not show: real-device performance (headless Chromium on a fast machine; the pages are light, so v1 also hit 16.7 ms and the win is layout stability, CLS 0.10 to 0.001), audio, or a person's judgement of feel. R6 and R7 were checked by inspection of screenshots. R5 is verified for up to six flags inside 30 sim seconds; a seventh pushes the oldest below the list with a "+N earlier" count. Page 4 is a comparison view, so hold is shown by its 60-second chart rather than moment cards.

## Out of scope for the mock-ups

Audio capture and playback, speech-to-text, real prompts to Jev, per-scenario window optimisation, saving playbooks. See README for the path to wire these.
