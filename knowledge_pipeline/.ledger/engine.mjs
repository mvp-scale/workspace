// The ledger kit's state engine (kit v1.0). Replays an append-only line file, enforces the ontology,
// transitions and invariants, and answers the reader questions. A refused line names its rule and carries the fix.
// Extended (operator, 2026-10-22/23): the shared space (stage, domain, capability, goal, checked against the contract), steps, focus,
// a computed bug priority, one validator per skill chain with recorded exceptions, a hash chain, and rule modes: a rule in warn mode lets
// the line through and returns a warning (rule, what, fix) to be appended; a rule is promoted to enforce by a decision citing its warnings.
// Day-one rules are always enforced: letting them through costs more to undo than stopping now. No dependencies but node:crypto.
import { createHash } from 'node:crypto';

export const CAUSES = ['skill', 'tool', 'task-definition', 'grouping', 'language', 'source', 'budget', 'evidence-gap', 'other'];
const KINDS = new Set(['wave', 'task', 'step', 'start', 'block', 'done', 'verdict', 'postmortem', 'opportunity', 'decision', 'ceremony', 'drop', 'note',
  'focus', 'exception', 'warning', 'goal', 'draft', 'proof', 'answer']);
const RESOLUTIONS = new Set(['fixed', 'retry', 'pooled', 'dropped']);
export const SEVERITIES = ['high', 'medium', 'low'];
export const BLASTS = ['code', 'component', 'container', 'system'];
const COVERAGE = ['full', 'partial', 'unknown'];
export const LIMITS = { title: 60, goal: 90, criterion: 200, criteria: 6, steps: 4, step: 60, width: 80 };
const ID = { wave: /^W\d+$/, task: /^[TB]\d+$/, opportunity: /^I\d+$/, decision: /^D\d+$/, ceremony: /^C\d+$/ };
const SHAPE = { wave: 'W<number>', task: 'T<number> (work) or B<number> (bug)', opportunity: 'I<number>', decision: 'D<number>', ceremony: 'C<number>' };

/** Rules that are always enforced (operator, 2026-10-23): ledger corruption, done without evidence, self-judging, ids the contract does not
 *  hold, unvalidated code marked done, and the structural rules the replay itself depends on. Every other rule starts in warn mode. */
export const DAY_ONE = new Set(['bad-kind', 'no-who', 'no-text', 'no-ts', 'bad-id', 'duplicate-wave', 'duplicate-task', 'duplicate-opportunity',
  'duplicate-ceremony', 'unknown-task', 'unknown-wave', 'unknown-need', 'bad-transition', 'chain-broken', 'no-evidence', 'self-verdict', 'bad-result',
  'no-criteria', 'verdict-inconsistent', 'unknown-space', 'no-validation', 'settled', 'no-new-evidence', 'bad-coverage', 'bad-mode']);
export const READY_AFTER = 3;

export class Violation extends Error {
  constructor(rule, message, fix) {
    super(message);
    this.rule = rule;
    this.fix = fix;
  }
}
const bad = (rule, message, fix) => {
  throw new Violation(rule, message, fix);
};

export const modeOf = (st, rule) => (DAY_ONE.has(rule) || st.modes[rule] === 'enforce' ? 'enforce' : 'warn');

const hasEvidence = (e) => Array.isArray(e) && e.length > 0 && e.every((x) => x && typeof x.type === 'string' && typeof x.ref === 'string' && x.ref);
const refs = (e) => new Set((e ?? []).map((x) => `${x.type}:${x.ref}`));
export const hashOf = (raw) => createHash('sha256').update(raw).digest('hex');

/** A bug's priority, computed, never typed: P1 only when severity is high and the blast is container or wider. */
export function priorityOf(severity, blast) {
  const wide = ['container', 'system'].includes(blast);
  if (severity === 'high' && wide) return 'P1';
  if (severity === 'high' || (severity === 'medium' && wide)) return 'P2';
  return 'P3';
}

/** An empty ledger. `space` is the contract's shared space ({stages, domains, capabilities, goals, order}); `modes` the rule modes so far. */
export const empty = ({ space = null, modes = {} } = {}) => ({
  n: 0, last: null, space, modes: { ...modes }, lines: new Map(), tasks: {}, waves: {}, opps: {}, decisions: {}, ceremonies: [],
  postmortemIds: [], warnings: [], exceptions: [], focus: [], goals: {}, drafts: {}, proof: {}, answers: null, pending: [],
});

