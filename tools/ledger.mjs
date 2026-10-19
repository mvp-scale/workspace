#!/usr/bin/env node
// ledger: append-only record of the work (steps, concerns, facts, claims, tasks, decisions) and the evidence for each.
// Every line of the store is an event; an item's current state is folded from its events, so history is never lost.
// Store: $LEDGER_FILE or <workspace>/ledger/ledger.jsonl. No dependencies. `ledger help` for usage.
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const FILE = process.env.LEDGER_FILE || path.join(ROOT, "ledger", "ledger.jsonl");
const MM3_LOG = path.join(ROOT, ".mm3", "log.jsonl");
const BY = process.env.LEDGER_BY || "claude";

const KINDS = {
  problem: ["P", "a pre-existing problem: --definition (what is wrong), --target (done / future state), --condition (what makes it true)"],
  step: ["S", "a step of the method of record (--step N); method and pass bar fixed in its body before it runs"],
  concern: ["C", "a risk or doubt that must be answered (e.g. 'test cannot see a 0.03 gain')"],
  assumption: ["A", "something a move relies on that is not yet backed; gate refuses moves resting on an unproven one"],
  fact: ["F", "something measured or read from a source; needs evidence to be proven"],
  claim: ["H", "a statement we want to prove or disprove (hypothesis, verdict)"],
  task: ["T", "work to do"],
  decision: ["D", "a choice made, by whom, and why"],
  note: ["N", "discussion worth keeping"],
};
const PROOF = ["unproven", "proven", "disproven", "retracted"];
const WORK = ["open", "active", "blocked", "done", "dropped", "removed"];

const HELP = {
  _: `ledger: the record of the work and its evidence (${path.relative(process.cwd(), FILE) || FILE})

Items (ids by kind: P problem, S step, C concern, F fact, H claim, T task, D decision, N note)
  ledger add <kind> "<title>" [--step N] [--body ".."] [--tag t].. [--ref ID].. [--parent ID]
             problem also: --definition ".." --target ".." [--condition ".."]..
             step, task, decision: --authorised-by method:<1-12> | D-.... (required: which plan row or rule allows it)
  ledger edit <ID> [--title ".."] [--body ".."] [--definition ..] [--target ..] [--condition ..].. [--tag t].. [--ref ID].. --why ".."
  ledger condition <ID> <n> <met|unmet> --why ".." [--eid E-0003]   condition n (1-based) of a problem

Predict, then score (the loop that tells us how to improve)
  ledger predict <ID> "<what will happen>" --p 0.7 [--check "how we will know"]   before the move; prints R-id
  ledger outcome <R-id> <right|wrong|partial> --actual ".." [--eid E-0003]       after the move
  ledger score [--kind k] [--step N] [--by name]   hit rate, Brier score, calibration by confidence, misses
  ledger remove <ID> --why ".."                 kept in history, hidden from lists

Evidence (pinned: files are hashed when attached)
  ledger evidence <ID> (--file f[:key] | --mm3 MM3-0007 | --url u | --text "..") [--cmd ".."]
                       [--supports | --contradicts] [--note ".."]

States (every change needs --why)
  ledger prove <ID> --why ..      proof: unproven -> proven     (needs supporting evidence, all files unchanged)
  ledger disprove <ID> --why ..   proof: -> disproven           (needs contradicting evidence)
  ledger retract <ID> --why ..    proof: -> retracted           (an earlier proof no longer stands)
  ledger unprove <ID> --why ..    proof: -> unproven
  ledger state <ID> <open|active|blocked|done|dropped> --why ..   (a step or claim is done only when proven)

Reading
  ledger show <ID> [--json]       current state, evidence (re-checked), full history
  ledger list [--kind k] [--proof p] [--state s] [--step N] [--tag t] [--text w] [--all] [--json]
  ledger board                    counts by kind x proof and state, and each step's state
  ledger check                    re-hash every evidence file; flags proven items whose evidence changed
  ledger trace <ID>               the provenance chain under an item, weak links marked
  ledger gate <ID>                exit 3 unless it rests only on proven items and unchanged evidence (run before a move)
  ledger kinds | ledger help <command>`,
  evidence: `ledger evidence <ID> <source> [options]
  source (one): --file path[:key]  a file; sha256 pinned now; :key names the field or row that holds the number
                --mm3 MM3-0007     an MM3 run; must exist in .mm3/log.jsonl
                --url https://..   a web source
                --text ".."        a quoted passage (say where it is from in --note)
                --stated ".."      a fact stated by a person; needs --who (e.g. --who user)
                --item ID          another ledger item; it counts only while that item is proven (or a met problem)
  basis is recorded per evidence: code (file + --cmd), file, mm3, source (url/text), stated, item.
  ledger trace <ID> walks the chain down; ledger gate <ID> refuses if it rests on anything unproven.
  --cmd ".."          command that reproduces it
  --supports          (default) evidence for the item;  --contradicts  evidence against it
  --note ".."         what it shows`,
  prove: `ledger prove <ID> --why ".."
Refused unless the item has at least one supporting evidence and none of its evidence files changed or went missing.
Use docs/proof-standard.md for what "proven" must mean; cite the MM3 reviews as --mm3 evidence.`,
  problem: `ledger add problem "<title>" --definition "what is wrong now" --target "the state that counts as done" \\
    --condition "a checkable condition" [--condition ..] [--step N]
Mark each condition met/unmet with ledger condition <P-id> <n> met --why .. --eid <evidence id>.
A problem can be set done only when every condition is met.`,
  predict: `ledger predict <ID> "<what will happen>" --p 0.0-1.0 [--check "how we will know"]
Record it BEFORE the move. Then: ledger outcome <R-id> right|wrong|partial --actual "what happened" [--eid E-..].
ledger score shows the hit rate against the stated confidence (Brier score: 0 is perfect, 0.25 is a coin flip at p 0.5).`,
  state: `ledger state <ID> <open|active|blocked|done|dropped> --why ".."
A step or claim can be set done only when its proof is proven or disproven. Use remove to hide an item.`,
  list: `ledger list [filters] [--all] [--json]
  --kind k  --proof unproven|proven|disproven|retracted  --state open|active|blocked|done|dropped|removed
  --step N  --tag t  --text word   (--all includes removed items)`,
};

