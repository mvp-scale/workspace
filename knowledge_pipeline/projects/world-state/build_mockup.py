import json, pathlib
D = json.load(open("runs/fusion/demo.json")); data = json.dumps(D).replace("</", "<\\/")
html = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cascade in action</title>
<style>
:root{--bg:#fafaf9;--card:#fff;--t1:#1c1917;--t2:#57534e;--t3:#a8a29e;--hair:#e7e5e4;--acc:#2563eb;--good:#16a34a;--bad:#dc2626;--up:#15803d;--dn:#b91c1c;--ent:#7c3aed}
@media (prefers-color-scheme:dark){:root{--bg:#141210;--card:#1c1917;--t1:#f5f5f4;--t2:#a8a29e;--t3:#78716c;--hair:#292524;--acc:#60a5fa;--good:#4ade80;--bad:#f87171;--up:#4ade80;--dn:#f87171;--ent:#c4b5fd}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--t1);font:14px/1.45 system-ui,sans-serif}.wrap{max-width:1100px;margin:0 auto;padding:16px}
h1{font-size:18px;margin:0 0 2px}h2{font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--t3);margin:0 0 8px}.sub{color:var(--t2);margin:0 0 12px}
.card{background:var(--card);border:1px solid var(--hair);border-radius:10px;padding:14px;margin-bottom:12px}.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.tab{border:1px solid var(--hair);background:var(--card);color:var(--t1);border-radius:8px;padding:6px 10px;cursor:pointer;font:inherit}.tab.on{border-color:var(--acc);outline:1px solid var(--acc)}.tab small{display:block;color:var(--t3);font-size:11px}
.sent{margin:0 0 6px}.sent.head{font-weight:600}.up{color:var(--up);font-weight:600}.dn{color:var(--dn);font-weight:600}.ent{border-bottom:2px solid var(--ent)}.ent sup{color:var(--ent);font-size:10px;margin-left:2px}.chg{background:color-mix(in srgb,var(--acc) 18%,transparent);border-radius:3px}
.claim{color:var(--t2);font-style:italic;margin-top:8px}.toggles{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:10px}.toggles label{cursor:pointer}
table{border-collapse:collapse;width:100%}th{color:var(--t3);font-size:11px;text-transform:uppercase;letter-spacing:.04em;text-align:left;font-weight:600;padding:4px 8px 6px 0}td{padding:6px 8px 6px 0;border-top:1px solid var(--hair);vertical-align:middle;white-space:nowrap}tr.sel td{background:color-mix(in srgb,var(--acc) 8%,transparent)}tr.row{cursor:pointer}
.bar{display:inline-block;width:90px;height:8px;background:var(--hair);border-radius:4px;position:relative;vertical-align:middle;margin-right:6px}.bar i{position:absolute;left:0;top:0;bottom:0;border-radius:4px;background:var(--acc)}.bar b{position:absolute;top:-2px;bottom:-2px;width:1px;background:var(--t3)}
.bar.off i{background:var(--t3);opacity:.4}.pbar{width:120px}.pbar i{background:var(--good)}.v{font-size:12px;color:var(--t2)}.vote{display:inline-block;min-width:34px;text-align:center;border-radius:5px;padding:1px 4px;font-size:12px}.vote.y{background:color-mix(in srgb,var(--good) 20%,transparent)}.vote.n{color:var(--t3)}
.probe{display:flex;gap:10px;padding:4px 0;border-top:1px solid var(--hair)}.probe span:first-child{width:46px;color:var(--t2)}.note{color:var(--t3);font-size:12px;margin-top:8px}.warn{color:var(--bad);font-size:12px}
.kv{display:grid;grid-template-columns:150px 1fr;gap:6px 12px;font-size:13px}.kv .k{color:var(--t3);font-size:12px}.chip{display:inline-block;border:1px solid var(--hair);border-radius:12px;padding:0 8px;margin:0 4px 4px 0;font-size:12px}.chip b{color:var(--ent);font-weight:600;margin-right:4px}.pill{display:inline-block;border-radius:5px;padding:0 6px;margin-right:6px;font-size:12px;background:color-mix(in srgb,var(--acc) 15%,transparent)}
.scroll{overflow-x:auto}@media (max-width:700px){.bar{width:50px}}
</style></head><body><div class="wrap">
<h1>Cascade in action</h1>
<p class="sub">One article goes through repeatable CPU layers. Each layer scores every condition; a fitted model fuses them; the four AI answers sit beside it for comparison. Local mockup: it holds publisher text, do not publish or commit it.</p>
<div class="tabs" id="tabs"></div><div id="view"></div>
<p class="note">How to read: a <b>z-score</b> says how far above a typical article the match is (about 2 or more is notable; the tick on each bar is 2). The fused bar is the model's probability that both AI labelers would name the condition. Untick a layer to see what the fused score does without it. Fused models were fitted on 7,710 items, so for these eight it is an in-sample demo, not a test.</p>
</div>
<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent).items;
const el = (tag, attrs, ...kids) => { const e = document.createElement(tag); for (const k in (attrs || {})) { const v = attrs[k]; if (v == null || v === false) continue; if (k === 'text') e.textContent = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v === true ? '' : String(v)); } for (const kid of kids.flat(Infinity)) if (kid != null && kid !== false) e.append(typeof kid === 'object' ? kid : String(kid)); return e; };
const LAY = [['whole text', [0]], ['best sentence', [1]], ['headline', [2]], ['claim (Haiku-written)', [3]], ['spaCy structure', [4, 5, 6, 7, 8, 9]]];
let cur = 0, sel = null, on = [true, true, true, true, true];
const sig = (x) => 1 / (1 + Math.exp(-x));
const pName = (c) => c.replace(/_/g, ' ');
function mark(text, it) {
  const rise = new RegExp('\\b(' + (it.lex.up.length ? it.lex.up.join('|') : '(?!x)x') + ')\\b', 'gi'), fall = new RegExp('\\b(' + (it.lex.down.length ? it.lex.down.join('|') : '(?!x)x') + ')\\b', 'gi');
  const marks = [];
  for (const [t, lab] of it.ents) { let i = text.indexOf(t); if (i >= 0 && t.length > 1) marks.push({ s: i, e: i + t.length, k: 'ent', lab }); }
  for (const m of text.matchAll(rise)) marks.push({ s: m.index, e: m.index + m[0].length, k: 'up' });
  for (const m of text.matchAll(fall)) marks.push({ s: m.index, e: m.index + m[0].length, k: 'dn' });
  for (const w of it.changes) { const re = new RegExp('\\b' + w.replace(/[^a-z]/g, '') + '\\w*', 'gi'); for (const m of text.matchAll(re)) marks.push({ s: m.index, e: m.index + m[0].length, k: 'chg' }); }
  marks.sort((a, b) => a.s - b.s || (a.k === 'ent') - (b.k === 'ent')); const out = []; let pos = 0;
  for (const m of marks) { if (m.s < pos) continue; if (m.s > pos) out.push(text.slice(pos, m.s)); const seg = text.slice(m.s, m.e); out.push(m.k === 'ent' ? el('span', { class: 'ent' }, seg, el('sup', { text: m.lab })) : el('span', { class: m.k, text: seg })); pos = m.e; }
  if (pos < text.length) out.push(text.slice(pos)); return out;
}

