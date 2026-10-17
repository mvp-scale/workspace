"""The one model registry. Standard library only.

Every page and script gets its list of models from here (served at /api/models; pages read it through Jev.models()),
so a model is added in exactly one place and shows up everywhere:
  demo/models.json   who each model is (id, code, name, facts, card text) -- the list and its order
  demo/backends.py   how to reach it (address, key) and what it can do (hosted = paid API; library_only = answers only
                     the yes/no questions it has learned, e.g. BitMob)
  stored results     which benchmark tiers, published probe sets and image tasks it has answers for, so a page can show
                     "not run yet" instead of leaving the model out
Nothing secret leaves this module: no addresses, no keys.
"""
import json
from pathlib import Path

import backends

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BENCH = ROOT / "data" / "bench"
PROBE_RUNS = ROOT / "data" / "probe-runs-v2"
IMAGE_RUNS = ROOT / "data" / "image-lab" / "runs"


def _sheet():
    return json.loads((HERE / "models.json").read_text())


def _probe_sets():
    return [f.stem for f in (ROOT / "probes" / "v2").glob("*.jsonl")]


def _results(mid):
    """What this model has stored answers for (counts only; the pages fetch the answers themselves)."""
    tiers = sorted(p.parent.name[len(mid) + 1:] for p in BENCH.glob(f"{mid}-*/summary.json") if p.parent.name[len(mid) + 1:] in ("easy", "original", "hard"))
    sets = sum(1 for st in _probe_sets() if (PROBE_RUNS / f"{mid}-{st}" / "results.jsonl").is_file())
    images = sum(1 for _ in (IMAGE_RUNS / mid).glob("*/results.jsonl")) if (IMAGE_RUNS / mid).is_dir() else 0
    try: p50 = json.loads((BENCH / f"{mid}-hard" / "summary.json").read_text()).get("latency", {}).get("p50_s")
    except (OSError, ValueError): p50 = None
    return {"bench_tiers": tiers, "probe_sets": sets, "image_tasks": images, "hard_p50_s": p50}


def models():
    """Every model, in registry order, with its facts, abilities and stored-result counts."""
    out = []
    for m in _sheet()["models"]:
        b = backends.BACKENDS.get(m["id"])
        out.append({**m,
                    "live": b is not None,                                   # has an address, so it can be loaded and asked
                    "hosted": bool(b and b["hosted"]),                       # a paid API
                    "library_only": bool(b and b["library_only"]),           # answers only the questions it has learned
                    "retired": m.get("retired"),                             # a reason, or None: retired models are hidden from every list
                    "results": _results(m["id"])})
    return out


def payload():
    """The /api/models body: the registry plus the sheet's notes and code rule."""
    s = _sheet()
    return {**{k: v for k, v in s.items() if k != "models"}, "models": models()}


def ids():
    return [m["id"] for m in _sheet()["models"]]
