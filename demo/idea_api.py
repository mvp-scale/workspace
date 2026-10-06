"""Random idea generator for the world engine's example buttons (demo/worldengine2.html). Stdlib only.

  GET /api/idea-kinds              -> {kinds: [{id, label, blurb, reach, mode}], ai, ai_model, ai_used, ai_cap}
  GET /api/idea?kind=KIND          -> {kind, label, mode, text, source}     KIND is one of the ids above, or "random"

Six kinds across a spectrum, from sensible to absurd and from one town to the whole world. Every call is a fresh random draw, tried in this order:
  1. a small model writes it in a dry, observational-comic voice (ANTHROPIC_API_KEY in the server's environment, a per-run cap)   source "model"
  2. otherwise a random item from the hand-written library demo/ideas.json (edit it freely; {co} {town} {price} {n} {pct} are filled in randomly)   source "library"
  3. otherwise a deadpan mad-lib built in this file   source "templates"
so the buttons never break. Everything is fictional: invented companies and towns, no real people or brands. `mode` says how the engine should read it: an announcement or news item (event) or a pitch for something you can buy (offer).
"""
import json
import os
import random
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MODEL = os.environ.get("IDEA_AI_MODEL", "claude-haiku-4-5-20251001")
CAP = int(os.environ.get("IDEA_AI_CAP", "300"))
_used = 0
_raw_recent: dict[str, list[str]] = {}       # kind -> library items already handed out, so a run does not repeat until it has seen half the library
_recent: dict[str, list[str]] = {}          # kind -> the last few texts, shown to the model so it does not repeat itself

KINDS = {
    "crazy_tech": {"label": "Crazy tech", "mode": "event", "reach": "local to macro", "blurb": "Absurdly ambitious tech, security or money products that change a town, a country or the world",
                   "brief": "An announcement, in news style, of an absurdly ambitious {domain} product, service or solution that changes things at the {level} level. Say what changes for ordinary people, what it replaces, and end on a dry punchline."},
    "ridiculous": {"label": "Ridiculous product", "mode": "offer", "reach": "personal", "blurb": "A fun, ridiculous product that no one should buy",
                   "brief": "A pitch for a ridiculous consumer product that no one should buy. State the price in dollars, whether it needs an app, a subscription or an ID check, and who it is for. Wry, deadpan, with one sharp line."},
    "sensible": {"label": "Sensible service", "mode": "offer", "reach": "local", "blurb": "The opposite: a boring, genuinely useful service people would adopt",
                 "brief": "A pitch for a boring but genuinely useful local service that ordinary people would actually adopt. State the price in dollars (or free), how you sign up, and who it is for. Dry humour about how unexciting it is."},
    "local_shock": {"label": "Local shock", "mode": "event", "reach": "local", "blurb": "Something upends one town or neighbourhood",
                    "brief": "A news item about a surprising event in one invented town involving {topic}: a closure, layoff, outage, scandal or windfall. Give the local stakes (who loses, who gains) and one sardonic line."},
    "policy": {"label": "New policy", "mode": "event", "reach": "country", "blurb": "A government rule that lands on millions",
               "brief": "A news item about a government announcing a new {level}-level policy or regulation about {topic}. Say who it hits, who it helps, and add a dry aside about how governments announce things."},
    "macro": {"label": "World event", "mode": "event", "reach": "macro", "blurb": "A big event that crosses borders",
              "brief": "A world-news item about a large event involving {topic} that crosses borders and moves markets, prices or politics in several countries. Add one sardonic aside about how the world reacts."},
}
DOMAINS = ["technology", "security", "financial", "technology", "security", "financial"]
LEVELS = ["local (one town or neighbourhood)", "country", "macro (worldwide)"]
TOPICS = {
    "tech": ["wearables", "payments", "passwords", "traffic lights", "school lunches", "voting", "home insurance", "pensions", "parking", "food delivery", "smart doorbells", "landlords", "tax filing", "public transit", "power grids", "dating apps", "customer service", "drone delivery", "banking apps", "visas", "garbage collection", "doctor appointments", "credit scores", "street lighting"],
    "local": ["the only bridge", "the one grocery store", "the high school", "the water supply", "the biggest employer", "the farmers' market", "the volunteer fire department", "the bus route", "the bank branch", "the maternity ward", "the annual festival", "the landlord who owns half the town", "the power substation", "the library", "the factory night shift"],
    "macro": ["shipping lanes", "a currency", "a heat wave", "chip supply", "grain exports", "an undersea internet cable", "a bank run", "a pandemic scare", "oil output", "a trade treaty", "satellites", "a cyberattack on payments", "a melting glacier", "an election in a big country", "an AI model release"],
    "policy": ["cash", "rent", "school hours", "social media", "speed limits", "pensions", "drones", "tipping", "airlines", "fuel taxes", "data privacy", "the working week", "gig workers", "bank fees", "bottled water"],
}
SYSTEM = """You write short, funny inputs for a world-simulation demo. Voice: a sardonic observational stand-up in the spirit of George Carlin: plainspoken, irreverent, suspicious of institutions, marketing and money, with a dry punchline. Never quote or imitate any real routine and never claim to be a real person.
Rules: everything is fictional (invent company and town names; no real people, no real brands); no profanity, slurs or sexual content; no instructions for real harm or real fraud; keep it concrete (who is affected, what changes, what it costs).
Reply with ONLY a JSON object: {"text": "..."}. The text is at most 420 characters, plain sentences, no emojis, no hashtags, no markdown."""
BAD = re.compile(r"\b(fuck|shit|cunt|nigg|fag|bitch|rape|nazi)\w*", re.I)


