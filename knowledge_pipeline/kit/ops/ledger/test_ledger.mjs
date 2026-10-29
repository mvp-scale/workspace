// Synthetic test for ledger.mjs (no real data). Run: node test_ledger.mjs   exit 0 = all pass.
import { spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const CLI = path.join(path.dirname(fileURLToPath(import.meta.url)), 'ledger.mjs')
const dir = mkdtempSync(path.join(tmpdir(), 'ledger-test-'))
const F = path.join(dir, 'ledger.jsonl')
const run = (args, input, who = 'tester') => spawnSync(process.execPath, [CLI, ...args], { input, encoding: 'utf8', env: { ...process.env, LEDGER_WHO: who } })
let fails = 0
const t = (name, ok) => { console.log(`${ok ? 'PASS' : 'FAIL'} ${name}`); if (!ok) fails++ }

try {
  t('append task', run(['append', F, JSON.stringify({ kind: 'task', task: 'T1', title: 'synthetic', done: ['f1 >= 0.5'] })]).status === 0)
  t('append run via stdin', run(['append', F, '-'], JSON.stringify({ kind: 'run', task: 'T1', where: 'host:/runs/x' })).status === 0)
  t('append result', run(['append', F, JSON.stringify({ kind: 'result', task: 'T1', text: 'f1 0.61 on 10 items' })]).status === 0)
  t('append verdict', run(['append', F, JSON.stringify({ kind: 'verdict', task: 'T1', result: 'pass', text: 're-scored, equal' })], undefined, 'evaluator').status === 0)
  t('append note without task', run(['append', F, JSON.stringify({ kind: 'note', text: 'hello' })]).status === 0)
  t('refuse unknown kind', run(['append', F, JSON.stringify({ kind: 'start', task: 'T1', text: 'x' })]).status === 1)
  t('refuse missing field', run(['append', F, JSON.stringify({ kind: 'result', task: 'T1' })]).status === 1)
  t('refuse bad verdict value', run(['append', F, JSON.stringify({ kind: 'verdict', task: 'T1', result: 'ok', text: 'x' })]).status === 1)
  t('refuse result for unknown task', run(['append', F, JSON.stringify({ kind: 'result', task: 'T9', text: 'x' })]).status === 1)
  t('refuse duplicate task', run(['append', F, JSON.stringify({ kind: 'task', task: 'T1', title: 'again', done: 'x' })]).status === 1)
  t('refuse bad json', run(['append', F, '{nope']).status === 1)

  const lines = readFileSync(F, 'utf8').trim().split('\n').map((l) => JSON.parse(l))
  t('ids sequential L1..L5', lines.map((l) => l.id).join(',') === 'L1,L2,L3,L4,L5')
  t('LEDGER_WHO applied', lines[3].who === 'evaluator' && lines[0].who === 'tester')
  t('caller cannot set id/prev', run(['append', F, JSON.stringify({ kind: 'note', text: 'x', id: 'L99', prev: 'abc' })]).status === 0 &&
    JSON.parse(readFileSync(F, 'utf8').trim().split('\n').at(-1)).id === 'L6')

  const c = run(['check', F])
  t('check passes on clean ledger', c.status === 0 && /ok: 6 lines/.test(c.stdout))

  const b = run(['brief', F, 'T1'])
  t('brief lists task, run, result, verdict', b.status === 0 && ['task T1', 'run', 'result', 'verdict pass'].every((s) => b.stdout.includes(s)) && !b.stdout.includes('hello'))
  t('brief unknown task exits 1', run(['brief', F, 'T9']).status === 1)

  const good = readFileSync(F, 'utf8')
  writeFileSync(F, good.replace('f1 0.61', 'f1 0.71'))
  t('check catches edited line', run(['check', F]).status === 1)
  const arr = good.trim().split('\n')
  writeFileSync(F, [arr[0], ...arr.slice(2)].join('\n') + '\n')
  t('check catches deleted line', run(['check', F]).status === 1)
  writeFileSync(F, [arr[0], arr[2], arr[1], ...arr.slice(3)].join('\n') + '\n')
  t('check catches reorder', run(['check', F]).status === 1)
  writeFileSync(F, good.replace(/\n/g, '\r\n'))
  t('check tolerates CRLF line endings', run(['check', F]).status === 0)
} finally {
  rmSync(dir, { recursive: true, force: true })
}
console.log(fails ? `${fails} failed` : 'all passed')
process.exit(fails ? 1 : 0)
