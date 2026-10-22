"""Country script checker (T-0012, D-0014): which of the ontology's 100 countries a headline+description mentions, how, and where.

No LLM. Gazetteer (names, aliases, demonyms, capitals, GeoNames cities >= 15k, first-level regions) + spaCy NER.
Place-like words outside the 100 go to out_of_list; words the script cannot settle go to review (for the Opus reviewer).

  models/nlp-venv/bin/python newsreader/bitmob/country_check.py data/jury/pilot50/stories.jsonl data/jury/pilot50/country-script.jsonl
"""
import json, re, sys, time
import spacy

ONT = "/workspace/exports/world-engine-ontology.yaml"; GEO = "/workspace/data/geo"

# Aliases and demonyms for the 100 (hand list; names from the ontology and GeoNames are added below).
EXTRA = {
    "ind": "Indian,Indians", "chn": "Chinese,PRC,Beijing's", "usa": "US,U.S.,USA,U.S.A.,America,American,Americans,United States of America,Washington,White House,Pentagon,NYC",
    "idn": "Indonesian,Indonesians", "pak": "Pakistani,Pakistanis", "nga": "Nigerian,Nigerians", "bra": "Brazilian,Brazilians",
    "bgd": "Bangladeshi,Bangladeshis", "rus": "Russian,Russians,Kremlin,Russian Federation", "eth": "Ethiopian,Ethiopians",
    "mex": "Mexican,Mexicans", "jpn": "Japanese", "egy": "Egyptian,Egyptians", "phl": "Philippine,Filipino,Filipinos,Filipina",
    "cod": "DRC,DR Congo,D.R. Congo,Congolese,Congo-Kinshasa", "vnm": "Vietnamese,Viet Nam", "irn": "Iranian,Iranians,Tehran's",
    "tur": "Turkey,Turkish,Turks,Turkiye", "deu": "German,Germans", "tha": "Thai,Thais", "gbr": "UK,U.K.,Britain,Great Britain,British,Briton,Britons,England,English,Scotland,Scottish,Wales,Welsh,Northern Ireland,Downing Street",
    "tza": "Tanzanian,Tanzanians", "fra": "French,Élysée", "zaf": "South African,South Africans", "ita": "Italian,Italians",
    "ken": "Kenyan,Kenyans", "mmr": "Burma,Burmese,Myanmar's", "col": "Colombian,Colombians", "kor": "South Korean,South Koreans,Republic of Korea,ROK,SKorea,S. Korea,Seoul's",
    "sdn": "Sudanese", "uga": "Ugandan,Ugandans", "esp": "Spanish,Spaniard,Spaniards", "dza": "Algerian,Algerians", "irq": "Iraqi,Iraqis",
    "arg": "Argentine,Argentinian,Argentinians", "afg": "Afghan,Afghans", "yem": "Yemeni,Yemenis", "can": "Canadian,Canadians,Sask.,B.C.",
    "pol": "Polish,Pole,Poles", "mar": "Moroccan,Moroccans", "ago": "Angolan,Angolans", "ukr": "Ukrainian,Ukrainians",
    "uzb": "Uzbek,Uzbeks", "mys": "Malaysian,Malaysians", "moz": "Mozambican,Mozambicans", "gha": "Ghanaian,Ghanaians",
    "per": "Peruvian,Peruvians", "sau": "Saudi,Saudis", "mdg": "Malagasy", "civ": "Côte d'Ivoire,Cote d'Ivoire,Ivorian,Ivorians",
    "npl": "Nepali,Nepalese", "cmr": "Cameroonian,Cameroonians", "ven": "Venezuelan,Venezuelans", "ner": "Nigerien,Nigeriens",
    "aus": "Australian,Australians,Aussie", "prk": "North Korean,North Koreans,DPRK,NKorea,N. Korea,Pyongyang's", "syr": "Syrian,Syrians",
    "mli": "Malian,Malians", "bfa": "Burkinabe,Burkinabè", "twn": "Taiwanese", "lka": "Sri Lankan,Sri Lankans",
    "mwi": "Malawian,Malawians", "zmb": "Zambian,Zambians", "kaz": "Kazakh,Kazakhs,Kazakhstani", "tcd": "Chadian,Chadians",
    "chl": "Chilean,Chileans", "rou": "Romanian,Romanians", "som": "Somali,Somalis", "sen": "Senegalese",
    "gtm": "Guatemalan,Guatemalans", "nld": "Dutch,Holland", "ecu": "Ecuadorian,Ecuadorians", "khm": "Cambodian,Cambodians",
    "zwe": "Zimbabwean,Zimbabweans", "gin": "Guinean,Guineans", "ben": "Beninese", "rwa": "Rwandan,Rwandans",
    "bdi": "Burundian,Burundians", "bol": "Bolivian,Bolivians", "tun": "Tunisian,Tunisians", "ssd": "South Sudanese",
    "hti": "Haitian,Haitians", "bel": "Belgian,Belgians", "jor": "Jordanian,Jordanians", "dom": "Dominican Republic's",
    "are": "UAE,U.A.E.,Emirati,Emiratis,Emirates", "cub": "Cuban,Cubans", "hnd": "Honduran,Hondurans", "cze": "Czech Republic,Czech,Czechs",
    "swe": "Swedish,Swede,Swedes", "tjk": "Tajik,Tajiks", "png": "PNG", "prt": "Portuguese", "aze": "Azerbaijani,Azerbaijanis,Azeri",
    "grc": "Greek,Greeks", "hun": "Hungarian,Hungarians", "tgo": "Togolese", "isr": "Israeli,Israelis", "aut": "Austrian,Austrians",
    "blr": "Belarusian,Belarusians",
}
# Words that are also everyday words or names: a hit is kept but sent to review unless spaCy calls it a place or nationality.
AMBIG = {"Chad", "Jordan", "Turkey", "Guinea", "Niger", "Georgia", "Washington", "Emirates", "Pole", "Poles", "English", "Dutch",
         "Chinese", "Japanese", "French", "Greek", "Swedish", "Polish", "Turkish", "Spanish", "Portuguese", "German"}
