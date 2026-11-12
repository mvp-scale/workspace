#!/usr/bin/env node
// The ledger kit's one tool (kit v1.0). A project folder holds contract/v<n>/ (versioned YAML, the source of truth: a released version is
// never edited, a change is a new version) and ledger.jsonl (one append-only line file). This tool reads the contract and is the only
// writer of the ledger: every line is checked by engine.mjs against the contract, chained to the line before it, and followed by a warning
// line for each rule in warn mode it bent. Nothing else writes either file.
//
//   node cp.mjs <verb> [--project <dir>]      the project defaults to the current folder
//   verify | release <v> --by <who> [--open "<item>"]... | versions   the contract: check it is intact, lock a version, list them
//   check | ready | brief <id> | readme | view                        read: replay, the next work, one task, the rules as text, the viewer's data
//   add|start|step|note|done|block|drop|verdict|exception|focus|decision <id> ...   append one line (--who, --evidence type:ref, ...)
//   serve [--port 18766]                                              the viewer on 127.0.0.1, its data built fresh on every load
import { readFileSync, writeFileSync, readdirSync, existsSync, statSync, appendFileSync, openSync, closeSync, unlinkSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { basename, dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { apply, replay, serialise, readyToEnforce, ready, brief, stale, shown, waveStatus, Violation } from './engine.mjs';

export const KIT = dirname(fileURLToPath(import.meta.url));
const Y = createRequire(join(KIT, 'package.json'))('yaml');
const RELEASE = 'release.yaml';
const sha = (file) => createHash('sha256').update(readFileSync(file)).digest('hex');

function filesOf(dir) {
  const out = [];
  const walk = (d) => { for (const n of readdirSync(d).sort()) { const p = join(d, n); if (statSync(p).isDirectory()) walk(p); else out.push(p); } };
  walk(dir);
  return out.map((p) => relative(dir, p)).filter((p) => p !== RELEASE);
}

/** Every version folder under <project>/contract/, oldest first, each with its release record when it has one. */
export function versions(project) {
  const dir = join(project, 'contract');
  if (!existsSync(dir)) return [];
  const num = (v) => v.slice(1).split('.').map(Number);
  return readdirSync(dir).filter((n) => /^v\d+\.\d+$/.test(n)).sort((a, b) => { const [x, y] = [num(a), num(b)]; return x[0] - y[0] || x[1] - y[1]; })
    .map((name) => ({ name, dir: join(dir, name), release: existsSync(join(dir, name, RELEASE)) ? Y.parse(readFileSync(join(dir, name, RELEASE), 'utf8')) : null }));
}

/** Changes to released versions: a file edited, added or removed since its release. Empty when the contract is intact. */
export function verify(project) {
  const problems = [];
  for (const v of versions(project).filter((x) => x.release)) {
    const now = filesOf(v.dir);
    for (const [file, want] of Object.entries(v.release.files ?? {})) {
      if (!now.includes(file)) problems.push(`${v.name}/${file} was removed after release`);
      else if (sha(join(v.dir, file)) !== want) problems.push(`${v.name}/${file} changed after release`);
    }
    for (const file of now) if (!(file in (v.release.files ?? {}))) problems.push(`${v.name}/${file} was added after release`);
  }
  return problems;
}

/** Locks a version: who released it, when, what is knowingly open, and a fingerprint of every file. Refused for a released version. */
export function release(project, name, { by, open = [], on = new Date().toISOString().slice(0, 10) }) {
  const v = versions(project).find((x) => x.name === name);
  if (!v) return { ok: false, why: `no contract/${name}/ to release` };
  if (v.release) return { ok: false, why: `${name} was released on ${v.release.released_on}; a change is a new version, never an edit` };
  if (!by) return { ok: false, why: 'name who releases it: --by <who>' };
  const files = Object.fromEntries(filesOf(v.dir).map((f) => [f, sha(join(v.dir, f))]));
  writeFileSync(join(v.dir, RELEASE), `# Contract ${name} release record (written by cp.mjs release; never edited).\n${Y.stringify({ version: name.slice(1), released_on: on, released_by: by, open, files }, { lineWidth: 0 })}`);
  return { ok: true, files: Object.keys(files).length };
}

/** The newest released contract, read whole. The journey and the experience are optional: without them the ledger simply has no shared space. */
export function contract(project) {
  const v = versions(project).filter((x) => x.release).at(-1);
  if (!v) return null;
  const rd = (rel, dflt) => (existsSync(join(v.dir, rel)) ? Y.parse(readFileSync(join(v.dir, rel), 'utf8')) : dflt);
  const journey = rd('journey.yaml', { stages: [], domains: [] });
  const capDir = join(v.dir, 'capabilities');
  const files = existsSync(capDir) ? readdirSync(capDir).filter((f) => f.endsWith('.yaml')).map((f) => f.slice(0, -5)) : [];
  const placed = journey.domains.flatMap((d) => d.capabilities ?? []);
  const order = [...new Set([...placed.filter((id) => files.includes(id)), ...files.sort()])];
  return {
    version: v.name, journey, order, capabilities: Object.fromEntries(order.map((id) => [id, rd(`capabilities/${id}.yaml`)])),
    experience: rd('experience.yaml', {}), northStar: rd('north-star.yaml', {}), proof: rd('proof.yaml', { items: [] }).items, quality: rd('quality.yaml', { gates: [] }),
    rules: { ledger: rd('rules/ledger.yaml', null), process: rd('rules/process.yaml', null) },
  };
}

/** The contract's shared space as the engine checks it; null when the project has no journey, so no line is checked against one. */
export function space(c) {
  if (!c || !c.journey.domains.length) return null;
  return {
    stages: new Set(c.journey.stages.map((s) => s.id)),
    domains: new Map(c.journey.domains.map((d) => [d.id, d.stage])),
    capabilities: new Map(c.journey.domains.flatMap((d) => (d.capabilities ?? []).map((id) => [id, d.id]))),
    goals: new Map(Object.values(c.capabilities).flatMap((x) => (x.goals ?? []).map((g) => [g.id, x.id]))),
    gates: new Set((c.quality?.gates ?? []).map((g) => g.id)),
    order: c.order,
  };
}

const ledgerOf = (project) => join(project, 'ledger.jsonl');
/** The ledger's state, replayed from its lines against the current contract; a broken or illegal line throws, naming it. */
export function state(project) {
  const f = ledgerOf(project);
  return replay(existsSync(f) ? readFileSync(f, 'utf8') : '', { space: space(contract(project)) });
}

/** One writer at a time: an exclusive lock file, retried briefly, removed when done. */
function locked(file, fn) {
  const lock = `${file}.lock`;
  for (let i = 0; ; i++) {
    try { closeSync(openSync(lock, 'wx')); break; } catch (e) {
      if (e.code !== 'EEXIST' || i > 200) throw new Error(`${lock} is held; if no writer is running, remove it`);
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 50);
    }
  }
  try { return fn(); } finally { unlinkSync(lock); }
}

/** Appends lines: each checked, chained and followed by a warning line per bent rule; nothing is written when any line is refused. */
export function append(project, lines, { who = 'cp' } = {}) {
  const file = ledgerOf(project);
  return locked(file, () => {
    const st = state(project);
    const raws = [], ids = [], warnings = [];
    for (const l of lines) {
      const ts = l.ts ?? new Date().toISOString();
      try {
        let raw = serialise(st, { ...l, ts });
        const r = apply(st, JSON.parse(raw));
        raws.push(raw); ids.push(r.line.id);
        for (const w of r.warnings) {
          raw = serialise(st, { kind: 'warning', who, ts, rule: w.rule, text: w.text, fix: w.fix, about: r.line.id, ...(l.task ? { task: l.task } : {}) });
          apply(st, JSON.parse(raw));
          raws.push(raw); warnings.push(w);
        }
      } catch (e) { if (e instanceof Violation) return { ok: false, why: `${e.rule}: ${e.message}`, fix: e.fix }; throw e; }
    }
    appendFileSync(file, raws.map((x) => `${x}\n`).join(''));
    return { ok: true, ids, warnings };
  });
}

/** The ledger's README, rendered from the contract's rules/ledger.yaml whenever it is asked for, so it is never a copy that drifts. */
export function readme(c) {
  const r = c?.rules.ledger;
  if (!r) return 'this contract has no rules/ledger.yaml';
  const title = (k) => k.replace(/_/g, ' ').replace(/^./, (x) => x.toUpperCase());
  const body = (v) => (Array.isArray(v) ? v.map((x) => `- ${typeof x === 'string' ? x : JSON.stringify(x)}`).join('\n')
    : v && typeof v === 'object' ? Object.entries(v).map(([k, x]) => `- **${title(k)}:** ${Array.isArray(x) ? x.join(', ') : x && typeof x === 'object' ? Object.entries(x).map(([a, b]) => `${a}: ${Array.isArray(b) ? b.join(', ') : b}`).join('; ') : x}`).join('\n')
    : String(v));
  const out = [`# The ledger (contract ${c.version}, rules/ledger.yaml)`, '', r.purpose, ''];
  for (const [k, v] of Object.entries(r)) if (k !== 'purpose') out.push(`## ${title(k)}`, '', body(v), '');
  return out.join('\n');
}

/** A task's state in words a person reads at a glance. */
function say(st, t, staleIds) {
  const s = shown(st, t);
  if (staleIds.includes(t.id)) return { tone: 'warn', label: 'Stalled', detail: `no update since ${t.lastTs.slice(0, 10)}` };
  if (s === 'in_progress') return { tone: 'live', label: 'In progress', detail: t.steps.length ? `${t.step} of ${t.steps.length} steps done` : 'no steps set' };
  if (s === 'blocked') return { tone: 'stop', label: 'Blocked', detail: t.blockedBy ?? '' };
  if (s === 'completed') return { tone: 'warn', label: 'Auto-review', detail: 'done; the reviewer ensemble judges it, nothing for you' };
  if (s === 'passed') return { tone: 'good', label: 'Passed', detail: '' };
  if (s === 'retry') return { tone: 'stop', label: 'Failed, retrying', detail: '' };
  if (s === 'failed') return { tone: 'stop', label: 'Failed', detail: '' };
  if (s === 'waiting') return { tone: 'quiet', label: 'Waiting', detail: `on ${t.needs.filter((n) => st.tasks[n].status !== 'passed').join(', ')}` };
  if (s === 'dropped') return { tone: 'quiet', label: 'Dropped', detail: '' };
  return { tone: 'ready', label: 'Ready', detail: '' };
}

/** Quality-gate results: every measure carried on a done or verdict line, and every decision that loosened a bar. */
const measuresOf = (st) => [...st.lines.values()].filter((l) => Array.isArray(l.measures)).flatMap((l) => l.measures.filter((m) => m && m.gate).map((m) => ({ ...m, task: l.task ?? null, ts: l.ts, line: l.id })));
const relaxations = (st) => [...st.lines.values()].filter((l) => l.kind === 'decision' && l.change === 'relax' && l.gate).map((l) => ({ gate: l.gate, from: l.from ?? '', to: l.to ?? '', text: l.text ?? '', ts: l.ts, line: l.id }));

/** What the viewer shows, computed fresh: the whole story (north star, journey, people, rules) and the work moving through it,
 *  with every task's detail and history so the page can drill in without asking again. */
export function view(project, now = new Date().toISOString()) {
  const c = contract(project);
  const st = state(project);
  const tasks = Object.values(st.tasks);
  const staleIds = stale(st, now, c?.rules.ledger?.stale?.window_hours ?? 48);
  const order = ready(st).map((t) => t.task);
  const history = (id) => [...st.lines.values()].filter((l) => l.task === id || (l.kind === 'warning' && l.task === id))
    .map((l) => ({ ts: l.ts, kind: l.kind, who: l.who, text: l.text ?? l.title ?? '', evidence: l.evidence ?? [], rule: l.rule ?? null }));
  const task = (t) => ({ id: t.id, title: t.title, why: t.why, ...say(st, t, staleIds), status: shown(st, t), who: t.who, wave: t.wave,
    stage: t.stage, domain: t.domain, capability: t.capability, goal: t.goal, steps: t.steps.map((x, i) => ({ text: x, done: i < t.step })),
    acceptance: t.acceptance, needs: t.needs.map((n) => ({ id: n, title: st.tasks[n].title, label: say(st, st.tasks[n], staleIds).label })),
    validator: t.validator, priority: t.priority, severity: t.severity, blast: t.blast, attempts: t.attempts, next: order.indexOf(t.id),
    notes: t.notes, proof: t.proof, last: t.lastTs, history: history(t.id), verdictCriteria: ([...st.lines.values()].filter((l) => l.kind === 'verdict' && l.task === t.id).at(-1)?.criteria ?? []), warnings: st.warnings.filter((w) => w.task === t.id).map((w) => w.rule) });
  const all = tasks.map(task);
  const byId = Object.fromEntries(all.map((t) => [t.id, t]));
  const x = c?.experience ?? {};
  const capView = (id) => {
    const k = c.capabilities[id] ?? {};
    const work = all.filter((t) => t.capability === id);
    return { id, name: k.name ?? id, definition: k.definition ?? '', tier: k.tier ?? '', confirmed: !!k.confirmed, entities: k.entities ?? [],
      goals: (k.goals ?? []).map((g) => ({ id: g.id, title: g.title, why: g.why, acceptance: g.acceptance ?? [], future: g.future ?? '',
        functions: g.functions ?? [], tasks: work.filter((t) => t.goal === g.id).map((t) => t.id) })),
      tasks: work.map((t) => t.id), passed: work.filter((t) => t.status === 'passed').length, active: work.filter((t) => ['in_progress', 'blocked'].includes(t.status)).length,
      stories: Object.entries(x.stories ?? {}).filter(([, s]) => s.area === id).map(([sid, s]) => ({ id: sid, story: s.story, outcome: s.outcome })) };
  };
  return {
    name: c?.northStar?.name ?? basename(project).replace(/[-_]/g, ' ').replace(/^./, (y) => y.toUpperCase()),
    contract: c?.version ?? null, lines: st.n, built: now,
    northStar: c?.northStar ?? {},
    counts: { passed: all.filter((t) => t.status === 'passed').length, live: all.filter((t) => t.status === 'in_progress').length,
      needsYou: all.filter((t) => ['blocked'].includes(t.status)).length, ready: order.length, total: all.length },
    attention: [
      ...all.filter((t) => t.status === 'blocked').map((t) => ({ id: t.id, why: `Blocked: ${t.detail}` })),
      ...all.filter((t) => t.status === 'completed').map((t) => ({ id: t.id, why: 'Done; automatic review pending' })),
      ...staleIds.map((id) => ({ id, why: `Stalled: ${byId[id].detail}` })),
      ...readyToEnforce(st).map((r) => ({ rule: r.rule, why: `${r.rule} has warned on ${r.runs} tasks: ready to enforce` })),
      ...Object.keys(st.waves).filter((w) => waveStatus(st, w) === 'completed').map((w) => ({ wave: w, why: `Wave ${w} is complete: hold its ceremony` })),
    ],
    journey: (c?.journey.stages ?? []).map((s) => ({ id: s.id, name: s.name, question: s.question, goal: s.goal,
      domains: c.journey.domains.filter((d) => d.stage === s.id).map((d) => ({ id: d.id, name: d.name, goal: d.goal, definition: d.definition ?? '',
        capabilities: (d.capabilities ?? []).map(capView) })) })),
    tasks: all, next: order, focus: st.focus,
    engine: { card: [...st.lines.values()].filter((l) => l.engine && typeof l.engine === 'object').at(-1)?.engine ?? null, measures: measuresOf(st).filter((m) => m.engine) },
    gates: (c?.quality?.gates ?? []).map((g) => { const ms = measuresOf(st).filter((m) => m.gate === g.id);
      return { ...g, last: ms.at(-1) ?? null, runs: ms.length, history: ms.slice(-8), relaxed: relaxations(st).filter((r) => r.gate === g.id).length }; }),
    ratchet: { rule: c?.quality?.ratchet?.rule ?? '', yieldRule: c?.quality?.ratchet?.yield_rule ?? '', relaxations: relaxations(st) },
    waves: Object.values(st.waves).map((w) => ({ id: w.id, title: w.title, goal: w.goal, status: waveStatus(st, w.id), tasks: all.filter((t) => t.wave === w.id).map((t) => t.id) })),
    people: { personas: Object.entries(x.personas ?? {}).map(([id, p]) => ({ id, ...p })), outcomes: Object.entries(x.outcomes ?? {}).map(([id, o]) => ({ id, ...o })),
      moments: Object.entries(x.moments ?? {}).map(([id, m]) => ({ id, ...m })) },
    rules: { dayOne: c?.rules.ledger?.enforcement?.day_one?.rules ?? [], readyAfter: c?.rules.ledger?.enforcement?.ready_after ?? 3,
      five: c?.rules.ledger?.five_rules ?? [], enforced: Object.entries(st.modes).filter(([, m]) => m === 'enforce').map(([r]) => r) },
    warnings: Object.values(st.warnings.reduce((by, w) => { const g = (by[w.rule] ??= { rule: w.rule, count: 0, tasks: new Set(), text: '', fix: '' }); g.count++; if (w.task) g.tasks.add(w.task); g.text = w.text; g.fix = st.lines.get(w.id)?.fix ?? ''; return by; }, {}))
      .map((g) => ({ ...g, tasks: [...g.tasks], ready: readyToEnforce(st).some((r) => r.rule === g.rule) })).sort((a, b) => b.count - a.count),
  };
}

/** The writing verbs: each makes one line, which append() checks, chains and warns on. */
const LINE_VERBS = {
  add: ({ id, who, text, flag }) => ({ kind: 'task', who, task: id, title: flag('--title')[0] ?? text, text: flag('--title')[0] ?? text, why: flag('--why')[0] ?? '',
    acceptance: flag('--acceptance'), steps: flag('--step').length ? flag('--step') : undefined, capability: flag('--capability')[0], domain: flag('--domain')[0],
    stage: flag('--stage')[0], goal: flag('--goal')[0], validator: flag('--validator')[0], needs: flag('--needs'),
    ...(flag('--severity')[0] ? { severity: flag('--severity')[0], blast: flag('--blast')[0] } : {}), ...(flag('--wave')[0] ? { wave: flag('--wave')[0] } : {}) }),
  start: ({ id, who }) => ({ kind: 'start', who, task: id, text: `${id} started` }),
  step: ({ id, who, text }) => ({ kind: 'step', who, task: id, step: Number(text.split(' ')[0]), text: `${id} step ${text}` }),
  note: ({ id, who, text }) => ({ kind: 'note', who, task: id, text }),
  done: ({ id, who, ev, text }) => ({ kind: 'done', who, task: id, text: text || `${id} completed`, evidence: ev }),
  engine: ({ id, who, flag }) => { const card = JSON.parse(flag('--card')[0] ?? '{}'); return { kind: 'note', who, task: id, text: `${id} engine card: ${card.name ?? '?'} ${card.version ?? ''}`.trim(), engine: card }; },
  measure: ({ id, who, flag }) => { const m = JSON.parse(flag('--measures')[0] ?? '[]'); return { kind: 'note', who, task: id, text: `${id} measured ${m.map((x) => x.gate).join(', ')}`, measures: m }; },
  block: ({ id, who, text }) => ({ kind: 'block', who, task: id, text }),
  drop: ({ id, who, text }) => ({ kind: 'drop', who, task: id, text }),
  verdict: ({ id, who, ev, flag, st }) => { const result = flag('--result')[0]; return { kind: 'verdict', who, task: id, result, text: `${id} ${result}`, evidence: ev, criteria: (st.tasks[id]?.acceptance ?? []).map((criterion) => ({ criterion, result })) }; },
  exception: ({ id, who, ev, text, flag }) => ({ kind: 'exception', who, task: id, rule: flag('--rule')[0], text, evidence: ev }),
  focus: ({ who, ev, text, flag }) => ({ kind: 'focus', who, order: flag('--order'), text, evidence: ev }),
  decision: ({ id, who, ev, text, flag }) => ({ kind: 'decision', who, decision: id, text, evidence: ev, ...(flag('--rule')[0] ? { rule: flag('--rule')[0], mode: flag('--mode')[0] } : {}) }),
};

/** Heartbeat files (kit/live/heartbeat.py) next to the project folder: one per running job, read fresh on every load. */
export function liveRuns(project) {
  const dir = join(resolve(project), '..', 'runs-live');
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter((n) => n.endsWith('.json')).map((n) => { try { return JSON.parse(readFileSync(join(dir, n), 'utf8')); } catch { return null; } }).filter(Boolean);
}

/** Finished runs (kit/live/heartbeat.py appends one line per run). Read fresh; the page gets the newest 30 and a per-day count. */
function histRead(project) {
  const f = join(resolve(project), '..', 'runs-history.jsonl');
  if (!existsSync(f)) return [];
  return readFileSync(f, 'utf8').split('\n').filter(Boolean).map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean)
    .sort((a, b) => String(b.ended).localeCompare(String(a.ended)));
}
export function liveData(project) {
  const all = histRead(project), byDay = {};
  for (const r of all) { const d = String(r.ended ?? '').slice(0, 10); const x = (byDay[d] ??= { done: 0, failed: 0, other: 0 }); x[r.state === 'done' ? 'done' : r.state === 'failed' ? 'failed' : 'other']++; }
  let phases = [];
  try { phases = JSON.parse(readFileSync(join(resolve(project), '..', 'projects', 'world-state', 'phases.json'), 'utf8')).phases ?? []; } catch { /* no definitions file */ }
  return { live: liveRuns(project), history: all.slice(0, 30), historyTotal: all.length, byDay, phases };
}
export function historyPage(project, q) {
  let all = histRead(project);
  if (q.where && q.where !== 'all') all = all.filter((r) => r.where === q.where);
  if (q.outcome && q.outcome !== 'all') all = all.filter((r) => r.state === q.outcome);
  const o = Math.max(0, Number(q.offset ?? 0)), n = Math.min(100, Math.max(1, Number(q.limit ?? 30)));
  return { rows: all.slice(o, o + n), total: all.length };
}

