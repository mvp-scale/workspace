"""Local demo: benchmark results viewer + live side-by-side compare of jeff, kev and hosted Jev.

    TYPESAFE_API_KEY=... python3 demo/server.py      # then open http://127.0.0.1:8100

The TypeSafe key stays server-side. Binds to 127.0.0.1 by default; set DEMO_HOST to expose it
(anyone who can reach the port can spend the key).
"""
import gzip
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import outside_api  # /v1/* for other systems: URL + API key (see its docstring)
import backends  # the TypeSafe models (address, key, model label) and the classifier's teacher setting
import registry  # the one list of models every page uses (demo/registry.py)
import audio_library  # read-only data/audio library for /flow-lab
import detector_api  # detector files + AI-drafted detectors for /flow-lab
import intake_api  # Latent lab intake: local-vs-Clef verdict per question
import idea_api  # random example ideas (crazy tech, ridiculous products, local shocks...) for /worldengine
import imagelab_api  # image tasks and stored answers for /imagelab
import persona_api  # seeded personas, extractors and audience scoring for /personalab

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "probes"))
try:
    import lab_custom_decompose as lcd  # noqa: E402 -- custom decomposition ("orbit map"); PyYAML-dependent, see below
    _LCD_ERROR = None
except Exception as e:  # PyYAML missing, or a library-file problem -- fail soft, not at import time
    lcd = None
    _LCD_ERROR = str(e)
_decompose_lock = threading.Lock()
BENCH = Path(os.environ.get("BENCH_DIR", HERE.parent / "data" / "bench"))
BACKENDS = backends.BACKENDS  # the TypeSafe models, ids as on the leaderboard: one list for every process (demo/backends.py)


