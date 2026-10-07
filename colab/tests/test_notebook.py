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


def free_pair() -> int:
    """A port p such that p and p+1 are both free right now (the gateway uses p, its model server p+1)."""
    for _ in range(200):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        try:
            with socket.socket() as a, socket.socket() as b:
                a.bind(("127.0.0.1", port))
                b.bind(("127.0.0.1", port + 1))
        except OSError:
            continue
        return port
    raise RuntimeError("no free port pair")


class TestStartStop(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        patch = mock.patch.object(notebook, "WORK", Path(self.dir.name))
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(notebook.stop)

    def test_second_start_reuses_the_running_gateway_and_its_key(self):
        client, info = notebook.start("/nonexistent/llama-server", port=free_pair())
        self.assertFalse(info["reused"])
        again, info2 = notebook.start("/nonexistent/llama-server", port=free_pair())
        self.assertTrue(info2["reused"])
        self.assertEqual((info2["pid"], info2["key"], again.key), (info["pid"], info["key"], client.key))

    def test_a_chosen_key_is_used_and_a_different_key_replaces_the_gateway(self):
        _, first = notebook.start("/nonexistent/llama-server", port=free_pair(), key="my-own-key")
        self.assertEqual(first["key"], "my-own-key")
        _, same = notebook.start("/nonexistent/llama-server", port=free_pair(), key="my-own-key")
        self.assertTrue(same["reused"])
        _, other = notebook.start("/nonexistent/llama-server", port=free_pair(), key="another")
        self.assertEqual((other["reused"], other["key"]), (False, "another"))

    def test_a_token_added_later_replaces_a_gateway_that_started_without_it(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HF_TOKEN", None)
            _, first = notebook.start("/nonexistent/llama-server", port=free_pair())
            os.environ["HF_TOKEN"] = "hf_test"
            _, second = notebook.start("/nonexistent/llama-server", port=free_pair())
            _, third = notebook.start("/nonexistent/llama-server", port=free_pair())
            os.environ.pop("HF_TOKEN")
        self.assertEqual((first["reused"], second["reused"], third["reused"]), (False, False, True))

    def test_the_token_comes_from_a_colab_secret_and_is_never_printed(self):
        secrets = mock.Mock()
        secrets.userdata.get.return_value = "hf_secret_value"
        with (
            mock.patch.dict(os.environ, {}, clear=False),
            mock.patch.dict("sys.modules", {"google": secrets, "google.colab": secrets}),
            mock.patch("builtins.print") as shown,
        ):
            os.environ.pop("HF_TOKEN", None)
            self.assertTrue(notebook.use_hf_token())
            self.assertEqual(os.environ["HF_TOKEN"], "hf_secret_value")
            os.environ.pop("HF_TOKEN")
        self.assertNotIn("hf_secret_value", " ".join(str(c) for c in shown.call_args_list))

    def test_no_secret_is_not_an_error(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HF_TOKEN", None)
            self.assertFalse(notebook.use_hf_token())  # not on Colab: google.colab cannot be imported

    def test_the_key_is_printed(self):
        with mock.patch("builtins.print") as shown:
            _, info = notebook.start("/nonexistent/llama-server", port=free_pair())
        self.assertIn(f"API key: {info['key']}", [c.args[0] for c in shown.call_args_list])

    def test_a_gateway_from_an_older_install_is_replaced_not_reused(self):
        _, first = notebook.start("/nonexistent/llama-server", port=free_pair())
        state_file = Path(self.dir.name) / "gateway.json"
        state = json.loads(state_file.read_text())
        state["version"] = "0.0.1"  # as if started before the package was upgraded
        state_file.write_text(json.dumps(state))
        _, second = notebook.start("/nonexistent/llama-server", port=free_pair())
        self.assertFalse(second["reused"])
        self.assertNotEqual(first["pid"], second["pid"])

    def test_stale_state_is_replaced_not_an_error(self):
        notebook.start("/nonexistent/llama-server", port=free_pair())
        state = json.loads((Path(self.dir.name) / "gateway.json").read_text())
        os.kill(state["pid"], 9)  # the gateway dies without cleaning up
        time.sleep(0.5)
        _, info = notebook.start("/nonexistent/llama-server", port=free_pair())
        self.assertFalse(info["reused"])
        self.assertNotEqual(info["pid"], state["pid"])

    def test_busy_port_is_skipped(self):
        with socket.socket() as busy:
            base = free_pair()
            busy.bind(("127.0.0.1", base))
            busy.listen()
            _, info = notebook.start("/nonexistent/llama-server", port=base)
        self.assertGreater(info["port"], base)  # the busy port was skipped

    def test_stop_twice_and_stop_when_nothing_runs(self):
        notebook.stop()
        notebook.start("/nonexistent/llama-server", port=free_pair())
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


def status(model="m", loaded=None, loading=None, progress=None, error=None, cached=False, **entry):
    base = {
        "id": model,
        "name": model.upper(),
        "runnable": True,
        "enabled": True,
        "fits": True,
        "vram_gib": 4,
        "disk_gib": 6,
        "cached": cached,
    }
    return {
        "gpu": "T4", "gpu_gib": 15.0, "gpu_free_gib": 14.5, "loaded": loaded, "loading": loading, "progress": progress, "error": error,
        "load_s": 3, "warm_ms": 5, "disk": {"free_gib": 40.0, "total_gib": 100.0, "keep": 2, "cached": []},
        "models": [{**base, **entry}, {**base, "id": "other", "name": "OTHER"}],
    }  # fmt: skip


class FakeClient:
    """A gateway whose loads fail a set number of times, then work. `script` lists the statuses it reports, in order, then repeats the last."""

    url = "http://127.0.0.1:8000"

    def __init__(self, script=None, refuse=None, fail_times=0):
        self.script, self.refuse, self.fail_times, self.selects = list(script or []), refuse, fail_times, 0
        self.state, self.calls = "idle", []

    def select(self, model, wait=True):
        if self.refuse:
            raise RuntimeError(self.refuse)
        self.selects += 1
        self.state = "loading"

    def models(self):
        if self.script:
            return self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if self.state == "loading":
            self.state = "failed" if self.selects <= self.fail_times else "loaded"
        if self.state == "loaded":
            return status(loaded="m")
        if self.state == "failed":
            return status(error="download dropped")
        return status(loading="m", progress={"phase": "downloading", "done_gib": 1, "total_gib": 4, "elapsed_s": 5})


class Said:
    """Capture what the helpers print."""

    def __enter__(self):
        self.lines = []
        self.patch = mock.patch.object(notebook, "_say", lambda *parts: self.lines.append(" ".join(map(str, parts))))
        self.patch.start()
        return self

    def __exit__(self, *exc):
        self.patch.stop()

    @property
    def text(self):
        return "\n".join(self.lines)


class TestWaitReady(unittest.TestCase):
    def test_loads(self):
        with Said():
            self.assertEqual(notebook.wait_ready(FakeClient(), "m", poll=0)["loaded"], "m")

    def test_a_failed_load_is_retried(self):
        client = FakeClient(fail_times=2)
        with Said():
            notebook.wait_ready(client, "m", poll=0, retries=2)
        self.assertEqual(client.selects, 3)

    def test_gives_up_with_the_last_error(self):
        with Said(), self.assertRaises(RuntimeError) as caught:
            notebook.wait_ready(FakeClient(fail_times=9), "m", poll=0, retries=1)
        self.assertIn("download dropped", str(caught.exception))

    def test_timeout_says_nothing_is_lost(self):
        client = FakeClient([status(loading="m", progress={"phase": "starting", "elapsed_s": 1})])
        with Said(), self.assertRaises(TimeoutError) as caught:
            notebook.wait_ready(client, "m", timeout=0.05, poll=0.01)
        self.assertIn("run this cell again", str(caught.exception))

    def test_an_already_loaded_model_is_a_no_op(self):
        client = FakeClient([status(loaded="m")])
        with Said() as said:
            notebook.wait_ready(client, "m", poll=0)
        self.assertEqual(client.selects, 0)
        self.assertIn("already loaded", said.text)

    def test_it_waits_for_another_load_to_finish_instead_of_failing(self):
        busy = status(loading="other", progress={"phase": "starting", "elapsed_s": 9})
        client = FakeClient(
            [busy, busy, status(), status(loading="m", progress={"phase": "starting", "elapsed_s": 1}), status(loaded="m")]
        )
        with Said() as said:
            notebook.wait_ready(client, "m", poll=0)
        self.assertIn("other is still loading", said.text)
        self.assertEqual(client.selects, 1)

    def test_a_long_step_prints_a_heartbeat_with_the_latest_log_line(self):
        installing = status(
            loading="m", progress={"phase": "installing", "total_gib": 8, "elapsed_s": 70, "detail": "Fetching 39 files: 85%"}
        )
        client = FakeClient([status(), installing, installing, installing, installing, status(loaded="m")])
        with Said() as said:
            notebook.wait_ready(client, "m", poll=0.01, heartbeat=0.02)
        beats = [line for line in said.lines if "still working" in line]
        self.assertTrue(beats, said.text)
        self.assertIn("Fetching 39 files: 85%", beats[0])
        self.assertIn("installing", beats[0])

    def test_phase_changes_are_announced_once(self):
        starting = status(loading="m", progress={"phase": "starting", "elapsed_s": 1})
        client = FakeClient([status(), starting, starting, starting, status(loaded="m")])
        with Said() as said:
            notebook.wait_ready(client, "m", poll=0, heartbeat=3600)
        self.assertEqual(sum("starting the model server" in line for line in said.lines), 1)

    def test_the_final_line_says_how_long_it_took_and_what_is_free(self):
        with Said() as said:
            notebook.wait_ready(FakeClient(), "m", poll=0)
        self.assertRegex(said.text, r"Ready: m is loaded \(\d+s in total")
        self.assertIn("Free disk", said.text)


class TestInterruptedAndUnloading(unittest.TestCase):
    def test_stopping_a_cell_says_the_load_keeps_going(self):
        client = FakeClient([status(), status(loading="m", progress={"phase": "starting", "elapsed_s": 1})])
        with (
            Said() as said,
            mock.patch.object(notebook.time, "sleep", side_effect=KeyboardInterrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            notebook.wait_ready(client, "m", poll=1)
        self.assertIn("keeps loading in the background", said.text)
        self.assertIn("run this cell again", said.text)

    def test_loading_another_model_says_it_unloads_the_current_one(self):
        client = FakeClient([status(loaded="other"), status(loaded="m")])
        with Said() as said:
            notebook.wait_ready(client, "m", poll=0)
        self.assertIn("unloads other first", said.text)


class TestPreflight(unittest.TestCase):
    def test_prints_gpu_disk_time_and_token(self):
        with (
            Said() as said,
            mock.patch.object(notebook, "_reachable", lambda url: True),
            mock.patch.dict(os.environ, {"HF_TOKEN": "x"}),
        ):
            notebook.preflight(FakeClient(), "m", status(first_run_min="3-5"))
        for expected in ("Pre-flight", "GPU memory", "14.5 GiB free of 15.0", "Disk", "typically 3-5 minutes", "token is used"):
            self.assertIn(expected, said.text)

    def test_an_installed_model_says_nothing_to_fetch(self):
        with Said() as said:
            notebook.preflight(FakeClient(), "m", status(cached=True))
        self.assertIn("nothing to fetch", said.text)
        self.assertIn("a minute or less", said.text)

    def test_refuses_a_model_that_does_not_fit_before_anything_is_downloaded(self):
        client = FakeClient()
        with Said(), self.assertRaises(RuntimeError) as caught:
            notebook.wait_ready(client, "m", poll=0) if False else notebook.preflight(
                client, "m", status(fits=False, vram_gib=18.5)
            )
        self.assertIn("needs about 18.5 GiB", str(caught.exception))
        self.assertEqual(client.selects, 0)

    def test_refuses_when_the_gpu_is_busy(self):
        busy = status()
        busy["gpu_free_gib"] = 2.0
        with Said(), self.assertRaises(RuntimeError) as caught:
            notebook.preflight(FakeClient(), "m", busy)
        self.assertIn("something else is using the GPU", str(caught.exception))

    def test_warns_when_older_models_will_be_deleted(self):
        tight = status(disk_gib=40)
        tight["disk"]["free_gib"] = 30.0
        with Said() as said, mock.patch.object(notebook, "_reachable", lambda url: True):
            notebook.preflight(FakeClient(), "m", tight)
        self.assertIn("older models will be deleted", said.text)

    def test_stops_if_hugging_face_is_unreachable(self):
        with Said(), mock.patch.object(notebook, "_reachable", lambda url: False), self.assertRaises(RuntimeError) as caught:
            notebook.preflight(FakeClient(), "m", status())
        self.assertIn("huggingface.co", str(caught.exception))

    def test_an_unknown_model_lists_the_choices(self):
        with Said(), self.assertRaises(RuntimeError) as caught:
            notebook.preflight(FakeClient(), "nope", status())
        self.assertIn("m, other", str(caught.exception))


class TestSetupChecks(unittest.TestCase):
    def run_setup(self, gpu=("Tesla T4", 15360), driver="580.82", reachable=True):
        completed = mock.Mock(stdout=driver + "\n")
        with (
            Said() as said,
            mock.patch.object(notebook.catalog, "gpu_info", lambda: gpu),
            mock.patch.object(notebook.subprocess, "run", return_value=completed),
            mock.patch.object(notebook, "_reachable", lambda url: reachable),
            mock.patch.object(notebook, "ensure_llama", lambda t4: "/llama"),
            mock.patch.object(notebook, "use_hf_token", lambda: False),
        ):
            result = notebook.setup()
        return result, said.text

    def test_a_good_machine_prints_each_finding_and_installs_llama(self):
        result, text = self.run_setup()
        self.assertEqual(result, "/llama")
        for expected in ("Checking this machine", "GPU", "Tesla T4", "driver 580.82: ok", "Disk", "Network", "Models"):
            self.assertIn(expected, text)

    def test_no_gpu_stops_with_the_fix(self):
        with self.assertRaises(SystemExit) as caught:
            self.run_setup(gpu=(None, 0))
        self.assertIn("T4 GPU", str(caught.exception))

    def test_an_old_driver_stops_before_anything_is_downloaded(self):
        with self.assertRaises(SystemExit) as caught:
            self.run_setup(driver="470.82")
        self.assertIn("older than 525", str(caught.exception))

    def test_no_network_stops_with_the_fix(self):
        with self.assertRaises(SystemExit) as caught:
            self.run_setup(reachable=False)
        self.assertIn("Cannot reach", str(caught.exception))


class TestConsoleGuide(unittest.TestCase):
    def test_explains_the_console_and_how_to_call_the_model_from_code(self):
        with Said() as said, mock.patch.object(notebook, "show_panel") as panel:
            notebook.console(FakeClient([status(loaded="m")]), {"port": 8000, "key": "k123"})
        panel.assert_called_once()
        for expected in (
            "Jev console",
            "Models",
            "Try a model",
            "Response times",
            "client.systemone",
            "k123",
            "http://127.0.0.1:8000",
            "reset",
        ):
            self.assertIn(expected, said.text)

    def test_a_stopped_gateway_gets_a_clear_message_not_a_traceback(self):
        client = FakeClient()
        client.models = mock.Mock(side_effect=ConnectionRefusedError())
        with Said() as said, mock.patch.object(notebook, "show_panel") as panel:
            notebook.console(client, {"port": 8000, "key": "k"})
        panel.assert_not_called()
        self.assertIn("not running", said.text)


if __name__ == "__main__":
    unittest.main()