// ---------- io ----------
function die(msg) { console.error(`ledger: ${msg}`); process.exit(1); }
function parse(argv) {
  const pos = [], opt = {};
  const flags = ["json", "all", "supports", "contradicts"];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith("--")) { pos.push(a); continue; }
    const k = a.slice(2);
    const v = flags.includes(k) ? true : argv[++i];
    if (v === undefined) die(`--${k} needs a value`);
    (opt[k] ??= []).push(v);
  }
  return { pos, opt };
}
const one = (opt, k) => (opt[k] ? opt[k][opt[k].length - 1] : undefined);
function events() {
  if (!fs.existsSync(FILE)) return [];
  return fs.readFileSync(FILE, "utf8").split("\n").filter(Boolean).map((l, n) => {
    try { return JSON.parse(l); } catch { die(`line ${n + 1} of ${FILE} is not JSON`); }
  });
}
function write(ev) {
  fs.mkdirSync(path.dirname(FILE), { recursive: true });
  fs.appendFileSync(FILE, JSON.stringify({ ts: new Date().toISOString(), by: BY, ...ev }) + "\n");
}
const sha = (f) => crypto.createHash("sha256").update(fs.readFileSync(f)).digest("hex");
const rel = (f) => path.relative(ROOT, path.resolve(f));
// an item holds (can be built on) when proven, or a problem whose conditions are all met
function holds(it) {
  if (!it || it.state === "removed") return false;
  if (it.proof === "proven") return true;
  return it.kind === "problem" && it.conditions.length > 0 && it.conditions.every((c) => c.status === "met");
}
function reaches(items, from, to, seen = new Set()) {
  if (from === to) return true;
  if (seen.has(from)) return false;
  seen.add(from);
  const it = items.get(from);
  return !!it && it.evidence.some((e) => e.src === "item" && reaches(items, e.item, to, seen));
}
function fileStatus(ev) {
  if (ev.src !== "file") return "n/a";
  const f = path.join(ROOT, ev.file);
  if (!fs.existsSync(f)) return "MISSING";
  return sha(f) === ev.sha256 ? "ok" : "CHANGED";
}

