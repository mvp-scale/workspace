# 11 · Model selection

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

**Up to 60M parameters (today's size class)** (32 open models scored; top 7)

| Model | Params | Context | Architecture | Mean | Classif. | Clustering | STS | Pair class. | ONNX in repo | Custom code | Updated | trained_on |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **MongoDB/mdbr-leaf-mt** | 22.6M | 512 | bert | 64.0 | 76.7 | 46.7 | 82.6 | 84.0 | yes | no | 2026-07-20 | no |
| avsolatorio/NoInstruct-small-Embedding-v0 | 33.4M | 512 | bert | 62.8 | 66.1 | 47.9 | 82.8 | 85.1 | no | no | 2024-05-04 | no |
| avsolatorio/GIST-small-Embedding-v0 | 33.4M | 512 | bert | 61.8 | 63.1 | 48.0 | 82.8 | 84.8 | yes | no | 2025-04-17 | yes |
| **BAAI/bge-small-en-v1.5** | 33.4M | 512 | bert | 61.5 | 62.0 | 47.0 | 81.3 | 84.9 | yes | no | 2024-02-22 | no |
| abhinand/MedEmbed-small-v0.1 | 33.4M | 512 | bert | 61.1 | 61.5 | 47.0 | 81.3 | 84.7 | no | no | 2024-10-23 | yes |
| **ibm-granite/granite-embedding-small-english-r2** | 47.7M | 8,192 | modernbert | 61.1 | 68.2 | 46.5 | 76.6 | 78.6 | no | no | 2026-01-21 | yes |
| thenlper/gte-small | 33.4M | 512 | bert | 60.6 | 61.6 | 47.4 | 81.9 | 83.7 | yes | no | 2024-11-16 | no |

**60M to 200M** (39 open models scored; top 7)

| Model | Params | Context | Architecture | Mean | Classif. | Clustering | STS | Pair class. | ONNX in repo | Custom code | Updated | trained_on |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dmis-lab/UltraBERT-Embed-150M | 151.0M | n/a | ultrabert | 67.2 | 81.7 | 49.7 | 83.0 | 85.3 | no | **YES** | 2026-10-16 | yes |
| codefuse-ai/F2LLM-v2-160M | 159.2M | 40,960 | qwen3 | 65.5 | 85.1 | 52.5 | 80.8 | 82.1 | no | no | 2026-09-03 | yes |
| prdev/mini-gte | 66.4M | 512 | distilbert | 65.1 | 80.0 | 47.9 | 81.6 | 84.8 | no | no | 2025-02-07 | yes |
| codefuse-ai/F2LLM-v2-80M | 80.1M | 40,960 | qwen3 | 64.1 | 83.9 | 50.7 | 79.7 | 80.2 | no | no | 2026-09-03 | yes |
| ibm-granite/granite-embedding-english-r2 | 149.0M | 8,192 | modernbert | 62.8 | 70.7 | 47.2 | 78.1 | 79.3 | no | no | 2026-01-06 | yes |
| avsolatorio/GIST-Embedding-v0 | 109.5M | 512 | bert | 62.7 | 63.7 | 48.5 | 83.3 | 86.3 | no | no | 2024-02-28 | yes |
| BAAI/bge-base-en-v1.5 | 109.5M | 512 | bert | 62.3 | 63.2 | 47.4 | 82.1 | 86.6 | yes | no | 2024-02-21 | no |

**200M to 500M** (35 open models scored; top 7)

| Model | Params | Context | Architecture | Mean | Classif. | Clustering | STS | Pair class. | ONNX in repo | Custom code | Updated | trained_on |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KaLM-Embedding/KaLM-embedding-multilingual-mini-instruct-v2.5 | 494.0M | 32,768 | qwen2 | 71.3 | 90.5 | 58.1 | 84.8 | 86.6 | no | **YES** | 2026-10-31 | yes |
| ai-sage/Giga-Embeddings-instruct-480M-0826 | 483.7M | 8,192 | qwen3_bidirec | 69.5 | 89.7 | 55.2 | 82.3 | 84.8 | no | **YES** | 2026-09-14 | no |
| codefuse-ai/F2LLM-v2-330M | 334.3M | 40,960 | qwen3 | 68.6 | 88.3 | 56.5 | 82.8 | 84.2 | no | no | 2026-09-03 | yes |
| microsoft/harrier-oss-v1-270m | 268.1M | 32,768 | gemma3_text | 67.2 | 83.0 | 53.6 | 83.5 | 83.4 | no | no | 2026-03-30 | yes |
| NovaSearch/stella_en_400M_v5 | 435.2M | 512 | new | 65.9 | 70.2 | 57.7 | 83.9 | 87.3 | no | **YES** | 2025-07-28 | yes |
| VPLabs/SearchMap_Preview | 434.1M | 8,192 | new | 64.1 | 75.0 | 48.5 | 81.6 | 84.9 | no | **YES** | 2025-07-31 | no |
| WhereIsAI/UAE-Large-V1 | 335.1M | 512 | bert | 63.7 | 65.2 | 47.9 | 84.4 | 87.3 | yes | no | 2025-07-29 | no |

**Best open model of 200M or fewer parameters per task type**

| Task type | Top three (score, parameters) |
|---|---|
| classification | F2LLM-v2-160M 85.1 (159M); F2LLM-v2-80M 83.9 (80M); UltraBERT-Embed-150M 81.7 (151M) |
| clustering | F2LLM-v2-160M 52.5 (159M); F2LLM-v2-80M 50.7 (80M); UltraBERT-Embed-150M 49.7 (151M) |
| similarity (STS) | GIST-Embedding-v0 83.3 (110M); UltraBERT-Embed-150M 83.0 (151M); GIST-small-Embedding-v0 82.8 (33M) |
| duplicate / paraphrase detection | bge-base-en-v1.5 86.6 (110M); GIST-Embedding-v0 86.3 (110M); e5-base-v2 85.7 (110M) |
| retrieval | snowflake-arctic-embed-m-v1.5 58.1 (109M); snowflake-arctic-embed-m 57.5 (109M); UltraBERT-Embed-150M 57.2 (151M) |

**Our earlier shortlist, for reference.** bge-small ranks 96 of 215 (mean 61.5); granite-small-r2 102 (61.1, trained_on); e5-small-v2 134 (58.9); nomic-v1.5 125 (59.5); arctic-embed-s 128 (59.1); potion-32M 168 (54.6); jina-v2-small 182 (49.9). gte-modernbert-base is not in the scored set.

**What the scan says for the stack**
- **Our size class has moved.** MongoDB/mdbr-leaf-mt (22.6M, Apache-2.0, 6-layer MiniLM, ONNX in the repo, no custom code, updated 2026-07, not trained_on) beats bge-small on the mean (+2.5), on generic classification (+14.7) and on similarity, at two-thirds the size and half the layers. It reads 512 tokens, so chunking applies.
- **Long context in small open models now also comes from Qwen3- and Gemma3-style embedders** (F2LLM-v2 80M and 160M at 40,960 tokens; harrier-oss-v1-270m at 32,768), not only ModernBERT (Granite, 8,192). None of them ship ONNX; F2LLM-v2 and harrier are trained_on.
- **Bigger is better on the mean, with a cost:** the 150M to 500M open models reach 67 to 71 (classification 82 to 90), but several need custom code (UltraBERT-Embed-150M, Giga-Embeddings-480M, KaLM v2.5) and none fits today's 50 ms budget on one thread without a measurement.

## Field scan B: tags and spans

No leaderboard covers open-vocabulary tagging, so this is the Hugging Face catalogue by downloads (open licence, up to 600M parameters; biomedical domain models removed). Quality numbers for these are author-reported; our own tag pilot decides.

**GLiNER family (zero-shot, schema-driven entity extraction)**

| Model | Params | Context | Architecture | ONNX | Updated | Downloads |
|---|---|---|---|---|---|---|
| urchade/gliner_large-v2 | 459.5M | n/a | n/a | no | 2024-07-12 | 244,613 |
| urchade/gliner_multi_pii-v1 | n/a | n/a | n/a | no | 2024-04-20 | 98,411 |
| urchade/gliner_small-v2.1 | n/a | n/a | n/a | no | 2024-04-10 | 93,229 |
| urchade/gliner_medium-v2.1 | 195.2M | n/a | n/a | no | 2024-08-21 | 30,876 |
| urchade/gliner_multi-v2.1 | 288.9M | n/a | n/a | no | 2025-12-08 | 22,789 |

Newer, low-download models read from their cards on 2026-11-01: fastino/gliner2.5-small-v1 (73.9M, Apache-2.0, created 2026-08, 4,096 tokens; entities, text classification, relations and structured records in one model; no ONNX; independent F1 0.812, p50 132 ms on four cores) and fastino/gliner2-base-v1 (208.5M, F1 0.935, p50 190 ms); knowledgator/gliner-pii-edge-v1.0 (ONNX, fp16, uint8; PII-oriented).

**General token-classification models by downloads** (domain- and language-specific ones removed): no general-purpose open-vocabulary leader appears besides the GLiNER family.

| Model | Params | Context | Architecture | ONNX | Updated | Downloads |
|---|---|---|---|---|---|---|
| dslim/bert-base-NER | 108.3M | 512 | bert | yes | 2024-10-08 | 1,046,372 |
| microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank | 177.3M | 512 | bert | no | 2025-01-08 | 765,454 |
| segment-any-text/sat-3l-sm | 213.7M | 514 | xlm-token | yes | 2024-09-24 | 465,098 |
| urchade/gliner_large-v2 | 459.5M | n/a | n/a | no | 2024-07-12 | 244,613 |
| segment-any-text/sat-12l-sm | 277.5M | 514 | xlm-token | yes | 2024-09-24 | 165,094 |
| dslim/bert-large-NER | 333.6M | 512 | bert | yes | 2024-10-08 | 157,863 |

**Option that needs no extra model:** a token-level tagging head trained on the trunk's own per-token states (any transformer has them). This is the test the tag pilot enables.

**Entity linking** (stage 4): ReFinED (Apache-2.0, LICENSE file present, last commit 2024-12 whose message says "new license": reconfirm; Wikipedia/Wikidata IDs in one pass; AIDA micro-F1 86.6 author-reported) and the MIT `entity-linkings` library (BM25, dual encoder, reranker).

## Field scan C: claim comparison

**NLI cross-encoders** (zero-shot-classification listing, open licence, up to 600M parameters)

| Model | Params | Context | Architecture | ONNX | Updated | Downloads |
|---|---|---|---|---|---|---|
| facebook/bart-large-mnli | 407.3M | 1,024 | bart | no | 2023-09-05 | 2,608,438 |
| MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7 | 278.8M | 512 | deberta-v2 | yes | 2024-04-11 | 883,176 |
| cross-encoder/nli-deberta-v3-small | 141.9M | 512 | deberta-v2 | yes | 2025-04-15 | 415,349 |
| joeddav/xlm-roberta-large-xnli | 560.9M | 514 | xlm-roberta | no | 2024-10-16 | 380,754 |
| MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli | 184.4M | 512 | deberta-v2 | no | 2024-04-11 | 358,824 |
| cross-encoder/nli-deberta-v3-base | 184.4M | 512 | deberta-v2 | yes | 2025-04-11 | 238,630 |
| cross-encoder/nli-MiniLM2-L6-H768 | 82.1M | 514 | roberta | yes | 2025-04-15 | 192,776 |

**Newer NLI models** (text-classification listing updated since 2025-06): small ModernBERT-family NLI with longer inputs.

| Model | Params | Context | Architecture | ONNX | Updated | Downloads |
|---|---|---|---|---|---|---|
| dleemiller/ModernCE-large-nli | 395.8M | 2,048 | modernbert | no | 2026-10-29 | 2,958 |
| dleemiller/EttinX-nli-s | 68.4M | 7,999 | modernbert | no | 2025-10-26 | 1,306 |
| dleemiller/ModernCE-base-nli | 149.6M | 2,048 | modernbert | no | 2026-10-29 | 618 |
| dleemiller/EttinX-nli-xs | 32.0M | 7,999 | modernbert | no | 2025-09-09 | 130 |
| BalaRajesh1/mmbert-small-nli | 140.6M | 8,192 | modernbert | no | 2026-02-28 | 123 |

**Rerankers** (pair scoring for join and compare)

| Model | Params | Context | Architecture | ONNX | Updated | Downloads |
|---|---|---|---|---|---|---|
| BAAI/bge-reranker-v2-m3 | 567.8M | 8,194 | xlm-roberta | no | 2024-06-24 | 14,567,359 |
| BAAI/bge-reranker-base | 278.0M | 514 | xlm-roberta | yes | 2024-06-24 | 2,866,136 |
| BAAI/bge-reranker-large | 559.9M | 514 | xlm-roberta | yes | 2024-05-11 | 2,000,839 |
| Alibaba-NLP/gte-reranker-modernbert-base | 149.6M | 8,192 | modernbert | yes | 2025-07-04 | 1,469,900 |
| Qwen/Qwen3-Reranker-0.6B | 595.8M | 40,960 | qwen3 | no | 2026-04-16 | 1,294,601 |
| mixedbread-ai/mxbai-rerank-xsmall-v1 | 70.8M | 512 | deberta-v2 | yes | 2025-04-02 | 697,602 |
| cl-nagoya/ruri-v3-reranker-310m | 315.2M | 8,192 | modernbert | no | 2025-04-18 | 264,445 |

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
