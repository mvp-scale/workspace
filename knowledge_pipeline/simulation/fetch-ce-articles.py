"""fetch-ce-articles (round C2, T158-C2): saves public article pages cited by the ce1 bullets as raw snapshots, one JSON file per url hash, under /workspace/data/anchors/current_events/ce1-articles/.
Polite: robots.txt respected (urllib.robotparser, per host, same User-Agent), >= 1.5 s between requests to one host, 20 s timeout, 2 MB cap, plain research User-Agent, no cookies, no login, no paywall circumvention, no retries. Failures are saved too (status + reason) so a rerun uses the snapshots and never refetches.
Only the FIRST cited url of each bullet is fetched (the item's url). No model, CPU only. Network: public pages only.
    /workspace/models/embed-zs/.venv/bin/python simulation/fetch-ce-articles.py [--days 2026-11-17,2026-11-18,2026-11-19] [--limit N]"""
import sys, os, json, time, hashlib, datetime, urllib.parse, urllib.robotparser
import requests
HERE = os.path.dirname(os.path.abspath(__file__)); WS = os.path.join(os.path.dirname(HERE), "projects", "world-state"); sys.path.insert(0, WS)
import source_adapters as SA
OUT = os.path.join(SA.CE_DIR, "ce1-articles"); UA = "knowledge-pipeline-research-script/1.0 (local non-commercial research; respects robots.txt; 1.5 s per host)"
a = sys.argv[1:]; DAYS = a[a.index("--days") + 1].split(",") if "--days" in a else ["2026-11-17", "2026-11-18", "2026-11-19"]; LIMIT = int(a[a.index("--limit") + 1]) if "--limit" in a else None
os.makedirs(OUT, exist_ok=True); last = {}; robots = {}; stats = {"urls": 0, "cached": 0, "ok": 0, "failed": {}}
def fail(why): stats["failed"][why] = stats["failed"].get(why, 0) + 1
def allowed(u):
    p = urllib.parse.urlparse(u); host = p.scheme + "://" + p.netloc
    if host not in robots:
        rp = urllib.robotparser.RobotFileParser(); rp.set_url(host + "/robots.txt")
        try:
            r = requests.get(host + "/robots.txt", headers={"User-Agent": UA}, timeout=20); last[p.netloc] = time.time()
            if r.status_code in (401, 403): robots[host] = "deny"          # robots.txt itself forbidden: treated as disallow all (RFC 9309 section 2.3.1.3)
            elif r.status_code >= 400: robots[host] = "allow"               # no robots.txt: allowed
            else: rp.parse(r.text.splitlines()); robots[host] = rp
        except Exception: robots[host] = "allow"                           # unreachable robots.txt: fetch attempt will show the real reason
    g = robots[host]
    return False if g == "deny" else True if g == "allow" else g.can_fetch(UA, u)
def wait(netloc):
    d = 1.6 - (time.time() - last.get(netloc, 0))
    if d > 0: time.sleep(d)
    last[netloc] = time.time()
items = SA.CurrentEventsAdapter().items({"days": DAYS})
for it in items[:LIMIT]:
    u = it["url"]; stats["urls"] += 1; f = os.path.join(OUT, hashlib.sha1(u.encode()).hexdigest() + ".json")
    if os.path.exists(f):
        stats["cached"] += 1; s = json.load(open(f))
        if s["status"] == "ok": stats["ok"] += 1
        else: fail(s["reason"])
        continue
    snap = {"url": u, "fetched_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "user_agent": UA, "status": "failed", "reason": None, "http": None, "final_url": None, "content_type": None, "html": None}
    netloc = urllib.parse.urlparse(u).netloc
    try:
        if not allowed(u): snap["reason"] = "robots.txt disallows"
        else:
            wait(netloc); r = requests.get(u, headers={"User-Agent": UA, "Accept": "text/html"}, timeout=20, stream=True, allow_redirects=True)
            snap["http"] = r.status_code; snap["final_url"] = r.url; snap["content_type"] = r.headers.get("content-type")
            body = r.raw.read(2_000_001, decode_content=True); r.close()
            if r.status_code != 200: snap["reason"] = "http %d" % r.status_code
            elif "html" not in (snap["content_type"] or "").lower(): snap["reason"] = "not html (%s)" % (snap["content_type"] or "none")
            else:
                snap["html"] = body[:2_000_000].decode(r.encoding or "utf-8", "replace"); snap["status"] = "ok"; snap["reason"] = "ok"
    except requests.exceptions.Timeout: snap["reason"] = "timeout"
    except Exception as e: snap["reason"] = "error %s" % type(e).__name__
    tmp = f + ".tmp"; json.dump(snap, open(tmp, "w"), ensure_ascii=False); os.replace(tmp, f)
    if snap["status"] == "ok": stats["ok"] += 1
    else: fail(snap["reason"])
    print("%-9s %s %s" % (snap["reason"][:24], netloc, u[:80]), flush=True)
print(json.dumps(stats))
