import json, time
from concurrent.futures import ThreadPoolExecutor
import offline as O
from personas import gen
from items import ITEMS
n = 400; pers = [gen(s) for s in range(1, n + 1)]
def job(a):
    i, t = a
    qs = {f"q{j}": {"type": "noul", "instructions": q} for j, q in enumerate(ITEMS[t])}
    ans = O.call("Person profile:\n" + pers[i]["profile"], qs)
    return [ans[f"q{j}"]["noul"] for j in range(len(ITEMS[t]))]
t0 = time.time(); jobs = [(i, t) for t in ITEMS for i in range(n)]
with ThreadPoolExecutor(4) as ex: out = list(ex.map(job, jobs))
res = {t: out[k * n:(k + 1) * n] for k, t in enumerate(ITEMS)}
open("/workspace/data/persona-lab/items.json", "w").write(json.dumps(res)); print("done", round(time.time() - t0), "s")
