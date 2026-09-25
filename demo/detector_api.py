"""Detector files and AI-drafted detectors for the Flow lab (demo/flow-lab.html). Stdlib + optional PyYAML.

  GET  /api/detector-files                  -> [{file, name, description, count}]        (demo/detectors/*.json|yaml|yml)
  GET  /api/detector-file?file=NAME         -> normalised document {name, description, detectors:[...]}
  POST /api/detector-save   {file, doc, overwrite?}  -> writes demo/detectors/<file>.json
  POST /api/detector-draft  {name, context?, icons} -> one detector drafted from just a name
  POST /api/detector-suggest {context, n, existing, icons} -> several detector proposals

A detector is either {"library": "<id of a validated detector>"} or a custom one:
  {name, what, example?, scope: person|call, icon?, key?}   (custom = your own wording, unvalidated)
The AI calls use ANTHROPIC_API_KEY from the environment (server side only), a small model and a per-process cap.
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DIR = Path(__file__).parent / "detectors"
MODEL = os.environ.get("DETECTOR_AI_MODEL", "claude-haiku-4-5-20251001")
AI_CAP = int(os.environ.get("DETECTOR_AI_CAP", "100"))
MAX_DETECTORS, MAX_BODY = 40, 65536
LIBRARY_IDS = {"manipulation", "phishing", "sarcasm", "threat", "anger", "fear", "politeness", "urgency", "scarcity", "social_proof", "persuasion"}
_ai_used = 0

SYSTEM = """You design "detectors" for a tool that scores short windows of transcribed speech (20-40 words from one speaker).
A detector is ONE yes/no question a model answers about the words. Good detectors:
- describe one observable behaviour in the words, phrased "the speaker <does X>" (e.g. "the speaker asks the other person to keep the call secret");
- are specific enough that a stranger could say yes or no from a single window of speech;
- do not depend on tone of voice, hidden intent, or truth ("is lying" is bad; "the speaker makes a claim of authority" is good);
- are not stacked ("angry and threatening" is two detectors) and not vague ("is bad").
Fields: name (1-3 words, Title Case), what (one sentence starting "the speaker"), example (one short realistic sentence someone might say that matches), scope ("person" for one speaker's words, "call" only if it needs the whole conversation), icon (pick one from the allowed list, best match).
Reply with JSON only, no prose, no code fences."""


def _ai(user: str, max_tokens: int):
    global _ai_used
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("no ANTHROPIC_API_KEY in the demo server's environment")
    if _ai_used >= AI_CAP:
        raise RuntimeError(f"AI draft cap of {AI_CAP} calls per server run reached")
    _ai_used += 1
    body = {"model": MODEL, "max_tokens": max_tokens, "system": SYSTEM, "messages": [{"role": "user", "content": user}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), method="POST",
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Anthropic API {e.code}: {e.read()[:200].decode('utf-8', 'replace')}")
    return "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")


def _json_from(text: str):
    m = re.search(r"[\[{]", text)
    if not m:
        raise ValueError("no JSON in the reply")
    dec = json.JSONDecoder()
    return dec.raw_decode(text[m.start():])[0]


def clean(d: dict, icons):
    """Validate one custom detector; returns a normalised dict or None."""
    if not isinstance(d, dict):
        return None
    if "library" in d:
        return {"library": d["library"]} if d["library"] in LIBRARY_IDS else None
    name, what = str(d.get("name", "")).strip()[:40], str(d.get("what", "")).strip()[:240]
    if not name or len(what) < 8:
        return None
    out = {"name": name, "what": what, "example": str(d.get("example", "")).strip()[:240], "scope": "call" if d.get("scope") == "call" else "person"}
    if d.get("icon") and (not icons or d["icon"] in icons):
        out["icon"] = d["icon"]
    if d.get("key") and re.fullmatch(r"[a-z0-9_]{1,40}", str(d["key"])):
        out["key"] = d["key"]
    return out


def _template(name: str) -> dict:
    return {"name": name[:40], "what": f'the speaker is expressing or doing "{name.strip()[:60]}"', "example": "", "scope": "person"}


def _doc(raw, fname):
    if not isinstance(raw, dict) or not isinstance(raw.get("detectors"), list):
        raise ValueError("a detector file needs a top-level `detectors:` list")
    dets = [c for c in (clean(x, None) for x in raw["detectors"][:MAX_DETECTORS]) if c]
    return {"name": str(raw.get("name") or fname)[:60], "description": str(raw.get("description", ""))[:400], "detectors": dets,
            "skipped": len(raw["detectors"][:MAX_DETECTORS]) - len(dets)}


def _load(fname):
    p = (DIR / fname).resolve()
    if p.parent != DIR.resolve() or not p.is_file() or p.suffix not in (".json", ".yaml", ".yml"):
        raise FileNotFoundError(fname)
    txt = p.read_text()
    if p.suffix == ".json":
        raw = json.loads(txt)
    else:
        import yaml
        raw = yaml.safe_load(txt)
    return _doc(raw, p.stem)


def handle_get(path, query):
    q = dict(urllib.parse.parse_qsl(query))
    if path == "/api/detector-files":
        out = []
        for p in sorted(DIR.glob("*")):
            if p.suffix in (".json", ".yaml", ".yml"):
                try:
                    d = _load(p.name)
                    out.append({"file": p.name, "name": d["name"], "description": d["description"], "count": len(d["detectors"])})
                except Exception as e:
                    out.append({"file": p.name, "name": p.name, "description": f"could not read: {e}", "count": 0})
        return 200, {"files": out, "ai": bool(os.environ.get("ANTHROPIC_API_KEY")), "ai_model": MODEL, "ai_used": _ai_used, "ai_cap": AI_CAP}
    if path == "/api/detector-file":
        try:
            return 200, _load(q.get("file", ""))
        except FileNotFoundError:
            return 404, {"error": "no such detector file"}
        except Exception as e:
            return 400, {"error": f"could not read that file: {e}"}
    return None


def handle_post(path, body: bytes):
    if len(body) > MAX_BODY:
        return 413, {"error": "too large"}
    try:
        req = json.loads(body or b"{}")
        assert isinstance(req, dict)
    except (ValueError, AssertionError):
        return 400, {"error": "need a JSON object"}
    icons = [i for i in req.get("icons", []) if isinstance(i, str)][:60]
    if path == "/api/detector-save":
        f = re.sub(r"[^A-Za-z0-9_-]", "-", str(req.get("file", "")).rsplit(".", 1)[0]).strip("-")[:50]
        if not f:
            return 400, {"error": "give the file a name"}
        try:
            doc = _doc(req.get("doc"), f)
        except ValueError as e:
            return 400, {"error": str(e)}
        target = DIR / (f + ".json")
        if target.exists() and not req.get("overwrite"):
            return 409, {"error": f"{target.name} already exists", "file": target.name}
        DIR.mkdir(exist_ok=True)
        doc.pop("skipped", None)
        target.write_text(json.dumps(doc, indent=2) + "\n")
        return 200, {"file": target.name, "count": len(doc["detectors"])}
    if path == "/api/detector-draft":
        name = str(req.get("name", "")).strip()[:60]
        if not name:
            return 400, {"error": "need a name"}
        ctx = str(req.get("context", "")).strip()[:300]
        try:
            txt = _ai(f'Design one detector named "{name}".' + (f" The conversations are: {ctx}." if ctx else "")
                      + f' Allowed icons: {", ".join(icons)}. Reply as JSON: {{"name":..., "what":..., "example":..., "scope":..., "icon":...}}', 400)
            d = clean(_json_from(txt), icons)
            if d:
                d["name"] = d["name"] if len(d["name"]) <= 40 else name
                return 200, {"detector": d, "ai": True, "model": MODEL}
            raise ValueError("the draft was not usable")
        except Exception as e:
            return 200, {"detector": _template(name), "ai": False, "note": f"AI draft unavailable ({e}); used a plain template, edit it before adding"}
    if path == "/api/detector-suggest":
        ctx = str(req.get("context", "")).strip()[:400]
        n = max(1, min(int(req.get("n", 8) or 8), 12))
        existing = [str(x)[:40] for x in req.get("existing", [])][:40]
        try:
            txt = _ai(f"Suggest {n} distinct detectors for conversations like: {ctx or 'general conversations between people'}. "
                      f"Do not repeat these existing ones: {', '.join(existing) or 'none'}. Allowed icons: {', '.join(icons)}. "
                      'Reply as a JSON list of {"name","what","example","scope","icon"}.', 1500)
            raw = _json_from(txt)
            raw = raw.get("detectors", []) if isinstance(raw, dict) else raw
            dets = [c for c in (clean(x, icons) for x in raw) if c and "library" not in c][:n]
            if not dets:
                raise ValueError("no usable suggestions")
            return 200, {"detectors": dets, "ai": True, "model": MODEL}
        except Exception as e:
            return 200, {"detectors": [], "ai": False, "note": f"AI suggestions unavailable ({e})"}
    return None
