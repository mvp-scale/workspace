"""The gateway's state: which model is loaded, which are enabled, and per-model latency stats."""

from __future__ import annotations

import json
import statistics
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import catalog
from .backends import KINDS, Server, last_line, log
from .disk import Disk, DiskFull


class Refused(Exception):
    """A request that is valid but not allowed right now (disabled, does not fit); carries an HTTP status."""

    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


class Stats:
    """Request counts and recent latencies per model, for the panel and /v1/stats."""

    def __init__(self, keep: int = 500):
        self._lock = threading.Lock()
        self._n = defaultdict(int)
        self._errors = defaultdict(int)
        self._ms: dict[str, deque] = defaultdict(lambda: deque(maxlen=keep))
        self._done: deque = deque(maxlen=20000)  # completion times, for the recent request rate

    def record(self, model: str | None, status: int, ms: float) -> None:
        with self._lock:
            self._n[model] += 1
            self._errors[model] += status >= 400
            self._ms[model].append(ms)
            self._done.append(time.monotonic())

    def rate(self, window: float = 30.0) -> float:
        """Completed requests per second over the last `window` seconds (the real throughput, whatever the callers sent)."""
        now = time.monotonic()
        with self._lock:
            recent = [t for t in self._done if now - t <= window]
        return round(len(recent) / window, 2)

    def snapshot(self) -> dict:
        with self._lock:
            out = {}
            for model, n in self._n.items():
                ms = sorted(self._ms[model])
                out[str(model)] = {
                    "requests": n,
                    "errors": self._errors[model],
                    "p50_ms": round(statistics.median(ms), 1),
                    "p95_ms": round(ms[min(len(ms) - 1, int(len(ms) * 0.95))], 1),
                }
            return out


