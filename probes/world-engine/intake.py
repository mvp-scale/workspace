"""RSS intake: fetch public feeds, keep headline + the feed's own one-line description + link, write immutable evidence lines. No article bodies are stored."""
import hashlib, json, sys, urllib.request, xml.etree.ElementTree as ET
from html import unescape
import re
FEEDS = {"npr_top": "https://feeds.npr.org/1001/rss.xml", "npr_world": "https://feeds.npr.org/1004/rss.xml", "npr_economy": "https://feeds.npr.org/1017/rss.xml"}
LEDGER = "/workspace/probes/world-engine/ledger"
def fetch(feeds=FEEDS, limit=10):
    out = []
    for name, url in feeds.items():
        root = ET.fromstring(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "world-engine-research/0.1"}), timeout=30).read())
        for it in root.findall("./channel/item")[:limit]:
            title = unescape(it.findtext("title") or "").strip(); desc = re.sub(r"<[^>]+>", "", unescape(it.findtext("description") or "")).strip()
            link = it.findtext("link") or ""; out.append({"evidence_id": hashlib.sha1(link.encode()).hexdigest()[:12], "source": name, "source_uri": link, "published_at": it.findtext("pubDate"),
                                                         "title": title, "description": desc[:300], "content_hash": hashlib.sha1((title + desc).encode()).hexdigest()[:12]})
    seen, uniq = set(), []
    for e in out:
        if e["evidence_id"] not in seen: seen.add(e["evidence_id"]); uniq.append(e)
    return uniq
if __name__ == "__main__":
    ev = fetch(); open(f"{LEDGER}/evidence.jsonl", "w").write("\n".join(json.dumps(e) for e in ev) + "\n"); print(len(ev), "evidence items written")
