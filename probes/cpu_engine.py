#!/usr/bin/env python3
"""CPU decision engine: a TypeSafe POST /v1/systemone server that answers yes/no (noul) questions on the CPU only.

The GPU is hidden from this process (CUDA_VISIBLE_DEVICES is cleared before torch loads). The text is encoded once by
e5-small (384 numbers): ONNX Runtime int8 on 8 threads by default (~4 ms; CPU_ENGINE_RUNTIME=torch for PyTorch fp32, ~12 ms); every question in the library is one logistic classifier on those numbers (1.5 KB each).
The library is the 14 depth-test questions (probes/latent_depth.py), each trained on all of its teacher's answers for its
training stream. A question is matched by its exact instructions text, or by its library id as the question key.

Each answer's noul is P(yes) re-centred so 0.5 is the yes/no cut chosen on the training stream (best F1, out of fold).
"confident" says whether the answer lies outside the gate (the band where the cascade still agrees with the teacher >= 97%).
With ?compare=1 the trace also carries the teacher's answer and time for every question (for side-by-side display). With ?backup=1, unsure answers and questions outside the library go to the teacher (any TypeSafe model, chosen in
data/embed-zs/teacher.json via demo/backends.py; default Clef Flash Q4); without it
the CPU answers everything it can and refuses questions outside its library.

    CUDA_VISIBLE_DEVICES= models/embed-zs/.venv/bin/python probes/cpu_engine.py      # 127.0.0.1:8020 (./service.sh start classifier)
GET /health (memory, device, timings), GET /library, POST /v1/systemone[?backup=1].
"""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""  # CPU only, whatever the caller set
import hashlib, json, resource, sys, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).parent))
from latent_depth import QUESTIONS, spec_of, thr_from_oof, LAB, BASE
from latent_intake import gate

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demo"))
import backends  # the TypeSafe models and the teacher setting (data/embed-zs/teacher.json), read on every request
PORT = int(os.environ.get("CPU_ENGINE_PORT", "8020"))
LOCK = threading.Lock()  # one encode at a time: the CPU number we quote is for one request, not a contended one
STATS = {"requests": 0, "cpu_answers": 0, "teacher_answers": 0, "encode_ms": []}


def rss_mb(): return int(open("/proc/self/status").read().split("VmRSS:")[1].split()[0]) // 1024


def logit(p): p = np.clip(p, 1e-6, 1 - 1e-6); return np.log(p / (1 - p))


RUNTIME = os.environ.get("CPU_ENGINE_RUNTIME", "onnx-int8")  # "onnx-int8" (default, ~4 ms) or "torch" (PyTorch fp32, ~12 ms)
THREADS = int(os.environ.get("CPU_ENGINE_THREADS", "8" if RUNTIME == "onnx-int8" else "4"))
ENGINE_DIR = BASE.parent / "engine"
if RUNTIME == "onnx-int8":
    # ONNX Runtime with the int8 (dynamically quantised) e5-small graph: AVX2 SIMD kernels across THREADS cores.
    # No torch in this process at all. Tokenisation is the fast Rust tokenizer, as in the model card.
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download
    from tokenizers import Tokenizer
    TOK = Tokenizer.from_file(hf_hub_download("intfloat/e5-small-v2", "tokenizer.json")); TOK.enable_truncation(512)
    _o = ort.SessionOptions(); _o.intra_op_num_threads = THREADS; _o.inter_op_num_threads = 1
    _o.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL; _o.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    SESS = ort.InferenceSession(str(ENGINE_DIR / "e5.int8.onnx"), _o, providers=["CPUExecutionProvider"])
    GPU_VISIBLE = "CUDAExecutionProvider" in SESS.get_providers()

    def encode(text):
        e = TOK.encode("query: " + text); ids = np.array([e.ids], np.int64); m = np.array([e.attention_mask], np.int64)
        h = SESS.run(None, {"input_ids": ids, "attention_mask": m, "token_type_ids": np.zeros_like(ids)})[0][0]
        v = h[m[0] == 1].mean(0); return (v / np.linalg.norm(v)).astype(np.float32)
else:
    import torch
    torch.set_num_threads(THREADS)
    from sentence_transformers import SentenceTransformer
    _ENC = SentenceTransformer("intfloat/e5-small-v2", device="cpu"); GPU_VISIBLE = bool(torch.cuda.is_available())

    def encode(text): return _ENC.encode(["query: " + text], normalize_embeddings=True)[0].astype(np.float32)


def corpus_vectors():
    """The classifiers must be trained on vectors from the same runtime that serves (int8 moves 2-6% of answers otherwise)."""
    if RUNTIME != "onnx-int8": return np.load(BASE / "corpus" / "emb_e5.npy")
    f = ENGINE_DIR / "emb_e5_int8.npy"
    if not f.exists():
        texts = [w["text"] for w in json.load(open(BASE / "corpus" / "windows.json"))]
        print(f"encoding {len(texts)} corpus windows with the int8 runtime (once)…", flush=True); np.save(f, np.stack([encode(t) for t in texts]))
    return np.load(f)


