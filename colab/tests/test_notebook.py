"""The notebook helpers are idempotent: running a cell twice, after a crash, or with a busy port needs no manual cleanup."""

import json
import os
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from jevgw import notebook


class TestStartStop(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        patch = mock.patch.object(notebook, "WORK", Path(self.dir.name))
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(notebook.stop)

    def test_second_start_reuses_the_running_gateway_and_its_key(self):
        client, info = notebook.start("/nonexistent/llama-server", port=18700)
        self.assertFalse(info["reused"])
        again, info2 = notebook.start("/nonexistent/llama-server", port=18700)
        self.assertTrue(info2["reused"])
        self.assertEqual((info2["pid"], info2["key"], again.key), (info["pid"], info["key"], client.key))

    def test_a_chosen_key_is_used_and_a_different_key_replaces_the_gateway(self):
        _, first = notebook.start("/nonexistent/llama-server", port=18740, key="my-own-key")
        self.assertEqual(first["key"], "my-own-key")
        _, same = notebook.start("/nonexistent/llama-server", port=18740, key="my-own-key")
        self.assertTrue(same["reused"])
        _, other = notebook.start("/nonexistent/llama-server", port=18740, key="another")
        self.assertEqual((other["reused"], other["key"]), (False, "another"))

    def test_the_key_is_printed(self):
        with mock.patch("builtins.print") as shown:
            _, info = notebook.start("/nonexistent/llama-server", port=18750)
        self.assertIn(f"API key: {info['key']}", [c.args[0] for c in shown.call_args_list])

    def test_stale_state_is_replaced_not_an_error(self):
        notebook.start("/nonexistent/llama-server", port=18710)
        state = json.loads((Path(self.dir.name) / "gateway.json").read_text())
        os.kill(state["pid"], 9)  # the gateway dies without cleaning up
        time.sleep(0.5)
        _, info = notebook.start("/nonexistent/llama-server", port=18710)
        self.assertFalse(info["reused"])
        self.assertNotEqual(info["pid"], state["pid"])

    def test_busy_port_is_skipped(self):
        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 18720))
            busy.listen()
            _, info = notebook.start("/nonexistent/llama-server", port=18720)
        self.assertEqual(info["port"], 18721)

    def test_stop_twice_and_stop_when_nothing_runs(self):
        notebook.stop()
        notebook.start("/nonexistent/llama-server", port=18730)
        notebook.stop()
        notebook.stop()
        self.assertFalse((Path(self.dir.name) / "gateway.json").exists())

    def test_reset_keeps_models_unless_asked(self):
        weights = Path(self.dir.name) / "weights"
        weights.mkdir()
        (weights / "m.gguf").write_text("x")
        notebook.reset()
        self.assertTrue((weights / "m.gguf").exists())
        notebook.reset(delete_models=True)
        self.assertFalse(weights.exists())


class FakeClient:
    """A gateway whose loads fail a set number of times, then work."""

    def __init__(self, fail_times=0, refuse=None):
        self.fail_times, self.refuse, self.selects, self.state = fail_times, refuse, 0, "idle"

    def select(self, model, wait=True):
        if self.refuse:
            raise RuntimeError(self.refuse)
        self.selects += 1
        self.state = "loading"

    def models(self):
        if self.state == "loading":
            if self.selects <= self.fail_times:
                self.state = "failed"
            else:
                self.state = "loaded"
        status = {"disk": {"free_gib": 40}, "load_s": 3, "warm_ms": 5, "error": None, "progress": None}
        if self.state == "loaded":
            return {**status, "loaded": "m", "loading": None}
        if self.state == "failed":
            return {**status, "loaded": None, "loading": None, "error": "download dropped"}
        return {**status, "loaded": None, "loading": "m", "progress": {"phase": "downloading", "done_gib": 1, "total_gib": 4}}


class TestWaitReady(unittest.TestCase):
    def test_loads(self):
        self.assertEqual(notebook.wait_ready(FakeClient(), "m", poll=0)["loaded"], "m")

    def test_a_failed_load_is_retried(self):
        client = FakeClient(fail_times=2)
        notebook.wait_ready(client, "m", poll=0, retries=2)
        self.assertEqual(client.selects, 3)

    def test_gives_up_with_the_last_error(self):
        with self.assertRaises(RuntimeError) as caught:
            notebook.wait_ready(FakeClient(fail_times=9), "m", poll=0, retries=1)
        self.assertIn("download dropped", str(caught.exception))

    def test_a_refusal_raises_at_once_with_the_reason(self):
        with self.assertRaises(RuntimeError) as caught:
            notebook.wait_ready(FakeClient(refuse="needs 18.5 GiB"), "m", poll=0)
        self.assertIn("18.5", str(caught.exception))

    def test_timeout(self):
        client = FakeClient()
        client.models = lambda: {"loaded": None, "loading": "m", "progress": None}
        with self.assertRaises(TimeoutError):
            notebook.wait_ready(client, "m", timeout=0.05, poll=0.01)


if __name__ == "__main__":
    unittest.main()
