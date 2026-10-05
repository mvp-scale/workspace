"""Seeded in-memory persona generator. gen(seed) is a pure function: same seed, same persona, nothing on disk.

Each persona has hidden latent traits (1 to 5, the ground truth we later check the extractor against), structured
attributes, and a rendered profile (backstory, worldview, current beliefs, aspiration). The profile is written in
varied everyday phrasing; it never uses the extractor's question wording.
"""
import random

TRAITS = ["tech", "price", "privacy", "social", "time", "novelty"]  # latent, 1 to 5
AGE_BANDS = [(18, 29), (30, 44), (45, 59), (60, 74), (75, 90)]
AREAS = ["large city", "suburb", "small town", "rural area"]
REGIONS = ["Northeast", "South", "Midwest", "West"]
INCOMES = ["under $30,000", "$30,000 to $60,000", "$60,000 to $100,000", "over $100,000"]
ASPIRATIONS = {
    "security": "to feel financially secure and never worry about a surprise bill",
    "career": "to move up in their career and be recognised for it",
    "freedom": "to stay independent and make their own choices",
    "family": "to be close to family and be there for them",
    "health": "to stay healthy for as long as possible",
    "community": "to be part of a community that looks out for each other",
    "learning": "to keep learning new things and trying new experiences",
}
WORLDVIEWS = {
    "self_reliant": "believes people do best when they rely on themselves and keep things simple",
    "communal": "believes people do best when they look after each other and share what they have",
    "traditional": "believes the older, proven ways of doing things are usually the best ones",
    "progressive": "believes new ideas and new tools usually make life better",
    "skeptical": "believes companies and institutions mostly look after themselves first",
}
PH = {  # latent trait -> phrasings by level (1 low .. 5 high); 2 and 4 reuse neighbours
    "tech": {1: ["still prints directions and pays by cheque", "gets flustered when a phone updates itself", "keeps an old flip phone and prefers calling"],
             3: ["uses a phone for messages, maps and a few apps", "can follow a new app if someone shows them once"],
             5: ["tries every new app and fixes the family's devices", "reads about gadgets and automates things at home"]},
    "price": {1: ["rarely checks what things cost", "pays for convenience without thinking much"],
              3: ["compares prices on bigger purchases", "keeps a rough monthly budget"],
              5: ["tracks every dollar and cancels subscriptions that are not used", "waits for sales and counts the cost of small monthly fees"]},
    "privacy": {1: ["shares freely online and does not mind being tracked", "uses one password and clicks accept without reading"],
                3: ["cautious about what they hand over but not strict", "reads settings on the apps that hold money"],
                5: ["covers webcams, avoids sharing ID and distrusts apps that ask for personal details", "refuses to give a face photo or ID unless the law requires it"]},
    "social": {1: ["prefers quiet evenings and a small circle", "dislikes dealing with people they do not know"],
               3: ["sees friends now and then and knows some neighbours", "comfortable in groups but does not seek them out"],
               5: ["always organising something and knows everyone on the street", "gets energy from meeting new people"]},
    "time": {1: ["has long open afternoons", "flexible days with little pressure"],
             3: ["a steady routine with some spare evenings", "busy weeks but free weekends"],
             5: ["every hour of the day is taken by work and caring duties", "rarely has more than ten spare minutes"]},
    "novelty": {1: ["sticks to the same shops, brands and routines", "wary of anything that is new and unproven"],
                3: ["will try something new if a friend recommends it", "open to change when there is a clear reason"],
                5: ["first in line to try new things", "bored by routine and always looking for something different"]},
}
BELIEF = {"tech": "Technology is {}.", "price": "Money is {}.", "privacy": "Personal data is {}.",
          "social": "Strangers are {}.", "time": "Free time is {}.", "novelty": "New things are {}."}
BELIEF_WORDS = {  # level 1..5 words
    "tech": ["a hassle to be avoided", "mostly more trouble than it is worth", "useful when it is simple", "generally helpful", "exciting and worth learning"],
    "price": ["not something to fret about", "a minor consideration", "worth watching on big items", "something to watch closely", "the first thing to check on anything"],
    "privacy": ["not a big concern", "mostly fine to share", "worth some care", "something to guard", "something to protect at nearly any cost"],
    "social": ["best kept at a distance", "people to be careful with", "fine in small doses", "usually friendly", "a source of good things"],
    "time": ["plentiful", "mostly available", "limited but manageable", "scarce", "almost non-existent"],
    "novelty": ["a risk", "worth a careful look first", "fine if it is proven", "worth trying", "the best part of life"],
}


