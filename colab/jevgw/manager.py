"""The gateway's state: which model is loaded, which are enabled, and per-model latency stats."""

from __future__ import annotations

import json
import statistics
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor

from . import catalog
from .backends import KINDS, Server, log


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

    def record(self, model: str | None, status: int, ms: float) -> None:
        with self._lock:
            self._n[model] += 1
            self._errors[model] += status >= 400
            self._ms[model].append(ms)

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
    def __init__(self, models: dict[str, dict], cfg: dict, only: set[str] | None = None):
        self.models, self.cfg = models, cfg
        self.disabled = {mid for mid in models if only is not None and mid not in only}
        self.gpu, self.gpu_mib = catalog.gpu_info()
        self.cur: Server | None = None
        self.cur_id: str | None = None
        self.loading: str | None = None
        self.load_s: float | None = None
        self.warm_ms: float | None = None
        self.error: str | None = None
        self.stats = Stats()
        # One long-lived thread does every launch and stop (see backends._die_with_parent).
        self._pool = ThreadPoolExecutor(1, thread_name_prefix="launcher")

    def fits(self, entry: dict) -> bool:
        return catalog.fits(entry, self.gpu_mib)

    # -- state changes (each runs on the launcher thread, one at a time) ---------------------------------------------

    def select(self, model_id: str) -> None:
        """Unload the current model and load `model_id`. Blocks until it answers."""
        if model_id not in self.models:
            raise KeyError(model_id)
        self._pool.submit(self._select, model_id).result()

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

    def _unload(self) -> None:
        if self.cur:
            log("unload", self.cur_id)
            self.cur.stop()
        self.cur, self.cur_id, self.load_s, self.warm_ms = None, None, None, None

    def _select(self, model_id: str) -> None:
        entry = self.models[model_id]
        if self.cur_id == model_id and self.cur:
            return
        if entry["kind"] not in KINDS:
            raise Refused(f"{model_id} has no recipe yet ({entry.get('status', 'kind ' + entry['kind'])})", 422)
        if model_id in self.disabled:
            raise Refused(f"{model_id} is disabled; enable it first", 403)
        if not self.fits(entry):
            raise Refused(f"{model_id} needs about {entry['vram_gib']} GiB; this GPU ({self.gpu or 'none'}) has "
                          f"{self.gpu_mib / 1024:.1f} GiB")  # fmt: skip
        self.loading, self.error = model_id, None
        try:
            self._unload()
            log("load", model_id)
            started = time.time()
            server = KINDS[entry["kind"]](entry, self.cfg)
            try:
                server.start()
            except Exception:
                server.stop()
                raise
            self.warm_ms = server.warm()
            self.cur, self.cur_id, self.load_s = server, model_id, round(time.time() - started, 1)
            log(f"ready {model_id} in {self.load_s}s (warm-up {self.warm_ms:.0f} ms)")
        except Exception as err:
            self.error = f"{type(err).__name__}: {err}"
            log("load failed:", self.error[:300])
            raise
        finally:
            self.loading = None

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
        keep = ("id", "name", "kind", "vram_gib", "vision", "gpu_hint", "note", "status", "verified")
        return {
            "gpu": self.gpu,
            "gpu_gib": round(self.gpu_mib / 1024, 1),
            "loaded": self.cur_id,
            "loading": self.loading,
            "load_s": self.load_s,
            "warm_ms": None if self.warm_ms is None else round(self.warm_ms),
            "error": self.error,
            "models": [
                {**{k: e[k] for k in keep if k in e}, "fits": self.fits(e), "loaded": mid == self.cur_id,
                 "enabled": mid not in self.disabled, "runnable": catalog.runnable(e)}
                for mid, e in self.models.items()
            ],
        }  # fmt: skip

    def shutdown(self) -> None:
        self._pool.submit(self._unload).result()
        self._pool.shutdown()
