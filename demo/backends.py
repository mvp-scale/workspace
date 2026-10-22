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


# keyed by the same model ids as the leaderboard (codes and names live in demo/models.json). Order = how pickers and the
# Models panel list them: the Clef Flash family first (our go-to model since Oct 2026), then the rest best first.
BACKENDS = {
    "clef-flash-q4km": {"url": _local("CLEF_Q4KM_URL", 8018), "key": ""},
    "clef-flash": {"url": _local("CLEF_FLASH_URL", 8017), "key": ""},
    "clef-flash-q2k": {"url": _local("CLEF_Q2K_URL", 8019), "key": ""},
    "clef-flash-nvfp4": {"url": _local("CLEF_NVFP4_URL", 8038), "key": ""},   # Clef Flash Fast: vLLM, on demand (benchmark port)
    "jev": {"url": os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai"), "key": _env("TYPESAFE_API_KEY"), "hosted": True,
            "model": os.environ.get("JEV_MODEL", "jev-1.14.0")},      # pinned: jev-latest still resolves to 1.13.0 (checked 2026-10-19); labels record the version used
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
    # BitMob: our CPU classifier (probes/cpu_engine.py, the "classifier" service). It answers every question, but only learned
    # ones are trained (the rest are labelled "untrained guess", near chance), so it is library_only: never a teacher, never a World engine reader, not offered where pages send
    # arbitrary questions; it shows in the Models panel and on the outside API.
    "bitmob": {"url": _local("CPU_ENGINE_URL", 8020), "key": "", "model": "bitmob", "library_only": True, "health": "/health"},
    # BitMob as a World-engine reader (D-0037, newsreader/bitmob/reader/engine_reader.py, :8021): our fine-tuned CPU readers answer the engine's gate, type, scope, recent, condition, topic and country
    # questions; library_only (so it is never a teacher, never in Auto, never offered where pages send arbitrary questions) but engine_reader (so the World engine's Reader picker can pin it).
    # The model label picks the mode: "bitmob-clef" sends expected-impact, severity and So-what questions to local Clef; "bitmob-cpu" refuses them (the engine skips them).
    "bitmob-cpu": {"url": _local("BITMOB_READER_URL", 8021), "key": "", "model": "bitmob-cpu", "library_only": True, "engine_reader": True, "cpu_only": True, "health": "/health"},
}
for _b in BACKENDS.values(): _b.setdefault("model", "jev-latest"); _b.setdefault("hosted", False); _b.setdefault("library_only", False); _b.setdefault("engine_reader", False); _b.setdefault("cpu_only", False)


def full_models():
    """Ids of the models that answer any TypeSafe question (every backend except library-only ones such as BitMob)."""
    return [b for b, v in BACKENDS.items() if not v["library_only"]]


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
    return t if t in BACKENDS and not BACKENDS[t]["library_only"] else DEFAULT_TEACHER


def set_teacher(bid):
    if bid not in BACKENDS or BACKENDS[bid]["library_only"]: raise KeyError(bid)
    TEACHER_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = TEACHER_FILE.with_suffix(".tmp"); tmp.write_text(json.dumps({"teacher": bid})); tmp.replace(TEACHER_FILE)
