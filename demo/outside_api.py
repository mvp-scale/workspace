"""The outside API: standard endpoints other systems can call with a URL and an API key. Standard library only.

    GET  /v1/models                  the models callable right now (ids, names, every accepted alias)
    POST /v1/systemone               a TypeSafe request; "model" may be the real id, the display name or the code name
                                     (Atlas, Atlas CPU ...): it is always resolved to the real model, and the response
                                     names the real id. "bitmob" (aliases BitMob, BITMOB, cpu-engine, cpu, classifier,
                                     Atlas CPU) is BitMob, the CPU classifier. No "model": the first loaded local model
                                     that answers any question (Clef first; never BitMob).
    POST /v1/audio/transcriptions    an audio file (multipart field "file", OpenAI-compatible, or a raw audio body) ->
                                     {"text", "segments": [{speaker, start, end, text}], "duration", "model"}

Keys: OUTSIDE_API_KEYS (comma-separated, in /workspace/.env), sent as "Authorization: Bearer <key>" or "X-API-Key".
A request from this machine (not through a tunnel) needs no key. With no keys configured, outside calls are refused.
Ten wrong keys from one address lock it out for a minute; each key gets OUTSIDE_API_PER_MINUTE calls a minute (120).
Hosted (paid) models are refused unless OUTSIDE_API_ALLOW_HOSTED=1. Secure mode does not apply here: real names.
"""
import email, hmac, json, os, secrets, subprocess, tempfile, threading, time, urllib.error, urllib.request
from pathlib import Path

import backends

ROOT = Path(__file__).resolve().parent.parent
VOICE_WS = "ws://" + os.environ.get("VOICE_ADDR", "127.0.0.1:8200") + "/ws"
VOICE_MODEL = "nvidia/multitalker-parakeet-streaming-0.6b-v1 + nvidia/Nemotron-3-Diarization"
MAX_AUDIO = 100 * 1024 * 1024
_lock = threading.Lock(); _misses = {}; _locked = {}; _buckets = {}


def models():
    """Every callable model: the backends, BitMob (the CPU classifier) included."""
    return dict(backends.BACKENDS)


def aliases():
    facts = {x["id"]: x for x in json.loads((ROOT / "demo" / "models.json").read_text())["models"]}
    mask = json.loads((ROOT / "demo" / "mask.json").read_text())["models"]
    out = {}
    for mid in models():
        names = {mid, facts.get(mid, {}).get("name"), facts.get(mid, {}).get("code"), mask.get(mid, {}).get("name"), mask.get(mid, {}).get("code"),
                 *facts.get(mid, {}).get("aliases", [])}   # older names, kept in models.json (e.g. BitMob was "cpu-engine")
        out[mid] = sorted(n for n in names if n)
    return out


def resolve(name):
    n = str(name).strip().lower()
    return next((mid for mid, al in aliases().items() if n in (a.lower() for a in al)), None)


def _up(mid, cfg):
    if cfg["hosted"]: return bool(cfg["key"])
    for path in ("/health", "/v1/models", "/healthz"):
        try:
            with urllib.request.urlopen(cfg["url"].rstrip("/") + path, timeout=1.5) as r: return r.status < 500
        except urllib.error.HTTPError as e:
            if e.code < 500: return True
        except Exception: pass
    return False


def auth(handler):
    """None when allowed; otherwise (status, body)."""
    if handler._local(): return None
    who = handler.headers.get("Cf-Connecting-Ip") or handler.client_address[0]
    with _lock:
        if _locked.get(who, 0) > time.time(): return 429, {"error": "too many wrong keys from this address; try again in a minute"}
    keys = [k.strip() for k in backends._env("OUTSIDE_API_KEYS").split(",") if k.strip()]
    if not keys: return 403, {"error": "the outside API is not enabled on this server (no OUTSIDE_API_KEYS)"}
    given = handler.headers.get("Authorization", "").removeprefix("Bearer ").strip() or handler.headers.get("X-API-Key", "").strip()
    if not any(hmac.compare_digest(given, k) for k in keys):
        with _lock:
            _misses[who] = [t for t in _misses.get(who, []) if t > time.time() - 60] + [time.time()]
            if len(_misses[who]) >= 10: _locked[who] = time.time() + 60; _misses[who] = []
        return 401, {"error": "missing or wrong API key (Authorization: Bearer <key>)"}
    per = int(backends._env("OUTSIDE_API_PER_MINUTE", "120") or 120)
    with _lock:
        b = _buckets.setdefault(given, [per, time.time()]); b[0] = min(per, b[0] + (time.time() - b[1]) * per / 60); b[1] = time.time()
        if b[0] < 1: return 429, {"error": f"rate limit: {per} calls a minute per key"}
        b[0] -= 1
    return None