function ext(it) {
  const x = it.x, rows = [];
  const chips = (arr) => arr.length ? arr.map((a) => el('span', { class: 'chip', text: a })) : el('span', { class: 'v', text: 'none found' });
  const top = Object.entries(x.story_cpu).sort((a, b) => b[1] - a[1]);
  rows.push(['Topic (AI labelers)', x.topic_ai[0].replace(/_/g, ' ') + (x.topic_ai[0] === x.topic_ai[1] ? ' (both agree)' : ' / ' + x.topic_ai[1].replace(/_/g, ' '))]);
  rows.push(['Story type', [el('span', { class: 'pill', text: 'CPU: ' + top[0][0] + ' ' + Math.round(top[0][1] * 100) + '%' }), el('span', { class: 'v', text: 'then ' + top.slice(1, 3).map(([c, p]) => c + ' ' + Math.round(p * 100) + '%').join(', ') + ' · AI labelers: ' + x.story_ai.join(' / ') })]]);
  rows.push(['Scope (heuristic)', [x.scope + (x.places.length ? ': ' + x.places.join(', ') : ''), x.global_words.length ? el('span', { class: 'v', text: '  global words: ' + x.global_words.join(', ') }) : null]]);
  rows.push(['Entities by type', Object.keys(x.entities).length ? Object.entries(x.entities).map(([t, v]) => v.map((e) => el('span', { class: 'chip' }, el('b', { text: t }), e))) : el('span', { class: 'v', text: 'none found' })]);
  rows.push(['Numbers', chips(x.numbers)]);
  rows.push(['Claim', it.claim ? it.claim + ' (written by Haiku)' : 'none']);
  rows.push(['Attribution / claimer', x.reporting.length ? x.reporting.map((r) => el('span', { class: 'chip' }, el('b', { text: r.verb }), r.claimer || 'no subject found')) : el('span', { class: 'v', text: 'no reporting verb: the outlet states it itself' })]);
  rows.push(['Quoted speech', x.quote ? 'yes, quotation marks present' : 'no']);
  rows.push(['Evidence markers', chips(x.evidence)]);
  rows.push(['Intent / modality', [chips([...x.modal.map((m) => 'modal: ' + m), ...x.future.map((m) => 'future: ' + m), ...x.hedge.map((m) => 'hedge: ' + m), ...x.opinion.map((m) => 'opinion: ' + m)])]]);
  rows.push(['Negation', chips(x.negation)]);
  rows.push(['Direction (lexicon)', it.lex.score > 0 ? 'rise words win → up (' + it.lex.up.join(', ') + ')' : it.lex.score < 0 ? 'fall words win → down (' + it.lex.down.join(', ') + ')' : 'no opinion']);
  return el('div', { class: 'card' }, el('h2', { text: '1b · Everything the cascade extracts from this item (CPU, repeatable; claim and topic are the only AI-written parts)' }), el('div', { class: 'kv' }, rows.flatMap(([k, v]) => [el('div', { class: 'k', text: k }), el('div', null, v)])),
    el('div', { class: 'note', text: 'Not yet extracted: event trigger and roles (who did what to whom), entity linking to a knowledge base, and a validated local-vs-world scope. Scope here is a place-count heuristic with no answer key.' }));
}
function fused(r) { let l = r.bias; LAY.forEach(([n, ix], q) => { if (on[q]) ix.forEach((j) => { l += r.contrib[j]; }); }); return sig(l); }
const vote = (d) => d ? el('span', { class: 'vote y', text: d === 'up' ? '✓ up' : '✓ down' }) : el('span', { class: 'vote n', text: '–' });
function zbar(z, off) { const w = Math.max(0, Math.min(1, z / 5)); return el('span', null, el('span', { class: 'bar' + (off ? ' off' : '') }, el('i', { style: 'width:' + (w * 100) + '%' }), el('b', { style: 'left:' + (2 / 5 * 100) + '%' })), el('span', { class: 'v', text: z.toFixed(1) })); }
function draw() {
  const it = D[cur]; document.getElementById('tabs').replaceChildren(...D.map((x, i) => el('button', { class: 'tab' + (i === cur ? ' on' : ''), onclick: () => { cur = i; sel = null; draw(); } }, 'Item ' + (i + 1), el('small', { text: (i < 5 ? 'hard · ' : 'clear · ') + x.topic.replace(/_/g, ' ') }))));
  const rows = it.rows.map((r) => ({ r, p: fused(r) })).sort((a, b) => b.p - a.p); if (!sel || !rows.find((x) => x.r.c === sel)) sel = rows[0].r.c;
  const text = el('div', { class: 'card' }, el('h2', { text: '1 · The item (headline + description, as the models see it)' }), it.sentences.map((s, i) => el('p', { class: 'sent' + (i === 0 ? ' head' : '') }, mark(s, it))),
    el('div', { class: 'claim' }, 'Claim (written by Haiku): ' + (it.claim || '–')), el('div', { class: 'note' }, 'Purple underline = spaCy entity · blue = change word (spaCy lemma) · ', el('span', { class: 'up', text: 'green' }), ' = rise word · ', el('span', { class: 'dn', text: 'red' }), ' = fall word'));
  const tg = el('div', { class: 'toggles' }, LAY.map(([n], q) => el('label', null, el('input', { type: 'checkbox', checked: on[q] ? true : null, onchange: (e) => { on[q] = e.target.checked; draw(); } }), ' ' + n)));
  const head = ['Condition', 'Fused', 'Whole', 'Sentence', 'Headline', 'Claim', 'A Haiku', 'A Sonnet', 'B Haiku', 'B Sonnet'];
  const tb = el('table', null, el('tr', null, head.map((h) => el('th', { text: h }))), rows.map(({ r, p }) => el('tr', { class: 'row' + (r.c === sel ? ' sel' : ''), onclick: () => { sel = r.c; draw(); } },
    el('td', { text: pName(r.c) }), el('td', null, el('span', { class: 'bar pbar' }, el('i', { style: 'width:' + (p * 100) + '%' })), el('span', { class: 'v', text: Math.round(p * 100) + '%' })),
    r.z.map((z, q) => el('td', null, zbar(z, !on[q]))), ['A Haiku', 'A Sonnet', 'B Haiku', 'B Sonnet'].map((k) => el('td', null, vote(it.ai[k][r.c]))))));
  const layers = el('div', { class: 'card' }, el('h2', { text: '2 · Layers → fused score per condition (click a row)' }), tg, el('div', { class: 'scroll' }, tb),
    el('div', { class: 'note' }, 'Conditions the AI labelers named but that are missing here have too few examples to fit a model (under 30).'), (() => { const miss = Object.entries(it.ai).flatMap(([k, o]) => Object.keys(o).filter((c) => !it.rows.find((r) => r.c === c)).map((c) => k + ': ' + pName(c))); return miss.length ? el('div', { class: 'warn', text: 'Not scored by the fused model: ' + miss.join(' · ') }) : null; })());
  const cr = it.rows.find((r) => r.c === sel);
  const probes = el('div', { class: 'card' }, el('h2', { text: '3 · Why: the closest probe sentences for ' + pName(sel) }), cr.top.map((t) => el('div', { class: 'probe' }, el('span', { text: 'z ' + t.z.toFixed(1) }), el('span', { text: t.probe }))),
    el('div', { class: 'note', text: 'Probes are generated by script from the guideline text. Each is compared with the article by cosine similarity on a static embedding, then standardised (z-score) against 2,000 other articles.' }));
  const verdict = it.lex.score > 0 ? 'rise words win → up' : it.lex.score < 0 ? 'fall words win → down' : 'no opinion';
  const dir = el('div', { class: 'card' }, el('h2', { text: '4 · Direction by change-word lexicon' }), el('p', null, 'Rise words: ', el('span', { class: 'up', text: it.lex.up.join(', ') || 'none' }), '   Fall words: ', el('span', { class: 'dn', text: it.lex.down.join(', ') || 'none' })),
    el('p', null, 'Lexicon says: ', el('b', { text: verdict }), ' (score ' + it.lex.score + ')'), el('div', { class: 'note', text: 'Measured on 3,073 agreed cases: right on 83% of the "up" cases and 54% of the "down" cases when it has an opinion (it has one on about half). One vote among several, not an answer.' }));
  document.getElementById('view').replaceChildren(text, ext(it), layers, probes, dir);
}
draw();
</script></body></html>'''
pathlib.Path("/workspace/_remove/cascade_mockup.html").write_text(html.replace("__DATA__", data), encoding="utf-8"); print("written", len(html) + len(data), "bytes")
