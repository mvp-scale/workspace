"""Completeness check for the knowledge-raw page (lesson 2026-11-20: a view of the pipeline starts from the full chain inventory).
Loads the page in headless Chrome (puppeteer), reads one article through the real API, walks every step and every Extract tab, and checks that
  (1) every stage name in the API's stage_out (the 15 live_trace stages plus the not_attached ones) has a rendered place: an element with data-stage="<name>" and visible text;
  (2) every scan spot class (scan_gate.PAT plus any class in the article's spots) has a rendered place: an element with data-spot="<class>" and visible text;
  (3) the page does not scroll at 1300x900 and logs no console error or page error;
  (4) Story/Status (2026-11-20): every step has a gate tag and a badge derived from status.json (a step shows "live in pipeline" only if every row it stands on is used in live_trace.py per status.json); the Status checklist has every
      playbook section 2 gate (G0, G1, G2, G3a, G3b, G4, G5, G6) and every inventory row; the plan shows 0a, 0b, 1-10; Needs you shows T171-T178; Status fits one screen at 1440x900 (no page scroll, no clipped panel);
  (5) Connect (2026-11-20): the two-line key counts equal the drawn lines of the article (UP by how, SIDE by relation); every drawn line has a reason (data-reason and hover title); up-lines are styled by how they were placed;
      selecting a chip dims the rest and lists a reason per lit line; assertion chips show the full triple (subject - verb -> object).
Exit code 1 if anything is missing. Needs a simulation server (server.py) on --sim; it serves the page itself from a tiny local frontend on --port that proxies /sim-api/ to it.
Run: /workspace/models/embed-zs/.venv/bin/python check-raw-complete.py [--sim http://127.0.0.1:18771] [--port 18772] [--id <article id>] [--shots <dir>]
No hosted calls; CPU only."""
import sys, os, json, argparse, threading, subprocess, tempfile, urllib.request, urllib.parse, http.server, pathlib
HERE = pathlib.Path(__file__).resolve().parent; WS = HERE.parent / "projects" / "world-state"; DEMO = HERE.parent.parent / "demo"
NODE_PATH = os.environ.get("PUPPETEER_NODE_PATH", "/root/.npm/_npx/7d92d9a2d2ccc630/node_modules"); CHROME = os.environ.get("CHROME", "/root/.cache/puppeteer/chrome/linux-153.0.8010.36/chrome-linux64/chrome")
STATUS = DEMO / "mockups" / "knowledge-raw" / "status.json"
VAPE = "b9bd5dedf7525c0d06846c5faccf48b317c43b468b9d0d67c80b11704919564c"
ap = argparse.ArgumentParser(); ap.add_argument("--sim", default="http://127.0.0.1:18771"); ap.add_argument("--port", type=int, default=18772); ap.add_argument("--id", default=VAPE); ap.add_argument("--shots", default=""); a = ap.parse_args()
def get(path):
    with urllib.request.urlopen(a.sim + "/api/" + path, timeout=600) as r: return json.load(r)
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *x): pass
    def do_GET(self):
        p, _, q = self.path.partition("?")
        if p.startswith("/sim-api/"):
            try:
                with urllib.request.urlopen(a.sim + "/api/" + p[len("/sim-api/"):] + ("?" + q if q else ""), timeout=600) as r: b = r.read(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            except Exception as e: b = json.dumps({"error": repr(e)}).encode(); self.send_response(502); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            return
        if p == "/favicon.ico": self.send_response(204); self.end_headers(); return   # the local frontend has no icon; not a page error
        f = (STATUS if p.endswith("/status.json") else DEMO / "mockups" / "knowledge-raw" / "index.html") if p.startswith("/mockups/knowledge-raw") else (DEMO / p.lstrip("/") if p.startswith("/static/") else None)
        if f is None or not f.is_file(): self.send_response(404); self.end_headers(); return
        b = f.read_bytes(); ct = "text/html; charset=utf-8" if f.suffix == ".html" else ("application/json" if f.suffix == ".json" else "text/css" if f.suffix == ".css" else "application/javascript"); self.send_response(200); self.send_header("Content-Type", ct); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
# the expected inventory: from the API itself
sys.path.insert(0, str(WS)); import scan_gate
d = get("raw/sample?n=1&window=any&pick=articles&id=" + a.id); rec = d["articles"][0]
if rec.get("state") != "traced": print("article not traced:", rec.get("state"), rec.get("skip_reason")); sys.exit(2)
stages = list(rec["stage_out"].keys()); classes = sorted({n for n, _ in scan_gate.PAT} | {s[2] for s in rec["scan"]["spots"]}); get("raw/reset")
CONNECT = r"""()=>{const k=document.getElementById('gkey');if(!k)return null;const up={},side={};k.querySelectorAll('[data-how] b').forEach(b=>up[b.dataset.n]=+b.textContent);k.querySelectorAll('button[data-via]').forEach(b=>{side[b.dataset.via]={n:+b.querySelector('b').textContent,off:b.dataset.off==='1'}});
const dU={},dS={},sty={};let noReason=0,total=0;document.querySelectorAll('#gwrap svg path[data-kind]').forEach(p=>{total++;const r=p.getAttribute('data-reason')||'',t=(p.querySelector('title')||{}).textContent||'';if(!r.trim()||!t.trim())noReason++;
 if(p.dataset.kind==='up'&&p.dataset.up!=='domain'){sty[p.dataset.up]={dash:p.getAttribute('stroke-dasharray')||'',op:+p.getAttribute('opacity')};}
 if(p.dataset.cur==='1'){if(p.dataset.kind==='up'&&p.dataset.up!=='domain')dU[p.dataset.up]=(dU[p.dataset.up]||0)+1;if(p.dataset.kind==='side')dS[p.dataset.side]=(dS[p.dataset.side]||0)+1}});
const nodes=[...document.querySelectorAll('#gwrap svg g[data-node]')].map(g=>g.dataset.node);const ent=nodes.find(n=>!/^[DTACRS]:/.test(n));const asr=nodes.find(n=>n.startsWith('A:'));const hl={};
for(const [nm,id] of [['entity',ent],['assertion',asr],['topic',nodes.find(n=>n.startsWith('T:'))]]){if(!id){hl[nm]=null;continue}window._gsel(id);const ps=[...document.querySelectorAll('#gwrap svg path[data-kind]')];hl[nm]={id,lit:ps.filter(p=>p.style.opacity==='1').length,dim:ps.filter(p=>p.style.opacity==='0.06').length,why:document.querySelectorAll('#gwhy .wl').length,whyBad:[...document.querySelectorAll('#gwhy .wl')].filter(w=>!/[↑↔]/.test(w.textContent)||w.textContent.length<12).length,sample:(document.querySelector('#gwhy .wl')||{}).textContent||''}}
window._gsel(null);const chips=[...document.querySelectorAll('#gwrap svg g[data-node^="A:"]')].map(g=>g.querySelector('text').textContent);
return {up,side,dU,dS,sty,noReason,total,hl,chips:chips.length,chipsNoTriple:chips.filter(t=>t.indexOf(' — ')<0).length,chipSample:chips.slice(0,2),guess:[...document.querySelectorAll('#gwrap svg text')].filter(t=>t.textContent==='guess').length,keyText:[...k.querySelectorAll('.kr')].map(r=>r.textContent.slice(0,90))}}"""
JS = r"""
const puppeteer=require('puppeteer');const fs=require('fs');
(async()=>{const [url,chrome,shots]=process.argv.slice(2);const b=await puppeteer.launch({executablePath:chrome,headless:true,args:['--no-sandbox','--disable-gpu']});const pg=await b.newPage();await pg.setViewport({width:1300,height:900});
const errs=[];pg.on('console',m=>{if(m.type()==='error')errs.push('console: '+m.text())});pg.on('pageerror',e=>errs.push('pageerror: '+e.message));pg.on('requestfailed',r=>errs.push('requestfailed: '+r.url()));pg.on('response',r=>{if(r.status()>=400)errs.push('http '+r.status()+' '+r.url())});
await pg.goto(url,{waitUntil:'networkidle0'});const found={stage:{},spot:{}},scroll=[],extra={story:null,connect:null,status:null},shot=async(n)=>{if(shots)await pg.screenshot({path:shots+'/'+n+'.png'})};
const collect=async(label)=>{const r=await pg.evaluate(()=>{const o={stage:{},spot:{},sc:[document.documentElement.scrollHeight,innerHeight,document.documentElement.scrollWidth,innerWidth]};document.querySelectorAll('[data-stage],[data-spot]').forEach(n=>{const t=(n.textContent||'').trim().length;const r=n.getBoundingClientRect();const vis=t>0&&(r.width>0||r.height>0);for(const k of(n.dataset.stage||'').split(' ').filter(Boolean))if(vis)o.stage[k]=(o.stage[k]||0)+t;for(const k of(n.dataset.spot||'').split(' ').filter(Boolean))if(vis)o.spot[k]=(o.spot[k]||0)+t});return o});
 for(const k in r.stage)found.stage[k]=(found.stage[k]||[]).concat(label);for(const k in r.spot)found.spot[k]=(found.spot[k]||[]).concat(label);scroll.push({label,doc:r.sc})};
extra.story=await pg.evaluate(()=>[...document.querySelectorAll('#steps li')].map(li=>({name:li.querySelector('.t').textContent,gate:(li.querySelector('.gtag')||{}).textContent||'',badge:(li.querySelector('.bdg')||{}).dataset?(li.querySelector('.bdg').dataset.badge||''):'',text:(li.querySelector('.bdg')||{}).textContent||'',live:li.querySelector('.bdg')?li.querySelector('.bdg').dataset.live:null,of:li.querySelector('.bdg')?li.querySelector('.bdg').dataset.of:null})));
await pg.click('#b_next');await pg.waitForFunction(()=>document.querySelectorAll('#steps li.go').length===6,{timeout:600000});await new Promise(r=>setTimeout(r,800));
for(let i=1;i<=6;i++){await pg.evaluate(i=>document.querySelectorAll('#steps li')[i-1].click(),i);await new Promise(r=>setTimeout(r,700));
 if(i===3){await collect('s3-extract');await shot('s3-extract')}
 else if(i===4){for(const v of ['graph','rel','flat']){await pg.evaluate(v=>{const b=document.querySelector('[data-view="'+v+'"]');if(b)b.click()},v);await new Promise(r=>setTimeout(r,700));await collect('s4-connect-'+v);await shot('s4-connect-'+v);if(v==='graph')extra.connect=await pg.evaluate(CONNECT)}}
 else{const nm='s'+i+({1:'-read',2:'-understand',4:'-connect',5:'-world',6:'-decision'}[i]||'');await collect(nm);await shot(nm)}}
await pg.setViewport({width:1440,height:900});await pg.evaluate(()=>document.querySelector('[data-mode=status]').click());await new Promise(r=>setTimeout(r,900));await shot('status-1440x900');
extra.status=await pg.evaluate(()=>{const d=document.documentElement,pn=[...document.querySelectorAll('#status .pn')].map(p=>({id:p.id,sh:p.scrollHeight,ch:p.clientHeight,sw:p.scrollWidth,cw:p.clientWidth}));return{doc:[d.scrollHeight,innerHeight,d.scrollWidth,innerWidth],panels:pn,rows:[...document.querySelectorAll('#p_check .ck')].map(r=>({id:r.dataset.row,ticks:[...r.querySelectorAll('.tk')].map(t=>t.dataset.s+':'+t.textContent.trim()),title:r.title.length})),gates:[...document.querySelectorAll('#p_check .ck .gt')].map(g=>g.textContent),count:(document.querySelector('[data-count=core]')||{}).textContent||'',steps:[...document.querySelectorAll('#p_next .sp')].map(r=>({id:r.dataset.step,state:r.dataset.state,text:r.textContent.length})),needs:[...document.querySelectorAll('#p_needs .ny')].map(r=>({id:r.dataset.task,un:[...r.querySelectorAll('.un')].map(u=>u.textContent)})),run:(document.querySelector('[data-running]')||{dataset:{}}).dataset.running||null,gen:(document.getElementById('stgen')||{}).textContent||'',hidden_story:getComputedStyle(document.querySelector('.app')).display}});
console.log(JSON.stringify({found,scroll,errs,extra}));await b.close()})().catch(e=>{console.error('FAIL',e);process.exit(3)});
"""
JS = "const CONNECT=" + CONNECT + ";\n" + JS
jf = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, dir=tempfile.gettempdir()); jf.write(JS); jf.close()
env = dict(os.environ, NODE_PATH=NODE_PATH); url = "http://127.0.0.1:%d/mockups/knowledge-raw/index.html?id=%s" % (a.port, a.id)
if a.shots: os.makedirs(a.shots, exist_ok=True)
pr = subprocess.run(["node", jf.name, url, CHROME, a.shots], capture_output=True, text=True, env=env, timeout=900); os.unlink(jf.name)
if pr.returncode != 0: print("browser run failed:", pr.stderr[-800:]); sys.exit(3)
res = json.loads(pr.stdout.strip().splitlines()[-1]); F = res["found"]; bad = 0
print("article %s | %d stages in stage_out | %d scan spot classes | page %s" % (a.id[:10], len(stages), len(classes), url.split("?")[0]))
for n in stages:
    w = F["stage"].get(n); print("  stage %-20s %s" % (n, ("rendered in " + ", ".join(sorted(set(w))[:4])) if w else "MISSING")); bad += 0 if w else 1
