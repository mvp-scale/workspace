"""The newsreader service: polls the catalogue, fetches and extracts in the background, and hands stories to a reader (the World engine) over HTTP.
  GET  /health                     {"ok": true}
  GET  /stats                      queue counts, rates (per second over the last 5 minutes), full-text share, extraction time, feed health
  GET  /next?n=1&lease=180&order=fair|newest|fifo   lease ready stories, with their Markdown (fair: rotate regions, then outlets)
  POST /ack {"ids": [...]}         mark leased stories read
  GET  /items?limit=50             recent stories, metadata only
  POST /poll                       poll every feed now
Run: .venv/bin/python -m nr.serve   (env: NR_PORT, NR_DB, NR_CATALOGUE, NR_WORKERS, NR_POLL_S, NR_KEEP_DAYS, NR_HOST_GAP)"""
import os, json, time, threading, urllib.parse, concurrent.futures as cf
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from . import store, sources, fetch

PORT, WORKERS = int(os.environ.get("NR_PORT", "8140")), int(os.environ.get("NR_WORKERS", "8"))
POLL_S, KEEP_DAYS = float(os.environ.get("NR_POLL_S", "900")), float(os.environ.get("NR_KEEP_DAYS", "7"))
STATE = {"started": time.time(), "last_poll": None, "polls": 0, "poll_now": threading.Event()}


def poller():
    while True:
        feeds = sources.catalogue(); t0 = time.time()
        with cf.ThreadPoolExecutor(16) as ex: res = list(ex.map(sources.poll, feeds))
        STATE.update(last_poll=time.time(), polls=STATE["polls"] + 1, last_poll_s=round(time.time() - t0, 1), last_new=sum(n for n, _ in res), feeds=len(feeds))
        print(f"poll: {len(feeds)} feeds, {STATE['last_new']} new stories, {sum(s != 'ok' for _, s in res)} feed errors, {STATE['last_poll_s']} s", flush=True)
        store.purge(KEEP_DAYS); STATE["poll_now"].wait(POLL_S); STATE["poll_now"].clear()


def fetcher():
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        running = set()
        while True:
            running = {f for f in running if not f.done()}
            free = WORKERS - len(running)
            todo = store.claim_new(free, fetch.busy_hosts()) if free else []
            for it in todo: running.add(ex.submit(fetch.one, it))
            time.sleep(0.05 if todo else 0.5)


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj, default=str).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path); q = dict(urllib.parse.parse_qsl(u.query))
        if u.path == "/health": return self._send(200, {"ok": True})
        if u.path == "/stats": return self._send(200, {**store.stats(), "uptime_s": round(time.time() - STATE["started"]), "poll": {k: STATE.get(k) for k in ("last_poll", "polls", "last_poll_s", "last_new", "feeds")}, "workers": WORKERS})
        if u.path == "/next":
            rows = store.lease(min(50, int(q.get("n", 1))), float(q.get("lease", 180)), q.get("order", "fair"))
            return self._send(200, {"items": [{k: r[k] for k in ("id", "story", "url", "source", "country", "region", "lang", "category", "title", "published", "image", "teaser", "body", "depth", "reason", "words")} for r in rows]})
        if u.path == "/items":
            rows = store.db().execute("SELECT id, source, country, title, published, depth, reason, words, state FROM items ORDER BY found_at DESC LIMIT ?", (min(500, int(q.get("limit", 50))),)).fetchall()
            return self._send(200, {"items": [dict(r) for r in rows]})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        u = urllib.parse.urlsplit(self.path)
        try: req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
        except ValueError: return self._send(400, {"error": "bad json"})
        if u.path == "/ack": return self._send(200, {"acked": store.ack([str(i) for i in req.get("ids", [])][:500])})
        if u.path == "/poll": STATE["poll_now"].set(); return self._send(200, {"ok": True})
        self._send(404, {"error": "not found"})

    def log_message(self, *a): pass


if __name__ == "__main__":
    store.db(); store.db().execute("UPDATE items SET state='new' WHERE state='fetching'")      # fetches cut short by a restart start over
    threading.Thread(target=poller, daemon=True).start(); threading.Thread(target=fetcher, daemon=True).start()
    print(f"newsreader on 127.0.0.1:{PORT}, db {store.DB}, {len(sources.catalogue())} feeds in the catalogue", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
