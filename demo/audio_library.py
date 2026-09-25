"""A small read-only audio library for the Flow lab: files in <repo>/data/audio (git-ignored, third-party audio stays out of the repo).

  GET /api/audio-files      -> {files: [{file, size, duration}]}
  GET /audio/<file>         -> the file, with HTTP Range support so the browser player can seek
"""
import json
import subprocess
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "data" / "audio"
TYPES = {".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg", ".webm": "audio/webm", ".flac": "audio/flac", ".aac": "audio/aac"}
_dur = {}


def _duration(p: Path):
    key = (p.name, p.stat().st_mtime_ns)
    if key not in _dur:
        try:
            out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True, timeout=10).stdout.strip()
            _dur[key] = round(float(out), 1)
        except Exception:
            _dur[key] = None
    return _dur[key]


def list_files():
    files = []
    if DIR.is_dir():
        for p in sorted(DIR.iterdir()):
            if p.is_file() and p.suffix.lower() in TYPES:
                files.append({"file": p.name, "size": p.stat().st_size, "duration": _duration(p)})
    return {"files": files}


def serve(h, name: str):
    """h is the http.server handler; writes the whole response (200 or 206)."""
    from urllib.parse import unquote
    p = (DIR / unquote(name)).resolve()
    if p.parent != DIR.resolve() or not p.is_file() or p.suffix.lower() not in TYPES:
        raw = json.dumps({"error": "not found"}).encode()
        h.send_response(404); h.send_header("Content-Type", "application/json"); h.send_header("Content-Length", str(len(raw))); h.end_headers(); h.wfile.write(raw); return
    size, start, end, code = p.stat().st_size, 0, p.stat().st_size - 1, 200
    rng = h.headers.get("Range", "")
    if rng.startswith("bytes="):
        a, _, b = rng[6:].partition("-")
        try:
            start = int(a) if a else max(0, size - int(b)); end = int(b) if (a and b) else end
            end = min(end, size - 1); code = 206
        except ValueError:
            start, end, code = 0, size - 1, 200
    if start > end or start >= size:
        h.send_response(416); h.send_header("Content-Range", f"bytes */{size}"); h.end_headers(); return
    h.send_response(code)
    h.send_header("Content-Type", TYPES[p.suffix.lower()]); h.send_header("Accept-Ranges", "bytes"); h.send_header("Content-Length", str(end - start + 1))
    if code == 206:
        h.send_header("Content-Range", f"bytes {start}-{end}/{size}")
    h.end_headers()
    with open(p, "rb") as f:
        f.seek(start); left = end - start + 1
        while left > 0:
            chunk = f.read(min(1 << 20, left))
            if not chunk:
                break
            try:
                h.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                return
            left -= len(chunk)
