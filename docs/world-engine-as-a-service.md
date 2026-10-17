# World engine as a service

Written 2026-10-17. A thinking document, not a plan of record. Numbers marked **measured** were taken on this machine this week; everything else is a projection or an idea.

## The idea in one paragraph

Every story moves the world in ways a reader never sees. The World engine reads a story once, turns it into typed answers (which conditions it moves, which way, is it fact, forecast or opinion), pushes that change through a rules graph (conditions → how people feel → what they might do → what that draws on), and forecasts where each resource is heading. Every forecast is scored when it comes due. Read everything that is freely available, keep the world model current, and sell **the signal and its track record**, not the text.

## How it breaks up

| Layer | What it does | Today | At scale |
|---|---|---|---|
| 1. Ingest | Pull stories from open feeds into a queue | A fixed file of 518 headlines | Any number of feeds; a queue, processed as stories land |
| 2. Read | Answer a fixed battery of yes/no questions per story (328 today) | Clef, local, **4.2 s per story (measured)** | A small trained reader: **~2 ms per story on CPU, ~17,000 stories/s on one GPU (measured speed; agreement with Clef not yet tested)**. Clef only teaches it and handles what it is unsure of |
| 3. World change | Apply the answers to the world model | **2–4 ms per story (measured)**, one at a time (~400/s) | Apply each tick's stories in one batch (not measured yet) |
| 4. Cascade | Rules carry the change to 300,005 simulated people, 20 decisions, 409 places | **~95–300 ms per update (measured)**, independent of story count, not blocking | Same |
| 5. Forecast and score | Forecast each resource for a day, week, month; score each when due | Running on the How it works page (in engine ticks, scored against the engine's own later state) | Scored against real-world data ("witnesses"), the track record published |
| 6. Deliver | API, dashboards, alerts | The console pages | See "What is sold" |

The point of the split: only layer 2 needs a large model, and only for teaching. Everything after it is arithmetic.

## What it costs

- **Reading:** at ~2 ms per story on one CPU core-set, a million stories is about 33 CPU-minutes. Even one million stories a day averages ~12 a second, far below the measured ceiling. Reading is no longer the cost.
- **Teaching:** Clef labels a few thousand stories once per question set (hours on one local GPU, no hosted calls). Re-teach when the question set changes.
- **World model and cascade:** one GPU holds it today (661 MB of tensors for 300,005 people).
- **The real costs are elsewhere:** collecting and de-duplicating feeds, the licence terms of each source, and building the real-world witness data that scores forecasts.

## What is sold

1. **Story → world-change events (API).** For each story: the typed answers and the conditions it moved, with direction and size. Structured data, no prose.
2. **Indices with forecasts.** Every condition and resource as a live index, with a day / week / month forecast and its **calibration** (how often our forecasts of that index have been right). The calibration is the product: it says how far to trust each number.
3. **Alerts.** "Food supply under strain, forecast holding for 3 weeks running."
4. **What-if.** "If this story were true, what moves?" The engine already answers this (the ask on the World engine page).
5. **Custom lenses.** A customer's own resources and decisions (their supply chain, their customers' likely moves) wired onto the shared world model.

## Honest limits

- **News is free to read, not free to republish.** Sell derived signals, never the text; check each feed's terms.
- **Link strengths are guesses until fitted.** The forecast-and-score loop is how they get fitted; until then the numbers show the mechanism, not the truth.
- **The small reader's accuracy is untested** on the 328 questions. Some questions need world knowledge (does this raise prices?), which is where small encoders were weakest (BitMob: ~29% on facts). Test before claiming: the Intake bar (≥97% agreement with Clef) is the yardstick.
- **Ticks are not days.** The demo assumes 1 tick = 1 day. A service needs a real clock and dated stories.
- **Attribution is hard.** Many stories move the same index; a single hit proves little. Calibration needs many forecasts per link.

## Not just news: any stream

