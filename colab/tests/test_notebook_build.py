"""The generated notebook carries every source file, and its code cells are valid Python."""

import json
import unittest
from pathlib import Path

import build_notebook

HERE = Path(__file__).resolve().parent.parent


class TestNotebook(unittest.TestCase):
    def setUp(self):
        self.cells = build_notebook.build()
        self.sources = ["".join(c["source"]) for c in self.cells if c["cell_type"] == "code"]

    def test_every_module_and_the_panel_are_written_by_the_notebook(self):
        written = {src.splitlines()[0].split()[-1] for src in self.sources if src.startswith("%%writefile")}
        for module in (HERE / "jevgw").glob("*.py"):
            self.assertIn(f"{build_notebook.APP}/jevgw/{module.name}", written, module.name)
        self.assertIn(f"{build_notebook.APP}/jevgw/ui/index.html", written)

    def test_written_files_match_the_repository(self):
        for src in self.sources:
            if src.startswith("%%writefile") and src.splitlines()[0].endswith(".py"):
                name = src.splitlines()[0].split("/")[-1]
                self.assertEqual(src.split("\n", 1)[1].rstrip(), (HERE / "jevgw" / name).read_text().rstrip(), name)

    def test_code_cells_compile(self):
        for src in self.sources:
            if not src.startswith(("%%", "!")):
                compile(src, "cell", "exec")

    def test_only_models_that_run_on_stock_llama_cpp(self):
        catalog = json.loads(next(s for s in self.sources if "/models.json" in s.splitlines()[0]).split("\n", 1)[1])
        self.assertEqual({m["kind"] for m in catalog["models"]}, {"llama"})


if __name__ == "__main__":
    unittest.main()
