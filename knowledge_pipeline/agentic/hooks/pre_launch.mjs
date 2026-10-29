// Claude Code PreToolUse hook (Bash): blocks compute launches that lack a passing task card.
// A launch command must carry CARD=<path-to-card.json>, e.g.  CARD=cards/T70.json sh kaggle_run.sh ...
// Exit 2 = block (stderr goes back to the agent); exit 0 = allow. Settings snippet in ../README.md.
// Fails closed: unreadable hook input or a missing checker blocks. The regex is a guard rail, not a sandbox;
// the kit's runners (kit/ops/kaggle_run.sh, local_gpu_run.sh) re-check the card themselves (MM3-0019 fix).
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const block = (msg) => { console.error(msg); process.exit(2) }
let raw = ''
try { for await (const c of process.stdin) raw += c } catch { block('Blocked: could not read hook input.') }
let cmd
try { cmd = JSON.parse(raw || '{}')?.tool_input?.command ?? '' } catch { block('Blocked: hook input is not valid JSON.') }

const LAUNCH = new RegExp([
  // kit entry points: compute or API spend
  String.raw`kit/student/(train|export|bench)\.py`, String.raw`kit/teacher/(claude_batch|open_model|qualify)\.py`,
  String.raw`kaggle_run\.sh`, String.raw`local_gpu_run\.sh`,
  // remote and cloud launchers
  String.raw`kaggle\s+kernels\s+push`, 'runpodctl', String.raw`gcloud\s+(ai|compute|batch)`, String.raw`\bsbatch\b`,
  String.raw`docker\s+run\b[^|;&]*--gpus`, String.raw`\bssh\b[^|;&]*\b(python|torchrun|accelerate|vllm|nohup)\b`,
  // local GPU training and serving
  String.raw`accelerate\s+launch`, String.raw`\btorchrun\b`, String.raw`\bdeepspeed\b`, String.raw`vllm\s+serve`,
  String.raw`CUDA_VISIBLE_DEVICES=`, String.raw`python\S*\s+(-m\s+)?\S*(train|finetune|distill|label)\S*`,
].join('|'))
if (!LAUNCH.test(cmd)) process.exit(0)
if (/claude_batch\.py\b.*--dry-run/.test(cmd)) process.exit(0)        // offline, no spend

const m = cmd.match(/\bCARD=(\S+)/)
if (!m) block('Blocked: compute launch without CARD=<task card>. Write a card (knowledge_pipeline/agentic/schemas/task-card.schema.json) and pass it.')
const checker = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'scripts', 'check_card.mjs')
if (!fs.existsSync(checker)) block(`Blocked: card checker not found at ${checker}.`)
try {
  execFileSync(process.execPath, [checker, m[1]], { stdio: ['ignore', 'pipe', 'pipe'] })
  process.exit(0)
} catch (e) {
  block('Blocked by check_card:\n' + String(e.stdout || e.message).split('\n').filter((l) => l.startsWith('FAIL')).join('\n'))
}
