"""Local demo: benchmark results viewer + live side-by-side compare of jeff, kev and hosted Jev.

    TYPESAFE_API_KEY=... python3 demo/server.py      # then open http://127.0.0.1:8100

The TypeSafe key stays server-side. Binds to 127.0.0.1 by default; set DEMO_HOST to expose it
(anyone who can reach the port can spend the key).
"""
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
BENCH = Path(os.environ.get("BENCH_DIR", HERE.parent / "data" / "bench"))
BACKENDS = {  # keyed by the same model ids as the leaderboard, best first; codes and names live in models.json
    "jev": {"url": os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai"), "key": os.environ.get("TYPESAFE_API_KEY", ""), "hosted": True},
    "semif": {"url": os.environ.get("SEMIF_URL", "http://127.0.0.1:8012"), "key": ""},
    "kev-4b": {"url": os.environ.get("KEV4_URL", "http://127.0.0.1:8010"), "key": ""},
    "so1": {"url": os.environ.get("SO1_URL", "http://127.0.0.1:8013"), "key": ""},
    "laya": {"url": os.environ.get("LAYA_URL", "http://127.0.0.1:8014"), "key": ""},
    "kev-0.8b": {"url": os.environ.get("KEV08_URL", "http://127.0.0.1:8011"), "key": ""},
    "jeff": {"url": os.environ.get("JEFF_URL", "http://127.0.0.1:8000"), "key": os.environ.get("JEFF_API_KEYS", "devkey").split(",")[0]},
    "kev-0.5b": {"url": os.environ.get("KEV05_URL", "http://127.0.0.1:8009"), "key": ""},
    "verdict": {"url": os.environ.get("VERDICT_URL", "http://127.0.0.1:8015"), "key": ""},
}


def call(name, cfg, body, whole=False):
    if name.startswith("jev") and not cfg["key"]:
        return {"backend": name, "error": "TYPESAFE_API_KEY not set"}
    headers = {"Content-Type": "application/json", "User-Agent": "jev-demo/0.1"}
    if cfg["key"]:
        headers["Authorization"] = f"Bearer {cfg['key']}"
    req = urllib.request.Request(cfg["url"].rstrip("/") + "/v1/systemone", json.dumps(body).encode(), headers)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data, status, resp_headers = json.load(r), r.status, dict(r.headers.items())
    except urllib.error.HTTPError as e:
        return {"backend": name, "error": f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"}
    except Exception as e:  # connection refused, timeout, bad JSON
        return {"backend": name, "error": f"{type(e).__name__}: {e}"}
    if whole:
        return {"backend": name, "status": status, "latency_ms": round((time.perf_counter() - t0) * 1000), "model": data.get("model"),
                "answers": data.get("answers") or {}, "extras": extras(data, {}, resp_headers)}
    answer = (data.get("answers") or {}).get("decision") or {}
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
    r = call(name, cfg, {"state": item["state"], "model": "jev-latest", "questions": item["questions"]}, whole=True)
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
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


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
        base = {"code": f.get("code"), "name": f.get("name", name), "hosted": bool(cfg.get("hosted")), "params": f.get("params")}
        if cfg.get("hosted"):
            if not cfg["key"]:
                return name, {**base, "up": False, "reason": "No API key configured", "identity": None}
            return name, {**base, "up": True, "identity": "hosted API (api.typesafe.ai)", "identity_ok": True, "gpu_mb": 0}
        headers = {"Authorization": f"Bearer {cfg['key']}"} if cfg["key"] else {}
        for path in ("/v1/models", "/healthz"):
            try:
                with urllib.request.urlopen(urllib.request.Request(cfg["url"].rstrip("/") + path, headers=headers), timeout=2) as r:
                    body = json.load(r)
            except Exception:
                continue
            m = (body.get("models") or [{}])[0] if isinstance(body, dict) else {}
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


PAGES = {"/": "index.html", "/compare": "compare.html", "/scenarios": "scenarios.html", "/flow": "flow.html", "/models": "models.html", "/report": "report.html"}
TYPES = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json"}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        if path in PAGES and (HERE / PAGES[path]).exists():
            self._send(200, (HERE / PAGES[path]).read_bytes(), "text/html; charset=utf-8")
        elif path.startswith("/static/"):
            f = (HERE / path.lstrip("/")).resolve()
            if f.is_file() and HERE / "static" in f.parents:
                self._send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))
            else:
                self._send(404, {"error": "not found"})
        elif path == "/api/leaderboard":
            self._send(200, leaderboard())
        elif path == "/api/models":
            self._send(200, json.loads((HERE / "models.json").read_text()))
        elif path == "/api/status":
            self._send(200, status())
        elif path == "/api/probes":
            self._send(200, probe_sets())
        elif path == "/api/probe":
            q = self.path.partition("?")[2]
            try:
                self._send(200, probe_detail(dict(x.split("=", 1) for x in q.split("&") if "=" in x).get("set", "")))
            except KeyError:
                self._send(404, {"error": "unknown set"})
        elif path == "/api/vram":
            self._send(200, vram())
        elif path == "/api/batch-perf":
            self._send(200, batch_perf())
        elif path == "/api/decompose-tree":
            self._send(200, decompose_tree())
        elif path == "/api/probe-macro":
            self._send(200, probe_macro())
        elif path == "/api/agreement":
            self._send(200, probe_agreement())
        elif path == "/api/scenes":
            self._send(200, scenes())
        elif path == "/api/dialogues":
            f = PROBES / "manipulation_windows.json"
            self._send(200, json.loads(f.read_text()) if f.is_file() else {"dialogues": []})
        elif path == "/api/window-study":
            self._send(200, window_study())
        elif path == "/api/speeches":
            self._send(200, speeches())
        elif path == "/api/results":
            self._send(200, results())
        elif path == "/api/backends":
            self._send(200, {n: {"url": c["url"], "has_key": bool(c["key"]) or not n.startswith("jev")} for n, c in BACKENDS.items()})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
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
            body = {"state": req["state"], "model": "jev-latest", "questions": {"decision": req["question"]}}
        except (ValueError, KeyError):
            return self._send(400, {"error": "need JSON {state, question}"})
        up = {n: v.get("up") for n, v in status().items()}
        with ThreadPoolExecutor(len(BACKENDS)) as ex:
            futs = [ex.submit(call, n, c, body) if up.get(n) else None for n, c in BACKENDS.items()]
            self._send(200, [f.result() if f else {"backend": n, "error": "Not loaded"} for f, n in zip(futs, BACKENDS)])

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    host, port = os.environ.get("DEMO_HOST", "127.0.0.1"), int(os.environ.get("DEMO_PORT", "8100"))
    print(f"demo on http://{host}:{port}  (typesafe key: {'set' if BACKENDS['jev']['key'] else 'MISSING'})")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