LANG_AMBIG = {"English", "Dutch", "Chinese", "Japanese", "French", "Greek", "Swedish", "Polish", "Turkish", "Spanish", "Portuguese", "German"}


def ontology_countries():
    out, on = {}, False
    for line in open(ONT):
        if re.match(r"^  countries:", line): on = True; continue
        if on:
            m = re.match(r"^    ([a-z]{3}): (.+?)\s*$", line)
            if not m: break
            out[m[1]] = m[2]
    return out


OUT_ALIAS = {"NZ": "nzl", "N.Z.": "nzl", "Kiwi": "nzl", "Irish": "irl", "Swiss": "che", "Danish": "dnk", "Dane": "dnk", "Singaporean": "sgp"}


def build():
    C = ontology_countries(); assert len(C) == 100, len(C)
    info = [l.rstrip("\n").split("\t") for l in open(f"{GEO}/countryInfo.txt") if not l.startswith("#")]
    iso2 = {r[0]: r[1].lower() for r in info}; allnames = {r[4]: r[1].lower() for r in info}
    G = {}  # surface -> (iso3, how)
    def put(s, iso, how):
        if s and s not in G: G[s] = (iso, how)
    for iso, name in C.items(): put(name, iso, "name")
    for r in info:
        if r[1].lower() in C: put(r[4], r[1].lower(), "name"); put(r[5], r[1].lower(), "capital")
    for iso, s in EXTRA.items():
        for w in s.split(","): put(w.strip(), iso, "demonym" if w[:1].isupper() and w.endswith(("an", "ans", "ese", "i", "is", "ish", "ch", "k", "ks", "ian", "ians")) else "name")
    # Most populous city of each name wins; names shared by two big cities in different countries go to review.
    cities, clash = {}, set()
    for l in open(f"{GEO}/cities15000.txt"):
        f = l.split("\t"); nm, iso, pop = f[1], iso2.get(f[8], ""), int(f[14] or 0)
        for s in {nm, f[2]}:
            if s in cities and cities[s][0] != iso and min(pop, cities[s][1]) >= 100_000: clash.add(s)
            if s not in cities or pop > cities[s][1]: cities[s] = (iso, pop)
    adm = {}
    for l in open(f"{GEO}/admin1CodesASCII.txt"):
        code, nm, asc = l.split("\t")[:3]; iso = iso2.get(code.split(".")[0], "")
        for s in {nm, asc}: adm.setdefault(s, iso)
    return C, G, cities, clash, adm, allnames


