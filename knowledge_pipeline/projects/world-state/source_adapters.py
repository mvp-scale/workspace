"""source_adapters: round C (00.1 Phase 2, plan design/plan-tactical-strategic.md:161, proof P3), the one place a source type is allowed to differ.
Interface: an adapter has `name` and `items(source) -> [source item]`; a source item is
  {id, title, text, time or None, source, owner or None, read_depth, url, reason, words, meta}
and everything from level 2 down (chain, slow clock, slow_consolidate, developments, the knowledge-raw page) reads only the queue-shaped rows `queue_rows(items)` makes from it (the allowlist of live_trace.ALLOW + the READ_SQL columns), so no stage is edited.
Adapters: NewsAdapter (the existing path, wrapped by reference: live_trace.select_sql on the news queue, read only) and CurrentEventsAdapter (Wikipedia current events, saved snapshots under /workspace/data/anchors/current_events, CC BY-SA 4.0; one dated bullet that cites at least one outlet = one source item; the first cited outlet is the item's publisher/owner, all cited outlets are kept in meta).
No network, no model, no pipeline import at module load. CPU only."""
import os, json, re, sqlite3, hashlib, datetime, glob
from html.parser import HTMLParser

NEWS_QUEUE = "/workspace/data/newsreader/queue.sqlite"
CE_DIR = "/workspace/data/anchors/current_events"
ARTICLE_DIR = os.path.join(CE_DIR, "ce1-articles")   # raw snapshots of the cited pages, saved by simulation/fetch-ce-articles.py (the adapter itself never touches the network)
OWNERS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "simulation", "fixtures", "knowledge", "ce1", "outlet-owners.json")
MIN_TEXT_CHARS = 400   # fewer extracted characters than this: the item stays title-only and is labelled teaser
ALLOW = ["id", "url", "source", "title", "teaser", "body", "published", "ready_at"]   # = live_trace.ALLOW (checked by queue_rows_match_allow)
FIELDS = ("id", "title", "text", "time", "source", "owner", "read_depth", "url", "reason", "words", "meta")

def _item(**k):
    it = {f: k.get(f) for f in FIELDS}
    miss = [f for f in ("id", "title", "source", "read_depth") if not it[f]]
    if miss: raise ValueError("source item without %s" % miss)
    return it

class NewsAdapter:
    """the existing intake, by reference: rows of the news queue (read only) as source items; nothing is changed or copied into the queue"""
    name = "news"
    def items(self, source):
        """source = {"ids": [queue ids]}; the allowlisted columns only (live_trace.select_sql)"""
        import live_trace as LT
        db = sqlite3.connect("file:%s?mode=ro" % LT.QUEUE, uri=True); out = []
        try:
            for i in source["ids"]:
                r = db.execute(LT.select_sql("id = ?"), (i,)).fetchone()
                if r is None: continue
                rd = db.execute(LT.READ_SQL, (i,)).fetchone() or (None, None, None)
                out.append(_item(id=r[0], title=r[3], text=r[5] or r[4] or "", time=r[6], source=r[2], owner=None, read_depth=rd[0] or "teaser", url=r[1], reason=rd[1], words=rd[2], meta={"ready_at": r[7], "teaser": r[4]}))
        finally: db.close()
        return out

_SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "button", "svg", "figcaption", "select", "iframe", "template"}
class _Paras(HTMLParser):
    """paragraph text of a saved page (stdlib only): the <p> blocks of the first <article> (else of the whole page), minus script/nav/header/footer/aside/form blocks"""
    def __init__(self):
        super().__init__(convert_charrefs=True); self.skip = 0; self.p = None; self.art = 0; self.in_art = []; self.all = []; self.art_paras = []
    def handle_starttag(self, t, a):
        if t in _SKIP: self.skip += 1
        elif t == "article": self.art += 1
        elif t == "p" and not self.skip: self.p = []
    def handle_endtag(self, t):
        if t in _SKIP and self.skip: self.skip -= 1
        elif t == "article" and self.art: self.art -= 1
        elif t == "p" and self.p is not None:
            x = re.sub(r"\s+", " ", "".join(self.p)).strip(); self.p = None
            if len(x) >= 40: self.all.append(x); (self.art_paras.append(x) if self.art else None)
    def handle_data(self, d):
        if self.p is not None and not self.skip: self.p.append(d)

def article_text(url, articles_dir=ARTICLE_DIR):
    """(text, info) of the saved snapshot of `url`: paragraphs joined by blank lines, deduplicated; text None when there is no usable snapshot; info says why (status, reason, chars, final_url, fetched_at)"""
    if not articles_dir: return None, {"status": "off", "reason": "article text not used"}
    f = os.path.join(articles_dir, hashlib.sha1(url.encode()).hexdigest() + ".json")
    if not os.path.exists(f): return None, {"status": "none", "reason": "no snapshot"}
    sn = json.load(open(f)); info = {"status": sn["status"], "reason": sn["reason"], "final_url": sn.get("final_url"), "fetched_at": sn.get("fetched_at"), "chars": 0}
    if sn["status"] != "ok" or not sn.get("html"): return None, info
    pp = _Paras(); pp.feed(sn["html"]); paras = pp.art_paras if sum(map(len, pp.art_paras)) >= MIN_TEXT_CHARS else pp.all; seen = set(); out = []
    for x in paras:
        if x not in seen: seen.add(x); out.append(x)
    t = "\n\n".join(out); info["chars"] = len(t)
    return (t if len(t) >= MIN_TEXT_CHARS else None), info

