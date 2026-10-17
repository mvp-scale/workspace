#!/usr/bin/env python3
"""CPU decision engine: a TypeSafe POST /v1/systemone server that answers yes/no (noul) questions on the CPU only.

Answers every yes/no (noul), choice and score question. Each answer's trace says its basis: "trained" (a head learned from
labelled answers) or "untrained guess" (closeness of the text to each option, with how such guesses measured on our sets).
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
BitMob locations: a router (a small static mob, ~0.2 ms) reads each question's request and names its area (code, science,
general); a question learned in several locations is answered by the routed location's head (data/bitmob/live/, built by
probes/bitmob_build.py). Every answer's trace says the location, the member, and the router's choice and runner-up.
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
STATS = {"requests": 0, "cpu_answers": 0, "teacher_answers": 0, "guesses": 0, "encode_ms": []}


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


# ---- BitMob locations (probes/bitmob_build.py -> data/bitmob/live/): a router reads each question's request (instructions +
# criteria + state) with a small static mob (~0.2 ms) and names its area; a question learned in several locations is answered
# by the head in the routed location (or, if that location has not learned it, the location that measured best). The router
# chooses on its own; callers never name a location. Library questions above live in the general location (e5-small).
LIVE = BASE.parent.parent / "bitmob" / "live"
MOBS, MULTI, ROUTER = {}, {}, None
if (LIVE / "questions.json").exists():
    from model2vec import StaticModel
    _cfg = json.loads((LIVE / "questions.json").read_text()); _members = {m["id"]: m for m in json.loads((LIVE.parent / "members.json").read_text())["members"]}

    def _static(mid):
        if mid not in MOBS:
            M = StaticModel.from_pretrained(_members[mid]["source"])
            def enc(t, M=M):
                v = np.asarray(M.encode([t])[0], np.float32); return v / max(float(np.linalg.norm(v)), 1e-9)
            MOBS[mid] = enc
        return MOBS[mid]
    _r = np.load(LIVE / "router.npz")
    ROUTER = {"reader": _cfg["router_reader"], "enc": _static(_cfg["router_reader"]), "W": _r["coef"], "b": _r["intercept"], "areas": [str(a) for a in _r["classes"]], "members": _cfg["areas"]}
    for _q in _cfg["questions"]:
        for _h in _q["heads"].values():
            _h["w"] = np.array(_h["w"], np.float32)
            if _h["member"] != "e5-small": _static(_h["member"])
        MULTI[_q["instructions"]] = _q
    MULTI_BY_ID = {q["id"]: q for q in MULTI.values()}
    print(f"router: areas {ROUTER['areas']} read by {ROUTER['reader']}; {len(MULTI)} question(s) learned in several locations", flush=True)


def route(state, q):
    """Which location this question's request belongs to: the area, its probability, the runner-up and the time taken."""
    t = time.perf_counter(); crit = q.get("criteria") or {}; opts = crit.values() if isinstance(crit, dict) else crit
    text = f"{q.get('instructions', '')} | {' / '.join(str(v) for v in opts)[:400]}\n{state[:1500]}"
    z = ROUTER["W"] @ ROUTER["enc"](text) + ROUTER["b"]; p = np.exp(z - z.max()); p /= p.sum(); o = np.argsort(-p)
    return {"location": ROUTER["areas"][o[0]], "p": round(float(p[o[0]]), 3), "runner_up": ROUTER["areas"][o[1]], "runner_up_p": round(float(p[o[1]]), 3),
            "ms": round((time.perf_counter() - t) * 1000, 2)}


def teacher_answer(state, q, tid):
    """The teacher's whole answer and time for one question of any type (the backup, and the side-by-side comparison)."""
    t = time.perf_counter(); out = backends.ask(tid, state, {"q": q})["q"]
    return out, (time.perf_counter() - t) * 1000


def teacher_ask(state, q, tid):
    out, ms = teacher_answer(state, q, tid); return float(out["noul"]), ms


def teacher_info(tid): return {"id": tid, "name": backends.name(tid), "hosted": backends.BACKENDS[tid]["hosted"]}


# ---- every question gets an answer --------------------------------------------------------------------------------------
# yes/no, choice and score are one thing: a probability over options (TypeSafe, as in kev/kev/api.py: noul = [no, yes] from
# criteria false/true, choice = its keys, score = its levels). A question with a trained head is answered by it (basis
# "trained"). Any other question is answered by closeness: cosine between the state vector and each option's vector
# (instructions + option text, same encoder), softmax with one global scale, labelled "untrained guess" together with how
# such guesses did on our labelled sets (data/bitmob/live/guess_accuracy.json, from probes/bitmob_guess.py). Never refused.
GUESS_SCALE = float(os.environ.get("BITMOB_GUESS_SCALE", "10"))
GUESS_FILE = BASE.parent.parent / "bitmob" / "live" / "guess_accuracy.json"
_OPTV = {}  # option text -> vector; the same questions come back again and again


