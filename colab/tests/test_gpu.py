"""Models run on the GPU only: refuse before downloading, and verify after loading."""

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jevgw import backends, catalog, manager
from jevgw.manager import Refused


def fake_llama(folder: Path, devices_output: str) -> str:
    """A stand-in llama-server whose --list-devices prints `devices_output`."""
    path = folder / "llama-server"
    path.write_text(f"#!/bin/sh\ncat <<'EOF'\n{devices_output}\nEOF\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


class TestRequireGpu(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("JEVGW_ALLOW_CPU", None)
        self.addCleanup(self.env.stop)

    def test_passes_when_llama_sees_a_cuda_device(self):
        binary = fake_llama(Path(self.dir.name), "Available devices:\n  CUDA0: Tesla T4 (14912 MiB, 14807 MiB free)")
        with mock.patch.object(backends, "gpu_info", lambda: ("Tesla T4", 15360)):
            backends.require_gpu(binary)

    def test_refuses_when_llama_sees_no_device_even_though_the_machine_has_a_gpu(self):
        binary = fake_llama(Path(self.dir.name), "Available devices:\n  (none)")
        with mock.patch.object(backends, "gpu_info", lambda: ("Tesla T4", 15360)), self.assertRaises(RuntimeError) as caught:
            backends.require_gpu(binary)
        self.assertIn("cannot see this machine's GPU", str(caught.exception))

    def test_refuses_a_machine_with_no_gpu(self):
        with mock.patch.object(backends, "gpu_info", lambda: (None, 0)), self.assertRaises(RuntimeError) as caught:
            backends.require_gpu("/nonexistent")
        self.assertIn("no GPU", str(caught.exception))

    def test_the_development_switch_allows_cpu(self):
        os.environ["JEVGW_ALLOW_CPU"] = "1"
        with mock.patch.object(backends, "gpu_info", lambda: (None, 0)):
            backends.require_gpu("/nonexistent")

    def test_llama_refuses_before_downloading_anything(self):
        binary = fake_llama(Path(self.dir.name), "Available devices:\n  (none)")
        entry = {"id": "m", "kind": "llama", "repo": "r", "file": "f.gguf", "file_gib": 1, "vram_gib": 1}
        cfg = {"llama_bin": binary, "weights": self.dir.name, "work": self.dir.name, "child_port": 1}
        with (
            mock.patch.object(backends, "gpu_info", lambda: ("Tesla T4", 15360)),
            mock.patch.object(backends, "fetch") as fetch,
            self.assertRaises(RuntimeError),
        ):
            backends.Llama(entry, cfg).start()
        fetch.assert_not_called()


class TestModelOnGpu(unittest.TestCase):
    """A loaded model must visibly use GPU memory: read from nvidia-smi, not from a server's log."""

    def check(self, kind, before, after, **entry):
        server = kind({"id": "m", "vram_gib": 8, **entry}, {"child_port": 1})
        server.log_path = Path("m.log")
        with mock.patch.object(backends, "gpu_used_mib", lambda: after), mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JEVGW_ALLOW_CPU", None)
            server.verify_gpu(before)

    def test_llama_memory_grew_by_the_weights_passes(self):
        self.check(backends.Llama, 400, 400 + 6700, file_gib=5.6, mmproj_gib=0.9)

    def test_a_llama_load_that_left_the_gpu_untouched_is_stopped(self):
        with self.assertRaises(RuntimeError) as caught:
            self.check(backends.Llama, 400, 420, file_gib=5.6, mmproj_gib=0.9)
        self.assertIn("running on the CPU", str(caught.exception))

    def test_a_recipe_model_is_checked_against_its_resident_size(self):
        self.check(backends.Proc, 400, 400 + 1700, resident_gib=2.5)  # needs at least 0.6 * 2.5 GiB
        with self.assertRaises(RuntimeError):
            self.check(backends.Proc, 400, 400 + 500, resident_gib=2.5)

    def test_unreadable_memory_or_no_expectation_does_not_block(self):
        self.check(backends.Llama, None, None, file_gib=5.6)
        self.check(backends.Proc, 400, 400, vram_gib=0)


class TestFreeMemory(unittest.TestCase):
    def test_refuses_before_download_when_the_gpu_is_busy(self):
        gw = manager.Gateway(
            {"m": {"id": "m", "name": "M", "kind": "llama", "vram_gib": 10, "file": "f", "repo": "r", "file_gib": 1}}, {}
        )
        self.addCleanup(gw.shutdown)
        with mock.patch.object(catalog, "gpu_free_mib", lambda: 2048), self.assertRaises(Refused) as caught:
            gw._require_free_gpu_memory(gw.models["m"])
        self.assertIn("only 2.0 GiB is free", str(caught.exception))

    def test_unreadable_free_memory_does_not_block(self):
        gw = manager.Gateway(
            {"m": {"id": "m", "name": "M", "kind": "llama", "vram_gib": 10, "file": "f", "repo": "r", "file_gib": 1}}, {}
        )
        self.addCleanup(gw.shutdown)
        with mock.patch.object(catalog, "gpu_free_mib", lambda: None):
            gw._require_free_gpu_memory(gw.models["m"])


if __name__ == "__main__":
    unittest.main()
