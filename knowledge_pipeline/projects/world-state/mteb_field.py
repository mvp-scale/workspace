"""Scan the whole MTEB field (L376): every model in the public mteb/results dataset, scored on the English v2 task set (38 tasks from the mteb benchmark definition + AmazonCounterfactualClassification (en), STS17 (en-en), STS22.v2 (en) = 41 tasks), then size / licence / dates from the Hugging Face API.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python mteb_field.py      network read only, no hosted-model calls, no code from the models run
Scores are the dataset's `score` (the task main score), averaged over splits/subsets kept; equal weight per task. Approximates the leaderboard's Mean (Task); verify against the live page before quoting."""
import json, re, sys, time, numpy as np, pandas as pd, pyarrow.parquet as pq
from huggingface_hub import HfFileSystem, HfApi
T = [l.strip() for l in open("runs/snapshots/mteb_eng_v2_tasks.txt") if l.strip()] + ["AmazonCounterfactualClassification", "STS17", "STS22.v2"]; SUB = {"AmazonCounterfactualClassification": "en", "STS17": "en-en", "STS22.v2": "en"}
fs = HfFileSystem(); frames = []
for k in range(4):
    f = pq.ParquetFile(fs.open(f"datasets/mteb/results/data/train-0000{k}-of-00004.parquet")); df = f.read(columns=["model_name", "task_name", "split", "subset", "score", "trained_on", "is_public"]).to_pandas()
    df = df[df.task_name.isin(T)]; frames.append(df); print("file", k, len(df), flush=True)
d = pd.concat(frames); d = d[d.split.isin(["test", "validation"])]
keep = d.apply(lambda r: (r.subset == SUB[r.task_name]) if r.task_name in SUB else True, axis=1) if len(d) < 3_000_000 else None
d = d[keep] if keep is not None else d
g = d.groupby(["model_name", "task_name"]).score.mean().unstack(); cov = g.notna().sum(1); print("models with any English-v2 score:", len(g), "| with all 41:", int((cov == 41).sum()), "| with 38+:", int((cov >= 38).sum()), flush=True)
PAIR = {"SprintDuplicateQuestions", "TwitterSemEval2015", "TwitterURLCorpus"}
grp = {"classification": [t for t in T if "Classification" in t and t not in PAIR], "clustering": [t for t in T if "Clustering" in t], "sts": [t for t in T if t.startswith("STS") or t in ("SICK-R", "BIOSSES")]}
res = g[cov >= 38].copy(); out = pd.DataFrame({"mean": res.mean(1) * 100}); 
for k, ts in grp.items(): out[k] = res[[t for t in ts if t in res.columns]].mean(1) * 100
tr = d.groupby("model_name").trained_on.max(); out["trained_on"] = tr.reindex(out.index); out["tasks"] = cov[out.index]; out = out.sort_values("mean", ascending=False); print("scored models kept:", len(out), flush=True)
api = HfApi(); info = {}
want = list(out.index[:260]) + [m for m in ("BAAI/bge-small-en-v1.5", "ibm-granite/granite-embedding-small-english-r2", "intfloat/e5-small-v2", "Alibaba-NLP/gte-modernbert-base", "nomic-ai/nomic-embed-text-v1.5", "Snowflake/snowflake-arctic-embed-s", "minishlab/potion-base-32M", "jinaai/jina-embeddings-v2-small-en", "ibm-granite/granite-embedding-english-r2") if m in out.index]
for m in dict.fromkeys(want):
    try:
        x = api.model_info(m, expand=["safetensors", "createdAt", "lastModified", "cardData", "tags"]); lic = (x.card_data.get("license") if x.card_data else None) or next((t.split(":", 1)[1] for t in (x.tags or []) if t.startswith("license:")), None)
        info[m] = {"params_m": round(x.safetensors.total / 1e6, 1) if x.safetensors else None, "license": lic, "created": str(x.created_at)[:10], "updated": str(x.last_modified)[:10]}
    except Exception as e: info[m] = {"params_m": None, "license": None, "created": None, "updated": None, "err": type(e).__name__}
I = pd.DataFrame(info).T; out = out.join(I); out["rank_all"] = np.arange(1, len(out) + 1)
OPEN = re.compile(r"^(apache-2\.0|mit|bsd.*|cc-by-4\.0|cc0-1\.0|openrail.*)$", re.I); out["open_licence"] = out.license.fillna("").apply(lambda s: bool(OPEN.match(str(s))))
out.to_csv("runs/snapshots/mteb_field.csv"); print("saved", len(out))