def _lvl(r, centre, spread=1.0):
    return max(1, min(5, round(r.gauss(centre, spread))))


def gen(seed):
    r = random.Random(seed * 7919 + 13)
    age = int(min(90, max(18, r.gauss(47, 18))))
    area = r.choices(AREAS, [3, 4, 2, 1.5])[0]
    region = r.choice(REGIONS)
    if age >= 65: work = r.choices(["retired", "part-time worker"], [8, 2])[0]
    else: work = r.choice(["student", "retail worker", "office worker", "nurse", "tradesperson", "teacher", "software developer", "self-employed", "manager", "unemployed", "stay-at-home parent"])
    if work == "student": age = min(age, 30)
    inc_c = {"student": 0.7, "retail worker": 1.0, "unemployed": 0.4, "retired": 1.6, "part-time worker": 1.2, "stay-at-home parent": 1.5,
             "software developer": 3.4, "manager": 3.2, "nurse": 2.4, "teacher": 2.2, "tradesperson": 2.3, "office worker": 2.2, "self-employed": 2.2}[work]
    income = INCOMES[max(0, min(3, round(r.gauss(inc_c, 0.8))))] if inc_c >= 0.7 else INCOMES[0]
    if age < 30 and work != "student": household = r.choice(["lives with housemates", "lives with parents", "lives alone", "lives with a partner"])
    elif age < 60: household = r.choice(["lives alone", "lives with a partner", "lives with a partner and children", "lives with a partner and children", "lives with housemates"])
    else: household = r.choice(["lives alone", "lives with a partner", "lives with a partner", "lives with an adult child"])
    caregiver = r.random() < (0.28 if 40 <= age <= 70 else 0.05)
    inc_i = INCOMES.index(income)
    lat = {"tech": _lvl(r, 5.0 - (age - 18) / 22 + (0.4 if work == "software developer" else 0), 0.9),
           "price": _lvl(r, 4.4 - inc_i * 0.9, 0.8),
           "privacy": _lvl(r, 3 + (age - 47) / 40, 1.1),
           "social": _lvl(r, 3 + (0.5 if area in ("small town", "rural area") else 0) - (0.4 if household == "lives alone" else 0), 1.1),
           "time": _lvl(r, 2.4 + (1.4 if household == "lives with a partner and children" else 0) + (1.0 if caregiver else 0) - (1.0 if work == "retired" else 0), 0.8),
           "novelty": _lvl(r, 4.2 - (age - 18) / 25, 1.0)}
    asp = r.choice(list(ASPIRATIONS)); wv = r.choice(list(WORLDVIEWS))
    ph = lambda t: r.choice(PH[t][1 if lat[t] <= 2 else 3 if lat[t] == 3 else 5])
    parts = [f"{age}-year-old, {work}, living in a {area} in the {region}, {household}, household income {income}."]
    if caregiver: parts.append("Looks after an older relative.")
    order = list(TRAITS); r.shuffle(order)
    parts.append("Day to day this person " + ph(order[0]) + ", " + ph(order[1]) + ", and " + ph(order[2]) + ".")
    parts.append("Also " + ph(order[3]) + " and " + ph(order[4]) + "; " + ph(order[5]) + ".")
    beliefs = " ".join(BELIEF[t].format(BELIEF_WORDS[t][lat[t] - 1]) for t in TRAITS[:])
    parts.append(f"Worldview: {WORLDVIEWS[wv]}. Current beliefs: {beliefs}")
    parts.append(f"Looking ahead, this person hopes {ASPIRATIONS[asp]}.")
    return {"seed": seed, "age": age, "work": work, "area": area, "region": region, "income": income, "household": household,
            "caregiver": caregiver, "latent": lat, "aspiration": asp, "worldview": wv, "profile": " ".join(parts)}


def age_band(age):
    return next(f"{a}-{b}" for a, b in AGE_BANDS if a <= age <= b)


def cohort(p):
    return (age_band(p["age"]), p["area"], p["income"])


if __name__ == "__main__":
    assert gen(5) == gen(5) and gen(5) != gen(6)
    print(gen(5)["profile"]); print(gen(6)["profile"])
    import collections
    c = collections.Counter(cohort(gen(s)) for s in range(10000))
    print("cohorts (age band x area x income) among 10,000:", len(c), "| smallest:", min(c.values()), "| >=30 members:", sum(1 for v in c.values() if v >= 30))
