# BRIDGE: where we are, for the next session

Updated 2026-10-05. NEW top section: 'World engine' (the persona and world-model work, 2026-10-02 to 2026-10-05; read it first for that work). Below it: the image lab and layered method (2026-10-01/02), a chronological log of the persona/world work, then the older voice material (2026-09-25). Read `CLAUDE.md` first — it's the authoritative map of the repo layout, commands, and architecture; this file is only the narrative of *why* things are the way they are and what's still open. Everything described here is local and **nothing from the 2026-10-02 to 2026-10-05 work is committed** (`probes/` and `data/` are not tracked by this repo; `BRIDGE.md` is modified but uncommitted; the repo is **public**, so check before pushing).
Older material (image lab, voice pipeline) was committed locally earlier; its last known state was `main` ahead of `origin` and unpushed, so check `git status` and `git log` before relying on that.

This file was compacted on 2026-09-24: the previous version's long round-by-round history (MMLU
world knowledge, the Decompose/Monte Carlo readability passes, the honesty-audit round, etc.) is
still fully recoverable from `git log` if a specific rationale is ever needed again — it isn't
reproduced here because none of it is load-bearing for what's currently in progress (see "Voice
pipeline" below).

## World engine (2026-10-02 to 2026-10-05): read this first for the persona and world work

**The idea, in the owner's terms.** A "world engine" is a simulation of a whole world audience that runs on arithmetic, not AI agents. Give it anything, large (an event) or small (an offer, a message), and it shows how that thing was identified, how it spreads through every layer (world, country, region, audience, person), and which **attractors** (factors pulling toward) and **detractors** (factors pushing away) drive each decision, at any layer you zoom to. It is built as a five-stage loop: **Collect, Identify, Propagate, Decide, Read**. It is simulated, and it gets more accurate as real data is collected at each stage. The comparison point is MiroFish (LLM agents, AGPL-3.0, no published accuracy); ours is the numeric version.

**How the owner wants me to work (feedback given this session; also saved in memory).**
- Plain language. Define every term on first use ("item", "components", "logit" were all flagged). Say what each number is measured *against* ("compared to what?"). Lead with the meaning, then the evidence. No jargon walls.
- **No made-up output.** Simulate realistic *inputs* at the start; everything downstream must be derived by structured, inspectable rules. If the input is refined the system works better; if the decision criteria are refined the decisions work better.
- **Attractor/detractor language**, measurable and traceable like stock-ticker lines (state, rule weight, push in points, why). Prose is not acceptable as the result.
- Whole-world view with zoom across layers; perspective is a control, not a separate page.
- UX: one clean ask, no page jumping, results in place, tell a story (three headline numbers, then what pulls up and down), details on hover or in a drawer, a slim professional stepper, no redundant pages. A poor first impression destroys trust.
- Primary sources, tagged verified or from-memory. The owner tests for sycophancy (asserting wrong details). Check the text before agreeing; do not guess names.
- Do not commit unless asked. Do not start/stop GPU services unless nothing runs on them. Never `pkill -f` a pattern that appears in my own command (it killed my shell twice). Port 8110 belongs to an old static mock-up server that is not ours.