// ---------- fold events into items ----------
function fold(evs) {
  const items = new Map();
  for (const e of evs) {
    if (e.ev === "add") {
      items.set(e.id, { id: e.id, kind: e.kind, title: e.title, body: e.body ?? null, step: e.step ?? null,
        tags: e.tags ?? [], refs: e.refs ?? [], parent: e.parent ?? null, proof: "unproven", state: "open",
        definition: e.definition ?? null, target: e.target ?? null,
        conditions: (e.conditions ?? []).map((text) => ({ text, status: "unmet" })),
        created: e.ts, by: e.by, evidence: [], predictions: [], history: [e] });
      continue;
    }
    if (e.ev === "outcome") {
      for (const it of items.values()) {
        const pr = it.predictions.find((p) => p.rid === e.rid);
        if (pr) { Object.assign(pr, { result: e.result, actual: e.actual, eid: e.eid ?? null, scored: e.ts }); it.history.push(e); }
      }
      continue;
    }
    const it = items.get(e.id);
    if (!it) continue;
    it.history.push(e);
    if (e.ev === "edit") {
      if (e.title) it.title = e.title;
      if (e.body) it.body = e.body;
      if (e.tags) it.tags = [...new Set([...it.tags, ...e.tags])];
      if (e.refs) it.refs = [...new Set([...it.refs, ...e.refs])];
      if (e.definition) it.definition = e.definition;
      if (e.target) it.target = e.target;
      if (e.conditions) it.conditions.push(...e.conditions.map((text) => ({ text, status: "unmet" })));
    } else if (e.ev === "cond") Object.assign(it.conditions[e.n - 1], { status: e.to, eid: e.eid ?? null });
    else if (e.ev === "predict") it.predictions.push({ rid: e.rid, text: e.text, p: e.p, check: e.check ?? null, ts: e.ts, by: e.by, result: null });
    else if (e.ev === "evidence") it.evidence.push(e);
    else if (e.ev === "proof") it.proof = e.to;
    else if (e.ev === "state") it.state = e.to;
  }
  return items;
}
function item(items, id) { const it = items.get(id); if (!it) die(`no item ${id ?? "(give an id)"}`); return it; }
function need(opt, k, what) { const v = one(opt, k); if (!v) die(`${what} needs --${k} ".."`); return v; }
function checkRefs(items, ids) { for (const r of ids) if (!items.has(r)) die(`no item ${r}`); }

// ---------- commands ----------
function add(pos, opt, items) {
  const [kind, title] = pos;
  if (!KINDS[kind]) die(`kind must be one of: ${Object.keys(KINDS).join(", ")}`);
  if (!title) die(`usage: ledger add ${kind} "<title>"`);
  const step = one(opt, "step");
  if (step !== undefined && !/^\d+$/.test(step)) die("--step must be a number");
  if (kind === "step" && step === undefined) die("a step needs --step N");
  checkRefs(items, [...(opt.ref ?? []), ...(opt.parent ?? [])]);
  const auth = one(opt, "authorised-by");
  if (["step", "task", "decision"].includes(kind)) {
    if (!auth) die(`a ${kind} needs --authorised-by "method:<step 1-12>" or a decision id (D-....): which plan row or pre-registered rule allows it? If none does, add it as a concern instead.`);
    if (!/^method:(1[0-2]|[1-9])$/.test(auth) && !items.has(auth)) die(`--authorised-by must be method:1..12 or an existing item id, got "${auth}"`);
    if (items.has(auth) && items.get(auth).kind !== "decision") die(`--authorised-by ${auth} is a ${items.get(auth).kind}; only a decision or a method step can authorise`);
  }
  if (kind === "problem" && (!one(opt, "definition") || !one(opt, "target")))
    die("a problem needs --definition (what is wrong) and --target (done / future state); see ledger help problem");
  const pre = KINDS[kind][0];
  const n = [...items.keys()].filter((k) => k.startsWith(pre + "-")).length + 1;
  const id = `${pre}-${String(n).padStart(4, "0")}`;
  write({ ev: "add", id, kind, title, body: one(opt, "body") ?? null, step: step === undefined ? null : Number(step),
    tags: opt.tag ?? [], refs: opt.ref ?? [], parent: one(opt, "parent") ?? null,
    definition: one(opt, "definition") ?? null, target: one(opt, "target") ?? null, conditions: opt.condition ?? [], authorised_by: auth ?? null });
  console.log(id);
}

