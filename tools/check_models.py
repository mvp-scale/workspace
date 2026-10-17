"""Fails if a console page or script keeps its own list of models instead of using the one registry.

The registry is demo/models.json (who) + demo/backends.py (how to reach it, what it can do), served by demo/registry.py at
/api/models and read in pages through Jev.models(). This check scans demo/*.html, demo/static/*.js and demo/*.py for:
  - a list or object naming two or more registered model ids  (a page-local model list)
  - a comparison against one model id, e.g. id === "jev"      (a page-local rule about one model)
Allowed: the registry files themselves, and per-model run scripts that must name the model they start (ALLOW below).
A line can opt out with the marker  registry-ok: <reason>  when the id is data (a column key), not a list of models.
Run: python3 tools/check_models.py   (exit 1 and the offending lines when something is found)
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
ALLOW = {"models.json", "backends.py", "registry.py", "mask.json",
         "vram.py", "serve_inproc.py", "serve_kev.py"}   # per-model start-up / measurement scripts: naming the model is their job
ids = [m["id"] for m in json.loads((DEMO / "models.json").read_text())["models"]]
q = "|".join(re.escape(i) for i in sorted(ids, key=len, reverse=True))
LIST = re.compile(rf"[\[{{][^\]}}\n]*?[\"']({q})[\"'][^\]}}\n]*?[\"']({q})[\"']")          # two ids inside one [...] or {...}
KEYS = re.compile(rf"\{{\s*\"?({q})\"?\s*:[^}}\n]*,\s*\"?({q})\"?\s*:")                   # {laya: ..., verdict: ...}
CMP = re.compile(rf"(===|!==|==|!=)\s*[\"']({q})[\"']|[\"']({q})[\"']\s*(===|!==|==|!=)|\.(includes|startsWith|indexOf|has)\(\s*[\"']({q})[\"']")  # id === "jev", list.includes("winnow")

bad = []
for f in sorted([*DEMO.glob("*.html"), *(DEMO / "static").glob("*.js"), *DEMO.glob("*.py")]):
    if f.name in ALLOW: continue
    for n, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
        if "registry-ok:" in line: continue
        for rx, why in ((LIST, "a list of models"), (KEYS, "an object keyed by model ids"), (CMP, "a rule about one model id")):
            if rx.search(line): bad.append(f"{f.relative_to(ROOT)}:{n}: {why}: {line.strip()[:140]}"); break
print("\n".join(bad) if bad else f"ok: no page-local model lists ({len(ids)} registered models)")
sys.exit(1 if bad else 0)
