"""Pulls headlines from public RSS/Atom feeds into /workspace/data/news/raw_headlines.json (git-ignored: third-party text stays out of the repo).
Each item: title, source, feed region (country code), kind ("news", "tech", "satire"). Untrusted XML: size-capped, DTD/entity declarations refused, parsed with the standard library.
Run: python3 -I build_news_bank.py"""
import json, os, re, sys, urllib.request, concurrent.futures as cf, xml.etree.ElementTree as ET
OUT = "/workspace/data/news/raw_headlines.json"
# (source, url, country code of the feed's focus, kind)
FEEDS = [
 ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", "WORLD", "news"), ("BBC UK", "https://feeds.bbci.co.uk/news/uk/rss.xml", "GB", "news"),
 ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml", "WORLD", "news"), ("BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml", "WORLD", "tech"),
 ("BBC Science", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "WORLD", "news"), ("BBC Health", "https://feeds.bbci.co.uk/news/health/rss.xml", "WORLD", "news"),
 ("BBC Entertainment", "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml", "WORLD", "news"), ("BBC Africa", "https://feeds.bbci.co.uk/news/world/africa/rss.xml", "NG", "news"),
 ("BBC Asia", "https://feeds.bbci.co.uk/news/world/asia/rss.xml", "WORLD", "news"), ("BBC Latin America", "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml", "BR", "news"),
 ("BBC Middle East", "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml", "WORLD", "news"), ("BBC Europe", "https://feeds.bbci.co.uk/news/world/europe/rss.xml", "DE", "news"),
 ("NPR News", "https://feeds.npr.org/1001/rss.xml", "US", "news"), ("NPR Politics", "https://feeds.npr.org/1014/rss.xml", "US", "news"), ("NPR Business", "https://feeds.npr.org/1006/rss.xml", "US", "news"),
 ("NPR Health", "https://feeds.npr.org/1128/rss.xml", "US", "news"), ("NPR Science", "https://feeds.npr.org/1007/rss.xml", "US", "news"), ("NPR Technology", "https://feeds.npr.org/1019/rss.xml", "US", "tech"),
 ("NPR Climate", "https://feeds.npr.org/1167/rss.xml", "US", "news"),
 ("Guardian World", "https://www.theguardian.com/world/rss", "WORLD", "news"), ("Guardian US", "https://www.theguardian.com/us-news/rss", "US", "news"),
 ("Guardian Business", "https://www.theguardian.com/uk/business/rss", "WORLD", "news"), ("Guardian Technology", "https://www.theguardian.com/technology/rss", "WORLD", "tech"),
 ("Guardian Environment", "https://www.theguardian.com/environment/rss", "WORLD", "news"), ("Guardian Science", "https://www.theguardian.com/science/rss", "WORLD", "news"),
 ("Guardian Australia", "https://www.theguardian.com/australia-news/rss", "AU", "news"), ("Guardian Global development", "https://www.theguardian.com/global-development/rss", "WORLD", "news"),
 ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "WORLD", "news"), ("DW", "https://rss.dw.com/rdf/rss-en-all", "DE", "news"), ("France 24", "https://www.france24.com/en/rss", "FR", "news"),
 ("NHK World", "https://www3.nhk.or.jp/rss/news/cat0.xml", "JP", "news"), ("Japan Times", "https://www.japantimes.co.jp/feed/", "JP", "news"),
 ("Times of India", "https://timesofindia.indiatimes.com/rssfeedstopstories.cms", "IN", "news"), ("The Hindu", "https://www.thehindu.com/news/national/feeder/default.rss", "IN", "news"),
 ("Straits Times", "https://www.straitstimes.com/news/world/rss.xml", "SG", "news"), ("Jakarta Post", "https://www.thejakartapost.com/feed", "ID", "news"),
 ("ABC Australia", "https://www.abc.net.au/news/feed/51120/rss.xml", "AU", "news"), ("CBC", "https://www.cbc.ca/webfeed/rss/rss-topstories", "CA", "news"),
 ("Premium Times", "https://www.premiumtimesng.com/feed", "NG", "news"), ("Punch Nigeria", "https://punchng.com/feed/", "NG", "news"), ("Mexico News Daily", "https://mexiconewsdaily.com/feed/", "MX", "news"),
 ("Rio Times", "https://www.riotimesonline.com/feed/", "BR", "news"), ("Daily Maverick", "https://www.dailymaverick.co.za/dmrss/", "ZA", "news"), ("Arab News", "https://www.arabnews.com/rss.xml", "SA", "news"),
 ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "WORLD", "tech"), ("The Verge", "https://www.theverge.com/rss/index.xml", "US", "tech"), ("Wired", "https://www.wired.com/feed/rss", "US", "tech"),
 ("TechCrunch", "https://techcrunch.com/feed/", "US", "tech"), ("Hacker News front page", "https://hnrss.org/frontpage", "WORLD", "tech"), ("MIT Technology Review", "https://www.technologyreview.com/feed/", "WORLD", "tech"),
 ("Nature news", "https://www.nature.com/nature.rss", "WORLD", "tech"), ("NASA", "https://www.nasa.gov/rss/dyn/breaking_news.rss", "US", "tech"), ("Phys.org", "https://phys.org/rss-feed/", "WORLD", "tech"),
 ("The Register", "https://www.theregister.com/headlines.atom", "WORLD", "tech"), ("Krebs on Security", "https://krebsonsecurity.com/feed/", "US", "tech"),
 ("CNBC Top", "https://www.cnbc.com/id/100003114/device/rss/rss.html", "US", "news"), ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories", "US", "news"),
 ("The Onion", "https://theonion.com/feed/", "US", "satire"), ("NewsThump", "https://www.newsthump.com/feed/", "GB", "satire"), ("The Daily Mash", "https://www.thedailymash.co.uk/feed", "GB", "satire"),
 ("Waterford Whispers", "https://waterfordwhispersnews.com/feed/", "IE", "satire"), ("The Babylon Bee", "https://babylonbee.com/feed", "US", "satire"), ("Reductress", "https://reductress.com/feed/", "US", "satire"),
 ("Betoota Advocate", "https://www.betootaadvocate.com/feed/", "AU", "satire"), ("The Hardy Bucks / Chaser", "https://chaser.com.au/feed/", "AU", "satire"),
 ("UPI Odd News", "https://rss.upi.com/news/odd_news.rss", "US", "satire"), ("Fark", "https://www.fark.com/fark.rss", "US", "satire"),
]
def local(t): return t.split("}")[-1]
def fetch(f):
    src, url, cc, kind = f
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (headline reader; local research)"})
        raw = urllib.request.urlopen(req, timeout=20).read(3_000_000)
        if re.search(rb"<!DOCTYPE[^>]*\[|<!ENTITY", raw[:4000] + raw): raw = re.sub(rb"<!DOCTYPE[^>]*>", b"", raw) if b"<!ENTITY" not in raw else b""
        if not raw: return f, [], "refused: entity declarations"
        root = ET.fromstring(raw); out = []
        for e in root.iter():
            if local(e.tag) in ("item", "entry"):
                t = next((c.text for c in e if local(c.tag) == "title" and c.text), None)
                if t: out.append(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t)).strip())
        return f, out[:30], None
    except Exception as ex: return f, [], f"{type(ex).__name__}: {str(ex)[:60]}"
items, seen, report = [], set(), []
with cf.ThreadPoolExecutor(12) as ex:
    for f, titles, err in ex.map(fetch, FEEDS):
        n = 0
        for t in titles:
            k = re.sub(r"\W+", "", t.lower())[:70]
            if 25 <= len(t) <= 160 and k not in seen: seen.add(k); items.append({"x": t, "src": f[0], "c": f[2], "kind": f[3]}); n += 1
        report.append((f[0], n, err))
json.dump(items, open(OUT, "w"), indent=0, ensure_ascii=False)
ok = [r for r in report if r[1]]; bad = [r for r in report if not r[1]]
print(f"{len(items)} unique headlines from {len(ok)} of {len(FEEDS)} feeds"); print("by kind:", {k: sum(1 for i in items if i['kind'] == k) for k in ("news", "tech", "satire")})
print("failed:", [(b[0], b[2]) for b in bad])