/** A wave is completed when every member is settled: passed, dropped, or failed with its post-mortem written and no retry pending. */
export function waveStatus(st, w) {
  if (st.waves[w]?.closed) return 'closed';
  const members = Object.values(st.tasks).filter((t) => t.wave === w);
  const settled = (t) => t.status === 'passed' || t.status === 'dropped' || (t.status === 'failed' && !t.pendingRetry);
  return members.length > 0 && members.every((t) => settled(t) && t.unexplained === 0) ? 'completed' : 'open';
}

export function check(st, l) {
  // A rule in warn mode records a warning for this line and lets it through; an imported line (history being backfilled) never warns.
  const soft = (rule, message, fix) => {
    if (modeOf(st, rule) === 'enforce' && !l.imported) bad(rule, message, fix);
    if (!l.imported) st.pending.push({ rule, text: message, fix });
  };
  const evidenceRule = (rule, message, fix) => (l.imported ? undefined : bad(rule, message, fix));
  // Quality-gate results ride on done and verdict lines as "measures":[{gate, pass, value, n_in, n_pass, thin}]; the contract's quality.yaml names the gates.
  const measures = () => {
    if (l.measures == null) return;
    if (!Array.isArray(l.measures)) return soft('bad-measure', '"measures" must be a list', 'use "measures":[{"gate":"Q04","pass":true,"value":"kappa 0.71"}]');
    for (const m of l.measures) {
      if (!m || typeof m.gate !== 'string' || typeof m.pass !== 'boolean') soft('bad-measure', 'a measure names its gate and says pass true or false', 'add {"gate":"Q04","pass":true,"value":"..."}');
      else if (st.space?.gates && !st.space.gates.has(m.gate)) soft('unknown-gate', `gate "${m.gate}" is not in the contract`, 'use a gate id from quality.yaml');
    }
  };
  const idOk = (kind, id) => {
    if (!ID[kind].test(id ?? '')) bad('bad-id', `${kind} id "${id}"`, `${kind} ids look like ${SHAPE[kind]}`);
  };
  const short = (field, max) => {
    const s = l[field];
    if (typeof s !== 'string' || !s.trim()) soft(`no-${field}`, `a ${l.kind} line needs a ${field}`, `add "${field}" (at most ${max} characters)`);
    else if (s.length > max) soft(`${field}-too-long`, `${field} is ${s.length} characters, limit ${max}`, 'shorten it; detail belongs in the acceptance criteria');
  };
  // A wave's goal is its own sentence; on every other line goal is a contract goal id.
  const space = (allowed) => {
    if (!st.space) return;
    const S = st.space;
    const goal = l.kind === 'wave' ? undefined : l.goal;
    if (l.stage && !S.stages.has(l.stage)) bad('unknown-space', `stage "${l.stage}" is not in the contract`, 'use a stage id from the contract journey');
    if (l.domain && !S.domains.has(l.domain)) bad('unknown-space', `domain "${l.domain}" is not in the contract`, 'use a domain id from the contract journey');
    for (const c of [l.capability, ...(l.capabilities ?? [])].filter(Boolean)) if (!S.capabilities.has(c)) bad('unknown-space', `capability "${c}" is not in the contract`, 'use a capability id from the contract');
    if (goal && !S.goals.has(goal)) bad('unknown-space', `goal "${goal}" is not in the contract`, 'use a goal id from a capability in the contract');
    if (!allowed) return;
    if (goal && l.capability && S.goals.get(goal) !== l.capability) soft('space-mismatch', `goal ${goal} belongs to ${S.goals.get(goal)}, not ${l.capability}`, 'name the goal\'s own capability');
    if (l.capability && l.domain && S.capabilities.get(l.capability) !== l.domain) soft('space-mismatch', `capability ${l.capability} sits in ${S.capabilities.get(l.capability)}, not ${l.domain}`, 'name the capability\'s own domain');
    if (l.domain && l.stage && S.domains.get(l.domain) !== l.stage) soft('space-mismatch', `domain ${l.domain} sits in stage ${S.domains.get(l.domain)}, not ${l.stage}`, 'name the domain\'s own stage');
  };
  if (!KINDS.has(l.kind)) bad('bad-kind', `unknown kind "${l.kind}"`, `use one of: ${[...KINDS].join(', ')}`);
  if (!l.who) bad('no-who', 'every line names who wrote it', 'add "who"');
  if (!l.text && !l.title) bad('no-text', 'every line carries one plain sentence', 'add "text"');
  if (!l.ts) bad('no-ts', 'every line carries a UTC timestamp', 'add "ts"');
  if (l.prev !== undefined && l.prev !== st.last) bad('chain-broken', `line ${l.id} does not follow the line before it`, 'a line is never edited or removed; append a correcting line instead');
  const t = l.task ? st.tasks[l.task] : undefined;
  const mustTask = () => {
    if (!t) bad('unknown-task', `no task "${l.task}"`, `append a "task" line for ${l.task} first`);
    return t;
  };
  const moveFrom = (...ok) => {
    mustTask();
    if (!ok.includes(t.status)) bad('bad-transition', `${l.kind} on ${l.task} while ${t.status}`, `${l.kind} is allowed only from: ${ok.join(', ')}`);
  };

  switch (l.kind) {
    case 'wave':
      idOk('wave', l.wave);
      if (st.waves[l.wave]) bad('duplicate-wave', `wave "${l.wave}" already exists`, 'use a new wave id');
      short('title', LIMITS.title);
      short('goal', LIMITS.goal);
      if (l.skills != null && (!Array.isArray(l.skills) || l.skills.some((s) => typeof s !== 'string'))) soft('bad-skills', 'skills is a list of skill names', 'use "skills":["name",...]');
      space(true);
      return;
    case 'task': {
      idOk('task', l.task);
      if (st.tasks[l.task]) bad('duplicate-task', `task "${l.task}" already exists`, 'use a new task id; to retry a task, append "start"');
      short('title', LIMITS.title);
      if (!Array.isArray(l.acceptance) || !l.acceptance.length || l.acceptance.length > LIMITS.criteria || l.acceptance.some((a) => typeof a !== 'string' || !a)) {
        soft('no-acceptance', `a task lists 1 to ${LIMITS.criteria} acceptance criteria`, 'add "acceptance":["what must be true",...]');
      } else if (l.acceptance.some((a) => a.length > LIMITS.criterion)) soft('acceptance-too-long', `a criterion is over ${LIMITS.criterion} characters`, 'split it into two criteria');
      for (const n of l.needs ?? []) if (!st.tasks[n]) bad('unknown-need', `needs ${n}, which does not exist`, `append the task ${n} first (this also makes a dependency cycle impossible)`);
      if (l.wave) {
        if (!st.waves[l.wave]) bad('unknown-wave', `no wave "${l.wave}"`, 'append a "wave" line first');
        if (st.waves[l.wave].closed) soft('wave-closed', `wave ${l.wave} is closed by a ceremony`, 'put the task in a new wave');
      }
      if (l.steps != null && (!Array.isArray(l.steps) || l.steps.length < 1 || l.steps.length > LIMITS.steps || l.steps.some((s) => typeof s !== 'string' || !s || s.length > LIMITS.step))) {
        soft('bad-steps', `steps are 1 to ${LIMITS.steps} outcomes of at most ${LIMITS.step} characters`, 'shorten or split the steps');
      }
      space(true);
      if ((l.capabilities ?? []).length > 1) soft('spans-capabilities', `${l.task} spans ${l.capabilities.join(', ')}`, 'a task\'s steps stay inside one capability: split it into one task per capability');
      const wd = l.wave && st.waves[l.wave]?.domain;
      if (wd && l.domain && wd !== l.domain) soft('wave-spans-domains', `${l.task} is in ${l.domain} but wave ${l.wave} works in ${wd}`, 'a wave\'s tasks share one domain: put it in a wave for its own domain');
      if (/^B\d+$/.test(l.task)) {
        if (!SEVERITIES.includes(l.severity)) soft('no-severity', 'a bug states its severity first', `add "severity": ${SEVERITIES.join(' | ')}`);
        if (!BLASTS.includes(l.blast)) soft('no-blast', 'a bug states its blast radius', `add "blast": ${BLASTS.join(' | ')}`);
        if (!l.capability) soft('no-area', 'a bug names the capability it is in', 'add "capability"');
        if (!hasEvidence(l.evidence)) soft('bug-no-evidence', 'a bug cites the evidence that it fails', 'add "evidence" (the failing test, command output or file:line)');
        if (['low', 'medium'].includes(l.severity)) soft('bug-not-pooled', `a ${l.severity} bug goes to the pool, not the work (D034)`, 'append it as an opportunity; only a high bug becomes a task');
      }
      if (l.from && st.opps[l.from]?.status !== 'pooled') soft('bad-source', `opportunity "${l.from}" is not pooled`, 'promote only a pooled opportunity');
      return;
    }
    case 'step':
      moveFrom('in_progress');
      if (!Number.isInteger(l.step) || l.step < 1 || l.step > t.steps.length) soft('step-order', `${l.task} has no step ${l.step}`, `steps run from 1 to ${t.steps.length}`);
      else if (l.step !== t.step + 1) soft('step-order', `${l.task} closes step ${l.step} after step ${t.step}`, `close step ${t.step + 1} next`);
      return;
    case 'start':
      moveFrom('open', 'failed', 'blocked');
      for (const n of t.needs) if (st.tasks[n].status !== 'passed') soft('needs-unmet', `${l.task} needs ${n}, which is ${st.tasks[n].status}`, `finish ${n} (passed) first`);
      if (t.budget != null && t.spent >= t.budget) soft('budget-exhausted', `${l.task} spent ${t.spent} of ${t.budget}`, 'append a "block" with cause budget and a post-mortem; do not keep spending');
      if (!t.steps.length && !l.imported) soft('no-steps', `${l.task} starts with no steps`, 'give it 2 to 4 steps, each an outcome, so one agent works them in order');
      return;
    case 'block':
      moveFrom('in_progress');
      return;
    case 'done':
      moveFrom('in_progress');
      if (l.who !== t.who) soft('not-owner', `${l.task} is held by ${t.who}`, 'only the agent that started it reports it completed');
      if (!hasEvidence(l.evidence)) evidenceRule('no-evidence', 'completed needs evidence', 'add "evidence":[{"type":"commit|test|file|command|mm3|validate","ref":"..."}]');
      measures();
      if (t.validator && !(l.evidence ?? []).some((e) => e.type === 'validate') && !st.exceptions.some((x) => x.task === l.task && x.rule === 'no-validation')) {
        evidenceRule('no-validation', `${l.task} names the validator ${t.validator} and its done cites no validate receipt`, 'run the validator and cite its receipt as {"type":"validate","ref":"..."}, or append an exception with the reason and evidence');
      }
      if (t.steps.length && t.step < t.steps.length && !l.imported) soft('steps-unfinished', `${l.task} is done at step ${t.step} of ${t.steps.length}`, 'close every step, or drop the steps that no longer apply in a note');
      return;
    case 'verdict': {
      moveFrom('completed');
      measures();
      if (l.who === t.who) bad('self-verdict', 'the Evaluator cannot be the agent that did the work', 'have a different agent append the verdict');
      if (!['pass', 'fail'].includes(l.result)) bad('bad-result', 'result is pass or fail', 'set "result"');
      if (!Array.isArray(l.criteria) || !l.criteria.length || l.criteria.some((c) => !c.criterion || !['pass', 'fail'].includes(c.result))) {
        bad('no-criteria', 'a verdict lists each acceptance criterion with its result', 'add "criteria":[{"criterion":"...","result":"pass|fail"}]');
      }
      const missing = t.acceptance.filter((a) => !l.criteria.some((c) => c.criterion === a));
      if (missing.length) soft('verdict-missing-criteria', `no result for: ${missing.join('; ')}`, 'judge every acceptance criterion the task listed, using its exact words');
      if ((l.result === 'pass') !== l.criteria.every((c) => c.result === 'pass')) bad('verdict-inconsistent', 'pass requires every criterion to pass', 'fix result or criteria');
      if (!hasEvidence(l.evidence)) evidenceRule('no-evidence', 'a verdict needs evidence (for example the MM3 run)', 'add "evidence"');
      if (l.result === 'pass' && t.overBudget) soft('over-budget', `${l.task} spent ${t.spent} of ${t.budget}`, 'record the budget criterion as fail, or a decision with evidence that raises the budget');
      return;
    }
    case 'postmortem':
      mustTask();
      if (!(t.fails > 0 && t.unexplained > 0)) soft('nothing-to-explain', `${l.task} has no unexplained failed verdict`, 'a post-mortem follows a failed verdict, once');
      if (!CAUSES.includes(l.cause)) soft('bad-cause', `cause "${l.cause}"`, `use one of: ${CAUSES.join(', ')}`);
      if (!RESOLUTIONS.has(l.resolution)) soft('bad-resolution', `resolution "${l.resolution}"`, `use one of: ${[...RESOLUTIONS].join(', ')}`);
      if (!hasEvidence(l.evidence)) evidenceRule('no-evidence', 'a post-mortem records why, with evidence', 'add "evidence"');
      if (l.resolution === 'fixed' && t.status !== 'passed') soft('resolution-mismatch', '"fixed" means the task now passed', `status is ${t.status}; use "retry" or "pooled"`);
      if (l.resolution === 'retry' && t.status !== 'failed') soft('resolution-mismatch', '"retry" applies to a failed task', `status is ${t.status}`);
      return;
    case 'drop':
      mustTask();
      if (t.status === 'passed' || t.status === 'dropped') bad('bad-transition', `cannot drop a ${t.status} task`, 'passed work stays passed');
      return;
    case 'opportunity': {
      idOk('opportunity', l.opp);
      if (st.opps[l.opp]) bad('duplicate-opportunity', `opportunity "${l.opp}" exists`, 'use a new id');
      if (!CAUSES.includes(l.cause)) soft('bad-cause', `cause "${l.cause}"`, `use one of: ${CAUSES.join(', ')}`);
      if (!Array.isArray(l.from) || !l.from.length || l.from.some((id) => !st.postmortemIds.includes(id) && !st.lines.has(id))) soft('no-source', 'an opportunity cites at least one post-mortem or bug line', 'add "from":[<line id>]');
      space(false);
      return;
    }
    case 'decision': {
      idOk('decision', l.decision);
      if (l.change === 'relax') soft('bar-relaxed', `quality bar ${l.gate ?? '?'} is being loosened`, 'only with new evidence, decided before the next measurement; list it at the phase review, and prefer fixing upstream');
      if (!hasEvidence(l.evidence)) evidenceRule('no-evidence', 'a decision without evidence is a guess', 'add "evidence"');
      const prior = st.decisions[l.decision];
      if (prior) {
        if (l.for !== prior.id) bad('settled', `${l.decision} is settled`, `to reopen, append with "for":"${prior.id}" and new evidence`);
        const seen = refs(prior.evidence);
        if (![...refs(l.evidence)].some((r) => !seen.has(r))) bad('no-new-evidence', 'reopening needs evidence not already cited', 'add a new evidence pointer');
      }
      if (l.rule !== undefined && !['warn', 'enforce'].includes(l.mode)) bad('bad-mode', `mode "${l.mode}"`, 'a decision on a rule sets "mode": warn | enforce');
      return;
    }
    case 'ceremony': {
      idOk('ceremony', l.ceremony);
      if (st.ceremonies.some((c) => c.ceremony === l.ceremony)) bad('duplicate-ceremony', 'ceremony id used', 'use a new id');
      for (const w of l.closes ?? []) {
        if (!st.waves[w]) bad('unknown-wave', `no wave "${w}"`, 'close only existing waves');
        const s = waveStatus(st, w);
        if (s !== 'completed') soft('wave-not-complete', `wave ${w} is ${s}`, 'every member must be passed, dropped, or failed with a post-mortem and no retry pending');
      }
      for (const p of l.patterns ?? []) {
        const ids = p.opportunities ?? [];
        if (!CAUSES.includes(p.cause) || ids.some((id) => st.opps[id]?.cause !== p.cause)) soft('pattern-mismatch', `pattern "${p.cause}" cites an opportunity of another cause or an unknown one`, 'list only opportunities with that cause');
        if (p.count !== ids.length) soft('pattern-count', `count ${p.count} but ${ids.length} opportunities listed`, 'count must equal the list');
      }
      for (const id of l.retires ?? []) if (st.opps[id]?.status !== 'pooled') soft('bad-retire', `${id} is not pooled`, 'retire only pooled opportunities');
      return;
    }
    case 'focus':
      if (!Array.isArray(l.order) || !l.order.length) bad('no-order', 'a focus line lists what comes first', 'add "order":[domain, capability or entity ids, first first]');
      if (st.space) for (const x of l.order) if (!st.space.domains.has(x) && !st.space.capabilities.has(x)) bad('unknown-space', `focus names "${x}", which the contract does not hold`, 'name a domain or capability id');
      if (!hasEvidence(l.evidence)) evidenceRule('no-evidence', 'a change of focus says why, with evidence', 'add "evidence"');
      return;
    case 'exception':
      mustTask();
      if (!l.rule) bad('no-rule', 'an exception names the rule it excepts', 'add "rule"');
      if (!hasEvidence(l.evidence)) evidenceRule('no-evidence', 'an exception gives its reason with evidence', 'add "evidence"');
      return;
    case 'warning':
      if (!l.rule) bad('no-rule', 'a warning names its rule', 'add "rule"');
      return;
    case 'goal':
      space(false);
      if (!l.goal) bad('unknown-space', 'a goal line names its goal', 'add "goal"');
      if (l.coverage !== undefined && !COVERAGE.includes(l.coverage)) bad('bad-coverage', `coverage "${l.coverage}"`, `use one of: ${COVERAGE.join(', ')}`);
      return;
    case 'draft':
      space(false);
      if (!l.goal) bad('unknown-space', 'a draft line names its goal', 'add "goal"');
      if (!l.draft?.future) soft('no-future', 'a draft needs a future', 'add "draft":{"future":"..."}');
      return;
    case 'proof':
    case 'answer':
    case 'note':
      return;
  }
}

