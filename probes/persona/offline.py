"""Offline test of the persona pipeline: generator -> persona extractor -> idea extractor -> surrogate, against direct model decisions.

    /workspace/kev/.venv/bin/python offline.py collect [--n 400]     # model calls, saved to data/persona-lab/offline.json
    /workspace/kev/.venv/bin/python offline.py report

PRE-REGISTERED (written before the first run):
 E2 extractor: Spearman(extracted trait, hidden latent) >= 0.60 for each of 6 traits; two wordings agree r >= 0.70
 E3 idea extractor: cost_monthly higher for $12 variants by >= 0.5; setup_app and id_photo higher for app variants by >= 0.5;
    strangers higher for stranger variants by >= 0.3
 E4 direct decisions: price lever hurts latent price>=4 more than <=2 by >= 0.10; app lever hurts (tech<=2 or privacy>=4) more than the rest by >= 0.10;
    Nightfall: young city (18-29, large city) minus 60+ rural >= 0.30; Gardenway: 60+ rural minus young city >= 0.30
 E5 surrogate (extracted persona numbers x idea numbers, ridge): held-out personas r >= 0.80; held-out products (Nightfall, Gardenway) r >= 0.50;
    per-persona lever effect r >= 0.50
"""
import itertools, json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
try:
    import numpy as np  # only report() needs it
except ImportError:
    np = None
from personas import gen, TRAITS, ASPIRATIONS, WORLDVIEWS, age_band

OUT = Path("/workspace/data/persona-lab/offline.json")
EP = "http://127.0.0.1:8091"

TRAIT_Q = {  # positive polarity: high P(yes) = high trait. two wordings each.
    "tech": ["This person is comfortable learning and using new phone apps.", "This person finds new phone apps easy to pick up."],
    "price": ["This person pays close attention to the cost of small recurring fees.", "This person would drop a service because of a $10 monthly fee."],
    "privacy": ["This person is reluctant to give personal details such as an ID or a face photo to a company.", "This person avoids sharing personal data with apps."],
    "social": ["This person is at ease meeting and dealing with people they do not know.", "This person often does things together with neighbours or groups."],
    "time": ["This person has very little spare time in a typical week.", "This person's days are fully booked."],
    "novelty": ["This person likes to try new products soon after they appear.", "This person tries new products soon after they are released."],
}
IDEA_Q = {
    "cost_monthly": "Using the product costs the user money every month.",
    "setup_app": "The user must install a phone app to use the product.",
    "id_photo": "The user must give a photo of their face or an ID to use the product.",
    "strangers": "Using the product involves dealing with people the user does not know.",
    "time_heavy": "Using the product takes the user more than one hour a week.",
    "urban_only": "The product is available only in large cities.",
    "youth_target": "The product is aimed at people under 30.",
    "older_target": "The product is aimed at people over 60.",
    "rural_target": "The product is aimed at people in rural areas.",
    "novel": "The product does something that most people have not used before.",
}
BASE = "Neighbour Loop lets people on the same street lend and borrow tools, ladders and kitchen appliances. "
L_PRICE = {0: "It is free. ", 1: "It costs $12 a month. "}
L_ACCESS = {0: "It works by text message: reply to a text to request or offer an item. ",
            1: "You need to install a phone app, and you must upload a photo of your face and a government ID to be approved. "}
L_SOCIAL = {0: "You can only borrow from people you personally invite.", 1: "You can borrow from anyone on your street who has joined, including people you have never met."}
PRODUCTS = {f"nl_p{p}a{a}s{s}": BASE + L_PRICE[p] + L_ACCESS[a] + L_SOCIAL[s] for p, a, s in itertools.product((0, 1), repeat=3)}
PRODUCTS["nightfall"] = ("Nightfall is a $25 monthly membership that gives people aged 21 to 30 in large cities access to late-night events and shared "
                         "rides home after 10pm. It is available only in large cities and works through a phone app.")
