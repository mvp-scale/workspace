"""T20 Phase C step 2: does the fine-tuned student add to the engine's sparse presence score? Loads student A or B, scores DEVQ + old, stacks [engine sparse blend logit, student presence logit (, student topic confidence)] with a cross-validated logistic stack, and reports recall at precision 0.83 on DEVQ vs the current gate. Local GPU for the student forward pass only. Registers heartbeat t20-ft-stack.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python ft_eval_stack.py B"""
import os, sys, json, glob, numpy as np, torch, torch.nn as nn
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; sys.path.insert(0, "../../kit/live"); import heartbeat as hb
V = sys.argv[1] if len(sys.argv) > 1 else "B"; hb.beat("t20-ft-stack", pid=os.getpid(), where="[5090] local GPU", task="T20", state="running", progress=f"stacking student {V} with the engine's sparse presence score", why="Does the fine-tuned student add to the full feature set (word counts + encoder)? Overnight program Phase C step 2.", success="Recall of real conditions at 83% precision on DEVQ up 0.08 over the current gate (0.330), bootstrap lower bound above 0", next="ONNX export + speed + build challenger, or close", need="Nothing", cap=3600)
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
raw = json.load(open("runs/pulse/raw_v5-leaf.json")); pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
items = [dict(r, set="devq") for r in raw["devq"]] + [dict(r, set="old") for r in raw["old"]]
ck = torch.load(f"runs/pulse/ceiling/ft_{V}.pt", map_location="cuda"); m = SentenceTransformer("MongoDB/mdbr-leaf-mt", device="cuda"); m.max_seq_length = 64; (m.load_state_dict(ck["st_full"]) if "st_full" in ck else m[0].auto_model.load_state_dict(ck["model"])); m.eval()
Wp = ck["heads"]["p.weight"].float(); bp = ck["heads"]["p.bias"].float(); Wt = ck["heads"]["t.weight"].float(); bt = ck["heads"]["t.bias"].float(); F = []
with torch.no_grad():
    for k in range(0, len(items), 256):
        f = {a: b.to("cuda") for a, b in m.tokenize([pool[r["id"]] for r in items[k:k + 256]]).items() if torch.is_tensor(b)}
        with torch.autocast("cuda", dtype=torch.bfloat16): e = m(f)["sentence_embedding"].float()
        lp = e @ Wp.T + bp; pl = (lp[:, 1] - lp[:, 0]).cpu().numpy(); pt = (e @ Wt.T + bt).softmax(1).max(1).values.cpu().numpy(); F.append(np.stack([pl, pt], 1))
F = np.concatenate(F); sparse = np.array([(lg(r["ph"]) + lg(r["ps"])) / 2 for r in items]); y = np.array([bool(r["S"]["conditions"]) for r in items]); isq = np.array([r["set"] == "devq" for r in items]); w = np.array([r.get("w", 1.0) if r["set"] == "old" else 1.0 for r in items])
def curve(p, yy):
    o = np.argsort(-p); tp = np.cumsum(yy[o]); n = np.arange(1, len(o) + 1); ok = tp / n >= 0.83; return float((tp / yy.sum())[ok].max()) if ok.any() else 0.0
cur = sparse; stu = F[:, 0]; res = {"student": V, "current_gate": round(curve(cur[isq], y[isq]), 3), "student_alone": round(curve(stu[isq], y[isq]), 3), "auc_current": round(float(roc_auc_score(y[isq], cur[isq])), 4), "auc_student": round(float(roc_auc_score(y[isq], stu[isq])), 4)}
X = np.stack([sparse, stu], 1); P = np.zeros(len(y))
for seed in range(3):
    for a, b in StratifiedKFold(5, shuffle=True, random_state=seed).split(X, y):
        mu, sd = X[a].mean(0), X[a].std(0) + 1e-6; P[b] += LogisticRegression(C=1.0, max_iter=500).fit((X[a] - mu) / sd, y[a], sample_weight=w[a]).predict_proba((X[b] - mu) / sd)[:, 1] / 3
rng = np.random.RandomState(0); ix = np.where(isq)[0]; d = []; ds = []
for _ in range(200): bb = ix[rng.randint(0, len(ix), len(ix))]; d.append(curve(P[bb], y[bb]) - curve(cur[bb], y[bb])); ds.append(curve(stu[bb], y[bb]) - curve(cur[bb], y[bb]))
res["stack_sparse_plus_student"] = {"recall_at_0.83_devq": round(curve(P[isq], y[isq]), 3), "gain_vs_current_boot": [round(float(np.mean(d)), 3), round(float(np.percentile(d, 2.5)), 3), round(float(np.percentile(d, 97.5)), 3)], "auc_devq": round(float(roc_auc_score(y[isq], P[isq])), 4)}; res["student_alone_gain_boot"] = [round(float(np.mean(ds)), 3), round(float(np.percentile(ds, 2.5)), 3), round(float(np.percentile(ds, 97.5)), 3)]
json.dump(res, open(f"runs/pulse/ft_stack_{V}.json", "w"), indent=1); print(json.dumps(res)); hb.finish("t20-ft-stack", "done", last=f"current {res['current_gate']}, student {res['student_alone']}, stack {res['stack_sparse_plus_student']['recall_at_0.83_devq']}")
