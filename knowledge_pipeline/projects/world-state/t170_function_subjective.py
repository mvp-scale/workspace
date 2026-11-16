"""T170 (derived from t148_checkthat_function.py): one subjectivity-worded question.  Was T148 (ledger T-0027, runbook R1): Jev function noul on CheckThat English subjectivity, scoring only (CC BY-NC-SA 4.0). Hosted Jev; state = the sentence.
    N=<limit> OUT=<json> /workspace/kev/.venv/bin/python -I t148_checkthat_function.py"""
import os, re, json, time, random, urllib.request, concurrent.futures as cf, collections
N = int(os.environ.get("N", 0)); OUT = os.environ.get("OUT", "/workspace/knowledge_pipeline/projects/world-state/runs/pulse/t170/t170_function_subjective.json"); os.makedirs(os.path.dirname(OUT), exist_ok=True)
KEY = ""
for l in open("/workspace/secrets/vault.env"):
    if l.startswith("TYPESAFE_API_KEY="): KEY = l.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
src = open("/workspace/knowledge_pipeline/projects/world-state/t135_full_read.py").read()
Q = {"function_subjective": {"type": "noul", "instructions": "Does this sentence express the writer's own opinion, feeling, belief or judgment rather than stating facts?", "criteria": {"true": "The sentence shows a personal view: an opinion, emotion, evaluation, speculation or persuasion.", "false": "The sentence states facts, events or neutral quotes."}}}
D = "/workspace/data/anchors/checkthat_subj/"; items = [json.loads(l) for l in open(D + "items_T30.jsonl")]; gold = json.load(open(D + "gold_T30.json"))
if N: random.Random(148).shuffle(items); items = items[:N]
tok = collections.Counter()
def one(x):
    body = {"state": x["text"], "questions": Q, "model": "jev-1.14.0"}; last = None
    for a in range(3):
        try:
            req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json", "User-Agent": "kp-t170/0.1", "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=300) as r: j = json.load(r)
            tok["in"] += (j.get("usage") or {}).get("input_tokens", 0); return {"id": x["id"], "gold": gold[x["id"]], "noul": {k: j["answers"][k]["noul"] for k in Q}}
        except Exception as e: last = e; time.sleep(2 + 3 * a)
    return {"id": x["id"], "error": repr(last)[:200]}
with cf.ThreadPoolExecutor(5) as ex: rows = list(ex.map(one, items))
ok = [r for r in rows if "error" not in r]
def auc(pos, neg):
    w = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg); return w / (len(pos) * len(neg))
def score(f):
    P = [f(r) for r in ok if r["gold"] == "SUBJ"]; Nn = [f(r) for r in ok if r["gold"] == "OBJ"]; a = auc(P, Nn); rng = random.Random(1); bs = []
    for _ in range(300): bs.append(auc([rng.choice(P) for _ in P], [rng.choice(Nn) for _ in Nn]))
    bs.sort(); return {"auc": round(a, 3), "ci95": [round(bs[7], 3), round(bs[292], 3)]}
f = lambda r: r["noul"]["function_subjective"]
P = [f(r) for r in ok if r["gold"] == "SUBJ"]; Nn = [f(r) for r in ok if r["gold"] == "OBJ"]
bal = (sum(p >= 0.5 for p in P) / len(P) + sum(p < 0.5 for p in Nn) / len(Nn)) / 2
res = {"n": len(items), "ok": len(ok), "errors": len(rows) - len(ok), "n_subj": len(P), "n_obj": len(Nn), "input_tokens": tok["in"], "cost_usd_at_0_042_per_million": round(tok["in"] * 0.042 / 1e6, 4), "function_subjective": score(f), "balanced_accuracy_at_0_5": round(bal, 3), "rows": rows}
res["pass"] = bool(res["function_subjective"]["auc"] >= 0.86)
json.dump(res, open(OUT, "w")); print(json.dumps({k: v for k, v in res.items() if k != "rows"}))
