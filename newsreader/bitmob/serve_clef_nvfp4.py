#!/usr/bin/env python3
"""Clef Flash Fast (NVFP4 on vLLM, id clef-flash-nvfp4, code CLF9F4) as a TypeSafe-shaped server for the benchmark adapter.
  /workspace/models/cygnet-venv/bin/python newsreader/bitmob/serve_clef_nvfp4.py [--port 8038] [--util 0.6]
POST /v1/systemone {model, state, questions:{id:{type noul|choice|score, instructions, criteria}}} -> {model, answers, usage} exactly as clef_vllm.ClefVLLM.systemone answers (same encode, same hidden states, same decide, same systemone_answer).
Concurrency: requests from many threads are collected by one worker, which runs ONE vLLM pooling call for up to --batch requests (as clef_two_step.py run() does), then decides each. GET /health.
Needs the GPU alone with the regular Clef: use newsreader/bitmob/serve_clef_nvfp4.sh start|stop (pauses :8018, always resumes it)."""
import os, sys, json, time, queue, threading, argparse
MP = "/workspace/data/models/clef-flash-nvfp4-alpha"; os.environ["CLEF_MODEL_PATH"] = MP; sys.path.insert(0, MP)
ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8038); ap.add_argument("--util", type=float, default=0.6); ap.add_argument("--batch", type=int, default=16); ap.add_argument("--wait_ms", type=int, default=15); a = ap.parse_args()
import torch
from clef_vllm import ClefVLLM
from joint_schema_model import systemone_answer
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
clef = ClefVLLM(MP, gpu_memory_utilization=a.util); Q = queue.Queue(); STATS = {"requests": 0, "batches": 0, "errors": 0, "started": time.time(), "model": "clef-flash-nvfp4"}


def validate(body):
    qs = body.get("questions")
    if not isinstance(body.get("model"), str) or "state" not in body: raise ValueError("model and state are required")
    if not isinstance(qs, dict) or not qs: raise ValueError("at least one question is required")
    for k, q in qs.items():
        if q.get("type") not in ("noul", "choice", "score"): raise ValueError(f"{k}: type must be noul, choice, or score")
        if q["type"] != "noul" and not q.get("criteria"): raise ValueError(f"{k}: criteria must not be empty")


def worker():
    while True:
        items = [Q.get()]; t_end = time.time() + a.wait_ms / 1000
        while len(items) < a.batch and time.time() < t_end:
            try: items.append(Q.get(timeout=max(t_end - time.time(), 0.001)))
            except queue.Empty: break
        ok = []
        for it in items:
            try: it["enc"] = clef.encode(it["body"]); ok.append(it)
            except Exception as e: it["err"] = str(e); it["ev"].set()
        if not ok: continue
        try:
            with torch.inference_mode():
                outs = clef.llm.encode([clef._prompt(it["body"], it["enc"]) for it in ok], pooling_task="token_embed", use_tqdm=False)
                for it, o in zip(ok, outs):
                    try:
                        h = o.outputs.data.to(clef.device, torch.bfloat16)
                        if h.shape[0] != len(it["enc"].input_ids): raise RuntimeError("vLLM position mismatch")
                        pr = clef.decide(it["enc"], h); qs = it["body"]["questions"]
                        it["out"] = {"model": it["body"]["model"], "answers": {q: systemone_answer(qs[q], p) for q, p in pr.items()}, "usage": {"input_tokens": len(it["enc"].input_ids), "output_tokens": 0}}
                    except Exception as e: it["err"] = str(e)
        except Exception as e:
            for it in ok: it["err"] = str(e)
        STATS["batches"] += 1
        for it in ok: it["ev"].set()


class H(BaseHTTPRequestHandler):
    def log_message(self, *x): pass
    def _send(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path.startswith("/health"): return self._send(200, {"status": "ok", **{k: v for k, v in STATS.items() if k != "started"}, "uptime_s": round(time.time() - STATS["started"])})
        self._send(404, {"error": "not found"})
    def do_POST(self):
        if not self.path.startswith("/v1/systemone"): return self._send(404, {"error": "not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)))); validate(body)
        except Exception as e: return self._send(400, {"error": str(e)})
        it = {"body": body, "ev": threading.Event()}; Q.put(it); it["ev"].wait(600); STATS["requests"] += 1
        if "out" in it: return self._send(200, it["out"])
        STATS["errors"] += 1; self._send(500, {"error": it.get("err", "timeout")})


threading.Thread(target=worker, daemon=True).start()
print(f"serving clef-flash-nvfp4 on 127.0.0.1:{a.port}", flush=True)
ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
