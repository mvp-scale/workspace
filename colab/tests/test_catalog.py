"""models.json is valid and its GPU tiers are what the README says."""

import json
import tempfile
import unittest
from pathlib import Path

from jevgw import catalog

ROOT = Path(__file__).resolve().parent.parent


class TestCatalog(unittest.TestCase):
    def setUp(self):
        self.models = catalog.load(ROOT / "models.json")

    def test_every_runnable_model_has_what_its_kind_needs(self):
        for model in self.models.values():
            if model["kind"] == "llama":
                self.assertTrue(model["repo"] and model["file"], model["id"])
            if model["kind"] == "proc":
                self.assertTrue(model["cmd"] and model["setup"], model["id"])
            if catalog.runnable(model):
                self.assertIn("vram_gib", model, model["id"])

    def test_tiers(self):
        def fitting(gib):
            return {m["id"] for m in self.models.values() if catalog.runnable(m) and catalog.fits(m, int(gib * 1024))}

        t4, l4 = fitting(15), fitting(22.4)
        self.assertEqual(l4 - t4, {"clef-flash", "kev-4b"})  # the two that need a 24 GB card
        self.assertTrue({"clef-flash-q4km", "clef-flash-q2k", "laya", "verdict", "jeff"} <= t4)
        self.assertNotIn("cygnet", l4)  # over the 20 GiB limit, never offered

    def test_cpu_models_fit_anywhere(self):
        self.assertTrue(catalog.fits({"vram_gib": 0}, 0))

    def test_validation_errors(self):
        def load(entries):
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                json.dump({"models": entries}, f)
            return catalog.load(f.name)

        for bad in (
            [{"id": "a", "name": "A"}],
            [{"id": "a", "name": "A", "kind": "weird"}],
            [{"id": "a", "name": "A", "kind": "llama"}],
            [{"id": "a", "name": "A", "kind": "none"}, {"id": "a", "name": "A", "kind": "none"}],
        ):
            with self.assertRaises(catalog.CatalogError):
                load(bad)


if __name__ == "__main__":
    unittest.main()
