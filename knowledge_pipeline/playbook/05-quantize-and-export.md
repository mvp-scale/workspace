# 05 · Quantize and export

**Goal:** one ONNX int8 file that gives the same answers as the fp32 model on dev, and runs everywhere you need.

## Rules

1. **Export fp32 ONNX first** and check it matches PyTorch outputs on dev (argmax agreement ~100%).
2. **Quantize several ways, choose on dev.** Candidates we tried: per-tensor dynamic int8 (cost entity −.040,
   outside the interval), static QDQ (too slow, 52.6 ms p50), MatMulNBits (too slow), bias-corrected variants, and
   partial int8 of Q/K/V + attention only ("QA", shipped: max dev drop .0007, 29.8 ms p50). Calibration set: 96
   articles, 320 windows. Pick by minimum per-layer agreement with fp32 on dev, label flip rate, then latency.
   Write the pick rule before scoring the test set (T61 had to be re-run because the first pick was made after
   seeing test scores).
   Some encoders don't tolerate int8: an MPNet topic model fell from F1 .81 to .62 with default settings (.79 with
   per-channel); MiniLM was fine. Batching windows hurt dynamic int8 on event nouns (−.04 to −.08).
3. **Graph optimisation.** ONNX Runtime fuses attention, layer norm and GELU into `com.microsoft` ops; our file has
   36 nodes. Fused files run in ORT (Python, C/C++, Rust `ort`, onnxruntime-web) but **not in OpenVINO**, which
   failed to convert them.
4. **Pin the tokenizer.** Ship `tokenizer.json` with the model and check the runtime tokenizer gives identical ids and
   offsets to the training tokenizer (we checked `tokenizers` vs `transformers` on all eval articles).
5. **Expect small cross-host drift.** int8 predictions differed by up to .011 between Kaggle CPU hosts; compare
   models on the same host.
6. **Check the chip.** int8 gains depend on VNNI/AVX-512/AMX. On a Kaggle Xeon without VNNI, int8 still beat fp32
   in ORT but was slower than fp32 in OpenVINO. Record CPU flags with every speed number.
7. **Record the sha** of the final file in the model card; every later report cites it.

## Done when

int8 file, sha, dev agreement with fp32 per layer, fused-op list and CPU flags are recorded.
