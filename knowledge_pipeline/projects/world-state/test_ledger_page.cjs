// test_ledger_page: checks of the resource ledger panel on the sim page (plan v2 step 5), no browser, a stub DOM.
//   node test_ledger_page.cjs <py_v2.json> <py_v1.json> [<synth_cases.json>] [<py_v6.json>] [<py_v7.json>]   (a 4th file adds the decision-weight run runs-v6/trace; pass "" for synth to skip it)      (the two files are written by: ledger_split.py <trace> --json <file>; v2 = runs-v2/trace, v1 = trace-demo)
// T1 every script of the page parses (new Function)   T2 the page's JS rules give the same numbers as ledger_split.py on two real traces   T3 render check with a stub DOM (initial grey rows, folder build, stream path, stale, greyed)
// T4 no innerHTML added by the panel.  Prints PASS/FAIL with the measured number per check; exit 1 on any FAIL.
const fs = require("fs"), vm = require("vm"), path = require("path");
const PAGE = path.resolve(__dirname, "../../simulation/index.html"), MOCK = "/workspace/demo/mockups";
const html = fs.readFileSync(PAGE, "utf8"), res = []; const rec = (id, ok, m) => { res.push([id, ok]); console.log((ok ? "PASS " : "FAIL ") + id + ": " + m) };
// T1
const scripts = [...html.matchAll(/<script(?![^>]*\ssrc=)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]); let bad = 0;
scripts.forEach((s, i) => { try { new Function(s) } catch (e) { bad++; console.log("  parse error in script", i, e.message) } }); rec("T1 scripts parse", bad === 0 && scripts.length > 0, scripts.length + " script(s), " + bad + " parse errors");
// stub DOM
const REG = {}; class Node { constructor(t) { this.tag = t; this.attrs = {}; this.kids = []; this.style = {}; this.classList = { add() {}, remove() {}, contains() { return false } }; this.hidden = false; this.value = "" }
  setAttribute(k, v) { this.attrs[k] = String(v); if (k === "id") REG[v] = this } getAttribute(k) { return this.attrs[k] } append(...c) { for (const x of c) this.kids.push(x instanceof Node ? x : new Txt(String(x))) } replaceChildren(...c) { this.kids = []; this.append(...c) } after() {}
  get firstChild() { return this.kids[0] || null } get lastChild() { return this.kids[this.kids.length - 1] || null } get textContent() { return this.kids.map(k => k.textContent).join("") } set textContent(v) { this.kids = [new Txt(String(v))] }
  all(f, o = []) { if (f(this)) o.push(this); this.kids.forEach(k => k.all && k.all(f, o)); return o } }
class Txt extends Node { constructor(t) { super("#text"); this.t = t } get textContent() { return this.t } set textContent(v) { this.t = v } all(f, o = []) { return o } }
const doc = { getElementById: id => REG[id] || (REG[id] = new Node("auto-" + id)), createElement: t => new Node(t), body: new Node("body") };
function mkFetch(over) { return async (u, o) => { u = String(u); if (over && over[u]) return over[u]; const m = u.match(/^\/mockups\/(.*)$/); const f = m ? path.join(MOCK, m[1]) : null;
    if (!f || !fs.existsSync(f)) return { ok: false, status: 404, json: async () => ({}) }; const buf = fs.readFileSync(f);
    return { ok: true, status: 200, json: async () => JSON.parse(buf.toString("utf8")), body: { getReader() { let i = 0; return { async read() { if (i >= buf.length) return { done: true }; const c = new Uint8Array(buf.subarray(i, i + 65536 + 7)); i += c.length; return { done: false, value: c } } } } } } } }
const mainRows = () => { const t = REG.s_ledger.all(n => n.tag === "table")[0]; return t ? t.all(n => n.tag === "tr").length : 0 };   // the first table is the resource table; the folded tables below it have rows too
const wait = async (f, ms = 20000) => { const t = Date.now(); while (Date.now() - t < ms) { if (f()) return true; await new Promise(r => setTimeout(r, 15)) } return false };
function load() { for (const k in REG) delete REG[k]; const sb = { document: doc, fetch: mkFetch(), Node, console: { log() {}, error() {} }, setTimeout: () => 0, clearTimeout() {}, TextDecoder, Date, Math, JSON, Set, Promise };
  sb.window = sb; vm.createContext(sb); vm.runInContext(scripts[0] + "\n;globalThis.__t={LS,LG,lgNew,lgAdd,lgRows,renderLedger,lgFolder,ledgerStream,lgSpec,ST};", sb); return sb }
