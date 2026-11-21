"""current-events-fetch: T174(a), targeted outside-truth fetch (owner yes L2870). One serial MediaWiki API request per calendar day, Portal:Current_events/<YYYY_Month_D>, action=parse prop=wikitext.
NETWORK ONLY IN THIS SCRIPT (tests read the saved snapshots). Descriptive User-Agent, serial, 1 s pause, maxlag=5, retry once on 429/maxlag/5xx honouring Retry-After (API:Etiquette).
Output: /workspace/data/anchors/current_events/<YYYY-MM-DD>.json (bullets: category, depth, parent, text, wikilinks, sources) + MANIFEST.json (sha256 per file, licence, attribution, fetch time).
Licence: Wikipedia text is CC BY-SA 4.0; attribution: 'Wikipedia contributors, Portal:Current events/<date>, https://en.wikipedia.org/wiki/Portal:Current_events/<date>, revision ids in each file'.
    python3 current-events-fetch.py [--trace <trace folder>] [--days 2026-11-05,2026-11-06] [--out <dir>] [--force]   (days default: every calendar day in the trace's published dates)"""
import sys, os, re, json, time, hashlib, datetime, urllib.request, urllib.parse, urllib.error, collections
UA = "knowledge-pipeline-research/0.1 (local)"; API = "https://en.wikipedia.org/w/api.php"
OUT = "/workspace/data/anchors/current_events"; TRACE = "/workspace/demo/mockups/structure-live/runs-v7/trace"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
LICENCE = "CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/)"
def trace_days(folder):
    c = collections.Counter()
    for ln in open(folder + "/chain.jsonl"):
        l = json.loads(json.loads(ln)["line"])
        if l.get("state") == "traced" and (l.get("published") or "")[:10]: c[l["published"][:10]] += 1
    return dict(sorted(c.items()))
def page_name(day):
    d = datetime.date.fromisoformat(day); return "Portal:Current_events/%d_%s_%d" % (d.year, MONTHS[d.month - 1], d.day)
def clean(t):
    t = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>|<!--.*?-->", "", t, flags=re.S); t = re.sub(r"\{\{small\|([^}]*)\}\}", r"\1", t)
    t = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", t); t = re.sub(r"'{2,}", "", t); t = re.sub(r"\{\{[^}]*\}\}", "", t)
    return re.sub(r"\s+", " ", t).strip()
def parse_wikitext(w):
    """-> list of bullets; categories are the '''bold''' lines, depth = number of leading *, parent = nearest shallower bullet's cleaned text"""
    out = []; cat = None; stack = {}
    for ln in w.splitlines():
        s = ln.rstrip()
        m = re.match(r"^'''(.+?)'''\s*$", s)
        if m: cat = clean(m.group(1)); stack = {}; continue
        m = re.match(r"^(\*+)\s*(.*)$", s)
        if not m or cat is None: continue
        depth = len(m.group(1)); raw = m.group(2); src = [{"url": u, "label": clean(lb).strip("() ")} for u, lb in re.findall(r"\[(https?://[^\s\]]+)\s*([^\]]*)\]", raw)]
        body = re.sub(r"\[https?://[^\]]*\]", "", raw); links = [x.split("|")[0] for x in re.findall(r"\[\[([^\]]+)\]\]", body)]
        text = clean(body); parent = next((stack[d] for d in range(depth - 1, 0, -1) if d in stack), None)
        stack[depth] = text; [stack.pop(d) for d in list(stack) if d > depth]
        if text: out.append({"category": cat, "depth": depth, "parent": parent, "text": text, "wikilinks": links, "sources": src})
    return out
def api(params, tries=2):
    q = urllib.parse.urlencode({**params, "format": "json", "formatversion": 2, "maxlag": 5})
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(API + "?" + q, headers={"User-Agent": UA, "Accept-Encoding": "identity"}), timeout=30) as r: d = json.loads(r.read())
            if d.get("error", {}).get("code") == "maxlag" and k + 1 < tries: time.sleep(5); continue
            return d
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and k + 1 < tries: time.sleep(int(e.headers.get("Retry-After") or 5)); continue
            return {"error": {"code": "http_%d" % e.code}}
        except Exception as e: return {"error": {"code": "exc", "info": repr(e)}}
def main():
    opt = lambda f: sys.argv[sys.argv.index(f) + 1] if f in sys.argv else None
    out = opt("--out") or OUT; os.makedirs(out, exist_ok=True); counts = trace_days(opt("--trace") or TRACE)
    days = opt("--days").split(",") if opt("--days") else list(counts); man = {"fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "source": "en.wikipedia.org MediaWiki API action=parse prop=wikitext|revid, page Portal:Current_events/<YYYY_Month_D>", "user_agent": UA, "licence": LICENCE,
           "attribution": "Wikipedia contributors, Portal:Current events (per-day pages), https://en.wikipedia.org/wiki/Portal:Current_events, text CC BY-SA 4.0; each day file carries the page title and revision id", "trace_day_item_counts": counts, "files": {}}
    for i, day in enumerate(days):
        fp = "%s/%s.json" % (out, day)
        if os.path.exists(fp) and "--force" not in sys.argv: print(day, "exists, kept"); d = json.load(open(fp)); man["files"][day + ".json"] = {"sha256": hashlib.sha256(open(fp, "rb").read()).hexdigest(), "bullets": len(d["bullets"]), "status": d["status"], "kept": True}; continue
        if i: time.sleep(1.0)
        r = api({"action": "parse", "page": page_name(day), "prop": "wikitext|revid"})
        if "parse" in r: p = r["parse"]; bl = parse_wikitext(p["wikitext"]); rec = {"date": day, "page": p["title"], "revid": p.get("revid"), "status": "ok" if bl else "empty", "licence": LICENCE, "url": "https://en.wikipedia.org/wiki/" + page_name(day), "bullets": bl}
        else: rec = {"date": day, "page": page_name(day).replace("_", " "), "revid": None, "status": "missing: " + (r.get("error") or {}).get("code", "?"), "licence": LICENCE, "url": "https://en.wikipedia.org/wiki/" + page_name(day), "bullets": []}
        json.dump(rec, open(fp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        man["files"][day + ".json"] = {"sha256": hashlib.sha256(open(fp, "rb").read()).hexdigest(), "bullets": len(rec["bullets"]), "status": rec["status"], "revid": rec["revid"]}
        print(day, rec["status"], len(rec["bullets"]), "bullets")
    json.dump(man, open(out + "/MANIFEST.json", "w"), indent=1)
    print("days", len(days), "ok", sum(1 for v in man["files"].values() if v["status"] == "ok"), "bullets", sum(v["bullets"] for v in man["files"].values()))
if __name__ == "__main__": main()
