"""Field scan for the WHOLE stack (L377). Every stage is read from live data, not from reports:
  A shared encoder: public mteb/results dataset (all models, per-task scores), English v2 task set (41 tasks) with exact task types; size, licence, dates, context, ONNX, custom code from the Hugging Face API.
  B tagging and span extraction: Hugging Face catalogue, GLiNER-family and token-classification models by downloads.
  C claim comparison: NLI / zero-shot-classification cross-encoders and rerankers by downloads.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python stack_field.py      network read only; no code from any model is run; writes runs/snapshots/stack_field.json + stack_field_*.csv"""
import json, re, sys, urllib.request, numpy as np, pandas as pd, pyarrow.parquet as pq, warnings
warnings.filterwarnings("ignore")
from huggingface_hub import HfFileSystem, HfApi
api = HfApi(); OPEN = re.compile(r"^(apache-2\.0|mit|bsd.*|cc-by-4\.0|cc0-1\.0|openrail.*)$", re.I)
TYPES = {"Classification": ["AmazonCounterfactualClassification", "Banking77Classification", "ImdbClassification", "MTOPDomainClassification", "MassiveIntentClassification", "MassiveScenarioClassification", "ToxicConversationsClassification", "TweetSentimentExtractionClassification"],
 "Clustering": ["ArXivHierarchicalClusteringP2P", "ArXivHierarchicalClusteringS2S", "BiorxivClusteringP2P.v2", "MedrxivClusteringP2P.v2", "MedrxivClusteringS2S.v2", "StackExchangeClustering.v2", "StackExchangeClusteringP2P.v2", "TwentyNewsgroupsClustering.v2"],
 "PairClassification": ["SprintDuplicateQuestions", "TwitterSemEval2015", "TwitterURLCorpus"], "Reranking": ["AskUbuntuDupQuestions", "MindSmallReranking"],
 "Retrieval": ["ArguAna", "CQADupstackGamingRetrieval", "CQADupstackUnixRetrieval", "ClimateFEVERHardNegatives", "FEVERHardNegatives", "FiQA2018", "HotpotQAHardNegatives", "SCIDOCS", "TRECCOVID", "Touche2020Retrieval.v3"],
 "STS": ["BIOSSES", "SICK-R", "STS12", "STS13", "STS14", "STS15", "STSBenchmark", "STS17", "STS22.v2"], "Summarization": ["SummEvalSummarization.v2"]}
T = [t for v in TYPES.values() for t in v]; assert len(T) == 41; SUB = {"AmazonCounterfactualClassification": "en", "STS17": "en-en", "STS22.v2": "en"}; fs = HfFileSystem(); frames = []
for k in range(4):
    df = pq.ParquetFile(fs.open(f"datasets/mteb/results/data/train-0000{k}-of-00004.parquet")).read(columns=["model_name", "task_name", "split", "subset", "score", "trained_on"]).to_pandas(); frames.append(df[df.task_name.isin(T)])
d = pd.concat(frames); d = d[d.split.isin(["test", "validation"])]; d = d[d.apply(lambda r: (r.subset == SUB[r.task_name]) if r.task_name in SUB else True, axis=1)]
g = d.groupby(["model_name", "task_name"]).score.mean().unstack(); cov = g.notna().sum(1); g = g[cov >= 38]
out = pd.DataFrame({"mean": g.mean(axis=1) * 100})
for k, ts in TYPES.items(): out[k] = g[[t for t in ts if t in g.columns]].mean(axis=1) * 100
out["trained_on"] = d.groupby("model_name").trained_on.max().reindex(out.index); out = out.sort_values("mean", ascending=False); out["rank"] = np.arange(1, len(out) + 1); print("A: models", len(out), flush=True)
def info(m):
    try:
        x = api.model_info(m, expand=["safetensors", "createdAt", "lastModified", "cardData", "tags", "downloads", "siblings"]); lic = (x.card_data.get("license") if x.card_data else None) or next((t.split(":", 1)[1] for t in (x.tags or []) if t.startswith("license:")), None)
        fl = [s.rfilename for s in (x.siblings or [])]; cfg = {}
        try: cfg = json.load(urllib.request.urlopen(f"https://huggingface.co/{m}/raw/main/config.json", timeout=15))
        except Exception: pass
        sb = {}
        try: sb = json.load(urllib.request.urlopen(f"https://huggingface.co/{m}/raw/main/sentence_bert_config.json", timeout=15))
        except Exception: pass
        return {"params_m": round(x.safetensors.total / 1e6, 1) if x.safetensors else None, "license": lic, "created": str(x.created_at)[:10], "updated": str(x.last_modified)[:10], "downloads": x.downloads, "arch": cfg.get("model_type"), "ctx": sb.get("max_seq_length") or cfg.get("max_position_embeddings"), "layers": cfg.get("num_hidden_layers"), "custom_code": bool(cfg.get("auto_map")), "onnx": bool([f for f in fl if f.endswith(".onnx")]), "base": (x.card_data.get("base_model") if x.card_data else None)}
    except Exception as e: return {"err": type(e).__name__}
cand = list(out.index[:300]); I = {m: info(m) for m in cand}; A = out.join(pd.DataFrame(I).T); A["open"] = A.license.fillna("").apply(lambda s: bool(OPEN.match(str(s)))); A.to_csv("runs/snapshots/stack_field_A_encoders.csv"); print("A features fetched for", len(I), flush=True)
def listing(**kw):
    rows = []
    for m in api.list_models(**kw):
        rows.append(m.id)
    return rows
B = {}
for name, kw in (("gliner", dict(filter="gliner", sort="downloads", limit=60)), ("token-classification", dict(pipeline_tag="token-classification", sort="downloads", limit=60)), ("nli-text-classification", dict(search="nli", pipeline_tag="text-classification", sort="downloads", limit=60)), ("zero-shot-classification", dict(pipeline_tag="zero-shot-classification", sort="downloads", limit=60)), ("reranker", dict(search="rerank", sort="downloads", limit=60))):
    ids = listing(**kw); B[name] = {m: info(m) for m in ids}; print("B/C", name, len(ids), flush=True)
json.dump(B, open("runs/snapshots/stack_field_BC.json", "w"), indent=1)
