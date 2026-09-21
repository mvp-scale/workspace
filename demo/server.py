"""Local demo: benchmark results viewer + live side-by-side compare of jeff, kev and hosted Jev.

    TYPESAFE_API_KEY=... python3 demo/server.py      # then open http://127.0.0.1:8100

The TypeSafe key stays server-side. Binds to 127.0.0.1 by default; set DEMO_HOST to expose it
(anyone who can reach the port can spend the key).
"""
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
BENCH = Path(os.environ.get("BENCH_DIR", HERE.parent / "data" / "bench"))
BACKENDS = {
    "jeff": {"url": os.environ.get("JEFF_URL", "http://127.0.0.1:8000"), "key": os.environ.get("JEFF_API_KEYS", "devkey").split(",")[0]},
    "kev": {"url": os.environ.get("KEV_URL", "http://127.0.0.1:8009"), "key": ""},
    "jev (typesafe)": {"url": os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai"), "key": os.environ.get("TYPESAFE_API_KEY", "")},
}


def call(name, cfg, body):
    if name.startswith("jev") and not cfg["key"]:
        return {"backend": name, "error": "TYPESAFE_API_KEY not set"}
    headers = {"Content-Type": "application/json", "User-Agent": "jev-demo/0.1"}
    if cfg["key"]:
        headers["Authorization"] = f"Bearer {cfg['key']}"
    req = urllib.request.Request(cfg["url"].rstrip("/") + "/v1/systemone", json.dumps(body).encode(), headers)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data, status = json.load(r), r.status
    except urllib.error.HTTPError as e:
        return {"backend": name, "error": f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"}
    except Exception as e:  # connection refused, timeout, bad JSON
        return {"backend": name, "error": f"{type(e).__name__}: {e}"}
    return {"backend": name, "status": status, "latency_ms": round((time.perf_counter() - t0) * 1000),
            "model": data.get("model"), "answer": (data.get("answers") or {}).get("decision")}


def results():
    out = []
    for p in sorted(BENCH.glob("*/summary.json")):
        s = json.loads(p.read_text())
        out.append({"run": p.parent.name, "accuracy": s["accuracy"], "ece": (s.get("ece") or {}).get("ece"),
                    "schema_validity": s["schema_validity"], "n": s["n_planned"],
                    "families": {k: v["accuracy"] for k, v in s["per_family"].items()}})
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/":
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/results":
            self._send(200, results())
        elif self.path == "/api/backends":
            self._send(200, {n: {"url": c["url"], "has_key": bool(c["key"]) or not n.startswith("jev")} for n, c in BACKENDS.items()})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/compare":
            return self._send(404, {"error": "not found"})
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            body = {"state": req["state"], "model": "jev-latest", "questions": {"decision": req["question"]}}
        except (ValueError, KeyError):
            return self._send(400, {"error": "need JSON {state, question}"})
        with ThreadPoolExecutor(len(BACKENDS)) as ex:
            futs = [ex.submit(call, n, c, body) for n, c in BACKENDS.items()]
            self._send(200, [f.result() for f in futs])

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    host, port = os.environ.get("DEMO_HOST", "127.0.0.1"), int(os.environ.get("DEMO_PORT", "8100"))
    print(f"demo on http://{host}:{port}  (typesafe key: {'set' if BACKENDS['jev (typesafe)']['key'] else 'MISSING'})")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
