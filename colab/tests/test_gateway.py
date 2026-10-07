"""The gateway end to end against a fake model server: no GPU, no downloads."""

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from jevgw import catalog, manager
from jevgw.backends import KINDS
from jevgw.server import App, serve

KEY = "test-key"


class FakeServer:
    """Stands in for llama-server / a recipe process. Records what the gateway did to it."""

    started, stopped, gate = [], [], None

    def __init__(self, entry, cfg):
        self.entry = entry

    def start(self):
        FakeServer.started.append(self.entry["id"])

    def warm(self):
        return 1.0

    def answer(self, body):
        if FakeServer.gate:
            FakeServer.gate.wait(5)
        return 200, json.dumps({"answers": {"echo": {"model": self.entry["id"], "bytes": len(body)}}}).encode()

    def stop(self):
        FakeServer.stopped.append(self.entry["id"])


MODELS = {
    "small": {"id": "small", "name": "Small", "kind": "proc", "cmd": ["x"], "vram_gib": 4, "vision": False},
    "other": {"id": "other", "name": "Other", "kind": "proc", "cmd": ["x"], "vram_gib": 6, "vision": True},
    "huge": {"id": "huge", "name": "Huge", "kind": "proc", "cmd": ["x"], "vram_gib": 40},
    "later": {"id": "later", "name": "Later", "kind": "pending", "status": "recipe not written yet"},
}


