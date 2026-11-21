"""Build specs/demonyms_wordnet_v0.json: country adjectives and people-nouns (Cuban, Cubans, Briton) from the Princeton WordNet files already in data/ontology_src/wordnet.
Rule: an adjective synset with a pertainym pointer (\\) to a noun synset whose lemma is a GeoNames country name or an ALIAS country; the adjective lemmas are demonyms, and so are the lemmas of derivation-linked noun synsets
glossed 'a native or inhabitant of'. Plurals add -s only for the people nouns (Cuban -> Cubans). Not hand-typed; unmeasured as a list beyond the place_val run.
    /workspace/models/embed-zs/.venv/bin/python build-demonyms.py"""
import json, re, hashlib, collections
WN = "/workspace/data/ontology_src/wordnet/wordnet/"
def synsets(fn):
    out = {}
    for l in open(WN + fn, encoding="utf-8"):
        if l.startswith("  "): continue
        h, _, gloss = l.partition(" | "); f = h.split(); wc = int(f[3], 16); words = [f[4 + 2 * i].replace("_", " ") for i in range(wc)]; i = 4 + 2 * wc; pc = int(f[i]); ptr = [tuple(f[i + 1 + 4 * k:i + 5 + 4 * k]) for k in range(pc)]
        out[f[0]] = {"words": words, "ptr": ptr, "gloss": gloss.strip()}
    return out
adj, noun = synsets("data.adj"), synsets("data.noun")
ctry = {}; POP = {}
for l in open("/workspace/data/geo/countryInfo.txt", encoding="utf-8"):
    if l[0] != "#": f = l.rstrip("\n").split("\t"); ctry[f[4]] = f[0]; POP[f[0]] = int(f[7] or 0)
import sys; sys.path.insert(0, "."); 
src = open("extract.py").read(); m = re.search(r"^ALIAS = (\{.*?\})\n[A-Z]", src, re.S | re.M); ALIAS = eval(m.group(1))
CT = {**ctry, **{k: v for k, v in ALIAS.items() if k not in ("Washington", "White House", "Capitol Hill", "Ohio", "Gaza", "West Bank") and len(v) == 2 and not k.endswith(".")}}
dem = collections.defaultdict(set)   # surface -> {iso2}
for off, s in adj.items():
    for sym, to, pos, st in s["ptr"]:
        if sym != "\\" or pos != "n": continue
        iso = {CT[w] for w in noun.get(to, {}).get("words", []) if w in CT}
        for w in s["words"]:
            if w[:1].isupper():
                for c in iso: dem[w].add(c)
        for sy2, to2, pos2, st2 in s["ptr"]:
            if sy2 == "+" and pos2 == "n" and to2 in noun and noun[to2]["gloss"].lower().startswith(("a native", "a resident", "an inhabitant", "a person who is a native")):
                for w in noun[to2]["words"]:
                    if w[:1].isupper():
                        for c in iso: dem[w].add(c); dem[w + "s"].add(c)
rows = {k: sorted(v) for k, v in sorted(dem.items())}
amb = {k: v for k, v in rows.items() if len(v) > 1}
spec = {"name": "demonyms_wordnet_v0", "label": "demonym v0 from WordNet pertainyms, unmeasured", "source": "Princeton WordNet (data.adj, data.noun) in data/ontology_src/wordnet; country names from data/geo/countryInfo.txt + extract.ALIAS", "n": len(rows), "ambiguous_resolved_by_population": sorted(amb), "tie_break": "several countries: the most populous (countryInfo population)", "map": {k: max(v, key=lambda c: POP.get(c, 0)) for k, v in rows.items()}}
json.dump(spec, open("specs/demonyms_wordnet_v0.json", "w"), indent=0, sort_keys=True); print(len(spec["map"]), "demonyms; ambiguous", sorted(amb)); print({k: spec["map"].get(k) for k in "Cuban Cubans American Americans British Briton Nigerian Chinese Israeli Iranian Russian French Dutch Irish Georgian Indian Turkish Ukrainian".split()})