def get_models():
    al = aliases(); out = []
    for mid, cfg in models().items():
        if cfg["hosted"] and backends._env("OUTSIDE_API_ALLOW_HOSTED") != "1": continue
        if _up(mid, cfg): out.append({"id": mid, "name": backends.name(mid), "aliases": al[mid],
                                      "kind": "classifier: yes/no questions it has learned" if cfg["library_only"] else "TypeSafe decision model"})
    return 200, {"object": "list", "data": out}


def systemone(raw):
    try: req = json.loads(raw or b"{}"); assert isinstance(req, dict)
    except (ValueError, AssertionError): return 400, {"error": "body must be a JSON TypeSafe request"}
    asked = req.get("model"); ms = models()
    if asked:
        mid = resolve(asked)
        if mid is None: return 404, {"error": f"unknown model {asked!r}; GET /v1/models lists what is callable"}
    else:
        mid = next((m for m, c in ms.items() if not c["hosted"] and not c["library_only"] and _up(m, c)), None)
        if mid is None: return 503, {"error": "no local model is loaded; name one in \"model\""}
    cfg = ms[mid]
    if cfg["hosted"] and backends._env("OUTSIDE_API_ALLOW_HOSTED") != "1": return 403, {"error": "hosted models are not offered on this API"}
    body = {**req, "model": cfg["model"]}
    hdr = {"Content-Type": "application/json", "User-Agent": "jev-demo/0.1", **({"Authorization": f"Bearer {cfg['key']}"} if cfg["key"] else {})}
    t0 = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(cfg["url"].rstrip("/") + "/v1/systemone", json.dumps(body).encode(), hdr), timeout=120) as r:
            status, out = r.status, r.read()
    except urllib.error.HTTPError as e: status, out = e.code, e.read()
    except Exception: return 503, {"error": f"model {mid} is not answering (is it switched on?)"}
    try:
        data = json.loads(out)
        if isinstance(data, dict): data["model"] = mid; data.setdefault("latency_ms", round((time.time() - t0) * 1000))
        return status, data
    except ValueError: return status, out


def transcriptions(raw, ctype):
    if len(raw) > MAX_AUDIO: return 413, {"error": f"audio is limited to {MAX_AUDIO // 2**20} MB"}
    audio, name = raw, "upload"
    if ctype.startswith("multipart/form-data"):
        msg = email.message_from_bytes(b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + raw)
        part = next((p for p in msg.walk() if p.get_param("name", header="content-disposition") == "file"), None)
        if part is None: return 400, {"error": "send the audio as a multipart field named \"file\" (or as a raw audio body)"}
        audio, name = part.get_payload(decode=True), part.get_filename() or "upload"
    if not audio: return 400, {"error": "empty audio"}
    with tempfile.NamedTemporaryFile(suffix="-" + Path(name).name[-60:], delete=True) as f:
        f.write(audio); f.flush()
        try:
            p = subprocess.run([str(ROOT / "voice" / ".venv" / "bin" / "python"), str(ROOT / "voice" / "transcribe_client.py"), f.name, "--url", VOICE_WS, "--timeout", "900"],
                               capture_output=True, text=True, timeout=960)
        except subprocess.TimeoutExpired: return 504, {"error": "transcription took longer than 15 minutes"}
    try: out = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): return 502, {"error": "the voice service gave no answer", "detail": p.stderr[-300:]}
    if "error" in out:
        if "Connect" in out["error"] or "refused" in out["error"].lower(): return 503, {"error": "voice is off: turn it on under Services (or ./service.sh start voice)"}
        return 502, out
    return 200, {**out, "model": VOICE_MODEL}


def new_key():
    return secrets.token_urlsafe(32)
