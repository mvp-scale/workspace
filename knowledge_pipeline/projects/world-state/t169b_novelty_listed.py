"""T169 Novelty pilot: coverage-by-area test, full vs held-out area list. Derived from t149_domain_wording.py. Was: three wordings of the 17-option Domain choice on MN-DS fresh2 gold (scoring only). Hosted Jev.
    OUT=<json> N_PICK=300 N_HELD=500 /workspace/kev/.venv/bin/python -I t149_domain_wording.py   (from projects/world-state)"""
import os, re, json, time, random, urllib.request, concurrent.futures as cf, collections
N_PICK, N_HELD = 0, 0; OUT = os.environ.get("OUT", "runs/pulse/t169/t169b_novelty_listed.json"); os.makedirs(os.path.dirname(OUT), exist_ok=True)
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
ids = sorted(i for i in gold if i in items); random.Random(142).shuffle(ids); 
O = json.load(open("/workspace/exports/world-engine-ontology-rules_v2.json")); T2I = json.load(open("specs/topic_to_iptc_v1.json"))["map"]
topics = {t["id"]: f"{t['name']}: {t['definition']}" for t in O["topics"]}
tok = collections.Counter(); N = int(os.environ.get("N", 100)); rng = random.Random(169); by = collections.defaultdict(list)
for i in sorted(ids): by[ALIAS.get(gold[i]["l1"], gold[i]["l1"])].append(i)
cats = sorted(by); S = []
for a in range(N): c = cats[a % len(cats)]; S.append(rng.choice(by[c]))
S = list(dict.fromkeys(S))
def one(a):
    cond, i = a; text = items[i]; g = ALIAS.get(gold[i]["l1"], gold[i]["l1"]); st, _ = build_state(text.split(". ")[0][:200], text, "")
    tp = topics if cond == "full" else {k: v for k, v in topics.items() if g not in T2I.get(k, [])}
    body = {"state": st, "questions": {"novelty_choice": {"type": "choice", "instructions": "Areas: " + "; ".join(v.split(":")[0] for v in tp.values()) + ". How well do these areas cover this story's subject?", "criteria": {"known": "The subject is clearly covered by a listed area.", "emerging": "The subject is partly covered but shows something new: a pattern, event type or actor the list does not name.", "unsupported": "The story makes claims it does not support, or no listed area applies."}}}, "model": "jev-1.14.0"}; last = None
    for t in range(3):
        try:
            req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json", "User-Agent": "kp-t169b/0.1", "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=300) as r: j = json.load(r)
            tok[cond] += (j.get("usage") or {}).get("input_tokens", 0); n = j["answers"]["novelty_choice"]
            return (cond, i, {"choice": n["choice"], "p_known": n["probabilities"].get("known"), "n_areas": len(tp)})
        except Exception as e: last = e; time.sleep(2 + 3 * t)
    return (cond, i, "ERR " + repr(last)[:100])
with cf.ThreadPoolExecutor(5) as ex: out = list(ex.map(one, [(c, i) for c in ("full", "removed") for i in S]))
R = collections.defaultdict(dict)
for c, i, a in out: R[c][i] = a
json.dump({c: {i: a for i, a in d.items()} for c, d in R.items()}, open(OUT + '.raw.json', 'w'))   # raw answers saved before scoring
good = [i for i in S if not isinstance(R["full"].get(i), str) and not isinstance(R["removed"].get(i), str) and R["full"][i]["p_known"] is not None and R["removed"][i]["p_known"] is not None]
kr = lambda c: sum(R[c][i]["choice"] == "known" for i in good) / len(good)
pos = [R["full"][i]["p_known"] for i in good]; neg = [R["removed"][i]["p_known"] for i in good]
auc = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))
res = {"n_stories": len(S), "n_ok": len(good), "known_rate_full": round(kr("full"), 3), "known_rate_removed": round(kr("removed"), 3), "gap": round(kr("full") - kr("removed"), 3), "auroc_full_vs_removed": round(auc, 3), "choice_counts_removed": dict(collections.Counter(R["removed"][i]["choice"] for i in good)),
       "mean_areas_removed": round(sum(R["removed"][i]["n_areas"] for i in good) / len(good), 1), "input_tokens": dict(tok), "cost_usd_at_0_042_per_million": round(sum(tok.values()) * 0.042 / 1e6, 3)}
res["pass"] = bool(res["auroc_full_vs_removed"] >= 0.80 and res["gap"] >= 0.30); res["detail"] = R
json.dump(res, open(OUT, "w")); print(json.dumps({k: v for k, v in res.items() if k != "detail"}))
