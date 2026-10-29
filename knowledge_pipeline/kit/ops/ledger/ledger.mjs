#!/usr/bin/env node
// Portable append-only JSONL ledger. Node 18+, no dependencies.
//   node ledger.mjs append <ledger.jsonl> '<json>' | -    add one line (stdin with -)
//   node ledger.mjs check  <ledger.jsonl>                 ids sequential, hash chain intact, kinds/fields valid
//   node ledger.mjs brief  <ledger.jsonl> <task>          the task line plus its runs, results, verdicts, decisions
// append assigns id (L1, L2, ...), ts (ISO) and prev (sha256 of the previous stored line, "0" for the first), so
// any edit, deletion or reorder of an earlier line breaks `check`. LEDGER_WHO overrides "who" so an agent cannot
// write as someone else. Exit 0 ok, 1 refused/broken (one line per problem, with a fix), 2 bad usage.
import { appendFileSync, closeSync, existsSync, openSync, readFileSync, realpathSync, statSync, unlinkSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { fileURLToPath } from 'node:url'

export const KINDS = {
  task: ['task', 'title', 'done'],       // done: definition of done (string or array of criteria)
  run: ['task', 'where'],                // where: kernel ref / host:path / run id
  result: ['task', 'text'],              // text: the numbers
  verdict: ['task', 'result', 'text'],   // result: pass | fail
  decision: ['text'],                    // owner or coordinator choice; task optional
  note: ['text'],
}
const NEEDS_TASK = new Set(['run', 'result', 'verdict'])
const sha = (s) => createHash('sha256').update(s).digest('hex')

// Validate a line against the lines before it. Returns a list of problems ("rule: message | fix: ...").
export function problems(line, prior) {
  const out = []
  const req = KINDS[line.kind]
  if (!req) return [`kind: "${line.kind}" not in ${Object.keys(KINDS).join('|')} | fix: use one of those kinds`]
  for (const k of [...req, 'who']) {
    const v = line[k]
    if (v === undefined || v === null || v === '' || (Array.isArray(v) && !v.length)) out.push(`field: ${line.kind} needs "${k}" | fix: add it`)
  }
  if (line.kind === 'verdict' && line.result && !['pass', 'fail'].includes(line.result)) out.push(`field: verdict result "${line.result}" | fix: pass or fail`)
  if (line.kind === 'task' && line.task && prior.some((p) => p.kind === 'task' && p.task === line.task)) out.push(`task: ${line.task} already defined | fix: use a new task id or a note`)
  if (NEEDS_TASK.has(line.kind) && line.task && !prior.some((p) => p.kind === 'task' && p.task === line.task)) out.push(`task: ${line.task} has no task line | fix: append the task line first`)
  return out
}

function parse(text) {
  const raw = text.split('\n').map((l) => l.replace(/\r$/, '')).filter((l) => l.trim())
  return raw.map((r, i) => { try { return { raw: r, obj: JSON.parse(r) } } catch (e) { return { raw: r, err: `line ${i + 1}: bad json (${e.message})` } } })
}

export function check(text) {
  const rows = parse(text), out = [], prior = []
  rows.forEach((r, i) => {
    if (r.err) { out.push(r.err); return }
    const l = r.obj, want = `L${i + 1}`
    if (l.id !== want) out.push(`line ${i + 1}: id ${l.id} expected ${want} (lines removed, inserted or reordered)`)
    const prev = i ? sha(rows[i - 1].raw) : '0'
    if (l.prev !== prev) out.push(`line ${i + 1}: prev hash mismatch (line ${i} was edited, or lines removed/reordered)`)
    if (!l.ts || Number.isNaN(Date.parse(l.ts))) out.push(`line ${i + 1}: missing or bad ts`)
    for (const p of problems(l, prior)) out.push(`line ${i + 1}: ${p}`)
    prior.push(l)
  })
  return { problems: out, lines: rows.length, head: rows.length ? sha(rows.at(-1).raw).slice(0, 12) : '0' }
}

const sleep = (ms) => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms)
function withLock(file, fn) {
  const lock = `${file}.lock`
  for (let i = 0; ; i++) {
    try { closeSync(openSync(lock, 'wx')); break } catch {
      if (existsSync(lock) && Date.now() - statSync(lock).mtimeMs > 30_000) { try { unlinkSync(lock) } catch {} }
      else if (i > 100) throw new Error(`lock: ${lock} held | fix: retry, or remove it if no writer is running`)
      else sleep(100)
    }
  }
  try { return fn() } finally { try { unlinkSync(lock) } catch {} }
}

export function append(file, line) {
  if (typeof line !== 'object' || line === null || Array.isArray(line)) throw new Error('bad-json: pass one JSON object')
  for (const k of ['id', 'ts', 'prev']) delete line[k]
  if (process.env.LEDGER_WHO) line.who = process.env.LEDGER_WHO
  return withLock(file, () => {
    const text = existsSync(file) ? readFileSync(file, 'utf8') : ''
    const rows = parse(text)
    const bad = rows.find((r) => r.err)
    if (bad) throw new Error(`${bad.err} | fix: repair the ledger before appending`)
    const prior = rows.map((r) => r.obj)
    const errs = problems(line, prior)
    if (errs.length) throw new Error(errs.join('\n'))
    const l = { id: `L${rows.length + 1}`, ts: new Date().toISOString(), ...line, prev: rows.length ? sha(rows.at(-1).raw) : '0' }
    appendFileSync(file, `${text && !text.endsWith('\n') ? '\n' : ''}${JSON.stringify(l)}\n`)
    return l
  })
}

export function brief(text, task) {
  const rows = parse(text).filter((r) => r.obj).map((r) => r.obj)
  const t = rows.find((l) => l.kind === 'task' && l.task === task)
  if (!t) return null
  const short = (l) => `${l.id} ${l.kind}${l.result ? ' ' + l.result : ''} ${l.who}: ${l.text ?? l.where ?? ''}${l.where && l.text ? ` [${l.where}]` : ''}`
  const out = [`${t.id} task ${t.task}: ${t.title}`, `  done: ${[].concat(t.done).join('; ')}`]
  for (const l of rows) if (l.task === task && ['run', 'result', 'verdict', 'decision'].includes(l.kind)) out.push(short(l))
  return out.join('\n')
}

const isMain = !!process.argv[1] && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url))
if (isMain) {
  const [cmd, file, arg] = process.argv.slice(2)
  const usage = () => { console.error("usage: node ledger.mjs append <file> '<json>'|-  |  check <file>  |  brief <file> <task>"); process.exit(2) }
  if (!cmd || !file) usage()
  if (cmd === 'append') {
    if (!arg) usage()
    let line
    try { line = JSON.parse(arg === '-' ? readFileSync(0, 'utf8') : arg) } catch (e) { console.error(`bad-json: ${e.message} | fix: pass one JSON object`); process.exit(1) }
    try { console.log(JSON.stringify(append(file, line))) } catch (e) { console.error(e.message); process.exit(1) }
  } else if (cmd === 'check') {
    const r = check(existsSync(file) ? readFileSync(file, 'utf8') : '')
    if (r.problems.length) { console.log(r.problems.join('\n')); process.exit(1) }
    console.log(`ok: ${r.lines} lines, chain head ${r.head}`)
  } else if (cmd === 'brief') {
    if (!arg) usage()
    const b = brief(existsSync(file) ? readFileSync(file, 'utf8') : '', arg)
    if (!b) { console.error(`no task line for ${arg}`); process.exit(1) }
    console.log(b)
  } else usage()
}
