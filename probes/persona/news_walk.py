import json, math
import offline as O
from world_model import *
ITEMS = [
 ("Cloaked in anonymity, Israeli soldiers describe mass civilian killings in 'NAZA'", "NAZA is an acronym for nezek agavi, Hebrew for 'collateral damage.'", "https://www.npr.org/2026/10/02/nx-s1-5987714/naza-review-israel-palestine"),
 ("The U.S. added only 29,000 jobs in September as job market lacks spark", "U.S. employers added 29,000 jobs in September as the unemployment rate inched up to 4.2%.", "https://www.npr.org/2026/10/02/nx-s1-5989140/jobs-labor-wages-federal-reserve"),
 ("Cornell rape case gets special prosecutor. And, Renee Good's family sues the government", "New legal action unfolds in two closely watched cases under investigation.", "https://www.npr.org/2026/10/02/g-s1-146075/up-first-newsletter-cornell-assault-case-christa-pike-jobs-report-renee-good"),
 ("Why is diesel more expensive than regular gas?", "A price shift occurred in 2004 due to air quality standards, market demand, and taxation changes.", "https://www.npr.org/sections/planet-money/2026/10/02/nx-s1-5988075/why-is-diesel-more-expensive-than-regular-gas"),
 ("San Francisco's car crime has plunged. How much credit does Flock deserve?", "AI-powered cameras helped drive a dramatic decline in car crime, while raising civil liberties concerns.", "https://www.npr.org/sections/planet-money/2026/10/02/g-s1-146060/san-franciscos-car-crime-has-plunged-how-much-credit-does-flock-deserve"),
]
Qs = questions(); names = list(Qs); out = []
for head, desc, url in ITEMS:
    P = {}
    for j in range(0, len(names), 20):
        a = O.call(f"News item:\n{head}. {desc}", {k: {"type": "noul", "instructions": Qs[k]} for k in names[j:j + 20]}); P.update({k: a[k]["noul"] for k in a})
    out.append({"headline": head, "desc": desc, "url": url, "p": P})
json.dump(out, open("/workspace/data/persona-lab/news_walk.json", "w"))
def attr_state(P, d, dirn, ai): m = (P[f"{d}|{dirn}|{ai}|0"] + P[f"{d}|{dirn}|{ai}|1"]) / 2; return m, ("present" if m >= .65 else "absent" if m <= .35 else "unsure")
net = {d: 0.0 for d in DIALS}
for it in out:
    P = it["p"]; g = {k.split("|")[1]: v for k, v in P.items() if k.startswith("genre")}; s = {k.split("|")[1]: v for k, v in P.items() if k.startswith("scope")}
    gate = (g["happened"] >= .5 or g["announced"] >= .5) and g["opinion"] < .5
    print("=" * 100); print(it["headline"]); print(it["url"])
    print(f"  reading (P yes): happened {g['happened']:.2f}  announced {g['announced']:.2f}  opinion {g['opinion']:.2f}  forecast {g['forecast']:.2f} | national {s['national']:.2f}  local {s['local']:.2f}  new today {s['new']:.2f}  -> counts as an event: {gate}")
    moved = {}
    for d in DIALS:
        res = {}
        for dirn in ("up", "down"):
            st = [attr_state(P, d, dirn, i) for i in range(3)]; res[dirn] = (st, sum(x[1] == "present" for x in st) >= 2)
        up, dn = res["up"][1], res["down"][1]
        show = any(x[0] >= .35 for dirn in ("up", "down") for x in res[dirn][0])
        if show or up or dn:
            f = lambda dirn: " ".join(f"{DIALS[d][dirn][i][0]}={res[dirn][0][i][0]:.2f}" for i in range(3))
            print(f"  {d:19s} up[{f('up')}] -> {'PRESENT' if up else 'no'} | down[{f('down')}] -> {'PRESENT' if dn else 'no'}")
        if gate and up != dn:
            dirn = "up" if up else "down"; strength = sum(x[0] for x in res[dirn][0] if x[1] == "present") / sum(x[1] == "present" for x in res[dirn][0])
            delta = (0.10 if dirn == "up" else -0.10) * strength * (1.0 if s["national"] >= .5 else 0.5); moved[d] = delta; net[d] += delta
    print("  dial changes (placeholder size rule: 0.10 x strength x (1 national / 0.5 otherwise)):", {d: f"{v:+.3f}" for d, v in moved.items()} or "none")
print("=" * 100); print("Net dial changes from the 5 items:", {d: f"{v:+.3f}" for d, v in net.items() if v})
perc = {d: 1 + net.get(d, 0) for d in DIAL_ORDER}
print("Effect on a persona who perceives everything fully (element change, percent):")
for e in ELEMENTS:
    ln = sum(GRID[(e, d)][0] * math.log(perc[d]) for d in DIAL_ORDER if (e, d) in GRID)
    if abs(ln) > 1e-6: print(f"   {e:20s} {(math.exp(ln) - 1) * 100:+.2f}%   (" + ", ".join(f"{d} {GRID[(e, d)][0]:+.1f}" for d in DIAL_ORDER if (e, d) in GRID and abs(net.get(d, 0)) > 1e-9) + ")")
