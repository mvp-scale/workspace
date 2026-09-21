"""Serve an in-process model as a TypeSafe-compatible /v1/systemone endpoint.

SemIf, open-alternative-jev, Laya and Verdict only ran in-process during benchmarks. This wraps the SAME jevbench adapter
that produced each model's benchmark numbers, so what answers live is what was measured. Standard library only, so it
runs in each model's own venv. Inference is serialised with a lock: these adapters are not thread-safe.

    /workspace/models/semif/.venv/bin/python demo/serve_inproc.py --model semif --port 8012

Endpoints: POST /v1/systemone, GET /v1/models (real identity of what is loaded), GET /healthz.
"""
import argparse, json, os, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "jevbench"))
from jevbench.tasks import Task  # noqa: E402


def snapshot(repo_dir):
    return sorted((ROOT / "data/models/hf-cache/hub" / repo_dir / "snapshots").iterdir())[0].name


def make(model):
    """Adapter and a description of what is really loaded."""
    if model == "semif":
        from jevbench.adapters.semif_direct import SemIfDirectAdapter
        rev = snapshot("models--Qwen--Qwen3.5-4B")
        return SemIfDirectAdapter(endpoint="Qwen/Qwen3.5-4B", revision=rev), {"base": "Qwen/Qwen3.5-4B (frozen, BF16)", "revision": rev, "readout": "answer-letter logits"}
    if model == "so1":
        from jevbench.adapters.so1_decider import So1DeciderAdapter
        return So1DeciderAdapter(), {"base": "Qwen/Qwen3.5-4B (frozen, BF16)", "readout": "option logits, questions scored separately"}
    if model == "laya":
        from jevbench.adapters.laya_local import LayaLocalAdapter
        return LayaLocalAdapter(endpoint=str(ROOT / "data/models/laya")), {"base": "ModernBERT-large 421M", "readout": "option markers"}
    if model == "verdict":
        from jevbench.adapters.verdict_local import VerdictLocalAdapter
        return VerdictLocalAdapter(endpoint=str(ROOT / "data/models/verdict")), {"base": "GLiClass ModernBERT-base 151M (CPU)", "readout": "option head with abstention slot"}
    raise SystemExit(f"unknown model {model}")


def to_task(qid, state, q):
    kind, crit = q["type"], q.get("criteria")
    labels = ["no", "yes"] if kind == "noul" else list(crit) if kind == "choice" else [str(i) for i in range(len(crit))]
    return Task(id=qid, family="serve", state=state, question=q, labels=labels, expected=None, split="public")


def confidence(probs):
    n = len(probs)
    return 1.0 if n < 2 else (max(probs.values()) - 1 / n) / (1 - 1 / n)


def answer(q, probs):
    kind = q["type"]
    if kind == "noul":
        return {"type": "noul", "noul": probs["yes"]}
    p = {k: round(v, 4) for k, v in probs.items()}
    if kind == "choice":
        return {"type": "choice", "choice": max(probs, key=probs.get), "confidence": round(confidence(probs), 4), "probabilities": p}
    return {"type": "score", "score": round(sum(int(k) * v for k, v in probs.items()), 4), "confidence": round(confidence(probs), 4),
            "legend": {str(i): lv for i, lv in enumerate(q["criteria"])}, "probabilities": p}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=["semif", "so1", "laya", "verdict"])
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    adapter, identity = make(a.model)
    t0 = time.time(); adapter.load(); print(f"{a.model} loaded in {time.time() - t0:.1f}s", flush=True)
    lock = threading.Lock()

    class H(BaseHTTPRequestHandler):
        def _send(self, code, body):
            raw = json.dumps(body).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

        def do_GET(self):
            if self.path.startswith("/healthz"):
                self._send(200, {"ok": True, "model": a.model})
            elif self.path.startswith("/v1/models"):
                self._send(200, {"models": [{"id": a.model, "aliases": ["jev-latest"], "run": f"jevbench adapter {type(adapter).__name__}", **identity}]})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/v1/systemone":
                return self._send(404, {"error": "not found"})
            try:
                req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                state, questions = req["state"], req["questions"]
                assert isinstance(questions, dict) and questions
            except (ValueError, KeyError, AssertionError):
                return self._send(422, {"error": "need {state, questions:{id: question}}"})
            t = time.perf_counter(); answers, tokens = {}, 0
            try:
                with lock:
                    for qid, q in questions.items():
                        res = adapter.run(to_task(qid, state, q))
                        if not res.ok:
                            return self._send(500, {"error": res.error or "model could not answer"})
                        answers[qid] = answer(q, res.probs); tokens += int((res.usage or {}).get("input_tokens", 0))
            except Exception as e:  # malformed question, model error
                return self._send(500, {"error": f"{type(e).__name__}: {e}"})
            self._send(200, {"model": a.model, "answers": answers, "usage": {"input_tokens": tokens, "output_tokens": len(answers)}, "latency_ms": round((time.perf_counter() - t) * 1000, 1)})

        def log_message(self, *args):
            pass

    print(f"serving {a.model} on {a.host}:{a.port}", flush=True)
    ThreadingHTTPServer((a.host, a.port), H).serve_forever()


if __name__ == "__main__":
    main()