function commit(st, l) {
  const t = l.task ? st.tasks[l.task] : undefined;
  if (t && typeof l.cost === 'number') {
    t.spent += l.cost;
    if (t.budget != null && t.spent > t.budget) t.overBudget = true;
  }
  if (t) t.lastTs = l.ts;
  switch (l.kind) {
    case 'wave':
      st.waves[l.wave] = { id: l.wave, title: l.title, goal: l.goal, skills: l.skills ?? [], budget: l.budget ?? null, closed: false, closedBy: null,
        stage: l.stage ?? null, domain: l.domain ?? null };
      break;
    case 'task':
      st.tasks[l.task] = { id: l.task, n: st.n, title: l.title, why: l.why ?? '', acceptance: l.acceptance ?? [], skills: l.skills ?? [], severity: l.severity ?? null,
        blast: l.blast ?? null, priority: /^B\d+$/.test(l.task) ? priorityOf(l.severity, l.blast) : null, status: 'open', needs: l.needs ?? [], wave: l.wave ?? null,
        budget: l.budget ?? null, spent: 0, attempts: 0, fails: 0, unexplained: 0, pendingRetry: false, overBudget: false, who: null, proof: null,
        steps: l.steps ?? [], step: 0, validator: l.validator ?? null, writes: l.writes ?? [], notes: [], lastTs: l.ts,
        stage: l.stage ?? null, domain: l.domain ?? null, capability: l.capability ?? null, goal: l.goal ?? null };
      if (l.from && st.opps[l.from]) st.opps[l.from].status = 'promoted';
      break;
    case 'step':
      if (Number.isInteger(l.step)) t.step = Math.max(t.step, l.step);
      break;
    case 'start':
      if (t.status !== 'blocked') t.attempts += 1;
      t.status = 'in_progress';
      t.who = l.who;
      t.pendingRetry = false;
      break;
    case 'block':
      t.status = 'blocked';
      t.blockedBy = l.text;
      break;
    case 'done':
      t.status = 'completed';
      t.proof = (l.evidence ?? [])[0] ?? null;
      break;
    case 'verdict':
      t.status = l.result === 'pass' ? 'passed' : 'failed';
      if (l.result === 'fail') {
        t.fails += 1;
        t.unexplained += 1;
      }
      break;
    case 'postmortem':
      t.unexplained = 0;
      t.pendingRetry = l.resolution === 'retry';
      st.postmortemIds.push(l.id);
      break;
    case 'drop':
      t.status = 'dropped';
      t.pendingRetry = false;
      break;
    case 'opportunity':
      st.opps[l.opp] = { id: l.opp, status: 'pooled', cause: l.cause, area: l.capability ?? l.area ?? null, from: l.from, text: l.text };
      break;
    case 'decision':
      st.decisions[l.decision] = { id: l.id, evidence: l.evidence, rule: l.rule ?? null, mode: l.mode ?? null };
      if (l.rule) st.modes[l.rule] = l.mode;
      break;
    case 'ceremony':
      for (const w of l.closes ?? []) {
        st.waves[w].closed = true;
        st.waves[w].closedBy = l.ceremony;
      }
      for (const id of l.retires ?? []) if (st.opps[id]) st.opps[id].status = 'retired';
      st.ceremonies.push(l);
      break;
    case 'focus':
      st.focus = l.order;
      break;
    case 'exception':
      st.exceptions.push({ task: l.task, rule: l.rule, id: l.id, text: l.text });
      break;
    case 'warning':
      st.warnings.push({ id: l.id, rule: l.rule, about: l.about ?? null, task: l.task ?? null, text: l.text, ts: l.ts });
      break;
    case 'goal': {
      const g = (st.goals[l.goal] ??= { current: '', tasks: [], coverage: 'unknown' });
      for (const k of ['current', 'tasks', 'coverage', 'coverage_note']) if (l[k] !== undefined) g[k] = l[k];
      break;
    }
    case 'draft':
      st.drafts[l.goal] = l.draft;
      break;
    case 'proof':
      st.proof[l.title] = l.tasks ?? [];
      break;
    case 'answer':
      st.answers = l.answers;
      break;
    case 'note':
      if (t) t.notes.push(l.text);
      break;
  }
}

