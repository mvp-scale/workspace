"""G0 Normalise: the source-agnostic record every later gate reads (owner correction 2026-11-05: normalising is the CONTRACT of what any content becomes, not the cleaning statistics).
NormalizedItem v1
  id                sha256 (16 hex) of kind | source.name | title | body
  kind              article | headline | email | transcript | document   (set by the adapter)
  source            {name, ref, published_at, author}   each may be null; ref is a url, message id or file
  title             text or null;           title_from: given | derived:<rule> | none
  description       one line;               description_from: given | derived:<rule>
  snapshot          first 250 characters of the body, cut at a word boundary (always derived)
  body              the full cleaned text; every later span cites character offsets into it
  language          {code, how}
  segments          list of {n, kind, title, start, end, chars, snapshot}: pages, sections, speaker turns or email messages, as offsets into body. A short item has one segment; a long source is a parent record plus its segments, and classifiers read one segment at a time (heading + snapshot), never the whole body.
  time              {published_at, ingested_at, anchor, lag_hours}: anchor is the date relative words in the text resolve against (published_at if given, else when we first saw it)
  provenance        playbook 00 section 5: tenant, permission_policy, normalised_at, transformation_history, extraction_version (hash is the id)
Title, description and snapshot are the owner's additions; the playbook lists only the provenance fields.
Small classifiers read the classifier view: title + description (expert_contract_v1: headline + short description + source).
Adapters here are run on real data: feed_article (newsreader records) and cc_headline (CC-News pool items). email, transcript and document are designed in ADAPTER_DESIGN and not run.
"""
import re, hashlib, unicodedata, datetime
EXTRACTION_VERSION = "normalize.py v1 (2026-11-05)"
STOP = set("the of and to a in is that for it on with as was at by from be this are an or have has had not but they their its were which will would about after more than also can been who said says".split())
STEPS = []
def _clean(raw):
    STEPS.clear(); orig = raw
    for name, rx in (("image tags removed", r"!\[[^\]]*\]\([^)]*\)"), ("links reduced to their text", r"\[[^\]]*\]\([^)]*\)"), ("heading marks removed", r"(?m)^#+\s"), ("bold marks removed", r"\*\*|__")):
        if re.search(rx, orig): STEPS.append(name)
    if unicodedata.normalize("NFKC", orig) != orig: STEPS.append("unicode normalised (NFKC)")
    STEPS.append("whitespace collapsed")
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", raw); t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t); t = re.sub(r"^#+\s*", "", t, flags=re.M); t = t.replace("**", "").replace("__", "")
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", t)).strip()
def _first_sentence(t, cap=250):
    m = re.match(r"(.{20,}?[.!?])(?:\s+(?=[A-Z0-9\"“‘'])|$)", t)
    s = m.group(1) if m else t[:cap]
    return s if len(s) <= cap else s[:cap].rsplit(" ", 1)[0]
def _snapshot(body, n=250):
    return body if len(body) <= n else body[:n].rsplit(" ", 1)[0]
def _lang(body):
    toks = re.findall(r"[a-z']+", body.lower()); sw = sum(1 for w in toks if w in STOP) / max(len(toks), 1)
    return {"code": "en" if sw > 0.2 else "unknown", "how": f"English stopword share {sw:.2f}"}
def _iso(ts): return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def _time(published, found_at):
    """Time block. anchor = the date that relative words in the text (Saturday, last week) resolve against: the feed publish time when given, else the time we first saw the item."""
    ing = _iso(found_at) if found_at else None; anchor = published or ing
    lag = None
    if published and ing: lag = round((datetime.datetime.fromisoformat(ing.replace("Z", "+00:00")) - datetime.datetime.fromisoformat(published.replace("Z", "+00:00"))).total_seconds() / 3600, 1)
    return {"published_at": published, "published_from": "given by the feed" if published else "not in the source", "ingested_at": ing, "anchor": anchor, "anchor_from": "published_at" if published else ("ingested_at (time we first saw it)" if ing else "none"), "lag_hours": lag}
def _finish(kind, source, title, title_from, desc, desc_from, body, steps=None, permission="public source", time=None, segments=None):
    h = hashlib.sha256(f"{kind}|{source.get('name')}|{title}|{body}".encode()).hexdigest()[:16]
    return {"id": h, "kind": kind, "source": source, "title": title, "title_from": title_from, "description": desc, "description_from": desc_from, "snapshot": _snapshot(body), "body": body, "body_chars": len(body), "segments": segments or [{"n": 1, "kind": "whole item", "title": title, "start": 0, "end": len(body), "chars": len(body), "snapshot": _snapshot(body)}], "language": _lang(body), "time": time or _time(None, None),
            "provenance": {"tenant": "default", "permission_policy": permission, "normalised_at": datetime.datetime.now().isoformat(timespec="seconds"), "transformation_history": list(steps or STEPS), "extraction_version": EXTRACTION_VERSION}}
