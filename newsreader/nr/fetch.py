"""Getting the article: one plain page request per story (no login, no cookies, no browser), robots.txt honoured, one request per site at a time with a gap.
The page becomes Markdown (Trafilatura). Anything odd still reaches the reader at the depth it has: the feed's teaser when the full text cannot be had."""
import os, time, socket, threading, urllib.request, urllib.error, urllib.robotparser, urllib.parse
import trafilatura
from . import store
from .sources import UA

socket.setdefaulttimeout(20)
HOST_GAP = float(os.environ.get("NR_HOST_GAP", "1.5"))     # seconds between two requests to the same site
FULL_WORDS = 150                                           # below this the extract is not treated as the article
_robots, _rlock = {}, threading.Lock()
_next_ok, _busy, _hlock = {}, set(), threading.Lock()


def allowed(url):
    p = urllib.parse.urlsplit(url); base = f"{p.scheme}://{p.netloc}"
    with _rlock: hit = _robots.get(base)
    if hit and time.time() - hit[1] < 86400: rp = hit[0]
    else:                                        # read outside the lock: one slow site does not hold up the others
        rp = urllib.robotparser.RobotFileParser(base + "/robots.txt")
        try: rp.read()
        except Exception: rp = None              # unreachable robots.txt: treated as no rules, like the standard says for 4xx
        with _rlock: _robots[base] = (rp, time.time())
    return True if rp is None else rp.can_fetch(UA, url)


def busy_hosts():
    with _hlock: return set(_busy) | {h for h, t in _next_ok.items() if t > time.time()}


def _mark(host, on):
    with _hlock:
        if on: _busy.add(host)
        else: _busy.discard(host); _next_ok[host] = time.time() + HOST_GAP


def one(item):
    """Fetch and extract one story; always ends with the story ready (full or teaser) or dropped."""
    host = item["host"]; _mark(host, True)
    try:
        if not allowed(item["url"]): return _teaser(item, "robots")
        try:
            r = urllib.request.urlopen(urllib.request.Request(item["url"], headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"}), timeout=30)
            ctype = r.headers.get("Content-Type", ""); raw = r.read(8_000_000)
        except urllib.error.HTTPError as e:
            return _teaser(item, "paywall_or_blocked" if e.code in (401, 402, 403, 451) else f"http_{e.code}")
        except Exception as e:
            return _teaser(item, f"fetch_error_{type(e).__name__}")
        if "html" not in ctype and not raw.lstrip()[:200].lower().startswith((b"<!doctype html", b"<html")):
            return _teaser(item, "not_html")
        t0 = time.perf_counter()
        md = trafilatura.extract(raw.decode("utf-8", "replace"), url=item["url"], output_format="markdown", include_comments=False, include_tables=True) or ""
        ms = round((time.perf_counter() - t0) * 1000, 1); words = len(md.split())
        if words >= FULL_WORDS: store.ready(item["id"], "full", md[:60000], words, ms)
        else: _teaser(item, "short_extract", ms)      # video pages, live blogs, galleries, consent walls
    finally:
        _mark(host, False)


def _teaser(item, reason, ms=None):
    t = (item.get("teaser") or "").strip()
    if item.get("title"): store.ready(item["id"], "teaser", t or None, len(t.split()), ms, reason)
    else: store.drop(item["id"], reason)
