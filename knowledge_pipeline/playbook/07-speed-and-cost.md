# 07 · Speed and cost

**Goal:** honest items-per-second numbers on the target hardware, and a per-stage budget to hit the product target.

## Rules

1. **Measure four numbers:** ms per model call (state window length), wall ms per typical item (p50 and p95), vCPU-s
   per item, and items/s on N vCPU with the process × thread layout. "30 ms" alone misleads: that was one 254-token
   call; a typical article was 228 ms and 0.68 vCPU-s.
2. **Break the item into stages.** Ours: model 128 ms, spaCy 57, time/quantity rules 19, assembly 20. Optimise the
   biggest stage first.
3. **Processes beat threads for throughput.** On 4 vCPU, 4 processes × 1 thread gave 5.9 articles/s; 1 process × 4
   threads gave 3.5. Threads help single-item latency, processes help throughput.
4. **Use a representative sample** (we used 1,000 news articles, fixed seed) and the same machine for every
   comparison; record CPU model and flags. Kaggle machines vary ~2.5× between sessions; compare ratios.
5. **Levers, in measured order of value:**

   | Lever | Measured or expected gain |
   |---|---|
   | Triage router: skip items that don't need full extraction | saves the whole item cost per skip |
   | One encoder for all heads (no second model) | avoids a full pass per extra task |
   | Smaller backbone (Ettin-17M) | 0.57× encoder time per window |
   | Remove or trim spaCy | tagger-only −47 ms; removed in v3 |
   | OpenVINO instead of ORT | none on our CPUs |
   | Rust or JS runtime | same ORT engine; small gain only in glue code |

6. **Cost per million items** = vCPU-s per item × 1e6 / 3,600 × $ per vCPU-hour. State the price used.

## Done when

The four numbers, the stage breakdown, and the layout are in the gate report, compared against the budget from
chapter 01.
