"""Fetch Wikipedia lead paragraphs for the known-topic pilot (D-0023). Text only, public API, ~1 request per 0.6 s.
  python3 -I newsreader/bitmob/known_topic_fetch.py   -> data/suite/known_topic/wiki/<topic>.jsonl  (untrusted data)"""
import json, time, random, urllib.request, urllib.parse
import sys, os
D = "/workspace/data/suite/known_topic"; MAP = sys.argv[1] if len(sys.argv) > 1 else f"{D}/wiki_mapping.json"; OUTD = sys.argv[2] if len(sys.argv) > 2 else f"{D}/wiki"; os.makedirs(OUTD, exist_ok=True); UA = {"User-Agent": "bitmob-research/0.1 (coreytgorman@gmail.com)"}; N = 50
def api(**p):
    time.sleep(0.6); u = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(p | {"format": "json"})
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
def members(cat, kind):
    out, cont = [], {}
    while len(out) < 300:
        r = api(action="query", list="categorymembers", cmtitle="Category:" + cat, cmlimit=100, cmtype=kind, **cont)
        out += [m["title"] for m in r.get("query", {}).get("categorymembers", [])]
        if "continue" not in r: break
        cont = {"cmcontinue": r["continue"]["cmcontinue"]}
    return out
def leads(titles):
    got = {}
    for i in range(0, len(titles), 20):
        r = api(action="query", prop="extracts", exintro=1, explaintext=1, exlimit="max", titles="|".join(titles[i:i + 20]))
        for p in r.get("query", {}).get("pages", {}).values():
            t = (p.get("extract") or "").strip()
            if len(t) >= 80 and not t.lower().startswith(("may refer to", "list of")): got[p["title"]] = t
    return got
mp = json.load(open(MAP)); rng = random.Random(5); seen = set(); report = {}
for topic, cats in ((k, v) for k, v in mp.items() if k != "about"):
    titles = []
    for c in cats: titles += members(c, "page")
    titles = [t for t in dict.fromkeys(titles) if t not in seen and not t.startswith(("List of", "Index of", "Outline of"))]
    if len(titles) < 3 * N:       # short: add pages of the first-level subcategories
        for c in cats:
            for sc in members(c, "subcat")[:6]: titles += members(sc.replace("Category:", ""), "page")[:40]
        titles = [t for t in dict.fromkeys(titles) if t not in seen and not t.startswith(("List of", "Index of", "Outline of"))]
    rng.shuffle(titles); got = leads(titles[:3 * N]); rows = []
    for t, x in list(got.items())[:N]:
        seen.add(t); rows.append({"id": "wk:" + t, "topic": topic, "title": t, "input": (t + " — " + x[:250]).replace("\n", " ")})
    open(f"{OUTD}/{topic}.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in rows)); report[topic] = {"titles": len(titles), "kept": len(rows)}
    print(topic, report[topic], flush=True)
json.dump(report, open(f"{OUTD}/_fetch_report.json", "w"), indent=1)