/** Appends one line to the state. Returns the line (with its id and chain pointer) and the warnings it raised, to be appended after it. */
export function apply(st, line) {
  const l = { ...line, id: line.id ?? `L${st.n + 1}` };
  st.pending = [];
  check(st, l);
  const raw = JSON.stringify(l);
  st.n += 1;
  st.lines.set(l.id, l);
  st.last = hashOf(raw);
  commit(st, l);
  const warnings = st.pending;
  st.pending = [];
  return { line: l, warnings };
}

/** Replays a whole file; returns the state or throws the first Violation with its line number. Each line's prev must be the hash of the
 *  line before it exactly as written, so an edited or removed line breaks the chain. */
export function replay(text, opts = {}) {
  const st = empty(opts);
  text.split('\n').filter(Boolean).forEach((raw, i) => {
    try {
      const l = JSON.parse(raw);
      if (l.prev === undefined) bad('chain-broken', `line ${i + 1} has no prev`, 'every line names the hash of the line before it');
      st.pending = [];
      check(st, l);
      st.n += 1;
      st.lines.set(l.id, l);
      st.last = hashOf(raw);
      commit(st, l);
    } catch (e) {
      if (e instanceof Violation) e.line = i + 1;
      throw e;
    }
  });
  st.pending = [];
  return st;
}

