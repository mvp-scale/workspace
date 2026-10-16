# GO — session handoff (overwritten at each handoff, never appended)

Written 2026-10-16. Read this, then CLAUDE.md for anything deeper. Memory (auto-loaded) has the standing rules.

## How to work with me (non-negotiable)
- **Lean communication.** Short answers. Lead with the point. No walls of text.
- **Prove, don't claim.** Before running anything: say what is tested, on which data, and what result means yes / no / inconclusive. Show real inputs and outputs I can check. Check the test is valid before reporting.
- **Validate small → I decide → then integrate.** Never build into the product before I've validated a tiny, transparent example.
- **Local only.** Never publish results to the cloud (no artifacts) unless I ask.
- Never call hosted Jev (costs money) without asking. Kill processes by verified PID, never `pkill -f`.

## Where things stand
- Services: `./service.sh up` (World Engine + console :8100, the only browser port). On demand (top-bar Services panel): voice :8200, classifier = CPU engine :8020, Clef Flash Q4 :8018, Winnow :8091. `./service.sh` shows state.
- Outside API on :8100: `GET /v1/models`, `POST /v1/systemone` (any model by any name; `Atlas CPU`/`cpu` = CPU engine), `POST /v1/audio/transcriptions`. Key: `OUTSIDE_API_KEYS` in `.env`. Details: START.md.
- Secure mode (top bar) masks model names on pages (`demo/mask.json`). It may be ON.
- Branch `world-engine-100-countries`, everything committed, nothing pushed.

## The open thread: does a well-defined state help the CPU classifier?
- **My (owner's) hypothesis:** a properly defined state (STAR-like: situation, task, action → result is the question) gives the small encoder denser vectors, so each question's examples group better. It matters for the CPU classifier and its training data, not for Clef/Jev.
- **What went wrong last session:** tests used a frame that was identical for every item (adds no information by construction), on anger one-liners where the words alone decide the label. Myopic; proved nothing. Lab code was built into the product before validation and has been reverted.
- **Current artifact:** `http://localhost:8100/mockups/star-walkthrough.html` — 7 sentences, every step visible (strings, 384 numbers, similarities, decision). Mechanism only; NOT a fair test.
- **What a fair test needs (agreed):** labels that change with the situation (same words, different right answer), hundreds of examples to see grouping/density, and states shaped like real requests (mm3: goal / situation / task / subject; or conversation detectors). Candidate data: the conversation corpus `data/embed-zs/intake/corpus` (donation-persuasion chats; labels like persuade / commitment / pushes back depend on context).
- **Next step:** propose (lean, ≤5 lines) a fair test design using that kind of data, get my OK, then build it as a small transparent mock-up first.

## Related, parked
- mm3 (github.com/mvp-scale/mm3) self-training: ledger lacks the full request text; proposed change = record the full call (`state`, questions, raw answers) in `askAll` (src/verbs/pay.ts) behind a `training` flag. Encoder choice simulated: e5-small int8 beats static (81% vs 75% answered on CPU at the same 97% accuracy); tiered is worse. Not started.
- Hard-coding audit leftovers: Services panel should read service.yaml; one port registry.
