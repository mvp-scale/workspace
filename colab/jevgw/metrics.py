"""GET /metrics: Prometheus text format, so any monitoring stack (Grafana, Datadog, RunPod's dashboards) can scrape the gateway.

Everything is read from state the gateway already keeps, plus one cached nvidia-smi call, so a scrape costs almost nothing.
"""

from __future__ import annotations

import time

from . import __version__, catalog

_gpu_cache: tuple[float, tuple[int, int] | None] = (0.0, None)


def _gpu() -> tuple[int, int] | None:
    """GPU utilization and memory, cached for 5 s so a scraper polling often does not run nvidia-smi every time."""
    global _gpu_cache
    now = time.monotonic()
    if now - _gpu_cache[0] > 5:
        _gpu_cache = (now, catalog.gpu_utilization())
    return _gpu_cache[1]


def _label(value) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def render(app) -> str:
    gw, lines = app.gw, []

    def metric(name: str, kind: str, help_text: str, samples: list[tuple[dict, float]]) -> None:
        lines.append(f"# HELP jevgw_{name} {help_text}")
        lines.append(f"# TYPE jevgw_{name} {kind}")
        for labels, value in samples:
            tags = ",".join(f'{k}="{_label(v)}"' for k, v in labels.items())
            lines.append(f"jevgw_{name}{{{tags}}} {value}" if tags else f"jevgw_{name} {value}")

    stats = gw.stats.snapshot()
    metric("info", "gauge", "Gateway version.", [({"version": __version__}, 1)])
    metric("uptime_seconds", "gauge", "Seconds since the gateway started.", [({}, round(time.time() - app.started))])
    metric("model_loaded", "gauge", "1 for the model on the GPU.", [({"model": gw.cur_id or "none"}, 1 if gw.cur_id else 0)])
    metric("model_load_seconds", "gauge", "How long the loaded model took to load.", [({}, gw.load_s or 0)])
    metric(
        "requests_total",
        "counter",
        "Calls to /v1/systemone that reached a model.",
        [({"model": m}, v["requests"]) for m, v in stats.items()],
    )
    metric(
        "errors_total",
        "counter",
        "Of those, calls the model server answered with an error.",
        [({"model": m}, v["errors"]) for m, v in stats.items()],
    )
    metric(
        "request_duration_ms",
        "gauge",
        "Recent latency through the gateway (includes time waiting for the model).",
        [({"model": m, "quantile": q}, v[k]) for m, v in stats.items() for q, k in (("0.5", "p50_ms"), ("0.95", "p95_ms"))],
    )
    metric("throughput_rps", "gauge", "Completed requests per second over the last 30 s.", [({}, gw.stats.rate())])
    metric("in_flight", "gauge", "Requests being served right now.", [({}, app.in_flight)])
    metric("capacity", "gauge", "Requests served at once before new ones are answered 429.", [({}, app.capacity)])
    metric("rejected_total", "counter", "Requests answered 429 because the gateway was at capacity.", [({}, app.rejected)])
    gpu = _gpu()
    if gpu:
        metric("gpu_utilization_percent", "gauge", "GPU 0 utilization.", [({}, gpu[0])])
        metric("gpu_memory_used_mib", "gauge", "GPU 0 memory in use.", [({}, gpu[1])])
    if gw.disk:
        metric("disk_free_gib", "gauge", "Free disk space for model files.", [({}, gw.disk.status(gw.models)["free_gib"])])
    return "\n".join(lines) + "\n"