def scan(nlp, B, title, desc):
    C, G, cities, clash, adm, allnames = B
    hits, out, review = {}, [], []
    for where, text in (("headline", title), ("description", desc)):
        text = re.sub(r"\b[A-Z]{4,}\b", lambda m: m[0].title(), text)  # all-caps datelines: SINGAPORE -> Singapore
        for s, iso in OUT_ALIAS.items():
            if re.search(r"(?<![\w'])" + re.escape(s) + r"(?![\w])", text): out.append({"surface": s, "iso3": iso, "where": where})
        doc = nlp(text); ents = {(e.start_char, e.end_char): e.label_ for e in doc.ents}
        spans = []
        for s, (iso, how) in G.items():  # longest surface first so "South Sudan" beats "Sudan"
            for m in re.finditer(r"(?<![\w'])" + re.escape(s) + r"(?![\w])", text): spans.append((m.start(), m.end(), s, iso, how))
        spans.sort(key=lambda x: (x[0], -(x[1] - x[0]))); taken = []
        for a, b, s, iso, how in spans:
            if any(a < tb and b > ta for ta, tb in taken): continue
            taken.append((a, b)); lab = next((l for (ea, eb), l in ents.items() if ea <= a and b <= eb), None)
            if s in AMBIG and lab not in ("GPE", "NORP", "LOC"):
                review.append({"surface": s, "iso3": iso, "where": where, "reason": "ambiguous word, not tagged as place", "ner": lab}); continue
            if s in LANG_AMBIG and lab == "LANGUAGE": continue
            hits.setdefault(iso, []).append({"how": how, "where": where, "surface": s})
        # Places spaCy sees that the gazetteer did not cover: cities, regions, other countries.
        for (a, b), lab in ents.items():
            if lab not in ("GPE", "LOC") or any(a < tb and b > ta for ta, tb in taken): continue
            s = text[a:b].removeprefix("the ").strip()
            if s in allnames and allnames[s] not in C: out.append({"surface": s, "iso3": allnames[s], "where": where}); continue
            # A first-level region beats a smaller town of the same name (Tuscany is Italy's, not a Canadian town's).
            if s in adm and not (s in cities and cities[s][1] >= 1_000_000): iso, how = adm[s], "region"
            elif s in cities: iso, how = cities[s][0], "city"
            else: iso, how = None, None
            if iso is None: review.append({"surface": s, "where": where, "reason": "place not found in GeoNames", "ner": lab}); continue
            if s in clash: review.append({"surface": s, "iso3": iso, "where": where, "reason": "city name shared by big cities in several countries", "ner": lab}); continue
            if iso in C: hits.setdefault(iso, []).append({"how": how, "where": where, "surface": s})
            else: out.append({"surface": s, "iso3": iso, "where": where})
    return hits, out, review


def main(src, dst):
    nlp = spacy.load("en_core_web_sm", disable=["lemmatizer"]); B = build()
    rows = [json.loads(l) for l in open(src)]; t0 = time.perf_counter()
    with open(dst, "w") as f:
        for r in rows:
            t = time.perf_counter(); hits, out, review = scan(nlp, B, r["title"], r["description"][:250])
            f.write(json.dumps({"n": r["n"], "id": r["id"], "countries": sorted(hits), "mentions": hits, "out_of_list": out,
                                "review": review, "ms": round(1000 * (time.perf_counter() - t), 1)}, ensure_ascii=False) + "\n")
    print(f"{len(rows)} stories, {1000 * (time.perf_counter() - t0) / len(rows):.1f} ms/story -> {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
