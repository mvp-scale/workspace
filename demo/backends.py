"""The TypeSafe models this workspace can call, in one place. Standard library only.

Every model is a TypeSafe POST /v1/systemone endpoint: id -> address, key and the "model" label sent with each request.
Addresses come from environment variables with local defaults (ports as in /workspace/service.yaml). Keys come from the
environment, or from /workspace/.env when a process was not started with it (the classifier and the training scripts);
they are only ever sent to the model they belong to, never to a browser.

The console (demo/server.py), the CPU classifier (probes/cpu_engine.py) and the Latent lab training scripts
(probes/latent_*.py) all resolve models here, so a teacher or reader is chosen by name and never hard-wired.

The classifier's teacher (the model whose answers train each question, and its optional backup) is one setting, saved in
data/embed-zs/teacher.json so every process agrees; default: Clef Flash Q4, which taught every question before 16 Oct 2026.
"""
import json, os, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEACHER_FILE = ROOT / "data" / "embed-zs" / "teacher.json"
DEFAULT_TEACHER = "clef-flash-q4km"


def _env(name, default=""):
    if name in os.environ: return os.environ[name]
    try:
        for line in (ROOT / ".env").read_text().splitlines():
            k, _, v = line.strip().partition("=")
            if k.strip().removeprefix("export ").strip() == name: return v.strip().strip("'\"")
    except OSError: pass
    return default


def _local(var, port): return os.environ.get(var, f"http://127.0.0.1:{port}")


# keyed by the same model ids as the leaderboard (codes and names live in demo/models.json), best first
BACKENDS = {
    "jev": {"url": os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai"), "key": _env("TYPESAFE_API_KEY"), "hosted": True},
    "cygnet": {"url": _local("CYGNET_URL", 8016), "key": ""},
    "winnow": {"url": _local("WINNOW_URL", 8091), "key": "", "model": "Winnow-12B"},
    "semif": {"url": _local("SEMIF_URL", 8012), "key": ""},
    "kev-4b": {"url": _local("KEV4_URL", 8010), "key": ""},
    "so1": {"url": _local("SO1_URL", 8013), "key": ""},
    "laya": {"url": _local("LAYA_URL", 8014), "key": ""},
    "kev-0.8b": {"url": _local("KEV08_URL", 8011), "key": ""},
    "jeff": {"url": _local("JEFF_URL", 8000), "key": _env("JEFF_API_KEYS", "devkey").split(",")[0]},
    "kev-0.5b": {"url": _local("KEV05_URL", 8009), "key": ""},
    "verdict": {"url": _local("VERDICT_URL", 8015), "key": ""},
    "clef-flash-q4km": {"url": _local("CLEF_Q4KM_URL", 8018), "key": ""},
    "clef-flash-q2k": {"url": _local("CLEF_Q2K_URL", 8019), "key": ""},
    "clef-flash": {"url": _local("CLEF_FLASH_URL", 8017), "key": ""},
}
for _b in BACKENDS.values(): _b.setdefault("model", "jev-latest"); _b.setdefault("hosted", False)


def name(bid):
    """Display name from demo/models.json (pages never show raw ids)."""
    try: return next(m["name"] for m in json.loads((ROOT / "demo" / "models.json").read_text())["models"] if m["id"] == bid)
    except (OSError, StopIteration, KeyError, ValueError): return bid


def ask(bid, state, questions, timeout=60):
    """One /v1/systemone call to model `bid`; returns its answers dict. Raises on any failure (callers retry or skip)."""
    b = BACKENDS[bid]
    hdr = {"Content-Type": "application/json", "User-Agent": "jev-demo/0.1", **({"Authorization": f"Bearer {b['key']}"} if b["key"] else {})}
    body = json.dumps({"state": state, "model": b["model"], "questions": questions}).encode()
    with urllib.request.urlopen(urllib.request.Request(b["url"].rstrip("/") + "/v1/systemone", body, hdr), timeout=timeout) as r:
        return json.load(r)["answers"]


def teacher():
    try: t = json.loads(TEACHER_FILE.read_text()).get("teacher")
    except (OSError, ValueError): t = None
    return t if t in BACKENDS else DEFAULT_TEACHER


def set_teacher(bid):
    if bid not in BACKENDS: raise KeyError(bid)
    TEACHER_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = TEACHER_FILE.with_suffix(".tmp"); tmp.write_text(json.dumps({"teacher": bid})); tmp.replace(TEACHER_FILE)
