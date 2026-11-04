"""T20 active labelling (ledger L482): score the unlabelled training-period items with the v6b student on the GPU and select 10,000 for Sonnet: the 6,000 with the highest presence probability plus 4,000 random from the 0.15 to 0.85 band. Writes runs/pulse/tranche2/c0..c3_items.jsonl (2,500 each)."""
import os, sys, json, glob, random, numpy as np, torch
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"
from sentence_transformers import SentenceTransformer
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; M = json.load(open("runs/pulse/ceiling/main_ids.json")); train_ids = M["ids"][:M["n_train"]]
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; sn = set()
for f in glob.glob("runs/p7b/*/labels.jsonl") + glob.glob("runs/pulse/tranche/c*/labels.jsonl") + glob.glob("runs/p6/sonnet/*.jsonl"):
    for r in J(f):
        if "item_id" in r: sn.add(r["item_id"])
cand = [i for i in train_ids if i not in sn]; print("unlabelled training-period items", len(cand), flush=True)
ck = torch.load("runs/pulse/ceiling/ft_B_t16e16lr5.pt", map_location="cuda"); m = SentenceTransformer("MongoDB/mdbr-leaf-mt", device="cuda"); m.max_seq_length = 64; m.load_state_dict(ck["st_full"]); m.eval(); Wp = ck["heads"]["p.weight"].float(); bp = ck["heads"]["p.bias"].float(); P = []
with torch.no_grad():
    for k in range(0, len(cand), 512):
        f = {a: b.to("cuda") for a, b in m.tokenize([pool[i]["text"] for i in cand[k:k + 512]]).items() if torch.is_tensor(b)}
        with torch.autocast("cuda", dtype=torch.bfloat16): e = m(f)["sentence_embedding"].float()
        lp = e @ Wp.T + bp; P.append(lp.softmax(1)[:, 1].cpu().numpy())
P = np.concatenate(P); o = np.argsort(-P); top = [cand[k] for k in o[:6000]]; band = [cand[k] for k in range(len(cand)) if 0.15 <= P[k] <= 0.85 and cand[k] not in set(top)]; r = random.Random(20261103); mid = r.sample(band, min(4000, len(band)))
pick = top + mid; r.shuffle(pick); print("top6000 min prob", round(float(P[o[5999]]), 3), "| band candidates", len(band), "| picked", len(pick), "| mean prob picked", round(float(np.mean([P[cand.index(i)] for i in pick[:300]])), 3), flush=True)
out = pathlib = __import__("pathlib").Path("runs/pulse/tranche2"); out.mkdir(exist_ok=True)
for c in range(4):
    ids = pick[c * 2500:(c + 1) * 2500]; (out / f"c{c}_items.jsonl").write_text("".join(json.dumps({k: pool[i][k] for k in ("id", "text", "date", "from")}) + "\n" for i in ids))
print("written", len(pick))
