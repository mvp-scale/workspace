"""Builds data/countries_top100.csv: the 100 most populous countries with real indicators and a source on every column.
Population and median age: UN World Population Prospects 2024 (medium variant, year 2024). Urban share, GDP per person (PPP), internet use, ages 65+:
World Bank open data, latest value 2019-2024 (the year is kept per column). Nothing here is estimated; a missing value stays blank. Run: python3 -I build_countries100.py"""
import csv, json, os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"); R = os.path.join(D, "sources_raw")
un = {}
for r in csv.DictReader(open(os.path.join(R, "un_wpp", "wpp2024.csv"), encoding="utf-8-sig")):
    if r["Time"] == "2024" and r["LocTypeName"] == "Country/Area" and r["ISO3_code"]: un[r["ISO3_code"]] = r
def wb(ind):
    d = json.load(open(os.path.join(R, f"wb_{ind}.json")))[1]; out = {}
    for x in d:
        if x["countryiso3code"] and x["value"] is not None: out[x["countryiso3code"]] = (x["value"], x["date"])
    return out
IND = {"urban": "SP.URB.TOTL.IN.ZS", "gdp_pc_ppp": "NY.GDP.PCAP.PP.CD", "internet": "IT.NET.USER.ZS", "age65": "SP.POP.65UP.TO.ZS", "age0_14": "SP.POP.0014.TO.ZS"}
W = {k: wb(v) for k, v in IND.items()}
top = sorted(un.values(), key=lambda r: -float(r["TPopulation1July"]))[:100]
cols = ["id", "iso3", "name", "pop_m", "median_age", "urban", "gdp_pc_ppp_k", "internet", "age65", "age0_14", "source"]
rows = []
for r in top:
    i = r["ISO3_code"]; g = lambda k: W[k].get(i)
    rows.append({"id": i.lower(), "iso3": i, "name": r["Location"], "pop_m": round(float(r["TPopulation1July"]) / 1000, 1), "median_age": round(float(r["MedianAgePop"]), 1),
                 "urban": round(g("urban")[0] / 100, 3) if g("urban") else "", "gdp_pc_ppp_k": round(g("gdp_pc_ppp")[0] / 1000, 1) if g("gdp_pc_ppp") else "",
                 "internet": round(g("internet")[0] / 100, 3) if g("internet") else "", "age65": round(g("age65")[0] / 100, 3) if g("age65") else "", "age0_14": round(g("age0_14")[0] / 100, 3) if g("age0_14") else "",
                 "source": "UN WPP 2024 (population, median age, year 2024); World Bank WDI latest 2019-2024 (urban SP.URB.TOTL.IN.ZS, GDP/person PPP NY.GDP.PCAP.PP.CD, internet IT.NET.USER.ZS, ages 65+ SP.POP.65UP.TO.ZS, ages 0-14 SP.POP.0014.TO.ZS)"})
w = csv.DictWriter(open(os.path.join(D, "countries_top100.csv"), "w", newline=""), fieldnames=cols); w.writeheader(); w.writerows(rows)
tot = sum(float(x["TPopulation1July"]) for x in un.values()) / 1000
print(f"{len(rows)} countries, {sum(r['pop_m'] for r in rows):,.0f} M of {tot:,.0f} M people ({sum(r['pop_m'] for r in rows) / tot:.1%}); smallest: {rows[-1]['name']} {rows[-1]['pop_m']} M")
for c in ("urban", "gdp_pc_ppp_k", "internet", "age65", "age0_14"): print(c, "missing:", [r["name"] for r in rows if r[c] == ""])

