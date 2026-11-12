"""T59: paired sealed comparison of the T56 best encoder (3 heads, leaf_ft_cpu2_best.pt) and the adopted v6b-student on the same sealed items. Judge: agreement with Sonnet, not outside truth. Candidate only; adopting it is the owner's engine decision.
    /workspace/models/embed-zs/.venv/bin/python compare_v6b.py -> runs/pulse/compare_v6b.json"""
import json, os, sys
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ.setdefault("HF_HOME", "/workspace/data/hf")
import numpy as np, torch
from transformers import AutoModel, AutoTokenizer
sys.path.insert(0, "."); from expert1_runtime import ExpertS
torch.set_num_threads(18); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sid = sorted(i for i in S if i in txt)
ck = torch.load("runs/expert1/leaf_ft_cpu2_best.pt"); TOP, ST = ck["topics"], ck["story_types"]; n = "MongoDB/mdbr-leaf-mt"; tok = AutoTokenizer.from_pretrained(n); enc = AutoModel.from_pretrained(n); enc.load_state_dict(ck["enc"]); enc.eval(); H = enc.config.hidden_size
hd = {"topic": torch.nn.Linear(H, len(TOP)), "story": torch.nn.Linear(H, len(ST))}
for k, m in hd.items(): m.load_state_dict({kk.split(".", 1)[1]: v for kk, v in ck["heads"].items() if kk.startswith(k + ".")})
T1, T2, SS = [], [], []
with torch.no_grad():
    for k in range(0, len(sid), 128):
        x = tok([txt[i] for i in sid[k:k + 128]], padding=True, max_length=64, truncation=True, return_tensors="pt"); h = enc(**x).last_hidden_state; m = x["attention_mask"].unsqueeze(-1).float(); e = (h * m).sum(1) / m.sum(1)
        lt = hd["topic"](e); o = lt.argsort(1, descending=True)[:, :2].numpy(); T1 += [TOP[a[0]] for a in o]; T2 += [[TOP[b] for b in a] for a in o]; SS += [ST[a] for a in hd["story"](e).argmax(1).numpy()]
v = ExpertS("runs/expert1/expert1_v6b_student.pkl"); R = [v.read(txt[i]) for i in sid]
gt = [S[i]["topic"] for i in sid]; gs = [S[i]["story_type"] for i in sid]
enc_s = np.array([a == b for a, b in zip(SS, gs)]); v_s = np.array([r["story_type"]["status"] == "answered" and r["story_type"]["answer"] == g for r, g in zip(R, gs)])
enc_t2 = np.array([g in a for a, g in zip(T2, gt)]); v_t2 = np.array([r["topic_top2"]["status"] == "answered" and g in (r["topic_top2"]["answer"] or []) for r, g in zip(R, gt)]); enc_t1 = np.array([a == g for a, g in zip(T1, gt)])
rg = np.random.default_rng(7); ix = [rg.integers(0, len(sid), len(sid)) for _ in range(1000)]
def pair(a, b): d = [a[i].mean() - b[i].mean() for i in ix]; return {"encoder": round(float(a.mean()), 4), "v6b": round(float(b.mean()), 4), "diff": round(float(a.mean() - b.mean()), 4), "diff_ci95": [round(float(np.percentile(d, 2.5)), 4), round(float(np.percentile(d, 97.5)), 4)]}
out = {"judge": "agreement with Sonnet on the sealed set, not outside truth", "n": len(sid), "story_type": pair(enc_s, v_s), "topic_top2": pair(enc_t2, v_t2), "encoder_topic_top1": round(float(enc_t1.mean()), 4), "note": "v6b abstains count as wrong; encoder answers every item; candidate only, engine decision is the owner's"}
json.dump(out, open("runs/pulse/compare_v6b.json", "w"), indent=1); print(json.dumps(out))
