"""Disk budget for downloaded model files.

A Colab session has far less disk than a server, and a GGUF is several GiB, so downloads are budgeted: at most `keep` models stay on
disk and a margin of free space is always left. Before a model is downloaded, the least recently used ones are deleted until it fits.
Files are shared between models (both Clef quants use one vision projector), so a file is deleted only when no other cached model,
and not the one about to load, needs it.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

GIB = 2**30


class DiskFull(Exception):
    """The model cannot be made to fit on disk, even after deleting every other cached model."""


def files_of(entry: dict) -> dict[str, float]:
    """{file name: expected GiB} for what a model needs on disk. Empty for models that bring their own install."""
    if entry.get("kind") != "llama":
        return {}
    files = {entry["file"]: entry.get("file_gib", 0.0)}
    if entry.get("mmproj"):
        files[entry["mmproj"]] = entry.get("mmproj_gib", 0.0)
    return files


class Disk:
    def __init__(
        self, folder: str | Path, state_file: str | Path, keep: int = 2, margin_gib: float = 5.0, usage=shutil.disk_usage
    ):
        self.folder, self.state_file = Path(folder), Path(state_file)
        self.keep, self.margin = keep, margin_gib * GIB
        self._usage = usage
        self.folder.mkdir(parents=True, exist_ok=True)

    # -- what is on disk ---------------------------------------------------------------------------------------------

    def cached(self, entry: dict) -> bool:
        names = files_of(entry)
        return bool(names) and all((self.folder / name).exists() for name in names)

    def _missing_bytes(self, entry: dict) -> float:
        return sum(gib * GIB for name, gib in files_of(entry).items() if not (self.folder / name).exists())

    def _stamps(self) -> dict[str, float]:
        try:
            return json.loads(self.state_file.read_text())
        except (OSError, ValueError):
            return {}

    def touch(self, model_id: str, now: float) -> None:
        """Record that a model was just used (it is then the last to be deleted)."""
        stamps = self._stamps()
        stamps[model_id] = now
        self.state_file.write_text(json.dumps(stamps))

    def downloaded_gib(self, entry: dict) -> tuple[float, float]:
        """(GiB on disk so far, GiB expected) for a model, counting a download in flight.

        A download goes to `.partial/<name>.incomplete` (see download.py). The gateway loads one model at a time and downloads its files one
        after another, so every partial file counts.
        """
        partial = self.folder / ".partial"
        done = sum(f.stat().st_size for f in partial.glob("*.incomplete"))
        done += sum((self.folder / name).stat().st_size for name in files_of(entry) if (self.folder / name).exists())
        return done / GIB, sum(files_of(entry).values())

    def free_gib(self) -> float:
        return self._usage(self.folder).free / GIB

    def status(self, models: dict[str, dict]) -> dict:
        usage = self._usage(self.folder)
        return {
            "free_gib": round(usage.free / GIB, 1),
            "total_gib": round(usage.total / GIB, 1),
            "keep": self.keep,
            "cached": [mid for mid, entry in models.items() if self.cached(entry)],
        }

    # -- making room -------------------------------------------------------------------------------------------------

    def make_room(self, target: dict, models: dict[str, dict]) -> list[str]:
        """Delete least recently used cached models until `target` fits within `keep` and the free-space margin.

        Returns the ids deleted. Raises DiskFull if it still cannot fit.
        """
        need = self._missing_bytes(target)
        stamps = self._stamps()
        others = sorted(
            (mid for mid, e in models.items() if e is not target and self.cached(e)), key=lambda mid: stamps.get(mid, 0)
        )
        evicted: list[str] = []
        while True:
            fits_count = len(others) + 1 <= self.keep
            fits_space = need == 0 or self._usage(self.folder).free - need >= self.margin  # nothing to download, nothing to fit
            if fits_count and fits_space:
                return evicted
            if not others:
                raise DiskFull(
                    f"{target['id']} needs {need / GIB:.1f} GiB more disk, with {self.margin / GIB:.0f} GiB kept free; "
                    f"{self.free_gib():.1f} GiB is free after deleting every other model"
                )
            victim = others.pop(0)
            self.delete(victim, models, keep_for=target)
            evicted.append(victim)

    def delete(self, model_id: str, models: dict[str, dict], keep_for: dict | None = None) -> None:
        """Delete a model's files, except any still needed by `keep_for` or by another cached model."""
        needed: set[str] = set(files_of(keep_for)) if keep_for else set()
        for other_id, other in models.items():
            if other_id != model_id and self.cached(other):
                needed |= set(files_of(other))
        for name in files_of(models[model_id]):
            if name not in needed:
                (self.folder / name).unlink(missing_ok=True)
