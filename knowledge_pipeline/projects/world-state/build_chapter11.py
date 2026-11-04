"""Builds playbook/11-model-selection.md from the live field scans (stack_field.py) plus the measured results. Tables come from the data, text is ours.
    /workspace/models/embed-zs/.venv/bin/python build_chapter11.py"""
import json, re, pandas as pd, warnings
warnings.filterwarnings("ignore")
OPEN = re.compile(r"^(apache-2\.0|mit|bsd.*|cc-by-4\.0|cc0-1\.0|openrail.*)$", re.I)
A = pd.read_csv("runs/snapshots/stack_field_A_encoders.csv", index_col=0)
for c in ("params_m", "ctx", "layers", "downloads"): A[c] = pd.to_numeric(A[c], errors="coerce")
O = A[A.open == True]; BC = json.load(open("runs/snapshots/stack_field_BC.json"))
f1 = lambda v: "n/a" if pd.isna(v) else f"{v:.1f}"; pm = lambda v: "n/a" if pd.isna(v) else f"{v:.1f}M"; ctx = lambda v: "n/a" if pd.isna(v) else (f"{int(v):,}")
def enc_rows(df, mark=()):
    out = []
    for m, r in df.iterrows():
        flag = ("**" if m in mark else "")
        out.append(f"| {flag}{m}{flag} | {pm(r.params_m)} | {ctx(r.ctx)} | {r.arch} | {f1(r['mean'])} | {f1(r.Classification)} | {f1(r.Clustering)} | {f1(r.STS)} | {f1(r.PairClassification)} | {'yes' if r.onnx else 'no'} | {'**YES**' if r.custom_code else 'no'} | {r.updated} | {'yes' if r.trained_on else 'no'} |")
    return "\n".join(out)
HEAD = "| Model | Params | Context | Architecture | Mean | Classif. | Clustering | STS | Pair class. | ONNX in repo | Custom code | Updated | trained_on |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
mine = {"BAAI/bge-small-en-v1.5", "ibm-granite/granite-embedding-small-english-r2", "MongoDB/mdbr-leaf-mt"}
tiers = []
for lo, hi, nm in ((0, 60, "Up to 60M parameters (today's size class)"), (60, 200, "60M to 200M"), (200, 500, "200M to 500M")):
    t = O[(O.params_m > lo) & (O.params_m <= hi)].sort_values("mean", ascending=False); tiers.append(f"**{nm}** ({len(t)} open models scored; top 7)\n\n" + HEAD + enc_rows(t.head(7), mine))
best = []
for k, lab in (("Classification", "classification"), ("Clustering", "clustering"), ("STS", "similarity (STS)"), ("PairClassification", "duplicate / paraphrase detection"), ("Retrieval", "retrieval")):
    t = O[O.params_m <= 200].sort_values(k, ascending=False).head(3); best.append(f"| {lab} | " + "; ".join(f"{i.split('/')[-1]} {r[k]:.1f} ({r.params_m:.0f}M)" for i, r in t.iterrows()) + " |")
ours = A.reindex(["BAAI/bge-small-en-v1.5", "ibm-granite/granite-embedding-small-english-r2", "intfloat/e5-small-v2", "nomic-ai/nomic-embed-text-v1.5", "Snowflake/snowflake-arctic-embed-s", "minishlab/potion-base-32M", "jinaai/jina-embeddings-v2-small-en", "ibm-granite/granite-embedding-english-r2"])
def listing(name, n, extra_filter=None):
    df = pd.DataFrame(BC[name]).T; df["open"] = df.license.fillna("").apply(lambda s: bool(OPEN.match(str(s)))); df["params_m"] = pd.to_numeric(df.params_m, errors="coerce"); df["ctx"] = pd.to_numeric(df.ctx, errors="coerce")
    df = df[(df.open) & ((df.params_m <= 600) | df.params_m.isna())]
    if extra_filter is not None: df = df[extra_filter(df)]
    rows = ["| Model | Params | Context | Architecture | ONNX | Updated | Downloads |", "|---|---|---|---|---|---|---|"]
    for m, r in df.head(n).iterrows(): rows.append(f"| {m} | {pm(r.params_m)} | {ctx(r.ctx)} | {r.arch if isinstance(r.arch, str) else 'n/a'} | {'yes' if r.onnx else 'no'} | {r.updated} | {int(r.downloads):,} |")
    return "\n".join(rows)
