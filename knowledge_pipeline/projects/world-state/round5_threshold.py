"""Round 5 (lap two, step 2): is a lower topic confidence threshold better than 700, chosen without looking at the items it is scored on?
Heads off. Per article: the topic confidence (sum of the top two topic probabilities) and whether the two guesses hit the human category (MN-DS fresh 1,600, through specs/topic_to_iptc_v1.json). Split into two halves with a fixed seed. Rule fixed before the run: on the half used to choose, take the LOWEST threshold on the grid 300..900 step 50 at which the answered set is right at least 0.80 of the time (the 0.80 line used for topic in the playbook); then report that threshold on the OTHER half: share answered and accuracy of the answered, against threshold 700 on the same half. Done both ways (A chooses, B scores; B chooses, A scores).
    /workspace/models/embed-zs/.venv/bin/python -u round5_threshold.py   (from projects/world-state)   -> runs/pulse/round5_threshold.json"""
import json, math, random, sys
import numpy as np
sys.path.insert(0, "."); import analyze2 as A2
from expert1_runtime import ExpertS
J = lambda p: [json.loads(l) for l in open(p)]
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json"))
items = {x["id"]: x["text"] for x in J("/workspace/data/anchors/mn_ds/items_T28b.jsonl")}; ids = sorted(i for i in items if i in G)
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); X = A2.Analyzer(e.S, json.load(open("runs/pulse/field_table.json")), threads=8)
conf = []; hit = []
for i in ids:
    o = X.analyze("", items[i], None); t = o["fields"]["topic"]; conf.append(int(round(1000 * (t["confidence"] or 0)))); hit.append(any(G[i]["l1"] in M.get(x, []) for x in (t["proposed"] or "").split(" / ")))
conf = np.array(conf); hit = np.array(hit); n = len(ids)
def wil(k, m, z=1.96):
    if m == 0: return [None, None]
    p = k / m; d = 1 + z * z / m; c = (p + z * z / (2 * m)) / d; h = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d; return [round(c - h, 3), round(c + h, 3)]
def at(idx, thr):
    a = conf[idx] >= thr; m = int(a.sum()); k = int(hit[idx][a].sum()); return {"thr": thr, "answered_share": round(m / len(idx), 3), "answered_acc": round(k / max(m, 1), 4), "ci95": wil(k, m)}
rng = random.Random(20261108); perm = list(range(n)); rng.shuffle(perm); H = [np.array(sorted(perm[: n // 2])), np.array(sorted(perm[n // 2:]))]
grid = list(range(300, 901, 50)); res = {"n": n, "rule": "lowest threshold with answered accuracy >= 0.80 on the choosing half", "seed": 20261108, "directions": []}
for a, b, name in ((0, 1, "A chooses, B scores"), (1, 0, "B chooses, A scores")):
    pick = next((t for t in grid if at(H[a], t)["answered_acc"] >= 0.80 and at(H[a], t)["answered_share"] > 0), None)
    res["directions"].append({"name": name, "chosen_thr": pick, "on_choosing_half": at(H[a], pick) if pick else None, "on_scoring_half_chosen": at(H[b], pick) if pick else None, "on_scoring_half_at_700": at(H[b], 700)})
res["whole_set_at_700"] = at(np.arange(n), 700); res["whole_set_curve"] = {str(t): at(np.arange(n), t) for t in grid}
json.dump(res, open("runs/pulse/round5_threshold.json", "w"), indent=1); print(json.dumps(res["directions"]))
