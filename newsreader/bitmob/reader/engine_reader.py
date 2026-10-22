#!/usr/bin/env python3
"""MULTI-HEAD MODE (D-0038, contract loop): when reader_config.json has "mh": "<model dir>", ONE shared e5 encoder + heads answer every engine question
(no zero-fill, no copies of the topic probability); only So-what/kind go to Clef. Layout of <model dir> (written by newsreader/bitmob/mh/ training):
  encoder/            HF dir (config, weights, tokenizer); text is read as "query: " + the state's story text, max_length 96, mean-pooled
  heads.json          {"max_length": 96, "groups": {name: {"keys": [...], "act": "sigmoid" | "softmax" | "softmax_groups", "levels": [...]  (softmax_groups only)}}}
  heads.pt            state_dict of torch.nn.ModuleDict of one nn.Linear(hidden, out) per group, i.e. keys "<group>.weight", "<group>.bias"
  groups: gate  sigmoid  [g|happened,g|announced,g|opinion,g|forecast,x|recent]
          scope sigmoid  [s|national,s|local,s|new]
          attr  sigmoid  every a|<dial>|<dir>|<i>|<0|1> key of classify.QS (318 per wording set; one output each)
          domain_yes sigmoid [y|<domain id>] (48, no 'other')
          domain_choice softmax [<domain id>] (49 incl. other)
          region softmax [<region name>..., GLOBAL]
          country softmax [<country id>..., global]  (100 + global; no top-N)
          expected sigmoid [e|<dial>|up, e|<dial>|down, ..., done]
          severity softmax_groups keys [<dial>|<up|down>], levels [<impact level ids>]; out dim = len(keys)*len(levels), reshaped (keys, levels)
Below: the earlier text of this file's docstring (single-head mode, used while "mh" is absent).
BitMob as a World-engine reader (D-0037). A TypeSafe-shaped POST /v1/systemone server on :8021 that answers the ENGINE's question families
from our fine-tuned CPU readers (e5-base heads + e5-small/tf-idf blend, torch fp32, CPU only by code) instead of from Clef:
  gate/type  g|happened g|announced g|opinion g|forecast   <- type head
  recent/scope x|recent s|national s|local s|new            <- heads (Jev P >= 0.5 labels)
  focus      x|us_focus x|foreign_focus                     <- country head (P(usa); 1-P(usa)-P(global)-P(other))
  conditions a|<dial>|<dir>|i|k                              <- 52 condition keys (dial|dir), fired at per-key cuts; only attribute 0 carries the reading, the rest answer 0 (no per-attribute answers exist)
  placement  choice "c" over the domains + y|<domain>       <- topic head (y| = the topic probability; no separate multi-tag head)
  country    region choice "g" and country choice "c"       <- country head (69 classes), summed per region; 'other' and countries outside the engine's 100 go to GLOBAL
Everything else (expected-impact e|*, 'done', severity choices, So-what, kind) goes to local Clef when the model alias is "bitmob-clef"; with "bitmob-cpu" it is refused (HTTP 422) and the engine skips it.
CPU only: CUDA_VISIBLE_DEVICES is cleared before torch loads.   models/embed-zs/.venv/bin/python newsreader/bitmob/reader/engine_reader.py   (BITMOB_READER_PORT, THREADS)
GET /health, GET /stats."""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import sys, json, time, csv, hashlib, threading, collections, urllib.request
import numpy as np, torch, joblib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from scipy.sparse import hstack, csr_matrix
from transformers import AutoTokenizer, AutoModel
W = "/workspace/data"; MD = f"{W}/bitmob-integration/models"; PORT = int(os.environ.get("BITMOB_READER_PORT", "8021"))
torch.set_num_threads(int(os.environ.get("THREADS", "8")))
CFG = json.load(open(f"{W}/bitmob-integration/reader_config.json"))
LABEL = {"bitmob-clef": "BitMob (+Clef for impact/severity)", "bitmob-cpu": "BitMob (CPU only)"}
sys.path.insert(0, "/workspace/demo")
def rss_mb(): return int(open("/proc/self/status").read().split("VmRSS:")[1].split()[0]) // 1024


