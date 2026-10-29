# Agentic kit: the CPU model factory for agents

The playbook (`../playbook/`) is the human-length reference. This folder is what agents load and what code
enforces. Rule of thumb from Claude Code's guidance: **if something has to happen every time, make it a hook, a
schema or a script; prose is for judgment calls.**

| Piece | File | Enforced by |
|---|---|---|
| Stage machine (entry, exit, gates, on-fail) | `stages.yaml` | coordinator follows it; evaluator checks exits |
| Skill (hard rules, defaults, report format) | `skills/cpu-model-factory/SKILL.md` | loaded by every role |
| Roles | `agents/*.md` (planner, guideline-agent, teacher-labeler, trainer, evaluator, bencher) | Claude Code sub-agents |
| Task card | `schemas/task-card.schema.json`, example `examples/T70-student-v3.card.json` | `scripts/check_card.mjs` (exit 1 blocks) |
| Launch gate | `hooks/pre_launch.mjs` | Claude Code PreToolUse hook (exit 2 blocks) |
| Acceptance IDs | `../ACCEPTANCE.md` (R, D, M, P, S) | check_card (R1–R5, M3), evaluator (rest) |
| Design validation | `validation/mm3-loop-factory.yaml` | MM3 `loop` |

## Install in a project

```sh
sh knowledge_pipeline/kit/ops/new_project.sh <new-project-dir>
```

It copies this whole `knowledge_pipeline/` folder into the new project, installs the skill and roles into
`.claude/`, wires the launch hook (`node knowledge_pipeline/agentic/hooks/pre_launch.mjs`) into
`.claude/settings.json`, and creates `cards/`, `gold/`, `data/`, `runs/`, `models/`, `secrets/`, an empty ledger
and a preflight template. All paths in the skill and roles start at the project root.

## Orchestration patterns

### Claude Code (interactive coordinator + sub-agents)

- **Coordinator** (main session) owns the stage machine and the ledger. It delegates one stage per sub-agent with
  the task card path only; sub-agents see their prompt plus CLAUDE.md, not the conversation, so the card must be
  self-contained.
- **Delegate** work whose output you won't reuse in full (labelling runs, training, benchmarks). Keep in the main
  thread anything needing back-and-forth or a quick edit.
- **Model per role:** planner, guideline, teacher, trainer on `sonnet`; evaluator and bencher on `haiku` (cheap,
  and the grader differs from the producer). Set `maxTurns` on every role so runaway work stops.
- **Parallelism:** independent cards (different heads, different compute tiers) run as parallel sub-agents. Never
  two jobs on one GPU (R4).
- **Verification:** the evaluator is read-mostly and never saw the worker's conversation; it reviews against the
  card's written criteria only ("a reviewer asked to find problems will always find something", so tie it to the spec).

### Headless and scheduled runs (`claude -p`)

For unattended stages (nightly labelling, benchmark sweeps):

```sh
claude -p "Run stage S6-speed for card cards/T70.json" --bare --output-format json \
  --allowedTools "Read,Grep,Glob,Bash" --max-turns 30 --max-budget-usd 2 --permission-mode dontAsk
```

`--bare` skips local hooks and CLAUDE.md for reproducibility, so put the hard rules in the prompt or the card,
or run without `--bare` when you need the launch hook. `--json-schema` returns a `structured_output` field; check
it exists before use. `total_cost_usd` is a client estimate; reconcile with the Console.

### Claude Console (API) for teacher labelling

- **Batches + caching:** Message Batches are 50% off, up to 100,000 requests or 256 MB per batch, most done within
  an hour, expire at 24 h (unbilled), results kept 29 days. Put the guideline and examples in a cached system prefix
  with the **1-hour TTL** (batches can outlast 5 minutes). On the 5.x models the minimum cacheable prefix is 512
  tokens; check `cache_read_input_tokens` > 0, since short prefixes silently don't cache.
- **Structured outputs:** `output_config.format` with a JSON schema (`additionalProperties: false`); still validate
  every row in code (refusals and `max_tokens` truncation can break the schema).
- **Workspace per project:** its own API key, monthly spend limit and alerts; batches can slightly exceed a limit,
  so keep the card cap below the workspace cap.
- **Evals in code**, not the Console: the Workbench was retired; the frozen scorer is the eval.
- **Managed Agents** (beta): hosted agent sessions in a cloud or self-hosted sandbox, for long-running unattended
  work and scheduled runs. Use them for a recurring factory stage (e.g. weekly drift sample → teacher → evaluator);
  use plain Batches for labelling itself. The repo's `agents/*.md` files are in the Managed Agents format
  (`model.id`, `agent_toolset`); the roles here map 1:1 (tools → toolset configs, model → `model.id`).

### Compute tiers

Local RTX 5090 / 3090 first (no queue, no cap, fast iteration); API for closed-model teachers; RunPod or Google
credits for bursts or > 32 GB VRAM; Kaggle as the free fallback. Kaggle notes: GPU quota is ~30 h/week (floats,
resets Saturday 00:00 UTC) and is charged while the accelerator is attached even when idle; internet is off by
default; only `/kaggle/working` survives; check `status` before `output`; record dataset versions used. Kaggle quota
and session figures come from forum posts and should be checked on the account's quota page.

## Validation status

MM3 `class`/`replay` runs MM3-0019 to MM3-0030 on the launch hook, card checker, batch labeller, scaffold, GPU runner
and the agent design: three real gaps found and fixed, two residual limits accepted by design, owner-set targets
still open. Details and run ids: `validation/RESULTS.md`.
