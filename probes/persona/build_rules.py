"""Writes rules/*.csv, the single source of truth for the persona engine (v2 draft). Every number is a guess unless status says otherwise."""
import csv, os
from world_model import DIALS as V1
from items import ITEMS
OUT = "/workspace/probes/persona/rules"
def w(name, header, rows):
    with open(f"{OUT}/{name}.csv", "w", newline="") as f:
        c = csv.writer(f); c.writerow(header); c.writerows(rows)

# ---- dials: id, name, kind, definition, half_life_ticks, grounding_series, status
D = [
 ("prices", "Prices and cost of living", "condition", "How expensive everyday goods and services are for ordinary households.", 150, "CPI (BLS, monthly)", "draft"),
 ("housing_cost", "Housing cost", "condition", "Rent, house prices and mortgage cost.", 300, "Case-Shiller, mortgage rate, rent index", "draft: split out of prices (reviewers)"),
 ("energy_fuel", "Energy and fuel", "condition", "Fuel, electricity and heating cost and supply.", 100, "gasoline price, energy CPI (EIA/BLS)", "draft: split out of prices"),
 ("financial_conditions", "Financial conditions", "condition", "Interest rates, credit availability and market stress.", 150, "policy rate, credit spreads, equity index", "draft: new, ConsumerSim signal class"),
 ("job_security", "Job and income security", "condition", "How secure people's work and income are.", 200, "unemployment rate, jobless claims, JOLTS", "draft"),
 ("crime", "Crime and personal safety", "condition", "Crime and violence around people's daily life.", 100, "FBI UCR / NCVS (annual, lagged)", "draft: was safety_fear; war and terror moved out"),
 ("war_terror", "War and terror", "condition", "Armed conflict and terrorism affecting the audience's country or region.", 150, "conflict event data (memory, unverified)", "draft: new, reviewers"),
 ("health_risk", "Health risk", "condition", "Exposure to illness and strain on care.", 150, "CDC and WHO surveillance", "draft"),
 ("trust_institutions", "Trust in institutions", "condition", "How credibly government, business and media are seen to act.", 300, "Edelman, Gallup confidence (annual)", "draft: may split government vs business/media"),
 ("community", "Community and belonging", "condition", "How connected and supportive local communities are.", 300, "volunteering and time-use surveys", "draft"),
 ("social_division", "Social division", "condition", "Polarisation and perceived unfairness in society.", 400, "Edelman grievance, polarisation surveys", "draft: merges polarisation and inequality; split if overlap test says so"),
 ("tech_pace", "Technology pace", "condition", "How fast technology is changing daily life and work.", 200, "Pew adoption surveys", "draft: measures launches not adoption"),
 ("disruption", "Disruption of routines", "condition", "Interruptions to travel, power, services, school and work (including weather).", 80, "NOAA storm events, outage data", "draft"),
 ("optimism", "Outlook (computed)", "outcome", "How hopeful people feel. Computed from the other dials, never read from a story.", 200, "Michigan sentiment (FRED UMCSENT)", "draft: outcome, not input"),
 ("news_overload", "News overload", "media", "Volume of reports per tick in the ledger. A fact about the media, not the world.", 20, "report counts in the ledger; GDELT", "draft"),
]
w("dials", ["id", "name", "kind", "definition", "half_life_ticks", "grounding_series", "status"], D)

# ---- elements: id, name, kind, definition, n_questions_target, status
E = [
 ("tech_comfort", "Tech comfort", "trait", "Ease learning and using new apps and devices.", 6, "draft; weakest in test (0.75), needs varied angles"),
 ("price_attention", "Price attention", "trait", "How closely the person watches costs and small fees.", 5, "draft"),
 ("privacy_stance", "Privacy stance", "trait", "Reluctance to hand personal data to companies.", 5, "draft"),
 ("social_ease", "Social ease", "trait", "Comfort dealing with people they do not know.", 5, "draft"),
 ("time_pressure", "Time pressure", "state", "How little spare time the person has.", 4, "draft"),
 ("novelty_seeking", "Novelty seeking", "trait", "Readiness to try new things early.", 5, "draft"),
 ("financial_stress", "Financial stress", "state", "Felt strain on the household budget.", 6, "draft; a feeling, not a resource"),
 ("optimism", "Optimism", "state", "How hopeful the person feels about their own future.", 5, "draft"),
 ("safety_concern", "Safety concern", "state", "How threatened the person feels in daily life.", 5, "draft"),
 ("institutional_trust", "Institutional trust", "state", "How much the person believes institutions act honestly.", 5, "draft"),
 ("liquidity", "Liquidity", "resource", "Cash buffer, income level and steadiness.", 5, "draft: new, strongest missing driver per decision-science review"),
 ("habit_inertia", "Habit and inertia", "trait", "Tendency to stay with existing choices.", 5, "draft: new"),
 ("loss_aversion", "Loss aversion", "trait", "How much losses weigh against gains.", 5, "draft: new"),
 ("tenure", "Tenure (rent or own)", "derived", "Rents or owns the home. Read from demographics, not asked.", 0, "draft: new; moderator"),
 ("life_stage", "Life stage and household", "derived", "Age, children, caring duties. Read from demographics, not asked.", 0, "draft: new; moderator"),
]
w("elements", ["id", "name", "kind", "definition", "n_questions_target", "status"], E)