function edit(pos, opt, items) {
  item(items, pos[0]);
  checkRefs(items, opt.ref ?? []);
  const why = need(opt, "why", "edit");
  const ch = { title: one(opt, "title"), body: one(opt, "body"), tags: opt.tag, refs: opt.ref,
    definition: one(opt, "definition"), target: one(opt, "target"), conditions: opt.condition };
  if (!Object.values(ch).some(Boolean)) die("nothing to edit (--title, --body, --definition, --target, --condition, --tag, --ref)");
  write({ ev: "edit", id: pos[0], ...ch, why });
  console.log(`${pos[0]} edited`);
}

function evidence(pos, opt, items) {
  const it = item(items, pos[0]);
  const srcs = ["file", "mm3", "url", "text", "stated", "item"].filter((k) => opt[k]);
  if (srcs.length !== 1) die("give exactly one of --file, --mm3, --url, --text, --stated, --item (see ledger help evidence)");
  if (opt.supports && opt.contradicts) die("--supports or --contradicts, not both");
  const ev = { ev: "evidence", id: it.id, eid: `E-${String(events().filter((e) => e.ev === "evidence").length + 1).padStart(4, "0")}`,
    src: srcs[0], stance: opt.contradicts ? "contradicts" : "supports", cmd: one(opt, "cmd") ?? null, note: one(opt, "note") ?? null };
  if (ev.src === "file") {
    const spec = one(opt, "file");
    const m = spec.match(/^(.*?)(?::([^:/\\]+))?$/);
    if (!fs.existsSync(m[1]) || !fs.statSync(m[1]).isFile()) die(`evidence file not found: ${m[1]}`);
    Object.assign(ev, { file: rel(m[1]), key: m[2] ?? null, sha256: sha(m[1]) });
  } else if (ev.src === "mm3") {
    const run = one(opt, "mm3");
    const log = fs.existsSync(MM3_LOG) ? fs.readFileSync(MM3_LOG, "utf8") : "";
    if (!log.includes(`"id":"${run}"`)) die(`${run} is not in ${rel(MM3_LOG)}`);
    ev.mm3 = run;
  } else if (ev.src === "url") {
    ev.url = one(opt, "url");
    if (!/^https?:\/\//.test(ev.url)) die("--url must start with http(s)://");
  } else if (ev.src === "stated") {
    ev.stated = one(opt, "stated");
    ev.who = one(opt, "who") ?? die("--stated needs --who (who said it)");
  } else if (ev.src === "item") {
    ev.item = one(opt, "item");
    item(items, ev.item);
    if (ev.item === it.id) die("an item cannot be its own evidence");
    if (reaches(items, ev.item, it.id)) die(`${ev.item} already rests on ${it.id}; that would be circular`);
  } else ev.text = one(opt, "text");
  ev.basis = ev.src === "file" ? (ev.cmd ? "code" : "file") : ev.src === "url" || ev.src === "text" ? "source" : ev.src;
  write(ev);
  console.log(`${ev.eid} -> ${it.id} (${ev.stance})`);
}

function proof(to, pos, opt, items) {
  const it = item(items, pos[0]);
  const why = need(opt, "why", to);
  if (it.state === "removed") die(`${it.id} is removed`);
  const target = { prove: "proven", disprove: "disproven", retract: "retracted", unprove: "unproven" }[to];
  if (to === "prove" || to === "disprove") {
    const stance = to === "prove" ? "supports" : "contradicts";
    if (!it.evidence.some((e) => e.stance === stance)) die(`${it.id} has no evidence that ${stance} it; add it with ledger evidence`);
    const solid = it.evidence.filter((e) => e.stance === stance && (e.src !== "item" || holds(items.get(e.item))));
    if (!solid.length) die(`${it.id}'s ${stance} evidence is only unproven items: ${it.evidence.filter((e) => e.src === "item").map((e) => e.item).join(", ")}`);
    const bad = it.evidence.filter((e) => ["CHANGED", "MISSING"].includes(fileStatus(e)));
    if (bad.length) die(`evidence changed since attached: ${bad.map((e) => `${e.eid} ${e.file} ${fileStatus(e)}`).join("; ")}`);
  }
  if (to === "retract" && it.proof === "unproven") die(`${it.id} was never proven or disproven`);
  write({ ev: "proof", id: it.id, from: it.proof, to: target, why });
  console.log(`${it.id} ${it.proof} -> ${target}`);
}

function state(pos, opt, items, forced) {
  const it = item(items, pos[0]);
  const to = forced ?? pos[1];
  if (!WORK.includes(to) || (!forced && to === "removed")) die(`state must be one of: ${WORK.filter((w) => w !== "removed").join(", ")} (use ledger remove)`);
  const why = need(opt, "why", forced ? "remove" : "state");
  if (to === "done" && ["step", "claim"].includes(it.kind) && !["proven", "disproven"].includes(it.proof))
    die(`${it.id} is a ${it.kind} with proof "${it.proof}"; prove or disprove it before done`);
  if (to === "done" && it.kind === "problem") {
    const open = it.conditions.map((c, i) => [i + 1, c]).filter(([, c]) => c.status !== "met");
    if (!it.conditions.length) die(`${it.id} has no conditions; add them with ledger edit ${it.id} --condition .. --why ..`);
    if (open.length) die(`${it.id} conditions not met: ${open.map(([i]) => i).join(", ")}`);
  }
  write({ ev: "state", id: it.id, from: it.state, to, why });
  console.log(`${it.id} ${it.state} -> ${to}`);
}

function eidExists(eid) {
  if (eid && !events().some((e) => e.ev === "evidence" && e.eid === eid)) die(`no evidence ${eid}`);
}

function condition(pos, opt, items) {
  const it = item(items, pos[0]);
  const n = Number(pos[1]), to = pos[2];
  if (!it.conditions[n - 1]) die(`${it.id} has no condition ${pos[1]} (it has ${it.conditions.length})`);
  if (!["met", "unmet"].includes(to)) die("usage: ledger condition <ID> <n> met|unmet --why ..");
  const why = need(opt, "why", "condition");
  eidExists(one(opt, "eid"));
  if (to === "met" && !one(opt, "eid")) die("a condition is met only with evidence: --eid E-.. (attach it with ledger evidence)");
  write({ ev: "cond", id: it.id, n, from: it.conditions[n - 1].status, to, eid: one(opt, "eid") ?? null, why });
  console.log(`${it.id} condition ${n}: ${to}`);
}

function predict(pos, opt, items) {
  const it = item(items, pos[0]);
  const text = pos[1];
  if (!text) die(`usage: ledger predict ${it.id} "<what will happen>" --p 0.7`);
  const p = Number(one(opt, "p"));
  if (!(p >= 0 && p <= 1) || one(opt, "p") === undefined) die("--p must be a probability from 0 to 1");
  const rid = `R-${String(events().filter((e) => e.ev === "predict").length + 1).padStart(4, "0")}`;
  write({ ev: "predict", id: it.id, rid, text, p, check: one(opt, "check") ?? null });
  console.log(`${rid} -> ${it.id} (p ${p})`);
}

function outcome(pos, opt, items) {
  const [rid, result] = pos;
  const owner = [...items.values()].find((it) => it.predictions.some((p) => p.rid === rid));
  if (!owner) die(`no prediction ${rid ?? "(give an R-id)"}`);
  const pr = owner.predictions.find((p) => p.rid === rid);
  if (pr.result) die(`${rid} already scored ${pr.result}; predictions are scored once`);
  if (!["right", "wrong", "partial"].includes(result)) die("result must be right, wrong or partial");
  const actual = need(opt, "actual", "outcome");
  eidExists(one(opt, "eid"));
  write({ ev: "outcome", id: owner.id, rid, result, actual, eid: one(opt, "eid") ?? null });
  console.log(`${rid} ${result} (said p ${pr.p})`);
}

function score(opt, items) {
  let its = [...items.values()];
  const k = one(opt, "kind"), st = one(opt, "step"), by = one(opt, "by");
  if (k) its = its.filter((it) => it.kind === k);
  if (st) its = its.filter((it) => it.step === Number(st));
  let ps = its.flatMap((it) => it.predictions.map((p) => ({ ...p, item: it.id })));
  if (by) ps = ps.filter((p) => p.by === by);
  const done = ps.filter((p) => p.result), open = ps.filter((p) => !p.result);
  const y = (p) => ({ right: 1, partial: 0.5, wrong: 0 })[p.result];
  console.log(`predictions: ${ps.length} (${done.length} scored, ${open.length} waiting)`);
  if (!done.length) return;
  const hit = done.reduce((s, p) => s + y(p), 0) / done.length;
  const said = done.reduce((s, p) => s + p.p, 0) / done.length;
  const brier = done.reduce((s, p) => s + (p.p - y(p)) ** 2, 0) / done.length;
  console.log(`hit rate ${hit.toFixed(2)} vs stated confidence ${said.toFixed(2)} (${hit < said ? "overconfident" : hit > said ? "underconfident" : "matched"}); Brier ${brier.toFixed(3)} (0 perfect, 0.25 = always p 0.5)`);
  console.log("by stated confidence:");
  for (const [lo, hi] of [[0, 0.5], [0.5, 0.7], [0.7, 0.9], [0.9, 1.01]]) {
    const b = done.filter((p) => p.p >= lo && p.p < hi);
    if (b.length) console.log(`  p ${lo.toFixed(1)}-${Math.min(hi, 1).toFixed(1)}: ${b.length} said, came true ${(b.reduce((s, p) => s + y(p), 0) / b.length).toFixed(2)}`);
  }
  const miss = done.filter((p) => p.result !== "right").sort((a, b) => b.p - a.p);
  if (miss.length) console.log("misses, most confident first:\n" + miss.map((p) => `  ${p.rid} ${p.item} p ${p.p} ${p.result}: "${p.text}" -> ${p.actual}`).join("\n"));
  if (open.length) console.log("waiting:\n" + open.map((p) => `  ${p.rid} ${p.item} p ${p.p}: "${p.text}"`).join("\n"));
}

const basisOf = (e) => e.basis ?? (e.src === "file" ? (e.cmd ? "code" : "file") : e.src === "url" || e.src === "text" ? "source" : e.src);
// walk the evidence chain; returns weak links (unproven items, changed files) under id
function walk(items, id, depth, out, seen) {
  const it = items.get(id);
  const pad = "  ".repeat(depth);
  out.lines.push(`${pad}${line(it)}${holds(it) ? "" : "   <- not proven"}`);
  if (!holds(it) && depth > 0) out.weak.push(`${it.id} (${it.kind}, ${it.proof})`);
  if (seen.has(id)) return;
  seen.add(id);
  for (const e of it.evidence) {
    if (e.src === "item") { out.lines.push(`${pad}  ${e.eid} ${e.stance} item:`); walk(items, e.item, depth + 2, out, seen); continue; }
    const fs_ = fileStatus(e);
    const where = e.src === "file" ? `${e.file}${e.key ? `:${e.key}` : ""} [${fs_}]` : e.src === "stated" ? `"${e.stated}" (${e.who})` : e[e.src];
    out.lines.push(`${pad}  ${e.eid} ${e.stance} ${basisOf(e)}: ${where}`);
    if (fs_ === "CHANGED" || fs_ === "MISSING") out.weak.push(`${e.eid} ${e.file} ${fs_}`);
  }
}
function trace(pos, items, gate) {
  const it = item(items, pos[0]);
  const out = { lines: [], weak: [] };
  walk(items, it.id, 0, out, new Set());
  if (!it.evidence.length) out.weak.push(`${it.id} has no evidence at all`);
  if (it.kind === "assumption" && !holds(it)) out.weak.push(`${it.id} is itself an unproven assumption`);
  if (!gate || out.weak.length) console.log(out.lines.join("\n"));
  if (out.weak.length) console.log(`\n${gate ? "GATE: refused" : "weak links"}: rests on\n  ${[...new Set(out.weak)].join("\n  ")}`);
  else console.log(gate ? `GATE: pass (${it.id} rests only on proven items and unchanged evidence)` : "\nno weak links");
  if (gate && out.weak.length) process.exitCode = 3;
}

function line(it) {
  const s = it.step === null ? "   " : `s${String(it.step).padStart(2)}`;
  return `${it.id}  ${s}  ${it.kind.padEnd(8)} ${it.proof.padEnd(9)} ${it.state.padEnd(7)}  ${it.title}`;
}

function show(pos, opt, items) {
  const it = item(items, pos[0]);
  const ev = it.evidence.map((e) => ({ ...e, now: fileStatus(e) }));
  if (opt.json) return console.log(JSON.stringify({ ...it, evidence: ev }));
  console.log(line(it));
  console.log(`created ${it.created} by ${it.by}${it.parent ? `, parent ${it.parent}` : ""}`);
  if (it.definition) console.log(`definition (now): ${it.definition}`);
  if (it.target) console.log(`target (done):    ${it.target}`);
  it.conditions.forEach((c, i) => console.log(`  condition ${i + 1} [${c.status}${c.eid ? ` ${c.eid}` : ""}] ${c.text}`));
  if (it.body) console.log(`\n${it.body}\n`);
  for (const p of it.predictions)
    console.log(`${p.rid} p ${p.p} "${p.text}" -> ${p.result ? `${p.result}: ${p.actual}` : "waiting"}${p.check ? ` (check: ${p.check})` : ""}`);
  if (it.tags.length) console.log(`tags: ${it.tags.join(", ")}`);
  if (it.refs.length) console.log(`refs: ${it.refs.join(", ")}`);
  const kids = [...items.values()].filter((x) => x.parent === it.id);
  if (kids.length) console.log(`children:\n${kids.map((k) => "  " + line(k)).join("\n")}`);
  for (const e of ev) {
    const where = e.src === "file" ? `${e.file}${e.key ? `:${e.key}` : ""} [${e.now}]` : e.src === "stated" ? `"${e.stated}" (${e.who})`
      : e.src === "item" ? `${e.item} [${holds(items.get(e.item)) ? "holds" : "not proven"}]` : e[e.src];
    console.log(`${e.eid} ${e.stance.padEnd(11)} ${basisOf(e).padEnd(6)} ${where}${e.note ? ` — ${e.note}` : ""}${e.cmd ? `\n      cmd: ${e.cmd}` : ""}`);
  }
  console.log("history:");
  for (const h of it.history) {
    const what = h.ev === "add" ? "added" : h.ev === "evidence" ? `evidence ${h.eid}` : h.ev === "edit" ? "edited"
      : h.ev === "predict" ? `predicted ${h.rid} p ${h.p}` : h.ev === "outcome" ? `${h.rid} ${h.result}`
      : h.ev === "cond" ? `condition ${h.n} ${h.from} -> ${h.to}` : `${h.ev} ${h.from} -> ${h.to}`;
    console.log(`  ${h.ts.slice(0, 16).replace("T", " ")}  ${h.by.padEnd(7)} ${what}${h.why ? ` — ${h.why}` : ""}`);
  }
}

function list(opt, items) {
  let r = [...items.values()].filter((it) => opt.all || it.state !== "removed");
  for (const k of ["kind", "proof", "state"]) { const v = one(opt, k); if (v) r = r.filter((it) => it[k] === v); }
  const st = one(opt, "step"), tag = one(opt, "tag"), text = one(opt, "text");
  if (st) r = r.filter((it) => it.step === Number(st));
  if (tag) r = r.filter((it) => it.tags.includes(tag));
  if (text) r = r.filter((it) => `${it.title} ${it.body ?? ""}`.toLowerCase().includes(text.toLowerCase()));
  if (opt.json) return r.forEach((it) => console.log(JSON.stringify(it)));
  console.log(r.length ? r.map(line).join("\n") : "(no items)");
}

function board(items) {
  const live = [...items.values()].filter((it) => it.state !== "removed");
  console.log(`${"kind".padEnd(9)}${PROOF.map((p) => p.padStart(10)).join("")}  |${WORK.slice(0, 5).map((w) => w.padStart(8)).join("")}`);
  for (const k of Object.keys(KINDS)) {
    const xs = live.filter((it) => it.kind === k);
    if (!xs.length) continue;
    const c = (f, v) => String(xs.filter((it) => it[f] === v).length);
    console.log(`${k.padEnd(9)}${PROOF.map((p) => c("proof", p).padStart(10)).join("")}  |${WORK.slice(0, 5).map((w) => c("state", w).padStart(8)).join("")}`);
  }
  const steps = live.filter((it) => it.kind === "step").sort((a, b) => a.step - b.step);
  if (steps.length) console.log("\nsteps:\n" + steps.map((s) => "  " + line(s)).join("\n"));
  const openC = live.filter((it) => it.kind === "concern" && !["done", "dropped"].includes(it.state));
  if (openC.length) console.log("\nopen concerns:\n" + openC.map((s) => "  " + line(s)).join("\n"));
}

function check(items) {
  let bad = 0;
  for (const it of items.values()) for (const e of it.evidence) {
    const s = fileStatus(e);
    if (s === "CHANGED" || s === "MISSING") {
      bad++;
      console.log(`${e.eid} ${e.file} ${s} (item ${it.id}, proof ${it.proof})${it.proof === "proven" ? "  <- proof rests on changed evidence" : ""}`);
    }
  }
  console.log(bad ? `${bad} evidence file(s) changed or missing` : "all evidence files unchanged");
  if (bad) process.exitCode = 2;
}

// ---------- main ----------
const { pos, opt } = parse(process.argv.slice(2));
const cmd = pos.shift();
const items = fold(events());
switch (cmd) {
  case undefined: case "help": console.log(HELP[pos[0]] ?? HELP._); break;
  case "kinds": for (const [k, [p, d]] of Object.entries(KINDS)) console.log(`${k.padEnd(9)}${p}-  ${d}`); break;
  case "add": add(pos, opt, items); break;
  case "edit": edit(pos, opt, items); break;
  case "remove": state(pos, opt, items, "removed"); break;
  case "evidence": evidence(pos, opt, items); break;
  case "prove": case "disprove": case "retract": case "unprove": proof(cmd, pos, opt, items); break;
  case "state": state(pos, opt, items); break;
  case "condition": condition(pos, opt, items); break;
  case "predict": predict(pos, opt, items); break;
  case "outcome": outcome(pos, opt, items); break;
  case "score": score(opt, items); break;
  case "trace": trace(pos, items, false); break;
  case "gate": trace(pos, items, true); break;
  case "show": show(pos, opt, items); break;
  case "list": list(opt, items); break;
  case "board": board(items); break;
  case "check": check(items); break;
  default: die(`unknown command "${cmd}"; try ledger help`);
}
