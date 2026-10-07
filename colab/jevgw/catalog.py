"""The model catalog (models.json) and the rule for what fits a GPU."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

KINDS = {"llama", "proc", "pending", "none"}
RUNNABLE = {"llama", "proc"}
HEADROOM_MIB = 800  # CUDA context and the desktop's share: a model must fit with this much to spare
_REQUIRED = {"llama": ("repo", "file"), "proc": ("cmd",)}


class CatalogError(ValueError):
    """models.json is malformed."""


def load(path: str | Path) -> dict[str, dict]:
    """Read and validate the catalog. Returns {id: entry}, in file order."""
    models: dict[str, dict] = {}
    for entry in json.loads(Path(path).read_text())["models"]:
        for key in ("id", "name", "kind"):
            if key not in entry:
                raise CatalogError(f"entry {entry.get('id', entry)!r} is missing {key!r}")
        if entry["kind"] not in KINDS:
            raise CatalogError(f"{entry['id']}: kind {entry['kind']!r} is not one of {sorted(KINDS)}")
        for key in _REQUIRED.get(entry["kind"], ()):
            if key not in entry:
                raise CatalogError(f"{entry['id']}: kind {entry['kind']!r} needs {key!r}")
        if entry["id"] in models:
            raise CatalogError(f"duplicate id {entry['id']!r}")
        models[entry["id"]] = entry
    return models


def runnable(entry: dict) -> bool:
    return entry["kind"] in RUNNABLE


def fits(entry: dict, gpu_mib: int) -> bool:
    """True if the model's peak GPU memory fits with headroom. A model that needs none (CPU) always fits."""
    need = entry.get("vram_gib", 0) * 1024
    return need == 0 or need + HEADROOM_MIB <= gpu_mib


def gpu_info() -> tuple[str | None, int]:
    """(name, total MiB) of GPU 0, or (None, 0) on a CPU-only machine."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], text=True, timeout=10
        )
        name, mib = out.strip().splitlines()[0].rsplit(",", 1)
        return name.strip(), int(mib)
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None, 0
