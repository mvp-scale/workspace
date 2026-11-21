"""wikidata_cache: T174(b), Wikidata identity cache (owner yes L2870). wbsearchentities per extracted name, serial, cached to /workspace/data/anchors/wikidata_cache/<sha1(name)[:16]>.json (CC0: Wikidata structured data is public domain).
Names: for each article in the G4 stores (runs/g4/store.jsonl + runs/g4/archive/store.jsonl-*; read-only, own decoder, g4-align is not imported) the top TOP=20 non-concept entities by alias mentions (canon name), plus every alias surface of those entities that differs from the canon (the surfaces the G4 same-entity merge joined: the identity check in resource_truth.py needs them).
NETWORK ONLY under --fetch (descriptive User-Agent, serial, 3 s pause, maxlag=5, on 429/5xx wait Retry-After + 2 s and retry (up to 6 tries)). lookup()/resolve() read the cache only: tests and resource_truth.py never touch the network.
    python3 wikidata_cache.py --freeze              (save the current plan to <cache>/PLAN.json; the stores grow while services run; --fetch, resource_truth.py and check-truth.py use the frozen plan)
    python3 wikidata_cache.py --plan                (list the names, count cache hits, no network)
    python3 wikidata_cache.py --fetch [--limit N]   (fetch the names not yet cached)
resolve(name) -> {"qid", "label", "description", "n_hits", "margin_note"} for the top hit, or None when the cache has no hit for it (not cached, or the search returned nothing); lookup(name) -> the cached record or None."""
import sys, os, re, json, glob, time, hashlib, datetime, collections, urllib.request, urllib.parse, urllib.error
UA = "knowledge-pipeline-research/0.1 (local)"; API = "https://www.wikidata.org/w/api.php"; CACHE = "/workspace/data/anchors/wikidata_cache"
H = os.path.dirname(os.path.abspath(__file__)); STORES = [os.path.join(H, "..", "..", "runs", "g4", "store.jsonl")] + sorted(glob.glob(os.path.join(H, "..", "..", "runs", "g4", "archive", "store.jsonl-*")))
TOP = 20; LIMIT = 5; PAUSE = 3.0; LICENCE = "CC0 1.0 (Wikidata structured data)"
def qname(s):
    """the query string: possessive stripped, whitespace collapsed (case kept: Wikidata search is case-insensitive but the cache key is lower-cased)"""
    s = re.sub(r"['’]s\b", "", str(s or "")); s = re.sub(r"['’]$", "", s); return re.sub(r"\s+", " ", s).strip()
def key(name): return hashlib.sha1(qname(name).lower().encode("utf-8")).hexdigest()[:16]
def path(name, cache=CACHE): return "%s/%s.json" % (cache, key(name))
def lookup(name, cache=CACHE):
    p = path(name, cache)
    try: return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
    except Exception: return None
def resolve(name, cache=CACHE):
    r = lookup(name, cache)
    if not r or not r.get("results"): return None
    t = r["results"][0]; return {"qid": t["id"], "label": t.get("label"), "description": t.get("description"), "n_hits": len(r["results"]), "alt_qids": [x["id"] for x in r["results"][1:3]]}
def dec(v):
    if isinstance(v, list): return [dec(x) for x in v]
    if isinstance(v, dict):
        if "__d" in v: return {dec(k): dec(x) for k, x in v["__d"]}
        if "__s" in v: return [dec(x) for x in v["__s"]]
        if "__t" in v: return tuple(dec(x) for x in v["__t"])
        if "__a" in v: return None
    return v
def read_entities(stores=None):
    """entity id -> latest decoded record across the store files (each JSONL line holds the entries that changed; later lines win)"""
    ents = {}
    for f in (stores or STORES):
        if not os.path.exists(f): continue
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                try: rows = json.loads(ln).get("ent", [])
                except ValueError: continue   # a line still being written by the live store
                for k, v in rows: ents[k] = dec(v)
    return ents