G = listing("gliner", 8, lambda d: ~d.index.str.contains("OpenMed|GGUF", regex=True)); TC = listing("token-classification", 6, lambda d: ~d.index.str.contains("punctuat|posp|deid|PII|pii|Pharma|Disease|Anatomy|indonesian|OpenMed|GGUF", regex=True)); NLI = listing("zero-shot-classification", 7); NLI2 = listing("nli-text-classification", 5, lambda d: (d.updated >= "2025-06-01") & ~d.index.str.contains("GGUF")); RR = listing("reranker", 7)
txt = f"""# 11 · Model selection

**Goal:** choose the models for the WHOLE stack as one design (shared encoder, tags and spans, joining, claim comparison, whole articles), on measured fit for our CPU budget, from live data, never from reports or memory.

## Rules

1. **Scan the whole field from data, not from reports.** Encoders: the public `mteb/results` dataset (every model, per-task scores). Everything else: the Hugging Face catalogue by task and downloads. `stack_field.py` does the scan; reports and model cards are used only to read features. A garden built from three research reports missed strong models (L376); do not repeat it.
2. **Design the stack, then pick per stage.** One read per article feeds: fixed Pulse fields; free-form tags (Obsidian-style join keys naming capabilities, concepts, entities, merged to one canonical tag); a tag structure (capabilities at layers); and a knowledge layer that checks each new article against what we know (confirm, contradict, extend, gap), every statement traced to its source. Judge each candidate against all of that, not one head.
3. **Select on measured fit, not parameter count.** CPU only; whole item under 50 ms on one thread (gate Q28), of which the trunk gets about 30 ms and runs only on routed items; memory a few hundred MB up to about 1 GB (our own target). Report parameters, memory and latency for every candidate.
4. **A leaderboard is a screen, not a decision.** Shortlist from the scan, then decide on our own items: same later unseen set, same frozen-embedding heads, Q26 interval rule, through `score_version.py`. The decision rule is written before the scores; a tie keeps the incumbent. MTEB classification is generic English tasks, not news-topic classification.
5. **Read the flags.** `trained_on` = trained on benchmark training data: its scores are likely inflated. Custom code (`trust_remote_code`) needs the owner's yes. No ONNX in the repo = export is our work (load fp32 explicitly; the dynamo exporter needs `/workspace/models/onnx-export-pkgs`). Licence from the page metadata and card (most repos have no LICENSE file).
6. **Quantization is tested, not assumed.** One independent 2026 CPU study found int8 2.7 to 3.4 times faster but only 94 to 98 percent of retrieval quality. Our gate is Q22 (drop 0.01 or less).
7. **Long articles: chunk first.** Measured on 1,500 long articles (L373, L374): truncating at 512 loses the late part; one long-context pass (Granite 8k) recovers some; chunking a small model recovers more at far lower CPU cost. Long-context models stay a branch, not the default.
8. **Dates and benchmark versions matter.** Compare scores only inside one benchmark version (MTEB v1 and v2 are not comparable); record created and updated dates.
9. **Treat any report as a lead.** Only numbers we measure go in the ledger.

## The stack and what each stage needs

| Stage | Job | What the model must have | Where it stands |
|---|---|---|---|
| 1. Pulse heads (fixed fields) | Story type, topic, condition, direction, size from the same read | Good short-text classification; fast on one CPU thread; heads train cheaply | **Built** (BitMob Expert 1); trunk = mdbr-leaf-mt since 2026-11-01 (L381), was bge-small |
| 2. Tags and spans | Free-form tags naming capabilities, concepts, entities | Per-token states from the trunk (any transformer) with a span head, or a schema-driven extractor (GLiNER family) as a second stage | Not built; needs tag labels from full articles (tag pilot) |
| 3. Joining and clustering | Group articles and merge tag variants | Strong clustering, similarity and duplicate-detection scores; multi-vector chunks for long articles | Trunk scores below; chunking measured |
| 4. Canonical identity | Link a mention to one stable entity | Entity linking (ReFinED, entity-linkings) plus embedding merge | Not built |
| 5. Claim comparison | Agree, contradict, extend, gap between statements | Pairwise NLI cross-encoder; optional reranker for pair scoring | Not built (downstream, Understanding layer) |
| 6. Whole articles | Read beyond 512 tokens | Chunking, or a long-context encoder | Chunking measured; long-context branch open |

## Field scan A: shared encoders (English MTEB v2, 41 tasks)

215 models have 38 or more of the 41 tasks; 162 have an open licence; 130 of those need no custom code. "Mean" is our approximation of the leaderboard's Mean (Task), equal weight per task; verify on the live page before quoting. Bold = models we have measured or are about to.

{(chr(10)*2).join(tiers)}

**Best open model of 200M or fewer parameters per task type**

| Task type | Top three (score, parameters) |
|---|---|
{chr(10).join(best)}

**Our earlier shortlist, for reference.** bge-small ranks {int(ours.loc['BAAI/bge-small-en-v1.5','rank'])} of 215 (mean {ours.loc['BAAI/bge-small-en-v1.5','mean']:.1f}); granite-small-r2 {int(ours.loc['ibm-granite/granite-embedding-small-english-r2','rank'])} ({ours.loc['ibm-granite/granite-embedding-small-english-r2','mean']:.1f}, trained_on); e5-small-v2 {int(ours.loc['intfloat/e5-small-v2','rank'])} ({ours.loc['intfloat/e5-small-v2','mean']:.1f}); nomic-v1.5 {int(ours.loc['nomic-ai/nomic-embed-text-v1.5','rank'])} ({ours.loc['nomic-ai/nomic-embed-text-v1.5','mean']:.1f}); arctic-embed-s {int(ours.loc['Snowflake/snowflake-arctic-embed-s','rank'])} ({ours.loc['Snowflake/snowflake-arctic-embed-s','mean']:.1f}); potion-32M {int(ours.loc['minishlab/potion-base-32M','rank'])} ({ours.loc['minishlab/potion-base-32M','mean']:.1f}); jina-v2-small {int(ours.loc['jinaai/jina-embeddings-v2-small-en','rank'])} ({ours.loc['jinaai/jina-embeddings-v2-small-en','mean']:.1f}). gte-modernbert-base is not in the scored set.

**What the scan says for the stack**
- **Our size class has moved.** MongoDB/mdbr-leaf-mt (22.6M, Apache-2.0, 6-layer MiniLM, ONNX in the repo, no custom code, updated 2026-07, not trained_on) beats bge-small on the mean (+2.5), on generic classification (+14.7) and on similarity, at two-thirds the size and half the layers. It reads 512 tokens, so chunking applies.
- **Long context in small open models now also comes from Qwen3- and Gemma3-style embedders** (F2LLM-v2 80M and 160M at 40,960 tokens; harrier-oss-v1-270m at 32,768), not only ModernBERT (Granite, 8,192). None of them ship ONNX; F2LLM-v2 and harrier are trained_on.
- **Bigger is better on the mean, with a cost:** the 150M to 500M open models reach 67 to 71 (classification 82 to 90), but several need custom code (UltraBERT-Embed-150M, Giga-Embeddings-480M, KaLM v2.5) and none fits today's 50 ms budget on one thread without a measurement.

## Field scan B: tags and spans

No leaderboard covers open-vocabulary tagging, so this is the Hugging Face catalogue by downloads (open licence, up to 600M parameters; biomedical domain models removed). Quality numbers for these are author-reported; our own tag pilot decides.

**GLiNER family (zero-shot, schema-driven entity extraction)**

{G}

Newer, low-download models read from their cards on 2026-11-01: fastino/gliner2.5-small-v1 (73.9M, Apache-2.0, created 2026-08, 4,096 tokens; entities, text classification, relations and structured records in one model; no ONNX; independent F1 0.812, p50 132 ms on four cores) and fastino/gliner2-base-v1 (208.5M, F1 0.935, p50 190 ms); knowledgator/gliner-pii-edge-v1.0 (ONNX, fp16, uint8; PII-oriented).

**General token-classification models by downloads** (domain- and language-specific ones removed): no general-purpose open-vocabulary leader appears besides the GLiNER family.

{TC}

**Option that needs no extra model:** a token-level tagging head trained on the trunk's own per-token states (any transformer has them). This is the test the tag pilot enables.

**Entity linking** (stage 4): ReFinED (Apache-2.0, LICENSE file present, last commit 2024-12 whose message says "new license": reconfirm; Wikipedia/Wikidata IDs in one pass; AIDA micro-F1 86.6 author-reported) and the MIT `entity-linkings` library (BM25, dual encoder, reranker).

## Field scan C: claim comparison

**NLI cross-encoders** (zero-shot-classification listing, open licence, up to 600M parameters)

{NLI}

**Newer NLI models** (text-classification listing updated since 2025-06): small ModernBERT-family NLI with longer inputs.

{NLI2}

**Rerankers** (pair scoring for join and compare)

{RR}

For agree / contradict / neutral on short statement pairs, the cross-encoder/nli-deberta-v3 family and mixedbread's xsmall reranker are small with ONNX files; ModernCE and EttinX-nli add longer inputs. Latencies: nli-deberta-v3-xsmall int8 8.0 ms p50 and nli-MiniLM2 5.1 ms (independent test); the others are unmeasured.

## Features that matter (read from model cards, 2026-11-01)

- **Matryoshka (shrinkable vectors for fast coarse clustering):** nomic-embed-text-v1.5 (768 to 64 dimensions, custom code), arctic-embed-m-v2.0 (256), embeddinggemma (gated Gemma terms), granite 311M sibling.
- **Prefixes required:** e5 (`query:`/`passage:`), nomic (`search_document:`, `clustering:`, `classification:`).
- **Static embeddings (potion-base-32M):** near-instant, no token states, so no tagging; rank 168 of 215.
- **Raw ModernBERT-base:** a masked-language model with no embedding head (the base to fine-tune our own trunk); not a ready embedder.
- **ONNX/int8 in the repo:** mdbr-leaf-mt (fp32, fp16, q4), bge-small, e5-small-v2, arctic-embed-s, gte-small, the cross-encoder NLI family, gte-reranker-modernbert-base, mxbai-rerank-xsmall.

## Measured by us (all on the 1,466 later Sonnet-labelled items unless stated)

| Trunk | Result | Verdict |
|---|---|---|
| bge-small-en-v1.5 (v3.2) | topic top-2 0.877, which-condition 0.863, story 0.911; p95 36 ms, 732 MB | retired as trunk 2026-11-01 |
| granite-embedding-small-english-r2 (v4-granite) | topic top-2 0.881, which-condition 0.875, story 0.911; p95 44.5 ms, 837 MB | tied inside the noise; not adopted (L366, L368) |
| **mdbr-leaf-mt (v5-leaf)** | topic top-2 0.883, which-condition 0.875, story 0.911 (ties inside the noise); 95% of reads under 22.6 ms, 643 MB (v3.2: 36.6 ms, 724 MB, interleaved A/B); joining 0.683 vs 0.648; chunked whole-article late recall 0.859 vs 0.867 | **adopted as the trunk** (L378, L380, L381) |

Joining quality (neighbour topic agreement; NMI): bge 0.648 / 0.408, Granite 0.634 / 0.383 (L371). Whole articles (1,500 long articles, passage from the late part finds its article, recall@1): bge truncated 0.503, Granite truncated 0.511, Granite 8k 0.643, bge chunked mean 0.771, bge best chunk 0.867 (L373, L374). Leaf-model detail: the speed and memory comparison with v3.2 was run interleaved (A/B, same period) because single runs are disturbed by occasional stalls of unknown cause (they hit v3.2 in 2 of 4 runs, the leaf version in 0 of 4). Lessons: transformers 5 loads bf16 by default, which onnxruntime CPU cannot run; the artefact names its own ONNX and tokenizer files; the Pulse fields do not separate trunks, so the trunk question is settled by joining, tagging and whole-article tests, not by Pulse.

## Plan for the stack (to be confirmed by measurement, in this order)

1. **Trunk: done.** mdbr-leaf-mt replaced bge-small after it met all three adoption rules (L381). Its embedding is 1,024-dimensional (a Dense layer after mean pooling), 512-token input: long articles are chunked. If long input matters after the tag pilot, branch to F2LLM-v2-80M or harrier-oss-v1-270m (no ONNX: export is our work).
2. **Tags and spans:** run the tag pilot on full articles; compare a token head on the trunk against GLiNER2.5-small as a second stage on the same items.
3. **Joining:** trunk embeddings with chunking, joined at the tag level; add Matryoshka only if coarse clustering needs it.
4. **Claims:** nli-deberta-v3-xsmall as the first test; ModernCE-base-nli if longer statements matter; a reranker only if pair scoring needs it.
5. **Linking:** ReFinED after tags exist.

## Sources

Scans run 2026-11-01: `mteb_field.py`, `stack_field.py` (results in `runs/snapshots/stack_field_A_encoders.csv`, `stack_field_BC.json`); public dataset https://huggingface.co/datasets/mteb/results; task list from the mteb benchmark definition (https://github.com/embeddings-benchmark/mteb); model facts from the Hugging Face API and cards; Vespa CPU study https://blog.vespa.ai/embedding-tradeoffs-quantified/ (2026-01-14). The earlier research reports are superseded and not relied on.
"""
open("../../playbook/11-model-selection.md", "w").write(txt); print(len(txt))
