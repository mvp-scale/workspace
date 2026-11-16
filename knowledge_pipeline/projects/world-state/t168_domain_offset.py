"""T168: wording A only, saves full probabilities, then a per-option log-prior shift fitted on PICK and scored on HELD. Derived from t149_domain_wording.py. Three wordings of the 17-option Domain choice on MN-DS fresh2 gold (scoring only). Hosted Jev.
    OUT=<json> N_PICK=300 N_HELD=500 /workspace/kev/.venv/bin/python -I t149_domain_wording.py   (from projects/world-state)"""
import os, re, json, time, random, urllib.request, concurrent.futures as cf, collections
N_PICK, N_HELD = int(os.environ.get("N_PICK", 300)), int(os.environ.get("N_HELD", 500)); OUT = os.environ.get("OUT", "runs/pulse/t168/t168_domain_offset.json"); os.makedirs(os.path.dirname(OUT), exist_ok=True)
KEY = ""
for l in open("/workspace/secrets/vault.env"):
    if l.startswith("TYPESAFE_API_KEY="): KEY = l.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
src = open("t135_full_read.py").read(); b0 = src.index("def build_state"); b1 = src.index("qh = lambda"); ns = {"re": re}; exec(src[b0:b1], ns); build_state = ns["build_state"]
IPT = json.load(open("/workspace/data/diag/flow/iptc_top_level.json"))["top_level"]; slug = lambda s: re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
ALIAS = {"politics": "politics and government", "religion and belief": "religion"}
EX = {"arts, culture, entertainment and media": "films, music, books, museums, celebrities, newspapers and broadcasting", "crime, law and justice": "arrests, trials, court rulings, police work, prisons", "disaster, accident and emergency incident": "fires, floods, earthquakes, plane or road crashes, rescue operations",
      "economy, business and finance": "company results, markets, inflation, trade, jobs data, mergers", "education": "schools, universities, exams, teachers, student funding", "environment": "pollution, climate change, wildlife, conservation, energy and resource use", "health": "diseases, hospitals, vaccines, medical research, public health policy",
      "human interest": "unusual personal stories, animals, local oddities, record attempts", "labour": "strikes, unions, wages, employment law, workplace conditions", "lifestyle and leisure": "travel, food, fashion, hobbies, home and garden", "politics and government": "elections, parties, legislation, ministers, diplomacy and government policy",
      "religion": "churches, faith leaders, religious practice, religious disputes", "science and technology": "research findings, space, computing, AI, engineering, new devices", "society": "social issues, demographics, rights, family, migration, community life", "sport": "matches, tournaments, athletes, clubs, doping",
      "conflict, war and peace": "wars, attacks, terrorism, ceasefires, peace talks, military action", "weather": "forecasts, storms, heatwaves, snow, seasonal conditions"}
V = {"A": lambda: {"type": "choice", "instructions": "Which broad subject is this story mainly about?", "criteria": {slug(v["label"]): v["definition"] for v in IPT.values()}},
     "B": lambda: {"type": "choice", "instructions": "Which broad subject is this story mainly about? Pick the one subject that the main events or argument belong to. Subjects and what they cover: " + " | ".join(f"{v['label']}: {v['definition']}" for v in IPT.values()), "criteria": {slug(v["label"]): v["label"] for v in IPT.values()}},
     "C": lambda: {"type": "choice", "instructions": "Which broad subject is this story mainly about?", "criteria": {slug(v["label"]): v["definition"] + ". Typical stories: " + EX[v["label"]] for v in IPT.values()}}}
assert set(EX) == {v["label"] for v in IPT.values()}
keys = {slug(v["label"]): v["label"] for v in IPT.values()}
gold = json.load(open("/workspace/data/anchors/mn_ds/gold_fresh2.json")); items = {}
for l in open("/workspace/data/anchors/mn_ds/items_fresh2.jsonl"): r = json.loads(l); items[r["id"]] = r["text"]
ids = sorted(i for i in gold if i in items); random.Random(142).shuffle(ids); PICK, HELD = ids[:N_PICK], ids[N_PICK:N_PICK + N_HELD]; assert not set(PICK) & set(HELD)
truth = {i: ALIAS.get(gold[i]["l1"], gold[i]["l1"]) for i in ids}; tok = collections.Counter()
def one(a):
    v, i = a; text = items[i]; st, _ = build_state(text.split(". ")[0][:200], text, ""); body = {"state": st, "questions": {"domain_main": V[v]()}, "model": "jev-1.14.0"}; last = None
    for t in range(3):
        try:
            req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json", "User-Agent": "kp-t149/0.1", "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=300) as r: j = json.load(r)
            tok[v] += (j.get("usage") or {}).get("input_tokens", 0); a = j["answers"]["domain_main"]; return (v, i, {"choice": keys[a["choice"]], "p": {keys[k]: x for k, x in a["probabilities"].items()}})
        except Exception as e: last = e; time.sleep(2 + 3 * t)
    return (v, i, "ERR " + repr(last)[:100])

def run(S):
    with cf.ThreadPoolExecutor(5) as ex: out = list(ex.map(one, [("A", i) for i in S]))
    return {i: a for _, i, a in out}
import math
PP = run(PICK); HH = run(HELD); errs = sum(isinstance(a, str) for d in (PP, HH) for a in d.values())
ok = lambda D: [i for i in D if not isinstance(D[i], str)]
opts = sorted({k for d in (PP, HH) for a in d.values() if not isinstance(a, str) for k in a["p"]})
mp = {k: sum(PP[i]["p"].get(k, 0) for i in ok(PP)) / len(ok(PP)) for k in opts}; gs = {k: (sum(truth[i] == k for i in ok(PP)) + 1) / (len(ok(PP)) + len(opts)) for k in opts}
off = {k: math.log(gs[k]) - math.log(max(mp[k], 1e-6)) for k in opts}
def pred(a, o): return max(opts, key=lambda k: math.log(max(a["p"].get(k, 0), 1e-6)) + o.get(k, 0))
zero = {k: 0 for k in opts}; H = ok(HH)
base = [pred(HH[i], zero) == truth[i] for i in H]; fix = [pred(HH[i], off) == truth[i] for i in H]; rng = random.Random(1); d = []
for _ in range(1000):
    s = [rng.randrange(len(H)) for _ in H]; d.append(sum(fix[j] for j in s) / len(s) - sum(base[j] for j in s) / len(s))
d.sort(); gain = sum(fix) / len(H) - sum(base) / len(H)
res = {"n_pick": len(ok(PP)), "n_held": len(H), "errors": errs, "held_acc_argmax": round(sum(base) / len(H), 3), "held_acc_offset": round(sum(fix) / len(H), 3), "gain": round(gain, 3), "gain_ci95": [round(d[25], 3), round(d[974], 3)], "offsets": {k: round(v, 2) for k, v in off.items()},
       "input_tokens": dict(tok), "cost_usd_at_0_042_per_million": round(sum(tok.values()) * 0.042 / 1e6, 3), "pass": bool(gain >= 0.03 and d[25] > 0), "pick_probs": PP, "held_probs": HH}
json.dump(res, open(OUT, "w")); print(json.dumps({k: v for k, v in res.items() if not k.endswith("_probs")}))
