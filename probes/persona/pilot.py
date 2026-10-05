"""Offline feasibility pilot: do persona-conditioned Winnow answers carry any audience signal?

    /workspace/kev/.venv/bin/python pilot.py [--n 100] [--seed 7]

Personas are sampled from attribute lists (no link to any product). Products are fixed below; the
expectations in EXPECT were written BEFORE the first run. Results: /workspace/data/persona-lab/pilot.jsonl
"""
import argparse, json, random, time, urllib.request
from pathlib import Path

OUT = Path("/workspace/data/persona-lab/pilot.jsonl")
ENDPOINT = "http://127.0.0.1:8091"

PRODUCTS = {
 "splitly": "Splitly is a free phone app for people who share a home. Each housemate links a bank card, the app splits rent, "
            "utilities and groceries automatically, and sends a chat reminder to anyone who has not paid after 3 days. "
            "It runs only as a phone app and works best when every housemate installs it.",
 "carecircle": "CareCircle is a large-screen tablet with large print, sold with a $15 monthly plan. It lists an older person's "
               "medications with an alarm for each dose, and sends a daily check-in to up to five family members. "
               "A nurse can be reached by video call from the same screen.",
 "universal": "StormText is a free service from the national weather agency. When a severe storm warning is issued for your "
              "address, you get one text message. No account, no ads, no app, and you can stop it by replying STOP.",
 "bad": "TimeBottle is a smart water bottle that shows the time on its lid. It costs $89 a month on a 24-month contract. "
        "It does not track water. To cancel, you mail a signed paper form and pay the remaining months.",
}
# written before the run
EXPECT = {"universal": "high for all", "bad": "low for all, universal - bad >= 0.3",
          "splitly": "age<35 higher than age>=55 by >= 0.15", "carecircle": "caregivers or age>=55 higher than age<35 by >= 0.15"}

FACETS = {"price": "the price", "effort": "the effort needed to start and keep using it",
          "relevance": "how much it applies to this person's daily life", "trust": "trust and privacy (money, health or personal data)"}


def sample_persona(r):
    age = int(min(88, max(18, r.gauss(46, 18))))
    p = {"age": age, "gender": r.choice(["woman", "man", "woman", "man", "non-binary"]),
         "area": r.choice(["large city", "large city", "suburb", "suburb", "small town", "rural area"]),
         "household": r.choice(["lives alone", "lives with a partner", "lives with housemates", "lives with partner and children",
                                "lives with parents", "lives with partner and children"] if age < 60 else
                               ["lives alone", "lives with a partner", "lives alone", "lives with a partner", "lives with an adult child"]),
         "work": r.choice(["student", "retail worker", "office worker", "nurse", "tradesperson", "teacher", "software developer",
                           "self-employed", "unemployed", "manager"] if age < 65 else ["retired", "retired", "retired", "part-time worker"]),
         "income": r.choice(["under $30,000", "$30,000 to $60,000", "$30,000 to $60,000", "$60,000 to $100,000", "over $100,000"]),
         "tech": r.choice(["uses new apps easily", "uses a few familiar apps", "avoids new technology"]),
         "cares_for_older_relative": r.random() < (0.25 if 40 <= age <= 70 else 0.07),
         "priority": r.choice(["saving money", "saving time", "safety of family", "privacy", "staying independent", "social life"])}
    return p


def render(p):
    s = (f"{p['age']}-year-old {p['gender']}, {p['work']}, lives in a {p['area']}, {p['household']}. Household income {p['income']}. "
         f"Technology: {p['tech']}. Top priority in life: {p['priority']}.")
    return s + (" Looks after an older relative." if p["cares_for_older_relative"] else "")


def questions():
    q = {"try": {"type": "noul", "instructions": "After reading the description, this person would try the product in the next month."},
         "take": {"type": "choice", "instructions": "What is this person's first reaction to the product?",
                  "criteria": {"try_it": "would try it", "skip_it": "would not try it", "need_more": "would ask for more information before deciding"}}}
    facet_opts = {k: v for k, v in FACETS.items()}
    q["delight"] = {"type": "choice", "instructions": "Which one aspect of the product counts most in its favour for this person?",
                    "criteria": {**{k: v for k, v in facet_opts.items()}, "none": "no aspect counts in its favour"}}
    q["frustration"] = {"type": "choice", "instructions": "Which one aspect of the product counts most against it for this person?",
                        "criteria": {**{k: v for k, v in facet_opts.items()}, "none": "no aspect counts against it"}}
    for k, v in FACETS.items():
        q[f"bad_{k}"] = {"type": "noul", "instructions": f"For this person, {v} is a reason not to use the product."}
    return q


def call(state, qs):
    body = {"model": "Winnow-12B", "state": state, "questions": qs}
    req = urllib.request.Request(ENDPOINT + "/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)["answers"]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=100); ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    r = random.Random(a.seed)
    people = [sample_persona(r) for _ in range(a.n)]
    qs = questions(); rows = []
    t0 = time.time()
    for pid, prod in PRODUCTS.items():
        for i, p in enumerate([None] + people):
            state = f"Product description:\n{prod}\n\n" + (f"Person reading it:\n{render(p)}" if p else "Person reading it: a typical adult.")
            try:
                ans = call(state, qs); err = None
            except Exception as e:
                ans, err = None, f"{type(e).__name__}: {e}"[:200]
            rows.append({"product": pid, "persona": i - 1, "attrs": p, "answers": ans, "error": err})
    OUT.write_text("\n".join(json.dumps(x, sort_keys=True) for x in rows) + "\n")
    print(f"{len(rows)} calls, {sum(1 for x in rows if x['error'])} errors, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
