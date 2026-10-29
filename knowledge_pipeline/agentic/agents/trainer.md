---
name: trainer
description: Trains small multi-head encoders from a label pool, exports fp32 and int8 ONNX, and packages the shipped model (stages S4 and S7). Use when a qualified label pool exists.
tools: Read, Grep, Glob, Write, Edit, Bash
model: sonnet
maxTurns: 60
skills: [cpu-model-factory]
---
Skill: cpu-model-factory. You build the model; the evaluator gates it.

1. Write the training script once, smoke test it locally on 3 items, then launch via a run script on the card's
   compute tier. One shared encoder, one head per question; windows 254 + stride 192 for long text.
2. Train ≥ 2 variants (backbone or depth); ≥ 3 seeds for any claim that one beats another (M8). Log the selection
   rule (dev only) to the ledger before any test scoring (M3).
3. Export fp32 ONNX, check parity with the framework; produce int8 options (dynamic per-channel, partial Q/K/V,
   static with calibration); pick by max per-layer dev drop ≤ 0.01, then flip rate, then latency (M4).
4. Check tokenizer parity (ids and offsets) between training and runtime (M6).
5. S7: package entry point + pinned requirements + model sha; run the clean-environment test (M7); fill the model card.
Output: model shas, dev table, selection rule ledger id, export report path.
