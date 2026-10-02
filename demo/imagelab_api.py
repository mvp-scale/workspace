"""Image lab: the 25 business image tasks, their items and every model's stored answers (read-only).

  GET /api/imagelab                    -> {areas, models, tasks:[...]} (one payload; small enough to send whole)
  GET /imagelab-img/<task>/<file>      -> one image from data/image-lab/images (git-ignored, third-party images stay out of the repo)

Task sets are built by probes/images/build_*.py; answers come from probes/images/run_winnow.py into
data/image-lab/runs/<model>/<task>/results.jsonl. Nothing here calls a model.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETS = ROOT / "probes" / "images"
DATA = ROOT / "data" / "image-lab"
IMAGES = DATA / "images"
RUNS = DATA / "runs"
TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

AREAS = [  # business area -> task numbers. 1-25 are the original lab. 26+ are the real-photo sets from the gap.
    ("Finance and admin", set(range(1, 9)) | {31, 32}), ("Insurance and claims", range(9, 13)), ("Retail and logistics", range(13, 18)),
    ("Safety and compliance", range(18, 21)), ("Manufacturing and field", range(21, 24)), ("IT and property", range(24, 26)),
    ("Traffic and parking", range(26, 27)), ("Livestock", set(range(27, 29)) | {38}), ("Property plans", range(29, 30)),
    ("Catastrophe claims", range(30, 31)), ("Utilities", {36}), ("Roads", {37}),
]
TASK_ID = re.compile(r"^t(\d\d)_[a-z0-9_]+$")


def _jsonl(path):
    return [json.loads(line) for line in path.read_text().split("\n") if line.strip()]


def _status_table():
    """STATUS.md rows -> {task_id: {...}}. The table is the single place that says why a task is not built."""
    f = SETS / "STATUS.md"
    out = {}
    if not f.is_file():
        return out
    for line in f.read_text().split("\n"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 7 and TASK_ID.match(cells[0]):
            out[cells[0]] = {"status": cells[1], "source": cells[3], "license": cells[4], "chance": cells[5], "note": cells[6].replace("`", "")}
    return out


def _results(task):
    out = {}
    if RUNS.is_dir():
        for d in sorted(RUNS.iterdir()):
            f = d / task / "results.jsonl"
            if f.is_file():
                out[d.name] = {r["task_id"]: {k: r.get(k) for k in ("predicted", "probs", "correct", "p_correct", "latency_s", "error")} for r in _jsonl(f)}
    return out


def _task(task_id, status):
    n = int(task_id[1:3])
    area = next(name for name, rng in AREAS if n in rng)
    st = status.get(task_id, {})
    t = {"id": task_id, "n": n, "title": task_id[4:].replace("_", " ").capitalize(), "area": area, "status": st.get("status", "UNKNOWN"),
         "source": st.get("source"), "license": st.get("license"), "chance_note": st.get("chance"), "note": st.get("note"), "items": [], "results": {}}
    md = SETS / f"{task_id}.md"
    t["md"] = md.read_text() if md.is_file() else None
    f = SETS / f"{task_id}.jsonl"
    if f.is_file() and f.stat().st_size:
        rows = _jsonl(f)
        prov = rows[0].get("provenance", {})
        t.update(source=prov.get("source") or t["source"], url=prov.get("url"), license=prov.get("license") or t["license"], label_origin=prov.get("label_origin"))
        t["items"] = [{"id": r["id"], "image": f"imagelab-img/{r['images'][0]}", "question": r["question"], "labels": r["labels"], "expected": r["expected"],
                       "source_id": r["provenance"].get("source_id"), "notes": r["provenance"].get("notes")} for r in rows]
        t["results"] = _results(task_id)
    return t


def payload():
    status = _status_table()
    ids = sorted({p.stem for p in SETS.glob("t[0-9][0-9]_*.md")} | set(status))
    models = sorted({m for d in ([RUNS] if RUNS.is_dir() else []) for m in (p.name for p in d.iterdir() if p.is_dir())})
    return {"areas": [a for a, _ in AREAS], "models": models, "tasks": [_task(t, status) for t in ids if TASK_ID.match(t)]}


def serve_image(handler, rel):
    """rel is '<task>/<file>'; refuses anything that is not a plain image directly under a task folder."""
    parts = rel.split("/")
    p = (IMAGES / parts[0] / parts[1]).resolve() if len(parts) == 2 and all(parts) else None
    if p is None or IMAGES.resolve() not in p.parents or p.suffix.lower() not in TYPES or not p.is_file():
        return handler._send(404, {"error": "not found"})
    handler.send_response(200)
    handler.send_header("Content-Type", TYPES[p.suffix.lower()])
    handler.send_header("Content-Length", str(p.stat().st_size))
    handler.send_header("Cache-Control", "max-age=3600")
    handler.end_headers()
    handler.wfile.write(p.read_bytes())