class Reader:
    def __init__(self):
        t0 = time.time(); self.areas = {}
        for a, d in CFG["e5base"].items():
            d = d if d.startswith("/") else f"/workspace/{d}"; keys = json.load(open(f"{d}/keys.json")); tok = AutoTokenizer.from_pretrained(d)
            enc = AutoModel.from_pretrained(d).float().eval(); head = torch.nn.Linear(enc.config.hidden_size, len(keys)); head.load_state_dict({k: v.float() for k, v in torch.load(f"{d}/head.pt").items()})
            self.areas[a] = {"keys": keys, "tok": tok, "enc": enc, "head": head, "multi": a in ("type", "conditions", "heads"), "w_tfidf": CFG["w_tfidf"].get(a, 0.0)}
        self.tok = self.areas["type"]["tok"]
        from sentence_transformers import SentenceTransformer
        self.small = SentenceTransformer("intfloat/e5-small-v2", device="cpu"); self.tf = joblib.load(f"{MD}/tfidf_vectorizer.joblib")
        self.lr = {a: joblib.load(f"{MD}/tfidf_{a}.joblib") for a, v in self.areas.items() if v["w_tfidf"] > 0}
        self.boot_s = round(time.time() - t0, 1)

    def e5(self, texts):
        b = self.tok(["query: " + t for t in texts], padding=True, truncation=True, max_length=96, return_tensors="pt"); out = {}
        for a, v in self.areas.items():
            h = v["enc"](**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1); o = v["head"]((h * m).sum(1) / m.sum(1))
            out[a] = (torch.sigmoid(o) if v["multi"] else torch.softmax(o, 1)).numpy()
        return out

    def read_many(self, texts):
        with torch.inference_mode():
            P = self.e5(texts)
            if self.lr:
                F = hstack([csr_matrix(self.small.encode(["query: " + t for t in texts], batch_size=64, normalize_embeddings=True, show_progress_bar=False)), self.tf.transform(texts)]).tocsr()
                for a, lr in self.lr.items():
                    if isinstance(lr, list): T = np.stack([x.predict_proba(F)[:, 1] if x is not None else np.zeros(len(texts)) for x in lr], 1)
                    else: T = np.zeros_like(P[a]); T[:, lr.classes_] = lr.predict_proba(F)
                    w = self.areas[a]["w_tfidf"]; P[a] = (1 - w) * P[a] + w * T
        return [{a: {k: float(p) for k, p in zip(self.areas[a]["keys"], P[a][i])} for a in P} for i in range(len(texts))]


MH_DIR = os.environ.get("BITMOB_MH_DIR") or CFG.get("mh") or ""


class MHReader:
    """The trainer's saved layout (newsreader/bitmob/mh/mh_common.save): <dir>/encoder, <dir>/<head>/head.pt, keys.json. Loaded through mh_common.load/predict (shared with score_mh.py)."""
    def __init__(self):
        sys.path.insert(0, "/workspace/newsreader/bitmob/mh"); import mh_common
        t0 = time.time(); d = MH_DIR if MH_DIR.startswith("/") else f"/workspace/{MH_DIR}"; self.mc = mh_common
        self.model, self.tok, self.K = mh_common.load(d); self.areas = {h: self.K[h] for h in mh_common.HEADS if h in self.K}; self.boot_s = round(time.time() - t0, 1)

    def read_many(self, texts):
        H = self.mc.predict(self.model, self.tok, texts, bs=32); K = self.K; out = []
        for n in range(len(texts)):
            r = {h: {k: float(p) for k, p in zip(K[h], H[h][n])} for h in ("gate", "scope", "cond", "topic_c", "topic_y", "region", "country", "expected", "done") if h in H}
            r["severity"] = {d: {l: float(H["severity"][n, j, q]) for q, l in enumerate(K["levels"])} for j, d in enumerate(K["severity"])}; out.append(r)
        return out


