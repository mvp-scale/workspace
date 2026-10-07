"""The disk budget: models are kept up to a limit, the oldest are deleted first, shared files survive, a model that cannot fit is refused."""

import collections
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from jevgw import catalog, manager
from jevgw.backends import KINDS
from jevgw.disk import GIB, Disk, DiskFull
from jevgw.manager import Refused
from tests.test_gateway import FakeServer

Usage = collections.namedtuple("Usage", "total used free")


def model(mid, file_gib, mmproj=None):
    entry = {"id": mid, "name": mid, "kind": "llama", "repo": "r", "file": f"{mid}.gguf", "file_gib": file_gib, "vram_gib": 4}
    if mmproj:
        entry |= {"mmproj": mmproj, "mmproj_gib": 1}
    return entry


class Base(unittest.TestCase):
    capacity_gib = 20

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.weights = Path(self.dir.name) / "weights"
        self.models = {m["id"]: m for m in (model("a", 5, "proj.gguf"), model("b", 4, "proj.gguf"), model("c", 6), model("d", 9))}
        self.disk = Disk(self.weights, Path(self.dir.name) / "disk.json", keep=2, margin_gib=2, usage=self.usage)

    def usage(self, _folder):
        used = sum(f.stat().st_size for f in self.weights.glob("*"))
        return Usage(self.capacity_gib * GIB, used, self.capacity_gib * GIB - used)

    def download(self, mid, now):
        """What a real download does: files appear on disk (sparse, so no real space is used), then the model counts as used."""
        for name, gib in __import__("jevgw.disk", fromlist=["files_of"]).files_of(self.models[mid]).items():
            with open(self.weights / name, "wb") as f:
                f.truncate(int(gib * GIB))
        self.disk.touch(mid, now)

    def on_disk(self):
        return sorted(f.name for f in self.weights.glob("*"))


class TestDisk(Base):
    def test_room_when_nothing_cached(self):
        self.assertEqual(self.disk.make_room(self.models["a"], self.models), [])

    def test_keep_limit_deletes_the_least_recently_used(self):
        self.download("a", 1)
        self.download("c", 2)  # a is older
        self.assertEqual(self.disk.make_room(self.models["b"], self.models), ["a"])
        self.assertEqual(self.on_disk(), ["c.gguf", "proj.gguf"])  # a's own file went; the projector stays because b will use it

    def test_recently_used_survives_and_touch_changes_the_order(self):
        self.download("a", 1)
        self.download("c", 2)
        self.disk.touch("a", 3)  # a used again: now c is the oldest
        self.assertEqual(self.disk.make_room(self.models["b"], self.models), ["c"])

    def test_shared_file_is_kept_for_the_target(self):
        self.download("a", 1)
        self.download("c", 2)
        self.assertEqual(self.disk.make_room(self.models["b"], self.models), ["a"])
        self.assertIn("proj.gguf", self.on_disk())  # b needs the same projector as a

    def test_space_margin_forces_eviction_even_under_the_count_limit(self):
        self.capacity_gib = 14
        self.download("a", 1)  # 6 GiB used, 8 free
        # d needs 9 and the margin is 2: 8 free is not enough, so a must go even though only one model is cached
        self.assertEqual(self.disk.make_room(self.models["d"], self.models), ["a"])

    def test_refused_when_it_cannot_fit_even_alone(self):
        self.capacity_gib = 10
        with self.assertRaises(DiskFull) as caught:
            self.disk.make_room(self.models["d"], self.models)  # 9 GiB + 2 margin on a 10 GiB disk
        self.assertIn("d needs", str(caught.exception))

    def test_a_cached_target_needs_no_download_space(self):
        self.capacity_gib = 6
        self.download("c", 1)
        self.assertEqual(self.disk.make_room(self.models["c"], self.models), [])

    def test_download_progress_counts_partial_files(self):
        partial = self.weights / ".cache" / "huggingface" / "download"
        partial.mkdir(parents=True)
        with open(partial / "YS5nZ3VmCg==.etag.hash.incomplete", "wb") as f:
            f.truncate(2 * GIB)
        done, total = self.disk.downloaded_gib(self.models["a"])
        self.assertEqual((round(done, 1), total), (2.0, 6.0))

    def test_status_and_delete(self):
        self.download("a", 1)
        self.assertEqual(self.disk.status(self.models)["cached"], ["a"])
        self.disk.delete("a", self.models)
        self.assertEqual((self.on_disk(), self.disk.status(self.models)["cached"]), ([], []))


class TestGatewayDisk(Base):
    def setUp(self):
        super().setUp()
        FakeServer.started, FakeServer.stopped, FakeServer.gate = [], [], None
        for patch in (
            mock.patch.dict(KINDS, {"llama": FakeServer}),
            mock.patch.object(catalog, "gpu_info", lambda: ("T", 16 * 1024)),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.gw = manager.Gateway(self.models, {"work": self.dir.name}, None, self.disk)
        self.addCleanup(self.gw.shutdown)

    def load(self, mid):
        self.gw.select(mid)
        self.download(mid, len(FakeServer.started) + 10)  # the fake server does not download; do what fetch() would have

    def test_third_model_deletes_the_oldest_and_status_reports_it(self):
        self.load("a")
        self.load("c")
        self.gw.select("b")  # keep=2: loading a third deletes the least recently used cached model
        cached = {m["id"]: m["cached"] for m in self.gw.status()["models"]}
        self.assertFalse(cached["a"])
        self.assertTrue(cached["c"])

    def test_purge_refuses_the_loaded_model_and_deletes_others(self):
        self.load("a")
        self.load("c")
        with self.assertRaises(Refused):
            self.gw.purge("c")
        self.gw.purge("a")
        self.assertNotIn("a.gguf", self.on_disk())

    def test_select_in_the_background_returns_at_once_and_is_repeatable(self):
        FakeServer.gate = None
        started = threading.Event()
        release = threading.Event()
        real_start = FakeServer.start

        def slow_start(server):
            started.set()
            release.wait(5)
            real_start(server)

        with mock.patch.object(FakeServer, "start", slow_start):
            self.gw.select("a", wait=False)
            started.wait(5)
            self.assertEqual(self.gw.status()["loading"], "a")
            self.assertEqual(self.gw.progress(), {"phase": "downloading", "done_gib": 0.0, "total_gib": 6.0})
            self.gw.select("a", wait=False)  # asking again while it loads is a no-op
            with self.assertRaises(Refused):  # a different model has to wait
                self.gw.select("b", wait=False)
            release.set()
            self.gw.select("a")  # and waiting on it joins the load in flight
        self.assertEqual((self.gw.cur_id, FakeServer.started), ("a", ["a"]))
        self.gw.select("a")  # loaded already: nothing happens
        self.assertEqual(FakeServer.started, ["a"])

    def test_a_failed_load_can_be_requested_again(self):
        with mock.patch.object(FakeServer, "start", side_effect=RuntimeError("download dropped")):
            self.gw.select("a", wait=False)
            self.gw._future.exception(5)
        status = self.gw.status()
        self.assertEqual((status["loading"], "download dropped" in status["error"]), (None, True))
        self.gw.select("a")  # the retry works and clears the error
        self.assertEqual((self.gw.cur_id, self.gw.error), ("a", None))

    def test_no_room_is_a_507(self):
        self.capacity_gib = 8
        with self.assertRaises(Refused) as caught:
            self.gw.select("d")
        self.assertEqual(caught.exception.status, 507)


if __name__ == "__main__":
    unittest.main()