/** The line to append, with its chain pointer, as the writer serialises it. */
export function serialise(st, line) {
  return JSON.stringify({ ...line, id: line.id ?? `L${st.n + 1}`, prev: st.last });
}

const unmet = (st, t) => t.needs.filter((n) => st.tasks[n].status !== 'passed');
/** What a person reads: open work is "ready" or "waiting"; a failed task with a retry pending is "retry". */
export const shown = (st, t) => (t.status === 'open' ? (unmet(st, t).length ? 'waiting' : 'ready') : t.status === 'failed' && t.pendingRetry ? 'retry' : t.status);

/** The order work is taken in: the latest focus first, then journey order (stage, domain, capability), then the order filed. */
export function orderKey(st, t) {
  const at = (x) => (x ? st.focus.indexOf(x) : -1);
  const f = [at(t.capability), at(t.domain)].filter((i) => i >= 0);
  const journey = st.space?.order ? st.space.order.indexOf(t.capability) : -1;
  return [f.length ? Math.min(...f) : st.focus.length, journey < 0 ? Infinity : journey, t.n];
}
const byOrder = (st) => (a, b) => { const x = orderKey(st, a), y = orderKey(st, b); return x[0] - y[0] || x[1] - y[1] || x[2] - y[2]; };

export const ready = (st) =>
  Object.values(st.tasks)
    .filter((t) => ['ready', 'retry'].includes(shown(st, t)) && !(t.budget != null && t.spent >= t.budget))
    .sort(byOrder(st))
    .map((t) => ({ task: t.id, title: t.title, wave: t.wave, capability: t.capability, attempts: t.attempts }));

