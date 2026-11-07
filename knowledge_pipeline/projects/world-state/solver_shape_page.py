"""Builds demo/mockups/solver/index.html: the six steps an article passes through, in one table. Numbers are read from runs/pulse/*.json at build time.
    python3 solver_shape_page.py   (from projects/world-state)"""
import json, html
R = "runs/pulse/"; L = lambda f: json.load(open(R + f))
sel = L("sparse_selective_flat.json"); rust = L("rust_decider_flat.json"); tm = L("timing_analyze2.json"); ft = L("fulltext_topic_flat.json"); sp = L("sparse_topic_human.json")
TR = json.load(open(R + "trace_articles.json"))["articles"]
import re as _re
for _a in TR: _a["shift"] = len(_re.sub(r"\s+", " ", _a["title"])) + 2
pct = lambda x: f"{x*100:.1f}%"
M = '<span class="chip m">trained model</span>'; RU = '<span class="chip r">rules</span>'
rows = [
 ("1", "Clean", "the article", "clean text", RU, ""),
 ("2", "Windows", "clean text", "slices the reader can take in", RU, ""),
 ("3", "BitMob Reader", "the slices", "topic and story type, each with a confidence", M + " BitMob Reader (22.6M)", f"{tm['t8_reader_median']:.0f} ms"),
 ("4", "Fact finder", "clean text", "facts: amounts, dates, names, who did what", RU + " + " + M + " spaCy parser (not ours)", f"{tm['t8_solver_median']:.0f} ms"),
 ("5", "Validator", "the facts", "each fact marked stated, unbound or invalid", RU, ""),
 ("6", "Decider", "answers, confidences, facts", "answer, or abstain and say why", RU + " proved in Lean, run in Rust", f"{rust['ns_per_call']} ns"),
]
tr = "".join(f"<tr><td>{a}</td><td><b>{b}</b></td><td>{c}</td><td>{d}</td><td>{e}</td><td>{f}</td></tr>" for a, b, c, d, e, f in rows)
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Mob solver</title><link rel="stylesheet" href="../mock.css">
<style>
main{{max-width:860px;margin:0 auto;padding:14px 16px 56px}} h1{{margin:0 0 6px;font-size:24px}} h2{{margin:26px 0 6px;font-size:18px}}
p{{line-height:1.55;font-size:15px;margin:6px 0}} .src{{font:12px ui-monospace,monospace;color:var(--ink-2)}}
table{{border-collapse:collapse;width:100%;font-size:14px}} th,td{{text-align:left;vertical-align:top;padding:7px 8px;border-bottom:1px solid var(--line,#8884)}} th{{font-size:12px;color:var(--ink-2);font-weight:600}}
.chip{{font:700 11px ui-monospace,monospace;padding:2px 7px;border-radius:10px;border:1px solid var(--line,#8884)}} .chip.m{{background:var(--accent);color:#fff}} .chip.r{{background:var(--surface-2)}}
.z-old{{background:#2e8b5744}} .z-read{{background:#3b7dd844}} .z-un{{color:var(--ink-2);opacity:.6}} .fact{{text-decoration:underline;text-decoration-thickness:2px}} .txt{{white-space:pre-wrap;line-height:1.5;font-size:13px;max-height:none;padding:8px;border:1px solid var(--line,#8884);border-radius:8px;margin:8px 0}}
.step{{margin:12px 0;padding:8px 10px;border-left:3px solid var(--accent)}} .step h3{{margin:0 0 4px;font-size:15px}} .io{{display:grid;grid-template-columns:40px 1fr;gap:2px 10px;font-size:14px}} .io p{{margin:2px 0}} .bar{{position:relative;height:18px;background:var(--surface-2);border:1px solid var(--line,#8884);border-radius:4px;margin:6px 0}} .wbar{{position:absolute;top:2px;bottom:2px;background:#3b7dd8;opacity:.6;border-right:1px solid #fff}} .obar{{position:absolute;top:0;height:5px;background:#2e8b57}}
.flow{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:12px 0}} .flow span{{padding:6px 10px;border:1px solid var(--line,#8884);border-radius:8px;background:var(--surface-2);font-size:13px}} .flow i{{font-style:normal;color:var(--ink-2)}}
dl{{display:grid;grid-template-columns:120px 1fr;gap:6px 12px;font-size:14px}} dt{{font-weight:700}} dd{{margin:0}}
@media (max-width:620px){{table,tbody,tr,td,th{{display:block}} th{{display:none}} tr{{padding:6px 0;border-bottom:1px solid var(--line,#8884)}} td{{border:0;padding:2px 0}} dl{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>The Mob solver: how an article becomes a Pulse answer</h1>
<p>The <b>Mob solver</b> is the whole chain: fixed-rule tools and BitMob models working together. An article passes through six steps. Each step hands a checked result to the next. The rules decide when a model is worth calling. The chain is defined in the playbook (sections 1, 2, 4) and built as <code>analyze2.py</code>.</p>
<div class="flow"><span>Article</span><i>→</i><span>1 Clean</span><i>→</i><span>2 Windows</span><i>→</i><span>3 BitMob Reader</span><i>→</i><span>4 Fact finder</span><i>→</i><span>5 Validator</span><i>→</i><span>6 Decider</span><i>→</i><span>Answer with working</span></div>
<table><tr><th>#</th><th>Step</th><th>Takes</th><th>Gives</th><th>Uses</th><th>Time</th></tr>{tr}</table>
<p class="src">Sources: analyze2.py; facts_lib.py; runs/pulse/timing_analyze2.json#t8_reader_median, #t8_solver_median (median, 8 threads); runs/pulse/rust_decider_flat.json#ns_per_call. Times not shown are not measured.</p>
<p>Step 6 is tested by the 160 cases in <code>vectors.txt</code>, made from the Lean rules. The Rust build fails if any case differs. Steps 1 to 5 are still Python.</p>


<h2>The names</h2>
<table><tr><th>Name</th><th>What it is</th><th>Status</th></tr>
<tr><td><b>Mob solver</b></td><td>The whole chain of tools and BitMob models</td><td>built (analyze2.py)</td></tr>
<tr><td><b>BitMob Reader</b></td><td>Step 3 model; registry code PULSEB; formerly Pulse reader</td><td>registered, in use</td></tr>
<tr><td><b>Fact finder</b></td><td>Step 4: pattern rules plus the spaCy parser; stands in for the true solver (your Rust rules and NER)</td><td>built, Python</td></tr>
<tr><td><b>BitMob Keys</b></td><td>Keyword topic model, the planned front step</td><td>candidate, not registered, not wired in</td></tr>
<tr><td><b>BitMob Domain, BitMob Area</b></td><td>Your idea: one model per level of the playbook, called only when the tools say so</td><td>idea; nothing trained, no result</td></tr></table>
<p class="src">Sources: demo/models.json (pulse-reader name, code PULSEB, aliases); playbook/00-knowledge-pipeline-v1.md sections 1, 2, 4; ledger L1022.</p>
<h2>Watch an article go through</h2>
<p>Pick a real article. Below it you see what each step took in and gave out. In the text, <span class="z-old">green</span> is what the old reader saw (first 64 word pieces), <span class="z-read">blue</span> is what the current reader reads (up to 12 windows), and <span class="z-un">grey</span> is text the reader never sees. Amounts and dates the solver found are underlined.</p>
<p><select id="pick"></select></p>
<div id="watch"></div>
<p class="src">Source: runs/pulse/trace_articles.json, made by trace_articles.py from runs/pulse/golden/articles.jsonl (8 of the 200 reference articles, picked by length).</p>
<script>
const DATA = {json.dumps(TR).replace("</","<\\/")};
const el = (t, c, x) => {{ const e = document.createElement(t); if (c) e.className = c; if (x !== undefined) e.textContent = x; return e; }};
const sel = document.getElementById("pick"), box = document.getElementById("watch");
DATA.forEach((a, i) => {{ const o = el("option", "", a.title.slice(0, 70) + " (" + a.body_chars.toLocaleString() + " characters)"); o.value = i; sel.appendChild(o); }});
function step(n, name, inp, out) {{ const d = el("div", "step"); d.appendChild(el("h3", "", n + " " + name)); const l = el("div", "io"); [["In", inp], ["Out", out]].forEach(([k, v]) => {{ l.appendChild(el("b", "", k)); const s = el("div", "", ""); (Array.isArray(v) ? v : [v]).forEach(x => {{ if (x instanceof Node) s.appendChild(x); else s.appendChild(el("p", "", x)); }}); l.appendChild(s); }}); d.appendChild(l); return d; }}
function textView(a) {{
  const t = a.clean, rs = a.shift + a.windows_cover_body_chars, os = a.shift + a.old_reading.body_chars_seen; const pts = new Set([0, t.length, os, rs]);
  a.facts.forEach(f => {{ pts.add(f.s); pts.add(f.e); }}); const P = [...pts].filter(x => x >= 0 && x <= t.length).sort((x, y) => x - y); const wrap = el("div", "txt");
  for (let i = 0; i < P.length - 1; i++) {{ const s = P[i], e = P[i + 1]; if (e <= s) continue; const sp = el("span", s < a.shift ? "z-old" : s < os ? "z-old" : s < rs ? "z-read" : "z-un", t.slice(s, e)); const f = a.facts.find(f => f.s <= s && e <= f.e); if (f) {{ sp.classList.add("fact"); sp.title = f.kind + ": " + f.text.trim() + " (" + f.status + ")"; }} wrap.appendChild(sp); }}
  return wrap;
}}
function render(a) {{
  box.textContent = ""; const T = a.ms;
  box.appendChild(el("h3", "", a.title)); box.appendChild(el("p", "src", "Reader reads " + Math.round(a.windows_cover_share * 100) + "% of the body; the old reader read " + Math.round(a.old_reading.body_share_seen * 100) + "%. The solver reads up to 12,000 characters."));
  box.appendChild(textView(a));
  box.appendChild(step("1", "Clean", a.raw_chars.toLocaleString() + " characters of headline and body", a.clean_chars.toLocaleString() + " characters of clean text (cut at 12,000)"));
  const bar = el("div", "bar"); a.windows.forEach((w, i) => {{ const s = el("span", "wbar"); s.style.left = (w.start / a.body_chars * 100) + "%"; s.style.width = Math.max((w.end - w.start) / a.body_chars * 100, .4) + "%"; s.title = "window " + (i + 1); bar.appendChild(s); }});
  const ob = el("span", "obar"); ob.style.left = "0"; ob.style.width = Math.max(a.old_reading.body_chars_seen / a.body_chars * 100, .4) + "%"; bar.appendChild(ob);
  box.appendChild(step("2", "Windows", "the clean text", [a.windows.length + " windows of up to " + a.max_pieces + " word pieces, headline kept in each, cap " + a.window_cap, bar, "Together they cover " + a.windows_cover_body_chars.toLocaleString() + " of " + a.body_chars.toLocaleString() + " body characters (" + Math.round(a.windows_cover_share * 100) + "%). The green mark is where the old reader stopped."]));
  const tb = el("table", ""); const hr = el("tr"); ["Window", "Characters", "Pieces", "Topic, top two", "Story type"].forEach(h => hr.appendChild(el("th", "", h))); tb.appendChild(hr);
  a.windows.forEach((w, i) => {{ const r = el("tr"); [i + 1, w.start + "-" + w.end, w.pieces, w.topic.map(x => x[0] + " " + x[1]).join(", "), w.story[0] + " " + w.story[1]].forEach(x => r.appendChild(el("td", "", String(x)))); tb.appendChild(r); }});
  box.appendChild(step("3", "BitMob Reader (" + T.reader_ms.toFixed(0) + " ms)", "the windows", [tb, "Averaged answer: " + a.topic_avg.map(x => x[0] + " " + x[1]).join(", ") + "; story type " + a.story_avg.map(x => x[0] + " " + x[1]).join(", ") + ". Old reader (first 64 pieces only): " + a.old_reading.topic.map(x => x[0] + " " + x[1]).join(", ") + "."]));
  const fl = el("div", ""); if (!a.facts.length) fl.appendChild(el("p", "", a.parse_ran ? "The parser ran and found no amount or date." : "No number or date word, so the parser was skipped.")); a.facts.slice(0, 12).forEach(f => fl.appendChild(el("p", "fact-row", f.kind + ": " + f.text.trim() + " -> " + (f.kind === "amount" ? "value " + f.value + ", counts " + (f.noun || f.verb || "nothing") : "date " + f.value) + " [" + f.status + "]"))); if (a.facts.length > 12) fl.appendChild(el("p", "src", "and " + (a.facts.length - 12) + " more"));
  box.appendChild(step("4", "Fact finder (" + T.solver_ms.toFixed(0) + " ms)", "the clean text", [a.facts.length + " amounts and dates found", fl]));
  const c = {{stated: 0, unbound: 0, invalid: 0}}; a.facts.forEach(f => c[f.status]++);
  box.appendChild(step("5", "Validator", "the " + a.facts.length + " facts", "stated " + c.stated + ", unbound " + c.unbound + ", invalid " + c.invalid + ". Each stated fact passed: literally in the text, value reads back, bound to a noun or verb, one sentence."));
  const dt = el("table", ""); const h2 = el("tr"); ["Field", "Outcome", "Answer", "Source"].forEach(h => h2.appendChild(el("th", "", h))); dt.appendChild(h2);
  Object.entries(a.decider).forEach(([k, v]) => {{ const r = el("tr"); [k, v.outcome, v.answer || "-", v.how].forEach(x => r.appendChild(el("td", "", String(x)))); dt.appendChild(r); }});
  box.appendChild(step("6", "Decider (" + T.decider_ms.toFixed(3) + " ms)", "answers, confidences, facts, field markers", dt));
}}
sel.onchange = () => render(DATA[+sel.value]); render(DATA[0]);
</script>

<h2>A planned step in front</h2>
<p><b>BitMob Keys</b> ({M}, candidate, not registered) would read first and give the topic in about {sp['word12_median_us']/1000:.0f} ms. The BitMob Reader would only see what BitMob Keys won't answer. In a test on 1,600 human-labelled articles it answered {pct(sel['share_070'])} of them and was right within two categories on {pct(sel['right_070'])} of those. It is tested alone and not wired in.</p>
<p class="src">Sources: runs/pulse/sparse_selective_flat.json#share_070, #right_070; runs/pulse/sparse_topic_human.json#word12_median_us</p>

<h2>Does it improve itself?</h2>
<p>Not yet. The loop is: answer, collect the answers it wasn't sure of, get them labelled, retrain, check, repeat. The Lean rule that decides which answers may become labels exists. The retraining and the drift check do not.</p>
<p>We have no settled name for this loop in our files.</p>

<h2>Words</h2>
<dl><dt>Mob solver</dt><dd>The whole chain: rules and tools plus BitMob models. Code: analyze2.py.</dd>
<dt>BitMob model</dt><dd>One of our small trained models that runs on a normal CPU.</dd>
<dt>Rules</dt><dd>Fixed instructions. Same input, same output.</dd>
<dt>Trained model</dt><dd>Learned from labelled examples. It can be wrong in ways nobody wrote down.</dd>
<dt>Label</dt><dd>The right answer for one example, from a person or from Claude.</dd>
<dt>Stated fact</dt><dd>A fact written in the text that passed all four checks.</dd>
<dt>Abstain</dt><dd>Decline to answer, and say why.</dd></dl>
<p class="src"><a href="../state/index.html">Pulse state</a> · <a href="../gates/index.html">Gates</a> · <a href="../decider/index.html">Decider</a></p>
</main></body></html>"""
open("/workspace/demo/mockups/solver/index.html", "w", encoding="utf-8").write(page); print("ok", len(page))