def build_library():
    """The depth-test questions, plus every extra wording that has teacher labels (probes/latent_wordings.py): each wording is
    its own question (id <question>_w2 .. _w5, same group), so a request can ask one question several ways."""
    E = corpus_vectors(); stream = set(json.load(open(BASE / "corpus" / "split.json"))["stream"])
    def train(P):
        idx = np.array([i for i in sorted(stream) if i in P]); y = np.array([P[i] > 0.5 for i in idx])
        if y.sum() < 10: return None  # too few yes examples to learn this question: it stays with the teacher
        oof = np.zeros(len(idx))
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=0).split(E[idx], y):
            oof[te] = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(E[idx][tr], y[tr]).predict_proba(E[idx][te])[:, 1]
        clf = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(E[idx], y)
        t = thr_from_oof(oof, y); _, lo, hi = gate(oof, y)
        return {"w": clf.coef_[0].astype(np.float32), "b": float(clf.intercept_[0]), "t": float(t), "lo": float(lo), "hi": float(hi), "trained_on": int(len(idx)), "positives": int(y.sum())}
    load = lambda f: {int(r["id"]): float(r["p"]) for r in map(json.loads, open(f))}
    def taught_by(f):  # the model that produced a label file (its .meta.json), so every question says who taught it
        try: return json.loads(Path(str(f)[:-6] + ".meta.json").read_text())["teacher"]
        except (OSError, ValueError, KeyError): return None
    try: from latent_wordings import WORDINGS
    except Exception: WORDINGS = {}
    lib = []
    for qid, name, lvl, sp in QUESTIONS:
        sp = spec_of(qid, sp); h = train(load(LAB / f"depth-{qid}.jsonl"))
        if h is not None: h["taught_by"] = taught_by(LAB / f"depth-{qid}.jsonl")
        if h is None: continue
        lib.append({"id": qid, "name": name, "group": qid, "wording": 1, "level": lvl, "instructions": sp["instructions"], "criteria": sp["criteria"], "what": sp.get("what"), **h})
        for k, wd in enumerate(WORDINGS.get(qid, [])):  # index k = file word-<qid>-<k>; index 0 is the library wording above
            f = LAB / f"word-{qid}-{k}.jsonl"
            if wd is None or not f.exists() or (h2 := train(load(f))) is None: continue
            h2["taught_by"] = taught_by(f)
            lib.append({"id": f"{qid}_w{k + 1}", "name": f"{name} · wording {k + 1}", "group": qid, "wording": k + 1, "level": lvl, "instructions": wd["instructions"], "criteria": wd["criteria"], "what": None, **h2})
    return lib


print("building library…", flush=True); t0 = time.time()
LIB = build_library(); BY_INS = {q["instructions"]: q for q in LIB}; BY_ID = {q["id"]: q for q in LIB}
W = np.stack([q["w"] for q in LIB]); B = np.array([q["b"] for q in LIB], np.float32)
for _ in range(5): encode("warm up")
BOOT = {"runtime": RUNTIME, "library_s": round(time.time() - t0, 1), "rss_mb_after_load": rss_mb()}
print(f"ready: {len(LIB)} questions, {BOOT}", flush=True)


def teacher_ask(state, q, tid):
    """The teacher's answer and time for one question (the backup, and the side-by-side comparison)."""
    t = time.perf_counter(); p = float(backends.ask(tid, state, {"q": q})["q"]["noul"])
    return p, (time.perf_counter() - t) * 1000


def teacher_info(tid): return {"id": tid, "name": backends.name(tid), "hosted": backends.BACKENDS[tid]["hosted"]}