for c in classes:
    w = F["spot"].get(c); print("  spot  %-20s %s" % (c, ("rendered in " + ", ".join(sorted(set(w))[:4])) if w else "MISSING")); bad += 0 if w else 1
EXP = ["g0_read", "g1_spans", "g1_places", "g2_facts", "g2_ner", "g2_claims", "g3_topic", "g3_area", "g3_condition", "g3_heads", "g3_time", "g3_decider", "g4_identity", "g4_contra", "g5_link", "g5_evol", "g6_educate", "journal", "lean_p", "learn", "world_resource", "world_truth", "two_clocks"]
X = res["extra"]; sj = json.load(open(STATUS)); rb = {r["id"]: r for r in sj["rows"]}
def chk(name, ok, detail=""):
    global bad; print("  %-4s %s %s" % ("ok" if ok else "FAIL", name, detail)); bad += 0 if ok else 1
import re as _re
pbg = _re.findall(r"^\| (G\d[ab]?) — ", _re.search(r"^## 2\. .*?(?=^## 3\.)", (HERE.parent / "playbook" / "00-knowledge-pipeline-v1.md").read_text(), _re.S | _re.M).group(0), _re.M)
dom = X["status"]
print("  --- Story / Status ---")
chk("status.json has every inventory row (%d)" % len(EXP), set(EXP) <= set(rb), "missing: %s" % sorted(set(EXP) - set(rb)))
chk("every playbook section 2 gate is covered by a row: %s" % ",".join(pbg), set(pbg) <= {g for r in sj["rows"] for g in r["gates"]}, "missing: %s" % sorted(set(pbg) - {g for r in sj["rows"] for g in r["gates"]}))
chk("Status checklist shows every inventory row and every gate", sorted(r["id"] for r in dom["rows"]) == sorted(rb) and set(pbg) <= set(" ".join(dom["gates"]).split()), "rendered %d of %d rows" % (len(dom["rows"]), len(rb)))
chk("every row has three ticks", all(len(r["ticks"]) == 3 and all(t.split(":")[0] in ("yes", "part", "no") for t in r["ticks"]) for r in dom["rows"]))
chk("rendered ticks equal status.json", all([t.split(":")[0] for t in r["ticks"]] == [rb[r["id"]][k]["s"] for k in ("aligned", "implemented", "used")] for r in dom["rows"]))
cc = sj["counts"]["core"]; chk("count line equals status.json (core %d of %d live)" % (cc["live"], cc["n"]), ("core: %d of %d live" % (cc["live"], cc["n"])) in dom["count"], dom["count"][:70])
sm = {x["step"]: x for x in sj["story"]}; sb = X["story"]
chk("Story has 6 steps, each with a gate tag and a badge", len(sb) == 6 and all(x["gate"] and x["badge"] for x in sb), str([(x["name"], x["gate"], x["badge"]) for x in sb]))
badok = True
for x in sb:
    rows_ = [rb[r]["used"]["s"] for r in sm[x["name"]]["rows"]]; exp = "live" if all(t == "yes" for t in rows_) else ("page" if not any(t == "yes" for t in rows_) else "part")
    if x["badge"] != exp or (x["badge"] == "live" and any(t != "yes" for t in rows_)): badok = False; print("      step %s shows %s, status.json says %s" % (x["name"], x["badge"], exp))