The same break-up works for any stream of text or events. What changes is the ontology (the topics, conditions, states, decisions and resources) and the question battery.

| Stream | Conditions it moves | Resources | Decisions forecast |
|---|---|---|---|
| Support tickets | product friction, outage risk | support capacity, goodwill | churn, upgrade, escalate |
| Sales and service calls (the Conversation flow page) | buyer intent, objections, trust | pipeline, rep time | buy, delay, walk |
| Company filings and earnings calls | demand, cost pressure, guidance | cash, capacity | hire, cut, invest |
| Reviews and social posts | sentiment, quality issues | brand trust | switch, recommend |
| Operations logs | load, error rates | compute, on-call time | scale, roll back |

## Applying it internally with your own knowledge

Build a world model of your own organisation: its conditions (customer health, team strain, delivery risk), its resources (cash, people's time, capacity) and the decisions you care about (hire, launch, cut, escalate). Feed it your own streams: meeting transcripts, tickets, CRM notes, chat. The forecast-and-score loop then tells you which of your own expectations hold.

Run it locally. This is the internal-data case for the word-of-caution card on How they work: a local reader means your data never goes to a hosted provider, so nothing about it can be logged, derived or trained on elsewhere.

## Two deployments, one engine

The engine is the same in both: the classifier tiers, the world model, the forecast-and-score loop. What differs is where it runs and whose data it reads.

### A. Public: news cards on Cloudflare (public data only)

```
 open feeds ──cron──▶ Queue ──▶ Reader Worker (tiers 0–2) ──▶ Queue ──▶ World Durable Object ──cron──▶ cards in R2/KV ──CDN──▶ users
                                     │ unsure (gate)                         (applies a tick's events             │
                                     ▼                                        in one batch)                         ▼
                              Clef on our GPU box (tier 3)                                                 predictions in D1
                              also writes teacher labels                                               scored when due: model vs
                                                                                                       crowd vs each user
```

- **Ingest:** a Cron Trigger pulls feeds; each story is hashed (de-duplicated) and put on a Queue.
- **Read:** a Worker runs the classifier tiers below; only the stories it is unsure of go to Clef.
- **World model:** one Durable Object (a single-writer, stateful Worker) holds the world state and applies each tick's events in one batch. In the cloud it runs at aggregate level (conditions per place, decisions per audience × place cell), not 300,005 individuals; the full GPU simulation stays an optional deep run on our box.
- **Cards:** each tick, a cron writes the forecast cards (index, forecast, calibration) to R2/KV; the CDN serves them. A customer picks the topics and resources they want ("accept and pull back"), and gets a card feed, a stream or an embeddable flow filtered to that.
- **Engagement loop:** users make their own call on a card (up, down, steady). Calls are stored in D1 and scored when the card comes due: the model, the crowd and each user. The score brings people back; the crowd's calls are free labels that show where the model is wrong. Points only, never money (staking money makes it a regulated prediction market).

### B. Private: in-house through an object-storage handoff

```
 customer tool ──writes──▶ inbox bucket ──event──▶ Queue ──▶ Reader + World (their account) ──writes──▶ processed bucket + manifest
                            (theirs)                          nothing leaves their account              input marked done
```

- No integration with the customer's tools: their tool writes files to their own **inbox** bucket (R2 or any S3-compatible store). A bucket event notification puts each new object on a Queue.
- The same Workers, deployed **in the customer's own Cloudflare account** (or a container in their cloud), read, classify and update *their* world model, then write results to a **processed** bucket with a manifest (input key, hash, time, model versions) and mark the input done.
- Their data never reaches us or a hosted model provider. The teacher (Clef) runs on their hardware or is not used; heads are trained on their side from their own labels.

## Breaking up the classifiers (cheapest first)

Each story falls through the tiers until one is confident; every answer records which tier gave it (as BitMob does with "trained" / "guess").

| Tier | What | Runs where | Job | Status |
|---|---|---|---|---|
| 0 | Rule NLP: compromise or wink-nlp (small JavaScript libraries) | Inside the Worker | Clean text, de-duplicate, pull out places, people, organisations, dates; route the story to its country and likely topics; drop non-stories | Not built; JS libraries that run in Workers |
| 1 | Static embeddings (a lookup table, like BitMob's router, potion-base-8M) + learned heads | Inside the Worker, pure JS, no runtime needed | The router (which area a story is in) and the easy, repeated questions | Router measured on our box (under 1 ms); not ported to JS |
| 2 | e5-small int8 + one learned head per question (BitMob's CPU engine) | Option 1: inside the Worker via ONNX Runtime Web (WebAssembly); the model file is 33.8 MB, under the 64 MiB script limit, but the 128 MB memory limit makes it tight (untested). Option 2: Workers AI's bge-small-en-v1.5 (same size class, 384 numbers per text) with heads retrained on its vectors | The 328-question battery for most stories | ~2 ms/story on our CPU (measured); agreement with Clef untested |
| 3 | Clef Flash Q4 (teacher) | Our GPU box (public) or the customer's (private) | Stories the gate is unsure of; labels to train tiers 1–2 | Running today (4.2 s/story) |

A gate after tiers 1 and 2 decides "answer here or pass down", tuned on held-out data (the Intake method: ≥97% agreement with Clef, ≤25% passed to Clef).

**Training data we know of:** Clef-labelled news (any amount, from the bank and feeds); the published probe sets already in `probes/v2/` (note their licences: MentalManip is non-commercial, OWASP Benchmark GPL-2.0, dark patterns GPL-3.0, LOGIC undeclared); GDELT (an open, dated, event-coded news index) for backtests and as a witness source.

## Cost model (Cloudflare list prices, checked 2026-10-17)

Per month, at 1 million stories, public deployment, before the teacher:

| Item | Price (source) | Estimate |
|---|---|---|
| Workers Paid plan | $5/month base, 10M requests and 30M CPU-ms included | $5 |
| Workers AI bge-small (if used for tier 2) | $0.020 per million input tokens | ~25M tokens (assumes ~25 tokens a headline) ≈ $0.50 |
| Queues | 1M operations included, then $0.40 per million | ~3 ops a story ≈ $0.80 |
| R2, D1, KV | R2 egress free; D1 25B rows read included; KV 10M reads included | Small at this volume |
| **Cloud total** | | **about $5–10 a month per million stories** |

The margin question is therefore not the cloud bill. It is (1) the share of stories passed to Clef and what running the teacher costs, and (2) feed licensing. With tier 2 handling most stories, 90%+ margins look reachable on a monthly or pay-as-you-go price, but only the reader-agreement test can confirm the pass-down share.

Limits that shape the design (Workers docs): 128 MB memory per isolate; 64 MiB script (uncompressed); up to 5 minutes CPU per request on the paid plan.

Sources: [Workers limits](https://developers.cloudflare.com/workers/platform/limits/), [Workers pricing (incl. Queues, R2, D1, KV)](https://developers.cloudflare.com/workers/platform/pricing/), [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/).

## Smallest next steps (each with a pass bar set before running)

1. **Reader agreement:** small reader vs Clef on the 328 questions over a few thousand stories. Pass: ≥97% agreement, or a gate that sends the rest to Clef with ≤25% routed.
2. **Real-time backtest:** a dated news archive (one past month); forecasts from week 1 checked against the following weeks' stories as witnesses. Pass: beats a "nothing changes" baseline on direction.
3. **Batched world change:** apply a tick's stories in one step on a copy of the engine. Pass: ≥10,000 stories/s into the world with the same end state as one at a time.
4. **Reader in a Worker:** e5-small int8 under ONNX Runtime Web within the 128 MB limit, or bge-small via Workers AI with retrained heads. Pass: fits, answers match the local engine (or meet the agreement bar), cost per million within the table above.
