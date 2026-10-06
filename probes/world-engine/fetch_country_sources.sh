#!/bin/bash
# Fetches the raw public data that build_countries100.py reads (kept out of git: third-party data, 43 MB).
# UN World Population Prospects 2024 (CC BY 3.0 IGO) and World Bank open data (CC BY 4.0). Run from anywhere, then: python3 -I build_countries100.py
set -e
R="$(cd "$(dirname "$0")" && pwd)/data/sources_raw"; mkdir -p "$R/un_wpp"
curl -s -m 300 -o "$R/un_wpp/wpp2024.csv.gz" "https://population.un.org/wpp/assets/Excel%20Files/1_Indicator%20(Standard)/CSV_FILES/WPP2024_Demographic_Indicators_Medium.csv.gz" && gunzip -kf "$R/un_wpp/wpp2024.csv.gz"
for ind in SP.POP.TOTL SP.URB.TOTL.IN.ZS NY.GDP.PCAP.PP.CD IT.NET.USER.ZS SP.POP.65UP.TO.ZS SP.POP.0014.TO.ZS; do
  curl -s -m 60 "https://api.worldbank.org/v2/country/all/indicator/$ind?format=json&per_page=20000&date=2019:2024&mrnev=1" -o "$R/wb_$ind.json"; done
curl -s -m 60 "https://api.worldbank.org/v2/country?format=json&per_page=400" -o "$R/wb_countries.json"
echo "fetched into $R"
