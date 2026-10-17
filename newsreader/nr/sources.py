"""Finding stories: RSS/Atom feeds (feedparser, with ETag/Last-Modified) and news sitemaps (for sites without a feed). No pages are fetched here."""
import csv, os, re, time, html, socket, urllib.request, xml.etree.ElementTree as ET
import feedparser, trafilatura
from . import store

socket.setdefaulttimeout(20)
UA = os.environ.get("NR_UA", "Mozilla/5.0 (compatible; WorldEngineReader/0.1; local research)")
CATALOGUE = os.environ.get("NR_CATALOGUE", os.path.join(os.path.dirname(__file__), "..", "catalogue.csv"))
RSSHUB = os.environ.get("NR_RSSHUB", "http://127.0.0.1:1200")
FULL_WORDS = 300          # a feed item with this much text is the article itself; no fetch needed


def catalogue():
    rows = [r for r in csv.DictReader(open(CATALOGUE)) if r["url"] and not r["id"].startswith("#")]
    for r in rows:
        if r["kind"] == "rsshub": r["url"] = RSSHUB.rstrip("/") + "/" + r["url"].lstrip("/")
    return rows


def text_of(fragment):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(fragment or ""))).strip()


def image_of(e):
    for k in ("media_content", "media_thumbnail"):
        for m in e.get(k) or []:
            if m.get("url"): return m["url"]
    for l in e.get("links") or []:
        if l.get("rel") == "enclosure" and (l.get("type") or "").startswith("image") and l.get("href"): return l["href"]
    m = re.search(r'<img[^>]+src="([^"]+)"', (e.get("summary") or "") + " ".join(c.get("value", "") for c in e.get("content") or []))
    return m.group(1) if m else None


def day_of(e):
    t = e.get("published_parsed") or e.get("updated_parsed")
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", t) if t else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def poll_rss(feed):
    """One feed: new stories go into the queue. Feeds that carry the full article skip the fetch."""
    c = store.db(); prev = c.execute("SELECT etag, modified FROM feeds WHERE id=?", (feed["id"],)).fetchone()
    d = feedparser.parse(feed["url"], agent=UA, etag=prev["etag"] if prev else None, modified=prev["modified"] if prev else None)
    status = getattr(d, "status", None)
    if status == 304: return 0, "ok"
    if not d.entries:
        return 0, f"no entries ({status or type(d.get('bozo_exception')).__name__})"
    new = 0
    for e in d.entries[:60]:
        title, link = text_of(e.get("title")), e.get("link")
        if not title or not link: continue
        content = " ".join(x.get("value", "") for x in e.get("content") or [])
        full = trafilatura.extract(f"<html><body><article>{content}</article></body></html>", output_format="markdown") if len(text_of(content).split()) >= FULL_WORDS else None
        item = {"url": link, "feed": feed["id"], "source": feed["name"], "country": feed["country"], "region": feed["region"], "lang": feed["lang"], "category": feed["category"],
                "title": title, "published": day_of(e), "image": image_of(e), "teaser": text_of(e.get("summary"))[:2000]}
        if full and len(full.split()) >= FULL_WORDS:
            item.update(state="ready", depth="full", body=full[:60000], words=len(full.split()), reason="full_text_in_feed", ready_at=time.time())
        else:
            item.update(state="new")
        new += store.add(item)
    c.execute("INSERT INTO feeds (id, etag, modified, last_poll, last_status, items_seen) VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET etag=excluded.etag, modified=excluded.modified, last_poll=excluded.last_poll, last_status=excluded.last_status, items_seen=items_seen+excluded.items_seen",
              (feed["id"], getattr(d, "etag", None), getattr(d, "modified", None), time.time(), "ok", new))
    return new, "ok"


def poll_sitemap(feed, max_age_h=48):
    """A news sitemap (Google News format) lists recent articles with titles and dates: the backup when a site has no feed."""
    raw = urllib.request.urlopen(urllib.request.Request(feed["url"], headers={"User-Agent": UA}), timeout=30).read(10_000_000)
    if raw[:2] == b"\x1f\x8b":
        import gzip; raw = gzip.decompress(raw)
    if b"<!ENTITY" in raw: return 0, "refused: entity declarations"
    root, new, cut = ET.fromstring(raw), 0, time.time() - max_age_h * 3600
    for u in (e for e in root.iter() if e.tag.split("}")[-1] == "url"):
        f = {k.tag.split("}")[-1]: (k.text or "").strip() for k in u.iter()}
        title, link, when = f.get("title"), f.get("loc"), f.get("publication_date") or f.get("lastmod") or ""
        if not title or not link: continue
        try:
            ts = time.mktime(time.strptime(when[:19], "%Y-%m-%dT%H:%M:%S"))
            if ts < cut: continue
        except ValueError: pass
        new += store.add({"url": link, "feed": feed["id"], "source": feed["name"], "country": feed["country"], "region": feed["region"], "lang": feed["lang"], "category": feed["category"],
                          "title": html.unescape(title), "published": when[:19] + "Z" if when else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "image": None, "teaser": "", "state": "new"})
    store.db().execute("INSERT INTO feeds (id, last_poll, last_status, items_seen) VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET last_poll=excluded.last_poll, last_status=excluded.last_status, items_seen=items_seen+excluded.items_seen",
                       (feed["id"], time.time(), "ok", new))
    return new, "ok"


def poll(feed):
    try:
        return poll_sitemap(feed) if feed["kind"] == "sitemap" else poll_rss(feed)
    except Exception as e:
        store.db().execute("INSERT INTO feeds (id, last_poll, last_status, errors) VALUES (?,?,?,1) ON CONFLICT(id) DO UPDATE SET last_poll=excluded.last_poll, last_status=excluded.last_status, errors=errors+1",
                           (feed["id"], time.time(), f"error: {type(e).__name__}"))
        return 0, f"error: {type(e).__name__}"