def render(v):
    if v is None: return ""
    if isinstance(v, (str, int, float, bool)): return str(v)
    if isinstance(v, list): return "\n".join(f"- {render(x)}" for x in v)
    return "\n".join(f"{k}: {render(x)}" for k, x in v.items())


def options_of(q):
    """(labels, option texts) for any TypeSafe question, the same way kev turns them into options."""
    ot = lambda k, d: k if d is None or d == "" else f"{k}: {render(d)}"
    c = q.get("criteria")
    if q["type"] == "noul": c = c or {}; return ["no", "yes"], [ot("no", c.get("false")), ot("yes", c.get("true"))]
    if q["type"] == "choice": return list(c), [ot(k, x) for k, x in c.items()]
    return [str(i) for i in range(len(c))], [render(x) for x in c]


def check(key, q):
    if not isinstance(q, dict) or q.get("type") not in ("noul", "choice", "score"): return f"question {key!r}: type must be noul, choice or score"
    c = q.get("criteria")
    if q["type"] == "choice" and not (isinstance(c, dict) and c): return f"question {key!r}: a choice question needs criteria as an object of options"
    if q["type"] == "score" and not (isinstance(c, list) and len(c) >= 2): return f"question {key!r}: a score question needs criteria as a list of at least 2 levels"
    if q["type"] == "noul" and c is not None and not isinstance(c, dict): return f"question {key!r}: noul criteria must be an object with true/false"
    return None


def guess(v, q):
    labels, texts = options_of(q); ins = render(q.get("instructions"))
    for t in texts:
        k = f"{ins}\n{t}"
        if k not in _OPTV:
            with LOCK: _OPTV[k] = encode(k)
            if len(_OPTV) > 5000: _OPTV.pop(next(iter(_OPTV)))
    cos = np.array([_OPTV[f"{ins}\n{t}"] @ v for t in texts]); z = cos * GUESS_SCALE; p = np.exp(z - z.max()); p /= p.sum()
    return labels, p, cos


def shaped(qtype, labels, p):
    """A TypeSafe answer from a probability over options (the same shapes kev returns)."""
    r = lambda x: round(float(x), 4); K = len(p)
    if qtype == "noul": return {"type": "noul", "noul": r(p[1])}
    if qtype == "choice":
        return {"type": "choice", "choice": labels[int(np.argmax(p))], "confidence": r(1.0 if K == 1 else (max(p) - 1 / K) / (1 - 1 / K)),
                "probabilities": {l: r(x) for l, x in zip(labels, p)}}
    mode = int(np.argmax(p))
    return {"type": "score", "score": r(sum(i * x for i, x in enumerate(p))), "probabilities": {l: r(x) for l, x in zip(labels, p)},
            "confidence": r(1.0 - sum(x * abs(i - mode) for i, x in enumerate(p)) / (K - 1))}


def guess_record(qtype):
    try: return json.loads(GUESS_FILE.read_text()).get(qtype)
    except (OSError, ValueError): return None