def call(name, cfg, body, whole=False):
    if name.startswith("jev") and not cfg["key"]:
        return {"backend": name, "error": "TYPESAFE_API_KEY not set"}
    headers = {"Content-Type": "application/json", "User-Agent": "jev-demo/0.1"}
    if cfg["key"]:
        headers["Authorization"] = f"Bearer {cfg['key']}"
    body = {**body, "model": cfg.get("model", "jev-latest")}  # each model's own label (demo/backends.py)
    req = urllib.request.Request(cfg["url"].rstrip("/") + "/v1/systemone", json.dumps(body).encode(), headers)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data, status, resp_headers = json.load(r), r.status, dict(r.headers.items())
    except urllib.error.HTTPError as e:
        if cfg.get("library_only") and e.code in (400, 422):   # BitMob: say why, instead of a generic "did not accept"
            return {"backend": name, "plain": True, "error": "BitMob could not read this request: " + e.read()[:200].decode("utf-8", "replace")}
        return {"backend": name, "error": f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"}
    except Exception as e:  # connection refused, timeout, bad JSON
        return {"backend": name, "error": f"{type(e).__name__}: {e}"}
    if whole and cfg.get("library_only") and not (data.get("answers") or {}).get("decision"):   # BitMob: the decision is not one it has learned
        return {"backend": name, "plain": True, "error": "Not in BitMob's library: it answers only the yes/no questions it has learned (Latent lab lists them)."}
    if whole:
        return {"backend": name, "status": status, "latency_ms": round((time.perf_counter() - t0) * 1000), "model": data.get("model"),
                "answers": data.get("answers") or {}, "extras": extras(data, {}, resp_headers)}
    answer = (data.get("answers") or {}).get("decision") or {}
    if cfg.get("library_only") and not answer:   # BitMob: the question is not one it has learned
        return {"backend": name, "plain": True, "error": "Not in BitMob's library: it answers only the yes/no questions it has learned (Latent lab lists them)."}
    return {"backend": name, "status": status, "latency_ms": round((time.perf_counter() - t0) * 1000),
            "model": data.get("model"), "answer": answer, "extras": extras(data, answer, resp_headers)}


COMPARABLE_ANSWER_KEYS = {"type", "choice", "score", "noul", "confidence", "probabilities", "legend"}


def flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(flatten(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out


def extras(data, answer, headers):
    """Everything a backend returned beyond the comparable answer, kept verbatim and grouped by where it came from."""
    return {
        "response": flatten({k: v for k, v in data.items() if k not in ("answers", "model")}),
        "headers": {k.lower(): v for k, v in headers.items() if k.lower().startswith("x-")},
        "answer": {k: v for k, v in answer.items() if k not in COMPARABLE_ANSWER_KEYS},
    }


MAX_BATCH_ITEMS = int(os.environ.get("DEMO_MAX_BATCH", "400"))  # protects the paid key from a runaway page
_cache = {}


def one_item(name, cfg, item):
    """One state with a battery of questions in a single call; cached by content, so re-runs are free."""
    key = hashlib.sha256(json.dumps([name, item], sort_keys=True).encode()).hexdigest()
    if key in _cache:
        return {**_cache[key], "cached": True}
    r = call(name, cfg, {"state": item["state"], "questions": item["questions"]}, whole=True)
    if "error" not in r:
        _cache[key] = r
    return r


def batch(backend, items):
    if backend not in BACKENDS:
        raise KeyError(backend)
    cfg = BACKENDS[backend]
    with ThreadPoolExecutor(min(8, max(1, len(items)))) as ex:
        return list(ex.map(lambda it: one_item(backend, cfg, it), items))


ROOT = HERE.parent
PROBES = ROOT / "probes" / "v2"
PROBE_RUNS = Path(os.environ.get("PROBE_RUNS", ROOT / "data" / "probe-runs-v2"))


def read_jsonl(path):
    # str.splitlines() also breaks on Unicode line/paragraph separators and NEL, which can appear
    # raw inside a JSON string value (ensure_ascii=False) and would corrupt that record's JSON.
    # A JSONL file only delimits records on '\n'.
    return [json.loads(line) for line in path.read_text().split("\n") if line.strip()]


def probe_sets():
    """Published probe sets with their provenance, so the page can show where every number comes from."""
    out = []
    for f in sorted(PROBES.glob("*.jsonl")):
        rows = read_jsonl(f)
        prov = rows[0].get("provenance", {})
        questions = {r["question"]["instructions"] for r in rows}
        classes = {}
        for r in rows:
            classes[r["expected"]] = classes.get(r["expected"], 0) + 1
        out.append({"id": f.stem, "n": len(rows), "classes": classes, "labels": rows[0]["labels"], "type": rows[0]["question"]["type"],
                    "questions": sorted(questions), "source": prov.get("source"), "url": prov.get("url"), "license": prov.get("license"),
                    "models_run": sorted(d.name[: -len(f.stem) - 1] for d in PROBE_RUNS.glob(f"*-{f.stem}") if (d / "results.jsonl").exists())})
    return out


class _Memo(bytes):
    """A remembered JSON answer; keeps its gzip copy so compressing is not repeated either."""
    def gz(self):
        if not hasattr(self, "_gz"): self._gz = gzip.compress(self, 5)
        return self._gz


_memo, _memo_locks, _memo_guard = {}, {}, threading.Lock()


def _memo_compute(key, fn):
    with _memo_guard: lock = _memo_locks.setdefault(key, threading.Lock())
    with lock:
        raw = _Memo(json.dumps(fn()).encode())           # an exception (unknown set) is not remembered
        _memo[key] = (time.time(), raw)
        return raw


def memo(key, fn, ttl=60):
    """Answers built from files on disk (leaderboard, probe sets) change only when a benchmark run writes new files, so
    each is computed once and kept in memory. Once older than `ttl` seconds the kept answer is still served at once and a
    fresh one is computed in the background, so nobody waits and new results appear within about a minute. Live state
    (/api/status, /api/services) is never kept here. One lock per key, so ten pages asking at once compute once."""
    hit = _memo.get(key)
    if hit is None: return _memo_compute(key, fn)
    if time.time() - hit[0] >= ttl and not _memo_locks.get(key, threading.Lock()).locked():
        threading.Thread(target=lambda: _memo_compute(key, fn), daemon=True).start()
    return hit[1]


def warm_memo():
    """Compute the remembered answers once at start, in the background, so the first visitor does not wait either."""
    try:
        memo("leaderboard", leaderboard); memo("agreement", probe_agreement); memo("probe-macro", probe_macro); memo("imagelab", imagelab_api.payload)
        sets = probe_sets(); memo("probes", lambda: sets)
        for x in sets: memo("probe:" + x["id"], lambda i=x["id"]: probe_detail(i))
    except Exception as e: print("warm-up skipped:", e, flush=True)


def probe_detail(set_id):
    f = PROBES / f"{set_id}.jsonl"
    if not f.is_file() or "/" in set_id:
        raise KeyError(set_id)
    items = read_jsonl(f)
    notes = PROBES / f"{set_id}.md"
    if not notes.is_file():  # sets that share one notes file, e.g. the two sarcasm sets
        notes = next(iter(sorted(PROBES.glob(f"{set_id.split('_')[0]}*.md"))), None)
    results = {}
    for d in PROBE_RUNS.glob(f"*-{set_id}"):
        rp = d / "results.jsonl"
        if rp.exists():
            results[d.name[: -len(set_id) - 1]] = {r["task_id"]: {"predicted": r.get("predicted"), "probs": r.get("probs"), "correct": bool(r.get("correct")),
                                                                   "latency_s": r.get("latency_s")} for r in read_jsonl(rp)}
    return {"id": set_id, "items": [{"id": r["id"], "state": r["state"], "expected": r["expected"], "labels": r["labels"], "question": r["question"],
                                       "family": r.get("family"), "group": r.get("group"), "notes": r.get("provenance", {}).get("notes")} for r in items],
            "results": results, "notes": notes.read_text() if notes else None}


def speeches():
    return [json.loads(f.read_text()) | {"slug": f.stem} for f in sorted((PROBES / "speeches").glob("*.json"))]


def scenes():
    """Real, cited scenes with their documented events."""
    return [json.loads(f.read_text()) | {"slug": f.stem} for f in sorted((PROBES / "scenes").glob("*.json"))]


def window_study():
    """Stored results of probes/window_study.py, keyed by backend."""
    d = ROOT / "data" / "window-study"
    return {f.stem: json.loads(f.read_text()) for f in sorted(d.glob("*.json"))} if d.is_dir() else {}


def hierarchy_study():
    """Stored results of probes/lab_hierarchy.py, keyed by backend."""
    d = PROBE_RUNS / "_hierarchy"
    return {f.stem: json.loads(f.read_text()) for f in sorted(d.glob("*.json"))} if d.is_dir() else {}


def time_study():
    """Stored results of probes/lab_time.py, keyed by backend. Per-dialogue 'series' arrays are
    dropped here (only used by lab_time.py itself for local inspection) to keep the payload small;
    the page only needs the per-dialogue summary fields."""
    d = PROBE_RUNS / "_time"
    out = {}
    for f in sorted(d.glob("*.json")) if d.is_dir() else []:
        rec = json.loads(f.read_text())
        rec["dialogues"] = [{k: v for k, v in dd.items() if k != "series"} for dd in rec.get("dialogues", [])]
        out[f.stem] = rec
    return out


def vram():
    """Measured GPU memory per model (demo/vram.py). steady = the most a running server needed under load."""
    f = HERE / "vram.json"
    if not f.is_file():
        return {"models": {}}
    d = json.loads(f.read_text())
    for m in d["models"].values():
        m["steady_peak_mb"] = m.get("gpu_workload_peak_mb", m["gpu_peak_mb"])
        m["startup_peak_mb"] = m["gpu_peak_mb"]
    return d


def probe_runs():
    """{model: {set: {item id: result}}} from the stored published-set runs."""
    out = {}
    for d in sorted(PROBE_RUNS.glob("*/results.jsonl")):
        run = d.parent.name
        for s in (f.stem for f in PROBES.glob("*.jsonl")):
            if run.endswith("-" + s):
                out.setdefault(run[: -len(s) - 1], {})[s] = {r["task_id"]: r for r in read_jsonl(d) if r.get("ok")}
    return out


def batch_perf():
    """{set: {model: [{size, n, failed, k, p50_ms, p90_ms, answered, errors}]}} from probes/lab_batch.py runs."""
    out = {}
    for f in sorted(PROBE_RUNS.glob("_batch/*/*/results.jsonl")):
        recs = read_jsonl(f)
        rows = []
        for size in sorted({r["size"] for r in recs}):
            rs = [r for r in recs if r["size"] == size]
            ok = [r for r in rs if not r.get("error")]
            lat = sorted(r["latency_ms"] for r in ok)
            errs = {}
            for r in rs:
                if r.get("error"):
                    errs[r["error"][:80]] = errs.get(r["error"][:80], 0) + 1
            rows.append({"size": size, "n": len(ok), "failed": len(rs) - len(ok), "k": sum(1 for r in ok if r["correct"]),
                         "p50_ms": lat[len(lat) // 2] if lat else None, "p90_ms": lat[int(len(lat) * .9)] if lat else None,
                         "answered": min((r["answered"] for r in ok), default=None), "errors": errs})
        out.setdefault(f.parent.parent.name, {})[f.parent.name] = rows
    return out


def decompose_tree():
    """The decompose-and-loop worked example: exploiting high-bandwidth RAM across Cloudflare Edge
    Workers, decomposed and scored by every loaded model, from probes/lab_decompose.py
    --tree probes/decompose/tree_ref_edge.json. (The original worked example, this project's own
    build plan, is still scored at data/probe-runs-v2/_decompose/tree_scored.json if wanted.)"""
    p = PROBE_RUNS / "_decompose" / "tree_scored_edge.json"
    if not p.is_file():
        return {"nodes": [], "models": []}
    return json.loads(p.read_text())


def monte_carlo_schedule():
    """Monte Carlo schedule risk analysis (PMI/PMBOK QSRA) over the same worked example as
    decompose_tree(), from probes/decompose/build_monte_carlo.py. Pure computation over
    hand-authored data -- no model calls, unlike decompose_tree()."""
    p = ROOT / "probes" / "decompose" / "monte_carlo_schedule.json"
    if not p.is_file():
        return {"tasks": []}
    return json.loads(p.read_text())


def decompose_examples():
    """The 7 existing foundry/ideas/*.json intakes -- the only idea-specific content foundry's one
    rule allows Claude to author -- so the custom-decomposition page gets example chips without
    anyone writing anything new for it. Reads only idea/customer, even where a file also has a
    (historical, pre-live-mechanism) 'pieces' field."""
    out = []
    for f in sorted((ROOT / "foundry" / "ideas").glob("*.json")):
        d = json.loads(f.read_text())
        out.append({"id": f.stem, "idea": d.get("idea", ""), "customer": d.get("customer", "")})
    return out


def probe_macro():
    """Mean accuracy per model over the published sets, and the sets each ran."""
    return {m: {"macro": sum(sum(r["correct"] for r in rs.values()) / len(rs) for rs in sets.values()) / len(sets), "n_sets": len(sets)} for m, sets in probe_runs().items() if sets}


def probe_agreement():
    """How often two models give the same answer on the same published items."""
    runs = probe_runs()
    models = sorted(runs)
    matrix = {a: {} for a in models}
    for a in models:
        for b in models:
            same = n = 0
            for s, ra in runs[a].items():
                for i, r in ra.items():
                    o = runs[b].get(s, {}).get(i)
                    if o is not None:
                        n += 1
                        same += r.get("predicted") == o.get("predicted")
            matrix[a][b] = same / n if n else None
    return {"models": models, "agreement": matrix}


def leaderboard():
    """One row per model, with every tier that has a finished run."""
    models = {}
    for p in sorted(BENCH.glob("*/summary.json")):
        model, _, tier = p.parent.name.rpartition("-")
        s = json.loads(p.read_text())
        lat = s.get("latency") or {}
        models.setdefault(model, {"id": model, "tiers": {}})["tiers"][tier] = {
            "accuracy": s["accuracy"], "n": s["n_planned"], "attempted": s["n_attempted"],
            "ece": (s.get("ece") or {}).get("ece"), "brier": s.get("brier_mean"),
            "p50_s": lat.get("p50_s"), "p95_s": lat.get("p95_s"),
            "schema_validity": s["schema_validity"], "ordinal_mae": s.get("ordinal_mae"),
            "families": {k: v["accuracy"] for k, v in s["per_family"].items()},
        }
    out = []
    for m in models.values():
        accs = [t["accuracy"] for t in m["tiers"].values()]
        m["mean_accuracy"] = sum(accs) / len(accs)
        m["complete"] = all(t["attempted"] == t["n"] for t in m["tiers"].values())
        out.append(m)
    return sorted(out, key=lambda m: -m["mean_accuracy"])


_status_cache = (0.0, None)


def _model_facts():
    return {m["id"]: m for m in json.loads((HERE / "models.json").read_text())["models"]}


def _listening_pids():
    """{port: pid} of local listeners, so a loaded model can be tied to its process."""
    try:
        out = subprocess.run(["ss", "-ltnpH"], capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    pids = {}
    for line in out.splitlines():
        m = re.search(r":(\d+)\s+\S+\s+users:\(\(\"[^\"]*\",pid=(\d+)", line)
        if m:
            pids[int(m.group(1))] = int(m.group(2))
    return pids


def _gpu_mb_by_pid():
    try:
        out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    return {int(a): int(b) for a, b in (ln.split(",") for ln in out.strip().splitlines() if "," in ln)}


def _rss_mb(pid):
    try:
        return int(re.search(r"VmRSS:\s+(\d+)", Path(f"/proc/{pid}/status").read_text()).group(1)) // 1024
    except (OSError, AttributeError):
        return None


def status():
    """What is actually loaded, checked live. Identity comes from the running server, not from our label, so a port serving
    something unexpected is flagged instead of trusted. Cached for two seconds."""
    global _status_cache
    if time.time() - _status_cache[0] < 2 and _status_cache[1] is not None:
        return _status_cache[1]
    facts, ports, gpu = _model_facts(), _listening_pids(), _gpu_mb_by_pid()

    def ping(item):
        name, cfg = item
        f = facts.get(name, {})
        base = {"code": f.get("code"), "name": f.get("name", name), "hosted": bool(cfg.get("hosted")), "params": f.get("params"), "library_only": bool(cfg.get("library_only"))}
        if cfg.get("hosted"):
            if not cfg["key"]:
                return name, {**base, "up": False, "reason": "No API key configured", "identity": None}
            return name, {**base, "up": True, "identity": "hosted API (api.typesafe.ai)", "identity_ok": True, "gpu_mb": 0}
        headers = {"Authorization": f"Bearer {cfg['key']}"} if cfg["key"] else {}
        for path in ((cfg["health"],) if cfg.get("health") else ("/v1/models", "/healthz")):
            try:
                with urllib.request.urlopen(urllib.request.Request(cfg["url"].rstrip("/") + path, headers=headers), timeout=2) as r:
                    body = json.load(r)
            except Exception:
                continue
            m = (body.get("models") or [{}])[0] if isinstance(body, dict) else {}
            if cfg.get("health") and isinstance(body, dict):  # BitMob's /health: its encoder and how many questions it has learned
                m = {"base": f"{body.get('encoder', '?')} + {body.get('library_size', '?')} learned questions (library only)"}
            said = " ".join(str(m.get(k, "")) for k in ("id", "base", "run")) or json.dumps(body)
            port = int(cfg["url"].rsplit(":", 1)[-1].strip("/")) if cfg["url"].rsplit(":", 1)[-1].strip("/").isdigit() else None
            pid = ports.get(port)
            return name, {**base, "up": True, "identity": m.get("base") or said.strip(), "identity_ok": f.get("verify", "").lower() in said.lower() if f.get("verify") else None,
                          "gpu_mb": gpu.get(pid, 0) if pid else None, "cpu_mb": _rss_mb(pid) if pid else None, "pid": pid}
        return name, {**base, "up": False, "reason": "Not loaded", "identity": None}

    with ThreadPoolExecutor(len(BACKENDS)) as ex:
        result = dict(ex.map(ping, BACKENDS.items()))
    _status_cache = (time.time(), result)
    return result


PAGES = {"/": "index.html", "/compare": "compare.html", "/scenarios": "scenarios.html", "/imagelab": "imagelab.html", "/personalab": "personalab.html", "/worldengine": "worldengine2.html", "/worldengine-how": "worldengine2-how.html", "/flow": "flow.html", "/flow-classic": "flow-classic.html", "/flow-lab": "flow-lab.html", "/flow-lab-final": "flow.html", "/models": "models.html", "/report": "report.html", "/latent": "latent.html"}
TYPES = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json",
         ".html": "text/html; charset=utf-8", ".md": "text/plain; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg", ".txt": "text/plain; charset=utf-8"}


WORLD_ENGINE = os.environ.get("WORLD_ENGINE_URL", "http://127.0.0.1:8112")  # probes/world-engine/world_service2.py (five-stage world engine, started by hand)


def world_engine_proxy(method, sub, body):
    if sub.split("?")[0] not in ("/state", "/request", "/drill", "/commit", "/reset", "/live", "/world", "/people_layout", "/people", "/gpu", "/graph", "/sowhat", "/reader"):
        return 404, {"error": "not found"}
    try:
        req = urllib.request.Request(WORLD_ENGINE + sub, body, {"Content-Type": "application/json"}, method=method)
        with urllib.request.urlopen(req, timeout=240) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        if e.code == 502:  # the engine's reader (any TypeSafe model) is not answering; say what to do instead of a bare 502
            r = reader_info()
            if r.get("auto"):
                return 503, {"error": "No local model is loaded to read stories with. Turn on Clef Flash Q4 (or Winnow) under Services; the reader is on Auto, so it starts using it by itself."}
            return 503, {"error": f"The World engine's reader ({backends.name(r.get('backend')) if r.get('backend') else r.get('url')}) is not answering, so it cannot read new stories. Set the Reader to Auto or pick a loaded model on this page, or turn it on under Services."}
        return e.code, e.read()
    except (urllib.error.URLError, OSError):
        return 503, {"error": "The World Engine is not running. ./service.sh up"}


def reader_info():
    """The World engine's current reader, named by its backend id when the address matches one we know."""
    try:
        with urllib.request.urlopen(WORLD_ENGINE + "/reader", timeout=5) as r: info = json.load(r)
    except Exception: return {}
    info["backend"] = info.get("current") if info.get("auto") else next((k for k, v in BACKENDS.items() if v["url"].rstrip("/") == info.get("url", "").rstrip("/")), None)
    return info


def set_reader(backend):
    """Point the World engine at another TypeSafe model; the address and key stay on this machine (the browser sends a name)."""
    if backend == "auto": body = json.dumps({"auto": True}).encode()
    elif backend not in BACKENDS: return 404, {"error": "unknown model"}
    elif BACKENDS[backend]["library_only"]: return 400, {"error": "BitMob answers only the questions it has learned, so it cannot read stories"}
    else: cfg = BACKENDS[backend]
    if backend == "auto":
        try:
            with urllib.request.urlopen(urllib.request.Request(WORLD_ENGINE + "/reader", body, {"Content-Type": "application/json"}), timeout=10) as r: r.read()
        except Exception as e: return 503, {"error": f"The World engine did not accept the reader: {e}"}
        return 200, reader_info()
    if cfg.get("hosted") and not cfg["key"]: return 400, {"error": "TYPESAFE_API_KEY is not set, so the hosted model cannot read"}
    body = json.dumps({"url": cfg["url"], "model": cfg["model"], "key": cfg["key"], "id": backend}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(WORLD_ENGINE + "/reader", body, {"Content-Type": "application/json"}), timeout=10) as r: r.read()
    except Exception as e: return 503, {"error": f"The World engine did not accept the reader: {e}"}
    return 200, reader_info()


MASK_FILE = HERE / "mask.json"                                   # code names (edit freely)
MASK_STATE = HERE.parent / "data" / "demo-mask.json"             # {"on": true|false}, set from the top bar


def mask_state():
    """Demo mode: whether names are masked, and every real -> code-name pair (longest real text first)."""
    try: on = bool(json.loads(MASK_STATE.read_text()).get("on"))
    except (OSError, ValueError): on = False
    out = {"on": on}
    if not on: return out
    m = json.loads(MASK_FILE.read_text()); facts = {x["id"]: x for x in json.loads((HERE / "models.json").read_text())["models"]}
    pairs = {}
    for mid, cn in m["models"].items():
        f = facts.get(mid, {})
        for real in (f.get("name"), mid): pairs[real] = cn["name"] if real == f.get("name") else cn["name"].lower().replace(" ", "-")
        if f.get("code"): pairs[f["code"]] = cn["code"]
    for real in m["encoders"]: pairs[real] = m.get("encoder_label", "Encoder")   # withheld: every encoder looks the same
    for real, fake in m["terms"].items(): pairs.setdefault(real, fake)
    ids = [[cn["name"].lower().replace(" ", "-"), mid] for mid, cn in m["models"].items()]   # encoders are withheld, so a URL cannot name one
    out.update(brand=m.get("brand"), pairs=sorted(([k, v] for k, v in pairs.items() if k), key=lambda kv: -len(kv[0])), ids=ids)  # ids: code name -> real id, for URLs
    return out


CPU_ENGINE = os.environ.get("CPU_ENGINE_URL", "http://127.0.0.1:8020")  # probes/cpu_engine.py: the local classifier (./service.sh start classifier)


def cpu_engine_proxy(method, sub, body):
    if sub.split("?")[0] not in ("/health", "/library", "/v1/systemone", "/embed"):
        return 404, {"error": "not found"}
    try:
        req = urllib.request.Request(CPU_ENGINE + sub, body, {"Content-Type": "application/json"}, method=method)
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, OSError):
        return 503, {"error": "The local classifier is off. Turn it on with the Classifier switch in the top bar, or ./service.sh start classifier"}


VOICE = os.environ.get("VOICE_ADDR", "127.0.0.1:8200")  # voice/server.py; the browser reaches it only through /voice/* here

# On-demand services the top bar can switch: every service tagged `demand` in /workspace/service.yaml (its port, health path
# and `panel` note), named by the model registry when it serves a registered model (matched by port), else by its `label`.
# Switching runs ./service.sh in its own session, so a console restart does not stop what it started.
def switches():
    import yaml  # PyYAML, already needed by tools/service.py, which the switches run
    svcs = (yaml.safe_load((HERE.parent / "service.yaml").read_text()) or {}).get("services", {})
    names = {urllib.parse.urlsplit(b["url"]).port: m["name"] for m in registry.models() if not m["retired"]
             for b in [backends.BACKENDS.get(m["id"])] if b and not b["hosted"]}
    return {n: {"label": names.get(sv.get("port")) or sv.get("label") or n, "port": sv.get("port"), "health": sv.get("health", "/"),
                "gpu": sv.get("panel", "")} for n, sv in svcs.items() if "demand" in (sv.get("tags") or [])}


_switching = {}  # name -> (action, Popen)


def _answers(port, path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=1.5) as r: return r.status < 500
    except urllib.error.HTTPError as e: return e.code < 500
    except Exception: return False


def services_state():
    out = []
    for name, sw in switches().items():
        job = _switching.get(name); busy = job and job[1].poll() is None
        out.append({"name": name, "label": sw["label"], "gpu": sw["gpu"], "up": _answers(sw["port"], sw["health"]), "busy": job[0] if busy else None})
    return out


def switch_service(name, action):
    sws = switches()
    if name not in sws or action not in ("start", "stop"): return 404, {"error": "unknown service or action"}
    job = _switching.get(name)
    if job and job[1].poll() is None: return 409, {"error": f"{sws[name]['label']} is already {job[0]}ing"}
    root = HERE.parent; log = open(root / "logs" / "service-switch.log", "ab")
    log.write(f"\n== {time.strftime('%F %T')} {action} {name} (console switch)\n".encode()); log.flush()
    p = subprocess.Popen(["python3", str(root / "tools" / "service.py"), action, name, "-y"], cwd=str(root), stdin=subprocess.DEVNULL,
                         stdout=log, stderr=log, start_new_session=True)
    _switching[name] = (action, p)
    return 202, {"name": name, "action": action}


class Handler(BaseHTTPRequestHandler):
    def _local(self):
        """Only someone on this machine (or a port forward to it) may switch services; never a visitor through a tunnel."""
        h = {k.lower() for k in self.headers.keys()}
        return self.client_address[0] in ("127.0.0.1", "::1") and not (h & {"cf-connecting-ip", "cf-ray", "x-forwarded-for", "forwarded"})

    def _voice_ws(self):
        """Relay a WebSocket to the voice service: hand the upgrade request on, then copy bytes both ways until either side closes."""
        host, port = VOICE.rsplit(":", 1)
        try: up = socket.create_connection((host, int(port)), timeout=5)
        except OSError: return self._send(503, {"error": "Voice is off. Turn it on with the Voice switch in the top bar, or ./service.sh start voice"})
        up.settimeout(None)
        head = ["GET /ws HTTP/1.1", f"Host: {VOICE}"] + [f"{k}: {v}" for k, v in self.headers.items() if k.lower() != "host"]
        up.sendall(("\r\n".join(head) + "\r\n\r\n").encode())
        client = self.connection

        def pump(src, dst):
            try:
                while (b := src.recv(65536)): dst.sendall(b)
            except OSError: pass
            for x in (src, dst):
                try: x.shutdown(socket.SHUT_RDWR)
                except OSError: pass
        t = threading.Thread(target=pump, args=(up, client), daemon=True); t.start()
        pump(client, up); t.join(5); up.close(); self.close_connection = True


    def _send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        zipped = len(raw) > 2048 and "gzip" in self.headers.get("Accept-Encoding", "") and ctype.split(";")[0] in (
            "application/json", "text/html", "text/javascript", "text/css", "text/plain", "image/svg+xml")
        if zipped: raw = body.gz() if isinstance(body, _Memo) else gzip.compress(raw, 5)   # JSON shrinks to about a tenth
        self.send_response(code)
        if zipped: self.send_header("Content-Encoding", "gzip"); self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _api(self, fn, *a, checked=False):
        rid = self.headers.get("X-Request-Id") or outside_api.secrets.token_hex(8)
        bad = None if checked else outside_api.auth(self)
        status, body = bad if bad else fn(*a)
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("X-Request-Id", rid)
        self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        if path == "/v1/models": return self._api(outside_api.get_models)
        if path == "/voice/ws" and self.headers.get("Upgrade", "").lower() == "websocket":
            return self._voice_ws()
        if path == "/voice/api/status":
            try:
                with urllib.request.urlopen(f"http://{VOICE}/api/status", timeout=5) as r: return self._send(r.status, r.read())
            except Exception: return self._send(503, {"error": "Voice is off"})
        if path == "/api/mask":
            return self._send(200, {**mask_state(), "can_switch": self._local()})
        if path == "/api/services":
            return self._send(200, {"services": services_state(), "can_switch": self._local()})
        if path == "/mockups" or path.startswith("/mockups/"):  # the static mock-ups (they had their own server on :8110)
            f = (HERE / path.lstrip("/")).resolve()
            if f.is_dir(): f = f / "index.html"
            if f.is_file() and (HERE / "mockups") in f.parents:
                return self._send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))
            return self._send(404, {"error": "not found"})
        if path.startswith("/audio/"):
            return audio_library.serve(self, path[len("/audio/"):])
        if path.startswith("/imagelab-img/"):
            return imagelab_api.serve_image(self, path[len("/imagelab-img/"):])
        if path == "/api/imagelab":
            return self._send(200, memo("imagelab", imagelab_api.payload))
        if path.startswith("/api/persona-lab/"):
            r = persona_api.handle_get(path, self.path.partition("?")[2])
            return self._send(*r)
        moved = {"/personalab": "/worldengine", "/worldlab": "/worldengine", "/worldengine2": "/worldengine", "/worldengine2-how": "/worldengine-how"}
        if path in moved:  # older pages folded into the world engine; v2 is now the only world engine
            q = self.path.partition("?")[2]
            self.send_response(302)
            self.send_header("Location", moved[path] + ("?" + q if q else ""))
            self.end_headers()
            return
        if path == "/api/world-engine/reader":
            return self._send(200, reader_info())
        if path.startswith("/api/world-engine/"):
            return self._send(*world_engine_proxy("GET", self.path[len("/api/world-engine"):], None))      # self.path keeps the query string (?since=N)
        if path.startswith("/api/cpu/"):
            return self._send(*cpu_engine_proxy("GET", path[len("/api/cpu"):], None))
        if path.startswith("/api/idea"):
            r = idea_api.handle_get(path, self.path.partition("?")[2])
            return self._send(*r) if r else self._send(404, {"error": "not found"})
        if path == "/api/audio-files":
            return self._send(200, audio_library.list_files())
        if path.startswith("/api/detector-"):
            r = detector_api.handle_get(path, self.path.partition("?")[2])
            return self._send(*r) if r else self._send(404, {"error": "not found"})
        if path in PAGES and (HERE / PAGES[path]).exists():
            self._send(200, (HERE / PAGES[path]).read_bytes(), "text/html; charset=utf-8")
        elif path.startswith("/static/"):
            f = (HERE / path.lstrip("/")).resolve()
            if f.is_file() and HERE / "static" in f.parents:
                self._send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))
            else:
                self._send(404, {"error": "not found"})
        elif path == "/api/leaderboard":
            self._send(200, memo("leaderboard", leaderboard))
        elif path == "/api/models":   # the one model registry (demo/registry.py): every page's list of models
            self._send(200, registry.payload())
        elif path == "/api/status":
            self._send(200, status())
        elif path == "/api/probes":
            self._send(200, memo("probes", probe_sets))
        elif path == "/api/probe":
            q = self.path.partition("?")[2]
            try:
                self._send(200, probe_detail(dict(x.split("=", 1) for x in q.split("&") if "=" in x).get("set", "")))
            except KeyError:
                self._send(404, {"error": "unknown set"})
        elif path.startswith("/api/probe/"):
            # Path form (rather than ?set=) so the same relative URL works unmodified as a static
            # file too -- a static host can't route a query string, but a literal path it can.
            set_id = path[len("/api/probe/"):]
            if set_id.endswith(".json"):
                set_id = set_id[: -len(".json")]
            try:
                self._send(200, memo("probe:" + set_id, lambda: probe_detail(set_id)))
            except KeyError:
                self._send(404, {"error": "unknown set"})
        elif path == "/api/vram":
            self._send(200, vram())
        elif path == "/api/latent/teacher":  # the classifier's teacher: trains new questions, and backs up / compares answers
            t = backends.teacher(); self._send(200, {"teacher": {"id": t, "name": backends.name(t), "hosted": BACKENDS[t]["hosted"]}, "can_switch": self._local()})
        elif path == "/api/latent/intake":  # Latent lab intake: measured local-vs-Clef verdict per question
            self._send(*intake_api.handle_get(self.path.partition("?")[2]))
        elif path == "/api/latent":  # Latent lab: probes/latent_export.py per model; ?model=<tag>&set=<id> for one set, else models + sweep
            q = dict(urllib.parse.parse_qsl(self.path.partition("?")[2]))
            base = ROOT / "data" / "embed-zs"
            models = sorted(d.name for d in (base / "latent").glob("*/") if (d / "index.json").is_file())
            model = q.get("model") or ("Qwen3-Embedding-4B" if "Qwen3-Embedding-4B" in models else (models[0] if models else ""))
            ok = lambda x: x.replace("_", "").replace("-", "").replace(".", "").isalnum()
            if "set" not in q:
                sweep = [json.loads(f.read_text()) for f in sorted((base / "sweep").glob("*.json"))]
                curve = [json.loads(f.read_text()) for f in sorted((base / "curve").glob("*.json"))]
                idx = base / "latent" / model / "index.json"
                if not models or not idx.is_file():
                    return self._send(404, {"error": "No latent export yet. Run probes/latent_export.py."})
                return self._send(200, {"models": models, "model": model, "index": json.loads(idx.read_text()), "sweep": sweep, "curve": curve,
                                        "verdicts": json.loads((base / "verdicts.json").read_text()) if (base / "verdicts.json").is_file() else None})
            f = base / "latent" / model / f"{q['set']}.json"
            if not (ok(model) and ok(q["set"])) or model not in models or not f.is_file():
                return self._send(404, {"error": "No latent export for that model and set."})
            self._send(200, f.read_bytes(), "application/json")
        elif path == "/api/batch-perf":
            self._send(200, batch_perf())
        elif path == "/api/decompose-tree":
            self._send(200, decompose_tree())
        elif path == "/api/monte-carlo":
            self._send(200, monte_carlo_schedule())
        elif path == "/api/decompose-library":
            if lcd is None:
                self._send(503, {"error": f"PyYAML missing or library failed to load: {_LCD_ERROR}"})
            else:
                self._send(200, lcd.skeleton(lcd.load_library()))
        elif path == "/api/decompose-examples":
            self._send(200, decompose_examples())
        elif path == "/api/probe-macro":
            self._send(200, memo("probe-macro", probe_macro))
        elif path == "/api/agreement":
            self._send(200, memo("agreement", probe_agreement))
        elif path == "/api/scenes":
            self._send(200, scenes())
        elif path == "/api/dialogues":
            f = PROBES / "manipulation_windows.json"
            self._send(200, json.loads(f.read_text()) if f.is_file() else {"dialogues": []})
        elif path == "/api/window-study":
            self._send(200, window_study())
        elif path == "/api/hierarchy":
            self._send(200, hierarchy_study())
        elif path == "/api/time-study":
            self._send(200, time_study())
        elif path == "/api/speeches":
            self._send(200, speeches())
        elif path == "/api/results":
            self._send(200, results())
        elif path == "/api/backends":
            self._send(200, {n: {"url": c["url"], "has_key": bool(c["key"]) or not n.startswith("jev")} for n, c in BACKENDS.items()})
        else:
            self._send(404, {"error": "not found"})

    def _stream(self, events):
        """HTTP/1.0-style streaming response: no Content-Length, connection closed at the end, so
        fetch() on the client can read it as it arrives. A client disconnect (Stop, or navigating
        away) raises BrokenPipeError/ConnectionResetError on the next write, which is caught here;
        events.close() then raises GeneratorExit inside lcd.walk(), which makes no further model
        calls (see lab_custom_decompose.py's walk() docstring and its GeneratorExit test)."""
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.close_connection = True
        try:
            for ev in events:
                self.wfile.write((json.dumps(ev) + "\n").encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            events.close()
            _decompose_lock.release()

    def _handle_decompose_live(self):
        if lcd is None:
            return self._send(503, {"error": f"PyYAML missing or library failed to load: {_LCD_ERROR}"})
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            text, who, models, budget = req.get("text", ""), req.get("who") or "", req.get("models"), req.get("budget")
            assert isinstance(text, str) and 0 < len(text) <= lcd.MAX_TEXT
            assert isinstance(who, str) and len(who) <= lcd.MAX_WHO
            assert isinstance(budget, int) and 3 <= budget <= 113
            assert isinstance(models, list) and 1 <= len(models) <= 5 and all(isinstance(m, str) for m in models)
        except (ValueError, KeyError, AssertionError, TypeError):
            return self._send(400, {"error": "need JSON {text, who?, models:[...], budget:3-113}"})
        for m in models:
            if m not in BACKENDS:
                return self._send(404, {"error": f"unknown backend {m}"})
        up = {n: v.get("up") for n, v in status().items()}
        not_loaded = [m for m in models if not up.get(m)]
        if not_loaded:
            return self._send(409, {"error": f"not loaded: {', '.join(not_loaded)}"})
        if not _decompose_lock.acquire(blocking=False):
            return self._send(409, {"error": "another decomposition is running; try again when it finishes"})
        try:
            events = lcd.walk(text, who, models, budget, lambda m, item: one_item(m, BACKENDS[m], item))
        except Exception as e:
            _decompose_lock.release()
            return self._send(500, {"error": str(e)})
        self._stream(events)

    def do_POST(self):
        if self.path.split("?")[0] in ("/v1/systemone", "/v1/audio/transcriptions"):
            bad = outside_api.auth(self)                       # before reading the body: a refused caller cannot make us read 100 MB
            if bad: self.close_connection = True; return self._api(lambda: bad, checked=True)
            n = int(self.headers.get("Content-Length", 0))
            if n > outside_api.MAX_AUDIO: return self._send(413, {"error": "request too large"})
            raw = self.rfile.read(n)
            if self.path.split("?")[0] == "/v1/systemone": return self._api(outside_api.systemone, raw, checked=True)
            return self._api(outside_api.transcriptions, raw, self.headers.get("Content-Type", ""), checked=True)
        if self.path.split("?")[0] == "/api/mask":  # demo mode on/off: only from this machine; everyone (shared-link visitors too) sees the result
            if not self._local(): return self._send(403, {"error": "Secure mode can only be changed from this machine."})
            try: on = bool(json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 200)))["on"])
            except (ValueError, KeyError): return self._send(400, {"error": "send {\"on\": true|false}"})
            MASK_STATE.parent.mkdir(parents=True, exist_ok=True); MASK_STATE.write_text(json.dumps({"on": on}))
            return self._send(200, {"on": on})
        if self.path.startswith("/api/services/"):
            if not self._local(): return self._send(403, {"error": "Services can only be switched from this machine, not through a shared link."})
            parts = self.path.split("?")[0].strip("/").split("/")  # api/services/<name>/<action>
            return self._send(*switch_service(parts[2], parts[3])) if len(parts) == 4 else self._send(404, {"error": "not found"})
        if self.path.startswith("/api/detector-"):
            r = detector_api.handle_post(self.path.split("?")[0], self.rfile.read(min(int(self.headers.get("Content-Length", 0)), detector_api.MAX_BODY + 1)))
            return self._send(*r) if r else self._send(404, {"error": "not found"})
        if self.path.split("?")[0] == "/api/world-engine/reader":  # a config change that can spend money (hosted Jev): local visitors only
            if not self._local(): return self._send(403, {"error": "The reader can only be changed from this machine, not through a shared link."})
            try: backend = str(json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 2000)))["backend"])
            except (ValueError, KeyError): return self._send(400, {"error": "send {\"backend\": \"<model id>\"}"})
            return self._send(*set_reader(backend))
        if self.path.startswith("/api/world-engine/"):
            return self._send(*world_engine_proxy("POST", self.path.split("?")[0][len("/api/world-engine"):], self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 20000))))
        if self.path.startswith("/api/cpu/"):
            return self._send(*cpu_engine_proxy("POST", self.path[len("/api/cpu"):], self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 200000))))
        if self.path.startswith("/api/persona-lab/"):
            return self._send(*persona_api.handle_post(self.path.split("?")[0], self.rfile.read(min(int(self.headers.get("Content-Length", 0)), persona_api.MAX_BODY + 1))))
        if self.path.split("?")[0] == "/api/latent/teacher":  # a setting that can spend money (a hosted teacher): local visitors only
            if not self._local(): return self._send(403, {"error": "The teacher can only be changed from this machine, not through a shared link."})
            try: bid = str(json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 2000)))["backend"])
            except (ValueError, KeyError): return self._send(400, {"error": "send {\"backend\": \"<model id>\"}"})
            if bid not in BACKENDS: return self._send(404, {"error": "unknown model"})
            if BACKENDS[bid]["library_only"]: return self._send(400, {"error": "BitMob learns from a teacher; it cannot be one"})
            if BACKENDS[bid]["hosted"] and not BACKENDS[bid]["key"]: return self._send(400, {"error": "TYPESAFE_API_KEY is not set, so the hosted model cannot teach"})
            backends.set_teacher(bid); return self._send(200, {"teacher": {"id": bid, "name": backends.name(bid), "hosted": BACKENDS[bid]["hosted"]}})
        if self.path.split("?")[0] == "/api/latent/intake":
            raw = self.rfile.read(min(int(self.headers.get("Content-Length", 0)), intake_api.MAX_BODY + 1))
            if not self._local() and "cancel=1" not in self.path:  # a run through a shared link must not spend money or pick its own teacher
                try: asked = (json.loads(raw or b"{}") or {}).get("teacher")
                except ValueError: asked = None
                if asked or BACKENDS[backends.teacher()]["hosted"]:
                    return self._send(403, {"error": "Through a shared link, questions can only be trained with the local teacher already chosen on this machine."})
            return self._send(*intake_api.handle_post(raw, self.path.partition("?")[2]))
        if self.path == "/api/decompose-live":
            return self._handle_decompose_live()
        if self.path == "/api/batch":
            try:
                req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                backend, items = req["backend"], req["items"]
                assert isinstance(items, list) and all(isinstance(i, dict) and "state" in i and isinstance(i.get("questions"), dict) for i in items)
            except (ValueError, KeyError, AssertionError):
                return self._send(400, {"error": "need JSON {backend, items:[{state, questions:{id: question}}]}"})
            if len(items) > MAX_BATCH_ITEMS:
                return self._send(413, {"error": f"at most {MAX_BATCH_ITEMS} items per batch"})
            try:
                return self._send(200, batch(backend, items))
            except KeyError:
                return self._send(404, {"error": f"unknown backend {backend}"})
        if self.path != "/api/compare":
            return self._send(404, {"error": "not found"})
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            qs = req.get("questions")
            if qs is not None:  # a battery: many questions about one state, answered together in one call per model
                assert isinstance(qs, dict) and 0 < len(qs) <= 20 and all(isinstance(v, dict) and v.get("type") in ("choice", "score", "noul") for v in qs.values())
                body, whole = {"state": req["state"], "questions": qs}, True
            else:
                body, whole = {"state": req["state"], "questions": {"decision": req["question"]}}, False
        except (ValueError, KeyError, AssertionError, TypeError):
            return self._send(400, {"error": "need JSON {state, question} or {state, questions:{id: question}}"})
        up = {n: v.get("up") for n, v in status().items()}
        with ThreadPoolExecutor(len(BACKENDS)) as ex:   # every model, BitMob included (it says so when a question is not in its library)
            futs = [ex.submit(call, n, c, body, whole) if up.get(n) else None for n, c in BACKENDS.items()]
            self._send(200, [f.result() if f else {"backend": n, "error": "Not loaded"} for f, n in zip(futs, BACKENDS)])

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    host, port = os.environ.get("DEMO_HOST", "127.0.0.1"), int(os.environ.get("DEMO_PORT", "8100"))
    print(f"demo on http://{host}:{port}  (typesafe key: {'set' if BACKENDS['jev']['key'] else 'MISSING'})")
    threading.Thread(target=warm_memo, daemon=True).start()
    class Server(ThreadingHTTPServer):
        # The standard queue holds 5 waiting connections; a page that opens 20+ requests at once (Scenario lab) then has
        # the rest dropped, and the browser retries after 1 s, 3 s... which was the "sometimes it takes seconds" delay.
        request_queue_size = 128
        daemon_threads = True
    Server((host, port), Handler).serve_forever()