**What exists (all under `probes/world-engine/` unless noted).**
- Page: `/worldengine` (`demo/worldengine.html`; proxy routes in `demo/server.py`; nav entry in `demo/static/app.js`). `/personalab` and `/worldlab` redirect here; their files and `demo/persona_api.py` remain, unlinked.
- Engine service (port 8112, started by hand): `world_service2.py`. Start: `cd /workspace/probes/world-engine && nohup /workspace/kev/.venv/bin/python world_service2.py > /workspace/logs/world-service2.log 2>&1 &`. Stop: `kill $(ss -ltnpH | grep ':8112 ' | grep -oP 'pid=\K[0-9]+')`. It needs Winnow on :8091. It is running now (started 2026-10-04). After editing `server.py` run `./start.sh restart` from `/workspace`.
- Inputs (simulated at the start): `data/countries.csv` (8 countries; the US row's dial starts come from real public indices in `baseline.json`; all other values are illustrative and mine), `data/segment_exposure.csv`, `data/factors.csv`, `ledger/` (evidence, measurements, clusters from 27 real NPR RSS items), `../persona/rules/*.csv` (dials, elements, grid, decisions, weights, attribute questions).
- Code: `world_pop.py` (100,000 people, 12,500 per country, weighted), `engine2.py` (WORLD > COUNTRY > REGION nodes, channels with gain, lag, gate, slant, seeded noise), `engine.py` (single-country engine, rules loader, the `Audience` take-up model), `classify.py` (local classifier: 144 yes/no questions per story plus a typed country choice question; ~1.3 s per story), `intake.py` (RSS), `cluster_events.py` (duplicate stories merged, run in `/workspace/models/embed-venv`), `audience.py` and `spec/audience.md` (typed audience request/response contract), `analysis/prd-review.md` (review of the ChatGPT PRD kept in `inputs/`), `README.md` (run order, known problems).
- The five stages in the service: Collect (news ledger, indices, request) > Identify (classifier reads the request; typed choice decides event vs offer and which country) > Propagate (event enters at a country or the world, channels carry it to regions; compared with a control run with no event, noise off) > Decide (event: 8 state decisions from person states; offer: take-up from 10 person factors x 10 offer properties, a ridge model fitted on 39 ideas x 400 people) > Read (heat map across world, countries, regions and 8 cross-country audiences found by clustering; `/drill` returns the attractor/detractor ledger for any cell).
- Persona work before the engine, in `probes/persona/`: `persona-profile-standard.md` (layers, Engine v0 spec and pre-registered checks), `model-v2.md` (five levels, 10x10 grids, one-layer cascade, channel distortion), `ontology-v1.md` (flagged by the owner as a patchwork of unrelated frameworks), `world-model-v1.md`, `rules/` plus `build_rules.py`/`rules.py` (the single-source rules tables and their checker), offline pilots with pre-registered pass lines (`EMBED-PREREG.md`, `ITEMS-PREREG.md`, `NEWS-PREREG.md`).

**Numbers worth keeping.**
- Speed: single-country engine, effective state plus 8 decisions for 100,000 people 49 ms, 500,000 people 290 ms (CPU). A GPU port of the same arithmetic: 0.4 ms per tick at 100,000 to 1,000,000 people, 7.7 ms at 10,000,000 (about 1.7 GB of the 13.5 GB free); CPU at 1,000,000 was 998 ms per tick. A world-engine request takes about 1.4 s (event) to 6 s (offer).
- Persona measurement tests (planted-truth, one run): ~6 yes/no questions per trait are enough (10 gave no more); raw probabilities pile up at 0 and 1 (65 to 73% in the tails), so use logit then z-score; tech comfort is the weakest trait (0.75 against the hidden truth); question consistency (0.95 to 0.99) is not validity. Text embeddings of persona text added no depth beyond the named layers and their gain was fragile (it changed sign across PCA sizes); embedding the *idea* text placed new ideas about as well as 10 LLM-read demands.
- Headline classifier: on 100 headlines I wrote myself it failed 3 of 7 pre-set lines (directed recall 75%, ambiguous 50%, time 1.27 s); irrelevant and opinion items never moved a dial. On real NPR items it misses and mis-reads some (e.g. 'oil supply cut' registered only as prices; a university president's statement read as trust up).
- Audience model caveats: 17 of the 39 training ideas are variants of one product; the app requirement and the ID photo always appeared together, so their separate effects cannot be told apart; labels are language-model answers about generated people, not real people.

**Verified external facts (checked in a source this session) vs from memory.** Verified (search results or fetched pages; several via vendor or summary text): OECD Better Life Index lists 11 dimensions; DPSIR (EEA, 1999, from OECD Pressure-State-Response 1993); CAMEO/GDELT actor-action-actor events with a -10..+10 Goldstein scale and nine extra domains (GDELT Cloud docs); DMN 1.5 (Aug 2024), SOSA/SSN, PROV-O; SQL:2016 row pattern recognition (`MATCH_RECOGNIZE`, Oracle 12c, Flink); cross-impact analysis (Gordon and Helmer 1966); Friedkin-Johnsen and Granovetter threshold models; social amplification of risk (Kasperson 1988), gatekeeping, two-step flow; JSON Schema 2020-12, MCP 2026-07-28 spec, A2A under the Linux Foundation; streaming databases (RisingWave Apache-2.0, Proton Apache-2.0, Feldera MIT, pg_ivm, TimescaleDB, ksqlDB under the non-OSI Confluent Community Licence, Materialize BSL per a competitor's blog); EsperTech/Esper (GPL v2, EPL); NDlib and PySD exist (licences not found); Model2Vec potion-base-8M (MIT, 256 dims, 30.2 MB); Nemotron-Personas-USA (CC-BY-4.0, 1M rows, mostly text); Census ACS PUMS (free, real person records, includes income and household size); MiroFish (AGPL-3.0, LLM agents on OASIS; OASIS paper: 5 A100s for 100,000 users x 10 steps took two days). From a research-agent summary, not opened by me: the ConsumerSim paper (arXiv 2606.30395: real microdata personas, GPT-4o salience step, persistence lambda 0.4/0.6/0.7, ablations) and the Maier et al. synthetic-consumer paper (arXiv 2510.08338). Real-world series values (unemployment 4.2%, 30-year mortgage 7.28%, regular gasoline $4.465, consumer sentiment 51.7, CPI 334.131) were read through a web-fetch tool summary on 2026-10-04; unemployment and mortgage agree with NPR stories; the tool's 'a year earlier' values looked wrong and were not used. Python could not reach FRED from this sandbox.

**Known gaps, most serious first (owner asked for an honest list).**
1. Nothing is validated against real people or outcomes; people are generated, labels are model answers, strengths are guesses (the simulation reviewer measured 93% of the uncertainty in two guessed numbers). The first real test should be a backtest against a consumer-confidence series with world inputs fed from published monthly series (the ConsumerSim precedent), against baselines.
2. Offer reading only handles product-like offers (10 fixed properties); it cannot yet read an article or message as the thing being asked about; and the take-up model is US-style people stretched to other countries.
3. The world barely moves product opinions (about 2 points for the example); no link between an item's topic and the matching dial.
4. Levels are thin: no actors or level-specific decisions; channel slant is zero (the 'political element of each level' is built in but not exercised); regions differ by small seeded gains; events do not spill between countries except via the world node.
5. One real decision (take-up); eight state decisions are hand-set; stage thresholds (calm/building/imminent) were far too low and are not used in the new page.
6. People are stateless (no savings or stress that accumulates, no feedback from decisions, no peer influence, no time horizon); the classifier misses and has no number extraction.
7. Rules are not editable in the page; mobile layout unchecked; popover only seen loading.

**Open decisions and the next steps I proposed.**
- Editable rules in the page (change a weight in the decision matrix or a country's start value and watch the map redraw): proposed, not answered.
- Replace the hand-weighted demographics with real census microdata (ACS PUMS for the US; licence and weights not yet read) and replace illustrative country values with real indices per country.
- Real-data backtest (above); level-specific agendas and decisions; spillover between countries; state variables with stocks; fix classifier gaps (energy dial, numbers in text); widen the offer reading to articles and messages (links the item to the dial it concerns).
- Political alignment as a persona element was left out pending the owner's decision (sensitive).
- The ChatGPT PRD review proposed three decisions that were never answered: store 10 states and derive the 10x10 view (I recommended yes), map our concrete variables up to the PRD's ten (yes), one-edge propagation on a graph (yes). The page follows the recommendations.

**Runtime state (2026-10-05).** Console on :8100 (restarted 2026-10-04 and again after the last edit), Winnow-12B on :8091 (about 15 GB), voice server on :8200, world engine service on :8112 (started by hand). The old world-lab service on :8111 was stopped. `models/embed-venv` holds model2vec and scikit-learn. Large outputs live in `data/persona-lab/` (git-ignored): `offline.json` (39 ideas x 400 people, the take-up training labels), `items.json`, `news.json`, `news_walk.json`, `pilot.jsonl`.

## Persona and world engine work: detailed log (chronological; the summary is above)

## Image lab and the layered method (2026-10-01 to 2026-10-02): read this first for the image work

**What exists.** `/imagelab` (`demo/imagelab.html`, `demo/imagelab_api.py`) is the Scenario lab's layout for image tasks, scored on Winnow-12B (llama.cpp `winnow-server`, `:8091`, Q8_0, mmproj for images). 45 tasks in 13 areas; 44 built with 25 images each, answers in `data/image-lab/runs/winnow/`, images in `data/image-lab/images/` (git-ignored; many sources are local-use-only licences). `probes/images/` holds the builders, `validate.py`, `STATUS.md`, `HANDOFF.md` (rules, 30 GB source budget) and the per-task notes. Run the model with `run_winnow.py [task]`. A Medical and dental area (t40 to t48, t49 roof hail is blocked: Roboflow needs an account) carries a "research benchmark only, not for clinical use" banner.

**Known weak spots in the 25-image tasks.** t10 uses CarDD through a mirror although the owner asks for prior consent by email (decide: get consent or drop). t09 negatives are parts-only photos, so its 48% is partly label noise. t48 holds skin conditions, not wounds (no usable wound data). t44 relies on a Turkish label word (`çürük` = caries, confirmed). Only 25 images per task: intervals are wide, and a 25-image chest set read 76% where 100 images read 64%.

**Question-wording audit (TypeSafe's own guidance, docs.typesafe.ai).** Atomic, narrow, positive-polarity questions; contrastive option descriptions (what / not_for / examples); an "other / none" option; Score for ordinal answers; send questions about one state together (they are evaluated independently, checked: batching changes an answer by at most 0.02). We were off on several points: 29 of 30 pick-one tasks send option names with no descriptions, 6 of 14 yes/no tasks carry criteria written in dataset language, only 4 pick-one tasks have a none option, ordinal tasks use Choice. Fixing the wording and re-measuring has NOT been done.

**Consistency angles** (`consistency.py`, results `winnow-consistency/`, shown in the lab): the same fact asked five ways. Useful as a stress test, but re-asking the same broad question adds almost nothing as a combined answer (`layers.py`: mean accuracy 73.4% to 73.9%). The "asked backwards" angle breaks TypeSafe's polarity rule; it is a test, not a method.

**The layered method, three versions, all on pilot sets of 48 to 100 images** (`pilots/*.jsonl`, images in `data/image-lab/pilot/`):
1. `cascade.py` (specs in `cascades/*.json`): gate, characteristics, discriminators, votes not averages.
2. `cascade2.py` (`cascades/v2/`): 100-question budget (gate 10, characteristics 20, discriminators 30, deep dive 25, backtrack 15), stops at consensus. Gate test (`gate_test.py`): stopped 36 of 36 off-topic images per task, including other radiograph types; wrongly stopped 0 to 10% of valid images. More budget added cost, not accuracy. Carrying facts in the state made no difference.
3. `cascade3.py` (`ontology_check.py`, `ONTOLOGY-SCHEMA.md`, `cascades/v3/*.json`): predefined families of finding (8 to 14 per task, up to 3 levels, 100 to 147 questions in the tree), broad pool first, then depth into families that look detectable. Order of questions is stored, so accuracy is readable at any number of questions. This is the user's design and the current one. Results land in the lab (`winnow-cascade3/summary.json`, regenerate with `cascade3.py export`).

**What we learned (the consensus view of the family cascade).**
- **The gate works** and is cheap (10 questions).
- **Observations carry information.** Families are detected well where a dataset column lets us score them (AUC: bone body part 1.00, chest haze 0.86 and opacity 0.84, endoscopy protruding growth 0.88, brain focal mass 0.85, dental impacted teeth 0.79). Skin and dental features are not detectable by this model.
- **Hand-written family votes beat the single question on chest only** (64% to 83% after the broad pool, 91% right on 32% handled by consensus). Where the single question already works (retina 81%, endoscopy 69%, brain 64%) the votes lose to it. The weak link is the hand-written family-to-class mapping.
- **A fitted combination of family scores (5-fold cross-validated on the same 100 images) reaches** chest 80%, retina 85%, endoscopy 80%, pathology 76%, bone 66%, brain 62%, skin 46%, dental 48%, against single-question 64/81/69/64/61/64/37/60. One sample, not a held-out test.
- **Depth past the broad pool adds nothing** (chest peaks at 50 questions, 77% at 100).
- **Consensus must be validated before trusted**: on skin, v2 consensus fired on 79% of images and was right on 30%.
- Confounds: brain "no tumour" comes from a different source than the tumour classes (23 of 25 are RGB); retina, chest and pathology sets are widely used and may be in training data. All ontologies are drafts needing clinician review.

**Value work (mostly inconclusive).** `VALUE-TRIAGE.md`, `VALUE-METRICS.md` (five measurable metrics: cost per case, expert hours, routine first-pass share, annual volume, cost of a miss), `RECON-PLAN.md` / `RECON-REPORT.md`, `DEEP-RESEARCH-PROMPT.md` (50 domains, qualification cards for datasets). Seven agents looked for $5,000-plus expert image workflows: public per-case prices were rarely findable, and Haiku reports contained wrong facts (CarDD "no-damage class", RICO as human-labelled). Treat every dollar figure there as unverified.

**Open items, in the order I would take them.**
1. Fit the family combination on one sample and score it on a second held-out sample per medical task; add a best stopping point per task.
2. Re-test the weakest tasks with TypeSafe-style wording (descriptions, none option, Score for ordinal), before building more layers on top.
3. Extend the ontology method to the non-medical tasks (reading, counting and ordinal tasks need ladders and per-option checks, not feature votes).
4. Decide t10 (CarDD consent) and t49. Turn the builders' column-derived angle questions into runs. Add a Value view to the lab. Have clinicians review the ontologies.

**Runtime state (2026-10-02).** GPU: Winnow-12B (about 15 GB) and the NeMo voice pipeline (`voice/server.py`, `:8200`, about 4 GB) are loaded; the classifier lineup (kev-4b, semif, so1, laya, verdict) is down. Demo console: `./start.sh restart` from `/workspace` (pid file and log in `logs/`); restart it after editing `demo/server.py` or `demo/imagelab_api.py` (page HTML is read from disk). Two Cloudflare tunnels forward `:8100` and `:8200`. Git: all of this is committed (HEAD `b7aa180`), local `main` matched `origin/main` at the last check; no third-party images are in the repo.

### Persona lab feasibility pilot (2026-10-02)

`probes/persona/pilot.py` + `analyze.py`, results `data/persona-lab/pilot.jsonl`. 100 sampled personas (age, household, work, income, tech comfort, caregiver, priority; no link to any product) x 4 fixed products, 12 typed questions per call on Winnow (404 calls, 44 s, 0 errors). Expectations were written before the run. Findings: (1) persona matters: no-persona baseline vs persona spread is large (Splitly sd 0.44); (2) universal 0.90 vs bad 0.03, passes; (3) CareCircle caregivers - non-caregivers +0.55 (CI 0.40 to 0.70) and old - young +0.48, passes; (4) Splitly young - old = -0.02 (CI -0.25 to 0.19), the pre-written age expectation FAILED. Exploratory, after seeing results: Splitly tracks household (housemates 0.85, lives alone 0.01) and tech comfort (avoids new tech 0.02), i.e. it reads the product's real requirements, not age. Caveats: "avoids new technology" at 0.02 looks like a stereotype; persona scores correlate positively with the bad product (0.2 to 0.4), a mild yes/no-sayer trait; one seed, one wording, 4 products, no real-people ground truth yet. Frustration/delight lanes give plausible, mostly "relevance"-driven answers.

### Persona pipeline offline test (2026-10-02, second pilot)

`probes/persona/personas.py` (seeded in-memory generator, `gen(seed)`; 10,000 seeds give 80 cohorts of age band x area x income, 71 with 30 or more) and `offline.py` (`collect`, `collect2`, `report`; results in `data/persona-lab/offline.json`; expectations E2 to E5 are pre-registered in its docstring). 400 personas, 20 ideas (8 lever combinations of Neighbour Loop, 9 targeting variants, 2 held-out targeted products), about 12,000 model calls. Persona extractor: 6 traits plus aspiration and worldview as typed questions; idea extractor: 10 yes/no demands. Results: extractor vs hidden latent rho 0.61 to 0.93 (tech weakest, 0.61); two wordings agree 0.82 to 0.96 except social 0.37 (FAIL); aspiration and worldview 100% (too easy: the profile states them). Idea extractor tracks levers exactly (price 1.00 vs 0.00, app 1.00 vs 0.01). Direct decisions pass every pre-registered effect (price drop 0.28 for price-sensitive vs 0.02; access drop 0.45 vs 0.07; Nightfall young city 0.40 vs 60+ rural 0.01; Gardenway 60+ rural 0.96 vs young city 0.05). Surrogate (ridge on extracted numbers x idea numbers): held-out personas r 0.76 to 0.80, per-persona lever effect r 0.66 to 0.79 (pass, usable for a live lever slider inside a trained idea family); held-out new products FAIL (r 0.06 to 0.22). Exploratory fix, no model calls: adding demographics (age, area, retired) to the persona vector lifts that to r 0.36 / 0.52 (still below 0.5 for Nightfall), and the demographic extractor itself is untested. Caveats: profile text states beliefs outright, so extractor scores are an upper bound; the generator and the questions were written by us. Direct scoring of 10,000 personas is about 10 minutes per idea (about 16 calls/s), so the surrogate is only needed for live sliders.

**Persona lab mock-up (built 2026-10-02):** `/personalab` (`demo/personalab.html`, `demo/persona_api.py`, routes in `server.py`, nav entry in `app.js`). Seed to persona (checked by regenerating), persona and idea extractors, 100/200/400-persona heat map with a change-vs-previous-run view, cohort shares from 10,000 seeds. Local Winnow only (:8091), in-memory cache, nothing stored. Mock-up: not yet checked against real people; surrogate not wired in (every cell is a direct model call, about 16 per second). Demo server was restarted to load it.

**Embedding litmus test (2026-10-02):** `probes/persona/embed_test.py`, pre-registration and result in `probes/persona/EMBED-PREREG.md`. Model2Vec potion-base-8M (MIT, 256 dims, 30.2 MB; separate venv `models/embed-venv`; no JS port found, Python package used). 20 varied ideas scored by Winnow on the 400 personas. Raw cosine similarity predicts nothing (within-idea r +0.05). Persona-text embeddings carry some persona signal (within-idea r +0.29 vs named layers +0.51) and add nothing on top of the named layers; embedding the IDEA text places new ideas about as well as LLM-read demands (pooled r +0.59 vs +0.62). T2 and T4 failed as pre-registered; the pre-registered pooled-r metric was flawed (dominated by idea-level differences). Conclusion: keep named layers as the core; consider idea-text embeddings as a cheap new-idea fallback.

**Reliability tests (2026-10-02):** `probes/persona/ITEMS-PREREG.md` (10 items per trait, 400 personas) and the PCA-size sweep in `EMBED-PREREG.md`. Raw P(yes) is saturated (65 to 73% in the tails), so use logit then z-score. 10 items per trait give alpha 0.95 to 0.99 and rho 0.85 to 0.93 vs hidden trait except tech 0.75 (text renders traits at 3 levels only); 6 items are enough. The embedding result is fragile: the k=8 gain over named layers vanishes at k=4, 16, 32 (k=32 collapses to negative r). Rule going forward: any persona number is a multi-item, logit-z-scored measure with a disagreement flag, never a single question.

**Engine v0 toy (2026-10-02):** spec + pre-registered checks E1 to E7 at the end of `probes/persona/persona-profile-standard.md`; code `probes/persona/engine.py` (numpy only, no GPU, no model calls). 10 world dials (start at 1, decay to 1), per-persona perception, 8 persona elements, 8 decision gates. 100,000 personas x 1,000 ticks in 39 s (39 ms/tick). E1 to E6 pass (E2 and the single-shock E6 are trivially true; with three simultaneous shocks the single-dial effects add up to within 0.8%). All checks test the wiring, not whether people behave this way: every strength is our guess. E7: redrawing the strengths by x0.5 to x1.5 keeps the sign but moves the size of the prices effect on 'subscribe' between -8.8% and -20.5% (nominal -13.9%). Next: validate against real data (backtest), add personality flair and persona-to-persona exposure, wire the classifier as the intake that turns text into dial changes.

**Real-news walkthrough (2026-10-02):** `probes/persona/world-model-v1.md` (9 content dials with 3 named attributes per direction, 2 yes/no questions each, plus the 10 x 10 grid persona element x dial, 26 of 100 cells non-zero, all guesses), `world_model.py`, `news_walk.py`, answers in `data/persona-lab/news_walk.json`. The earlier 100-headline test used headlines I wrote myself (it tested the mechanism only; 3 of 7 pre-set lines failed). CNN (HTTP 451) and the BBC feed refused this fetcher and were not worked around; NPR's public RSS worked. Five real items run: findings are four design faults: (1) attributes are alternative kinds of evidence, not repeats, so the 2-of-3 rule missed the clearest story (the jobs report), a one-attribute rule catches it (exploratory); (2) no region: a story about Israel moved the US safety dial; (3) no date: a diesel explainer about a 2004 shift counted as a price rise today; (4) size rule is a placeholder and numbers inside stories (29,000 jobs, 4.2%) are unused because yes/no questions cannot extract numbers. Next: regions, dates, one-attribute rule, a number-extraction step, re-run on a fresh batch of real items.

**Five-expert review of the grid (2026-10-02; measurement, decision science, public opinion, simulation structure, red team; mostly from memory, few primary sources opened).** Agreement: the persona side lacks money and life situation (cash buffer, income steadiness, debt, life stage, rent/own, habit/inertia, loss aversion, time preference; moving, changing work and spend-or-save cannot be modelled); the dial side lacks housing, war/terror apart from crime, inequality/fairness, polarisation, climate/energy, immigration, general economy, government as a problem; optimism, trust and safety elements are near-copies of their dials (do not reuse questions); 4 to 6 well-spread questions per element, not 10 everywhere (our 'consistency' is one model agreeing with itself, only match to planted truth counts); dial structure mixes repeats (2 questions per attribute) with alternative evidence (3 attributes), so classify the event first, then score each attribute from 3 differently-angled questions and combine with weights calibrated on 100+ hand-labelled headlines. Engine: multiplicative grid is equivalent to additive log-linear (defensible); the simulation reviewer measured 93% of the uncertainty in two guessed numbers (prices->price attention 70%, subscribe<-price weight 23%; effect range -6.1% to -23.5%); strengths and decision weights are confounded (only their product is identifiable); engine.py has 16 non-zero of 80 cells (8 elements) while world_model.py defines 26 of 100 (10 elements): not yet unified. Missing structure: dial-to-dial links, fast/medium/slow time layers, per-cohort strengths with Monte Carlo ranges, regional dials, stocks (savings). Backtest on about 5 to 8 real past shocks is the main gap. Real series named (verified exist): Michigan sentiment on FRED, Gallup most-important-problem, Eurobarometer, Edelman, Ipsos What Worries the World, Fed SHED, BLS CE.

**World-engine slice (2026-10-04):** `probes/world-engine/` (README lists run order and known problems). ChatGPT PRD reviewed in `analysis/prd-review.md` (adopt: derived 10x10 view over stored states, edge channels, decision x state matrix, coefficient origin tags, scenario branches; differ: concrete variables mapped up, persons as arrays, node agendas, real-series backtest). Runnable: RSS (NPR) -> local classifier -> events -> world/country/region/segment state -> 100k to 500k people -> decisions -> audience opinion -> scenario branch. 500,000 people: effective state plus 8 decisions in 290 ms; 100,000 in 49 ms. Deterministic by seed; noise changes the result. Weak points: classifier errors, decision stage thresholds too low (everything 'imminent'), slant not exercised, audience classifier extrapolates, no real-data check.

**Audience spec (2026-10-04):** `probes/world-engine/spec/audience.md` and `audience.py`: a classifier-shaped request (state, typed questions noul/choice/rank, as_of, nodes) answered at five levels from our own world state and population, with percentile among 39 known ideas, levels_above_typical, world_effect, extrapolation flag and a replayable snapshot. Only the take-up decision exists (ridge fitted on language-model answers about generated people); world and country are the same roll-up in v0; example item was in the fitting set. Open: which decisions to register, how 'clears' is defined, level-specific decisions.

**World lab mock-up (2026-10-04):** page `/worldlab` (demo/worldlab.html, proxy routes in demo/server.py, engine service probes/world-engine/world_service.py on :8111, started by hand; README in probes/world-engine has start/stop). Starting world from public indices (baseline.json: unemployment 4.2%, 30-year mortgage 7.28%, gasoline $4.465, consumer sentiment 51.7; unemployment and mortgage cross-checked against NPR stories; reference levels are assumptions) plus 19 events from the NPR feed; add-a-headline box reads typed headlines with the local classifier; ask box gives take-up by age x income, blockers split into fix-the-offer / change-their-mind / wait-for-the-world, dials to watch, timeline. 50,000 people, an ask takes about 6 s. Still true: people simulated, model fitted on language-model answers, world effect on opinions small (about -2 points for the example), nothing checked against real people.

**World lab rebuilt audience-first (2026-10-04):** owner feedback: the focus was a yes/no; it should be the audience and what drives support. `/worldlab` now shows 8 segments (clustered on beliefs, habits and life situation together), each with a five-level support spread, pulls-toward and pushes-away drivers with points, what would move them (offer, belief, world) and a segment x lever matrix; world and news moved below as context. Drivers are exact on the logit scale from the fitted take-up model; segments are model-made, not real groups; app and ID photo effects are confounded in the training ideas.

**World engine page (2026-10-04, replaces World lab in the nav):** owner feedback: show the whole world, not one audience; attractors and detractors as measurable traceable factors; a five-stage loop; inputs simulated at the start, everything else derived by rules. Built: `/worldengine` (strip of five stages with data-status tags and loops; Collect, Identify, Propagate, Decide, Read panels; heat map world > countries > regions plus cross-country audiences; click a cell for the ledger of state, rule weight, push, why; a table of where better data sharpens each stage). New files in probes/world-engine: data/countries.csv, data/segment_exposure.csv, data/factors.csv, world_pop.py (100,000 people, 8 countries), engine2.py, world_service2.py (port 8112). Classifier now names the country of a story with a typed choice question. Event mode compares against a control run so only the event differs. Open: rules are not editable in the page; spillover between countries; offer model extrapolated beyond US-style people; no backtest; classifier misses.

**World engine UX rebuild (2026-10-04):** owner review: redundancy (persona lab, world lab, world engine), unpolished stage strip taking a third of the screen, no clean ask, page jumped on click, data dumped without a story. Now one page `/worldengine`: pinned ask bar, auto event-or-offer detection, slim stepper with hover explanations, in-place results, three headline numbers plus pulls/pushes, perspective navigator (tree/countries/regions/audiences), tabs and a Data & rules drawer. /personalab and /worldlab redirect; old service on :8111 stopped. Not yet done: editable rules in the page, mobile check, spillover between countries.

## START HERE: priority for the next session

**Status 2026-09-25 (latest, read this first):** the swap is DONE: `/flow` (`demo/flow.html`) is the new page and the original lives at `/flow-classic` (`demo/flow-classic.html`; `/flow-lab-final` is an alias). The new page is the old `flow.html` plus Live audio, Levels, Counters, detector packs, AI-drafted detectors, voice lanes and Jev-assisted coaching. **Next**: (1) a paid check of the whole loop on `data/audio/nanobaiter-5min.m4a` with the Scam call caller + victim packs (about 70 detector calls plus about 20 coaching calls, cap 150) to see real scores, wins and coaching; (2) the static build does not include the flow pages, so nothing to change there (Live cannot run in a static build); (3) still open: the voice server needs a restart to pick up the YouTube 403 retry in `voice/ingest.py`, and `ANTHROPIC_API_KEY` in `.env` is an empty placeholder so name-only detector drafting falls back to a template. Findings so far are in `docs/voice-flow-integration-plan.md` ("Measured so far"). The rest of this section is the original plan, kept for the reasoning.

**Live audio in Conversation flow, proven in an isolated mock-up first.** Do not touch
`demo/flow.html` until the mock-up has measured the open questions. Plan (decisions already made,
phases, safeguards, measured server behaviour): `docs/voice-flow-integration-plan.md`. Read it fully.

The shape, in five lines:
- **Two modes**: *Replay* = a saved conversation (precomputed answers); *Live* = real audio from a
  mic/call, an **uploaded audio file**, or a **YouTube link**. Today's "Live" (scripted words, real
  model calls) was never truly live and folds into Replay as an option.
- **Mock-up** `demo/flow-lab.html`, served by `demo/server.py` at `/flow-lab`, not in the nav, not
  in the static build. It watches voices arrive, has detectors, and lets you **add a detector while
  it runs** on paid Jev (all detector questions in one composite `/v1/systemone` call per checkpoint).
- **Ingest is server-side** in `voice/server.py` (`yt-dlp` piped into ffmpeg for YouTube; file bytes
  over the same WebSocket), with an allowlist and caps. `yt-dlp` is not installed yet (pip into `voice/.venv`).
- **Seed the integration, do not fork it.** The mock-up should look and behave like `flow.html` so
  porting is mostly moving code: load `static/app.css` and `static/app.js` (`Jev.*` helpers), reuse
  the thread markup classes (`msg`, `bub`, `meta`, `words`), the detector colours `--s1..--s8` and
  icon set, the checkpoint rule (`trig`: `((sentence end || turn end) && since >= 3) || since >= 12`
  words), `personWindow`/`callWindow`, and the `QALL` question shapes for library and custom
  detectors. Write the live path as one function with the same shape as flow's `onWord(wd)` (a word
  event `{spk, w, t, turnId, last}` in, thread + runner out) so it lifts across unchanged.
- **Recon questions to answer with numbers** (real panel/stream audio, not the clean clip): rewrite
  rate of committed words, speech-to-detector lag, speaker flips per minute, hosted spend per hour,
  GPU fit, add-a-detector-mid-stream behaviour. Write the answers into the plan file.

**Runtime state right now**: the voice server is **running** (`:8200`, started from
`/workspace/voice` with `.venv/bin/python -u server.py`) and the classifier lineup is **down**
(voice plus the full ~30 GB lineup runs out of GPU memory; plan adds a smaller `lineup.sh voice`
profile). Hosted Jev works with no GPU. To get the lineup back: stop the voice server, then
`demo/lineup.sh up`. The demo console (`:8100`) runs from `/workspace` with `.env` loaded
(`set -a; . ./.env; set +a; python3 demo/server.py`).

**Also done this session, relevant here**: Baseline compare now has ten simple scenarios, two of
them code-security *batteries* (a snippet plus ten yes/no checks and a decision answered in one
composite request; `/api/compare` accepts `questions`) — the same composite mechanism the
mock-up's detectors will use. A stylesheet bug that let `.field { display:flex }` override the
`hidden` attribute was fixed in `compare.html`.

## Where things stand

**The benchmark side** (published probe sets, MMLU World Knowledge, the Leaderboard, Report, and
"How they work" pages) is stable and unchanged from what `CLAUDE.md` already describes. Nothing
about it needs revisiting to start the next project.

**Custom Decomposition** (Scenario lab) was substantially rebuilt this session:
- Jev (hosted) can now be selected alongside the local models — it was previously hard-refused as
  a cost-safety default; the run's own budget parameter (3-113 calls) already bounds the cost, so
  the refusal was removed in both the server and the CLI.
- The old Map + Outline (a tiny side detail panel, only reachable from the Map, never wired up
  from Outline) was replaced with **Results**: a real table, one column per model actually run,
  grouped **Shape → Category → Leaf** with a rollup row per shape/category, a **Decision** column
  (a disclosed, stated rule combining each item's live phase/gap answer with its real agreement
  level — low agreement overrides everything else), and an **Agreement** column (1 − spread).
  Starts fully collapsed; click anywhere on a group row (not just a tiny caret) to expand; each
  table gets its own Expand-all/Collapse-all.
- The schedule table (Chapter 2, "What it might cost") got the same shape/category grouping and
  collapse behavior, dropped a duration-range column and the now-redundant "models split" badge
  (Results already shows per-model agreement), and its day-precision axis was softened to
  "relative effort, not a calendar" language throughout, since the heuristic duration-band rule
  never supported calendar-level precision in the first place.
- Budget slider now defaults to 113 (the full library) instead of 60 — a full run against local
  models is a couple of seconds, so there was no reason to default to a partial one.

**Conversation flow got a real recorded dataset**: `data/flow-recordings/` holds genuine
`POST /v1/systemone` exports (via `flow.html`'s own "Export" button) — Apollo 13 across all four
models (jev/semif/so1/kev-4b), plus two MentalManip library dialogues (`mmwin-85514422`,
`mmwin-85515526`, jev only, chosen for having real manipulation-detector signal — the first replay
choice, Apollo 13 alone, was too quiet to be a good demo and got called out for it). Only 6
recordings exist; adding more is just running the live page once and dropping the export in.

## The static site: live, public, done

The console now has a public static export, separate from the live `demo/server.py` instance:

- **`demo/build_static.py`** regenerates the static build by calling `demo/server.py`'s own
  functions directly (never reimplemented) for Leaderboard, Scenario lab (all 72 published +
  MMLU sets), How they work, and Report — genuinely zero live model calls, no key, no GPU needed
  to view them. Baseline compare has no static equivalent (a live, free-typed question has no
  static form). Conversation flow ships as the recorded-summary page above
  (`flow-recordings.html`), not the live word-by-word player.
- Output goes to **`docs/`** (not `dist/` — GitHub Pages' simple branch-deploy mode only serves
  from the repo root or a folder literally named `docs/`). `docs/` also holds real hand-written
  project docs (`custom-decomposition-design.md` and others) that predate this build — the script
  only ever deletes the specific paths it generates (`api/`, `static/`, the named page files),
  never the whole directory (it did once, by accident, and silently deleted those docs; restored
  from git history, now structurally prevented).
- Every internal link (nav, the Leaderboard's per-model deep links) is a **relative path** on
  purpose, so the same build works whether it's served from a domain root or from a path prefix
  (a GitHub Pages *project* site lives at `<user>.github.io/<repo>/`, not the root — an absolute
  `/models.html` resolves to the wrong place there).
- **Live at <https://mvp-scale.github.io/workspace/>**, via GitHub Pages on `main:/docs`. The repo
  (`github.com/mvp-scale/workspace`) is public. Audited before pushing — no secrets, keys, or
  `.env` content anywhere in the tracked tree, `docs/`, or full git history.
- A real, unrelated pre-existing bug was found and fixed along the way: `research/classifier-dev`
  was tracked as a broken git submodule reference (gitlink, no `.gitmodules` entry) from an
  earlier commit. GitHub's Pages Actions deploy does a submodule-recursive checkout and was
  failing on it before ever reaching the site content. Untracked (the directory itself is
  untouched on disk); this is why the first two deploy attempts failed with no obvious connection
  to anything in `docs/`.

**Known limitations of this setup, worth remembering:**
- Not a CI pipeline — updating the live site means re-running `build_static.py` and manually
  `git add docs/ && git commit && git push` again. Nothing rebuilds automatically on data changes.
- `docs/` is committed (not gitignored) specifically so GitHub can see it; this means every
  rebuild that changes data adds a real diff to the repo's history, unlike a normal gitignored
  build artifact.
- Genuinely static: no live status, no live GPU state, no way to ever add Baseline compare or
  live Conversation flow to this specific deployment without adding a real backend.

## Other open threads, not touched this session, still just where they were

Two research questions were explicitly parked mid-investigation and never picked back up:
1. **A business/decision-relevant knowledge benchmark** — LegalBench (CC BY 4.0, real, ~100-250
   usable items after excluding ContractNLI-derived subtasks) is the one domain that cleanly
   survived a strict-sourcing bar; ESGenius (1,136 items, real/recent, but LLM-*generated* then
   expert-validated) is a tempting but not-yet-accepted exception to the "no manufactured content"
   standard every other set here holds to. Not decided: take LegalBench alone, also accept ESG, or
   keep searching (real estate, corporate governance, risk management, auditing-vs-accounting).
2. **An architecture/systems-design decision-reasoning benchmark** — no public, licensed benchmark
   for this is known to exist (cloud certification exams are the closest real-world analog, and
   they're vendor-proprietary, same "gated behind a certifying body" problem as most business
   domains). Humanity's Last Exam was flagged as a possible fit for a *different* axis ("esoteric
   synthesis of sparse knowledge") that probably shouldn't be conflated with this one.

`foundry/PLAN.md`'s own backlog (the `ATOMIC_THRESHOLD` re-threshold decision, ~15-18
`world-knowledge.yaml` content edits, `sort_and_rank.py`'s hosted-model-skip bug) and
`docs/scenario-lab-plan.md`'s original items 1-4 and 14-18 are untouched, unchanged from before.

## Voice pipeline: live speaker-attributed transcription, in progress

The "next: voice" project from the previous update is now a real, working prototype at
`/workspace/voice/` (separate from `demo/`, not yet wired into the console). Not a finished
feature — read this section before touching it, several non-obvious things were learned the
hard way.

**The code has moved past a simpler design mid-session — treat current files as ground truth.**
What's running now is NVIDIA's actual coupled multitalker pipeline (`mt_pipeline.py`, using
`LiveMultitalkerSession`/`SpeakerTaggedASR` per NVIDIA's own `ASR_INTEGRATION_GUIDE.md`), not the
earlier two-independent-models version this session started with. `voice/reference/` holds
verbatim copies of NVIDIA's guide, both model READMEs, and a `PROD_BEST_PRACTICES.md` +
`SOURCES.md` — read those for the current architecture's rationale, not this file's blow-by-blow.

**Models**: `nvidia/Nemotron-3-Diarization` (8-speaker Sortformer, needs NeMo installed from
GitHub `main` — PyPI's 3.0.0 release predates the RoPE support this model's encoder needs) +
`nvidia/multitalker-parakeet-streaming-0.6b-v1` (coupled streaming ASR, not the standalone
`parakeet_realtime_eou_120m-v1` this session tried first).

**Real pitfalls hit and fixed, worth knowing before changing settings or chunk sizing**:
- Both streaming services' internal feature buffers advance by a **fixed stride** set at init
  (derived from `chunk_size_in_secs`/`chunk_len`) — call `.diarize()`/`.transcribe()` with
  anything other than exactly that many samples and the feature window silently desyncs from the
  real audio (no exception, just empty/garbled decoding).
- NVIDIA's own published "very low latency" diarization preset (chunk_len=6) was A/B tested here
  under real-time-paced audio and measurably broke ASR output (word fragments vanished) — likely
  a real-time compute-budget issue (640ms window too tight for this heavier buffer config on this
  hardware), not a wrong-parameters issue. The "low latency"/"Balanced" preset (chunk_len=9,
  1.04s budget) verified working correctly and is the current default. Re-verify before trusting
  Fast/Ultra presets for a live mic rather than assuming NVIDIA-published means safe here.
- Lowering `max_num_speakers` below the checkpoint's trained 8 does **not** reduce compute — it
  silently breaks diarization output entirely (confirmed by direct test). Not exposed as a
  setting for this reason.
- Audio transport is a single persistent WebSocket with a decoupled recv/inference/send 3-loop
  architecture (matches NVIDIA's own reference and a real production streaming-Parakeet
  deployment) — an earlier single-blocking-loop version caused connection resets under real load,
  because inference blocking the same loop that receives audio backs up the mic-side buffer.
- The ASR's `<EOU>`/`<EOB>` end-marker can appear inside the decoded text string itself, not just
  as a separate flag — strip it, but only when present (an earlier unconditional `.strip()` broke
  word-boundary spacing between fragments).
- Real diarization jitter (a continuous speaker's label flipping chunk-to-chunk) is expected and
  was never exercised until a real multi-speaker test — an EMA smoother over per-speaker
  confidence is in place; tune `SPEAKER_EMA_ALPHA` if it's too sluggish or too jittery.

**What the mockup UI has**: live-reconfigurable settings (sliders with shaded "verified-good"
bands, not raw numbers), preset buttons for NVIDIA's four latency profiles labeled honestly
(verified vs. untested-here), a mic self-test (record 3s, play back, download WAV — bypasses the
whole ML pipeline, for isolating capture-quality problems from model problems), and known-content
test clips (`warmup.pcm`, `twovoice.pcm`) to replay without needing a live mic.

**Audio capture options** (the user wants to demo live Zoom/Teams call audio, said "tomorrow" as
of 2026-09-24): the audio-source selector supports mic-only, a virtual-loopback-device path
("both"/"dev" — needs Stereo Mix, VB-CABLE, or similar), and a **no-install** path via Chrome's
`getDisplayMedia` screen-share dialog ("screen"/"tab" — pick "Entire Screen" + "Share system
audio", zero drivers, zero reboot, already verified working end-to-end). The user is installing
VB-CABLE as the more polished option for the actual demo but confirmed the no-install path works
as a fallback. **VB-CABLE requires a reboot** (their own install page says so — an earlier claim
in this session that it usually doesn't was wrong and got corrected).

**Where things stand right now**: see "Runtime state right now" under START HERE.

**Next (planned, not started)**: two modes in `demo/flow.html` (Replay = saved conversation, Live = real audio from mic/call, an uploaded file, or a YouTube link), proven first in an isolated `demo/flow-lab.html` with live-added detectors on paid Jev. Full plan: `docs/voice-flow-integration-plan.md` (measured transcript behaviour, ingest design and safeguards, phases; test fixture `voice/fixtures/twovoice-snapshots.json`).

**Not yet done**: wiring this into `demo/flow.html`'s transcript-source abstraction (still the
long-term integration target per the original plan) — this is still a standalone prototype at
`voice/`, deliberately not touched in `demo/` yet.