# ---- element questions: the six traits have 10 written items each (items.py)
EID = {"tech": "tech_comfort", "price": "price_attention", "privacy": "privacy_stance", "social": "social_ease", "time": "time_pressure", "novelty": "novelty_seeking"}
w("element_questions", ["element_id", "question", "selected"], [(EID[t], q, "todo") for t, qs in ITEMS.items() for q in qs])

# ---- dial attributes (from v1; war_terror and new dials still need attributes)
DIAL_V1 = {"safety_fear": "crime"}
rows = []
for d, spec in V1.items():
    did = DIAL_V1.get(d, d)
    if d == "optimism": continue
    for dirn in ("up", "down"):
        for name, defn, qs in spec[dirn]:
            if d == "safety_fear" and name == "public threat": continue   # moves to war_terror
            rows.append((did, dirn, name, defn, qs[0], qs[1], "draft v1; needs 3 differently-angled questions"))
for did in ("housing_cost", "energy_fuel", "financial_conditions", "war_terror", "social_division"):
    rows.append((did, "up", "todo", "attributes to be written", "", "", "todo"))
w("dial_attributes", ["dial_id", "direction", "attribute", "definition", "question_1", "question_2", "status"], rows)

# ---- grid: element <- dial   (strength: dial 10% above neutral moves the element about strength x 10%); moderated_by = who it matters more to
G = [
 ("price_attention", "prices", .8, "higher prices make people watch costs", "liquidity (low = stronger)", "guess"),
 ("price_attention", "housing_cost", .3, "housing cost squeezes everything else", "tenure (renter = stronger)", "guess"),
 ("price_attention", "energy_fuel", .4, "fuel and energy bills are visible", "", "guess"),
 ("price_attention", "job_security", -.3, "insecure people watch costs more (dial down, attention up)", "", "guess"),
 ("financial_stress", "prices", .6, "higher prices strain budgets", "liquidity (low = stronger)", "guess"),
 ("financial_stress", "housing_cost", .5, "rent and mortgage are the largest bills", "tenure (renter, or owner with mortgage)", "guess"),
 ("financial_stress", "energy_fuel", .3, "energy bills", "", "guess"),
 ("financial_stress", "financial_conditions", .4, "rising rates and tight credit raise strain", "tenure; debt", "guess"),
 ("financial_stress", "job_security", -.8, "more security eases stress", "", "guess"),
 ("financial_stress", "health_risk", .3, "illness brings cost", "", "guess"),
 ("liquidity", "prices", -.3, "inflation erodes buffers", "", "guess"),
 ("liquidity", "job_security", .4, "secure income rebuilds buffers", "", "guess"),
 ("optimism", "optimism", .6, "the outlook dial is anchored on a real sentiment index and acts on personal optimism; identity-like: never reuse the same questions", "", "identity-like (anchored)"),
 ("optimism", "prices", -.4, "cost pressure dampens hope", "", "guess"),
 ("optimism", "job_security", .5, "secure work lifts hope", "", "guess"),
 ("optimism", "crime", -.3, "fear dampens hope", "", "guess"),
 ("optimism", "war_terror", -.2, "conflict dampens hope", "", "guess"),
 ("optimism", "financial_conditions", -.2, "market stress dampens hope", "asset ownership", "guess"),
 ("optimism", "social_division", -.2, "division dampens hope", "", "guess"),
 ("safety_concern", "crime", .9, "more crime, more concern", "", "identity-like: same construct as the dial; do not reuse questions"),
 ("safety_concern", "war_terror", .5, "conflict raises concern", "", "guess"),
 ("safety_concern", "health_risk", .3, "health threats raise caution", "", "guess"),
 ("safety_concern", "disruption", .2, "disruption raises caution", "", "guess"),
 ("safety_concern", "trust_institutions", -.2, "trusted institutions reassure", "", "guess"),
 ("institutional_trust", "trust_institutions", .9, "same construct as the dial", "political alignment (not in v2 yet)", "identity-like: do not reuse questions"),
 ("institutional_trust", "social_division", -.3, "division erodes trust", "", "guess"),
 ("social_ease", "community", .5, "stronger community, easier with others", "", "guess"),
 ("social_ease", "crime", -.3, "fear reduces openness to strangers", "", "guess"),
 ("social_ease", "health_risk", -.3, "illness keeps people apart", "", "guess"),
 ("social_ease", "social_division", -.3, "division makes strangers feel riskier", "", "guess"),
 ("time_pressure", "disruption", .6, "disruption eats time", "life_stage (caring duties = stronger)", "guess"),
 ("time_pressure", "news_overload", .2, "overload eats attention", "", "guess"),
 ("novelty_seeking", "crime", -.3, "fear narrows exploration", "", "guess"),
 ("novelty_seeking", "tech_pace", .2, "fast tech change invites trying", "", "guess"),
 ("tech_comfort", "tech_pace", .1, "small effect", "", "weak: near noise; hold at zero until data"),
 ("privacy_stance", "trust_institutions", -.5, "more trust, less reluctance to share", "", "contested sign"),
 ("privacy_stance", "crime", -.2, "fear can raise acceptance of surveillance", "", "contested sign"),
 ("loss_aversion", "financial_conditions", .2, "volatility raises loss sensitivity", "", "guess"),
 ("loss_aversion", "war_terror", .2, "threat raises loss sensitivity", "", "guess"),
]
w("grid", ["element_id", "dial_id", "strength", "why", "moderated_by", "status"], G)