def load_owners(path=OWNERS_FILE):
    return json.load(open(path)) if path and os.path.exists(path) else {"wires": [], "via": False}

def owner_of_label(label, owners):
    """(owner of record, distributing outlet or None) for one cited outlet label. 'WIRE via OUTLET' (the Wikipedia cite-news via= convention) is a copy of the wire: owner = the wire, outlet kept as distributor; any other label is its own owner. Data in outlet-owners.json, not in pipeline code."""
    m = re.match(r"^(.+?) via (.+)$", label) if owners.get("via") else None
    if m and m.group(1).strip() in owners.get("wires", []): return m.group(1).strip(), m.group(2).strip()
    return label, None

class CurrentEventsAdapter:
    """Wikipedia 'Portal:Current events' day pages (saved snapshots, CC BY-SA 4.0) -> source items.
    unit = one bullet that cites at least one outlet (bullets without a citation are headings or sub-topics: dropped and counted, never invented);
    time = the day of the page (the page gives no hour); publisher/owner = the owner of record of the first cited outlet (a 'WIRE via OUTLET' label is the wire's copy: owner = the wire, see owner_of_label); meta keeps every cited outlet, owners, distributors, category, parent, wikilinks, page, revision id;
    round C2: text = the paragraphs of the saved snapshot of the first cited url (simulation/fetch-ce-articles.py; no network here); read_depth 'full' when >= MIN_TEXT_CHARS were extracted, else 'teaser' with the bullet as the title and no body; title = the bullet text."""
    name = "current-events"
    def __init__(self, snapshot_dir=CE_DIR, articles_dir=ARTICLE_DIR, owners_file=OWNERS_FILE): self.dir = snapshot_dir; self.articles_dir = articles_dir; self.owners = load_owners(owners_file); self.dropped = []; self.fetch = {}
    def items(self, source):
        """source = {"days": ["2026-11-17", ...]}"""
        out = []; self.dropped = []
        for day in source["days"]:
            p = os.path.join(self.dir, day + ".json")
            if not os.path.exists(p): raise FileNotFoundError("no saved snapshot for %s (%s)" % (day, p))
            d = json.load(open(p)); n = 0
            if d.get("status") != "ok": raise ValueError("snapshot %s status %r" % (day, d.get("status")))
            for b in d["bullets"]:
                if not b["sources"]: self.dropped.append({"day": day, "why": "no cited outlet", "text": b["text"][:80]}); continue
                key = "|".join((day, d["page"], b["category"], b.get("parent") or "", b["text"]))
                outs = [s["label"] for s in b["sources"] if s.get("label")]
                if not outs: self.dropped.append({"day": day, "why": "cited link without an outlet label", "text": b["text"][:80]}); continue
                own = [owner_of_label(o, self.owners) for o in outs]; owner = own[0][0]
                text, info = article_text(b["sources"][0]["url"], self.articles_dir); self.fetch[b["sources"][0]["url"]] = info
                full = text is not None
                out.append(_item(id=hashlib.sha1(key.encode()).hexdigest(), title=b["text"], text=text or "", time="%sT12:00:00Z" % day, source=owner, owner=owner, read_depth="full" if full else "teaser", url=b["sources"][0]["url"],
                                 reason=("cited article text from the saved snapshot (%d chars)" % info["chars"]) if full else "title-only: %s" % ("; ".join(x for x in (info.get("status"), info.get("reason")) if x)), words=len(text.split()) if full else len(b["text"].split()),
                                 meta={"day": day, "page": d["page"], "revid": d["revid"], "category": b["category"], "parent": b.get("parent"), "outlets": outs, "owners": [o[0] for o in own], "distributors": [o[1] for o in own], "urls": [s["url"] for s in b["sources"]], "article": info, "wikilinks": b["wikilinks"], "licence": d["licence"]}))
        return out

def queue_rows(items):
    """source items -> the allowlisted tuples live_trace.Chain.trace takes, in ALLOW order: (id, url, source, title, teaser, body, published, ready_at)"""
    rows = []
    for it in items:
        ra = None
        if it["time"] and re.match(r"^\d{4}-\d{2}-\d{2}", it["time"]):
            ra = datetime.datetime.strptime(it["time"][:10], "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp() + 43200
        rows.append((it["id"], it["url"], it["source"], it["title"], "", it["text"] or "", it["time"], ra))
    return rows

def write_queue_db(items, path):
    """a queue-shaped sqlite (table items: the ALLOW columns + depth, reason, words) so the unedited fixture builder and live_trace.read_info read the source like the news queue"""
    tmp = path + ".tmp"
    if os.path.exists(tmp): os.replace(tmp, tmp + ".old")
    db = sqlite3.connect(tmp); db.execute("create table items (%s, depth, reason, words)" % ", ".join(ALLOW))
    for it, r in zip(items, queue_rows(items)): db.execute("insert into items values (?,?,?,?,?,?,?,?,?,?,?)", r + (it["read_depth"], it["reason"], it["words"]))
    db.commit(); db.close(); os.replace(tmp, path); return path
