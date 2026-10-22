"""Significance parts from headline + description, CPU only (T-0015, D-0016): reach in people, reach in places, magnitude, incident vs measured trend.

No LLM. spaCy entities + word lists. Output per story: the parts, the words that triggered them, and a size band (small / medium / large).
  models/nlp-venv/bin/python newsreader/bitmob/significance.py <stories.jsonl> <out.jsonl>
"""
import json, re, sys, time
import spacy

ONE = re.compile(r"\b(a|one|an|single|lone)\s+(man|woman|boy|girl|teen(ager)?|person|driver|pastor|singer|player|officer|suspect|victim|mother|father|child|lawyer|student|resident|worker|patient)\b", re.I)
FEW = re.compile(r"\b(two|three|four|five|six|seven|eight|nine|ten|couple|pair|family|\d)\s+(people|men|women|children|officers|workers|victims|suspects|residents|patients|students|drivers|soldiers)\b", re.I)
MANY = re.compile(r"\b(dozens|hundreds|scores|thousands|millions|billions|tens of thousands|hundreds of thousands)\b|\b\d{2,}(,\d{3})*\s+(people|jobs|homes|workers|residents|cases|deaths|families|students|patients)\b", re.I)
WIDE = re.compile(r"\b(nationwide|national|across (the )?(country|nation|region|europe|asia|africa|world|\w+)|countrywide|worldwide|global(ly)?|international(ly)?|economy|economies|markets|sector|industry-wide|population|all \w+ (residents|citizens|workers))\b", re.I)
NARROW = re.compile(r"\b(pub|bar|school|arena|club|church|street|neighbou?rhood|village|town|home|house|flat|apartment|hospital ward|campus|store|shop|restaurant)\b", re.I)
CHANGE = re.compile(r"\b(rise[sn]?|rose|rising|fall(s|en|ing)?|fell|up|down|surge[sd]?|jump(s|ed)?|drop(s|ped)?|cut[s]?|increase[sd]?|decrease[sd]?|climb(s|ed)?|slump(s|ed)?|plunge[sd]?|soar(s|ed)?|double[sd]?|halve[sd]?|grow(s|n)?|grew|shrink(s)?|shrank)\b", re.I)
TREND = re.compile(r"\b(rate[sd]?|figures|statistics|data (show|shows|showed)|year[- ]on[- ]year|annual(ly)?|quarter(ly)?|record (high|low)|highest since|lowest since|survey|index|inflation|average|per cent|percent|trend|official (data|figures)|census|report(s|ed)? (shows?|finds?|found))\b", re.I)
INCIDENT = re.compile(r"\b(jailed|sentenced|charged|arrested|accused|killed|stabbed|shot|died|crash(ed)?|fire|attack(ed)?|kidnapp(ed|ing)|robbed|injured|rescued|missing|glassing|assault(ed)?|fined|sued)\b", re.I)


def parts(nlp, text):
    doc = nlp(text); hit = lambda rx: [m.group(0) for m in rx.finditer(text)]
    ents = [(e.label_, e.text) for e in doc.ents]
    mag = [t for l, t in ents if l in ("PERCENT", "MONEY")]; places = {t for l, t in ents if l == "GPE"}
    p = {"one": hit(ONE), "few": hit(FEW), "many": hit(MANY), "wide": hit(WIDE), "narrow": hit(NARROW),
         "magnitude": mag, "change": hit(CHANGE), "trend": hit(TREND), "incident": hit(INCIDENT), "places": sorted(places)}
    people = "many" if p["many"] else "few" if p["few"] else "one" if p["one"] else "unknown"
    scale = "wide" if p["wide"] or len(places) >= 3 else "narrow" if p["narrow"] else "unknown"
    measured = bool((p["magnitude"] and p["change"]) or p["trend"])
    if people == "many" or scale == "wide" or measured: band = "large" if (people == "many" and (scale == "wide" or measured)) or (scale == "wide" and measured) else "medium"
    elif p["incident"] or people in ("one", "few") or scale == "narrow": band = "small"
    else: band = "medium"
    return {"people": people, "scale": scale, "measured_change": measured, "incident": bool(p["incident"]), "band": band, "evidence": {k: v for k, v in p.items() if v}}


def main(src, dst):
    nlp = spacy.load("en_core_web_sm", disable=["lemmatizer"]); rows = [json.loads(l) for l in open(src)]; t0 = time.perf_counter()
    with open(dst, "w") as f:
        for r in rows:
            f.write(json.dumps({"n": r.get("n"), "id": r["id"], **parts(nlp, f"{r['title']}. {(r.get('description') or '')[:250]}")}, ensure_ascii=False) + "\n")
    print(f"{len(rows)} stories, {1000 * (time.perf_counter() - t0) / len(rows):.1f} ms/story -> {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
