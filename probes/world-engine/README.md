# world-engine

Working folder for the local world-state engine: the five-lens model (world, country, region, segment, person) with a state side and a decision side, driven by classified news.

- `inputs/`  outside material we did not write (for example the ChatGPT-drafted PRD). An input is evidence of options, not a spec. Never edited in place.
- `analysis/`  what we make of each input: what to adopt, adapt or skip, with the reason and a source tag.
- later: `spec/` for our agreed base version, once chosen.

Related work that predates this folder (still in `../persona/`): persona-profile-standard.md, model-v2.md, ontology-v1.md, rules/ (CSV tables), engine.py, world_model.py, news_walk.py, offline test notes.

## The runnable slice (2026-10-04)
Run in order with `/workspace/kev/.venv/bin/python` (cluster step with `/workspace/models/embed-venv/bin/python`):
1. `intake.py`  reads three public NPR RSS feeds; stores headline, the feed's one-line description and link (no article bodies) in `ledger/evidence.jsonl`.
2. `classify.py`  the local classifier (Winnow) answers 144 yes/no questions per item; fixed rules turn them into dial readings; `ledger/measurements.jsonl`.
3. `cluster_events.py`  merges near-duplicate items into one event (small embedding model, threshold 0.72); `ledger/clusters.json`.
4. `engine.py`  nodes (world, country, 4 regions, 4 segments), channels (gain, lag, gate, slant, seeded noise), persons as arrays, decisions, and `Audience` (the higher-level classifier: a node's yes/no probability for an item).
5. `demo.py [--n 100000]`  the full run: events, state per level, a trace, decisions, opinion on new items, a scenario branch, noise and repeatability.
Rules come from `../persona/rules/*.csv` (dials, elements, grid, decisions, weights, attributes). All strengths are guesses.

## Known problems in this slice (do not read the numbers as findings)
- Classifier misses and errors on real items (for example a presidential statement about a scandal read as trust up; a diesel reserve release read as community and division).
- Decision stage thresholds (0.005, 0.02) were fixed in advance but are far too low: nearly every decision shows 'imminent'.
- Channel slant is zero everywhere, so the agenda/political element of each level is built in but not exercised; channel noise (5%) is small against the effects.
- The audience classifier is a fit to language-model answers on generated people, applied to world-modified traits (an extrapolation).
- Region nodes differ only by small seeded gains; segment gains are hand-set.
- No comparison with any real outcome yet.

## World lab mock-up (2026-10-04)
Page: http://127.0.0.1:8100/worldlab (nav: World lab). Files: `/workspace/demo/worldlab.html`, proxy routes in `/workspace/demo/server.py`, engine service `world_service.py`.
Start the service by hand (port 8111; 8110 is used by a static mock-up server that is not ours):
  `cd /workspace/probes/world-engine && nohup /workspace/kev/.venv/bin/python world_service.py --n 50000 > /workspace/logs/world-service.log 2>&1 &`
Stop it: `kill $(ss -ltnpH | grep ':8111 ' | grep -oP 'pid=\K[0-9]+')`   (do not use `pkill -f`: it matches your own shell).
The service needs the local classifier (Winnow, :8091) for typed headlines and for reading the item you ask about.
Starting world: `baseline.json` (public indices read through a web-fetch tool on 2026-10-04; reference levels and scales are our assumptions); news from `ledger/`.
What the page shows: the world today (indices plus news), news flowing in with an add-a-headline box, a question box, and for any item: take-up by age x income, what's in the way split into fix the offer / change their mind / wait for the world, the dials to watch, and take-up as the news came in.
Typed headlines skip the recency test (they are 'now') but opinion and forecast pieces are still refused.

### Audience-first rebuild (2026-10-04)
The page now centres on the audience. `world_service.py` builds 8 segments once by clustering people on beliefs, habits and life situation together (k-means; names come from each segment's most distinctive traits), and `/audience` returns per segment: support, how people split across five support levels, drivers (the segment's deviation on each of 16 person factors times that factor's effect on this offer, exact on the logit scale, shown in approximate points, plus the world's effect), levers (offer changes, belief shifts, a calm world) with points gained, leading dials, who they are, and support per story. Known limitation: in the training ideas the app requirement and the ID photo always came together, so their separate effects cannot be told apart.

## World engine, five stages (2026-10-04): page /worldengine
Files: `data/countries.csv` (8 countries, simulated start values; the US row carries the real-index dial starts), `data/segment_exposure.csv` (rules for how each audience feels each dial), `data/factors.csv` (the 10 attractor/detractor factors), `world_pop.py` (100,000 people from the country table), `engine2.py` (WORLD > COUNTRY > REGION nodes with channels), `world_service2.py` (port 8112), `/workspace/demo/worldengine.html`.
Flow: Collect (news ledger, indices, request) > Identify (local classifier reads the request into elements; typed choice question names the country) > Propagate (event enters at a country or the world, channels carry it to regions; a control run with no event isolates the event) > Decide (event mode: 8 state decisions from person states; offer mode: take-up from person factors x offer properties) > Read (heat map across world, countries, regions and cross-country audiences; click a cell for the attractor/detractor ledger: state, rule weight, push in points, why).
Start/stop: `cd /workspace/probes/world-engine && nohup /workspace/kev/.venv/bin/python world_service2.py > /workspace/logs/world-service2.log 2>&1 &`   stop: `kill $(ss -ltnpH | grep ':8112 ' | grep -oP 'pid=\K[0-9]+')`. The older /worldlab page (port 8111) is still there but no longer in the nav.
Known limits: country and settlement parameters are illustrative; events do not spill between countries except through the world node; the offer model was fitted on US-style generated people and is extrapolated to other countries; classifier misses (for example 'oil supply cut' read only as prices); rule editing is by CSV or code, not in the page.

### UX rebuild (2026-10-04, after owner review)
One page replaces three: /personalab and /worldlab now redirect to /worldengine and are out of the nav (files left in place; the old world-lab service on :8111 was stopped). Page rules: one pinned ask bar and nothing before it; the engine decides event or offer itself (typed choice question, shown as 'Read as', one click to override); a slim five-stage stepper that fills as the stages run, with hover explanations; results appear in place and nothing scrolls on a click; the story is three headline numbers then what pulls up and pushes down (at world level: the strongest place-and-factor pairs); perspective is chosen in the navigator (tree, countries, regions, audiences); heat maps, how it was read, how it spread and the decision rules sit in tabs; the rule behind any line opens inline or in a popover; inputs and rules live in a side drawer (Data & rules).
