"""Place reach test (pre-registered L1037): spaCy place entities linked by exact name to the GeoNames files in data/geo. Same 300 articles as extraction_inventory.py. Writes runs/harvest/place_reach.json.
    /workspace/models/embed-zs/.venv/bin/python place_reach.py   (from projects/world-state)"""
import json, re, random, collections, spacy
G = "/workspace/data/geo/"; ctry = {}; city = collections.defaultdict(set); adm = collections.defaultdict(set)
for l in open(G + "countryInfo.txt", encoding="utf-8"):
    if l[0] != "#": f = l.rstrip("\n").split("\t"); ctry[f[4]] = f[0]
for l in open(G + "cities15000.txt", encoding="utf-8"):
    f = l.split("\t"); city[f[1]].add(f[8]); city[f[2]].add(f[8])
for l in open(G + "admin1CodesASCII.txt", encoding="utf-8"):
    f = l.rstrip("\n").split("\t"); adm[f[1]].add(f[0].split(".")[0]); adm[f[2]].add(f[0].split(".")[0])
R = [r for r in map(json.loads, open("runs/harvest/sample.jsonl")) if len(r["text"] or "") >= 800]; random.Random(20261107).shuffle(R); R = R[:300]
nlp = spacy.load("en_core_web_sm"); has = 0; ctry_hit = 0; any_link = 0; cities_linked = 0; cities_amb = 0; miss = collections.Counter(); linked_kinds = collections.Counter(); n_places = 0
for r in R:
    d = nlp(re.sub(r"\s+", " ", (r["title"] or "") + ". " + r["text"])[:12000]); P = {x.text.strip() for x in d.ents if x.label_ in ("GPE", "LOC", "FAC")}; n_places += len(P)
    if P: has += 1
    cs = set(); lk = False
    for p in P:
        if p in ctry: cs.add(ctry[p]); lk = True; linked_kinds["country"] += 1
        elif p in adm: cs |= adm[p]; lk = True; linked_kinds["region"] += 1
        elif p in city:
            cities_linked += 1; cities_amb += len(city[p]) > 1; cs |= city[p]; lk = True; linked_kinds["city"] += 1
        else: miss[p] += 1
    any_link += lk; ctry_hit += bool(cs)
res = {"articles": len(R), "with_place_entity": has, "with_any_link": any_link, "with_country": ctry_hit, "places_per_article": round(n_places / len(R), 2), "linked_kinds": dict(linked_kinds), "city_links": cities_linked, "city_links_ambiguous": cities_amb, "top_unlinked": miss.most_common(25),
       "gazetteer": {"countries": len(ctry), "city_names": len(city), "region_names": len(adm)}}
json.dump(res, open("runs/harvest/place_reach.json", "w"), indent=1); print(json.dumps(res, indent=1)[:1800])
