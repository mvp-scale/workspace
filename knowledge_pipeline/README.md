# Knowledge pipeline

This folder turns what the world-engine news classifier learned into two things other projects can use:

1. **The knowledge pipeline spec**: `prd/`. v0.1 is the original design; v0.2 revises it with measured results.
2. **A playbook for training small, fast CPU models** (ONNX, int8) with LLMs as teachers: `playbook/`. It is
   written for any extraction or classification task, not only news.

`workstreams/` breaks the pipeline into work packages that separate teams or agents can pick up from different
angles: world model, knowledge management, ingestion, model training. `templates/` holds the cards every package
uses: task card, gate report, model card.

**Agents start in `agentic/`** (skill, roles, stage machine, task-card schema, launch hook). The playbook is the
human-length reference behind each rule. `ACCEPTANCE.md` defines every gate by ID; `TECHNIQUE_REVIEW.md` says what
could beat the current method.

## Start a new project from this folder

```sh
sh knowledge_pipeline/kit/ops/new_project.sh ../my-media-engine
```

The new project gets this whole folder, the agent skill and roles in `.claude/`, the launch hook, an empty ledger,
`cards/ gold/ data/ runs/ models/ secrets/` (private ones gitignored) and a preflight template. Nothing in it
depends on this repo. Tools:

| Folder | What it runs | Compute |
|---|---|---|
| `kit/eval/` | span scorer with bootstrap CIs, agreement (F1, κ) and gates, two-teacher consensus, gate report, paired compare | CPU, stdlib only |
| `kit/teacher/` | Claude Console batch labeller (1 h cache, strict JSON, spend cap), open-model labeller (vLLM/Ollama/RunPod), CPU candidates, teacher qualification | API / local GPU |
| `kit/student/` | multi-head training, ONNX export + int8 pick, runtime, tokenizer parity, speed bench, clean-env ship test, browser runner | local GPU / RunPod / Kaggle; CPU for runtime |
| `kit/ops/` | local/RunPod GPU runner over ssh, Kaggle runner + private datasets, hash-chained ledger, preflight, project scaffold | — |

`EVIDENCE.md` explains every ledger (L###) and task (T##) id cited in these docs.

## How to use it

| You want to… | Start here |
|---|---|
| Understand the target system | `prd/Knowledge_Pipeline_PRD_v0_2.md`, sections A, B, L |
| Run the factory as an agent | `agentic/README.md`, then `agentic/skills/cpu-model-factory/SKILL.md` |
| Train a new CPU model for one task (human) | `playbook/README.md` (one-page checklist), then chapters 01–09 in order |
| Know what "done" means | `ACCEPTANCE.md` |
| Know whether a better technique exists | `TECHNIQUE_REVIEW.md` |
| Avoid our expensive mistakes | `playbook/10-lessons.md` |
| Pick up a piece of the pipeline | `workstreams/README.md`, choose a package, copy `templates/task-card.md` |
| Report a result | `templates/gate-report.md` |

## The method in one paragraph

Write down the question and how a human would mark the answer. Measure how well two annotators (or two LLM families)
agree; that sets the quality bar. Freeze a scorer and a small human-checked test set. Have large LLMs label a
training pool offline. Train one small encoder with a head per question, quantize it to int8, and pick the variant
on dev data only. Score it once on the frozen test set, judged on the low end of a 95% interval. Measure speed per
item on the target CPU. Ship one file plus pinned code. Every run is a ledger task with a definition of done and a
stop rule written before it starts.

## What is proven and what isn't

| Proven here (English news) | Not yet proven |
|---|---|
| Distilled 19M-parameter int8 student: entity .88, event verb .91, time .94, quantity .83 overlap F1 | Entity types, roles, modality, linking to IDs |
| Topic encoder: IPTC level 1 macro F1 .86 (TF-IDF .79) | Other languages and non-news sources (email, chat, documents) |
| Two-LLM consensus as a ruler for event verbs and triggers | The ruler for event nouns (judges agree at .38) |
| 4.8–5.9 articles/s on 4 vCPU; the same model runs in a browser | 3,000–4,000 items/min (needs ~10× per machine) |

Origin: repo `world-engine-news-classifier`, ledger `ledger.jsonl` (L1–L411), rule card `best-practices/README.md`.
