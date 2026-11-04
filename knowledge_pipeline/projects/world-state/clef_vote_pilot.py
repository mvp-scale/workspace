"""Pilot: local Clef (port 8018, /v1/systemone) as a third voter on 'is the main subject a change in a real-world condition?'. 500 random Sonnet-voted items."""
import json, glob, random, sys, time, urllib.request, concurrent.futures as cf, pathlib
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 500; OUT = H0 / "runs/clef_vote.jsonl"
hk, sn = {}, {}
for f in glob.glob("runs/p7/*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; ids = sorted(i for i in sn if i in hk); random.Random(7).shuffle(ids)
done = {json.loads(l)["id"] for l in open(OUT)} if OUT.exists() else set(); todo = [i for i in ids if i not in done][:N]
Q = "Is the main subject of this item a change in a real-world condition, such as prices, unrest, health, weather, jobs or conflict? A passing mention does not count."
def call(i):
    d = pool[i]["date"] or "2026-10-25"; body = {"state": f"News item (published {d}; today is {d}):\n{pool[i]['text'][:700]}", "questions": {"q": {"type": "noul", "instructions": Q}}, "model": "clef-flash-q4km"}
    r = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8018/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=300); a = json.load(r)["answers"]["q"]
    return {"id": i, "raw": a, "haiku": int(bool(hk[i]["conditions"])), "sonnet": int(bool(sn[i]["conditions"]))}
hb.beat("clef-vote-pilot", where="[5090]", task="T10", state="running", why="Is local Clef an independent third voter on whether a condition is the main subject?", success="Clef agrees with each teacher at 0.62+", next="Score the pilot and decide the lever", need="Nothing", progress=f"0/{len(todo)}", spent=0.0, cap=0.0)
t0 = time.time(); n = 0
with open(OUT, "a") as f, cf.ThreadPoolExecutor(6) as ex:
    for res in ex.map(lambda i: (lambda: call(i))() if True else None, todo):
        f.write(json.dumps(res) + "\n"); n += 1
        if n % 50 == 0: hb.beat("clef-vote-pilot", progress=f"{n}/{len(todo)} at {n / (time.time() - t0):.1f} items/s")
print(n, "items", round(time.time() - t0), "s", round((time.time() - t0) / max(n, 1), 3), "s/item"); print(open(OUT).readline())
hb.finish("clef-vote-pilot", "done", last=f"{n} items in {time.time() - t0:.0f}s", progress=f"{n} items")