/** In progress with no new line for longer than `hours`: flagged for a ceremony, never acted on. */
export const stale = (st, now, hours = 48) => Object.values(st.tasks).filter((t) => t.status === 'in_progress' && (Date.parse(now) - Date.parse(t.lastTs)) / 36e5 > hours).map((t) => t.id);

/** Rules in warn mode that have warned about READY_AFTER distinct tasks or waves: ready for a decision that enforces them. */
export function readyToEnforce(st) {
  const by = {};
  for (const w of st.warnings) if (modeOf(st, w.rule) === 'warn') (by[w.rule] ??= new Set()).add(w.task ?? w.about ?? w.id);
  return Object.entries(by).filter(([, s]) => s.size >= READY_AFTER).map(([rule, s]) => ({ rule, runs: s.size, warnings: st.warnings.filter((w) => w.rule === rule).map((w) => w.id) }));
}

export const pool = (st) => {
  const by = {};
  for (const o of Object.values(st.opps).filter((o) => o.status === 'pooled')) (by[`${o.cause}/${o.area ?? '-'}`] ??= []).push(o.id);
  return Object.entries(by).map(([k, ids]) => ({ cause_area: k, count: ids.length, opportunities: ids })).sort((a, b) => b.count - a.count);
};

export const waves = (st) => Object.keys(st.waves).map((w) => ({ wave: w, status: waveStatus(st, w) }));