def answer(req, backup, compare=False):
    state = req.get("state"); qs = req.get("questions") or {}
    if not isinstance(state, str) or not state.strip(): return 400, {"error": "state must be a non-empty string (this engine reads text)"}
    if not isinstance(qs, dict) or not qs: return 400, {"error": "questions must be a non-empty object"}
    t_all = time.perf_counter()
    with LOCK:
        t = time.perf_counter(); v = encode(state); enc_ms = (time.perf_counter() - t) * 1000
    t = time.perf_counter(); p_all = 1 / (1 + np.exp(-(W @ v + B))); heads_ms = (time.perf_counter() - t) * 1000
    answers, trace, unanswered = {}, {}, {}; tid = backends.teacher(); tname = backends.name(tid)
    for key, q in qs.items():
        if not isinstance(q, dict) or q.get("type") != "noul":
            return 422, {"error": f"question {key!r}: this engine answers noul (yes/no) questions only; choice and score are not built yet"}
        lq = BY_INS.get(q.get("instructions")) or BY_ID.get(key)
        if lq is None:  # outside the library: answer the rest, and say so for this one (or let the teacher answer it)
            if not backup:
                unanswered[key] = f"not in the CPU library ({len(LIB)} trained questions): train it first, or turn the backup on ({tname} answers it)"; continue
            p, ms = teacher_ask(state, q, tid); answers[key] = {"type": "noul", "noul": round(p, 4)}
            trace[key] = {"answered_by": "teacher", "why": "not in the CPU library", "teacher_ms": round(ms, 1)}; STATS["teacher_answers"] += 1; continue
        i = LIB.index(lq); p = float(p_all[i]); conf = p < lq["lo"] or p > lq["hi"]
        noul = float(1 / (1 + np.exp(-(logit(p) - logit(lq["t"])))))
        if backup and not conf:
            pc, ms = teacher_ask(state, {"type": "noul", "instructions": lq["instructions"], "criteria": lq["criteria"]}, tid)
            answers[key] = {"type": "noul", "noul": round(pc, 4)}
            trace[key] = {"answered_by": "teacher", "why": "the CPU was unsure", "cpu_noul": round(noul, 4), "teacher_ms": round(ms, 1), "library_id": lq["id"]}
            STATS["teacher_answers"] += 1
        else:
            answers[key] = {"type": "noul", "noul": round(noul, 4)}
            trace[key] = {"answered_by": "cpu", "confident": bool(conf), "library_id": lq["id"], "taught_by": lq.get("taught_by")}; STATS["cpu_answers"] += 1
    if compare:  # ask the teacher too, for every question, so the page can show both side by side (4 at a time, Clef's slot count)
        from concurrent.futures import ThreadPoolExecutor
        def ask(item):
            key, q = item; lq = BY_INS.get(q.get("instructions")) or BY_ID.get(key)
            qq = {"type": "noul", "instructions": lq["instructions"], "criteria": lq["criteria"]} if lq else q
            try: return key, teacher_ask(state, qq, tid)
            except Exception: return key, (None, None)
        with ThreadPoolExecutor(4) as ex:
            for key, (pc, ms) in ex.map(ask, qs.items()): trace.setdefault(key, {"answered_by": "none"}).update(teacher_noul=None if pc is None else round(pc, 4), teacher_compare_ms=None if ms is None else round(ms, 1))
    STATS["requests"] += 1; STATS["encode_ms"] = (STATS["encode_ms"] + [enc_ms])[-200:]
    return 200, {"answers": answers, "engine": {"device": "cpu", "runtime": RUNTIME, "gpu_visible": GPU_VISIBLE, "encode_ms": round(enc_ms, 1),
                                                "classifiers_ms": round(heads_ms, 3), "total_ms": round((time.perf_counter() - t_all) * 1000, 1),
                                                "library_size": len(LIB), "memory_mb": rss_mb(), "teacher": teacher_info(tid), "trace": trace,
                                                **({"unanswered": unanswered} if unanswered else {})}}


def health():
    e = sorted(STATS["encode_ms"])
    return {"ok": True, "device": "cpu", "gpu_visible": GPU_VISIBLE, "threads": THREADS, "runtime": RUNTIME,
            "encoder": "intfloat/e5-small-v2" + (" (ONNX, int8)" if RUNTIME == "onnx-int8" else " (PyTorch, fp32)"),
            "library_size": len(LIB), "memory_mb": rss_mb(), "peak_memory_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024,
            "classifier_bytes": int(W.nbytes + B.nbytes), "boot": BOOT, "requests": STATS["requests"], "cpu_answers": STATS["cpu_answers"],
            "teacher_answers": STATS["teacher_answers"], "teacher": teacher_info(backends.teacher()),
            "taught_by": {t: sum(q.get("taught_by") == t for q in LIB) for t in {q.get("taught_by") for q in LIB}}, "median_encode_ms": round(e[len(e) // 2], 1) if e else None}


def library():
    return {"questions": [{k: q.get(k) for k in ("id", "name", "group", "wording", "level", "instructions", "criteria", "what", "trained_on", "positives", "taught_by")} |
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
        raw = self.rfile.read(n)
        try: req = json.loads(raw or b"{}")
        except ValueError: return self._send(400, {"error": "body must be JSON"})
        try:
            code, out = answer(req, "backup=1" in self.path, "compare=1" in self.path)
            if code == 200:  # receipt: what this server actually got, so a caller can check nothing was dropped or invented
                qs = req.get("questions") or {}
                out["engine"]["received"] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "questions": len(qs), "question_keys": list(qs),
                                             "request_no": STATS["requests"]}
            self._send(code, out)
        except Exception as e: self._send(500, {"error": str(e)[:300]})

    def log_message(self, *a): pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
