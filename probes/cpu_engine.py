#!/usr/bin/env python3
"""CPU decision engine: a TypeSafe POST /v1/systemone server that answers yes/no (noul) questions on the CPU only.

The GPU is hidden from this process (CUDA_VISIBLE_DEVICES is cleared before torch loads). The text is encoded once by
e5-small (384 numbers, ~12 ms); every question in the library is one logistic classifier on those numbers (1.5 KB each).
The library is the 14 depth-test questions (probes/latent_depth.py), each trained on all of Clef's answers for its
training stream. A question is matched by its exact instructions text, or by its library id as the question key.

Each answer's noul is P(yes) re-centred so 0.5 is the yes/no cut chosen on the training stream (best F1, out of fold).
"confident" says whether the answer lies outside the gate (the band where the cascade still agrees with Clef >= 97%).
With ?compare=1 the trace also carries Clef's answer and time for every question (for side-by-side display). With ?backup=1, unsure answers and questions outside the library go to the local Clef server (:8018, GPU); without it
the CPU answers everything it can and refuses questions outside its library.

    CUDA_VISIBLE_DEVICES= models/embed-zs/.venv/bin/python probes/cpu_engine.py      # 127.0.0.1:8019
GET /health (memory, device, timings), GET /library, POST /v1/systemone[?backup=1].
"""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""  # CPU only, whatever the caller set
import json, resource, sys, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).parent))
from latent_depth import QUESTIONS, spec_of, thr_from_oof, LAB, BASE
from latent_intake import gate

CLEF = "http://127.0.0.1:8018/v1/systemone"; PORT = int(os.environ.get("CPU_ENGINE_PORT", "8019"))
LOCK = threading.Lock()  # one encode at a time: the CPU number we quote is for one request, not a contended one
STATS = {"requests": 0, "cpu_answers": 0, "clef_answers": 0, "encode_ms": []}


def rss_mb(): return int(open("/proc/self/status").read().split("VmRSS:")[1].split()[0]) // 1024


def logit(p): p = np.clip(p, 1e-6, 1 - 1e-6); return np.log(p / (1 - p))


def build_library():
    E = np.load(BASE / "corpus" / "emb_e5.npy"); split = json.load(open(BASE / "corpus" / "split.json"))
    lib = []
    for qid, name, lvl, sp in QUESTIONS:
        sp = spec_of(qid, sp)
        P = {int(r["id"]): float(r["p"]) for r in map(json.loads, open(LAB / f"depth-{qid}.jsonl"))}
        idx = np.array([i for i in split["stream"] if i in P]); y = np.array([P[i] > 0.5 for i in idx])
        if y.sum() < 10: continue  # too few yes examples to learn this question: it stays with Clef
        oof = np.zeros(len(idx))
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=0).split(E[idx], y):
            oof[te] = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(E[idx][tr], y[tr]).predict_proba(E[idx][te])[:, 1]
        clf = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(E[idx], y)
        t = thr_from_oof(oof, y); _, lo, hi = gate(oof, y)
        lib.append({"id": qid, "name": name, "level": lvl, "instructions": sp["instructions"], "criteria": sp["criteria"], "what": sp.get("what"),
                    "w": clf.coef_[0].astype(np.float32), "b": float(clf.intercept_[0]), "t": float(t), "lo": float(lo), "hi": float(hi),
                    "trained_on": int(len(idx)), "positives": int(y.sum())})
    return lib


print("building library…", flush=True); t0 = time.time()
LIB = build_library(); BY_INS = {q["instructions"]: q for q in LIB}; BY_ID = {q["id"]: q for q in LIB}
W = np.stack([q["w"] for q in LIB]); B = np.array([q["b"] for q in LIB], np.float32)
import torch
torch.set_num_threads(int(os.environ.get("CPU_ENGINE_THREADS", "4")))
from sentence_transformers import SentenceTransformer
ENC = SentenceTransformer("intfloat/e5-small-v2", device="cpu")
ENC.encode(["query: warm up"])
BOOT = {"library_s": round(time.time() - t0, 1), "rss_mb_after_load": rss_mb()}
print(f"ready: {len(LIB)} questions, {BOOT}", flush=True)


def clef(state, q):
    body = json.dumps({"state": state, "questions": {"q": q}}).encode()
    t = time.perf_counter()
    with urllib.request.urlopen(urllib.request.Request(CLEF, body, {"Content-Type": "application/json"}), timeout=60) as r:
        return float(json.loads(r.read())["answers"]["q"]["noul"]), (time.perf_counter() - t) * 1000


