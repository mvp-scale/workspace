"""Place judge from place-name spans: most mentioned country in title+body (country names, a few short forms, GeoNames cities over 1,000,000) -> Jev's 8 place_region options; scores Jev place_region (accuracy). Prediction in ledger L2214.
Run: python3 -I t167_place_judge.py (from projects/world-state) -> runs/pulse/t167/t167_place_judge.json"""
import json, re, sqlite3, collections, pathlib
OUT = pathlib.Path("runs/pulse/t167"); OUT.mkdir(parents=True, exist_ok=True)
GEO = "/workspace/data/geo/"
cinfo = {}
for l in open(GEO + "countryInfo.txt"):
    if l.startswith("#") or not l.strip(): continue
    f = l.split("\t"); cinfo[f[0]] = {"name": f[4], "cont": f[8]}
SHORT = {"US": ["u.s.", "united states", "america", "american"], "GB": ["u.k.", "britain", "british", "england", "scotland", "wales", "united kingdom"], "RU": ["russia", "russian", "kremlin"], "KR": ["south korea"], "KP": ["north korea"], "CZ": ["czech"], "CD": ["congo"], "PS": ["gaza", "west bank", "palestin"], "AE": ["uae", "emirates"], "TR": ["turkey", "turkiye"]}
MENA = set("DZ BH DJ EG IR IQ IL JO KW LB LY MA OM PS QA SA SY TN AE YE AF PK EH".split())
SOUTH = set("IN BD LK NP BT MV".split()); CENTRAL = set("KZ UZ TM KG TJ AM AZ GE TR RU".split())
def region(cc):
    c = cinfo[cc]["cont"]
    if cc in MENA: return "Middle East, North Africa, Afghanistan & Pakistan"
    if cc in SOUTH: return "South Asia"
    if cc in CENTRAL or c == "EU": return "Europe & Central Asia"
    if cc in ("US", "CA"): return "North America"
    if c == "SA" or (c == "NA"): return "Latin America & Caribbean"
    if c == "AF": return "Sub-Saharan Africa"
    if c in ("AS", "OC"): return "East Asia & Pacific"
    return None
names = {}
for cc, v in cinfo.items():
    if region(cc): names[v["name"].lower()] = cc
for cc, ws in SHORT.items():
    for w in ws: names[w] = cc
for l in open(GEO + "cities15000.txt"):
    f = l.split("\t")
    if len(f) > 14 and f[14].isdigit() and int(f[14]) >= 1000000 and f[8] in cinfo and region(f[8]): names.setdefault(f[1].lower(), f[8])
for amb in ("georgia", "jordan", "turkey", "chad", "guinea", "niger", "mali", "oman", "peru", "washington", "victoria", "lima", "paris", "jersey", "santiago", "monaco", "cuba"): pass
AMB = {"georgia", "jordan", "chad", "guinea", "niger", "mali", "washington", "victoria", "jersey", "santiago", "lima"}   # names that are also common non-place words or US places; dropped
for a in AMB: names.pop(a, None)
PAT = re.compile(r"\b(" + "|".join(sorted((re.escape(n) for n in names), key=len, reverse=True)) + r")\b", re.I)
L = "/workspace/data/newsreader/labels/"; ans = {}
for f in ("calibration-1000.jsonl", "t144_read.jsonl"):
    for l in open(L + f):
        r = json.loads(l); a = r.get("answers_call1", {}).get("place_region")
        if a and a.get("choice"): ans[r["id"]] = a["choice"].strip()
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); rows = []
for i, ch in ans.items():
    q = db.execute("select title, body from items where id=?", (i,)).fetchone()
    if not q or not q[1]: continue
    cnt = collections.Counter(names[m.lower()] for m in PAT.findall((q[0] or "") + ". " + q[1]))
    tot = sum(cnt.values()); truth = None
    if tot >= 2:
        cc, n = cnt.most_common(1)[0]
        if n / tot >= 0.6: truth = region(cc)
    rows.append({"id": i, "jev": ch, "truth": truth, "mentions": tot})
dec = [r for r in rows if r["truth"]]; ok = sum(r["jev"] == r["truth"] for r in dec)
conf = collections.Counter((r["truth"], r["jev"]) for r in dec if r["jev"] != r["truth"])
res = {"stories_with_body": len(rows), "decidable": len(dec), "accuracy": round(ok / len(dec), 3) if dec else None,
       "truth_mix": dict(collections.Counter(r["truth"] for r in dec)), "jev_global_share_of_decidable": round(sum(r["jev"] == "GLOBAL" for r in dec) / max(len(dec), 1), 3),
       "top_errors": [[a, b, c] for (a, b), c in conf.most_common(6)]}
json.dump(res, open(OUT / "t167_place_judge.json", "w"), indent=1); print(json.dumps(res, indent=1))
