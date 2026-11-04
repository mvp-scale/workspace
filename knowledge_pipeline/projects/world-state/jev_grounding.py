"""T21 'does Sonnet make it up?' grounding test (pre-registration L672 part c). For each Sonnet A positive on the 601 devq items: hosted Jev is asked whether the item supports (1) Sonnet's own condition+direction statement, (2) the OPPOSITE direction (control), (3) a random OTHER condition (control), (4) Sonnet's claim sentence, (5) the claim of a random OTHER item (control). Jev answers P(yes) per statement. Pre-registered reading: grounded if supported >= 0.80 on true statements and <= 0.25 on both controls (P >= 0.5 counts as supported). Cap 0.30 USD at the public tariff. python3 jev_grounding.py"""
import json, sys, re, random, time, urllib.request, concurrent.futures as cf, pathlib, os, threading
sys.path[:0] = ["/workspace/demo"]; import backends
H0 = pathlib.Path("/workspace/knowledge_pipeline/projects/world-state"); os.chdir(H0); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
B = backends.BACKENDS["jev"]; PRICE = 0.042 / 1e6; CAP = 0.30; rng = random.Random(5)
spec = json.load(open("specs/world_state_v3b_nosize_sonnet.json")); g = spec["guideline"]; g = "\n".join(g) if isinstance(g, list) else g
DEF = {}
for l in g[g.index("CONDITIONS"):].split("\n")[1:]:
    m = re.match(r"(\w+): (.*?) \| up = (.*?) \| down = (.*)", l.strip())
    if m: DEF[m.group(1)] = {"up": m.group(3).strip().rstrip("."), "down": m.group(4).strip().rstrip(".")}
text = {r["id"]: r["text"] for r in J("runs/pulse/ceiling_sonnet/items601.jsonl")}; A = {r["item_id"]: r["label"] for r in J("runs/pulse/ceiling_sonnet/a601/labels.jsonl")}
pos = [i for i in A if A[i]["conditions"] and i in text]; print("positives", len(pos), "conditions known", len(DEF))
jobs = []
for i in pos:
    c = A[i]["conditions"][0]; k, d = c["condition"], c["direction"]; od = "down" if d == "up" else "up"
    if k not in DEF: continue
    other = rng.choice([x for x in DEF if x != k]); od2 = rng.choice(["up", "down"]); j = rng.choice([x for x in pos if x != i])
    jobs += [(i, "cond_true", f"Does the item report that {DEF[k][d]}?"), (i, "cond_opposite", f"Does the item report that {DEF[k][od]}?"), (i, "cond_random", f"Does the item report that {DEF[other][od2]}?"), (i, "claim_true", f"Does the item say this: {A[i]['claim']}"), (i, "claim_random", f"Does the item say this: {A[j]['claim']}")]
tok = [0]; lock = threading.Lock()
def call(job):
    i, kind, q = job
    if tok[0] * PRICE > CAP: return {"id": i, "kind": kind, "error": "cap"}
    body = {"state": f"News item:\n{text[i][:450]}", "questions": {"q": {"type": "noul", "instructions": q}}, **({"model": B["model"]} if B["model"] else {})}
    hdr = {"Content-Type": "application/json", "User-Agent": "jev-demo/0.1", **({"Authorization": f"Bearer {B['key']}"} if B["key"] else {})}
    for a in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(B["url"].rstrip("/") + "/v1/systemone", json.dumps(body).encode(), hdr), timeout=300) as resp: dd = json.load(resp)
            with lock: tok[0] += (dd.get("usage") or {}).get("input_tokens", 0)
            return {"id": i, "kind": kind, "p": dd["answers"]["q"]["noul"], "q": q}
        except Exception as e:
            if a == 2: return {"id": i, "kind": kind, "error": str(e)[:100]}
            time.sleep(2)
with cf.ThreadPoolExecutor(6) as ex: R = list(ex.map(call, jobs))
os.makedirs("runs/pulse/jev_grounding", exist_ok=True)
with open("runs/pulse/jev_grounding/raw.jsonl", "w") as f:
    for r in R: f.write(json.dumps(r) + "\n")
import collections; by = collections.defaultdict(list)
for r in R:
    if "p" in r: by[r["kind"]].append(r["p"])
print("errors", sum("error" in r for r in R), "usd", round(tok[0] * PRICE, 4))
for k in ("cond_true", "cond_opposite", "cond_random", "claim_true", "claim_random"):
    v = by[k]; print(f"{k:14s} n {len(v):3d}  supported (P>=0.5) {sum(x >= 0.5 for x in v) / len(v):.3f}  mean P {sum(v) / len(v):.3f}")