def kinds_payload():
    return {"kinds": [{"id": k, "label": v["label"], "blurb": v["blurb"], "reach": v["reach"], "mode": v["mode"]} for k, v in KINDS.items()],
            "ai": bool(os.environ.get("ANTHROPIC_API_KEY")), "ai_model": MODEL, "ai_used": _used, "ai_cap": CAP}


def _prompt(kind, rng):
    k = KINDS[kind]
    topic_pool = {"crazy_tech": "tech", "ridiculous": "tech", "sensible": "local", "local_shock": "local", "policy": "policy", "macro": "macro"}[kind]
    brief = k["brief"].format(domain=rng.choice(DOMAINS), level=rng.choice(LEVELS), topic=rng.choice(TOPICS[topic_pool]))
    avoid = _recent.get(kind, [])[-5:]
    tail = ("\nDo not repeat the ideas in these earlier ones:\n- " + "\n- ".join(a[:140] for a in avoid)) if avoid else ""
    return f"{brief}\nRandom seed words for variety: {rng.choice(TOPICS['tech'])}, {rng.choice(TOPICS['local'])}, {rng.choice(TOPICS['macro'])}.{tail}"


def _ai(kind, rng):
    global _used
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key or _used >= CAP:
        return None
    _used += 1
    body = {"model": MODEL, "max_tokens": 320, "temperature": 1.0, "system": SYSTEM, "messages": [{"role": "user", "content": _prompt(kind, rng)}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), method="POST",
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.load(r)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None
    raw = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        text = json.loads(m.group(0))["text"] if m else raw
    except (ValueError, KeyError, TypeError):
        text = raw
    text = re.sub(r"\s+", " ", str(text)).strip().strip('"')
    return text if 40 <= len(text) <= 520 and not BAD.search(text) else None


# ---- the local fallback: deadpan mad-libs, so the buttons work with no key, no network and no cap ----
CO = ["Gloomberg Labs", "Nimbus & Sons", "Dormant Dynamics", "Halfway Systems", "Lintlock Security", "Tumble Capital", "Mild Mannered Machines", "Grand Overreach Inc.", "Quasi Corp", "Beige Ventures"]
TECH = {"technology": ["a refrigerator that negotiates your electricity price", "a doorbell that votes on behalf of the whole street", "an app that replaces your commute with a sternly worded notification", "a traffic-light network that learns drivers' names"],
        "security": ["a passport you cannot lose because it follows you home", "a neighbourhood alarm that gossips", "a password replaced by a firm handshake with your phone", "a face scanner that only admits people who look sure of themselves"],
        "financial": ["a savings account that charges you rent for having feelings about money", "a loan whose rate depends on your star sign", "a pension fund that invests only in things already on sale", "a payment app that rounds every purchase up to the nearest apology"]}
EFFECT = {"local": ["One town says its parking has never been this honest.", "The local bank branch has been replaced by a sign pointing at the app.", "The only shop on Main Street has pre-ordered forty."],
          "country": ["The government says it will save the country billions, which is what it says about everything.", "Every ministry has asked for one, and none can say what for.", "The tax office is already calling it a household."],
          "macro": ["Analysts say it will move global markets, mostly because analysts say that about the weather.", "Eleven countries have banned it and nine have already pre-ordered it.", "Shipping lanes, currencies and one very confused pension fund are bracing."]}
QUIP = ["Nobody asked for it, which in this economy counts as market research.", "It comes with a terms-and-conditions page longer than the product.", "The launch was delayed once, for dramatic effect."]
ITEM = ["a gym membership for your couch", "an umbrella that only opens indoors", "bottled air from a place nobody has visited", "a smart spoon that judges your soup", "a fan club for a parking space", "a subscription that mails you your own mail a week late"]
USEFUL = ["a free tool library for the street", "a printed bus timetable that is actually correct", "a repair cafe where someone fixes your toaster for free", "a monthly neighbourhood tool swap", "a dentist who calls you back"]
TOWN = ["Little Dunmore", "Port Grundy", "Saltmere", "Upper Hobbleton", "Wexcombe"]
SHOCK = ["the only hospital is cutting its night shift", "the biggest employer announced 800 layoffs", "the only bridge has closed for six months", "the water supply failed for three days", "the bank, the pharmacy and the diner all closed in one week"]
POLICY = ["a ban on cash payments over ten dollars", "a four-day working week for everyone except the people who announced it", "a ten percent tax on bottled water", "mandatory pensions for gig workers", "a cap on bank fees that banks may exceed 'for administrative reasons'"]
MACRO = ["A key shipping lane has closed and ships are going the long way round", "A heat wave has cut grain exports from three countries at once", "A cyberattack has frozen payments across a dozen banks", "A major chip factory has stopped production after a power failure", "An oil producer has cut output without telling its customers"]
ASIDE = ["Officials called it temporary, which is also what they call everything.", "Experts were consulted, and then ignored, in that order.", "Markets responded by doing something, then explaining it afterwards."]


def _library(kind, rng):
    """A random hand-written item from ideas.json with its blanks filled in; re-read each call so edits show up without a restart."""
    try:
        items = json.loads((Path(__file__).with_name("ideas.json")).read_text())[kind]
    except (OSError, ValueError, KeyError):
        return None
    fresh = [t for t in items if t not in _raw_recent.get(kind, [])] or items
    raw = rng.choice(fresh); _raw_recent[kind] = (_raw_recent.get(kind, []) + [raw])[-max(1, len(items) // 2):]
    fills = {"co": rng.choice(CO), "town": rng.choice(TOWN), "price": rng.choice(["$4.99", "$12", "$29", "$49", "$149"]), "n": rng.choice(["120", "450", "800", "1,200", "3,000"]), "pct": rng.choice(["8", "12", "15", "20", "30"])}
    return re.sub(r"\{(co|town|price|n|pct)\}", lambda m: fills[m.group(1)], raw)


def _template(kind, rng):
    if kind == "crazy_tech":
        dom = rng.choice(list(TECH)); lvl = rng.choice(list(EFFECT))
        return f"{rng.choice(CO)} announced {rng.choice(TECH[dom])}. {rng.choice(EFFECT[lvl])} {rng.choice(QUIP)}"
    if kind == "ridiculous":
        return f"{rng.choice(CO)} is selling {rng.choice(ITEM)}. It costs {rng.choice(['$4.99 a month', '$89 one-off', '$12 a month, cancel anytime (you cannot)'])}. {rng.choice(['It needs an app, a photo of your face and a government ID.', 'No app: a coupon arrives in the mail.', 'Sign up by phone and a human will sigh at you.'])} Made for {rng.choice(['people who have everything and use none of it', 'commuters, optimists and the easily marketed to'])}."
    if kind == "sensible":
        return f"{rng.choice(['A neighbourhood group', 'The town council', 'A local charity'])} is offering {rng.choice(USEFUL)}. It is {rng.choice(['free', '$3 a month', '$5 a visit'])}, you sign up with a name and a phone number, and it is open to anyone on the street. It is not exciting, which is the whole point."
    if kind == "local_shock":
        return f"In {rng.choice(TOWN)}, {rng.choice(SHOCK)}. Residents say they were told last, as usual. {rng.choice(ASIDE)}"
    if kind == "policy":
        return f"The government announced {rng.choice(POLICY)}. It hits renters, small shops and anyone who reads the footnotes. {rng.choice(ASIDE)}"
    return f"{rng.choice(MACRO)}. Prices are rising in several countries and two governments have already blamed each other. {rng.choice(ASIDE)}"


def handle_get(path, query):
    if path == "/api/idea-kinds":
        return 200, kinds_payload()
    if path != "/api/idea":
        return None
    kind = dict(urllib.parse.parse_qsl(query)).get("kind", "random")
    rng = random.Random()
    if kind == "random":
        kind = rng.choice(list(KINDS))
    if kind not in KINDS:
        return 400, {"error": "unknown kind", "kinds": list(KINDS)}
    text = _ai(kind, rng); source = "model"
    if text is None:
        text, source = _library(kind, rng), "library"
    if text is None:
        text, source = _template(kind, rng), "templates"
    _recent.setdefault(kind, []).append(text)
    _recent[kind] = _recent[kind][-8:]
    return 200, {"kind": kind, "label": KINDS[kind]["label"], "mode": KINDS[kind]["mode"], "text": text, "source": source, "model": MODEL if source == "model" else None, "library_size": len(json.loads(Path(__file__).with_name("ideas.json").read_text()).get(kind, [])) if source == "library" else None}
