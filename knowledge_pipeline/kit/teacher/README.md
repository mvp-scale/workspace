# kit/teacher: teacher labelling (stage S3; D4, D5, D6, R2, R5)

Project-agnostic. A task spec (`task_spec.py`, example `examples/span_task.json`) defines guideline, layers, reply and
label schemas, few-shot examples (synthetic text only), model, `max_tokens`, `cap_usd` and `prompt_version`.
Python 3.10+; only `anthropic` (Claude) and `requests` (open models), both imported lazily; PyYAML only for YAML specs.

## Commands (repo root; `T=knowledge_pipeline/kit/teacher`)

```
python $T/task_spec.py SPEC                                          # validate spec; prefix tokens (cache needs >= 512)
python $T/candidates.py --spec SPEC --items items.jsonl --out RUN/cands.jsonl         # CPU candidates (verify mode)
python $T/qualify.py --spec SPEC --gold gold.jsonl --iaa iaa.json --out RUN/qualify --teacher claude --key-file secrets/vault.env
python $T/claude_batch.py --spec SPEC --items items.jsonl --cands RUN/cands.jsonl --out RUN --dry-run
python $T/claude_batch.py --spec SPEC --items items.jsonl --cands RUN/cands.jsonl --out RUN --limit 3 --sync   # R2 smoke
python $T/claude_batch.py --spec SPEC --items items.jsonl --cands RUN/cands.jsonl --out RUN --key-file secrets/vault.env
python $T/open_model.py --spec SPEC --items items.jsonl --cands RUN/cands.jsonl --out RUN2 --base-url http://localhost:8000/v1 --model MODEL
python -m unittest discover -s $T/tests                              # offline, mocked
```

Order: dry run -> smoke (<= 3 items) -> qualify (<= 50 gold items) -> bulk. Bulk only after `teacher_gate.json` says
PASS on every layer the teacher labels. `claude_batch.py` blocks until the run ends (polls with backoff itself); call it
once, don't poll. Exit 3 = stopped (cap or wait limit); re-run resumes.

## Teacher order (S3 on_fail)

1. CPU candidates + small API model (`mode: verify`, e.g. Haiku): the model labels candidate ids, offsets come from text.
2. Add a second model family (`open_model.py`: Qwen/Llama on vLLM, local 3090/5090 or RunPod); a consensus ruler must
   not include the student's own teacher for the layer judged (D5).
3. Larger model (e.g. Sonnet) on the layers that still fail. Stop at the cap; report failing layers.

## What each tool guarantees

| tool | guarantees |
|---|---|
| `task_spec.py` | closed schemas (`additionalProperties: false`), examples match the reply schema, spec sha256 for provenance |
| `candidates.py` | deterministic ids `c1..cN`, offsets match the text, voters in `src`; plug-ins: regex, dictionary, spaCy (optional) |
| `claude_batch.py` | one cached system block (`cache_control` ephemeral, `ttl` 1h); `output_config.format` json_schema; every row validated, malformed rows retried once synchronously, then `rejects.jsonl`; worst-case cap check before every batch and retry (R5); one `spend.jsonl` line per batch (input, cache write, cache read, output tokens); warns when `cache_read_input_tokens` is 0; chunks <= 100k requests / 200 MB |
| `open_model.py` | same validation and label format; guided JSON when the server supports it; loop guard (max_tokens, repetition detector, optional repetition_penalty, one retry); `--workers` concurrency; wall-clock $ cap for rented GPUs |
| `qualify.py` | <= 50 items; scores with `kit/eval/score_spans.py`, gates with `kit/eval/gate.py` (inline TODO fallback only if absent); writes `teacher_gate.json` (D4 PASS/FAIL) |

Every label row: `item_id`, `label`, `provenance` {teacher, model, prompt_version, spec_sha256, request_id,
custom_id, batch_id, mode, date, text_sha256}, `usage` (D6). Licence/terms for training use are checked separately.

## Rules

- Prices in `prices.json` are TO_BE_VERIFIED; spend.jsonl is a client estimate, the Console bill is the truth. Keep
  `cap_usd` below the workspace spend limit (batches can slightly overrun it).
- Key: env `ANTHROPIC_API_KEY` or `--key-file`; never printed, logged or written.
- Kaggle Model Proxy outputs are evaluation-only: never use them as training labels.
- Publisher text stays private: items, `cands.jsonl` and run folders quote it, so they stay gitignored and off the
  public site. Labels store `text_sha256`, not the full text (spans still quote excerpts: keep labels private too). Spec examples use synthetic text only.