const near = (a, b) => Math.abs(a - b) <= 1e-6 * Math.max(1, Math.abs(a), Math.abs(b));
(async () => {
  const sb = load(), T = sb.__t, ok0 = await wait(() => T.LS.spec && REG.s_ledger && mainRows() === 27);
  // T3a initial render
  const S = REG.s_ledger, trs = { length: mainRows() }, txt = S.textContent;
  const auto = T.LS.src === "v7" && /As of article/.test(txt);   // the page now opens on the recorded run v7 and builds it by itself: accept that or the grey first render
  rec("T3a initial render: 26 rows (grey, or the default run v7 already built), draft wording", ok0 && trs.length === 27 && ((txt.match(/no mention yet/g) || []).length === 26 || auto) && txt.includes("Draft wording, owner to confirm (R7)") && txt.includes("A running tally of the world's resources"), trs.length - 1 + " rows, 'no mention yet' x" + (txt.match(/no mention yet/g) || []).length);
  // T2 parity + T3b folder build, both traces
  for (const [k, pyf, name] of [["v2", process.argv[2], "runs-v2/trace (IPTC route)"], ["v1", process.argv[3], "trace-demo (Area route)"]].concat(process.argv[5] ? [["v6", process.argv[5], "runs-v6/trace (IPTC route, abstain weights)"]] : []).concat(process.argv[6] ? [["v7", process.argv[6], "runs-v7/trace (IPTC route, re-ranked topic)"]] : [])) {
    const py = JSON.parse(fs.readFileSync(pyf, "utf8")); T.LS.src = k; const live = k === "v2" ? "/mockups/structure-live/trace-v2/" : "/mockups/structure-live/trace-demo/";
    await T.lgFolder(k); const L = T.LS.shown, rows = T.lgRows(L), pm = {}; py.rows.forEach(r => pm[r.resource] = r); let diff = 0, maxd = 0; const bad = [];
    for (const r of rows) { const p = pm[r.resource]; let d = !p || p.state !== r.state || p.items !== r.items || p.publishers !== r.publishers || p.up_n !== r.up_n || p.down_n !== r.down_n || p.last_seq !== r.last_seq || JSON.stringify(p.feeds) !== JSON.stringify(r.feeds) || !near(p.value, r.value) || !near(p.net, r.net);
      if (p) maxd = Math.max(maxd, Math.abs(p.value - r.value), Math.abs(p.net - r.net)); if (d) { diff++; bad.push(r.resource + " js " + r.state + " " + r.value.toFixed(4) + " / py " + (p && p.state) + " " + (p && p.value)) } }
    rec("T2 parity JS vs Python, " + name, rows.length === 26 && diff === 0 && L.tick === py.as_of.tick && L.items === py.items && L.dirs === py.direction_items, rows.length + " resources, " + diff + " differ, max abs diff " + maxd.toExponential(1) + ", tick " + L.tick + " vs " + py.as_of.tick + ", items " + L.items + " vs " + py.items + (bad.length ? "; " + bad.slice(0, 3).join(" | ") : ""));
    if (k === "v2") await wait(() => REG.s_ledger.textContent.includes("Split-half check"), 3000); const trs2 = { length: mainRows() }, t2 = REG.s_ledger.textContent, st = REG.l_st ? REG.l_st.textContent : "";
    rec("T3b folder render " + k, trs2.length === 27 && t2.includes("As of article #" + L.seq) && t2.includes("run " + L.run.run_id) && t2.includes("labels ") && /Built from .*chain\.jsonl|Built from/.test(st) && t2.includes(k === "v2" ? "IPTC landing 3597" : (k === "v6" || k === "v7") ? "IPTC landing " + py.routes.iptc : "Area topic (legacy) 2086"), trs2.length - 1 + " rows; as-of text: " + (REG.s_ledger.all(n => n.tag === "div" && /^As of article/.test(n.textContent)).map(n => n.textContent.slice(0, 150))[0] || "missing"));
    if (k === "v2") rec("T3c split-half line from ledger.json shown", t2.includes("Split-half check") && t2.includes("rank agreement " + py.split_half.whole_stream) && t2.includes(py.split_half.m4_failed + " of 5 checks FAILED") && t2.includes("FAIL: whole-stream rank agreement") && t2.includes("FAIL: per-window median"), (t2.match(/Split-half check[^.]*\./) || ["missing"])[0].slice(0, 120));
    if (k === "v1") rec("T3d no split-half line when the folder has no ledger.json (trace-demo is read-only)", !t2.includes("Split-half check"), "absent as expected");
  }
  // T3e stream path: 30 lines one by one through ledgerStream, journal-less copy not counted, stale + greyed
  const sb2 = load(), T2 = sb2.__t; await wait(() => T2.LS.spec); const lines = []; const rd = fs.readFileSync(MOCK + "/structure-live/runs-v2/trace/chain.jsonl", "utf8").split("\n").slice(0, 40).filter(Boolean).map(l => JSON.parse(JSON.parse(l).line)).filter(l => l.state === "traced");
  T2.ST.run = JSON.parse(fs.readFileSync(MOCK + "/structure-live/runs-v2/trace/run.json", "utf8")); T2.LS.src = "stream"; for (const l of rd) await T2.ledgerStream({ article_line: l });
  const dup = Object.assign({}, rd[3], { seq: 9999, source: "Other Paper" }); await T2.ledgerStream({ article_line: dup }); const Ls = T2.LS.stream, tx = REG.s_ledger.textContent;
  rec("T3e stream path counts articles, a same-title copy adds nothing", Ls.items === rd.length + 1 && Ls.indep === Ls.tick && (Ls.kinds.copy || 0) >= (rd[3].title.split(/\s+/).length >= 5 ? 1 : 0) && tx.includes("As of article #") && mainRows() === 27, "read " + Ls.items + ", counted " + Ls.tick + ", kinds " + JSON.stringify(Ls.kinds));
  Ls.run = Object.assign({}, T2.ST.run, { label_version: { iptc_release: "2099-01-01", cards: "deadbeefdeadbeef" } }); const stale = T2.lgRows(Ls).every(r => r.stale === true && r.as_of.run_id === Ls.run.run_id && r.label_version.iptc_release === "2026-09-30T12:00:00+00:00");
  T2.renderLedger(Ls, ""); const stx = REG.s_ledger.textContent.includes("STALE");
  rec("T3f every row carries as_of + label_version, stale flag on a changed IPTC release", stale && stx, "26 rows stale=" + stale + ", panel says STALE=" + stx);
  Ls.run = { run_id: "r", state: "running", now_epoch: 1, label_version: T2.LS.spec.label_version }; T2.renderLedger(Ls, ""); const gr = REG.s_ledger.all(n => /opacity:\.55/.test(n.attrs.style || "")).length, gt = REG.s_ledger.textContent.includes("Greyed");
  rec("T3g greyed when a running run has not written for 60 s", gr === 1 && gt, gr + " greyed block, text " + gt);
  // T5 made-up streams (ledger_split.py --selftest --dump-synth <file>, argv[4]): the page's JS gives the states and sizes the Python rules give where the real trace has none (decaying, warming, untouched, conflicted, severe/extreme)
  if (process.argv[4]) { const cs = JSON.parse(fs.readFileSync(process.argv[4], "utf8")); let bad5 = 0; const msgs = [];
    for (const c of cs) { const L = T.lgNew(T.LS.spec); c.lines.forEach(l => T.lgAdd(L, l)); const r = T.lgRows(L).find(x => x.resource === c.resource); const okc = "state" in c ? r.state === c.state : Math.abs(r.value - c.value) < 1e-9; if (!okc) { bad5++; msgs.push(c.name + ": want " + (c.state ?? c.value) + ", got " + r.state + " " + r.value) } }
    rec("T5 page JS gives the expected state and size step on " + cs.length + " made-up streams", bad5 === 0, bad5 + " differ" + (msgs.length ? ": " + msgs.join("; ") : "")) }
  // T4 no innerHTML in the page's ledger block
  const i0 = html.indexOf("/* ---- Resource ledger v0"), blk = html.slice(i0, html.lastIndexOf("</script>")), tot = (html.match(/innerHTML/g) || []).length; const bk = (blk.match(/innerHTML/g) || []).length;
  rec("T4 panel uses textContent / el(), no innerHTML", i0 > 0 && bk === 0, "innerHTML in the ledger block: " + bk + " (whole page: " + tot + ")");
  const f = res.filter(r => !r[1]).length; console.log(f ? f + " FAILED" : "ALL PASS (" + res.length + ")"); process.exit(f ? 1 : 0)
})().catch(e => { console.log("HARNESS ERROR", e); process.exit(2) });
