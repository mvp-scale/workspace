# Call cockpit: enhancement spec

Builds on `../SPEC.md` (rolling signals, 30 s hold, continuous motion). The original cockpit (`../2-call-cockpit.html`) is unchanged. This spec covers what the three variations in this folder add, and what must be true before any of it is wired to real models.

## 1. What changes

| # | Enhancement | Decision |
|---|---|---|
| E1 | **One highlight per phrase** | A detected phrase is wrapped as a single inline element: one continuous tint, one 2 px underline in the signal colour, with no gaps at word breaks. An optional tiny code label sits above its end (variants A and B; C shows none). |
| E2 | **Message thread** | The conversation reads like SMS: other people left, us right, an avatar per person, a call-clock time on each message. A bubble is sized to its final text (invisible copy) so it never grows or moves while words arrive. |
| E3 | **Per-person analysis** | Every person has their own reading window (last N words of that person only, never the interleaved text). Text inside a person's window is bright, older text is dimmed. Signals belong to a side: THEM (external cues) or US (internal guidance). |
| E4 | **Model selection** | Lives in the Captured-so-far area: SEMIF4 and KEV4B (local, loaded) and JEV113 (hosted). Each shows its typical lag. Choosing the hosted model asks first and states the estimated cost. |
| E5 | **Window selection** | 5, 10, 20 or 40 words per person, and when to score: each sentence or every 5 words. Shows the estimated tokens per check. |
| E6 | **Us versus them** | Two lanes (or one merged strip) of signals. Our side: questions asked, key points made, hedging. A key-points checklist ticks off as points are made. Talk share and pace are computed from the timeline (no model). |
| E7 | **Full page and responsive** | The app fills the viewport: header, watch bar, stage, chart. Panels scroll or clip inside. Under 1000 px it becomes one pane at a time with a bottom tab bar (Talk, Signals, Cues, History). |

Guidance signals for us are separate from the cues about them. Cue cards carry only cues about them; repeat fires of the same signal within 12 s merge into one card with a count. Our own events live in the lanes, the checklist and the chart (dashed lines).

## 2. Variations

| | Signals | Model, window | Coaching (us) | Captured area |
|---|---|---|---|---|
| **A: lanes and tabs** | Two lanes, THEM above US, each with who is speaking | A tab: Captured, Model and window, Coaching | Tab in the same card | Tabbed card under the cue cards |
| **B: strip and popover** | One merged strip, each signal tagged THEM or US | A button on the Captured card opens a popover | Header inside the conversation panel | Card under the cue cards |
| **C: coaching and chips** | Two lanes | Chips always visible at the top of the Captured card | A column beside the cue cards | Card under both, model chips on top |

## 3. Requirements added

| # | Requirement | Target | How checked |
|---|---|---|---|
| R13 | Highlight is one element per phrase | one wrapper per phrase, no per-word highlight | DOM check |
| R14 | Bubbles are stable | CLS at most 0.01 over 45 s at 1440x900 and 1920x1080 (measured: at most 0.0017) | measure.py |
| R15 | Windows are per person | each person's bright text is at most N words of their own | inspection |
| R16 | Model choice changes behaviour visibly | highlight lag follows the chosen model's typical lag; hosted asks first | inspection |
| R17 | Full page | no panel taller than the viewport; no horizontal scroll at 400 px | measure.py |
| R18 | Hold survives the added load | hot cue cards stay visible 30 sim seconds; the design viewport is 1920x1080, and at 1440x900 up to about five hot cards fit before a "+N earlier" count | measure.py |
| R19 | Honest mock | MOCK-UP pill in the header on every page; the only computed measures are talk share and pace | inspection |

## 3b. Results (headless Chromium; 45 s at 2x per viewport)

| Variation | Viewport | p95 frame | CLS | Largest glide step | First word | Cue cards that left the list before 30 s | CLS from adding a watch item |
|---|---|---|---|---|---|---|---|
| A lanes and tabs | 1920x1080 | 16.7 ms | 0.0015 | 7.2 px | 70 ms | none | 0.0014 |
| A lanes and tabs | 1440x900 | 16.8 ms | 0.0017 | 7.2 px | 70 ms | 3 (f2, f4, f5) | 0.0001 |
| B strip and popover | 1920x1080 | 16.7 ms | 0.0002 | 7.2 px | 69 ms | none | 0.0 |
| B strip and popover | 1440x900 | 16.7 ms | 0.0007 | 7.3 px | 63 ms | none | 0.0005 |
| C coaching and chips | 1920x1080 | 16.8 ms | 0.0011 | 7.3 px | 66 ms | none | 0.0009 |
| C coaching and chips | 1440x900 | 16.7 ms | 0.0013 | 7.2 px | 67 ms | 3 (f2, f4, f5) | 0.0001 |

All pages: no horizontal scroll at 400 px, no non-font network requests, no script errors, both themes render. The original pages were re-measured after the shared-engine changes and did not regress (live captions CLS 0.0003, call cockpit 0.0012, no flags short). The 8-hue palette was validated in the reference order in light and dark (all checks pass; light-mode contrast is covered by the relief rule: every series has a code, a legend entry and a numeric readout).

What the numbers say about the variations: at a 1080 px viewport all three hold every cue card for 30 s in the densest stretch of the sales script. At 900 px tall, B still does; A and C run out of room (three early cards leave the list, the "+N earlier" count appears) because their rail gives less height to the cue cards. Choose B, or give A or C more height, if 900 px screens matter. One layout issue found and fixed on the way: the cue card header reused the page header's class name and inherited its padding.

Not verified: real-device performance, audio, and how it feels to a person. The first version of these pages had layout shift 0.024 to 0.026 from bubbles growing leftward as words arrived; sizing each bubble to its final text with an invisible copy removed it (0.0012).

## 4. What is simulated, and what has to be true for the real thing

| Mock-up | Real build needs |
|---|---|
| Scripted transcript, scripted tags, keyword-based custom items | Live speech-to-text with speaker separation, and Jev (or SEMIF4, KEV4B) scoring each person's window |
| Model choice changes only highlight lag, window changes only what is bright | The real models' scores depend on window size and model; this must be measured (below) |
| Talk share and pace | Computed the same way from real word timestamps |
| Us versus them | Two-channel audio gives it for free; a multi-party meeting needs diarization |
| Vocal tone | Not covered: needs an audio model. Jev reads text |

### Speech to text (for later)

Streaming ASR that keeps timestamps and separates speakers is the front end. NVIDIA's NeMo family (Parakeet TDT for transcription; Sortformer for streaming multi-speaker diarization) is the candidate discussed. Neither has been installed or tested here. Before choosing, check on this machine: the model's licence, GPU memory next to the loaded models (KEV4B uses about 9.8 GiB of the 32 GiB card and only about 1.7 GiB is spare), real-time factor, how many speakers it separates at once, and whether partial results are stable enough to score.

### The test that gates the claim

"Per-person windows work" is a hypothesis. The window study over 200 real MentalManip dialogues (manipulation only, dialogue-level labels) found about 20 to 40 words or 2 to 3 turns best. Before building on it: run the same study with per-person windows against whole-dialogue windows on the local models, for each signal that has labels. If per-person windows do not help, say so and keep the simpler design.

## 5. Out of scope

Audio capture, ASR, diarization, vocal tone, saving playbooks, real scoring. The mock-ups do not spend on the hosted model; picking JEV113 in the UI only changes the mock's timing.
