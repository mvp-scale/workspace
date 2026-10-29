# 09 · Ship and monitor

**Goal:** a model others can run and trust, and a way to notice when it stops being right.

## Rules

1. **Ship one entry point + pinned environment.** Kit: `kit/student/runtime.py` + `kit/student/ship_check.py` (text in, spans JSON out;
   `--jsonl --workers 4` for batches), `requirements.txt` pinned, a lock file from a clean venv, model file by sha.
   Test it from a clean environment before calling it shipped (T65, T67).
2. **Same file, many runtimes.** The int8 ONNX runs in Python ORT on servers and in browsers via onnxruntime-web
   (single-thread WebAssembly). The browser path allows local-only processing of private text. Port the tokenizer
   and decoding exactly, then check outputs match the Python engine on fixed examples.
3. **Output contract.** Emit character offsets into the original text and the model sha with every result, so any
   downstream claim traces back to a span and a model version (PRD v0.2, B2).
4. **Shadow before replace.** Run a new model beside the old one on live input and compare before switching.
5. **Monitor drift cheaply.** Track per-layer counts per 1,000 items and the share of low-margin decisions; route a
   small weekly sample to teacher re-labelling and compare. A jump means re-check, not auto-retrain.
6. **Release decisions are the owner's.** Weights trained on copyrighted text: confirm before public release or a
   public model card.

## Done when

Clean-environment test passes, model card is filled, and a monitoring sample is scheduled.