def answer(req, backup, compare=False):
    state = req.get("state"); qs = req.get("questions") or {}
    if not isinstance(state, str) or not state.strip(): return 400, {"error": "state must be a non-empty string (this engine reads text)"}
    if not isinstance(qs, dict) or not qs: return 400, {"error": "questions must be a non-empty object"}
    t_all = time.perf_counter()
    with LOCK:
        t = time.perf_counter(); v = ENC.encode(["query: " + state], normalize_embeddings=True)[0].astype(np.float32); enc_ms = (time.perf_counter() - t) * 1000
    t = time.perf_counter(); p_all = 1 / (1 + np.exp(-(W @ v + B))); heads_ms = (time.perf_counter() - t) * 1000
    answers, trace = {}, {}
    for key, q in qs.items():
        if not isinstance(q, dict) or q.get("type") != "noul":
            return 422, {"error": f"question {key!r}: this engine answers noul (yes/no) questions only; choice and score are not built yet"}
        lq = BY_INS.get(q.get("instructions")) or BY_ID.get(key)
        if lq is None:
            if not backup: return 422, {"error": f"question {key!r} is not in the CPU library ({len(LIB)} trained questions). Train it first, or send with backup on so Clef answers it."}
            p, ms = clef(state, q); answers[key] = {"type": "noul", "noul": round(p, 4)}
            trace[key] = {"answered_by": "clef (GPU)", "why": "not in the CPU library", "clef_ms": round(ms, 1)}; STATS["clef_answers"] += 1; continue
        i = LIB.index(lq); p = float(p_all[i]); conf = p < lq["lo"] or p > lq["hi"]
        noul = float(1 / (1 + np.exp(-(logit(p) - logit(lq["t"])))))
        if backup and not conf:
            pc, ms = clef(state, {"type": "noul", "instructions": lq["instructions"], "criteria": lq["criteria"]})
            answers[key] = {"type": "noul", "noul": round(pc, 4)}
            trace[key] = {"answered_by": "clef (GPU)", "why": "the CPU was unsure", "cpu_noul": round(noul, 4), "clef_ms": round(ms, 1), "library_id": lq["id"]}
            STATS["clef_answers"] += 1
        else:
            answers[key] = {"type": "noul", "noul": round(noul, 4)}
            trace[key] = {"answered_by": "cpu", "confident": bool(conf), "library_id": lq["id"]}; STATS["cpu_answers"] += 1
    if compare:  # ask Clef too, for every question, so the page can show both side by side (4 at a time, Clef's slot count)
        from concurrent.futures import ThreadPoolExecutor
        def ask(item):
            key, q = item; lq = BY_INS.get(q.get("instructions")) or BY_ID.get(key)
            qq = {"type": "noul", "instructions": lq["instructions"], "criteria": lq["criteria"]} if lq else q
            try: return key, clef(state, qq)
            except Exception: return key, (None, None)
        with ThreadPoolExecutor(4) as ex:
            for key, (pc, ms) in ex.map(ask, qs.items()): trace[key].update(clef_noul=None if pc is None else round(pc, 4), clef_compare_ms=None if ms is None else round(ms, 1))
    STATS["requests"] += 1; STATS["encode_ms"] = (STATS["encode_ms"] + [enc_ms])[-200:]
    return 200, {"answers": answers, "engine": {"device": "cpu", "gpu_visible": bool(torch.cuda.is_available()), "encode_ms": round(enc_ms, 1),
                                                "classifiers_ms": round(heads_ms, 3), "total_ms": round((time.perf_counter() - t_all) * 1000, 1),
                                                "library_size": len(LIB), "memory_mb": rss_mb(), "trace": trace}}


def health():
    e = sorted(STATS["encode_ms"])
    return {"ok": True, "device": "cpu", "gpu_visible": bool(torch.cuda.is_available()), "threads": torch.get_num_threads(), "encoder": "intfloat/e5-small-v2",
            "library_size": len(LIB), "memory_mb": rss_mb(), "peak_memory_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024,
            "classifier_bytes": int(W.nbytes + B.nbytes), "boot": BOOT, "requests": STATS["requests"], "cpu_answers": STATS["cpu_answers"],
            "clef_answers": STATS["clef_answers"], "median_encode_ms": round(e[len(e) // 2], 1) if e else None}


def library():
    return {"questions": [{k: q[k] for k in ("id", "name", "level", "instructions", "criteria", "what", "trained_on", "positives")} |
                          {"gate": {"no_below": round(q["lo"], 3), "yes_above": round(q["hi"], 3)}} for q in LIB]}


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        raw = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/health": return self._send(200, health())
        if p == "/library": return self._send(200, library())
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.split("?")[0] != "/v1/systemone": return self._send(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length", 0))
        if n > 200_000: return self._send(413, {"error": "too large"})
        try: req = json.loads(self.rfile.read(n) or b"{}")
        except ValueError: return self._send(400, {"error": "body must be JSON"})
        try: self._send(*answer(req, "backup=1" in self.path, "compare=1" in self.path))
        except Exception as e: self._send(500, {"error": str(e)[:300]})

    def log_message(self, *a): pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
