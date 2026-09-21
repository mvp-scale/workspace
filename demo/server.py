"""Local demo: benchmark results viewer + live side-by-side compare of jeff, kev and hosted Jev.

    TYPESAFE_API_KEY=... python3 demo/server.py      # then open http://127.0.0.1:8100

The TypeSafe key stays server-side. Binds to 127.0.0.1 by default; set DEMO_HOST to expose it
(anyone who can reach the port can spend the key).
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
BENCH = Path(os.environ.get("BENCH_DIR", HERE.parent / "data" / "bench"))
BACKENDS = {
    "jeff": {"url": os.environ.get("JEFF_URL", "http://127.0.0.1:8000"), "key": os.environ.get("JEFF_API_KEYS", "devkey").split(",")[0]},
    "kev-0.5b": {"url": os.environ.get("KEV05_URL", "http://127.0.0.1:8009"), "key": ""},
    "kev-0.8b": {"url": os.environ.get("KEV08_URL", "http://127.0.0.1:8011"), "key": ""},
    "kev-4b": {"url": os.environ.get("KEV4_URL", "http://127.0.0.1:8010"), "key": ""},
    "jev (typesafe)": {"url": os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai"), "key": os.environ.get("TYPESAFE_API_KEY", "")},
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


def status():
    """Reachability of each compare backend, checked in parallel with a short timeout."""
    def ping(item):
        name, cfg = item
        if name.startswith("jev") and not cfg["key"]:
            return name, {"up": False, "reason": "No API key configured"}
        headers = {"Authorization": f"Bearer {cfg['key']}"} if cfg["key"] else {}
        for path in ("/healthz", "/v1/models"):
            try:
                with urllib.request.urlopen(urllib.request.Request(cfg["url"].rstrip("/") + path, headers=headers), timeout=2):
                    return name, {"up": True}
            except urllib.error.HTTPError as e:
                if e.code < 500 and e.code != 404 and e.code != 401:
                    return name, {"up": True}
            except Exception as e:
                reason = type(e).__name__
        return name, {"up": False, "reason": "Not reachable"}
    with ThreadPoolExecutor(len(BACKENDS)) as ex:
        return dict(ex.map(ping, BACKENDS.items()))


PAGES = {"/": "index.html", "/compare": "compare.html", "/scenarios": "scenarios.html", "/windows": "windows.html", "/models": "models.html", "/report": "report.html"}
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
        with ThreadPoolExecutor(len(BACKENDS)) as ex:
            futs = [ex.submit(call, n, c, body) for n, c in BACKENDS.items()]
            self._send(200, [f.result() for f in futs])

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    host, port = os.environ.get("DEMO_HOST", "127.0.0.1"), int(os.environ.get("DEMO_PORT", "8100"))
    print(f"demo on http://{host}:{port}  (typesafe key: {'set' if BACKENDS['jev (typesafe)']['key'] else 'MISSING'})")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