const fit = (s, w) => (s.length <= w ? s : `${s.slice(0, w - 1)}…`);
const num = (id) => Number(id.slice(1));

/** Everything an agent needs to start one task, nothing else: its shared space, skills, validator, steps, acceptance and needs. */
export function brief(st, id) {
  const t = st.tasks[id];
  if (!t) bad('unknown-task', `no task "${id}"`, 'run ready to see task ids');
  const wv = t.wave ? st.waves[t.wave] : null;
  const skills = [...new Set([...(wv?.skills ?? []), ...t.skills])];
  const out = [`${t.id}  ${t.title}${wv ? `   (wave ${wv.id}: ${wv.title})` : ''}`];
  const where = [t.stage, t.domain, t.capability, t.goal].filter(Boolean).join(' › ');
  if (where) out.push(`space    ${where}`);
  if (wv) out.push(`goal     ${wv.goal}`);
  if (skills.length) out.push(`skills   ${skills.join(', ')}`);
  if (t.validator) out.push(`validate ${t.validator}`);
  out.push(`state    ${shown(st, t)} · attempt ${t.attempts}${t.budget != null ? ` · spend ${t.spent}/${t.budget}` : ''}${t.priority ? ` · ${t.priority} (${t.severity}, ${t.blast})` : ''}`);
  t.steps.forEach((s, i) => out.push(`${i === 0 ? 'steps  ' : '       '}  ${i + 1}. ${s}${i < t.step ? '  done' : ''}`));
  t.acceptance.forEach((a, i) => out.push(`${i === 0 ? 'accept ' : '       '}  ${i + 1}. ${fit(a, LIMITS.width - 12)}`));
  if (!t.needs.length) out.push('needs    none');
  t.needs.forEach((n, i) => {
    const d = st.tasks[n];
    out.push(`${i === 0 ? 'needs  ' : '       '}  ${n} ${shown(st, d)}${d.proof ? `  ${d.proof.type}:${String(d.proof.ref).slice(0, 12)}` : ''}  ${fit(d.title, 30)}`);
  });
  return out.join('\n');
}

export { num };
