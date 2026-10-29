#!/usr/bin/env node
// Generic preflight before any run (R3 frozen inputs, S1 keys, R5/C3 spend, optional Kaggle quota). Node 18+, no deps.
//   node kit/ops/preflight.mjs [preflight.json] [--kaggle]      exit 0 = all PASS, 1 = any FAIL, 2 = bad config
// Config (paths relative to the current directory):
//   { "frozen": { "eval/score.py": "ffefe369", "gold/gold.jsonl": "<sha256 or prefix>" },
//     "keys":   ["ANTHROPIC_API_KEY", "KAGGLE_API_TOKEN"],          // present in env or vault; values never printed
//     "vault":  "secrets/vault.env",
//     "spend":  { "file": "runs/spend.jsonl", "cap_usd": 100 },     // sums usd | cost_usd | usd_total per line
//     "kaggle": { "quota": true, "cmd": "kaggle" } }                // or pass --kaggle; makes a network call
// A frozen file passes if its sha256 (or a prefix of it) matches the raw bytes or the LF-normalised text, so a
// CRLF checkout of a file frozen on LF still passes.
import fs from 'node:fs'
import crypto from 'node:crypto'
import { execSync } from 'node:child_process'

const args = process.argv.slice(2)
const cfgPath = args.find((a) => !a.startsWith('--')) ?? 'preflight.json'
let cfg
try { cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8')) } catch (e) { console.error(`config ${cfgPath}: ${e.message}`); process.exit(2) }

const rows = []
const ok = (id, pass, msg) => rows.push(`${pass ? 'PASS' : 'FAIL'} ${id} ${msg}`)
const sha = (b) => crypto.createHash('sha256').update(b).digest('hex')

for (const [f, want] of Object.entries(cfg.frozen ?? {})) {
  if (!fs.existsSync(f)) { ok('R3 frozen', false, `${f} missing`); continue }
  const b = fs.readFileSync(f)
  const got = [sha(b), sha(Buffer.from(b.toString('utf8').replace(/\r\n/g, '\n')))]
  const w = String(want).toLowerCase()
  ok('R3 frozen', got.some((h) => h.startsWith(w)), `${f} ${got[0].slice(0, Math.max(8, w.length))} want ${w}`)
}

const vaultFile = cfg.vault ?? 'secrets/vault.env'
const vault = fs.existsSync(vaultFile) ? fs.readFileSync(vaultFile, 'utf8') : ''
const vaultHas = (k) => new RegExp(`^${k}=\\S`, 'm').test(vault)
for (const k of cfg.keys ?? []) {
  const where = process.env[k] ? 'env' : vaultHas(k) ? 'vault' : null
  ok('S1 key', !!where, `${k} ${where ? `present in ${where}` : `missing (env and ${vaultFile})`} (value not shown)`)
}

if (cfg.spend) {
  const f = cfg.spend.file, cap = Number(cfg.spend.cap_usd)
  let total = 0, bad = 0
  if (fs.existsSync(f)) for (const l of fs.readFileSync(f, 'utf8').split(/\r?\n/)) {
    if (!l.trim()) continue
    try { const d = JSON.parse(l); total += Number(d.usd ?? d.cost_usd ?? d.usd_total ?? 0) || 0 } catch { bad++ }
  }
  ok('R5 spend', Number.isFinite(cap) && total < cap, `$${total.toFixed(2)} of $${cap} cap (${f}${fs.existsSync(f) ? '' : ', no file yet'}${bad ? `, ${bad} unparsable lines` : ''})`)
}

if (args.includes('--kaggle') || cfg.kaggle?.quota) {
  const tok = process.env.KAGGLE_API_TOKEN || (vault.match(/^KAGGLE_API_TOKEN=(.*)$/m) || [])[1]?.trim()
  let out
  try {
    out = execSync(`${cfg.kaggle?.cmd ?? 'kaggle'} quota`, { env: { ...process.env, KAGGLE_API_TOKEN: tok ?? '' }, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 60000 }).trim()
  } catch (e) { out = 'ERR ' + String(e.stderr || e.message).split(/\r?\n/)[0] }
  if (tok) out = out.split(tok).join('***')                      // never echo the token, even inside an error
  ok('R4 kaggle quota', !out.startsWith('ERR'), out.replace(/\s+/g, ' ').slice(0, 160))
}

if (!rows.length) { console.error('config has nothing to check'); process.exit(2) }
console.log(rows.join('\n'))
process.exit(rows.some((r) => r.startsWith('FAIL')) ? 1 : 0)
