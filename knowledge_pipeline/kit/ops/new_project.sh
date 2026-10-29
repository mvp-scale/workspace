#!/usr/bin/env bash
# Scaffold a new CPU-model-factory project. Idempotent: re-running adds what is missing and refreshes kit copies,
# and never overwrites ledger.jsonl, secrets, preflight.json or your own .gitignore/settings lines.
#   bash knowledge_pipeline/kit/ops/new_project.sh <target-dir>
set -euo pipefail
[ $# -ge 1 ] || { echo "usage: new_project.sh <target-dir>" >&2; exit 2; }
KP=$(cd "$(dirname "$0")/../.." && pwd)                       # knowledge_pipeline/
T=$1; mkdir -p "$T"; T=$(cd "$T" && pwd)
[ -d "$KP/agentic" ] && [ -d "$KP/kit" ] || { echo "kit source not found under $KP" >&2; exit 2; }

mkdir -p "$T"/{cards,gold,data,runs,models,secrets,.claude/skills,.claude/agents}
[ -f "$T/models/README.md" ] || cat > "$T/models/README.md" <<'MD'
# models/
Exported models live here and are gitignored. Ship via a private Kaggle dataset or release asset; record each
file's sha256 in the model card and on the ledger. Only small public demo models may be allowlisted in .gitignore.
MD
[ -f "$T/ledger.jsonl" ] || : > "$T/ledger.jsonl"

# .gitignore: append any missing line.
GI="$T/.gitignore"; touch "$GI"
while IFS= read -r line; do
  grep -qxF -- "$line" "$GI" || echo "$line" >> "$GI"
done <<'GITIGNORE'
# --- factory kit (new_project.sh) ---
secrets/
*.env
!secrets.example.env
*.pem
.kaggle/
# data and gold carry publisher text: never commit
data/
gold/
**/*_text.jsonl
# models: allowlist a public demo model below with a !path line, nothing else
models/*
!models/README.md
*.onnx
*.pt
*.safetensors
.kaggle_stage/
ledger.jsonl.lock
__pycache__/
.venv/
GITIGNORE

[ -f "$T/secrets.example.env" ] || cat > "$T/secrets.example.env" <<'ENV'
# Template only (committed). Copy to secrets/vault.env (gitignored) and fill that copy. Scripts read keys from the
# environment or secrets/vault.env, export them to their own process only, and never print them.
ANTHROPIC_API_KEY=
KAGGLE_API_TOKEN=
RUNPOD_API_KEY=
ENV

[ -f "$T/preflight.json" ] || cat > "$T/preflight.json" <<'JSON'
{
  "frozen": {},
  "keys": ["ANTHROPIC_API_KEY"],
  "vault": "secrets/vault.env",
  "spend": { "file": "runs/spend.jsonl", "cap_usd": 100 }
}
JSON

# Agent skill, roles, launch gate and the kit itself (refreshed on every run).
cp -R "$KP/agentic/skills/cpu-model-factory" "$T/.claude/skills/"
cp "$KP"/agentic/agents/*.md "$T/.claude/agents/"
# The whole knowledge_pipeline/ folder (docs, agentic kit, tools) so every path in the skill and roles resolves.
mkdir -p "$T/knowledge_pipeline"
cp -R "$KP/." "$T/knowledge_pipeline/"
find "$T/knowledge_pipeline" -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
chmod +x "$T"/knowledge_pipeline/kit/ops/*.sh 2>/dev/null || true

# PreToolUse hook: merge into .claude/settings.json, once.
node - "$T/.claude/settings.json" <<'JS'
const fs = require('fs'), f = process.argv[2]
const s = fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8') || '{}') : {}
const cmd = 'node knowledge_pipeline/agentic/hooks/pre_launch.mjs'
s.hooks ??= {}; s.hooks.PreToolUse ??= []
const has = s.hooks.PreToolUse.some((m) => (m.hooks || []).some((h) => h.command === cmd))
if (!has) s.hooks.PreToolUse.push({ matcher: 'Bash', hooks: [{ type: 'command', command: cmd }] })
fs.writeFileSync(f, JSON.stringify(s, null, 2) + '\n')
console.log(has ? 'hook already in .claude/settings.json' : 'hook added to .claude/settings.json')
JS

cat <<NEXT
Scaffolded $T
Next:
  1. cp secrets.example.env secrets/vault.env   and fill it in (never commit; scripts never print values)
  2. cd $T && git init (if new)  and check: git status shows no data/, gold/, secrets/, models/*
  3. Write the first task card in cards/ (knowledge_pipeline/agentic/schemas/task-card.schema.json); check it:
       node knowledge_pipeline/agentic/scripts/check_card.mjs cards/T1.json
  4. Ledger:  LEDGER_WHO=planner node knowledge_pipeline/kit/ops/ledger/ledger.mjs append ledger.jsonl '{"kind":"task","task":"T1","title":"...","done":["..."]}'
  5. Fill preflight.json (frozen shas, keys, spend cap), then run:  node knowledge_pipeline/kit/ops/preflight.mjs preflight.json
  6. Launch with CARD=cards/T1.json knowledge_pipeline/kit/ops/local_gpu_run.sh ...  (local first) or knowledge_pipeline/kit/ops/kaggle_run.sh ...
  Read knowledge_pipeline/kit/ops/README.md for the tiers and rules.
NEXT
