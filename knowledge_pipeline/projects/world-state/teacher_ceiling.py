"""Teacher ceiling for topic: Sonnet's single topic on 300 fresh-slice articles, scored as one guess against the human category (specs/topic_to_iptc_v1.json), next to BitMob Domain v6b (one guess and two guesses) and the calibrated sparse topic head on the same 300. MN-DS is used for scoring only.
    /workspace/models/embed-zs/.venv/bin/python teacher_ceiling.py   (from projects/world-state) -> runs/pulse/teacher_ceiling.json"""
import json, math, pickle, sys
import numpy as np
sys.path.insert(0, "."); from expert1_runtime import ExpertS
D = "/workspace/data/anchors/mn_ds/"; M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open(D + "gold_fresh.json"))
items = {x["id"]: x["text"] for x in json.load(open("runs/harvest/pool_v2/items_ceiling300.json"))}; T = json.load(open("runs/harvest/pool_v2/ceiling300_labels.json")); ids = sorted(items); assert set(T) == set(ids)
hit = lambda i, tops: any(G[i]["l1"] in M.get(t, []) for t in tops)
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); H = pickle.load(open("runs/expert1/sparse_heads_v2.pkl", "rb")); m = H["topic_model"]; W = np.ascontiguousarray(m.coef_.T.astype(np.float32)); b = m.intercept_.astype(np.float32); cl = np.array(m.classes_)
t1 = []; v1 = []; v2 = []; s1 = []; s2 = []
for i in ids:
    r = e.read(items[i])["topic_top2"]["answer"] or []; z = np.asarray(H["topic_vec"].transform([items[i]]).astype(np.float32) @ W).ravel() + b; o = np.argsort(-z)[:2]
    t1.append(hit(i, [T[i]])); v1.append(hit(i, r[:1])); v2.append(hit(i, r[:2])); s1.append(hit(i, [str(cl[o[0]])])); s2.append(hit(i, [str(cl[k]) for k in o]))
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
n = len(ids); f = lambda a: {"rate": round(float(np.mean(a)), 4), "ci95": wil(int(np.sum(a)), n)}
rng = np.random.default_rng(7); A = np.array(t1, float); B = np.array(v1, float); ds = []
for _ in range(1000): ix = rng.integers(0, n, n); ds.append(A[ix].mean() - B[ix].mean())
res = {"n": n, "judge": "MN-DS human labels, first fresh slice (scoring only)", "teacher_top1": f(t1), "v6b_top1": f(v1), "v6b_top2": f(v2), "sparse_top1": f(s1), "sparse_top2": f(s2), "teacher_minus_v6b_top1": {"diff": round(float(A.mean() - B.mean()), 4), "ci95": [round(float(np.percentile(ds, 2.5)), 3), round(float(np.percentile(ds, 97.5)), 3)]}}
json.dump(res, open("runs/pulse/teacher_ceiling.json", "w"), indent=1); print(json.dumps(res))
