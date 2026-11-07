#!/usr/bin/env python3
"""Pulse reader: serves the registered CPU engine (ExpertS, artefact name from PULSE_READER_ARTEFACT, default v6b-student) as POST /v1/pulse.
Thin glue only: the answer is ExpertS.read(text) unchanged (story type, topic top 2, condition present, and the condition fields when present).
CPU only (GPU hidden), one ONNX thread, no network, no hosted calls. Artefact: knowledge_pipeline/projects/world-state/runs/expert1/ (ledger L771, L774).
    POST /v1/pulse    {"text": "Headline. Description."}  or  {"items": [{"id": "..", "text": ".."}, ...]}   ->  {"engine", "ms", "result"} / {"engine", "results": [{"id", "ms", "result"}]}
Kind heads (T35 follow-up, spec ledger L890 to L898): "conditions" lists {kind, p, present} for air_pollution, biodiversity_loss, civil_unrest and cyber_insecurity (one logistic head each on the v6b-student embedding the reader
already computes; weights runs/expert1/pulse_kind_heads_v1.npz, sha256 checked at start). When biodiversity_loss is present its entry also carries "direction" {answer: down|up, p_down}. No size, no direction for the other kinds.
The old union "condition_present" stays and is marked status "parked" (the reader's own answered/unknown moves to "reader_status"); the legacy "condition" block carries parked: true. Heads agree with Sonnet labels only (two Claude labellers, no outside truth set).
    GET  /health      engine, artefact, device, memory, request count and latency of the last requests
    ./service.sh start pulse-reader      (127.0.0.1:8023)
"""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""  # CPU only, whatever the caller set
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
import hashlib, json, resource, sys, threading, time
import numpy as np
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "knowledge_pipeline" / "projects" / "world-state"
PORT = int(os.environ.get("PULSE_READER_PORT", "8023"))
ENGINE = os.environ.get("PULSE_READER_ENGINE", "v6b-student")
LOCK = threading.Lock()  # one read at a time: the latency we quote is for one request on one thread
MAX_ITEMS = 200; MAX_CHARS = 20000
os.chdir(WS)  # the artefact names its encoder files relative to this folder
sys.path.insert(0, str(WS))
from expert1_runtime import ExpertS
VERSIONS = {v["version"]: v for v in json.load(open("engine_versions.json"))}
if ENGINE not in VERSIONS: raise SystemExit(f"unknown engine version {ENGINE}; known: {sorted(VERSIONS)}")
if VERSIONS[ENGINE]["class"] != "ExpertS": raise SystemExit(f"{ENGINE} is class {VERSIONS[ENGINE]['class']}; this service serves ExpertS artefacts")
ARTEFACT = VERSIONS[ENGINE]["path"]
READER = ExpertS(ARTEFACT); READER.read("Warm up. The service loads the encoder and the heads before the first request arrives, so the first call is not slow.")
HEADS_META = json.load(open("runs/expert1/pulse_kind_heads_v1.json"))
if hashlib.sha256(open("runs/expert1/" + HEADS_META["npz"], "rb").read()).hexdigest() != HEADS_META["sha256"]: raise SystemExit("kind heads file does not match its recorded sha256")
HZ = np.load("runs/expert1/" + HEADS_META["npz"]); KINDS = [str(k) for k in HZ["kinds"]]; DIR_KIND = str(HZ["dir_kind"])
_embed = READER.student; _last = [None, None]
def _cached(text):  # one ONNX pass per request: read() and the kind heads share the embedding
    if _last[0] != text: _last[0], _last[1] = text, _embed(text)
    return _last[1]
READER.student = _cached
sig = lambda z: float(1 / (1 + np.exp(-z)))
def kind_heads(text):
    v = _cached(text).astype(np.float32); out = []
    for k, w, b, t in zip(KINDS, HZ["W"], HZ["b"], HZ["thr"]):
        p = sig(float(v @ w + b)); e = {"kind": k, "p": round(p, 4), "present": bool(p >= float(t))}
        if k == DIR_KIND and e["present"]: pd = sig(float(v @ HZ["dir_W"] + HZ["dir_b"])); e["direction"] = {"answer": "down" if pd >= 0.5 else "up", "p_down": round(pd, 4)}
        out.append(e)
    return out
RECENT = []; COUNT = [0]

def read(text):
    t0 = time.perf_counter()
    with LOCK:
        r = READER.read(text)
        if r.get("story_type", {}).get("reason"): r["conditions_status"] = "skipped: " + r["story_type"]["reason"]
        else: r["conditions"] = kind_heads(text)
        cp = r.get("condition_present")
        if cp is not None: cp["reader_status"] = cp.get("status"); cp["status"] = "parked"
        if "condition" in r: r["condition"]["parked"] = True
    ms = (time.perf_counter() - t0) * 1000; RECENT.append(ms); del RECENT[:-200]; COUNT[0] += 1
    return r, round(ms, 2)

class H(BaseHTTPRequestHandler):
    def _send(self, code, body):
        b = json.dumps(body).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.split("?")[0] not in ("/health", "/healthz"): return self._send(404, {"error": "not found"})
        s = sorted(RECENT); q = lambda p: round(s[min(len(s) - 1, int(p * len(s)))], 2) if s else None
        self._send(200, {"status": "ok", "engine": ENGINE, "encoder": f"{ENGINE} leaf student", "library_size": 5, "kind_heads": HEADS_META["name"], "artefact": ARTEFACT, "device": "cpu", "threads": 1, "requests": COUNT[0],
                         "ms_median": q(0.5), "ms_p95": q(0.95), "rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)})
    def do_POST(self):
        if self.path.split("?")[0] != "/v1/pulse": return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0)); body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e: return self._send(400, {"error": f"bad JSON: {e}"})
        if isinstance(body.get("text"), str):
            if len(body["text"]) > MAX_CHARS: return self._send(413, {"error": f"text over {MAX_CHARS} characters"})
            r, ms = read(body["text"]); return self._send(200, {"engine": ENGINE, "ms": ms, "result": r})
        items = body.get("items")
        if isinstance(items, list) and items and len(items) <= MAX_ITEMS and all(isinstance(x, dict) and isinstance(x.get("text"), str) for x in items):
            if any(len(x["text"]) > MAX_CHARS for x in items): return self._send(413, {"error": f"text over {MAX_CHARS} characters"})
            out = []
            for x in items:
                r, ms = read(x["text"]); out.append({"id": x.get("id"), "ms": ms, "result": r})
            return self._send(200, {"engine": ENGINE, "results": out})
        self._send(400, {"error": f'send {{"text": "..."}} or {{"items": [{{"id": "..", "text": ".."}}]}} with 1 to {MAX_ITEMS} items'})

if __name__ == "__main__":
    print(f"pulse reader: {ENGINE} ({ARTEFACT}) on 127.0.0.1:{PORT}, CPU, one thread", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
