"""models.json is valid and its GPU tiers are what the README says."""

import json
import tempfile
import unittest

from jevgw import DATA, catalog


class TestCatalog(unittest.TestCase):
    def setUp(self):
        self.models = catalog.load(DATA / "models.json")

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
        self.assertTrue({"clef-flash-q4km", "clef-flash-q2k", "laya", "jeff"} <= t4)
        self.assertNotIn("cygnet", l4)  # over the 20 GiB limit, never offered

    def test_no_cpu_model_can_be_loaded(self):
        """These models run on a GPU only: anything that needs no GPU memory is not offered at all."""
        for model in self.models.values():
            if catalog.runnable(model):
                self.assertGreater(model.get("vram_gib", 0), 0, model["id"])
        self.assertFalse(catalog.runnable(self.models["verdict"]))

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
