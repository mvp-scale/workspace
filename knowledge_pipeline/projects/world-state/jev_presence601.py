"""T21: hosted Jev as an independent rater of presence on the 601 devq items (owner yes 2026-11-04; pre-registration L668 + addendum). One typed question with the field definition; threshold 0.5 on P(yes) fixed before the run. Cap 0.30 USD at the public tariff. Raw answers -> runs/pulse/jev_presence601/raw.jsonl. python3 jev_presence601.py [--probe]"""
import json, sys, time, urllib.request, concurrent.futures as cf, pathlib, os, threading
sys.path[:0] = ["/workspace/demo", "/workspace/knowledge_pipeline/kit/live"]
import heartbeat as hb, backends
H0 = pathlib.Path("/workspace/knowledge_pipeline/projects/world-state"); os.chdir(H0); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
B = backends.BACKENDS["jev"]; PRICE = 0.042 / 1e6; CAP = 0.30; OD = H0 / os.environ.get("JP_OUT", "runs/pulse/jev_presence601"); OD.mkdir(exist_ok=True)
Q = {"presence": "Does the item report that a condition of daily life or society (for example prices, jobs, safety, health, the environment, public order, services or markets) has itself already changed, for the people or place the item is about? A plan, a warning, a reaction, a statement of intent or a possible future effect does not count. A single small event that does not change conditions for many people does not count."}
items = J(os.environ.get("JP_ITEMS", "runs/pulse/ceiling_sonnet/items601.jsonl")); items = items[:2] if "--probe" in sys.argv else items
tok = [0]; lock = threading.Lock()
def call(it):
    if tok[0] * PRICE > CAP: raise RuntimeError("cap")
    body = {"state": f"News item:\n{it['text'][:450]}", "questions": {k: {"type": "noul", "instructions": q} for k, q in Q.items()}, **({"model": B["model"]} if B["model"] else {})}
    hdr = {"Content-Type": "application/json", "User-Agent": "jev-demo/0.1", **({"Authorization": f"Bearer {B['key']}"} if B["key"] else {})}
    for a in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(B["url"].rstrip("/") + "/v1/systemone", json.dumps(body).encode(), hdr), timeout=300) as resp: dd = json.load(resp)
            with lock: tok[0] += (dd.get("usage") or {}).get("input_tokens", 0)
            return {"id": it["id"], "answers": dd["answers"], "usage": dd.get("usage")}
        except Exception as e:
            if a == 2: return {"id": it["id"], "error": str(e)[:160]}
            time.sleep(3)
if "--probe" not in sys.argv: hb.beat("t21-jev-presence601", where="[HOST]", task="T21", state="running", why="Is presence reproducible by an independent family (Jev)?", success="601 answers, spend under 0.30 USD", next="Compute alpha vs Sonnet A with a bootstrap interval; apply the pre-registered verdict", need="Nothing", progress=f"{len(items)} items", cap=1800)
t0 = time.time()
with cf.ThreadPoolExecutor(6) as ex: R = list(ex.map(call, items))
if "--probe" in sys.argv: print(json.dumps(R, indent=1)[:1500]); sys.exit()
with open(OD / "raw.jsonl", "w") as f:
    for r in R: f.write(json.dumps(r) + "\n")
err = sum("error" in r for r in R); print("done", len(R), "errors", err, "input tokens", tok[0], "usd", round(tok[0] * PRICE, 4), "s", round(time.time() - t0)); hb.finish("t21-jev-presence601", "done" if err < 10 else "failed", spent=round(tok[0] * PRICE, 4), last=f"{len(R) - err} answered, {err} errors")
