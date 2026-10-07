"""The generated notebook is short, valid, and agrees with the package's model list."""

import base64
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import build_notebook
from jevgw import DATA, __version__, catalog

HERE = Path(__file__).resolve().parent.parent


class TestNotebook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wheel = build_notebook.make_wheel()
        cls.cells = build_notebook.build(cls.wheel)
        cls.code = ["".join(c["source"]) for c in cls.cells if c["cell_type"] == "code"]
        cls.text = "\n".join("".join(c["source"]) for c in cls.cells if c["cell_type"] == "markdown")

    def embedded(self):
        """The wheel exactly as the notebook's code would decode it."""
        namespace: dict = {}
        exec(next(src for src in self.code if "JEVGW_WHEEL_B64" in src).split("\n", 1)[1], namespace)  # noqa: S102
        return namespace, base64.b64decode(namespace["JEVGW_WHEEL_B64"])

    def test_it_is_compact_and_holds_no_source_files(self):
        self.assertLessEqual(len(self.cells), 18)
        self.assertFalse(any("%%writefile" in src for src in self.code))
        visible = [src for src in self.code if "JEVGW_WHEEL_B64" not in src]
        self.assertLess(len("".join(visible)), 12_000)  # everything a person might read; the package itself is one collapsed cell

    def test_code_cells_are_form_cells_with_a_title_and_compile(self):
        for cell, src in zip([c for c in self.cells if c["cell_type"] == "code"], self.code, strict=True):
            self.assertEqual(cell["metadata"], {"cellView": "form"})
            self.assertTrue(src.startswith("#@title "), src[:40])
            compile(src, "cell", "exec")

    def test_nothing_is_fetched_from_github_to_run_it(self):
        for src in self.code:
            self.assertNotIn(
                "github.com", src.replace('https://github.com"', "")
            )  # the network pre-check names the host; nothing installs from it
            self.assertNotIn("git+", src)
            self.assertNotIn("ls-remote", src)

    def test_the_embedded_package_matches_the_repository_exactly(self):
        namespace, wheel = self.embedded()
        self.assertEqual(hashlib.sha256(wheel).hexdigest(), namespace["JEVGW_SHA256"])
        self.assertEqual(namespace["JEVGW_VERSION"], __version__)
        with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
            packaged = {n: archive.read(n) for n in archive.namelist() if n.startswith("jevgw/")}
        repo = {
            f"jevgw/{p.relative_to(HERE / 'jevgw').as_posix()}": p.read_bytes()
            for p in (HERE / "jevgw").rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        }
        self.assertEqual(packaged, repo)  # every file, byte for byte: the notebook cannot drift from the code

    def test_the_wheel_is_built_the_same_way_every_time(self):
        self.assertEqual(build_notebook.make_wheel(), self.wheel)

    def test_the_embedded_package_installs_without_a_network_and_imports(self):
        _, wheel = self.embedded()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / f"jevgw-{__version__}-py3-none-any.whl"
            path.write_bytes(wheel)
            pip = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-q",
                    "--no-deps",
                    "--no-index",
                    "--target",
                    f"{folder}/site",
                    str(path),
                ],
                capture_output=True,
                text=True,
            )
            if "No module named pip" in pip.stderr:
                self.skipTest("pip is not available here")
            self.assertEqual(pip.returncode, 0, pip.stderr)
            check = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import jevgw, jevgw.notebook, jevgw.server; from jevgw import DATA, catalog; print(jevgw.__version__, len(catalog.load(DATA / 'models.json')), (DATA / 'vendor' / 'dev-bench-setup.sh').exists())",
                ],
                env={**os.environ, "PYTHONPATH": f"{folder}/site"},
                capture_output=True,
                text=True,
                cwd=folder,
            )
        self.assertEqual(check.stdout.strip(), f"{__version__} 13 True", check.stderr)

    def test_the_install_cell_is_idempotent_checks_the_hash_and_fails_with_one_message(self):
        install = next(src for src in self.code if "nvidia-smi" in src and "pip" in src)
        self.assertLess(install.index("nvidia-smi"), install.index("pip"))  # no GPU: stop before installing anything
        self.assertIn("T4 GPU", install)
        self.assertIn("is already installed", install)
        self.assertLess(install.index("is already installed"), install.index("pip"))
        self.assertIn("checksum mismatch", install)
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
        ids = [cell["id"] for cell in build_notebook.with_ids(build_notebook.build(self.wheel))]
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(ids, [cell["id"] for cell in build_notebook.with_ids(build_notebook.build(self.wheel))])

    def test_the_committed_notebook_is_current(self):
        committed = json.loads((HERE / "jevgw_colab.ipynb").read_text())["cells"]
        self.assertEqual(committed, build_notebook.with_ids(build_notebook.build(self.wheel)), "run python build_notebook.py")


if __name__ == "__main__":
    unittest.main()
