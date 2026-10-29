// Launch gate for one task card (acceptance R1-R5). No dependencies.
//   node check_card.mjs <card.json> [--repo <dir>] [--gpu-busy]
// exit 0 = launch allowed; 1 = blocked (one FAIL line per broken rule); 2 = bad usage.
// --gpu-busy: pass when the caller's status check found another job on the target GPU (R4).
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'

const args = process.argv.slice(2)
if (!args[0]) { console.error('usage: node check_card.mjs <card.json> [--repo <dir>] [--gpu-busy]'); process.exit(2) }
const repo = args.includes('--repo') ? args[args.indexOf('--repo') + 1] : process.cwd()
const card = JSON.parse(fs.readFileSync(args[0], 'utf8'))
const rows = []
const ok = (id, pass, msg) => rows.push(`${pass ? 'PASS' : 'FAIL'} ${id} ${msg}`)
const req = ['id', 'stage', 'question', 'method', 'inputs', 'outputs', 'done', 'stop', 'budget', 'compute', 'smoke']

// R1: card complete
const missing = req.filter((k) => card[k] === undefined || card[k] === '' || (Array.isArray(card[k]) && !card[k].length))
ok('R1', !missing.length, missing.length ? `missing: ${missing.join(', ')}` : 'card complete')
ok('R1', typeof card.stop === 'string' && card.stop.length >= 10, 'stop rule written')
ok('R1', (card.done || []).every((d) => d.metric && d.op && typeof d.value === 'number'), 'definition of done is measurable')
ok('R1', !!card.method?.source, `method source: ${card.method?.source ?? 'none'}`)
if (card.stage === 'S4-train') ok('M3', !!card.selection_rule, 'selection rule written before training/test scoring')

// R2: smoke test first. Required for every GPU/remote tier whatever the declared caps (caps are self-declared),
// and for any run over 30 min; the log must exist on disk (MM3-0021).
const b = card.budget || {}
const long = (b.gpu_h ?? 0) > 0.5 || (b.cpu_h ?? 0) > 0.5
const remote = card.compute !== 'local-cpu'   // every tier except a short local-CPU job (MM3-0025)
if (card.smoke?.required || long || remote) {
  const log = card.smoke?.log
  ok('R2', !!log && fs.existsSync(path.resolve(repo, log)), log ? `smoke log ${log}${fs.existsSync(path.resolve(repo, log)) ? '' : ' not found'}` : `${card.compute} run needs smoke.log first`)
}

// R3: frozen inputs match their sha
for (const i of card.inputs || []) {
  const p = path.resolve(repo, i.path)
  if (!fs.existsSync(p)) { ok('R3', !i.frozen, `${i.path} not found locally${i.frozen ? '' : ' (remote input, checked in-run)'}`); continue }
  const h = crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex').slice(0, 8)
  const hl = crypto.createHash('sha256').update(fs.readFileSync(p, 'utf8').replace(/\r\n/g, '\n')).digest('hex').slice(0, 8)
  ok('R3', h === i.sha8 || hl === i.sha8, `${i.path} ${h}${h === hl ? '' : '/' + hl + ' (LF)'} vs ${i.sha8}`)
}

// R4: one job per GPU
if (/gpu/.test(card.compute)) ok('R4', !args.includes('--gpu-busy'), `${card.compute} free`)

// R5: caps present and positive where used
ok('R5', ['gpu_h', 'cpu_h', 'usd', 'tokens'].every((k) => typeof b[k] === 'number'), `caps gpu_h=${b.gpu_h} cpu_h=${b.cpu_h} usd=${b.usd} tokens=${b.tokens}`)
if (/gpu/.test(card.compute)) ok('R5', b.gpu_h > 0, 'GPU task has a GPU-hour cap > 0')

console.log(rows.join('\n'))
process.exit(rows.some((r) => r.startsWith('FAIL')) ? 1 : 0)