def answer(req, backup, compare=False):
    state = req.get("state"); qs = req.get("questions") or {}
    if not isinstance(state, str): state = render(state)
    if not state.strip(): return 400, {"error": "state must not be empty"}
    if not isinstance(qs, dict) or not qs: return 400, {"error": "questions must be a non-empty object"}
    for key, q in qs.items():
        if (err := check(key, q)): return 422, {"error": err}
    t_all = time.perf_counter()
    with LOCK:
        t = time.perf_counter(); v = encode(state); enc_ms = (time.perf_counter() - t) * 1000
    t = time.perf_counter(); p_all = 1 / (1 + np.exp(-(W @ v + B))); heads_ms = (time.perf_counter() - t) * 1000
    answers, trace = {}, {}; tid = backends.teacher()
    for key, q in qs.items():
        rt = route(state, q) if ROUTER else None
        mq = (MULTI.get(q.get("instructions")) or MULTI_BY_ID.get(key)) if MULTI and q["type"] == "noul" else None
        lq = (BY_INS.get(q.get("instructions")) or BY_ID.get(key)) if q["type"] == "noul" and mq is None else None
        if mq is not None:  # trained in several locations: the router's location answers
            loc = rt["location"] if rt and rt["location"] in mq["heads"] else max(mq["heads"], key=lambda l: mq["heads"][l]["held_out_balanced_accuracy"])
            h = mq["heads"][loc]; vv = v if h["member"] == "e5-small" else MOBS[h["member"]](state)
            p = float(1 / (1 + np.exp(-(h["w"] @ vv + h["b"])))); conf = p < h["lo"] or p > h["hi"]; noul = p
            info = {"basis": "trained", "location": loc, "member": h["member"], "route": rt, "library_id": mq["id"], "taught_by": mq["taught_by"],
                    "trained_on": h["trained_on"], "held_out_balanced_accuracy": round(h["held_out_balanced_accuracy"], 3)}
            ask_q = {"type": "noul", "instructions": mq["instructions"], "criteria": mq["criteria"]}
        elif lq is not None:  # trained (the library, general location)
            i = LIB.index(lq); p = float(p_all[i]); conf = p < lq["lo"] or p > lq["hi"]
            noul = float(1 / (1 + np.exp(-(logit(p) - logit(lq["t"])))))
            info = {"basis": "trained", "library_id": lq["id"], "taught_by": lq.get("taught_by"), "trained_on": lq["trained_on"],
                    **({"location": "general", "member": "e5-small", "route": rt} if rt else {})}
            ask_q = {"type": "noul", "instructions": lq["instructions"], "criteria": lq["criteria"]}
        else:  # nobody taught this question: answer by closeness, and say so
            labels, p, cos = guess(v, q)
            info = {"basis": "untrained guess", "measured": guess_record(q["type"]), "cosines": {l: round(float(c), 4) for l, c in zip(labels, cos)}, "member": "e5-small",
                    **({"route": rt} if rt else {})}
            if backup:
                out, ms = teacher_answer(state, q, tid); answers[key] = out
                trace[key] = {"answered_by": "teacher", "why": "untrained question", "cpu_answer": shaped(q["type"], labels, p), "teacher_ms": round(ms, 1), **info}
                STATS["teacher_answers"] += 1; continue
            answers[key] = shaped(q["type"], labels, p); trace[key] = {"answered_by": "cpu", **info}; STATS["cpu_answers"] += 1; STATS["guesses"] = STATS.get("guesses", 0) + 1
            continue
        if backup and not conf:
            pc, ms = teacher_ask(state, ask_q, tid); answers[key] = {"type": "noul", "noul": round(pc, 4)}
            trace[key] = {"answered_by": "teacher", "why": "the CPU was unsure", "cpu_noul": round(noul, 4), "teacher_ms": round(ms, 1), **info}
            STATS["teacher_answers"] += 1
        else:
            answers[key] = {"type": "noul", "noul": round(noul, 4)}; trace[key] = {"answered_by": "cpu", "confident": bool(conf), **info}; STATS["cpu_answers"] += 1
    if compare:  # ask the teacher too, for every question, so the page can show both side by side (4 at a time, Clef's slot count)
        from concurrent.futures import ThreadPoolExecutor
        def ask(item):
            key, q = item
            try: return key, teacher_answer(state, q, tid)
            except Exception: return key, (None, None)
        with ThreadPoolExecutor(4) as ex:
            for key, (out, ms) in ex.map(ask, qs.items()):
                trace.setdefault(key, {"answered_by": "none"}).update(teacher_answer=out, teacher_compare_ms=None if ms is None else round(ms, 1),
                                                                     teacher_noul=None if not out or out.get("type") != "noul" else round(float(out["noul"]), 4))
    STATS["requests"] += 1; STATS["encode_ms"] = (STATS["encode_ms"] + [enc_ms])[-200:]
    basis = [t.get("basis") for t in trace.values()]
    return 200, {"answers": answers, "engine": {"device": "cpu", "runtime": RUNTIME, "gpu_visible": GPU_VISIBLE, "encode_ms": round(enc_ms, 1),
                                                "classifiers_ms": round(heads_ms, 3), "total_ms": round((time.perf_counter() - t_all) * 1000, 1),
                                                "library_size": len(LIB) + len(MULTI), "memory_mb": rss_mb(), "teacher": teacher_info(tid), "trace": trace,
                                                "basis": {"trained": basis.count("trained"), "untrained guess": basis.count("untrained guess")}}}


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
                          {"gate": {"no_below": round(q["lo"], 3), "yes_above": round(q["hi"], 3)}, "location": "general"} for q in LIB] +
                         [{"id": q["id"], "name": q["name"], "group": q["id"], "wording": 1, "instructions": q["instructions"], "criteria": q["criteria"],
                           "taught_by": q["taught_by"], "example": q.get("example"),
                           "locations": {l: {k: h[k] for k in ("member", "trained_on", "positives", "held_out_balanced_accuracy", "held_out_n")} for l, h in q["heads"].items()}}
                          for q in MULTI.values()],
            "router": {"reader": ROUTER["reader"], "areas": ROUTER["areas"], "members": ROUTER["members"]} if ROUTER else None}


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
        if self.path.split("?")[0] == "/embed":   # the raw encoder step, for inspection: exact string in, 384 numbers out
            try: texts = [str(t)[:2000] for t in json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")["texts"]][:50]
            except (ValueError, KeyError, TypeError): return self._send(400, {"error": "send {\"texts\": [\"...\"]} (up to 50)"})
            return self._send(200, {"encoder": "intfloat/e5-small-v2 (" + RUNTIME + ")", "items": [{"string": "query: " + t, "vector": [round(float(x), 6) for x in encode(t)]} for t in texts]})
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