# ---- decisions: id, name, opportunity_rate (chance of meeting the decision on a tick), bias
DEC = [("spend", "Spend (vs save)", .20, 0.0), ("buy_new", "Buy something new", .05, -.5), ("subscribe", "Subscribe or commit", .02, -.8), ("travel", "Travel", .01, -.3),
       ("change_work", "Change work", .002, -1.5), ("move", "Move home", .001, -2.2), ("switch_brand", "Switch brand or provider", .01, -1.0), ("share", "Share or engage publicly", .10, -.5)]
w("decisions", ["id", "name", "opportunity_rate", "bias", "status"], [d + ("guess",) for d in DEC])
W = {"spend": {"financial_stress": -1.0, "optimism": .8, "price_attention": -.8, "liquidity": .8, "loss_aversion": -.4},
     "buy_new": {"novelty_seeking": .8, "price_attention": -.9, "financial_stress": -.6, "tech_comfort": .2, "liquidity": .5, "habit_inertia": -.4},
     "subscribe": {"price_attention": -1.0, "privacy_stance": -.3, "financial_stress": -.5, "time_pressure": -.3, "habit_inertia": .4},
     "travel": {"financial_stress": -.8, "time_pressure": -.6, "novelty_seeking": .6, "optimism": .5, "liquidity": .6, "safety_concern": -.5},
     "change_work": {"financial_stress": .4, "optimism": .4, "novelty_seeking": .5, "loss_aversion": -.6, "liquidity": .4, "habit_inertia": -.4},
     "move": {"novelty_seeking": .5, "financial_stress": .2, "liquidity": .6, "loss_aversion": -.5, "habit_inertia": -.6},
     "switch_brand": {"price_attention": .9, "novelty_seeking": .5, "habit_inertia": -.8},
     "share": {"social_ease": .9, "privacy_stance": -.7, "time_pressure": -.4}}
w("decision_weights", ["decision_id", "element_id", "weight", "status"], [(d, e, v, "guess") for d, m in W.items() for e, v in m.items()])

# ---- the loop, in tick order
w("loop", ["step", "name", "what_happens"], [
 (1, "ingest", "read new report lines from the ledger; dial changes from classifier readings; news_overload from report count"),
 (2, "dial_update", "each dial: multiply by event factors, then drift back toward 1 at its own half-life; optimism computed from the others"),
 (3, "perceive", "each persona perceives each dial through its own salience (and region, once regional dials exist)"),
 (4, "modify_elements", "effective element = base element x product over dials of perceived dial ^ strength (grid)"),
 (5, "persist", "blend with the previous state (inertia), as in ConsumerSim; strength fitted on a calibration period"),
 (6, "gates", "for each decision met this tick, act with probability sigmoid(bias + sum of weights x standardised elements)"),
 (7, "log", "write dial values, events, per-cohort rates and the cause of each change to the ledger")])
print("written", sorted(os.listdir(OUT)))