PRODUCTS["gardenway"] = ("Gardenway is a free monthly paper newsletter, with a phone line you can call, for retired people living in rural areas. "
                         "It shares seasonal gardening advice and puts local gardeners in touch with each other by post.")
HELD_OUT = ["nightfall", "gardenway"]
# iteration 2 (added AFTER seeing iteration 1 failed to transfer to new products; exploratory): vary who it is aimed at and where it is available
AUD = {"open": "", "young": "It is aimed at people aged 21 to 30. ", "retired": "It is aimed at retired people. "}
AVAIL = {"all": "", "city": "It is available only in large cities. ", "rural": "It is available only in rural areas and small towns. "}
PRODUCTS2 = {f"t_{a}_{v}": BASE + "It is free. It works by text message: reply to a text to request or offer an item. " + AUD[a] + AVAIL[v] + "You can only borrow from people you personally invite."
             for a in AUD for v in AVAIL}


def call(state, qs):
    req = urllib.request.Request(EP + "/v1/systemone", json.dumps({"model": "Winnow-12B", "state": state, "questions": qs}).encode(), {"Content-Type": "application/json"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=300) as r: return json.load(r)["answers"]
        except Exception:
            if attempt: raise


def persona_numbers(p):
    qs = {f"{t}{i}": {"type": "noul", "instructions": w} for t, ws in TRAIT_Q.items() for i, w in enumerate(ws)}
    qs["aspiration"] = {"type": "choice", "instructions": "What does this person most want from the future?", "criteria": dict(ASPIRATIONS)}
    qs["worldview"] = {"type": "choice", "instructions": "Which statement describes this person's general outlook?", "criteria": dict(WORLDVIEWS)}
    a = call("Person profile:\n" + p["profile"], qs)
    out = {f"{t}{i}": a[f"{t}{i}"]["noul"] for t, ws in TRAIT_Q.items() for i in range(len(ws))}
    out["asp"] = a["aspiration"]["probabilities"]; out["wv"] = a["worldview"]["probabilities"]
    return out


def collect(n):
    t0 = time.time(); D = {"n": n}
    pers = [gen(s) for s in range(1, n + 1)]
    with ThreadPoolExecutor(4) as ex: D["persona"] = list(ex.map(persona_numbers, pers))
    print("persona extractor", round(time.time() - t0), "s", flush=True)
    iq = {k: {"type": "noul", "instructions": v} for k, v in IDEA_Q.items()}
    D["idea"] = {k: {q: a["noul"] for q, a in call("Product description:\n" + txt, iq).items()} for k, txt in PRODUCTS.items()}
    def direct(job):
        k, p = job
        a = call(f"Product description:\n{PRODUCTS[k]}\n\nPerson reading it:\n{p['profile']}", {"try": {"type": "noul", "instructions": "After reading the description, this person would try the product in the next month."}})
        return a["try"]["noul"]
    jobs = [(k, p) for k in PRODUCTS for p in pers]
    with ThreadPoolExecutor(4) as ex: vals = list(ex.map(direct, jobs))
    D["direct"] = {k: vals[i * n:(i + 1) * n] for i, k in enumerate(PRODUCTS)}
    OUT.write_text(json.dumps(D)); print("done", round(time.time() - t0), "s")


def collect2():
    D = json.loads(OUT.read_text()); n = D["n"]; pers = [gen(s) for s in range(1, n + 1)]
    iq = {k: {"type": "noul", "instructions": v} for k, v in IDEA_Q.items()}
    for k, txt in PRODUCTS2.items(): D["idea"][k] = {q: a["noul"] for q, a in call("Product description:\n" + txt, iq).items()}
    def direct(job):
        k, p = job
        return call(f"Product description:\n{PRODUCTS2[k]}\n\nPerson reading it:\n{p['profile']}", {"try": {"type": "noul", "instructions": "After reading the description, this person would try the product in the next month."}})["try"]["noul"]
    with ThreadPoolExecutor(4) as ex: vals = list(ex.map(direct, [(k, p) for k in PRODUCTS2 for p in pers]))
    for i, k in enumerate(PRODUCTS2): D["direct"][k] = vals[i * n:(i + 1) * n]
    OUT.write_text(json.dumps(D)); print("collect2 done")


def spearman(a, b):
    from scipy.stats import spearmanr
    return float(spearmanr(a, b)[0])


def report():
    D = json.loads(OUT.read_text()); n = D["n"]; pers = [gen(s) for s in range(1, n + 1)]
    PN = D["persona"]; ID = D["idea"]; DR = {k: np.array(v) for k, v in D["direct"].items()}
    lat = {t: np.array([p["latent"][t] for p in pers]) for t in TRAITS}
    print("E2 extractor vs hidden latent (Spearman), wording agreement (Pearson):")
    ext = {}
    for t in TRAITS:
        w0 = np.array([x[f"{t}0"] for x in PN]); w1 = np.array([x[f"{t}1"] for x in PN]); ext[t] = (w0 + w1) / 2
        print(f"  {t:8s} rho={spearman(ext[t], lat[t]):.2f}  wording r={np.corrcoef(w0, w1)[0,1]:.2f}  (w0 rho={spearman(w0, lat[t]):.2f}, w1 rho={spearman(w1, lat[t]):.2f})")
    asp_true = [p["aspiration"] for p in pers]; wv_true = [p["worldview"] for p in pers]
    print("  aspiration top-1 =", round(np.mean([max(x["asp"], key=x["asp"].get) == a for x, a in zip(PN, asp_true)]), 2), "(chance .14)",
          "| worldview top-1 =", round(np.mean([max(x["wv"], key=x["wv"].get) == a for x, a in zip(PN, wv_true)]), 2), "(chance .20)")
    print("E3 idea extractor (lever -> number):")
    def lv(q, bit, idx): 
        hi = [ID[f"nl_p{p}a{a}s{s}"][q] for p, a, s in itertools.product((0, 1), repeat=3) if (p, a, s)[idx] == bit]; return np.mean(hi)
    print(f"  cost_monthly  $12 {lv('cost_monthly',1,0):.2f} vs free {lv('cost_monthly',0,0):.2f}")
    print(f"  setup_app     app {lv('setup_app',1,1):.2f} vs sms {lv('setup_app',0,1):.2f};  id_photo {lv('id_photo',1,1):.2f} vs {lv('id_photo',0,1):.2f}")
    print(f"  strangers     open {lv('strangers',1,2):.2f} vs invite-only {lv('strangers',0,2):.2f}")
    for k in HELD_OUT: print(" ", k, {q: round(v, 2) for q, v in ID[k].items() if v >= .5})
    print("E4 direct decisions:")
    fac = [(p, a, s) for p, a, s in itertools.product((0, 1), repeat=3)]
    def drop(idx, mask):
        d = [DR[f"nl_p{p}a{a}s{s}"][mask] for p, a, s in fac if (p, a, s)[idx] == 0]; u = [DR[f"nl_p{p}a{a}s{s}"][mask] for p, a, s in fac if (p, a, s)[idx] == 1]
        return float(np.mean(d) - np.mean(u))
    pr_hi = lat["price"] >= 4; pr_lo = lat["price"] <= 2
    print(f"  price lever drop: price>=4 {drop(0, pr_hi):.2f} (n={pr_hi.sum()}) vs price<=2 {drop(0, pr_lo):.2f} (n={pr_lo.sum()})")
    ap = (lat["tech"] <= 2) | (lat["privacy"] >= 4); print(f"  app lever drop: tech<=2 or privacy>=4 {drop(1, ap):.2f} (n={ap.sum()}) vs rest {drop(1, ~ap):.2f}")
    ages = np.array([p["age"] for p in pers]); area = np.array([p["area"] for p in pers])
    yc = (ages < 30) & (area == "large city"); or_ = (ages >= 60) & (area == "rural area")
    print(f"  nightfall: young city {DR['nightfall'][yc].mean():.2f} (n={yc.sum()}) vs 60+ rural {DR['nightfall'][or_].mean():.2f} (n={or_.sum()})")
    print(f"  gardenway: 60+ rural {DR['gardenway'][or_].mean():.2f} vs young city {DR['gardenway'][yc].mean():.2f}")
    print("E5 surrogate (ridge on extracted persona numbers x idea numbers):")
    from sklearn.linear_model import Ridge
    iq = list(IDEA_Q)
    pf = np.column_stack([ext[t] for t in TRAITS] + [[x["asp"][a] for x in PN] for a in ASPIRATIONS])  # 6 + 7
    def feats(k, rows):
        iv = np.array([ID[k][q] for q in iq]); P = pf[rows]
        return np.hstack([P, np.tile(iv, (len(P), 1)), (P[:, :6, None] * iv[None, None, :]).reshape(len(P), -1)])
    logit = lambda p: np.log(np.clip(p, .02, .98) / (1 - np.clip(p, .02, .98)))
    tr = np.arange(n) < int(n * .7); te = ~tr
    train_k = [k for k in list(PRODUCTS) + list(PRODUCTS2) if k not in HELD_OUT and k in DR]
    X = np.vstack([feats(k, tr) for k in train_k]); y = np.concatenate([logit(DR[k][tr]) for k in train_k])
    m = Ridge(alpha=3.0).fit(X, y); pred = lambda k, rows: 1 / (1 + np.exp(-m.predict(feats(k, rows))))
    ra = np.corrcoef(np.concatenate([pred(k, te) for k in train_k]), np.concatenate([DR[k][te] for k in train_k]))[0, 1]
    print(f"  held-out personas, same products: r={ra:.2f}")
    for k in HELD_OUT: print(f"  held-out product {k}: r={np.corrcoef(pred(k, np.arange(n) >= 0), DR[k])[0,1]:.2f}  mean pred {pred(k, np.arange(n)>=0).mean():.2f} vs direct {DR[k].mean():.2f}")
    # per-persona lever effect
    for name, idx in (("price", 0), ("access", 1), ("strangers", 2)):
        dd = np.mean([DR[f"nl_p{p}a{a}s{s}"][te] - DR[f"nl_p{(p, a, s)[0] if idx else 0}a{a}s{s}"][te] for p, a, s in fac if (p, a, s)[idx] == 1 for _ in [0]] if False else
                     [DR["nl_p%da%ds%d" % t][te] - DR["nl_p%da%ds%d" % tuple(0 if i == idx else v for i, v in enumerate(t))][te] for t in fac if t[idx] == 1], axis=0)
        sd = np.mean([pred("nl_p%da%ds%d" % t, te) - pred("nl_p%da%ds%d" % tuple(0 if i == idx else v for i, v in enumerate(t)), te) for t in fac if t[idx] == 1], axis=0)
        print(f"  lever {name}: per-persona effect direct vs surrogate r={np.corrcoef(dd, sd)[0,1]:.2f} (mean direct {dd.mean():+.2f}, surrogate {sd.mean():+.2f})")
    print("cohort heat (direct P(try), age band x area), nightfall | gardenway:")
    for k in HELD_OUT:
        print(" ", k)
        bands = [age_band(a) for a in ages]
        for b in sorted(set(bands)):
            print("   ", b.ljust(6), "  ".join(f"{a[:5]}:{DR[k][(np.array(bands) == b) & (area == a)].mean():.2f}" if ((np.array(bands) == b) & (area == a)).sum() >= 5 else f"{a[:5]}: -  " for a in ("large city", "suburb", "small town", "rural area")))

# ---- embedding litmus test: 20 varied ideas (different kinds, audiences, costs) scored directly on the same 400 personas ----
DIVERSE = {
 "mealkit": "FreshBox delivers a weekly box of pre-measured ingredients and recipes for three dinners. It costs $70 a week, you order on a website, and you can skip any week.",
 "seniorfit": "SilverStride is a free weekly group walking club for people over 65, run by volunteers at local parks. No sign-up is needed; you just turn up.",
 "crypto": "CoinSwipe is a phone app for trading cryptocurrency with borrowed money. It charges 2% per trade, shows live price alerts, and pays a bonus for inviting friends.",
 "studentbudget": "PennyPlan is a free phone app for university students that links to your bank account and shows where your money goes each week, with tips for saving on food and rent.",
 "hearing": "ClearEar sells hearing aids you can buy online without a prescription for $299, with a fitting by video call and a 60-day return window.",
 "codecamp": "CodeKids is a two-week summer coding camp for children aged 8 to 12 in suburban schools. It costs $450 per child and runs 9am to 3pm on weekdays.",
 "farmloan": "AgriFlex offers equipment loans for farmers at 6% interest, with the application handled by phone and a local loan officer who visits your farm.",
 "language": "Lingo10 is a phone app that teaches a new language in ten-minute daily lessons with games and streaks. The first month is free, then $13 a month.",
 "watch": "StreetWatch is a free text-message alert service run by local police. You get a message when a crime is reported within a mile of your home.",
 "gaming": "PlayPass is a $15 monthly subscription that gives access to a catalogue of 400 video games on any console or phone, with no downloads.",
 "tours": "Sunset Living offers free guided tours of local retirement communities every Saturday, with lunch included and no obligation to sign anything.",
 "petins": "PawShield is pet insurance that pays 80% of vet bills for $38 a month. You file claims by taking a photo of the receipt in the app.",
 "telehealth": "QuickDoc connects you by video to a licensed doctor within 15 minutes for $49 a visit, without an appointment. Prescriptions go to your local pharmacy.",
 "solar": "BrightRoof installs solar panels on your home at no upfront cost. You pay a fixed monthly fee for 20 years that is lower than your current electricity bill, and the company owns the panels.",
 "evening": "NightSchool offers evening courses in accounting, welding and nursing assistance at the local community college. Each course costs $300 and meets twice a week.",
 "dating50": "SecondAct is a dating website for people over 50. It costs $25 a month, matches you using a questionnaire, and has phone support for members.",
 "ruralbox": "ValleyBox delivers fresh produce from local farms to rural towns every Thursday. It is $35 a week with no contract, and you order by phone or at the general store.",
 "truecrime": "Cold Cases Daily is a free podcast that explores unsolved crimes, with a new episode each weekday morning and a paid ad-free version for $5 a month.",
 "doorbell": "SeeAll is a doorbell with a camera that records everyone who comes to your door and stores the video in the cloud for $8 a month. Neighbours can opt to share clips.",
 "partyapp": "Afterhours is a free phone app that shows what is happening tonight in your city, from concerts to club nights, and lets you split a shared ride home with other users.",
}


def collect3():
    D = json.loads(OUT.read_text()); n = D["n"]; pers = [gen(s) for s in range(1, n + 1)]
    iq = {k: {"type": "noul", "instructions": v} for k, v in IDEA_Q.items()}
    for k, txt in DIVERSE.items(): D["idea"][k] = {q: a["noul"] for q, a in call("Product description:\n" + txt, iq).items()}
    def direct(job):
        k, p = job
        return call(f"Product description:\n{DIVERSE[k]}\n\nPerson reading it:\n{p['profile']}", {"try": {"type": "noul", "instructions": "After reading the description, this person would try the product in the next month."}})["try"]["noul"]
    with ThreadPoolExecutor(4) as ex: vals = list(ex.map(direct, [(k, p) for k in DIVERSE for p in pers]))
    for i, k in enumerate(DIVERSE): D["direct"][k] = vals[i * n:(i + 1) * n]
    OUT.write_text(json.dumps(D)); print("collect3 done")


if __name__ == "__main__":
    if sys.argv[1] == "collect3": collect3()
    elif sys.argv[1] == "collect2": collect2()
    elif sys.argv[1] == "collect": collect(int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 400)
    else: report()
