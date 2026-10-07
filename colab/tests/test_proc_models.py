"""Models that run in Python: their environments are part of the disk budget, shared folders survive, and the model field is filled in."""

import collections
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jevgw import backends
from jevgw.backends import Proc, with_model
from jevgw.disk import GIB, Disk

Usage = collections.namedtuple("Usage", "total used free")


def proc(mid, install_gib, *paths, **extra):
    return {
        "id": mid,
        "name": mid,
        "kind": "proc",
        "cmd": ["x"],
        "vram_gib": 4,
        "install_gib": install_gib,
        "paths": list(paths),
        **extra,
    }


class TestProcDisk(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        base = Path(self.dir.name)
        self.root, self.work = base / "root", base / "work"
        self.work.mkdir()
        self.cache = base / "uvcache"
        self.models = {
            "a": proc("a", 6, "models/a", "data/hf"),  # a and b share the weights in data/hf
            "b": proc("b", 5, "models/b", "data/hf"),
            "c": proc("c", 7, "models/c"),
        }
        self.capacity = 20
        self.disk = Disk(self.work / "w", self.work / "disk.json", 2, 2, self.usage, self.root, caches=(self.cache,))

    def usage(self, _folder):
        used = sum(f.stat().st_size for f in list(self.root.rglob("*")) + list(self.cache.rglob("*")) if f.is_file())
        return Usage(self.capacity * GIB, used, self.capacity * GIB - used)

    def install(self, mid, now=1, cache_gib=0):
        """What a recipe's setup does: create the folders, fill them (sparse), write the marker."""
        for rel in self.models[mid]["paths"]:
            path = self.root / rel
            path.mkdir(parents=True, exist_ok=True)
            if not (path / "blob").exists():
                with open(path / "blob", "wb") as f:
                    f.truncate(int(self.models[mid]["install_gib"] / len(self.models[mid]["paths"]) * GIB))
        (self.work / f"{mid}.setup-done").touch()
        self.disk.touch(mid, now)
        if cache_gib:
            self.cache.mkdir(exist_ok=True)
            with open(self.cache / "wheels", "wb") as f:
                f.truncate(cache_gib * GIB)

    def test_installed_only_with_the_marker_and_its_folder(self):
        self.assertFalse(self.disk.cached(self.models["a"]))
        self.install("a")
        self.assertTrue(self.disk.cached(self.models["a"]))
        (self.work / "a.setup-done").unlink()
        self.assertFalse(self.disk.cached(self.models["a"]))  # an interrupted install does not count

    def test_the_budget_tracks_recipe_models_but_not_ones_with_no_paths(self):
        self.assertTrue(self.disk.tracks(self.models["a"]))
        self.assertFalse(self.disk.tracks({"id": "z", "kind": "proc", "cmd": ["x"]}))

    def test_keep_limit_deletes_the_oldest_environment_and_its_marker(self):
        self.install("a", 1)
        self.install("c", 2)
        self.assertEqual(self.disk.make_room(self.models["b"], self.models), ["a"])
        self.assertFalse((self.root / "models/a").exists())
        self.assertFalse((self.work / "a.setup-done").exists())  # its setup runs again next time

    def test_a_folder_shared_with_the_target_is_kept(self):
        self.install("a", 1)
        self.install("c", 2)
        self.disk.make_room(self.models["b"], self.models)  # a goes, b needs a's weights folder
        self.assertTrue((self.root / "data/hf").exists())

    def test_a_shared_folder_goes_when_nothing_else_uses_it(self):
        self.install("a")
        self.disk.delete("a", self.models)
        self.assertFalse((self.root / "data/hf").exists())

    def test_wheel_caches_are_freed_before_any_model_is_deleted(self):
        self.capacity = 18
        self.install("a", 1, cache_gib=6)  # 6 GiB of models + 6 GiB of wheels on an 18 GiB disk
        # c needs 7 GiB with 2 kept free: not enough until the 6 GiB wheel cache goes; a does not need to be deleted
        self.assertEqual(self.disk.make_room(self.models["c"], self.models), [])
        self.assertFalse(self.cache.exists())
        self.assertTrue(self.disk.cached(self.models["a"]))

    def test_status_lists_installed_models(self):
        self.install("c")
        self.assertEqual(self.disk.status(self.models)["cached"], ["c"])


class TestLogLines(unittest.TestCase):
    """What a long step is doing right now, read from its log: this is what the heartbeat and the console show."""

    def last(self, text, **kw):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "x.log"
            path.write_bytes(text.encode() if isinstance(text, str) else text)
            return backends.last_line(path, **kw)

    def test_the_last_real_line(self):
        self.assertEqual(self.last("first\nsecond\n\n  \n"), "second")

    def test_a_progress_bar_that_rewrites_one_line_gives_its_latest_state(self):
        self.assertEqual(
            self.last("Fetching 39 files:   0%|\rFetching 39 files:  85%|\rFetching 39 files: 100%|"), "Fetching 39 files: 100%|"
        )

    def test_colour_codes_are_removed(self):
        self.assertEqual(self.last("\x1b[90mHint: use the hf cli\x1b[0m\n"), "Hint: use the hf cli")

    def test_long_lines_are_cut(self):
        self.assertEqual(len(self.last("x" * 500, width=50)), 50)

    def test_missing_or_empty_logs_give_an_empty_string(self):
        self.assertEqual(backends.last_line("/nonexistent/x.log"), "")
        self.assertEqual(self.last(""), "")

    def test_only_the_end_of_a_huge_log_is_read(self):
        self.assertEqual(self.last("a\n" * 100_000 + "the end"), "the end")

    def test_a_failed_setup_names_the_last_line_and_the_log(self):
        with tempfile.TemporaryDirectory() as folder:
            server = Proc(
                {"id": "m", "setup": ["echo 'could not resolve host' >&2; exit 3"]},
                {"work": folder, "root": folder, "here": folder, "child_port": 1},
            )
            with self.assertRaises(RuntimeError) as caught:
                server._setup(server.entry, {})
        self.assertIn("could not resolve host", str(caught.exception))
        self.assertIn("m.setup.log", str(caught.exception))


class TestModelField(unittest.TestCase):
    def test_added_when_missing(self):
        self.assertEqual(json.loads(with_model(b'{"state": "s"}', "jev-latest")), {"state": "s", "model": "jev-latest"})

    def test_a_callers_model_is_kept(self):
        body = b'{"state": "s", "model": "mine"}'
        self.assertEqual(with_model(body, "jev-latest"), body)

    def test_not_json_or_not_an_object_is_passed_through_for_the_server_to_refuse(self):
        for body in (b"not json", b"[1, 2]"):
            self.assertEqual(with_model(body, "jev-latest"), body)

    def test_only_models_that_declare_a_default_get_one(self):
        seen = []

        class Recorder(backends.Server):
            pass

        for entry, expect_model in (({"id": "jeff", "default_model": "jev-latest"}, True), ({"id": "other"}, False)):
            server = Recorder(entry, {"child_port": 1})
            conn = mock.Mock()
            conn.getresponse.return_value = mock.Mock(status=200, read=lambda: b"{}")
            server._local.conn = conn
            server.answer(b'{"state": "s"}')
            sent = conn.request.call_args.args[2]
            seen.append(("model" in json.loads(sent)) == expect_model)
        self.assertEqual(seen, [True, True])


class TestResidentSize(unittest.TestCase):
    def test_a_recipe_model_is_checked_against_its_measured_resident_size(self):
        self.assertEqual(
            Proc({"id": "j", "vram_gib": 9.5, "resident_gib": 2.5}, {"child_port": 1}).expected_gpu_mib(), 2.5 * 1024
        )

    def test_without_one_it_falls_back_to_a_share_of_the_peak(self):
        self.assertAlmostEqual(Proc({"id": "j", "vram_gib": 10}, {"child_port": 1}).expected_gpu_mib(), 3.0 * 1024)


if __name__ == "__main__":
    unittest.main()
