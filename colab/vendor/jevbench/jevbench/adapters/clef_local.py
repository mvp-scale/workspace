"""Clef Flash (Cloudflare) adapter: open weights loaded in-process with the author's `joint_schema_model.py`.

Interface (https://huggingface.co/Cloudflare/clef-flash, read 2026-10-06):
  model, processor = load_release_model(<snapshot dir>, device="cuda")     # Qwen3.5-9B backbone + joint schema head
  systemone(model, processor, {"state", "questions"})                      # Jev / SystemOne request and response bodies
Questions go in unchanged and answers come back in Jev's shape, so every JevBench record maps 1:1:
  noul   answer["noul"] = P(true)            -> {"yes": p, "no": 1-p}
  choice answer["probabilities"]            -> used as-is (keys = options)
  score  answer["probabilities"]            -> used as-is (keys = level indices)
Probabilities are the model's own softmax over each question's option logits (native); no generation, no parsing.

Requests are batched: `run()` is thread-safe, and concurrent callers are gathered by a MicroBatcher into padded batches
through the card's own `collate_records` (one forward pass per batch). With one caller it degenerates to batches of 1.
The model's answers do not depend on batching beyond bf16 rounding; tests/test_batching.py and the serial-vs-batched
comparison in the add-model skill check that. Env: CLEF_MAX_BATCH (items, default 32), CLEF_MAX_BATCH_TOKENS (padded
tokens per batch, default 32768).

Local weights have no provider tariff: price is null here and estimated later by size class, never 0.
"""

from __future__ import annotations

import os
import sys
import threading
import time

from ..batching import MicroBatcher
from .base import DecisionResult, build_question


class ClefLocalAdapter:
    name = "clef_local"
    cost_basis = "local_gpu_no_provider_tariff"
    thread_safe = True  # serve_inproc.py and the concurrent runner may call run() from many threads
    accepts_images = True  # answer_request() takes `images` (data URLs); run() stays text-only for the benchmark tasks

    def __init__(self, endpoint=None, model=None, key_env="", timeout_s=None,
                 price_input_per_m=None, price_output_per_m=None, device="cuda", revision=None):
        self.path = endpoint  # local snapshot of Cloudflare/clef-flash
        self.model = model or "Cloudflare/clef-flash"
        self.key_env = key_env
        self.price_input_per_m = price_input_per_m
        self.price_output_per_m = price_output_per_m
        self.device = device
        self.revision = revision
        self._loaded = None
        self._load_lock = threading.Lock()
        self._tok_lock = threading.Lock()
        self.batch_stats = []  # (items, padded_tokens, seconds) per forward pass

    def load(self):
        with self._load_lock:
            if self._loaded is None:
                if self.path not in sys.path:
                    sys.path.insert(0, self.path)  # the snapshot ships joint_schema_model.py next to the weights
                import torch
                import joint_schema_model as jsm

                model, processor = jsm.load_release_model(self.path, device=self.device)
                self._jsm, self._torch = jsm, torch
                self._batcher = MicroBatcher(self._forward, max_batch=int(os.environ.get("CLEF_MAX_BATCH", 32)),
                                             max_tokens=int(os.environ.get("CLEF_MAX_BATCH_TOKENS", 32768)),
                                             on_batch=lambda *a: self.batch_stats.append(a), name="clef-batcher")
                self._loaded = (model, processor)
        return self._loaded

    def _forward(self, encoded):
        """One padded forward pass over a list of encoded records; one answers dict per record."""
        jsm, torch = self._jsm, self._torch
        model, processor = self._loaded
        device = next(model.parameters()).device
        with torch.inference_mode():
            logits = model(jsm.collate_records(encoded, processor.tokenizer.pad_token_id, device))
        out = []
        for enc, rec_logits in zip(encoded, logits):
            out.append({q.question_id: dict(zip(q.option_ids, ql.float().softmax(-1).tolist())) for q, ql in zip(enc.questions, rec_logits)})
        return out

    @staticmethod
    def _decode_images(urls):
        """Data URLs (`data:image/...;base64,...`, the same field llama-server's /v1/systemone takes) to PIL images."""
        import base64
        import io

        from PIL import Image

        out = []
        for u in urls:
            if not isinstance(u, str) or not u.startswith("data:") or ";base64," not in u:
                raise ValueError("images must be data URLs (data:image/...;base64,...)")
            out.append(Image.open(io.BytesIO(base64.b64decode(u.split(";base64,", 1)[1]))).convert("RGB"))
        return out

    def answer_request(self, body):
        """A whole /v1/systemone request: every question decided jointly in one pass (as the model is built to), optional `images`."""
        self.load()
        return self._answer(body)

    def _answer(self, body):
        """The card's systemone(), with the forward pass going through the batcher."""
        jsm = self._jsm
        _, processor = self._loaded
        if body.get("images"):
            body = {**body, "images": self._decode_images(body["images"])}
        if "videos" in body:
            raise ValueError("videos are not wired into this adapter yet")
        with self._tok_lock:  # tokenizers are not safe to share across threads
            enc = jsm.encode_record(processor.tokenizer, body, max_length=16384, processor=processor)
        probs = self._batcher.submit(enc, size=len(enc.input_ids)).result()
        answers = {qid: jsm.systemone_answer(body["questions"][qid], p) for qid, p in probs.items()}
        return {"model": body["model"], "answers": answers, "usage": {"input_tokens": len(enc.input_ids), "output_tokens": 0}}

    def build_request(self, task) -> dict:
        return {"model": "clef-flash", "state": task.state, "questions": {"decision": build_question(task)}}

    def run(self, task) -> DecisionResult:
        res = DecisionResult(adapter=self.name, ok=False, probs_source="native", model=self.model)
        body = self.build_request(task)
        res.request_body = body
        try:
            self.load()
        except Exception as e:  # noqa: BLE001 - a failed load is a failed attempt
            res.error = f"load failed: {type(e).__name__}: {str(e)[:250]}"
            return res
        t0 = time.perf_counter()
        try:
            out = self._answer(body)
        except Exception as e:  # noqa: BLE001
            res.latency_s = time.perf_counter() - t0
            res.error = f"{type(e).__name__}: {str(e)[:300]}"
            return res
        res.latency_s = time.perf_counter() - t0
        res.raw = {"response": out, "runtime": {"device": self.device, "revision": self.revision,
                                                "probability_origin": "native-softmax"}}
        res.usage = dict((out or {}).get("usage") or {})
        ans = ((out or {}).get("answers") or {}).get("decision")
        try:
            if not isinstance(ans, dict) or ans.get("type") != task.question["type"]:
                raise ValueError("missing or mistyped answers.decision")
            if task.question["type"] == "noul":
                p = float(ans["noul"])
                if not (0.0 <= p <= 1.0):
                    raise ValueError(f"noul out of range: {p}")
                res.probs = {"yes": p, "no": 1.0 - p}
            else:
                probs = ans["probabilities"]
                if not isinstance(probs, dict):
                    raise ValueError("missing probabilities")
                res.probs = {str(k): float(v) for k, v in probs.items()}
        except (KeyError, TypeError, ValueError) as e:
            res.error = f"answer parse failed: {e}"
            return res
        res.ok = True
        return res

    def reserve_estimate(self, task) -> float:
        return 0.0
