"""harvest: lazy, resumable label harvester (extends analyze2's tools; owner direction 2026-11-07: tools are the gold, models validate).
Reads runs/harvest/sample.jsonl in chunks; skips rows already in runs/harvest/labels.jsonl; appends one record per article with each tool's label AND its evidence.
    /workspace/models/embed-zs/.venv/bin/python harvest.py [max_new_rows]"""
import sys, json, re, os
from multiprocessing import Pool
from urllib.parse import urlparse
import facts_lib as FL
SEC = {  # URL section word -> MN-DS level-1 class (rule table; one line per class)
 "sport": "sport", "sports": "sport", "soccer": "sport", "football": "sport", "nba": "sport", "nfl": "sport", "cricket": "sport", "tennis": "sport", "golf": "sport", "rugby": "sport", "baseball": "sport", "hockey": "sport",
 "business": "economy, business and finance", "economy": "economy, business and finance", "finance": "economy, business and finance", "markets": "economy, business and finance", "money": "economy, business and finance", "companies": "economy, business and finance",
 "entertainment": "arts, culture, entertainment and media", "tvshowbiz": "arts, culture, entertainment and media", "music": "arts, culture, entertainment and media", "movies": "arts, culture, entertainment and media", "arts": "arts, culture, entertainment and media", "celebrity": "arts, culture, entertainment and media", "tv": "arts, culture, entertainment and media", "showbiz": "arts, culture, entertainment and media",
 "politics": "politics", "election": "politics", "elections": "politics",
 "health": "health", "healthcare": "health",
 "tech": "science and technology", "technology": "science and technology", "science": "science and technology",
 "environment": "environment", "climate": "environment",
 "education": "education", "weather": "weather", "religion": "religion and belief", "crime": "crime, law and justice", "law": "crime, law and justice", "lifestyle": "lifestyle and leisure", "travel": "lifestyle and leisure", "food": "lifestyle and leisure", "life": "lifestyle and leisure",
}
FN = {"opinion": "opinion", "opinions": "opinion", "editorial": "opinion", "comment": "opinion", "commentary": "opinion", "blog": "opinion", "blogs": "opinion", "analysis": "analysis", "video": "video", "videos": "video", "watch": "video", "press-release": "release", "news-releases": "release", "pressreleases": "release", "obituaries": "obituary"}
def job(r):
    segs = [s.lower() for s in urlparse(r["url"] or "").path.split("/") if s]; out = {"row": r["row"], "domain": r["domain"], "date": (r["date"] or "")[:10] or None, "chars": len(r["text"] or "")}
    w = next((s for s in segs[:-1] if s in SEC or s in FN), None)  # section words sit before the slug
    if w in SEC: out["domain_label"] = {"label": SEC[w], "tool": "url_section", "evidence": w}
    if w in FN: out["function_label"] = {"label": FN[w], "tool": "url_section", "evidence": w}
    text = re.sub(r"\s+", " ", (r["title"] or "") + ". " + (r["text"] or ""))[:12000]
    try: facts = FL.facts_for(text, (out["date"] + "T00:00:00Z") if out["date"] else None)[0]
    except Exception as e: facts = []; out["facts_error"] = str(e)[:80]
    out["amounts"] = [f["text"] for f in facts if f["kind"] == "amount" and f["status"] == "stated"][:8]; out["dates"] = [f["text"] for f in facts if f["kind"] == "date" and f["status"] == "stated"][:5]
    return out
if __name__ == "__main__":
    cap = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9; SMP = sys.argv[2] if len(sys.argv) > 2 else "runs/harvest/sample.jsonl"; P = sys.argv[3] if len(sys.argv) > 3 else "runs/harvest/labels.jsonl"
    done = {json.loads(l)["row"] for l in open(P)} if os.path.exists(P) else set()
    todo = [r for r in map(json.loads, open(SMP)) if r["row"] not in done][:cap]; n = 0
    with Pool(16) as pool, open(P, "a") as w:
        for o in pool.imap(job, todo, chunksize=20): w.write(json.dumps(o) + "\n"); n += 1
    print("harvested", n, "new; total", len(done) + n)
