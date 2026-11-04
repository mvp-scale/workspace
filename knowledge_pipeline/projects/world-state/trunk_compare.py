"""Long-term feature comparison of two trunks on our own items (L366 follow-up): joining quality and long-input cost.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python trunk_compare.py      local GPU about 2 min for the embeddings, CPU for the rest, no hosted calls
A: nearest-neighbour topic agreement (later Sonnet items vs training-period Haiku labels) and k-means NMI vs the Haiku topic. B: ms per text on one CPU thread by token length."""
import os, sys, json, re, glob, time, numpy as np, torch
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"
from sentence_transformers import SentenceTransformer
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; ids = json.load(open("runs/embeds/bge_small_ids.json"))
hk = {}; old = {}; sn = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]; old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7/more*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]; test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test); vt = [i for i in test if i in sn]
trn = [i for i in hk if i not in tset and pool[i]["date"] and pool[i]["date"] < start]; clean = lambda i: re.sub(r"\s+", " ", pool[i]["text"])[:3000]
MODELS = {"bge-small-en-v1.5": ("BAAI/bge-small-en-v1.5", 512), "granite-small-r2": ("ibm-granite/granite-embedding-small-english-r2", 8192), "mdbr-leaf-mt": ("MongoDB/mdbr-leaf-mt", 512)}
if os.environ.get("ONLY"): MODELS = {k: v for k, v in MODELS.items() if k in os.environ["ONLY"].split(",")}; res = {"n_train": len(trn), "n_query": len(vt), "A": {}, "B": {}}
from sklearn.cluster import KMeans; from sklearn.metrics import normalized_mutual_info_score as nmi
ytr = np.array([hk[i]["topic"] for i in trn]); yq = np.array([sn[i]["topic"] for i in vt])
for name, (rid, mx) in MODELS.items():
    st = SentenceTransformer(rid, device="cuda", model_kwargs={"dtype": torch.float32}); st.max_seq_length = 512; t0 = time.time()
    Etr = st.encode([clean(i) for i in trn], batch_size=128, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True); Eq = st.encode([clean(i) for i in vt], batch_size=128, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True)
    S = torch.tensor(Eq, device="cuda") @ torch.tensor(Etr, device="cuda").T; top = S.topk(5, dim=1).indices.cpu().numpy(); nb = ytr[top]
    top1 = float(np.mean(nb[:, 0] == yq)); maj = float(np.mean([(np.bincount(np.searchsorted(np.unique(ytr), nb[k])).argmax() == np.searchsorted(np.unique(ytr), yq[k])) if yq[k] in set(ytr) else False for k in range(len(yq))])); any5 = float(np.mean([yq[k] in set(nb[k]) for k in range(len(yq))]))
    km = KMeans(n_clusters=49, n_init=1, random_state=0).fit(Etr); res["A"][name] = {"nn_top1_topic": round(top1, 4), "nn_majority5_topic": round(maj, 4), "nn_any_of_5_topic": round(any5, 4), "kmeans49_nmi_vs_topic": round(float(nmi(ytr, km.labels_)), 4), "embed_s": round(time.time() - t0)}; print(name, res["A"][name], flush=True)
    del st; torch.cuda.empty_cache()
torch.set_num_threads(1); words = " ".join(clean(i) for i in trn[:3000]).split()
for name, (rid, mx) in MODELS.items():
    st = SentenceTransformer(rid, device="cpu", model_kwargs={"dtype": torch.float32}); res["B"][name] = {}
    for L in (64, 128, 256, 512, 1024, 2048, 4096, 8192):
        if L > mx: continue
        st.max_seq_length = L; txt = " ".join(words[:int(L * 0.85)]); ntok = len(st.tokenizer(txt, truncation=True, max_length=L)["input_ids"]); st.encode([txt], batch_size=1); ts = []
        for _ in range(3 if L <= 1024 else 1): a = time.perf_counter(); st.encode([txt], batch_size=1); ts.append((time.perf_counter() - a) * 1000)
        res["B"][name][str(L)] = {"tokens": ntok, "ms": round(float(np.median(ts)))}; print(name, L, res["B"][name][str(L)], flush=True)
    del st
json.dump(res, open(os.environ.get("OUT", "runs/snapshots/trunk_compare.json"), "w"), indent=1)
