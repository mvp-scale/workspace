"""Download a file from the Hugging Face Hub with the standard library: resumable, checksummed, no extra packages.

Colab images differ in what they ship, so nothing here needs `huggingface_hub`. A download goes to `<folder>/.partial/<name>.incomplete`
and is moved to `<folder>/<name>` only when it is complete and its SHA-256 matches the one the Hub reports, so an interrupted run leaves
no corrupt model behind and the next attempt continues from the bytes already there.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PARTIAL = ".partial"
CHUNK = 1 << 20
SHA256 = re.compile(r"[0-9a-f]{64}")


def url_for(repo: str, name: str, revision: str = "main") -> str:
    base = os.environ.get("JEVGW_HF_BASE", "https://huggingface.co")  # overridden only in tests
    return f"{base}/{repo}/resolve/{revision}/{urllib.parse.quote(name)}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


class _DropAuthAcrossHosts(urllib.request.HTTPRedirectHandler):
    """Hugging Face redirects to a signed CDN URL, which rejects a request that also carries our token: send it only to the first host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and urllib.parse.urlsplit(newurl).netloc != urllib.parse.urlsplit(req.full_url).netloc:
            new.remove_header("Authorization")
        return new


def _open(url: str, have: int):
    headers = {"User-Agent": "jevgw"}
    if token := os.environ.get("HF_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    if have:
        headers["Range"] = f"bytes={have}-"
    opener = urllib.request.build_opener(_DropAuthAcrossHosts)
    return opener.open(urllib.request.Request(url, headers=headers), timeout=60)


def _attempt(url: str, part: Path, final: Path) -> None:
    have = part.stat().st_size if part.exists() else 0
    expected = None
    try:
        response = _open(url, have)
    except urllib.error.HTTPError as err:
        if err.code != 416:  # 416: the partial file is already the whole file
            raise
        response = None
    if response is not None:
        if response.status == 200:  # the server ignored the range: start over
            have = 0
        etag = (response.headers.get("X-Linked-Etag") or "").strip('"')
        expected = etag if SHA256.fullmatch(etag) else None
        promised, got = int(response.headers.get("Content-Length") or -1), 0
        with response, open(part, "ab" if have else "wb") as out:
            while chunk := response.read(CHUNK):
                out.write(chunk)
                got += len(chunk)
        if (
            promised >= 0 and got != promised
        ):  # http.client does not raise when a connection closes early; the partial file is kept to resume
            raise OSError(f"connection dropped after {got} of {promised} bytes")
    if expected and _sha256(part) != expected:
        part.unlink()
        raise OSError(f"{final.name}: checksum mismatch after download; the partial file was deleted")
    part.replace(final)


def download(repo: str, name: str, folder: str | Path, tries: int = 3, revision: str = "main", log=print) -> str:
    """Download `name` from `repo` into `folder`. Returns the path. Safe to call again: a complete file is kept, a partial one resumed."""
    folder = Path(folder)
    final, part = folder / name, folder / PARTIAL / f"{name}.incomplete"
    if final.exists():
        return str(final)
    part.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, tries + 1):
        try:
            _attempt(url_for(repo, name, revision), part, final)
            return str(final)
        except (OSError, urllib.error.URLError) as err:  # HTTPError is a URLError; includes dropped connections and timeouts
            if isinstance(err, urllib.error.HTTPError) and err.code in (401, 403, 404):
                raise RuntimeError(f"{repo}/{name}: HTTP {err.code} (does the file exist, and is the repo public?)") from None
            if attempt == tries:
                raise
            log(f"download of {name} failed ({type(err).__name__}: {err}); retrying ({attempt}/{tries - 1})")
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")