# ---- engine input: data/countries_world100.csv (same columns the population builder reads, plus iso2/iso3). Rules, all visible here:
#  income_k  = 0.6 x GDP per person (PPP, thousands). 0.6 is the average ratio of our earlier eight countries' typical-person income to their GDP per person (range 0.3 to 0.8): a rule, not a measurement.
#  tech      = 2.4 + 1.6 x internet-use share (so 2.4 to 4.0): internet use is real data.
#  privacy, social, time, novelty, price = 3.0 ("world default"): no real series is wired in yet.
#  d_* (starting level of each world condition) = 0 except the United States, whose values came from public indices read 2026-10-04 (kept from the earlier file). Nothing else is invented.
#  Any missing real value is filled with the median of the other countries and listed in the source column.
import statistics, statistics as st
old = {r["id"]: r for r in csv.DictReader(open(os.path.join(D, "countries_8.csv")))}
iso2 = {x["id"]: x["iso2Code"] for x in json.load(open(os.path.join(R, "wb_countries.json")))[1]}; iso2["TWN"] = "TW"
region_of = {x["id"]: x["region"]["value"] for x in json.load(open(os.path.join(R, "wb_countries.json")))[1]}
SHORT = {"United States of America": "United States", "China, Taiwan Province of China": "Taiwan", "Viet Nam": "Vietnam", "Iran (Islamic Republic of)": "Iran", "Dem. Republic of the Congo": "DR Congo", "Republic of Korea": "South Korea",
         "Dem. People's Republic of Korea": "North Korea", "Russian Federation": "Russia", "United Republic of Tanzania": "Tanzania", "Bolivia (Plurinational State of)": "Bolivia", "Venezuela (Bolivarian Republic of)": "Venezuela",
         "Syrian Arab Republic": "Syria", "Lao People's Democratic Republic": "Laos", "Republic of Moldova": "Moldova", "China, Hong Kong SAR": "Hong Kong", "State of Palestine": "Palestine", "Czechia": "Czechia", "Côte d'Ivoire": "Ivory Coast"}
med = {c: st.median(float(r[c]) for r in rows if r[c] != "") for c in ("urban", "gdp_pc_ppp_k", "internet")}
OUTCOLS = ["id", "iso2", "iso3", "region", "name", "pop_m", "median_age", "income_k", "urban", "tech", "privacy", "social", "time", "novelty", "price"] + [k for k in next(iter(old.values())) if k.startswith("d_")] + ["source"]
out = []
for r in rows:
    filled = [c for c, key in (("urban", "urban"), ("gdp_pc_ppp_k", "gdp_pc_ppp_k"), ("internet", "internet")) if r[key] == ""]
    u = float(r["urban"]) if r["urban"] != "" else med["urban"]; g = float(r["gdp_pc_ppp_k"]) if r["gdp_pc_ppp_k"] != "" else med["gdp_pc_ppp_k"]; it = float(r["internet"]) if r["internet"] != "" else med["internet"]
    row = {"id": r["id"], "iso2": iso2.get(r["iso3"], ""), "iso3": r["iso3"], "region": region_of.get(r["iso3"], "East Asia & Pacific"), "name": SHORT.get(r["name"], r["name"]), "pop_m": r["pop_m"], "median_age": r["median_age"], "income_k": round(0.6 * g, 2), "urban": round(u, 3),
           "tech": round(2.4 + 1.6 * min(1, max(0, it)), 2), "privacy": 3.0, "social": 3.0, "time": 3.0, "novelty": 3.0, "price": 3.0}
    usa = old.get("usa") if r["iso3"] == "USA" else None
    for k in OUTCOLS:
        if k.startswith("d_"): row[k] = usa[k] if usa else 0.0
    row["source"] = "UN WPP 2024 + World Bank WDI; income_k=0.6 x GDP per person PPP (rule); tech=2.4+1.6 x internet use; other traits world default 3.0" + (f"; filled from median: {', '.join(filled)}" if filled else "") + ("; dial levels from public indices 2026-10-04" if usa else "; dial levels 0 (no data wired)")
    out.append(row)
w2 = csv.DictWriter(open(os.path.join(D, "countries_world100.csv"), "w", newline=""), fieldnames=OUTCOLS); w2.writeheader(); w2.writerows(out)
print("engine file written:", len(out), "rows;", sum(1 for o in out if "filled from median" in o["source"]), "with a filled value")