chk("Story never shows live for an item status.json marks not live", badok, "badges: " + ", ".join("%s=%s" % (x["name"], x["text"]) for x in sb))
chk("Status plan shows 0a, 0b, 1-10", [s["id"] for s in dom["steps"]] == ["0a", "0b"] + [str(i) for i in range(1, 11)], str([(s["id"], s["state"]) for s in dom["steps"]]))
stt = {s["id"]: s["state"] for s in dom["steps"]}; chk("steps 0a, 0b, 1, 3 are done", all(stt.get(k) == "done" for k in ("0a", "0b", "1", "3")))
nd = {n["id"]: n["un"] for n in dom["needs"]}; chk("Needs you shows T171-T178", all(("T%d" % i) in nd for i in range(171, 179)), str(sorted(nd)))
mp = {"T172": "step 2", "T173": "step 4", "T174": "step 5", "T171": "step 3 provisional", "T178": "step 3 provisional", "T175": "step 3"}
chk("each decision names the plan steps it unlocks", all(any(m in u for u in nd.get(t, [])) for t, m in mp.items()), str({t: nd.get(t) for t in mp}))
chk("a running card is shown if one exists in round_cards/started", (dom["run"] not in (None, "none")) == bool(sj["plan"]["running"]), "run=%s" % dom["run"])
chk("generation time shown", "generated" in dom["gen"], dom["gen"][:60])
chk("Status fits one screen at 1440x900 (no page scroll)", dom["doc"][0] <= dom["doc"][1] + 1 and dom["doc"][2] <= dom["doc"][3] + 1, str(dom["doc"]))
clip = [p for p in dom["panels"] if p["sh"] > p["ch"] + 1 or p["sw"] > p["cw"] + 1]; chk("no Status panel is clipped (3 panels)", len(dom["panels"]) == 3 and not clip, str(clip or [(p["id"], p["sh"], p["ch"]) for p in dom["panels"]]))
print("  --- Connect key ---"); C = X["connect"]
chk("key and graph rendered", C is not None)
if C:
    chk("UP key counts equal drawn up-lines of this article", all(C["up"].get(h, 0) == C["dU"].get(h, 0) for h in set(C["up"]) | set(C["dU"])), "key %s | drawn %s" % (C["up"], C["dU"]))
    chk("SIDE key counts equal drawn side-lines of this article", all((C["side"][v]["n"] == C["dS"].get(v, 0)) for v in C["side"] if not C["side"][v]["off"]) and all(v in C["side"] for v in C["dS"]), "key %s | drawn %s" % ({v: x["n"] for v, x in C["side"].items() if not x["off"]}, C["dS"]))
    chk("every drawn edge has a reason (data-reason and hover title): %d edges" % C["total"], C["noReason"] == 0 and C["total"] > 0, "%d without" % C["noReason"])
    stl = C["sty"]; chk("up-lines styled by how they were placed (exact solid, WordNet dashed, sentence dotted, article topic faint)", all([("exact" not in stl or stl["exact"]["dash"] == ""), ("wordnet" not in stl or stl["wordnet"]["dash"] == "6 3"), ("sentence" not in stl or stl["sentence"]["dash"] == "1.5 3"), ("article-topic" not in stl or stl["article-topic"]["op"] <= .5)]), str(stl))
    chk("article-topic placements are labelled 'guess'", (C["dU"].get("article-topic", 0) == 0) or C["guess"] > 0, "%d guess labels" % C["guess"])
    hl = C["hl"]; chk("selecting an entity, an assertion or a topic lights its links, dims the rest and lists a reason per lit line", all(v is not None and v["lit"] > 0 and v["dim"] > 0 and v["why"] > 0 and v["whyBad"] == 0 for v in hl.values()), "; ".join("%s: lit %d dim %d why %d" % (k, v["lit"], v["dim"], v["why"]) for k, v in hl.items() if v))
    print("      why sample: " + " | ".join(v["sample"][:110] for v in hl.values() if v))
    chk("assertion chips show the full triple (subject — verb → object): %d chips" % C["chips"], C["chips"] > 0 and C["chipsNoTriple"] == 0, str(C["chipSample"]))
    print("      key lines: " + " || ".join(C["keyText"]))
over = [s for s in res["scroll"] if s["doc"][0] > s["doc"][1] + 1 or s["doc"][2] > s["doc"][3] + 1]
print("  page scroll at 1300x900: %s" % ("NONE" if not over else "; ".join("%s %s" % (s["label"], s["doc"]) for s in over))); bad += len(over)
print("  console/page errors: %s" % ("none" if not res["errs"] else "; ".join(res["errs"][:5]))); bad += len(res["errs"])
print("RESULT:", "PASS" if not bad else "FAIL (%d problems)" % bad); srv.shutdown(); sys.exit(1 if bad else 0)
