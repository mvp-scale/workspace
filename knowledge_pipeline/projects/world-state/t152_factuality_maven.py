"""T152 (ledger T-0031): Jev factuality on MAVEN-FACT gold_T33b, scoring only. Two readings per marked-event sentence: happened (noul) and the production FACT choice.
    N=<limit> OUT=<json> /workspace/kev/.venv/bin/python -I t152_factuality_maven.py   (from projects/world-state)"""
import os, re, json, time, random, urllib.request, concurrent.futures as cf, collections
N = int(os.environ.get("N", 0)); OUT = os.environ.get("OUT", "runs/pulse/t152/t152_factuality_maven.json"); os.makedirs(os.path.dirname(OUT), exist_ok=True)
KEY = ""
for l in open("/workspace/secrets/vault.env"):
    if l.startswith("TYPESAFE_API_KEY="): KEY = l.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
src = open("t135_full_read.py").read(); FACT = eval(re.search(r"^FACT = (\{.*\})$", src, re.M).group(1))
Q = {"happened": {"type": "noul", "instructions": "According to the text, has the event marked between « and » already taken place?", "criteria": {"true": "The text presents the marked event as having happened or being in effect.", "false": "The text presents the marked event as only planned, predicted, possible, denied or unclear."}},
     "fact_choice": {"type": "choice", "instructions": "How does the story present the event marked between « and »?", "criteria": FACT}}
D = "/workspace/data/anchors/maven_fact/"; items = [json.loads(l) for l in open(D + "items_T33b.jsonl")]; gold = json.load(open(D + "gold_T33b.json"))
if N: random.Random(152).shuffle(items); items = items[:N]
tok = collections.Counter()
def one(x):
    body = {"state": x["text"], "questions": Q, "model": "jev-1.14.0"}; last = None
    for a in range(3):
        try:
            req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json", "User-Agent": "kp-t152/0.1", "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=300) as r: j = json.load(r)
            tok["in"] += (j.get("usage") or {}).get("input_tokens", 0); A = j["answers"]; return {"id": x["id"], "yes": gold[x["id"]]["yes"], "fac": gold[x["id"]]["factuality"], "happened": A["happened"]["noul"], "choice": A["fact_choice"]["choice"]}
        except Exception as e: last = e; time.sleep(2 + 3 * a)
    return {"id": x["id"], "error": repr(last)[:200]}
with cf.ThreadPoolExecutor(5) as ex: rows = list(ex.map(one, items))
ok = [r for r in rows if "error" not in r]
def ba(pred, S):
    P = [r for r in S if r["yes"]]; Nn = [r for r in S if not r["yes"]]; return (sum(pred(r) for r in P) / len(P) + sum(not pred(r) for r in Nn) / len(Nn)) / 2
def auc(f):
    P = [f(r) for r in ok if r["yes"]]; Nn = [f(r) for r in ok if not r["yes"]]; return sum((p > n) + 0.5 * (p == n) for p in P for n in Nn) / (len(P) * len(Nn))
def boot(fn):
    rng = random.Random(1); b = sorted(fn([rng.choice(ok) for _ in ok]) for _ in range(300)); return [round(b[7], 3), round(b[292], 3)]
def sc(pred): return {"balanced_accuracy": round(ba(pred, ok), 3), "ci95": boot(lambda S: ba(pred, S))}
res = {"n": len(items), "ok": len(ok), "errors": len(rows) - len(ok), "n_yes": sum(r["yes"] for r in ok), "input_tokens": tok["in"], "cost_usd_at_0_042_per_million": round(tok["in"] * 0.042 / 1e6, 4),
       "happened_at_0_5": sc(lambda r: r["happened"] >= 0.5), "happened_auc": round(auc(lambda r: r["happened"]), 3),
       "choice_asserted_is_yes": sc(lambda r: r["choice"] == "asserted"), "choice_asserted_or_reported_is_yes": sc(lambda r: r["choice"] in ("asserted", "reported")),
       "choice_counts_by_gold": {g: dict(collections.Counter(r["choice"] for r in ok if r["fac"] == g)) for g in ("CT+", "PS+", "CT-", "PS-", "Uu")}, "rows": rows}
json.dump(res, open(OUT, "w")); print(json.dumps({k: v for k, v in res.items() if k != "rows"}))