def plan(stores=None):
    """-> {"names": ordered unique query names, "per_article": {art: [canon names]}, "merges": [(entity id, type, canon, [surfaces])]}"""
    ents = read_entities(stores); per = collections.defaultdict(list)
    for e in ents.values():
        if e["type"] == "concept": continue
        w = sum(e["aliases"].values()) if isinstance(e["aliases"], dict) else len(e["aliases"])
        for a in (e.get("arts") or {}): per[a].append((w, e["canon"], e["id"]))
    top = {a: sorted(v, key=lambda x: (-x[0], x[1]))[:TOP] for a, v in per.items()}; eids = {x[2] for v in top.values() for x in v}
    names = []; seen = set(); merges = []
    def add(n):
        n = qname(n)
        if n and n.lower() not in seen: seen.add(n.lower()); names.append(n)
    for a in sorted(top): [add(x[1]) for x in top[a]]
    for i in sorted(eids):
        e = ents[i]; sf = sorted({qname(a) for a in e["aliases"] if qname(a).lower() != qname(e["canon"]).lower() and qname(a)})
        if sf: merges.append((i, e["type"], e["canon"], sf)); [add(s) for s in sf]
    return {"names": names, "per_article": {a: [x[1] for x in v] for a, v in top.items()}, "merges": merges}
PLAN_FILE = CACHE + "/PLAN.json"
def freeze(P=None):
    """the G4 stores keep growing while the services run: --freeze saves the plan (names, per-article top 20, merge entities) next to the cache so fetch, scoring and tests all use the same list"""
    P = P or plan(); json.dump({"frozen_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "stores": [os.path.basename(f) for f in STORES if os.path.exists(f)], "names": P["names"], "per_article": P["per_article"], "merges": P["merges"]}, open(PLAN_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1); return P
def load_plan():
    """the frozen plan when PLAN.json exists, else a fresh one from the stores"""
    if os.path.exists(PLAN_FILE):
        d = json.load(open(PLAN_FILE, encoding="utf-8")); return {"names": d["names"], "per_article": d["per_article"], "merges": [tuple(m) for m in d["merges"]]}
    return plan()
def api(params, tries=6):
    q = urllib.parse.urlencode({**params, "format": "json", "maxlag": 5})
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(API + "?" + q, headers={"User-Agent": UA, "Accept-Encoding": "identity"}), timeout=30) as r: d = json.loads(r.read())
            if d.get("error", {}).get("code") == "maxlag" and k + 1 < tries: time.sleep(5); continue
            return d
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and k + 1 < tries: time.sleep(min(int(e.headers.get("Retry-After") or 5), 120) + 2); continue   # honour Retry-After (Wikimedia rate limits: anonymous clients get 429)
            return {"error": {"code": "http_%d" % e.code}}
        except Exception as e: return {"error": {"code": "exc", "info": repr(e)}}
def fetch(names, cache=CACHE, limit=None):
    os.makedirs(cache, exist_ok=True); done = 0; first = True; errs = 0
    for n in names:
        if os.path.exists(path(n, cache)): continue
        if limit is not None and done >= limit: break
        if not first: time.sleep(PAUSE)
        first = False; r = api({"action": "wbsearchentities", "search": n, "language": "en", "uselang": "en", "type": "item", "limit": LIMIT})
        if "search" not in r: errs += 1; print("ERROR", n, r.get("error"), flush=True); continue
        rec = {"query": n, "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "licence": LICENCE, "results": [{"id": x["id"], "label": x.get("label"), "description": x.get("description"), "match": (x.get("match") or {}).get("type")} for x in r["search"]]}
        json.dump(rec, open(path(n, cache), "w", encoding="utf-8"), ensure_ascii=False, indent=1); done += 1
        if done % 50 == 0: print("fetched", done, flush=True)
    man = {"licence": LICENCE, "user_agent": UA, "source": API + " action=wbsearchentities language=en type=item limit=%d" % LIMIT, "written_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "files": {}}
    for f in sorted(glob.glob(cache + "/*.json")):
        if os.path.basename(f) not in ("MANIFEST.json", "PLAN.json"): man["files"][os.path.basename(f)] = {"sha256": hashlib.sha256(open(f, "rb").read()).hexdigest(), "query": json.load(open(f, encoding="utf-8"))["query"]}
    json.dump(man, open(cache + "/MANIFEST.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False); return done, errs
if __name__ == "__main__":
    if "--freeze" in sys.argv: freeze(); print("frozen", PLAN_FILE)
    P = load_plan(); hit = sum(1 for n in P["names"] if lookup(n)); print("articles", len(P["per_article"]), "names", len(P["names"]), "cached", hit, "merge entities", len(P["merges"]))
    if "--fetch" in sys.argv:
        lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None; d, e = fetch(P["names"], limit=lim); print("fetched", d, "errors", e)
