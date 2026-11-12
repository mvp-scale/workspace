"""T61: rank unlabelled CC-News articles by how unsure the T56 best encoder is (topic margin). Text = title + '. ' + description (the headline plus teaser form the heads were trained on), 64 tokens. Excludes ids already in the label store. Only a ranked list; no labels are requested.
    /workspace/models/embed-zs/.venv/bin/python queue_unsure.py [PER_FILE]  -> runs/queue/unsure_v1.jsonl, runs/queue/unsure_v1_summary.json"""
import json, os, sys, time, glob
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ.setdefault("HF_HOME", "/workspace/data/hf")
import numpy as np, torch, pyarrow.parquet as pq
from transformers import AutoModel, AutoTokenizer
T0 = time.time(); PER = int(sys.argv[1]) if len(sys.argv) > 1 else 8000; torch.set_num_threads(18); os.makedirs("runs/queue", exist_ok=True)
lab = {json.loads(l)["item_id"] for l in open("runs/label_store/labels.jsonl")}; rng = np.random.default_rng(7); rows = []
for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet")):
    t = pq.read_table(f, columns=["title", "description", "url", "domain", "date"]).to_pylist(); ix = rng.permutation(len(t))[:PER * 2]
    got = 0
    for k in ix:
        r = t[k]; d = " ".join((r["description"] or "").split()); ti = " ".join((r["title"] or "").split())
        if len(ti) < 10 or len(d) < 30 or "cc:" + (r["url"] or "") in lab: continue
        rows.append({"id": "cc:" + r["url"], "text": ti + ". " + d, "domain": r["domain"], "date": str(r["date"])[:10]}); got += 1
        if got >= PER: break
print("sampled", len(rows), f"{time.time() - T0:.0f}s", flush=True)
ck = torch.load("runs/expert1/leaf_ft_cpu2_best.pt"); n = "MongoDB/mdbr-leaf-mt"; tok = AutoTokenizer.from_pretrained(n); enc = AutoModel.from_pretrained(n); enc.load_state_dict(ck["enc"]); enc.eval(); H = enc.config.hidden_size
hs = torch.nn.ModuleDict({"topic": torch.nn.Linear(H, len(ck["topics"])), "story": torch.nn.Linear(H, len(ck["story_types"])), "pres": torch.nn.Linear(H, 2)}); hs.load_state_dict(ck["heads"]); out = []
with torch.no_grad():
    for k in range(0, len(rows), 128):
        b = rows[k:k + 128]; x = tok([r["text"] for r in b], padding=True, max_length=64, truncation=True, return_tensors="pt"); h = enc(**x).last_hidden_state; m = x["attention_mask"].unsqueeze(-1).float(); e = (h * m).sum(1) / m.sum(1)
        pt = hs["topic"](e).softmax(1); ps = hs["story"](e).softmax(1); pp = hs["pres"](e).softmax(1)[:, 1]; top2 = pt.topk(2, 1)
        for j, r in enumerate(b): out.append({**r, "topic": ck["topics"][int(top2.indices[j, 0])], "topic_p": round(float(top2.values[j, 0]), 3), "topic_margin": round(float(top2.values[j, 0] - top2.values[j, 1]), 3), "story": ck["story_types"][int(ps[j].argmax())], "story_p": round(float(ps[j].max()), 3), "presence_p": round(float(pp[j]), 3)})
        if (k // 128) % 40 == 0: print("scored", k, f"{time.time() - T0:.0f}s", flush=True)
out.sort(key=lambda r: r["topic_margin"])
with open("runs/queue/unsure_v1.jsonl", "w") as w:
    for r in out: w.write(json.dumps(r) + "\n")
mg = np.array([r["topic_margin"] for r in out]); dom = {}
for r in out[:2000]: dom[r["domain"]] = dom.get(r["domain"], 0) + 1
s = {"scored": len(out), "wall_s": round(time.time() - T0, 1), "share_margin_lt_0p20": round(float((mg < 0.20).mean()), 4), "share_margin_lt_0p10": round(float((mg < 0.10).mean()), 4), "median_margin": round(float(np.median(mg)), 3), "excluded_already_labelled": "ids in label store skipped while sampling", "queue_top": 2000, "top2000_distinct_domains": len(dom), "top2000_largest_domain_share": round(max(dom.values()) / 2000, 3), "top2000_topics": {t: sum(1 for r in out[:2000] if r["topic"] == t) for t in sorted({r["topic"] for r in out[:2000]})}, "encoder": "runs/expert1/leaf_ft_cpu2_best.pt"}
json.dump(s, open("runs/queue/unsure_v1_summary.json", "w"), indent=1); print(json.dumps({k: v for k, v in s.items() if k != "top2000_topics"}))