def answer_mh(key, q, r):
    """Answer one engine question from the multi-head reads r (head -> {key: p}). None = not answerable (So-what, kind)."""
    t = q.get("type"); crit = q.get("criteria") or {}
    if key in r["gate"]: return {"type": "noul", "noul": r["gate"][key]}
    if key in r["scope"]: return {"type": "noul", "noul": r["scope"][key]}          # s|national, s|local, s|new, x|us_focus, x|foreign_focus
    if key.startswith("a|"): _, d, dr, i, _w = key.split("|"); v = r["cond"].get(f"{d}|{dr}|{i}"); return None if v is None else {"type": "noul", "noul": v}      # both wordings get the head's mean
    if key.startswith("y|") and key[2:] in r["topic_y"]: return {"type": "noul", "noul": r["topic_y"][key[2:]]}
    if key.startswith("e|") and key[2:] in r["expected"]: return {"type": "noul", "noul": r["expected"][key[2:]]}
    if key == "done" and t == "noul": return {"type": "noul", "noul": r["done"]["done"]}
    if t == "choice" and key == "g" and "GLOBAL" in crit: return choice(r["region"], list(crit))
    if t == "choice" and key == "c" and "other_here" in crit: return choice({k: r["country"].get(k, 0.0) for k in crit}, list(crit))
    if t == "choice" and key == "c" and len(set(crit) & set(r["topic_c"])) >= 20: return choice(r["topic_c"], list(crit))
    if t == "choice" and key in r["severity"]: return choice(r["severity"][key], list(crit))
    return None


MH = bool(MH_DIR)
R = None; LOCK = threading.Lock(); CACHE = collections.OrderedDict()
STATS = {"requests": 0, "stories_read": 0, "bitmob_questions": 0, "clef_questions": 0, "clef_calls": 0, "clef_s": 0.0, "refused": 0, "read_ms": [], "started": time.time()}


def read_story(text):
    k = hashlib.sha1(text.encode()).hexdigest()
    with LOCK:
        if k in CACHE: return CACHE[k]
        t = time.time(); r = R.read_many([text])[0]; STATS["read_ms"].append(round(1000 * (time.time() - t), 1)); STATS["read_ms"] = STATS["read_ms"][-500:]; STATS["stories_read"] += 1
        CACHE[k] = r
        while len(CACHE) > 64: CACHE.popitem(last=False)
        return r


def countries():
    rows = list(csv.DictReader(open(os.environ.get("WORLD_COUNTRIES", "/workspace/probes/world-engine/data/countries_world100.csv")))); return {r["id"]: r["region"] for r in rows}
REGION_OF = countries()


def conds(r):
    """-> {dial|dir: (p, fired)}"""
    return {k: (p, p >= CFG["cond_cuts"].get(k, 1.01)) for k, p in r["conditions"].items()}


def state_text(state):
    return state.split("\n", 1)[1] if state.startswith("News item") and "\n" in state else state


def choice(probs, keys):
    p = {k: max(float(probs.get(k, 0.0)), 0.0) for k in keys}; s = sum(p.values()) or 1.0; p = {k: v / s for k, v in p.items()}; c = max(p, key=p.get)
    return {"type": "choice", "choice": c, "probabilities": p, "confidence": p[c]}


