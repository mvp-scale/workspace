"""The generated notebook is short, valid, and agrees with the package's model list."""

import json
import re
import unittest
from pathlib import Path

import build_notebook
from jevgw import DATA, __version__, catalog

HERE = Path(__file__).resolve().parent.parent


class TestNotebook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cells = build_notebook.build()
        cls.code = ["".join(c["source"]) for c in cls.cells if c["cell_type"] == "code"]
        cls.text = "\n".join("".join(c["source"]) for c in cls.cells if c["cell_type"] == "markdown")

    def test_it_is_short_and_readable_with_no_blob_inside(self):
        """No bundled binaries or encoded payloads: every line in the file is something a person can read."""
        self.assertLessEqual(len(self.cells), 18)
        self.assertLess(len(json.dumps(self.cells)), 30_000)
        self.assertFalse(any("%%writefile" in src for src in self.code))
        for src in self.code:
            self.assertLess(len(src), 4_000)
            self.assertNotIn("base64", src)
            self.assertNotIn("b64decode", src)
            self.assertIsNone(re.search(r"[A-Za-z0-9+/=]{200,}", src), "a long encoded string")

    def test_code_cells_are_form_cells_with_a_title_and_compile(self):
        for cell, src in zip([c for c in self.cells if c["cell_type"] == "code"], self.code, strict=True):
            self.assertEqual(cell["metadata"], {"cellView": "form"})
            self.assertTrue(src.startswith("#@title "), src[:40])
            compile(src, "cell", "exec")

    def test_it_installs_the_package_from_the_public_repository_at_a_release_tag_it_names(self):
        install = self.code[0]
        self.assertIn(build_notebook.REPO, install)
        self.assertIn(f"subdirectory={build_notebook.SUBDIR}", install)
        self.assertIn(f'"{build_notebook.REF}"', install)
        self.assertEqual(build_notebook.REF, f"v{__version__}")  # a tag, never a branch that moves
        self.assertNotIn('"main"', install)
        self.assertIn(build_notebook.REPO, self.text)  # and the notebook says where the code comes from

    def test_the_install_cell_is_idempotent_and_fails_with_one_plain_message(self):
        install = self.code[0]
        self.assertLess(install.index("nvidia-smi"), install.index("pip"))  # no GPU: stop before installing anything
        self.assertIn("T4 GPU", install)
        self.assertIn("is already installed", install)
        self.assertLess(install.index("is already installed"), install.index("pip"))  # the right version is there: skip pip
        self.assertIn("ls-remote", install)  # an unpublished release is reported plainly before pip's long error
        self.assertIn("is not published", install)
        self.assertIn("from None", install)  # no chained traceback: Colab's error display cannot cope with one
        self.assertIn("del sys.modules[name]", install)  # after an upgrade, never keep running the old code

    def test_the_only_choices_a_person_has_to_make_are_a_model_and_optionally_a_key(self):
        params = [line for src in self.code for line in src.splitlines() if "#@param" in line]
        names = [line.split("=")[0].strip() for line in params]
        self.assertEqual(names, ["API_KEY", "MODEL", "IMAGE", "VIDEO", "SERVE", "ACTION"])
        self.assertIn('API_KEY = ""', "\n".join(params))  # empty by default: a random key is made and printed

    def test_dropdown_and_table_list_exactly_the_models_that_fit_a_t4(self):
        models = catalog.load(DATA / "models.json")
        expected = [m["id"] for m in models.values() if catalog.runnable(m) and 0 < m.get("vram_gib", 0) <= build_notebook.T4_GIB]
        dropdown = json.loads(re.search(r"#@param (\[.*\])", next(s for s in self.code if "MODEL =" in s)).group(1))
        self.assertEqual(dropdown, expected)
        for model_id in expected:
            self.assertIn(f"`{model_id}`", self.text)
        for too_big in ("clef-flash`", "kev-4b"):
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
            t
            for t in ("".join(c["source"]) for c in self.cells if c["cell_type"] == "markdown")
            if "Typical first-time total" in t
        )
        self.assertNotIn("? min", table)
        self.assertEqual(table.count(" min |"), len(build_notebook.t4_models()))

    def test_the_public_endpoint_cell_prints_a_console_address_that_opens_the_whole_console(self):
        serve = next(src for src in self.code if "SERVE" in src)
        self.assertIn("/#key=", serve)
        self.assertIn("manage the gateway from any browser", serve)
        self.assertIn("/healthz", serve)

    def test_the_second_cell_opens_the_console_as_a_link_not_an_embedded_window(self):
        start = next(src for src in self.code if "notebook.start" in src)
        self.assertIn("notebook.show_panel(info)", start)
        self.assertNotIn("inline", start)

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
        committed = json.loads((HERE / "jevgw_colab.ipynb").read_text())["cells"]
        self.assertEqual(committed, build_notebook.with_ids(build_notebook.build()), "run python build_notebook.py")


if __name__ == "__main__":
    unittest.main()