class Gateway:
    def __init__(self, models: dict[str, dict], cfg: dict, only: set[str] | None = None, disk: Disk | None = None):
        self.models, self.cfg, self.disk = models, cfg, disk
        self.disabled = {mid for mid in models if only is not None and mid not in only}
        self.gpu, self.gpu_mib = catalog.gpu_info()
        self.cur: Server | None = None
        self.cur_id: str | None = None
        self.loading: str | None = None
        self.load_s: float | None = None
        self.warm_ms: float | None = None
        self.error: str | None = None
        self.stats = Stats()
        self._future = None
        self.loading_since: float | None = None
        # One long-lived thread does every launch and stop (see backends._die_with_parent).
        self._pool = ThreadPoolExecutor(1, thread_name_prefix="launcher")

    def fits(self, entry: dict) -> bool:
        return catalog.fits(entry, self.gpu_mib)

    # -- state changes (each runs on the launcher thread, one at a time) ---------------------------------------------

    def select(self, model_id: str, wait: bool = True) -> None:
        """Unload the current model and load `model_id`. Safe to repeat: loaded or already loading is a no-op.

        With wait=True this blocks until the model answers. With wait=False it returns at once, the load runs in the background,
        and the state (loading, progress, error) is in status(). A failed load can simply be requested again.
        """
        entry = self._loadable(model_id)
        if self.cur_id == model_id and self.cur:
            return
        if self.loading and self.loading != model_id:
            raise Refused(f"still loading {self.loading}; wait for it to finish", 409)
        if self.loading != model_id:
            self.loading, self.error, self.loading_since = model_id, None, time.time()
            self._future = self._pool.submit(self._load, model_id, entry)
        if wait:
            self._future.result()

    def unload(self) -> None:
        self._pool.submit(self._unload).result()

    def set_enabled(self, model_id: str, enabled: bool) -> None:
        """Disabled models cannot be loaded. Disabling the loaded model unloads it."""
        if model_id not in self.models:
            raise KeyError(model_id)
        if enabled:
            self.disabled.discard(model_id)
            return
        self.disabled.add(model_id)
        if self.cur_id == model_id:
            self.unload()

    def purge(self, model_id: str) -> None:
        """Delete a model's downloaded files. The loaded model cannot be purged."""
        if model_id not in self.models:
            raise KeyError(model_id)
        if not self.disk:
            raise Refused("this gateway does not manage disk", 404)
        if model_id == self.cur_id or model_id == self.loading:
            raise Refused(f"{model_id} is loaded; unload it first")
        self.disk.delete(model_id, self.models)

    def _unload(self) -> None:
        if self.cur:
            log("unload", self.cur_id)
            self.cur.stop()
        self.cur, self.cur_id, self.load_s, self.warm_ms = None, None, None, None

    def _loadable(self, model_id: str) -> dict:
        """The catalog entry, or the reason it cannot be loaded right now."""
        if model_id not in self.models:
            raise KeyError(model_id)
        entry = self.models[model_id]
        if entry["kind"] not in KINDS:
            raise Refused(f"{model_id} has no recipe yet ({entry.get('status', 'kind ' + entry['kind'])})", 422)
        if model_id in self.disabled:
            raise Refused(f"{model_id} is disabled; enable it first", 403)
        if not self.fits(entry):
            raise Refused(f"{model_id} needs about {entry['vram_gib']} GiB; this GPU ({self.gpu or 'none'}) has "
                          f"{self.gpu_mib / 1024:.1f} GiB")  # fmt: skip
        return entry

    def _load(self, model_id: str, entry: dict) -> None:
        try:
            self._unload()
            self._require_free_gpu_memory(entry)
            self._make_room(entry)
            log("load", model_id)
            started = time.time()
            server = KINDS[entry["kind"]](entry, self.cfg)
            used_before = catalog.gpu_used_mib()
            try:
                server.start()
                self.warm_ms = server.warm()
                server.verify_gpu(used_before)
            except Exception:
                server.stop()
                raise
            if self.disk:
                self.disk.touch(model_id, time.time())
            self.cur, self.cur_id, self.load_s = server, model_id, round(time.time() - started, 1)
            log(f"ready {model_id} in {self.load_s}s (warm-up {self.warm_ms:.0f} ms)")
        except Exception as err:
            self.error = f"{type(err).__name__}: {err}"
            log("load failed:", self.error[:300])
            raise
        finally:
            self.loading, self.loading_since = None, None

    def progress(self) -> dict | None:
        """What a load in flight is doing: downloading (with GiB done) or starting the model server."""
        if not self.loading:
            return None
        entry, work = self.models[self.loading], Path(self.cfg.get("work", "."))
        elapsed = round(time.time() - self.loading_since) if self.loading_since else 0
        if self.disk and self.disk.tracks(entry) and not self.disk.cached(entry):
            if entry["kind"] == "proc":
                detail = last_line(work / f"{self.loading}.setup.log")
                return {"phase": "installing", "total_gib": entry.get("install_gib", 0), "elapsed_s": elapsed, "detail": detail}
            done, total = self.disk.downloaded_gib(entry)
            return {"phase": "downloading", "done_gib": round(done, 2), "total_gib": round(total, 2), "elapsed_s": elapsed}
        return {"phase": "starting", "elapsed_s": elapsed, "detail": last_line(work / f"{self.loading}.log")}

    def _require_free_gpu_memory(self, entry: dict) -> None:
        """Before downloading anything: is the GPU memory this model needs actually free? Something else may be using it."""
        free, need = catalog.gpu_free_mib(), entry.get("vram_gib", 0) * 1024
        if free is not None and need and free < need:
            raise Refused(
                f"{entry['id']} needs about {entry['vram_gib']} GiB of GPU memory and only {free / 1024:.1f} GiB is free: "
                "something else is using the GPU. Free it (Runtime > Restart session) and try again",
                409,
            )

    def _make_room(self, entry: dict) -> None:
        if not self.disk or not self.disk.tracks(entry):
            return
        try:
            for gone in self.disk.make_room(entry, self.models):
                log(f"disk: deleted {gone} to make room for {entry['id']}")
        except DiskFull as err:
            raise Refused(str(err), 507) from None

    # -- serving -----------------------------------------------------------------------------------------------------

    def answer(self, body: bytes) -> tuple[int, bytes, str | None]:
        """Proxy one request to the loaded model. Returns (status, body, model id)."""
        server, model_id = self.cur, self.cur_id
        if not server:
            message = f"loading {self.loading}" if self.loading else "no model loaded"
            return 503, json.dumps({"error": message}).encode(), None
        start = time.perf_counter()
        try:
            status, out = server.answer(body)
        except OSError as err:
            status, out = 502, json.dumps({"error": f"model server unreachable: {err}"}).encode()
        self.stats.record(model_id, status, (time.perf_counter() - start) * 1000)
        return status, out, model_id

    def status(self) -> dict:
        keep = ("id", "name", "kind", "vram_gib", "vision", "gpu_hint", "note", "status", "verified", "first_run_min")
        return {
            "gpu": self.gpu,
            "gpu_gib": round(self.gpu_mib / 1024, 1),
            "gpu_free_gib": None if (free := catalog.gpu_free_mib()) is None else round(free / 1024, 1),
            "loaded": self.cur_id,
            "loading": self.loading,
            "progress": self.progress(),
            "load_s": self.load_s,
            "warm_ms": None if self.warm_ms is None else round(self.warm_ms),
            "error": self.error,
            "disk": self.disk.status(self.models) if self.disk else None,
            "models": [
                {**{k: e[k] for k in keep if k in e}, "fits": self.fits(e), "loaded": mid == self.cur_id,
                 "enabled": mid not in self.disabled, "runnable": catalog.runnable(e),
                 "cached": bool(self.disk and self.disk.cached(e)),
                 "disk_gib": round(e.get("file_gib", 0) + e.get("mmproj_gib", 0) or e.get("install_gib", 0), 2) or None}
                for mid, e in self.models.items()
            ],
        }  # fmt: skip

    def shutdown(self) -> None:
        self._pool.submit(self._unload).result()
        self._pool.shutdown()
