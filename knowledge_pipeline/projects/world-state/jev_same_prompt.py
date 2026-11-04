"""T21 fairness fix D2 (ledger L674): hosted Jev on the 601 devq items with the SAME instruction text the other raters got (guideline + layers + 3 examples from specs/world_state_v3b_nosize_sonnet.json, via task_spec.system_text) and the FULL item text. One typed yes/no question closes the instructions. Threshold P(yes) >= 0.5, fixed before the run. Cap 0.40 USD at the public tariff. python3 jev_same_prompt.py [--probe]"""
import json, sys, time, urllib.request, concurrent.futures as cf, pathlib, os, threading
sys.path[:0] = ["/workspace/demo", "/workspace/knowledge_pipeline/kit/teacher"]
import backends, task_spec as TS
H0 = pathlib.Path("/workspace/knowledge_pipeline/projects/world-state"); os.chdir(H0); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
spec = TS.load(str(H0 / "specs/world_state_v3b_nosize_sonnet.json")) if hasattr(TS, "load") else None
B = backends.BACKENDS["jev"]; PRICE = 0.042 / 1e6; CAP = 0.40; OD = H0 / os.environ.get("JS_OUT", "runs/pulse/jev_same_prompt"); OD.mkdir(exist_ok=True)
system = spec.system_text()
Q = system + "\n\nTASK FOR THIS CALL: apply the instructions above to the news item you are given. Answer yes if your reply would list at least one condition under 'conditions', answer no if the list would be empty."
items = J(os.environ.get("JS_ITEMS", "runs/pulse/ceiling_sonnet/items601.jsonl")); items = items[:2] if "--probe" in sys.argv else items
tok = [0]; lock = threading.Lock()
def call(it):
    if tok[0] * PRICE > CAP: return {"id": it["id"], "error": "cap"}
    body = {"state": spec.user_text(it) if False else it["text"], "questions": {"presence": {"type": "noul", "instructions": Q}}, **({"model": B["model"]} if B["model"] else {})}
    hdr = {"Content-Type": "application/json", "User-Agent": "jev-demo/0.1", **({"Authorization": f"Bearer {B['key']}"} if B["key"] else {})}
    for a in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(B["url"].rstrip("/") + "/v1/systemone", json.dumps(body).encode(), hdr), timeout=300) as resp: dd = json.load(resp)
            with lock: tok[0] += (dd.get("usage") or {}).get("input_tokens", 0)
            return {"id": it["id"], "answers": dd["answers"], "usage": dd.get("usage")}
        except Exception as e:
            if a == 2: return {"id": it["id"], "error": str(e)[:200]}
            time.sleep(3)
t0 = time.time()
with cf.ThreadPoolExecutor(6) as ex: R = list(ex.map(call, items))
if "--probe" in sys.argv: print(json.dumps(R, indent=1)[:900]); sys.exit()
with open(OD / "raw.jsonl", "w") as f:
    for r in R: f.write(json.dumps(r) + "\n")
print("done", len(R), "errors", sum("error" in r for r in R), "input tokens", tok[0], "usd", round(tok[0] * PRICE, 4), "s", round(time.time() - t0))
