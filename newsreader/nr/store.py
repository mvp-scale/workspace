"""The queue: one SQLite file (WAL), one row per story. States: new (needs fetching) -> ready (leaseable; depth full or teaser) -> done; or dropped (reason)."""
import os, re, time, sqlite3, hashlib, threading, unicodedata

DB = os.environ.get("NR_DB", "/workspace/data/newsreader/queue.sqlite")
SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY, url TEXT UNIQUE, feed TEXT, source TEXT, country TEXT, region TEXT, lang TEXT, category TEXT,
  title TEXT, published TEXT, image TEXT, teaser TEXT, body TEXT, depth TEXT, state TEXT, reason TEXT,
  words INTEGER, extract_ms REAL, found_at REAL, ready_at REAL, leased_until REAL, done_at REAL, story TEXT);
CREATE INDEX IF NOT EXISTS items_state ON items(state, published);
CREATE INDEX IF NOT EXISTS items_found ON items(found_at);
CREATE INDEX IF NOT EXISTS items_done ON items(done_at);
CREATE TABLE IF NOT EXISTS served (kind TEXT, key TEXT, at REAL, PRIMARY KEY (kind, key));
CREATE TABLE IF NOT EXISTS feeds (id TEXT PRIMARY KEY, etag TEXT, modified TEXT, last_poll REAL, last_status TEXT, items_seen INTEGER DEFAULT 0, errors INTEGER DEFAULT 0);
"""
_local = threading.local()


def db():
    """One connection per thread; WAL lets the poller, the fetchers and the API work at once."""
    c = getattr(_local, "c", None)
    if c is None:
        os.makedirs(os.path.dirname(DB), exist_ok=True)
        c = sqlite3.connect(DB, timeout=30, isolation_level=None); c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA synchronous=NORMAL"); c.executescript(SCHEMA); _local.c = c
    return c


def normalise(title):
    t = unicodedata.normalize("NFKC", title or "").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()


def story_id(title, source, day):
    """The reuse key from the service design: sha256(normalised title | source | day)."""
    return hashlib.sha256(f"{normalise(title)}|{(source or '').strip().lower()}|{(day or '')[:10]}".encode()).hexdigest()


def story_key(title):
    """Title only: links the same wire story across sources."""
    return hashlib.sha256(normalise(title).encode()).hexdigest()[:16]


def add(item):
    """Insert a story found in a feed; returns True if it is new (same id or same link = already known)."""
    item = dict(item); item.setdefault("found_at", time.time()); item["id"] = story_id(item["title"], item["source"], item.get("published"))
    item["story"] = story_key(item["title"]); cols = ",".join(item); qs = ",".join("?" * len(item))
    cur = db().execute(f"INSERT OR IGNORE INTO items ({cols}) VALUES ({qs})", list(item.values())); return cur.rowcount == 1


def claim_new(limit, busy_hosts):
    """Oldest unfetched stories whose site is not cooling down (per-site politeness is decided by the caller)."""
    rows = db().execute("SELECT id, url, title, teaser, source FROM items WHERE state='new' ORDER BY found_at LIMIT ?", (limit * 20,)).fetchall()
    out, hosts = [], set(busy_hosts)
    for r in rows:
        h = re.sub(r"^https?://([^/]+).*$", r"\1", r["url"] or "")
        if h in hosts: continue
        hosts.add(h); out.append(dict(r, host=h))
        if len(out) == limit: break
    for r in out: db().execute("UPDATE items SET state='fetching' WHERE id=? AND state='new'", (r["id"],))
    return out


def ready(id_, depth, body, words, ms, reason=None):
    db().execute("UPDATE items SET state='ready', depth=?, body=?, words=?, extract_ms=?, reason=?, ready_at=? WHERE id=?", (depth, body, words, ms, reason, time.time(), id_))


def drop(id_, reason):
    db().execute("UPDATE items SET state='dropped', reason=?, ready_at=? WHERE id=?", (reason, time.time(), id_))


def lease(n=1, seconds=180, order="fair"):
    """Hand out ready stories (with their text) for reading; a lease that is not acked returns them to the queue.
    order=fair (default): the region served longest ago, then its outlet served longest ago, then that outlet's newest story, so no one region
    or outlet fills the feed. order=newest: newest first across everything. order=fifo: oldest found first."""
    c, now = db(), time.time()
    c.execute("BEGIN IMMEDIATE")
    try:
        c.execute("UPDATE items SET state='ready', leased_until=NULL WHERE state='leased' AND leased_until < ?", (now,))
        rows = []
        if order == "fair":
            for _ in range(int(n)):
                last = {(k, key): at for k, key, at in c.execute("SELECT kind, key, at FROM served")}
                pool = c.execute("SELECT DISTINCT region, source FROM items WHERE state='ready'").fetchall()
                if not pool: break
                region = min({r[0] for r in pool}, key=lambda g: (last.get(("region", g or ""), 0), g or ""))
                source = min({r[1] for r in pool if r[0] == region}, key=lambda s_: (last.get(("source", s_), 0), s_))
                r = c.execute("SELECT * FROM items WHERE state='ready' AND source=? ORDER BY published DESC, found_at DESC LIMIT 1", (source,)).fetchone()
                c.execute("UPDATE items SET state='leased', leased_until=? WHERE id=?", (now + seconds, r["id"]))
                for k, key in (("region", region or ""), ("source", source)): c.execute("INSERT INTO served VALUES (?,?,?) ON CONFLICT(kind, key) DO UPDATE SET at=excluded.at", (k, key, time.time()))
                rows.append(dict(r))
        else:
            o = "published DESC, found_at DESC" if order == "newest" else "found_at"
            rows = [dict(r) for r in c.execute(f"SELECT * FROM items WHERE state='ready' ORDER BY {o} LIMIT ?", (int(n),)).fetchall()]
            for r in rows: c.execute("UPDATE items SET state='leased', leased_until=? WHERE id=?", (now + seconds, r["id"]))
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK"); raise
    return rows


def ack(ids):
    now = time.time()
    for i in ids: db().execute("UPDATE items SET state='done', done_at=?, leased_until=NULL WHERE id=?", (now, i))
    return len(ids)


def purge(keep_days):
    """Article text is kept locally for a short time only; metadata stays."""
    cut = time.time() - keep_days * 86400
    return db().execute("UPDATE items SET body=NULL WHERE body IS NOT NULL AND found_at < ?", (cut,)).rowcount


def stats():
    c, now = db(), time.time()
    by_state = {r[0]: r[1] for r in c.execute("SELECT state, COUNT(*) FROM items GROUP BY state")}
    by_depth = {r[0]: r[1] for r in c.execute("SELECT depth, COUNT(*) FROM items WHERE depth IS NOT NULL GROUP BY depth")}
    reasons = {r[0]: r[1] for r in c.execute("SELECT reason, COUNT(*) FROM items WHERE reason IS NOT NULL GROUP BY reason")}
    rate = lambda col: c.execute(f"SELECT COUNT(*) FROM items WHERE {col} > ?", (now - 300,)).fetchone()[0] / 300
    ms = [r[0] for r in c.execute("SELECT extract_ms FROM items WHERE extract_ms IS NOT NULL ORDER BY ready_at DESC LIMIT 500")]
    feeds = c.execute("SELECT COUNT(*), SUM(last_status='ok'), SUM(errors > 0) FROM feeds").fetchone()
    fetched = by_depth.get("full", 0) + by_depth.get("teaser", 0)
    return {"items": sum(by_state.values()), "by_state": by_state, "by_depth": by_depth, "reasons": reasons,
            "found_per_s": round(rate("found_at"), 3), "extracted_per_s": round(rate("ready_at"), 3), "read_per_s": round(rate("done_at"), 3),
            "backlog": by_state.get("ready", 0) + by_state.get("leased", 0), "to_fetch": by_state.get("new", 0) + by_state.get("fetching", 0),
            "full_text_share": round(by_depth.get("full", 0) / fetched, 3) if fetched else None,
            "extract_ms_median": sorted(ms)[len(ms) // 2] if ms else None, "feeds": {"total": feeds[0], "ok": feeds[1] or 0, "with_errors": feeds[2] or 0}}
