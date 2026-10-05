"""Persona lab (mock-up): seeded personas, the persona and idea extractors, and audience scoring on the local Winnow server.

  GET  /api/persona-lab/persona?seed=N      -> persona + sha1 (same seed, same persona; also regenerated and compared)
  GET  /api/persona-lab/cohorts             -> counts of 10,000 seeded personas by age band, area, income, household (no model)
  POST /api/persona-lab/extract {seed}      -> typed-question numbers read from the profile text
  POST /api/persona-lab/idea {text}         -> the idea's demands as numbers
  POST /api/persona-lab/score {text, seeds} -> P(try) per persona, at most 100 seeds per call; cached in memory by text and seed

Personas are generated in memory (probes/persona/personas.py), nothing is stored. Questions live in probes/persona/offline.py,
the same ones the offline pilot measured. Calls go to winnow-server on :8091 only (no hosted spend).
"""
import hashlib
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "probes" / "persona"))
import offline  # noqa: E402
import personas  # noqa: E402

MAX_BODY = 20000
MAX_SEEDS = 100
_pool = ThreadPoolExecutor(4)
_cache = {}
_cohorts = None
TRY_Q = {"try": {"type": "noul", "instructions": "After reading the description, this person would try the product in the next month."}}


def _sha(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:12]


def _seed(v):
    s = int(v)
    if not 0 <= s <= 2**31:
        raise ValueError("seed out of range")
    return s


def _public(p):
    return {**p, "age_band": personas.age_band(p["age"])}


def persona(seed):
    p = personas.gen(seed)
    return {"persona": _public(p), "sha1": _sha(p), "again": _sha(personas.gen(seed)), "same": p == personas.gen(seed)}


def cohorts():
    global _cohorts
    if _cohorts is None:
        c = Counter()
        for s in range(1, 10001):
            p = personas.gen(s)
            c[(personas.age_band(p["age"]), p["area"], p["income"], p["household"])] += 1
        _cohorts = {"total": 10000, "cells": [{"age_band": a, "area": b, "income": i, "household": h, "n": n} for (a, b, i, h), n in sorted(c.items())],
                    "dims": {"age_band": [f"{a}-{b}" for a, b in personas.AGE_BANDS], "area": personas.AREAS, "income": personas.INCOMES}}
    return _cohorts


def extract(seed):
    p = personas.gen(seed)
    n = offline.persona_numbers(p)
    traits = {t: {"w0": n[f"{t}0"], "w1": n[f"{t}1"], "value": (n[f"{t}0"] + n[f"{t}1"]) / 2, "hidden": p["latent"][t]} for t in personas.TRAITS}
    return {"seed": seed, "traits": traits, "aspiration": {"probs": n["asp"], "hidden": p["aspiration"]}, "worldview": {"probs": n["wv"], "hidden": p["worldview"]}}


def idea(text):
    qs = {k: {"type": "noul", "instructions": v} for k, v in offline.IDEA_Q.items()}
    a = offline.call("Product description:\n" + text, qs)
    return {"demands": {k: a[k]["noul"] for k in offline.IDEA_Q}, "labels": offline.IDEA_Q}


def _score_one(job):
    key, text, seed = job
    if key in _cache:
        return _cache[key]
    p = personas.gen(seed)
    v = offline.call(f"Product description:\n{text}\n\nPerson reading it:\n{p['profile']}", TRY_Q)["try"]["noul"]
    row = {"seed": seed, "p": v, "age_band": personas.age_band(p["age"]), "area": p["area"], "income": p["income"], "household": p["household"]}
    _cache[key] = row
    return row


def score(text, seeds):
    h = hashlib.sha1(text.encode()).hexdigest()[:16]
    rows = list(_pool.map(_score_one, [((h, s), text, s) for s in seeds]))
    return {"rows": rows}


def handle_get(path, query):
    q = dict(kv.split("=", 1) for kv in query.split("&") if "=" in kv)
    try:
        if path == "/api/persona-lab/persona":
            return 200, persona(_seed(q.get("seed", "1")))
        if path == "/api/persona-lab/cohorts":
            return 200, cohorts()
    except (ValueError, TypeError) as e:
        return 400, {"error": str(e)}
    return 404, {"error": "not found"}


def handle_post(path, raw):
    if len(raw) > MAX_BODY:
        return 413, {"error": "body too large"}
    try:
        req = json.loads(raw)
        if path == "/api/persona-lab/extract":
            return 200, extract(_seed(req["seed"]))
        text = str(req.get("text", "")).strip()
        if path in ("/api/persona-lab/idea", "/api/persona-lab/score") and not 10 <= len(text) <= 2000:
            return 400, {"error": "idea text must be 10 to 2000 characters"}
        if path == "/api/persona-lab/idea":
            return 200, idea(text)
        if path == "/api/persona-lab/score":
            seeds = [_seed(s) for s in req["seeds"]]
            if not 0 < len(seeds) <= MAX_SEEDS:
                return 400, {"error": f"1 to {MAX_SEEDS} seeds per call"}
            return 200, score(text, seeds)
    except (ValueError, KeyError, TypeError) as e:
        return 400, {"error": f"bad request: {e}"}
    except OSError as e:
        return 502, {"error": f"Winnow server (:8091) not reachable: {e}"}
    return 404, {"error": "not found"}