export function serve(project, port = 18766) {
  const page = join(KIT, 'viewer.html');
  return createServer((req, res) => {
    const path = (req.url ?? '/').split('?')[0];
    if (req.method !== 'GET') { res.writeHead(405); return res.end('read only'); }
    if (path.endsWith('/history')) { res.writeHead(200, { 'content-type': 'application/json', 'cache-control': 'no-store' }); return res.end(JSON.stringify(historyPage(project, Object.fromEntries(new URL(req.url, 'http://x').searchParams)))); }
    if (path.endsWith('/training')) {
      try { res.writeHead(200, { 'content-type': 'application/json', 'cache-control': 'no-store' }); return res.end(readFileSync(join(resolve(project), '..', 'training', 'training.json'))); }
      catch (e) { res.writeHead(404, { 'content-type': 'text/plain' }); return res.end('no training.json; run build_training.py'); }
    }
    if (path.endsWith('/data')) {
      try { res.writeHead(200, { 'content-type': 'application/json', 'cache-control': 'no-store' }); return res.end(JSON.stringify({ ...view(project), ...liveData(project) })); }
      catch (e) { res.writeHead(500, { 'content-type': 'text/plain' }); return res.end(e instanceof Violation ? `${e.rule}: ${e.message} (fix: ${e.fix})` : String(e)); }
    }
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' });
    res.end(readFileSync(page));
  }).listen(port, '127.0.0.1', () => console.log(`viewer: http://127.0.0.1:${port}/  (project ${project})`));
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  const raw = process.argv.slice(2);
  const pAt = raw.indexOf('--project');
  const project = resolve(pAt >= 0 ? raw[pAt + 1] : process.cwd());
  const args = pAt >= 0 ? raw.filter((_, i) => i !== pAt && i !== pAt + 1) : raw;
  const [cmd, ...rest] = args;
  const flag = (name) => rest.flatMap((a, i) => (a === name ? [rest[i + 1]] : []));
  const fail = (why, fix) => { console.log(`refused: ${why}${fix ? `\n  fix: ${fix}` : ''}`); process.exit(1); };
  if (cmd === 'verify') {
    const p = verify(project);
    for (const x of p) console.log(`refused: ${x} (a released version is never edited; make the change in a new version)`);
    if (p.length) process.exit(1);
    console.log(`contract intact: ${versions(project).filter((v) => v.release).map((v) => v.name).join(', ') || 'nothing released yet'}`);
  } else if (cmd === 'release') {
    const r = release(project, rest[0], { by: flag('--by')[0], open: flag('--open') });
    if (!r.ok) fail(r.why);
    console.log(`released ${rest[0]}: ${r.files} files fingerprinted and locked`);
  } else if (cmd === 'versions') {
    for (const v of versions(project)) console.log(`${v.name}  ${v.release ? `released ${v.release.released_on} by ${v.release.released_by}` : 'not released'}`);
  } else if (cmd === 'check') {
    try { const st = state(project); console.log(`ledger replays: ${st.n} lines, ${Object.keys(st.tasks).length} tasks, ${st.warnings.length} warnings`); }
    catch (e) { if (e instanceof Violation) fail(`line ${e.line}: ${e.rule}: ${e.message}`, e.fix); throw e; }
  } else if (cmd === 'ready') {
    const st = state(project);
    for (const t of ready(st)) console.log(`${t.task}  ${t.capability ?? '-'}  ${t.title}`);
    const due = readyToEnforce(st);
    if (due.length) console.log(`rules ready to enforce: ${due.map((r) => `${r.rule} (${r.runs} runs)`).join(', ')}`);
  } else if (cmd === 'brief') {
    console.log(brief(state(project), rest[0]));
  } else if (cmd === 'readme') {
    console.log(readme(contract(project)));
  } else if (cmd === 'view') {
    console.log(JSON.stringify(view(project), null, 1));
  } else if (cmd === 'serve') {
    serve(project, Number(flag('--port')[0] ?? 18766));
  } else if (LINE_VERBS[cmd]) {
    const who = flag('--who')[0] ?? 'agent';
    const ev = flag('--evidence').map((x) => { const at = x.indexOf(':'); return { type: x.slice(0, at), ref: x.slice(at + 1) }; });
    const words = rest.filter((a, i) => !a.startsWith('--') && !(i > 0 && rest[i - 1].startsWith('--')));
    const text = (cmd === 'focus' ? words : words.slice(1)).join(' ');   // focus names no task, so every word is its reason
    const r = append(project, [LINE_VERBS[cmd]({ id: rest[0], who, ev, text, flag, st: state(project) })]);
    if (!r.ok) fail(r.why, r.fix);
    console.log(`${r.ids.join(', ')} appended${r.warnings.length ? `; warned: ${r.warnings.map((w) => `${w.rule} (${w.text}; fix: ${w.fix})`).join('; ')}` : ''}`);
  } else {
    console.log('usage: node cp.mjs <verify|release|versions|check|ready|brief|readme|view|serve|add|start|step|note|measure|engine|done|block|drop|verdict|exception|focus|decision> ... [--project <dir>]');
    process.exit(2);
  }
}
