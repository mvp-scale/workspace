"""The HTTP API and the control panel.

Public:   GET /  (the panel), GET /healthz
Key:      GET  /v1/models /v1/stats /v1/tunnel
          POST /v1/systemone  /admin/select  /admin/unload  /admin/enable  /admin/tunnel
The key is "Authorization: Bearer <key>" or "X-API-Key: <key>". Every response carries X-Request-Id and X-Gateway-Version.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__
from .manager import Gateway, Refused
from .tunnel import Tunnel

HERE = Path(__file__).resolve().parent
MAX_BODY = 32 * 1024 * 1024  # a few base64 images
PUBLIC = {("GET", "/"), ("GET", "/healthz")}


class RateLimit:
    """A token bucket: `per_minute` requests a minute, bursting up to `burst`. per_minute=0 turns it off."""

    def __init__(self, per_minute: int, burst: int | None = None):
        self.rate, self.burst = per_minute / 60.0, float(burst or max(per_minute // 6, 1))
        self.tokens, self.last, self._lock = self.burst, time.monotonic(), threading.Lock()

    def take(self) -> float:
        """0 if allowed, else seconds to wait."""
        if not self.rate:
            return 0.0
        with self._lock:
            now = time.monotonic()
            self.tokens = min(self.burst, self.tokens + (now - self.last) * self.rate)
            self.last = now
            if self.tokens >= 1:
                self.tokens -= 1
                return 0.0
            return (1 - self.tokens) / self.rate


class App:
    """Everything a request handler needs."""

    def __init__(self, gateway: Gateway, key: str, tunnel: Tunnel | None = None, work: str | None = None,
                 max_inflight: int = 64, per_minute: int = 600):  # fmt: skip
        self.gw, self.key, self.tunnel = gateway, key, tunnel
        self.started = time.time()
        self.inflight = threading.BoundedSemaphore(max_inflight)
        self.limit = RateLimit(per_minute)
        self.panel = (HERE / "ui" / "index.html").read_bytes()
        self.access_log = Path(work) / "requests.jsonl" if work else None
        self._log_lock = threading.Lock()

    def record(self, entry: dict) -> None:
        """One JSON line per request: no bodies, so nothing a caller sent is stored."""
        if self.access_log:
            with self._log_lock, open(self.access_log, "a") as out:
                out.write(json.dumps(entry) + "\n")


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        # -- plumbing ------------------------------------------------------------------------------------------------

        def _send(self, status: int, body, extra: dict | None = None, ctype: str = "application/json") -> None:
            raw = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            headers = {
                "Content-Type": ctype,
                "Content-Length": str(len(raw)),
                "X-Request-Id": self.rid,
                "X-Gateway-Version": __version__,
                "X-Model": str(app.gw.cur_id),
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, X-API-Key, X-Request-Id",
                "Access-Control-Expose-Headers": "X-Latency-Ms, X-Model, X-Request-Id",
                **(extra or {}),
            }
            if self.command == "POST" and not self.body_read:
                headers["Connection"] = "close"  # an unread body would corrupt the next request on this connection
                self.close_connection = True
            for name, value in headers.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(raw)
            self.status = status

        def _authed(self) -> bool:
            token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip() or self.headers.get("X-API-Key", "")
            return secrets.compare_digest(token.encode(), app.key.encode())

        def _read(self) -> bytes | None:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                self._send(413, {"error": f"body over {MAX_BODY // 2**20} MB"})
                return None
            self.body_read = True
            return self.rfile.read(length)

        def _json(self, body: bytes) -> dict:
            try:
                data = json.loads(body or b"{}")
            except ValueError:
                raise Refused("body is not valid JSON", 400) from None
            if not isinstance(data, dict):
                raise Refused("body must be a JSON object", 400)
            return data

        def _dispatch(self, method: str) -> None:
            self.rid = (self.headers.get("X-Request-Id") or "")[:64] or uuid.uuid4().hex[:12]
            self.status, self.model, self.body_read, started = 0, None, False, time.perf_counter()
            path = self.path.split("?")[0]
            try:
                if method == "OPTIONS":
                    return self._send(204, b"", {"Access-Control-Allow-Methods": "GET, POST, OPTIONS"})
                route = ROUTES.get((method, path))
                if route is None:
                    return self._send(404, {"error": "not found"})
                if (method, path) not in PUBLIC and not self._authed():
                    return self._send(401, {"error": "missing or wrong API key (Authorization: Bearer <key>)"})
                body = self._read() if method == "POST" else b""
                if body is None:
                    return None
                getattr(self, route)(body)
            except Refused as err:
                self._send(err.status, {"error": str(err)})
            except KeyError as err:
                self._send(404, {"error": f"unknown model {err}", "models": list(app.gw.models)})
            except Exception as err:  # a failed load or a bug: tell the caller, keep serving
                self._send(500, {"error": f"{type(err).__name__}: {err}"[:1500]})
            finally:
                app.record({"ts": round(time.time(), 3), "id": self.rid, "method": method, "path": path, "status": self.status,
                            "ms": round((time.perf_counter() - started) * 1000, 1), "model": self.model,
                            "ip": self.headers.get("CF-Connecting-IP") or self.client_address[0]})  # fmt: skip

        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

        def do_OPTIONS(self):
            self._dispatch("OPTIONS")

        def log_message(self, *args):
            pass

        # -- routes --------------------------------------------------------------------------------------------------

        def panel(self, _body):
            self._send(200, app.panel, ctype="text/html; charset=utf-8")

        def health(self, _body):
            gw = app.gw
            self._send(200 if gw.cur else 503, {"ok": bool(gw.cur), "loaded": gw.cur_id, "loading": gw.loading})

        def models(self, _body):
            self._send(200, app.gw.status())

        def stats(self, _body):
            self._send(200, {"version": __version__, "up_s": round(time.time() - app.started), "stats": app.gw.stats.snapshot()})

        def tunnel_status(self, _body):
            self._send(200, app.tunnel.status() if app.tunnel else {"running": False, "available": False})

        def systemone(self, body):
            wait = app.limit.take()
            if wait:
                return self._send(429, {"error": "rate limit"}, {"Retry-After": str(max(1, round(wait)))})
            if not app.inflight.acquire(blocking=False):
                return self._send(429, {"error": "too many requests in flight"}, {"Retry-After": "1"})
            try:
                started = time.perf_counter()
                status, out, self.model = app.gw.answer(body)
                extra = (
                    {"Retry-After": "10"} if status == 503 else {"X-Latency-Ms": f"{(time.perf_counter() - started) * 1000:.1f}"}
                )
                self._send(status, out, extra)
            finally:
                app.inflight.release()

        def select(self, body):
            app.gw.select(str(self._json(body).get("model", "")))
            self._send(200, app.gw.status())

        def unload(self, _body):
            app.gw.unload()
            self._send(200, app.gw.status())

        def enable(self, body):
            data = self._json(body)
            app.gw.set_enabled(str(data.get("model", "")), bool(data.get("enabled", True)))
            self._send(200, app.gw.status())

        def tunnel_action(self, body):
            if not app.tunnel:
                raise Refused("this gateway was started without tunnel support", 404)
            action = self._json(body).get("action")
            if action not in ("start", "stop"):
                raise Refused('action must be "start" or "stop"', 400)
            try:
                self._send(200, app.tunnel.start() if action == "start" else app.tunnel.stop())
            except RuntimeError as err:
                raise Refused(str(err), 502) from None

    ROUTES = {
        ("GET", "/"): "panel", ("GET", "/healthz"): "health", ("GET", "/v1/models"): "models", ("GET", "/v1/stats"): "stats",
        ("GET", "/v1/tunnel"): "tunnel_status", ("POST", "/v1/systemone"): "systemone", ("POST", "/admin/select"): "select",
        ("POST", "/admin/unload"): "unload", ("POST", "/admin/enable"): "enable", ("POST", "/admin/tunnel"): "tunnel_action",
    }  # fmt: skip
    return Handler


def serve(app: App, port: int, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    """Start the server on a background thread and return it (call .shutdown() to stop)."""
    server = ThreadingHTTPServer((host, port), make_handler(app))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True, name="http").start()
    return server