def answer_one(key, q, r, cd):
    t = q.get("type")
    if key.startswith("g|") and key[2:] in r["type"]: return {"type": "noul", "noul": r["type"][key[2:]]}
    if key in ("x|recent", "s|national", "s|local", "s|new"): return {"type": "noul", "noul": r["heads"][key.split("|")[1]]}
    if key == "x|us_focus": return {"type": "noul", "noul": r["country"].get("usa", 0.0)}
    if key == "x|foreign_focus": return {"type": "noul", "noul": max(0.0, 1 - r["country"].get("usa", 0.0) - r["country"].get("global", 0.0) - r["country"].get("other", 0.0))}
    if key.startswith("a|"):
        _, d, dr, i, _w = key.split("|"); c = cd.get(f"{d}|{dr}")
        if c is None or i != "0": return {"type": "noul", "noul": 0.0}
        return {"type": "noul", "noul": max(c[0], 0.65) if c[1] else min(c[0], 0.64)}
    if key.startswith("y|") and key[2:] in r["topic"]: return {"type": "noul", "noul": r["topic"][key[2:]]}
    crit = q.get("criteria") or {}
    if key == "c" and t == "choice" and "other_here" not in crit and len(set(crit) & set(r["topic"])) >= 20: return choice(r["topic"], list(crit))
    if key == "g" and t == "choice" and "GLOBAL" in crit:
        reg = {g: 0.0 for g in crit}
        for c, p in r["country"].items():
            g = REGION_OF.get(c); reg[g if g in reg else "GLOBAL"] += p
        return choice(reg, list(reg))
    if key == "c" and t == "choice" and "other_here" in crit: return choice({**{c: r["country"].get(c, 0.0) for c in crit if c != "other_here"}, "other_here": 0.0}, list(crit))
    return None


def systemone(body):
    state, qs = body["state"], body["questions"]; mode = body.get("model") or "bitmob-clef"; STATS["requests"] += 1; ans, rest = {}, {}
    r = None; t0 = time.time()
    for k, q in qs.items():
        if r is None: r = read_story(state_text(state)); cd = None if MH else conds(r)
        a = answer_mh(k, q, r) if MH else answer_one(k, q, r, cd)
        if a is None: rest[k] = q
        else: ans[k] = a; STATS["bitmob_questions"] += 1
    if rest:
        if mode == "bitmob-cpu": STATS["refused"] += 1; raise PermissionError("pure-CPU mode: this question needs an LLM reader (expected impact, severity, So-what): " + ", ".join(list(rest)[:3]))
        import backends
        b = backends.BACKENDS["clef-flash-q4km"]; req = urllib.request.Request(b["url"].rstrip("/") + "/v1/systemone", json.dumps({"state": state, "questions": rest, **({"model": b["model"]} if b.get("model") and b["model"] != "jev-latest" else {})}).encode(), {"Content-Type": "application/json"})
        t = time.time()
        with urllib.request.urlopen(req, timeout=300) as resp: out = json.load(resp)
        STATS["clef_s"] += time.time() - t; STATS["clef_calls"] += 1; STATS["clef_questions"] += len(rest)
        for k, a in out["answers"].items(): ans[k] = a
    return {"model": mode, "reader": LABEL.get(mode, mode), "answers": ans, "usage": {"clef_questions": len(rest)}}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path.startswith("/health"):
            ms = STATS["read_ms"]; return self._send(200, {"status": "ok", "ready": R is not None, "device": "cpu", "cuda_visible": bool(torch.cuda.is_available()), "rss_mb": rss_mb(), "boot_s": R and R.boot_s,
                                                              "readers": LABEL, "mode": "multi-head" if MH else "single-head", "areas": ({a: len(v) for a, v in R.areas.items()} if MH else {a: len(v["keys"]) for a, v in R.areas.items()}) if R else {}, "median_read_ms": float(np.median(ms)) if ms else None})
        if self.path.startswith("/stats"): return self._send(200, {k: v for k, v in STATS.items() if k != "read_ms"} | {"rss_mb": rss_mb(), "median_read_ms": float(np.median(STATS["read_ms"])) if STATS["read_ms"] else None})
        self._send(404, {"error": "not found"})
    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            if self.path == "/read": return self._send(200, {"read": read_story(body["text"])} if "text" in body else {"reads": R.read_many(list(body["texts"]))})      # raw head outputs, no Clef (one text: cached, as the engine path)
            if not self.path.startswith("/v1/systemone"): return self._send(404, {"error": "not found"})
            self._send(200, systemone(body))
        except PermissionError as e: self._send(422, {"error": str(e)})
        except Exception as e: self._send(500, {"error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    R = MHReader() if MH else Reader(); R.read_many(["warm up the reader with one short story about a flood."])
    print(f"BitMob engine reader ready on :{PORT} (boot {R.boot_s}s, rss {rss_mb()} MB, cuda {torch.cuda.is_available()})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
