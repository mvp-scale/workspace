"""Latent lab intake: measure whether a TypeSafe yes/no question can be answered by the local engine.

GET  /api/latent/intake          -> {"results": [summary...], "running": id | null}
GET  /api/latent/intake?id=<id>  -> one full result (curve, examples, reasons)
POST /api/latent/intake          -> start a run for {"name", "what", "example"} (built like the Conversation flow's
                                    custom detectors) or {"name", "instructions", "criteria": {"true", "false"}}.
Runs probes/latent_intake.py in the background, one at a time: a quick check (300 local Clef calls, ~10-30 s, provisional) by
default, or mode "full" (1,300 calls, 1-3 minutes). POST ?cancel=1 stops the running one and deletes it; results land in
data/embed-zs/intake/results/. The teacher is the saved setting (demo/backends.py, data/embed-zs/teacher.json) or the request's "teacher"; a hosted
teacher costs money, so the page asks before choosing one, and only a local visitor can change the setting.
"""
import json, os, re, subprocess, time

import backends  # the TypeSafe models and the teacher setting
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "embed-zs" / "intake"
PY = ROOT / "models" / "embed-zs" / ".venv" / "bin" / "python"
SCRIPT = ROOT / "probes" / "latent_intake.py"
LIVE = ROOT / "probes" / "latent_live.py"
MAX_BODY = 1_500_000  # live runs carry up to 2,000 texts
_proc = {"p": None, "id": None}


def _summary(r):
    c = (r.get("curve") or [{}])[-1]
    return {"id": r["spec"]["id"], "name": r["spec"].get("name"), "source": r["spec"].get("source", "intake"), "status": r.get("status"),
            "tier": r.get("tier"), "clef_share": None if r.get("status") != "done" else round(1 - c.get("local_share", 0), 4),
            "agree": c.get("agree"), "yes_f1": c.get("yes_f1"), "base_rate": r.get("base_rate"), "positives": r.get("positives_stream"),
            "teacher_entropy": r.get("teacher_entropy"), "started": r.get("started"), "mode": r["spec"].get("mode"),
            "teacher": r["spec"].get("teacher", "clef-flash-q4km")}  # runs before 16 Oct 2026 were all taught by Clef Flash Q4


def running():
    p = _proc["p"]
    if p is not None and p.poll() is None: return _proc["id"]
    return None


def handle_get(query):
    q = dict(x.split("=", 1) for x in query.split("&") if "=" in x)
    if "wordings" in q:
        f = BASE / "wordings.json"
        return (200, json.loads(f.read_text())) if f.is_file() else (404, {"error": "No wordings test yet. Run probes/latent_wordings.py eval."})
    if "depth" in q:
        f = BASE / "depth.json"
        return (200, json.loads(f.read_text())) if f.is_file() else (404, {"error": "No depth test yet. Run probes/latent_depth.py eval."})
    if "journey" in q:
        if not re.fullmatch(r"[a-z0-9-]{1,80}", q["journey"]): return 400, {"error": "Bad id."}
        f = BASE / f"journey-{q['journey']}.json"
        return (200, json.loads(f.read_text())) if f.is_file() else (404, {"error": "No walkthrough for that question. Run probes/latent_journey.py."})
    if "id" in q:
        if not re.fullmatch(r"[a-z0-9-]{1,80}", q["id"]): return 400, {"error": "Bad id."}
        f = BASE / "results" / f"{q['id']}.json"
        return (200, json.loads(f.read_text())) if f.is_file() else (404, {"error": "No intake result with that id."})
    rows = []
    for f in sorted((BASE / "results").glob("*.json")):
        try:
            r = json.loads(f.read_text())
            if r.get("kind") == "live" or r["spec"].get("mode") == "live": continue
            rows.append(_summary(r))
        except Exception: pass
    return 200, {"results": rows, "running": running()}


