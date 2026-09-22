# classifier.dev (mrmps/classifier-dev): what it is

Source: https://github.com/mrmps/classifier-dev, cloned to `research/classifier-dev/` at a68b524 (2026-09-21). Read from its README, AGENTS.md, CONTEXT.md, `src/jev.ts`, `src/laya.ts`, `eval/README.md`. Nothing was run and none of its numbers were reproduced here.

## Short answer
It is not a classifier model. It is a Cloudflare Worker (TypeScript, no runtime deps, no DB in the hot path) that turns a URL or JSON call into a Jev-class /v1/systemone request and forwards it to a hosted model. Nothing is classified in the Worker's memory. The model runs elsewhere, on GPUs owned by others:
- Jev: TypeSafe (api.typesafe.ai/v1/systemone), or Vercel AI Gateway (typesafe-ai/jev) when enabled; the gateway was disabled on 2026-09-19 after 429s.
- Laya and Kev (`jev/laya`, `jev/kev`): hosted by Beam (app.beam.cloud/v1/systemone), same protocol. Moved off Modal in #105.
- Fallback when TypeSafe is down: LLM chains via OpenRouter, max 20 inputs per call.

"No GPU" is true for the Worker only. The Worker does packing, validation, retries, rate limits, analytics.

## What makes it "zero-shot text classification over plain HTTP"
1. Labels come from the caller in the URL path: GET /spam,not+spam/Win+a+free+iPhone returns "spam".
2. Single-label: one `choice` question per input, criteria = the labels (values null), "Which category does item `id` belong to?" Answer = argmax, scores = probabilities.
3. Multi-label: one `noul` (yes/no) question per label, "Does the category X apply to `id`?"; labels with P>=0.7 are returned, most likely first.
4. Batch: state is an array of {id, text}; each input gets its own question; up to 1000 inputs per request. `jev.ts` packs by an estimated-token budget (48k of a documented 64k for Jev), runs the requests 8 at a time, and on a context error halves the batch and retries (`max_tokens_exceeded`).
5. Backend limits differ: Beam allows at most 32 named questions per request; Laya's documented limit is state + one question within 512 tokens (packed to 460), max 16 items.
6. "smart" tier: single-label answers with confidence < 0.7 are re-asked of a reasoning LLM (gemini-3.8-flash) and replaced, marked `escalated: true`. That is a confidence-routed cascade.
7. Ops: per-request cost meter, hashed (keyed) caller pseudonyms, Analytics Engine, 15-minute alerts, feedback.now protocol, a CLI (`classify`), MCP servers.

## Their claims (unverified by us)
- 400 news headlines in ~650 ms end to end; packing 100 items scored the same as sending them one at a time.
- Calibration on 400 six-way emotion items: >=0.9 confidence right 82%; <0.5 right 29%.
- Multi-label F1 0.887 in 230 ms vs 0.799 for their LLM cascade (1.5 s).
- Jev 87.7% AG News / 60.5% emotion vs 82.0% / 57.0% for ling-3.0-flash (2026-09-17).
- JevBench lists classifier.dev fast tier at 83.6 as unranked because it runs Jev at a different price point.

## What is useful for us
- Batch packing and halve-on-context-error, a working precedent for the batch-size experiment (5..160 answers).
- The URL-as-API surface and multi-label as one noul per label.
- Confidence-routed escalation with a stated threshold (0.7), and reporting which model actually answered (their fallback served an F1 0.546 model for weeks unnoticed).
- Beam's 32-question cap and Laya's 512-token limit are real ceilings to plan around.

## Answer to "anything in memory, no GPU?"
No. It has no model of its own. A GPU-free path would need a small CPU model (for example our VERD2H, a 151M model on CPU, already in the lineup), not this repo.
