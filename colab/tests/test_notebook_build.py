"""The generated notebook is short, valid, and agrees with the package's model list."""

import json
import re
import unittest
from pathlib import Path

import build_notebook
from jevgw import DATA, catalog


class TestNotebook(unittest.TestCase):
    def setUp(self):
        self.cells = build_notebook.build()
        self.code = ["".join(c["source"]) for c in self.cells if c["cell_type"] == "code"]
        self.text = "\n".join("".join(c["source"]) for c in self.cells if c["cell_type"] == "markdown")

    def test_it_is_compact_and_holds_no_source_files(self):
        self.assertLessEqual(len(self.cells), 16)
        self.assertLess(len(json.dumps(self.cells)), 25_000)
        self.assertFalse(any("%%writefile" in src for src in self.code))

    def test_code_cells_are_form_cells_with_a_title_and_compile(self):
        for cell, src in zip([c for c in self.cells if c["cell_type"] == "code"], self.code, strict=True):
            self.assertEqual(cell["metadata"], {"cellView": "form"})
            self.assertTrue(src.startswith("#@title "), src[:40])
            compile(src, "cell", "exec")

    def test_it_installs_the_package_from_github_pinned_to_its_own_version(self):
        from jevgw import __version__

        install = self.code[0]
        self.assertIn(build_notebook.REPO, install)
        self.assertIn(f"subdirectory={build_notebook.SUBDIR}", install)
        self.assertIn(f'REF = "v{__version__}"', install)  # a tag, never a branch that moves
        self.assertNotIn('REF = "main"', install)

    def test_the_install_cell_skips_pip_when_the_right_version_is_there_and_clears_stale_imports_after_one(self):
        install = self.code[0]
        self.assertIn("already installed", install)
        self.assertIn("PackageNotFoundError", install)
        self.assertIn("del sys.modules[name]", install)
        self.assertLess(install.index("already installed"), install.index("pip"))

    def test_it_stops_before_installing_anything_if_there_is_no_gpu(self):
        install = self.code[0]
        self.assertLess(install.index("nvidia-smi"), install.index("pip"))
        self.assertIn("T4 GPU", install)

    def test_dropdown_and_table_list_exactly_the_models_that_fit_a_t4(self):
        models = catalog.load(DATA / "models.json")
        gib = build_notebook.T4_GIB
        expected = [m["id"] for m in models.values() if catalog.runnable(m) and 0 < m.get("vram_gib", 0) <= gib]
        dropdown = json.loads(re.search(r"#@param (\[.*\])", next(s for s in self.code if "MODEL =" in s)).group(1))
        self.assertEqual(dropdown, expected)
        for model_id in expected:
            self.assertIn(f"`{model_id}`", self.text)
        for too_big in ("clef-flash`", "kev-4b"):  # 18.5 and 17.8 GiB, and the CPU-only Verdict is not offered at all
            self.assertNotIn(too_big, self.text)
        self.assertNotIn("verdict", dropdown)

    def test_expectations_are_up_front(self):
        intro = "".join(self.cells[0]["source"])
        for expected in (
            "What will happen",
            "Typical time",
            "2–9 min",
            "HF_TOKEN",
            "faster",
            "429",
            "GPU only",
            "Run all",
            "5 minutes",
            "Jev console",
            "latest log line",
        ):
            self.assertIn(expected, intro)

    def test_each_model_shows_a_typical_first_time_total(self):
        table = next(
            text
            for text in ("".join(c["source"]) for c in self.cells if c["cell_type"] == "markdown")
            if "Typical first-time total" in text
        )
        self.assertNotIn("? min", table)
        self.assertEqual(table.count(" min |"), len(build_notebook.t4_models()))

    def test_the_last_cell_guides_the_user_to_the_console(self):
        self.assertIn("notebook.console(", self.code[-1])
        self.assertIn("Jev console", "".join(self.cells[-2]["source"]))

    def test_the_public_endpoint_is_off_by_default_with_the_terms_shown(self):
        self.assertIn("SERVE = False", next(s for s in self.code if "SERVE" in s))
        self.assertIn("web service offerings", self.text)

    def test_every_cell_has_a_unique_stable_id(self):
        ids = [cell["id"] for cell in build_notebook.with_ids(build_notebook.build())]
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(ids, [cell["id"] for cell in build_notebook.with_ids(build_notebook.build())])

    def test_the_committed_notebook_is_current(self):
        committed = json.loads((Path(build_notebook.HERE) / "jevgw_colab.ipynb").read_text())["cells"]
        self.assertEqual(committed, build_notebook.with_ids(build_notebook.build()), "run python build_notebook.py")


if __name__ == "__main__":
    unittest.main()
