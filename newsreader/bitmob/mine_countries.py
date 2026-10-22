"""Country mining (D-0038): ccnews stories (same input filter as build_trainset, D-0010) that name rare/missing countries, not already in any trainset file.
  /workspace/kev/.venv/bin/python newsreader/bitmob/mine_countries.py OUT.jsonl [--per 30] [--min 40]
Rare = fewer than --min stories in the existing training/test labels (Jev country). Name/alias/demonym match on title+description; title match preferred."""
import re, os, sys, json, csv, glob, unicodedata, random, collections, argparse
import pyarrow.parquet as pq, pyarrow as pa
ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--per", type=int, default=30); ap.add_argument("--min", type=int, default=40); a = ap.parse_args()
s = open("/workspace/newsreader/bitmob/country_check.py").read(); i = s.index("EXTRA = {"); j = s.index("\n}", i) + 2; ns = {}; exec(s[i:j], ns); EXTRA = ns["EXTRA"]
rows = list(csv.DictReader(open("/workspace/probes/world-engine/data/countries_world100.csv")))
used = set(); cnt = collections.Counter()
for f in glob.glob("/workspace/data/trainset/*.jsonl"):
    for l in open(f):
        try: r = json.loads(l)
        except Exception: continue
        used.add(r.get("id")); cnt[r.get("country")] += 1
rare = [r["id"] for r in rows if cnt[r["id"]] < a.min]; name = {r["id"]: r["name"] for r in rows}
pat = {}
for c in rare:
    al = {name[c]} | {x.strip() for x in EXTRA.get(c, "").split(",") if x.strip()}
    pat[c] = re.compile(r"\b(" + "|".join(re.escape(x) for x in sorted(al, key=len, reverse=True)) + r")\b")
src = open("/workspace/newsreader/bitmob/ccnews_headline_test.py").read(); OUTLETS = set(re.findall(r'"([a-z0-9.-]+\.[a-z]{2,})"', src.split("OUTLETS = [")[1].split("]")[0]))
AD = re.compile(r"(\d+% off|\bcoupons?\b|promo code|discount code|buy now|shop now|sale ends|\bbest [\w\s-]{0,30}\b(deals|to buy)\b|\bdeals (on|for)\b|\bon sale\b)", re.I)
ROUND = re.compile(r"(morning (everyone|briefing)|evening briefing|newsletter|what we know so far|live updates?|as it happened|in pictures|news in brief|top stories)", re.I)
COMMON = set("the a an of to in and for on is was are with that by as at from has have it be said will after its his her their were not this but".split())
def english(t):
    L = [c for c in t if c.isalpha()]
    if not L or sum(not c.isascii() for c in L) / len(L) > 0.05: return False
    w = re.findall(r"[a-z']+", t.lower()); return len(w) >= 5 and sum(x in COMMON for x in w) / len(w) >= 0.05
got = collections.defaultdict(list); seen = set()
for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet")):
    pf = pq.ParquetFile(f)
    for b in pf.iter_batches(batch_size=20000, columns=["url", "domain", "date", "title", "description"]):
        for r in b.to_pylist():
            if r["domain"] not in OUTLETS: continue
            t, d = r["title"] or "", (r["description"] or "").strip()[:250]; tx = f"{t} {d}"; rid = "cc:" + r["url"]
            if rid in used or len(d) < 60 or not english(tx) or AD.search(tx) or ROUND.search(tx): continue
            for c in rare:
                if len(got[c]) >= a.per * 6: continue
                m = pat[c].search(tx)
                if m: got[c].append((0 if pat[c].search(t) else 1, {"id": rid, "title": t, "description": d, "date": (r["date"] or "")[:10], "mined_for": c}))
out = []; random.seed(3)
for c in rare:
    L = sorted(got[c], key=lambda x: (x[0], random.random()))[:a.per]
    for _, r in L:
        if r["id"] not in seen: seen.add(r["id"]); out.append(r)
open(a.out, "w").write("\n".join(json.dumps(r) for r in out) + "\n")
print(len(rare), "rare countries;", len(out), "stories;", "short:", {c: len(got[c]) for c in rare if len(got[c]) < a.per})
