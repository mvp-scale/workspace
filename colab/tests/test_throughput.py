"""Throughput behaviour: a kept-alive connection to the model server, honest 429s under overload, and the metrics endpoint."""

import http.server
import threading
import unittest

from jevgw.backends import Server
from tests.test_gateway import Base, FakeServer


class Child(http.server.BaseHTTPRequestHandler):
    """A model server that counts the connections it is given and can drop the idle one."""

    protocol_version = "HTTP/1.1"
    connections = 0
    close_after_reply = False

    def setup(self):
        super().setup()
        type(self).connections += 1

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        body = b'{"answers": {}}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        if type(self).close_after_reply:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class TestPooledConnection(unittest.TestCase):
    def setUp(self):
        Child.connections, Child.close_after_reply = 0, False
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Child)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.server = Server({"id": "m"}, {"child_port": self.httpd.server_address[1]})

    def test_one_connection_serves_many_calls(self):
        for _ in range(5):
            self.assertEqual(self.server.answer(b"{}")[0], 200)
        self.assertEqual(Child.connections, 1)

    def test_a_connection_the_server_closed_is_replaced_once(self):
        Child.close_after_reply = True  # the server hangs up after each reply
        for _ in range(3):
            self.assertEqual(self.server.answer(b"{}")[0], 200)
        self.assertEqual(Child.connections, 3)  # a new connection each time, no error surfaced

    def test_each_thread_gets_its_own_connection(self):
        results = []
        threads = [threading.Thread(target=lambda: results.append(self.server.answer(b"{}")[0])) for _ in range(3)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(results, [200] * 3)

    def test_an_unreachable_server_raises(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        with self.assertRaises(OSError):
            self.server.answer(b"{}")


class TestOverload(Base):
    max_inflight = 1

    def hold_the_slot(self):
        self.call("POST", "/admin/select", {"model": "small"})
        FakeServer.gate = threading.Event()
        worker = threading.Thread(target=lambda: self.call("POST", "/v1/systemone", {}))
        worker.start()
        for _ in range(100):  # wait until it is being served
            if self.app.in_flight:
                break
            threading.Event().wait(0.02)
        return worker

    def test_overload_is_an_immediate_429_that_says_when_to_come_back(self):
        worker = self.hold_the_slot()
        status, body, response = self.call("POST", "/v1/systemone", {})
        FakeServer.gate.set()
        worker.join(5)
        self.assertEqual(status, 429)
        self.assertIn("busy", body["error"])
        self.assertGreaterEqual(body["retry_after_s"], 1)
        self.assertEqual(int(response.getheader("Retry-After")), body["retry_after_s"])

    def test_stats_report_throughput_in_flight_and_rejections(self):
        worker = self.hold_the_slot()
        self.call("POST", "/v1/systemone", {})
        FakeServer.gate.set()
        worker.join(5)
        stats = self.call("GET", "/v1/stats")[1]
        self.assertEqual((stats["capacity"], stats["rejected"]), (1, 1))
        self.assertGreater(stats["throughput_rps"], 0)
        self.assertEqual(stats["in_flight"], 0)


class TestLatencyOverhead(Base):
    def test_the_gateway_adds_almost_no_time(self):
        """Nagle's algorithm plus delayed ACKs once added a fixed 41 ms to every response; with an instant model it must stay tiny."""
        import http.client
        import statistics
        import time

        self.call("POST", "/admin/select", {"model": "small"})
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        self.addCleanup(conn.close)
        headers = {"Authorization": "Bearer test-key", "Content-Type": "application/json"}
        times = []
        for _ in range(25):
            start = time.perf_counter()
            conn.request("POST", "/v1/systemone", b"{}", headers)
            conn.getresponse().read()
            times.append((time.perf_counter() - start) * 1000)
        self.assertLess(statistics.median(times[5:]), 15, times)

    def test_a_burst_of_new_connections_is_answered_not_refused(self):
        self.call("POST", "/admin/select", {"model": "small"})
        results = []
        threads = [threading.Thread(target=lambda: results.append(self.call("POST", "/v1/systemone", {})[0])) for _ in range(64)]
        [t.start() for t in threads]
        [t.join(20) for t in threads]
        self.assertEqual(len(results), 64)
        self.assertTrue(all(code in (200, 429) for code in results), sorted(set(results)))

    def test_listen_queue_is_deep(self):
        from jevgw.server import GatewayHTTPServer

        self.assertGreaterEqual(GatewayHTTPServer.request_queue_size, 128)


class TestAutoCapacity(Base):
    max_inflight = 0

    def test_default_is_twice_the_model_servers_slots(self):
        from jevgw.backends import SLOTS

        self.assertEqual(self.app.capacity, 2 * SLOTS)


class TestMetrics(Base):
    def test_requires_the_key(self):
        self.assertEqual(self.call("GET", "/metrics", key=None)[0], 401)

    def test_prometheus_text_with_what_an_operator_needs(self):
        self.call("POST", "/admin/select", {"model": "small"})
        self.call("POST", "/v1/systemone", {})
        status, text, response = self.call("GET", "/metrics")
        text = text.decode()
        self.assertEqual(status, 200)
        self.assertTrue(response.getheader("Content-Type").startswith("text/plain"))
        for expected in (
            'jevgw_model_loaded{model="small"} 1',
            'jevgw_requests_total{model="small"} 1',
            "# TYPE jevgw_requests_total counter",
            "jevgw_throughput_rps",
            "jevgw_in_flight 0",
            "jevgw_rejected_total 0",
            'jevgw_request_duration_ms{model="small",quantile="0.95"}',
        ):
            self.assertIn(expected, text)
        for line in text.splitlines():  # every sample line is `name{labels} number`
            if line and not line.startswith("#"):
                float(line.rsplit(" ", 1)[1])


if __name__ == "__main__":
    unittest.main()