class Base(unittest.TestCase):
    per_minute, max_inflight = 0, 64

    def setUp(self):
        FakeServer.started, FakeServer.stopped, FakeServer.gate = [], [], None
        self.work = tempfile.TemporaryDirectory()
        patches = [
            mock.patch.dict(KINDS, {"proc": FakeServer}),
            mock.patch.object(catalog, "gpu_info", lambda: ("Test GPU", 16 * 1024)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.gw = manager.Gateway(dict(MODELS), {"work": self.work.name})
        self.app = App(self.gw, KEY, None, self.work.name, self.max_inflight, self.per_minute)
        self.server = serve(self.app, 0)
        self.port = self.server.server_address[1]
        self.addCleanup(self.work.cleanup)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.gw.shutdown)

    def call(self, method, path, body=None, key=KEY, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Content-Type": "application/json", **(headers or {})}
        if key:
            h["Authorization"] = f"Bearer {key}"
        conn.request(method, path, json.dumps(body) if body is not None else None, h)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        try:
            data = json.loads(raw)
        except ValueError:
            data = raw
        return response.status, data, response


class TestAuthAndPlumbing(Base):
    def test_key_required_except_panel_and_health(self):
        self.assertEqual(self.call("GET", "/v1/models", key=None)[0], 401)
        self.assertEqual(self.call("GET", "/v1/models", key="wrong")[0], 401)
        self.assertEqual(self.call("POST", "/v1/systemone", {}, key="wrong")[0], 401)
        self.assertEqual(self.call("GET", "/v1/models")[0], 200)
        status, _, response = self.call("GET", "/", key=None)
        self.assertEqual((status, response.getheader("Content-Type")), (200, "text/html; charset=utf-8"))
        self.assertEqual(self.call("GET", "/healthz", key=None)[0], 503)  # nothing loaded yet

    def test_panel_is_not_served_through_the_tunnel(self):
        self.assertEqual(self.call("GET", "/", key=None)[0], 200)
        for header in ("Cf-Ray", "Cf-Connecting-Ip"):
            self.assertEqual(self.call("GET", "/", key=None, headers={header: "x"})[0], 404)
        self.assertEqual(self.call("GET", "/v1/models", headers={"Cf-Ray": "x"})[0], 200)  # the API still works through it

    def test_x_api_key_header_also_works(self):
        status, _, _ = self.call("GET", "/v1/models", key=None, headers={"X-API-Key": KEY})
        self.assertEqual(status, 200)

    def test_cors_preflight_and_headers(self):
        status, _, response = self.call("OPTIONS", "/v1/systemone", key=None)
        self.assertEqual(status, 204)
        self.assertEqual(response.getheader("Access-Control-Allow-Origin"), "*")
        self.assertIn("Authorization", response.getheader("Access-Control-Allow-Headers"))

    def test_request_id_is_echoed_or_made_and_version_sent(self):
        _, _, response = self.call("GET", "/healthz", key=None, headers={"X-Request-Id": "abc123"})
        self.assertEqual(response.getheader("X-Request-Id"), "abc123")
        self.assertTrue(self.call("GET", "/healthz", key=None)[2].getheader("X-Request-Id"))
        self.assertTrue(self.call("GET", "/healthz", key=None)[2].getheader("X-Gateway-Version"))

    def test_unknown_route_and_bad_json(self):
        self.assertEqual(self.call("GET", "/nope")[0], 404)
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        self.addCleanup(conn.close)
        conn.request("POST", "/admin/select", "{not json", {"Authorization": f"Bearer {KEY}"})
        self.assertEqual(conn.getresponse().status, 400)

    def test_rejected_post_does_not_corrupt_the_next_request_on_the_connection(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        self.addCleanup(conn.close)
        conn.request("POST", "/v1/systemone", json.dumps({"state": "x" * 5000}), {"Authorization": "Bearer wrong"})
        first = conn.getresponse()
        first.read()
        self.assertEqual(first.status, 401)
        conn.request("GET", "/v1/models", headers={"Authorization": f"Bearer {KEY}"})
        self.assertEqual(conn.getresponse().status, 200)


class TestModels(Base):
    def test_load_serve_switch_unload(self):
        status, body, _ = self.call("POST", "/admin/select", {"model": "small"})
        self.assertEqual((status, body["loaded"]), (200, "small"))
        self.assertEqual(self.call("GET", "/healthz", key=None)[0], 200)
        status, body, response = self.call("POST", "/v1/systemone", {"state": "s", "questions": {}})
        self.assertEqual(status, 200)
        self.assertEqual((response.getheader("X-Model"), body["answers"]["echo"]["model"]), ("small", "small"))
        self.assertIsNotNone(response.getheader("X-Latency-Ms"))
        self.call("POST", "/admin/select", {"model": "other"})
        self.assertEqual(FakeServer.stopped, ["small"])  # one model at a time: the old one went first
        self.assertEqual(self.call("POST", "/admin/unload", {})[1]["loaded"], None)
        status, _, response = self.call("POST", "/v1/systemone", {})
        self.assertEqual((status, response.getheader("Retry-After")), (503, "10"))

    def test_refusals(self):
        self.assertEqual(self.call("POST", "/admin/select", {"model": "huge"})[0], 409)  # 40 GiB on a 16 GiB GPU
        self.assertEqual(self.call("POST", "/admin/select", {"model": "later"})[0], 422)
        self.assertEqual(self.call("POST", "/admin/select", {"model": "nope"})[0], 404)
        self.assertEqual(FakeServer.started, [])  # nothing was attempted

    def test_disable_blocks_load_and_unloads_a_loaded_model(self):
        self.call("POST", "/admin/enable", {"model": "other", "enabled": False})
        self.assertEqual(self.call("POST", "/admin/select", {"model": "other"})[0], 403)
        self.call("POST", "/admin/select", {"model": "small"})
        status, body, _ = self.call("POST", "/admin/enable", {"model": "small", "enabled": False})
        self.assertEqual((status, body["loaded"]), (200, None))
        self.call("POST", "/admin/enable", {"model": "small", "enabled": True})
        self.assertEqual(self.call("POST", "/admin/select", {"model": "small"})[0], 200)

    def test_failed_load_is_reported_and_leaves_nothing_loaded(self):
        with mock.patch.object(FakeServer, "start", side_effect=RuntimeError("boom")):
            status, body, _ = self.call("POST", "/admin/select", {"model": "small"})
        self.assertEqual(status, 500)
        self.assertIn("boom", body["error"])
        state = self.call("GET", "/v1/models")[1]
        self.assertIsNone(state["loaded"])
        self.assertIn("boom", state["error"])

    def test_status_lists_fit_enabled_and_loaded(self):
        self.call("POST", "/admin/select", {"model": "small"})
        models = {m["id"]: m for m in self.call("GET", "/v1/models")[1]["models"]}
        self.assertEqual((models["small"]["loaded"], models["small"]["fits"]), (True, True))
        self.assertFalse(models["huge"]["fits"])
        self.assertFalse(models["later"]["runnable"])

    def test_only_disables_everything_else(self):
        gw = manager.Gateway(dict(MODELS), {"work": self.work.name}, only={"small"})
        self.addCleanup(gw.shutdown)
        self.assertEqual(gw.disabled, {"other", "huge", "later"})


class TestLimits(Base):
    per_minute, max_inflight = 6, 1

    def test_rate_limit_answers_429_with_retry_after(self):
        self.call("POST", "/admin/select", {"model": "small"})
        codes = [self.call("POST", "/v1/systemone", {})[0] for _ in range(4)]
        self.assertEqual(codes[0], 200)
        self.assertIn(429, codes)
        status, _, response = self.call("POST", "/v1/systemone", {})
        self.assertEqual(status, 429)
        self.assertGreaterEqual(int(response.getheader("Retry-After")), 1)

    def test_in_flight_cap(self):
        self.app.limit.rate = 0  # isolate the cap from the rate limit
        self.call("POST", "/admin/select", {"model": "small"})
        FakeServer.gate = threading.Event()
        first = []
        worker = threading.Thread(target=lambda: first.append(self.call("POST", "/v1/systemone", {})[0]))
        worker.start()
        for _ in range(50):  # wait until the first call holds the slot
            if not self.app.inflight.acquire(blocking=False):
                break
            self.app.inflight.release()
            threading.Event().wait(0.02)
        self.assertEqual(self.call("POST", "/v1/systemone", {})[0], 429)
        FakeServer.gate.set()
        worker.join(5)
        self.assertEqual(first, [200])


class TestObservability(Base):
    def test_stats_and_access_log_without_bodies(self):
        self.call("POST", "/admin/select", {"model": "small"})
        for _ in range(3):
            self.call("POST", "/v1/systemone", {"state": "a secret the log must not keep"})
        stats = self.call("GET", "/v1/stats")[1]["stats"]["small"]
        self.assertEqual((stats["requests"], stats["errors"]), (3, 0))
        self.assertGreaterEqual(stats["p95_ms"], stats["p50_ms"])
        lines = (Path(self.work.name) / "requests.jsonl").read_text().splitlines()
        self.assertTrue(any('"/v1/systemone"' in line for line in lines))
        self.assertFalse(any("secret" in line for line in lines))
        self.assertEqual({"ts", "id", "method", "path", "status", "ms", "model", "ip"}, set(json.loads(lines[0])))

    def test_panel_does_not_build_html_from_data(self):
        html = (Path(__file__).resolve().parent.parent / "jevgw" / "ui" / "index.html").read_text()
        self.assertNotIn("innerHTML", html)


if __name__ == "__main__":
    unittest.main()