def cancel():
    rid, p = _proc["id"], _proc["p"]
    if p is None or p.poll() is not None: return 200, {"cancelled": None}
    p.terminate()
    try: p.wait(5)
    except Exception: p.kill()
    for f in [BASE / "results" / f"{rid}.json", BASE / "specs" / f"{rid}.json", BASE / "specs" / f"{rid}.log", BASE / "specs" / f"{rid}.texts.json"]: f.unlink(missing_ok=True)
    _proc["p"] = _proc["id"] = None
    return 200, {"cancelled": rid}


def handle_post(raw, query=""):
    if "cancel=1" in query: return cancel()
    if len(raw) > MAX_BODY: return 413, {"error": "Request too large."}
    if running(): return 409, {"error": f"An intake is already running ({_proc['id']}). Wait for it to finish."}
    try: req = json.loads(raw or b"{}")
    except ValueError: return 400, {"error": "Body must be JSON."}
    name = str(req.get("name", "")).strip()[:80]
    if req.get("what"):
        what, ex = str(req["what"]).strip()[:300], str(req.get("example", "")).strip()[:300]
        instructions = f"Does the text match this description: {what}"
        criteria = {"true": f'The text matches: {what}.' + (f' Example: "{ex}"' if ex else ""), "false": f"The text does not match: {what}"}
    else:
        instructions = str(req.get("instructions", "")).strip()[:400]
        crit = req.get("criteria") or {}
        criteria = {"true": str(crit.get("true", "")).strip()[:300], "false": str(crit.get("false", "")).strip()[:300]}
        what, ex = None, None
    if not name or not instructions or not criteria["true"] or not criteria["false"]:
        return 400, {"error": "Give a name and either a description (what) or instructions with true and false criteria."}
    texts = req.get("texts")
    if texts is not None:
        if not isinstance(texts, list): return 400, {"error": "texts must be a list of strings."}
        texts = [re.sub(r"\s+", " ", str(t)).strip()[:600] for t in texts]
        texts = list(dict.fromkeys(t for t in texts if len(t) >= 8))[:2000]
        if len(texts) < 60: return 400, {"error": f"Give at least 60 distinct texts of 8+ characters (got {len(texts)}). One conversation line or window per line."}
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "question"
    rid = f"{'live' if texts is not None else 'intake'}-{slug}-{int(time.time())}"
    teacher = str(req.get("teacher") or backends.teacher())
    if teacher not in backends.BACKENDS: return 400, {"error": "Unknown teacher model."}
    spec = {"id": rid, "name": name, "source": "intake", "what": what, "example": ex, "type": "noul", "instructions": instructions,
            "criteria": criteria, "mode": "full" if req.get("mode") == "full" else "quick", "teacher": teacher}  # who teaches, recorded with the result
    spec.update({"n_stream": 800, "n_test": 500} if spec["mode"] == "full" else {"n_stream": 200, "n_test": 100})
    (BASE / "specs").mkdir(parents=True, exist_ok=True); (BASE / "results").mkdir(parents=True, exist_ok=True)
    sp = BASE / "specs" / f"{rid}.json"; sp.write_text(json.dumps(spec))
    (BASE / "results" / f"{rid}.json").write_text(json.dumps({"spec": spec, "status": "queued", "started": time.time()}))
    env = {**os.environ, "HF_HOME": str(ROOT / "data" / "hf"), "OMP_NUM_THREADS": "4", "CUDA_VISIBLE_DEVICES": ""}
    log = open(BASE / "specs" / f"{rid}.log", "w")
    if texts is not None:
        spec["mode"] = "live"; sp.write_text(json.dumps(spec))
        tp = BASE / "specs" / f"{rid}.texts.json"; tp.write_text(json.dumps(texts))
        cmd = [str(PY), "-I", str(LIVE), "--spec", str(sp), "--texts", str(tp)]
    else:
        cmd = [str(PY), "-I", str(SCRIPT), "--spec", str(sp)]
    _proc["p"] = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, cwd=str(ROOT))
    _proc["id"] = rid
    return 202, {"id": rid, "status": "queued"}
