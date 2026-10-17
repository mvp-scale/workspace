"""No network: the queue, the story key, feed parsing from a string, and the fetch outcomes (full, teaser, robots, not html)."""
import os, sys, time, tempfile, unittest
from unittest import mock
os.environ["NR_DB"] = os.path.join(tempfile.mkdtemp(), "q.sqlite")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from nr import store, sources, fetch

LONG = " ".join(f"word{i}" for i in range(400))
RSS = f"""<?xml version="1.0"?><rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>T</title>
<item><title>Short one</title><link>https://a.example/1</link><description>A teaser line.</description><pubDate>Sat, 17 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>Long one</title><link>https://a.example/2</link><description>x</description><content:encoded><![CDATA[<p>{LONG}</p>]]></content:encoded><pubDate>Sat, 17 Oct 2026 11:00:00 GMT</pubDate></item>
</channel></rss>"""
FEED = {"id": "t", "name": "Test", "url": RSS, "kind": "rss", "country": "GB", "region": "Europe", "lang": "en", "category": "general"}


class T(unittest.TestCase):
    def setUp(self): store.db().execute("DELETE FROM items"); store.db().execute("DELETE FROM feeds")

    def test_story_id_normalises(self):
        a = store.story_id("Hello,  World!", "BBC", "2026-10-17T10:00:00Z"); b = store.story_id("hello world", "bbc", "2026-10-17")
        self.assertEqual(a, b); self.assertNotEqual(a, store.story_id("hello world", "npr", "2026-10-17"))

    def test_feed_parse_full_and_teaser(self):
        n, st = sources.poll_rss(FEED); self.assertEqual((n, st), (2, "ok"))
        rows = {r["title"]: dict(r) for r in store.db().execute("SELECT * FROM items")}
        self.assertEqual(rows["Long one"]["state"], "ready"); self.assertEqual(rows["Long one"]["depth"], "full"); self.assertGreaterEqual(rows["Long one"]["words"], 300)
        self.assertEqual(rows["Short one"]["state"], "new"); self.assertEqual(rows["Short one"]["teaser"], "A teaser line.")
        self.assertEqual(sources.poll_rss(FEED)[0], 0)          # same stories again: nothing new

    def test_lease_ack_and_expiry(self):
        sources.poll_rss(FEED); got = store.lease(5, seconds=0.01)
        self.assertEqual(len(got), 1); self.assertEqual(store.lease(5), [])
        time.sleep(0.02); again = store.lease(5); self.assertEqual(len(again), 1)    # an un-acked lease returns to the queue
        store.ack([again[0]["id"]]); self.assertEqual(store.stats()["by_state"].get("done"), 1)

    def _one(self, **resp):
        sources.poll_rss(FEED); it = store.claim_new(1, set())[0]
        page = resp.get("body", b""); r = mock.MagicMock(); r.read.return_value = page; r.headers = {"Content-Type": resp.get("ctype", "text/html")}
        with mock.patch.object(fetch, "allowed", return_value=resp.get("allowed", True)), mock.patch("urllib.request.urlopen", return_value=r):
            fetch.one(it)
        return dict(store.db().execute("SELECT * FROM items WHERE id=?", (it["id"],)).fetchone())

    def test_fetch_full(self):
        html = f"<html><head><title>Short one</title></head><body><nav>menu</nav><article><h1>Short one</h1><p>{LONG}</p></article></body></html>".encode()
        r = self._one(body=html); self.assertEqual((r["state"], r["depth"]), ("ready", "full")); self.assertGreater(r["words"], 300)

    def test_fetch_robots_keeps_teaser(self):
        r = self._one(allowed=False); self.assertEqual((r["state"], r["depth"], r["reason"], r["body"]), ("ready", "teaser", "robots", "A teaser line."))

    def test_fetch_not_html(self):
        r = self._one(body=b"%PDF-1.7 ...", ctype="application/pdf"); self.assertEqual((r["depth"], r["reason"]), ("teaser", "not_html"))

    def test_fetch_short_page(self):
        r = self._one(body=b"<html><body><p>Watch the video.</p></body></html>"); self.assertEqual((r["depth"], r["reason"]), ("teaser", "short_extract"))


if __name__ == "__main__": unittest.main()
