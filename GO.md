# GO — session handoff

Written 2026-10-20 (end of a long session). Overwritten at each handoff.

## First reply of the new session
Read this file in full, run `node tools/ledger.mjs board` and `node tools/ledger.mjs score`, skim `.claude/skills/ontology-trainer/SKILL.md`. Then reply in at most 8 lines: (1) the goal, (2) where we are, (3) the next step and its logged forecasts, (4) anything waiting on the user. Do not run anything until the user confirms.

## Rules that bind (CLAUDE.md, memory, ledger)
- Every claim cites a ledger item, a pinned file + command, or an MM3 run id. Predict before each run (tag forecasts [source]/[harness]/[structure]/[model]), score after.
- Caps (D-0012, amends D-0005): every step < 1 h with `timeout`; longer cascades get an independent `systemd-run` guard that kills by verified PID, plus `MemoryMax`; Jev spend cap; bounded queues (an unbounded one was OOM-killed).
- Jev may read article text (D-0008), pinned `jev-1.14.0` (D-0011). MM3: `tools/mm3local` (Clef, = the MCP tool) and `tools/mm3hosted` (Jev); report splits; `mm3 doctor`/log baseURL are unreliable (N-0012).
- Stopping services is blocked for Claude by the safety check: give the user `! ./service.sh stop <name> -y`. Starting is allowed.
- Short replies, bottom line first, plain language; user wants recommendations, not just reports; proof via per-item examples.

## Goal
BitMob: fast CPU classifiers for the World engine's read layers (story type, scope/focus, topic, country, 78 condition keys) from headline + description (D-0009), no GPU at run time, < 100 ms/article (D-0007), quality proven against a jury-labelled test set. Ontology: `exports/world-engine-ontology.yaml`. Method: the new skill `ontology-trainer` (+ human guide `.claude/skills/ontology-trainer/guide/README.md`, `LESSONS.md`).

## Where things stand (ledger ids)
- Labels: Jev one call per story, all questions (F-0041), ~450 stories/min. 10,000 headline+description stories labelled overnight: `data/trainset/night1.jsonl` (F-0048).
- Baselines (CPU, agreement with Jev): story type happened AP 0.975 / announced 0.916; country acc 0.79; topic 0.69; 44 condition keys mean AP 0.45 (e5-small frozen; 8-12 ms/article); per-item proof `data/trainset/night1-examples.md`: keys found 17/17 but 33 false alarms on 20 stories (thresholds untuned) (F-0048).
- Jury pilot, 50 stories (F-0049): id-list output only (0/1 strings broke). Condition overlap Jev-Sonnet 0.41, Jev-Haiku 0.34, Sonnet-Haiku 0.70 (same family); 28 condition yeses only Jev gives; my brief was unequal (Claude told "no passing hints", Jev not). Stricter Jev cut-off makes it worse. Diagnosis: condition DEFINITIONS are the weak point.
- Clef speed: llama.cpp is 1 request at a time by design (N-0016); vLLM 0.30 + alpha-x-ai NVFP4 (`data/models/clef-flash-nvfp4-alpha`, env `models/cygnet-venv`) 31/min, two-step screen v2 64/min with readings = full battery 99/100, anchor vs bf16 16/20 (F-0047, MM3-0481: adopt after a fresh confirmation run). Scripts `newsreader/bitmob/clef_two_step.py`, `clef_nvfp4_test.py`.
- Input length: headline catches ~35-40% of full-text signal, 600 words ~92% (F-0031..F-0033); D-0009 keeps headline+description.
- Forecast record: 58 scored, Brier 0.218, hit 0.58 vs stated 0.60.

## Next step (task T-0011, forecasts R-0064..R-0068 logged)
Skill step 1b on `data/jury/pilot50/` (stories.jsonl, questions.json, jev.jsonl, sonnet-ids.jsonl, haiku-ids.jsonl):
1. Write a codebook entry per condition (definition, counts, does not count, one real example each) INSIDE the question text; same text for every juror.
2. Re-run Jev (script pattern in this session: one systemone call with all questions + topic choice + `C.ask_country_detailed`), Sonnet and Haiku subagents (Read/Write only, output `{"n","yes":[ids],"topic","country"}`), validate ids by script.
3. Measure overlap and per-condition agreement; score R-0064..R-0068. Expected: overlap rises but may stay < 0.7; 50 stories too few per condition (R-0066 p 0.75) -> then a targeted 150-200-story pilot enriched per condition.

## Then (in order)
2. Draft ~10 acceptance criteria per area; MM3 check (both wrappers); user approves.
3. Frozen 2,000-story jury test set (Sonnet + Jev + Clef two-step; Opus investigates splits; user spot-checks ~50).
4. Hour-long targeted rounds (fine-tuned encoder, per-key thresholds, mining for rare keys, regression checks) under D-0012 caps.
5. Two-step Clef confirmation on 1,000 fresh stories.

## Open with the user
- Country list lacks Ireland, Switzerland, Singapore, Denmark (F-0049): ontology gap.
- Engine gate lets non-news move the world; live input filter (D-0010 is training-only); CC-News licence check.
- Services: all default services up (`./service.sh up`, baseline = world, demo, voice, classifier, clef-flash-q4km). Old models' systemd units still enabled at boot (kev-4b, laya, semif, so1, verdict) unless the user disabled them.