def feed_article(rec, store=None):
    """newsreader record {id, source, region, title, text}: the feed gives a title; the text may repeat it as a heading, carry an italic standfirst (the outlet's own one-line summary) and open with a dateline."""
    raw = rec["text"]; title = _clean(rec["title"]); extra = []
    raw2 = re.sub(r"^\s*#+\s*" + re.escape(rec["title"]).replace("\\ ", r"\s+") + r"\s*(?:-\s*Published\s*)?", "", raw, count=1)
    if raw2 != raw: extra.append("title heading removed from the body"); raw = raw2
    desc = None; desc_from = None
    m = re.match(r"\s*\*([^*]{20,400})\*\s*", raw)
    if m: desc = _clean(m.group(1)); desc_from = "given: the outlet's italic standfirst"; raw = raw[m.end():]; extra.append("standfirst moved to description")
    body = _clean(raw); steps = list(STEPS) + extra; dateline = None
    m = re.match(r"([A-Z][A-Z .,'’]{2,40}?)(?:\s+\(([A-Za-z .]+)\))?\s+[—–-]\s+", body)
    if m: dateline = m.group(1).strip() + (f" ({m.group(2)})" if m.group(2) else ""); body = body[m.end():]; steps.append("dateline moved to source.dateline")
    if desc is None: desc, desc_from = _first_sentence(body), "derived:first sentence of the body"
    ref, region, tm, lang = rec["id"], rec.get("region"), _time(None, None), None
    if store:
        ref, region, tm = store["url"], store["country"], _time(store["published"], store["found_at"])
        if store["teaser"] and desc_from.startswith("derived"): desc, desc_from = _clean(store["teaser"]), "given: the feed's own description"
        lang = {"code": store["lang"], "how": "given by the feed"}
    c = _finish("article", {"name": rec["source"], "ref": ref, "region": region, "author": None, "dateline": dateline}, title, "given", desc, desc_from, body, steps, time=tm)
    if lang: c["language"] = lang
    return c
def cc_headline(rec):
    """CC-News pool item {id: 'cc:<url>', text: 'Headline. Short description…', date}: headline and description arrive fused in one string."""
    body = _clean(rec["text"]); url = rec["id"][3:] if rec["id"].startswith("cc:") else rec["id"]
    m = re.match(r"(.{8,}?[.!?])\s+(?=[A-Z0-9\"“‘'])", body); title = m.group(1) if m else body[:120]; rest = body[len(title):].lstrip() if m else ""
    host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
    return _finish("headline", {"name": host, "ref": url, "author": None}, title, "derived:text before the first sentence end", _first_sentence(rest) if rest else None, "derived:first sentence after the headline" if rest else "none", body, time={"published_at": rec.get("date"), "published_from": "given by the dataset (date only)" if rec.get("date") else "not in the source", "ingested_at": None, "anchor": rec.get("date"), "anchor_from": "published_at" if rec.get("date") else "none", "lag_hours": None})
def markdown_document(text, name, ref):
    """A long markdown document: the body keeps paragraph breaks; each heading opens a section segment with offsets into the body. Fenced code blocks are removed and counted."""
    steps = []; nfence = len(re.findall(r"^```", text, re.M)) // 2
    if nfence: text = re.sub(r"^```.*?^```\s*$", "", text, flags=re.M | re.S); steps.append(f"{nfence} fenced code blocks removed")
    blocks = []  # (is_heading, level, text)
    for chunk in re.split(r"\n\s*\n", text):
        chunk = chunk.strip()
        if not chunk: continue
        m = re.match(r"^(#{1,3})\s+(.*)$", chunk)
        if m and "\n" not in chunk: blocks.append((True, len(m.group(1)), _clean(m.group(2))))
        else: blocks.append((False, 0, _clean(re.sub(r"^[-*]\s+|^\|", "", chunk, flags=re.M))))
    title = next((b[2] for b in blocks if b[0] and b[1] == 1), name); body = ""; segs = []; cur = None
    def close():
        if cur: cur["end"] = len(body); cur["chars"] = cur["end"] - cur["start"]; cur["snapshot"] = _snapshot(body[cur["start"]:cur["end"]]); segs.append(cur)
    for is_h, lvl, tx in blocks:
        if is_h and lvl >= 1:
            close(); body += ("\n\n" if body else ""); cur = {"n": len(segs) + 1, "kind": f"section (h{lvl})", "title": tx, "start": len(body)}; body += tx
        else: body += ("\n\n" if body else "") + tx
    close()
    first = next((b[2] for b in blocks if not b[0] and len(b[2]) > 40), "")
    steps = ["markdown marks removed", "paragraph breaks kept"] + steps
    return _finish("document", {"name": name, "ref": ref, "author": None}, title, "derived:first heading", _first_sentence(first) if first else None, "derived:first sentence of the first paragraph", body, steps, time=_time(None, None), segments=segs)
ADAPTER_DESIGN = [
    ("News feed article", "given by the feed", "first sentence of the body (derived)", "extracted article text", "run on 3 real articles"),
    ("Headline item (CC-News)", "text before the first sentence end (derived)", "first sentence after it (derived)", "the whole string", "run on real items"),
    ("Transcript", "session title or first spoken line", "first spoken sentence", "one segment per speaker turn, with speaker and time", "design, not run"),
    ("Markdown document", "first heading (derived)", "first sentence of the first paragraph (derived)", "paragraphs kept; one segment per heading", "run on playbook 00"),
    ("Long file (PDF, book)", "file title or cover page", "abstract or first paragraph", "one segment per page; the parent keeps the outline, not the pages", "design, not run"),
    ("Email thread", "subject of the first message", "first sentence of the first message", "one segment per message, quoted replies removed", "design, not run"),
]
