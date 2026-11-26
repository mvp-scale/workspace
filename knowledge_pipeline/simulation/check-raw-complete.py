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
ap = argparse.ArgumentParser(); ap.add_argument("--sim", default="http://127.0.0.1:18771"); ap.add_argument("--port", type=int, default=18772); ap.add_argument("--id", default=VAPE); ap.add_argument("--shots", default=""); ap.add_argument("--src", default="", help="article source of the page: window, queue or area:<key> (default: the page default)"); a = ap.parse_args()
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
if not a.src and a.id == VAPE and not get("raw/sample?n=1&window=24h&pick=articles&src=window&id=" + VAPE).get("articles"):   # the default id is not in the newest pipeline window: read that window's first article so the page stays on the window source
    w = get("raw/sample?n=1&window=24h&pick=articles&src=window").get("articles") or []
    if w: a.id = w[0]["id"]
if rec.get("state") != "traced": print("article not traced:", rec.get("state"), rec.get("skip_reason")); sys.exit(2)
stages = list(rec["stage_out"].keys()); classes = sorted({n for n, _ in scan_gate.PAT} | {s[2] for s in rec["scan"]["spots"]}); get("raw/reset")
CONNECT = r"""()=>{const k=document.getElementById('gkey');if(!k)return null;const up={},side={};k.querySelectorAll('[data-how] b').forEach(b=>up[b.dataset.n]=+b.textContent);k.querySelectorAll('button[data-via]').forEach(b=>{side[b.dataset.via]={n:+b.querySelector('b').textContent,off:b.dataset.off==='1'}});
const dU={},dS={},sty={};let noReason=0,total=0;document.querySelectorAll('#gwrap svg path[data-kind]').forEach(p=>{total++;const r=p.getAttribute('data-reason')||'',t=(p.querySelector('title')||{}).textContent||'';if(!r.trim()||!t.trim())noReason++;
 if(p.dataset.kind==='up'&&p.dataset.up!=='domain'){sty[p.dataset.up]={dash:p.getAttribute('stroke-dasharray')||'',op:+p.getAttribute('opacity')};}
 if(p.dataset.cur==='1'){if(p.dataset.kind==='up'&&p.dataset.up!=='domain')dU[p.dataset.up]=(dU[p.dataset.up]||0)+1;if(p.dataset.kind==='side')dS[p.dataset.side]=(dS[p.dataset.side]||0)+1}});
const nodes=[...document.querySelectorAll('#gwrap svg g[data-node]')].map(g=>g.dataset.node);const ent=nodes.find(n=>!/^[DTACRS]:/.test(n));const asr=nodes.find(n=>n.startsWith('A:'));const hl={};
for(const [nm,id] of [['entity',ent],['assertion',asr],['topic',nodes.find(n=>n.startsWith('T:'))]]){if(!id){hl[nm]=null;continue}window._gsel(id);const ps=[...document.querySelectorAll('#gwrap svg path[data-kind]')];hl[nm]={id,lit:ps.filter(p=>p.style.opacity==='1').length,dim:ps.filter(p=>p.style.opacity==='0.06').length,why:document.querySelectorAll('#gwhy .wl').length,whyBad:[...document.querySelectorAll('#gwhy .wl')].filter(w=>!/[↑↔]/.test(w.textContent)||w.textContent.length<12).length,sample:(document.querySelector('#gwhy .wl')||{}).textContent||''}}
window._gsel(null);const chips=[...document.querySelectorAll('#gwrap svg g[data-node^="A:"]')].map(g=>g.querySelector('text').textContent);
return {up,side,dU,dS,sty,noReason,total,hl,chips:chips.length,chipsNoTriple:chips.filter(t=>t.indexOf(' — ')<0&&!t.endsWith('…')).length,chipSample:chips.slice(0,2),guess:[...document.querySelectorAll('#gwrap svg text')].filter(t=>t.textContent==='guess').length,keyText:[...k.querySelectorAll('.kr')].map(r=>r.textContent.slice(0,90))}}"""
JS = r"""
const puppeteer=require('puppeteer');const fs=require('fs');
(async()=>{const [url,chrome,shots]=process.argv.slice(2);const b=await puppeteer.launch({executablePath:chrome,headless:true,args:['--no-sandbox','--disable-gpu']});const pg=await b.newPage();await pg.setViewport({width:1300,height:900});
const errs=[];pg.on('console',m=>{if(m.type()==='error')errs.push('console: '+m.text())});pg.on('pageerror',e=>errs.push('pageerror: '+e.message));pg.on('requestfailed',r=>errs.push('requestfailed: '+r.url()));pg.on('response',r=>{if(r.status()>=400)errs.push('http '+r.status()+' '+r.url())});
await pg.goto(url,{waitUntil:'networkidle0'});const found={stage:{},spot:{}},scroll=[],extra={story:null,connect:null,status:null},shot=async(n)=>{if(shots)await pg.screenshot({path:shots+'/'+n+'.png'})};
const collect=async(label)=>{const r=await pg.evaluate(()=>{const o={stage:{},spot:{},sc:[document.documentElement.scrollHeight,innerHeight,document.documentElement.scrollWidth,innerWidth]};document.querySelectorAll('[data-stage],[data-spot]').forEach(n=>{const t=(n.textContent||'').trim().length;const r=n.getBoundingClientRect();const vis=t>0&&(r.width>0||r.height>0);for(const k of(n.dataset.stage||'').split(' ').filter(Boolean))if(vis)o.stage[k]=(o.stage[k]||0)+t;for(const k of(n.dataset.spot||'').split(' ').filter(Boolean))if(vis)o.spot[k]=(o.spot[k]||0)+t});return o});
 for(const k in r.stage)found.stage[k]=(found.stage[k]||[]).concat(label);for(const k in r.spot)found.spot[k]=(found.spot[k]||[]).concat(label);scroll.push({label,doc:r.sc})};
extra.story=await pg.evaluate(()=>[...document.querySelectorAll('#steps li')].map(li=>({name:li.querySelector('.t').textContent,gate:(li.querySelector('.gtag')||{}).textContent||'',badge:(li.querySelector('.bdg')||{}).dataset?(li.querySelector('.bdg').dataset.badge||''):'',text:(li.querySelector('.bdg')||{}).textContent||'',live:li.querySelector('.bdg')?li.querySelector('.bdg').dataset.live:null,of:li.querySelector('.bdg')?li.querySelector('.bdg').dataset.of:null})));
await pg.click('#b_next');await pg.waitForFunction(()=>document.querySelectorAll('#steps li.go').length===7,{timeout:600000});await new Promise(r=>setTimeout(r,800));
for(let i=1;i<=7;i++){await pg.evaluate(i=>document.querySelectorAll('#steps li')[i-1].click(),i);await new Promise(r=>setTimeout(r,700));
 if(i===3){await collect('s3-extract');await shot('s3-extract')}
 else if(i===4){for(const v of ['graph','rel','flat']){await pg.evaluate(v=>{const b=document.querySelector('[data-view="'+v+'"]');if(b)b.click()},v);await new Promise(r=>setTimeout(r,700));await collect('s4-connect-'+v);await shot('s4-connect-'+v);if(v==='graph')extra.connect=await pg.evaluate(CONNECT)}}
 else if(i===5){await pg.setViewport({width:1440,height:900});await pg.waitForFunction(()=>{const k=document.querySelector('[data-knowledge]');return k&&k.dataset.knowledge!=='loading'},{timeout:600000});await new Promise(r=>setTimeout(r,600));await collect('s5-knowledge-1440x900');await shot('s5-knowledge');extra.kn=await pg.evaluate(KNOWL);extra.wi=await pg.evaluate(WHAT);if(extra.wi&&extra.wi.has){await pg.evaluate(()=>document.querySelector('#kn_whatis > summary').click());await new Promise(r=>setTimeout(r,400));extra.wiOpen=await pg.evaluate(WHAT);if(shots)await pg.screenshot({path:shots+'/kn-whatis-open.png'});await pg.evaluate(()=>document.querySelector('#kn_whatis > summary').click());await new Promise(r=>setTimeout(r,300));extra.wiClosed=await pg.evaluate(WHAT)}
   if(extra.kn&&extra.kn.ctr){extra.knEv={};for(const c of ['new','reinforced','contested','bridging']){await pg.evaluate(c=>document.querySelector('[data-counter="'+c+'"]').click(),c);await new Promise(r=>setTimeout(r,250));extra.knEv[c]=await pg.evaluate(KNEV)}await pg.evaluate(()=>document.querySelector('[data-counter="reinforced"]').click())}
   if(extra.kn&&extra.kn.ctr&&await pg.evaluate(()=>!!document.querySelector('[data-build]'))){const BS=()=>pg.evaluate(()=>{const k=document.getElementById('kn'),b=k.querySelector('[data-build]'),ad=k.querySelector('[data-added]'),c={};k.querySelectorAll('.cb').forEach(x=>c[x.dataset.counter]=+x.dataset.n);return{k:+b.dataset.buildK,n:+b.dataset.buildN,label:(k.querySelector('[data-build-label]')||{}).textContent||'',ctr:c,items:ad?ad.querySelectorAll('[data-added-kind]').length:-1,kinds:ad?[...new Set([...ad.querySelectorAll('[data-added-kind]')].map(x=>x.dataset.addedKind))]:[],from:ad?+ad.dataset.addedFrom:-1,to:ad?+ad.dataset.addedTo:-1,doc:[document.documentElement.scrollHeight,innerHeight]}});
    const slp=ms=>new Promise(r=>setTimeout(r,ms));extra.build=[await BS()];
    await pg.evaluate(()=>{const s=document.getElementById('bk_slider');s.value='1';s.dispatchEvent(new Event('change'))});await slp(300);extra.build.push(await BS());
    for(const id of ['bk_p5','bk_p1','bk_p10']){await pg.evaluate(id=>document.getElementById(id).click(),id);await slp(300);extra.build.push(await BS())}
    extra.buildWhy=await pg.evaluate(async()=>{const w=document.querySelector('[data-added-kind] .why1');if(!w)return null;w.click();await new Promise(r=>setTimeout(r,100));const d=document.getElementById('det');return{open:d.classList.contains('open'),rows:d.querySelectorAll('.r').length}});
    await pg.evaluate(()=>{const d=document.getElementById('det');if(d)d.classList.remove('open')});await pg.evaluate(()=>{const b=document.getElementById('bk_read');if(b)b.click()});await slp(300);extra.buildBack=await BS()}
   /* Concepts view (2026-11-22): card slots, street map, delta list, go deep, view switch */
   {const slp=ms=>new Promise(r=>setTimeout(r,ms)),CVS=()=>pg.evaluate(()=>{const k=document.getElementById('kn'),c=document.getElementById('kn_concepts');if(!c||!k)return null;const d=document.documentElement,card=c.querySelector('[data-card]'),svg=c.querySelector('svg.map'),vis=e=>!!e&&e.getClientRects().length>0;
     return{view:k.dataset.view,state:c.dataset.concepts,none:(c.querySelector('[data-concepts=none]')||{}).textContent||'',focus:c.dataset.focus,card:card?card.dataset.card:null,name:(c.querySelector('[data-card-name]')||{}).textContent||'',slots:[...c.querySelectorAll('[data-slot]')].map(x=>x.dataset.slot),fills:c.querySelectorAll('[data-slot-fill]').length,badge:(c.querySelector('.stb')||{}).textContent||'',bar:!!c.querySelector('.cbar i'),nodes:svg?svg.querySelectorAll('g[data-node]').length:-1,nodesAttr:svg?+svg.dataset.nodes:-1,links:svg?svg.querySelectorAll('g.lnk').length:-1,linksAttr:svg?+svg.dataset.links:-1,mapLabel:(c.querySelector('[data-map-count]')||{}).textContent||'',delta:(c.querySelector('[data-delta]')||{dataset:{}}).dataset.delta,known:(c.querySelector('[data-known]')||{dataset:{}}).dataset.known,knownTxt:(c.querySelector('[data-known]')||{}).textContent||'',verdicts:[...c.querySelectorAll('[data-verdict-line]')].map(x=>x.dataset.verdictLine),deepPanel:(c.querySelector('[data-deep-panel]')||{dataset:{}}).dataset.deepState||null,deepSec:[...c.querySelectorAll('[data-deep-panel] .dsec')].map(x=>x.textContent),focusDepth:(()=>{const f=svg&&svg.querySelector('g.nd.focus');return f?+f.dataset.depth:-1})(),cardDepth:card?+card.dataset.depth:-1,doc:[d.scrollHeight,innerHeight,d.scrollWidth,innerWidth],ctrVisible:vis(k.querySelector('.cb')),bldVisible:vis(k.querySelector('.bld')),addedVisible:vis(k.querySelector('[data-added]')),evpVisible:vis(k.querySelector('.evp')),ansVisible:vis(k.querySelector('.ans')),cvVisible:vis(c),swBtns:[...k.querySelectorAll('[data-view-btn]')].map(b=>b.dataset.viewBtn),lineDeep:c.querySelectorAll('[data-deep-line]').length}}),
    ready=async()=>{await pg.waitForFunction(()=>{const c=document.getElementById('kn_concepts');return c&&c.dataset.concepts&&c.dataset.concepts!=='loading'},{timeout:120000});await slp(400)};
    /* Developments view (2026-11-23): the default view of the Knowledge step; list, detail (since your last look, KNOW / FOLLOW / EXPECT), assertion -> evidence */
    {const DVS=()=>pg.evaluate(()=>{const k=document.getElementById('kn'),c=document.getElementById('kn_developments');if(!c||!k)return null;return{view:k.dataset.view,state:c.dataset.developments,none:(c.querySelector('[data-developments=none]')||{}).textContent||'',count:+c.dataset.count,thin:+(c.dataset.thin||0),moved:c.dataset.moved,rows:c.querySelectorAll('[data-dev]').length,strip:(c.querySelector('[data-dv-strip]')||{}).textContent||'',movedTxt:(c.querySelector('[data-dv-moved]')||{}).textContent||'',swBtns:[...k.querySelectorAll('[data-view-btn]')].map(b=>b.dataset.viewBtn),secs:[...c.querySelectorAll('[data-dev-detail] [data-sec]')].map(x=>x.dataset.sec),assertions:c.querySelectorAll('[data-assertion]').length,cut:!!c.querySelector('[data-dv-cut]'),doc:[document.documentElement.scrollHeight,innerHeight,document.documentElement.scrollWidth,innerWidth]}}),
     dvReady=async()=>{await pg.waitForFunction(()=>{const c=document.getElementById('kn_developments');return c&&c.dataset.developments&&c.dataset.developments!=='loading'},{timeout:120000});await new Promise(r=>setTimeout(r,400))};
     extra.dv={};if(await pg.evaluate(()=>!!document.getElementById('kn_developments'))){await dvReady();extra.dv.first=await DVS();await shot('developments-1-list-detail');extra.dv.across=await pg.evaluate(async()=>{const c=document.getElementById('kn_developments'),a=c&&c.querySelector('[data-dv-across]');if(!a)return null;const doc=[document.documentElement.scrollHeight,innerHeight,document.documentElement.scrollWidth,innerWidth];a.open=true;await new Promise(r=>setTimeout(r,100));return{cuts:+a.dataset.dvAcross,gaps:+a.dataset.acGaps,rows:[...a.querySelectorAll('[data-ac-id]')].map(r=>({id:r.dataset.acId,st:r.dataset.status,t:r.textContent})),gapLabels:[...a.querySelectorAll('[data-gap]')].map(g=>g.textContent),doc,noMissing:c.textContent.indexOf('MISSING')<0,steps:a.querySelectorAll('[data-ac-step]').length}});
      extra.dv.open=await pg.evaluate(async()=>{const d=document.querySelector('#kn_developments details[data-assertion]');if(!d)return null;d.open=true;await new Promise(r=>setTimeout(r,100));return{id:d.dataset.assertion,frags:d.querySelectorAll('[data-fragment]').length}});await shot('developments-2-assertion-evidence');
      extra.dv.second=await pg.evaluate(async()=>{const b=document.querySelectorAll('#kn_developments [data-dev]')[1];if(!b)return null;b.click();await new Promise(r=>setTimeout(r,200));return{id:b.dataset.dev,shown:(document.querySelector('[data-dev-detail]')||{dataset:{}}).dataset.devDetail}});}}
    extra.cv={};if(await pg.evaluate(()=>!!document.querySelector('[data-view-btn=concepts]'))){await pg.evaluate(()=>document.querySelector('[data-view-btn=concepts]').click());await ready();
    await pg.evaluate(()=>{const s=document.getElementById('bk_slider');if(s){s.value=s.max;s.dispatchEvent(new Event('change'))}});await ready();extra.cv.first=await CVS();await shot('concepts-1-card-map-delta');
    if(extra.cv.first&&extra.cv.first.state==='ready'){
      extra.cv.scent=await pg.evaluate(async()=>{const g=document.querySelector('svg.map g.lnk');if(!g)return null;g.dispatchEvent(new MouseEvent('mouseenter'));await new Promise(r=>setTimeout(r,50));const t=document.querySelector('[data-scent]').textContent;const w=g.dataset.why;g.dispatchEvent(new MouseEvent('mouseleave'));return{t,w,rel:g.dataset.rel}});
      extra.cv.clickedFrom=extra.cv.first.focus;
      extra.cv.clicked=await pg.evaluate(async()=>{const ns=[...document.querySelectorAll('svg.map g[data-node]')].filter(g=>!g.classList.contains('focus'));if(!ns.length)return null;const g=ns[0];const id=g.dataset.node;g.dispatchEvent(new MouseEvent('click',{bubbles:true}));await new Promise(r=>setTimeout(r,300));return id});
      extra.cv.second=await CVS();
      await pg.evaluate(()=>document.getElementById('cv_deep').click());extra.cv.deepNow=await CVS();extra.cv.deepFocus=extra.cv.second&&extra.cv.second.focus;
      await pg.waitForFunction(()=>{const p=document.querySelector('[data-deep-panel]');return p&&p.dataset.deepState!=='loading'},{timeout:180000});await slp(400);extra.cv.deep=await CVS();await shot('concepts-2-after-go-deep');
      extra.cv.lineDeep=await pg.evaluate(async()=>{const b=document.querySelector('[data-deep-line]:not([disabled])');return b?b.dataset.deepLine:null});
    }
    for(const v of ['build','evidence','concepts']){await pg.evaluate(v=>document.querySelector('[data-view-btn='+v+']').click(),v);await slp(500);extra.cv['v_'+v]=await CVS();if(v!=='concepts')await shot('concepts-view-'+v)}
    await pg.evaluate(()=>{const b=document.getElementById('bk_read');if(b)b.click()});await slp(300)}
   }
   await pg.setViewport({width:1300,height:900})}
 else{const nm='s'+i+({1:'-read',2:'-understand',4:'-connect',6:'-world',7:'-decision'}[i]||'');await collect(nm);await shot(nm)}}
extra.grow=[];if((await pg.evaluate(()=>!!document.getElementById('areasw')&&/^area:/.test(new URLSearchParams(location.search).get('src')||'')))){await pg.setViewport({width:1440,height:900});await pg.evaluate(()=>document.getElementById('b_reset').click());await new Promise(r=>setTimeout(r,700));await pg.click('#b_next');await pg.waitForFunction(()=>document.querySelectorAll('#steps li.go').length===7,{timeout:600000});await pg.evaluate(()=>document.querySelectorAll('#steps li')[4].click());
  for(let k=0;k<5;k++){await pg.waitForFunction(()=>{const x=document.querySelector('[data-knowledge]');return x&&x.dataset.knowledge==='ready'},{timeout:600000});await new Promise(r=>setTimeout(r,500));extra.grow.push(await pg.evaluate(KNOWL));if(k===1)await shot('s5-knowledge-early');
    if(k<4){await pg.evaluate(()=>document.getElementById('kn_next').click());await new Promise(r=>setTimeout(r,2500))}}await pg.setViewport({width:1300,height:900})}
await pg.setViewport({width:1440,height:900});await pg.evaluate(()=>document.querySelector('[data-mode=status]').click());await new Promise(r=>setTimeout(r,900));await shot('status-1440x900');
extra.status=await pg.evaluate(()=>{const d=document.documentElement,pn=[...document.querySelectorAll('#status .pn')].map(p=>({id:p.id,sh:p.scrollHeight,ch:p.clientHeight,sw:p.scrollWidth,cw:p.clientWidth}));return{doc:[d.scrollHeight,innerHeight,d.scrollWidth,innerWidth],panels:pn,rows:[...document.querySelectorAll('#p_check .ck')].map(r=>({id:r.dataset.row,ticks:[...r.querySelectorAll('.tk')].map(t=>t.dataset.s+':'+t.textContent.trim()),title:r.title.length})),gates:[...document.querySelectorAll('#p_check .ck .gt')].map(g=>g.textContent),count:(document.querySelector('[data-count=core]')||{}).textContent||'',steps:[...document.querySelectorAll('#p_next .sp')].map(r=>({id:r.dataset.step,state:r.dataset.state,text:r.textContent.length})),needs:[...document.querySelectorAll('#p_needs .ny')].map(r=>({id:r.dataset.task,un:[...r.querySelectorAll('.un')].map(u=>u.textContent)})),run:(document.querySelector('[data-running]')||{dataset:{}}).dataset.running||null,gen:(document.getElementById('stgen')||{}).textContent||'',hidden_story:getComputedStyle(document.querySelector('.app')).display}});
console.log(JSON.stringify({found,scroll,errs,extra}));await b.close()})().catch(e=>{console.error('FAIL',e);process.exit(3)});
"""
KNOWL = r"""()=>{const k=document.getElementById('kn');if(!k)return {none:(document.querySelector('[data-knowledge=none]')||{}).textContent||'absent'};const d=document.documentElement,ctr={};k.querySelectorAll('.cb').forEach(b=>ctr[b.dataset.counter]=+b.dataset.n);
return {asof:(k.querySelector('[data-asof]')||{}).textContent||'',ctr,seq:+k.dataset.asofSeq,statements:k.querySelectorAll('[data-statement]').length,stNoPub:[...k.querySelectorAll('[data-statement]')].filter(x=>!/publisher/.test((x.querySelector('.pubn')||{}).textContent||'')).length,stLinks:[...k.querySelectorAll('[data-statement]')].filter(x=>x.querySelectorAll('a[href]').length>0).length,question:(k.querySelector('[data-block=answer] h3')||{}).textContent||'',funnel:[...k.querySelectorAll('[data-funnel]')].map(x=>x.dataset.funnel),growth:!!k.querySelector('svg[data-growth]'),growthNow:(k.querySelector('[data-growth-now]')||{}).textContent||'',yl:!!k.querySelector('[data-yield]'),doc:[d.scrollHeight,innerHeight,d.scrollWidth,innerWidth],kscroll:[k.scrollHeight,k.clientHeight],col:(c=>[c.scrollHeight,c.clientHeight])(document.querySelector('.col')),kbottom:k.getBoundingClientRect().bottom,innerH:innerHeight,panels:[...k.querySelectorAll('.ans,.evp,.rp')].map(p=>({c:p.className,b:p.getBoundingClientRect().bottom}))}}"""
KNEV = r"""()=>{const e=document.querySelector('.evp');if(!e)return null;const rows=[...e.querySelectorAll(e.dataset.evidence==='contested'?'[data-pair]':'[data-edge],[data-capability]')],fr=[...e.querySelectorAll('[data-fragment]')];return {kind:e.dataset.evidence,rows:rows.length,pairs:e.querySelectorAll('[data-pair]').length,frags:fr.length,fragBad:fr.filter(f=>!(f.querySelector('b')||{}).textContent||f.textContent.trim().length<8).length,caps:e.querySelectorAll('[data-capability]').length,head:(e.querySelector('h3')||{}).textContent||'',hasNone:!!e.querySelector('.l.na')}}"""
WHAT = r"""()=>{const d=document.getElementById('kn_whatis');if(!d)return {has:false};const n={};d.querySelectorAll('[data-whatis]').forEach(b=>n[b.dataset.whatis]=b.dataset.n);const r=document.documentElement,k=document.getElementById('kn'),w=d.querySelector('.wib'),kr=k.getBoundingClientRect();let ls=null;try{ls=localStorage.getItem('kr_whatis')}catch(e){}
return {has:true,open:d.open,n,text:d.textContent.length,st:(d.querySelector('[data-whatis-status]')||{}).textContent||'',doc:[r.scrollHeight,innerHeight,r.scrollWidth,innerWidth],ls,wibBottom:w?w.getBoundingClientRect().bottom:0,kBottom:kr.bottom,gates:['G0','G1-G2','G3','G4-G5','G3b'].filter(g=>d.textContent.includes(g)).length}}"""
JS = "const CONNECT=" + CONNECT + ";const KNOWL=" + KNOWL + ";const WHAT=" + WHAT + ";const KNEV=" + KNEV + ";\n" + JS
jf = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, dir=tempfile.gettempdir()); jf.write(JS); jf.close()
env = dict(os.environ, NODE_PATH=NODE_PATH); url = "http://127.0.0.1:%d/mockups/knowledge-raw/index.html?" % a.port + ("" if a.src.startswith("area:") and a.id == VAPE else "id=%s&" % a.id) + ("src=" + urllib.parse.quote(a.src, safe=":") if a.src else "")   # a staged area reads its own first article; the queue default id is not in it
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
chk("Story has 7 steps (Read, Understand, Extract, Connect, Knowledge, World state, Decision), each with a gate tag and a badge", [x["name"] for x in sb] == ["Read", "Understand", "Extract", "Connect", "Knowledge", "World state", "Decision"] and all(x["gate"] and x["badge"] for x in sb), str([(x["name"], x["gate"], x["badge"]) for x in sb]))
badok = True
for x in sb:
    if x["name"] == "Knowledge":
        if x["badge"] not in ("live", "page", "na"): badok = False; print("      Knowledge step shows badge %s" % x["badge"])   # not in status.json (check-alignment.py does not list it): the page derives it from the knowledge.json of the source
        continue
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
print("  --- Knowledge step ---"); KX = X.get("kn"); src_k = a.src or "window"
try: kd = get("raw/knowledge?src=" + urllib.parse.quote(src_k, safe=":"))
except Exception as e: kd = {"exists": False, "why": repr(e)}
if not kd.get("exists"):
    chk("source %s has no knowledge.json: the step shows a block with the reason, no crash" % src_k, bool(KX) and "none" in KX and ("knowledge.json" in KX["none"] or "No consolidated window" in KX["none"]), str(KX)[:160]); print("      reason: %s" % str(kd.get("why"))[:160])
else:
    K = kd["knowledge"]; G = {g["seq"]: g for g in K.get("growth", [])}; Ctr = K["counters"]
    chk("Knowledge step rendered for source %s" % src_k, bool(KX) and "ctr" in KX, str(KX)[:160])
    if KX and "ctr" in KX:
        chk("label 'as of consolidation <time>, N articles, P publishers' equals knowledge.json", ("as of consolidation" in KX["asof"]) and ("%s articles" % K["articles"]) in KX["asof"] and ("%s publishers" % K["publishers"]) in KX["asof"], KX["asof"])
        seq = KX["seq"]; g0 = G.get(seq) or G[max(x for x in G if x <= seq)] if G else {}
        exp = {"new": g0.get("assertions"), "reinforced": g0.get("reinforced"), "contested": g0.get("contested"), "bridging": Ctr["bridging"]["n"]}
        chk("four counters new/reinforced/contested/bridging equal the growth row of this article (seq %s)" % seq, KX["ctr"] == exp, "page %s | knowledge.json %s" % (KX["ctr"], exp))
        final = bool(G) and seq >= max(G); E_ = K["edges"]; ev = X["knEv"]
        if final:
            want = {"new": min(len(Ctr["new"]["evidence"]), 100), "reinforced": min(len(Ctr["reinforced"]["evidence"]), 100), "contested": min(len(K.get("contested", [])), 100), "bridging": len(Ctr["bridging"]["evidence"])}
            chk("final article: each counter opens an evidence list with the rows of knowledge.json", {k: ev[k]["rows"] for k in want} == want, "page %s | want %s" % ({k: ev[k]["rows"] for k in want}, want))
        chk("every opened fragment shows a publisher and its sentence (%d fragments)" % sum(v["frags"] for v in ev.values()), all(v["fragBad"] == 0 for v in ev.values()) and all(ev[k]["frags"] > 0 for k in ("new", "reinforced", "contested") if ev[k]["rows"] > 0), str({k: (v["rows"], v["frags"], v["fragBad"]) for k, v in ev.items()}))
        sts = (K.get("answer") or {}).get("statements") or []; arts = kd["articles"]
        withref = sum(1 for x in sts if any(f["art"] in arts and arts[f["art"]].get("url") for r in x.get("refs", []) for f in E_.get(r, {}).get("fragments", [])))
        chk("answer card: question, every statement with a publisher count and source links (%d statements, %d with links)" % (len(sts), withref), KX["statements"] == len(sts) and KX["stNoPub"] == 0 and KX["stLinks"] == withref and (len(sts) > 0) == bool(KX["question"].strip()), "page %s statements, %s without publisher count, %s with links; question %r" % (KX["statements"], KX["stNoPub"], KX["stLinks"], KX["question"][:60]))
        fk = [k for k in ("observations", "fragments", "assertions", "reinforced", "contested", "capabilities", "bridging", "concepts") if K.get("funnel", {}).get(k) is not None]
        chk("funnel bands, growth line and yield row present", KX["funnel"] == fk and (KX["growth"] or len(G) < 2) and KX["yl"], "bands %s growth %s yield %s" % (KX["funnel"], KX["growth"], KX["yl"]))
        WI = X.get("wi"); F_ = K.get("funnel", {})
        chk("'What is this?' panel exists, closed by default", bool(WI) and WI.get("has") and not WI["open"], str(WI)[:120])
        if WI and WI.get("has"):
            WO = X.get("wiOpen") or {}; fexp = {k: str(F_.get(k)) if F_.get(k) is not None else "\u2013" for k in ("observations", "fragments", "sources", "facts_raw", "assertions", "reinforced", "contested", "capabilities", "bridging")}
            chk("panel opens on click and is remembered (localStorage kr_whatis=1)", WO.get("open") is True and WO.get("ls") == "1", "open %s ls %s" % (WO.get("open"), WO.get("ls")))
            chk("panel numbers equal knowledge.json funnel %s" % fexp, all(WO["n"].get(k) == v for k, v in fexp.items()), "page %s" % {k: WO["n"].get(k) for k in fexp})
            cp = (F_["fragments"] - F_["sources"]) if F_.get("fragments") is not None and F_.get("sources") is not None else None
            chk("panel wire copies = fragments - sources (%s) and answer statements = %d" % (cp, len(sts)), WO["n"].get("copies") == (str(cp) if cp is not None else "\u2013") and WO["n"].get("answer") == str(len(sts)), str({k: WO["n"].get(k) for k in ("copies", "answer")}))
            kr_ = [r for r in sj["rows"] if r.get("group") == "knowledge"]
            chk("panel status line comes from status.json Knowledge rows (%d rows)" % len(kr_), bool(kr_) and all(r["label"] in WO["st"] and r["quality"]["state"] in WO["st"] for r in kr_), WO["st"][:140])
            chk("panel maps all five gate groups (G0, G1-G2, G3, G4-G5, G3b)", WO.get("gates") == 5, str(WO.get("gates")))
            chk("open panel at 1440x900: no page scroll, panel stays inside the Knowledge block", WO["doc"][0] <= WO["doc"][1] + 1 and WO["doc"][2] <= WO["doc"][3] + 1 and WO["wibBottom"] <= WO["kBottom"] + 1, "doc %s panel bottom %.0f block bottom %.0f" % (WO["doc"], WO["wibBottom"], WO["kBottom"]))
        chk("Knowledge fits 1440x900: no page scroll, no clipped block, left column fully visible", KX["doc"][0] <= KX["doc"][1] + 1 and KX["doc"][2] <= KX["doc"][3] + 1 and KX["kscroll"][0] <= KX["kscroll"][1] + 1 and KX["col"][0] <= KX["col"][1] + 1 and KX["kbottom"] <= KX["innerH"] + 1 and all(q["b"] <= KX["innerH"] + 1 for q in KX["panels"]), "doc %s | kn scroll/client %s | left column scroll/client %s | bottom %s of %s" % (KX["doc"], KX["kscroll"], KX["col"], round(KX["kbottom"]), KX["innerH"]))
        print("      counters: %s | %s" % (KX["ctr"], KX["growthNow"]))
        BL = X.get("build")
        if BL:
            ks = [x["k"] for x in BL[1:]]; Gs = sorted(K.get("growth", []), key=lambda g: g["seq"])
            chk("build view: controls act without reloading the chain; +5 / +1 / +10 move data-build-k (%s)" % ks, len(BL) == 5 and BL[1]["k"] == 1 and ks == sorted(ks) and all(ks[i] < ks[i + 1] for i in range(len(ks) - 1)) or (BL[0]["n"] <= 1), str([(x["k"], x["label"]) for x in BL]))
            chk("build view: new / reinforced / contested counters never fall while k grows (k %s)" % ks, all(BL[i]["ctr"][c] <= BL[i + 1]["ctr"][c] for i in range(1, len(BL) - 1) for c in ("new", "reinforced", "contested")), str([x["ctr"] for x in BL]))
            chk("build view: counters at each k equal the growth row of that article", all(x["ctr"]["new"] == Gs[x["k"] - 1]["assertions"] and x["ctr"]["reinforced"] == Gs[x["k"] - 1]["reinforced"] and x["ctr"]["contested"] == Gs[x["k"] - 1]["contested"] for x in BL if 1 <= x["k"] <= len(Gs)), str([(x["k"], x["ctr"]) for x in BL]))
            chk("build view: the added panel lists at least one item at some k, each item tagged data-added-kind (kinds %s)" % sorted({k for x in BL for k in x["kinds"]}), any(x["items"] >= 1 for x in BL) and all(x["from"] <= x["to"] for x in BL), str([(x["k"], x["items"], x["from"], x["to"]) for x in BL]))
            chk("build view: a jump of 5 lists what articles %s to %s added (more than one article)" % (BL[2]["from"], BL[2]["to"]), BL[2]["to"] - BL[2]["from"] >= 1 or BL[0]["n"] <= 1, str(BL[2]))
            chk("build view: 'why' opens the source sentences (detail panel)", bool(X.get("buildWhy")) and X["buildWhy"]["open"] and X["buildWhy"]["rows"] >= 2, str(X.get("buildWhy")))
            chk("build view: back to the article being read restores the old counters", X["buildBack"]["ctr"] == BL[0]["ctr"] and X["buildBack"]["k"] == BL[0]["k"], "%s vs %s" % (X["buildBack"]["ctr"], BL[0]["ctr"]))
            chk("build view: no page scroll while building at 1440x900", all(x["doc"][0] <= x["doc"][1] + 1 for x in BL), str([x["doc"] for x in BL]))
    # ---- Concepts view (2026-11-22): the default view of the Knowledge step ----
    CX = X.get("cv") or {}; F1 = CX.get("first")
    try: cd = get("raw/concepts?src=" + urllib.parse.quote(src_k, safe=":"))
    except Exception as e: cd = {"exists": False, "why": repr(e)}
    chk("view switch: Developments | Concepts | Build | Evidence (all reachable)", bool(F1) and F1["swBtns"] == ["developments", "concepts", "build", "evidence"] and F1["view"] == "concepts", str(F1 and (F1["swBtns"], F1["view"])))
    # ---- Developments view (2026-11-23): the default view of the Knowledge step (needs the bench restarted: /api/raw/developments is new) ----
    DX = X.get("dv") or {}; DV0 = DX.get("first")
    try: dd = get("raw/developments?src=" + urllib.parse.quote(src_k, safe=":"))
    except Exception as e: dd = {"exists": False, "why": repr(e)}
    chk("developments view is the default view of the Knowledge step (Developments first in the switch)", bool(DV0) and DV0["view"] == "developments" and DV0["swBtns"][:1] == ["developments"], str(DV0 and (DV0["view"], DV0["swBtns"])))
    if not dd.get("exists"):
        chk("developments view, no feed for %s: a clear reason block, no crash" % src_k, bool(DV0) and DV0["state"] == "none" and len(DV0["none"]) > 10, str(DV0 and DV0["none"])[:160]); print("      reason: %s" % str(dd.get("why"))[:140])
    else:
        nL, nT = len(dd["developments"]), len(dd["thin"]); mv = dd["counts"]["moved"]
        chk("developments view lists at least 3 rows (feed: %d developments, %d thin)" % (nL, nT), DV0["state"] == "ready" and DV0["count"] == nL and DV0["count"] >= 3 and DV0["thin"] == nT and DV0["rows"] == nL + nT, str(DV0)[:200])
        chk("area strip: '%d articles -> %d developments' and '%d developments moved since your last look' equal the feed" % (dd["window"]["articles"], nL, mv), ("%d articles \u2192 %d development" % (dd["window"]["articles"], nL)) in DV0["strip"] and DV0["moved"] == str(mv) and ("%d development" % mv) in DV0["movedTxt"] and DV0["cut"], DV0["strip"][:120])
        chk("development detail: Since your last look, KNOW, FOLLOW, EXPECT blocks are drawn (%s)" % DV0["secs"], all(x in DV0["secs"] for x in ("since", "know", "follow", "expect")), str(DV0["secs"]))
        DO = DX.get("open"); e0 = dd["developments"][0]["know"][0] if dd["developments"] and dd["developments"][0]["know"] else None
        chk("assertion opens its evidence rows (quote, publisher, owner, day, read depth, article link): %s rows" % (DO and DO["frags"]), bool(DO) and bool(e0) and DO["id"] == e0["id"] and DO["frags"] == len(e0["evidence"]) >= 1, str((DO, e0 and e0["id"])))
        chk("a second development opens its own detail", bool(DX.get("second")) and DX["second"]["shown"] == DX["second"]["id"] or nL + nT < 2, str(DX.get("second")))
        chk("developments view at 1440x900: no page scroll", bool(DV0) and DV0["doc"][0] <= DV0["doc"][1] + 1 and DV0["doc"][2] <= DV0["doc"][3] + 1, str(DV0 and DV0["doc"]))
        # ---- round V (2026-11-24): Across cuts block (changes of each development over the window's cuts, gaps named) ----
        AC = dd.get("across"); AX = DX.get("across")
        chk("across cuts (V): the feed carries 'across' with cuts, steps and gaps, and the page block is drawn", bool(AC) and bool(AX) and AX["cuts"] == len(AC["cuts"]) and AX["steps"] == len(AC["steps"]), str((bool(AC), AX and (AX["cuts"], AX["steps"])))[:200])
        if AC and AX:
            apirows = [(r["id"], r["status"]) for s_ in AC["steps"] for r in s_["rows"]]
            chk("across cuts (V): one row per development per step, equal to the feed (%d rows); every status word is new / kept / merged / split" % len(apirows), sorted((r["id"], r["st"]) for r in AX["rows"]) == sorted(apirows) and all(w in ("new", "kept", "merged", "split") for _, w in apirows), str((len(AX["rows"]), len(apirows)))[:200])
            chk("across cuts (V): every gap in the feed is named on the page (%d gaps), none invented, and a window of < 2 cuts says 'one cut only'" % len(AC["gaps"]), sorted(AX["gapLabels"]) == sorted(g["label"] for g in AC["gaps"]) and (len(AC["cuts"]) >= 2 or any("one cut only" in g["label"] for g in AC["gaps"])), str(AX["gapLabels"])[:200])
            chk("across cuts (V): the page no longer says ids are MISSING stability, and every row title is an article title of the window (quoted, no model text)", AX["noMissing"] and all(r["t"].startswith("\u201c") for r in AX["rows"]), str(AX["noMissing"]))
            chk("across cuts (V): the closed block keeps the developments view at 1440x900 with no page scroll", AX["doc"][0] <= AX["doc"][1] + 1 and AX["doc"][2] <= AX["doc"][3] + 1, str(AX["doc"]))
    if not cd.get("exists"):
        chk("concepts view, no concepts feed for %s: a clear reason block, no crash" % src_k, bool(F1) and F1["state"] == "none" and len(F1["none"]) > 10, str(F1 and F1["none"])[:160]); print("      reason: %s" % str(cd.get("why"))[:140])
    else:
        C_ = cd["concepts"]; CMAP = {c["id"]: c for c in C_}; NMAX = min(40, len(C_)); R_ = {"conflict": 0, "update": 1, "new_link": 2, "new-link": 2, "new_concept": 3, "new-concept": 3}
        chk("concepts view renders (%d concepts in the feed)" % len(C_), F1["state"] == "ready" and F1["focus"] in CMAP, str(F1)[:200])
        chk("focus card (L1): the five slots what it is / direction / drivers / resources / related, each with a fill mark, a state badge and a certainty bar", F1["slots"] == ["what_it_is", "direction", "drivers", "resources", "related"] and F1["fills"] == 5 and F1["badge"] and F1["bar"] and F1["name"] == CMAP[F1["focus"]]["label"], "%s fills %s badge %r name %r want %r" % (F1["slots"], F1["fills"], F1["badge"], F1["name"], CMAP.get(F1["focus"], {}).get("label")))
        chk("street map: nodes drawn = concepts counted in its label (%d of %d, cap 40), links drawn = data-links" % (NMAX, len(C_)), F1["nodes"] == F1["nodesAttr"] == NMAX and F1["mapLabel"].startswith("%d concept" % NMAX) and F1["links"] == F1["linksAttr"] and F1["links"] > 0, "nodes %s attr %s label %r links %s/%s" % (F1["nodes"], F1["nodesAttr"], F1["mapLabel"][:40], F1["links"], F1["linksAttr"]))
        SC = CX.get("scent")
        chk("street map: hovering a link shows why it connects (relation, certainty, owners)", bool(SC) and SC["t"] == SC["w"] and "certainty" in SC["t"] and "owner" in SC["t"], str(SC)[:200])
        chk("street map: clicking a node makes it the focus and the card updates", bool(CX.get("clicked")) and CX["second"]["focus"] == CX["clicked"] != CX["clickedFrom"] and CX["second"]["card"] == CX["clicked"] and CX["second"]["name"] == CMAP[CX["clicked"]]["label"], "from %s clicked %s now %s card %s" % (CX.get("clickedFrom"), CX.get("clicked"), CX.get("second") and CX["second"]["focus"], CX.get("second") and CX["second"]["card"]))
        Gs_ = sorted(K.get("growth", []), key=lambda g: g["seq"]); NG_ = len(Gs_); lo_ = NG_ // 2; loSeq = Gs_[lo_ - 1]["seq"] if NG_ and lo_ >= 1 else -1; hiSeq = Gs_[-1]["seq"] if NG_ else 10 ** 9
        tri_ = [t for t in cd.get("triage", []) if loSeq < t["seq"] <= hiSeq]; kn_ = sum(1 for t in tri_ if t["verdict"] == "known"); it_ = [t for t in tri_ if t["verdict"] in R_]
        rk = [R_.get(v, 9) for v in F1["verdicts"]]
        chk("delta list: items since the mark (half the window) = triage rows of those articles minus known (%d shown, %d known hidden), ranked conflict > update > new link > new concept" % (len(it_), kn_), F1["delta"] == str(len(it_)) and F1["known"] == str(kn_) and str(kn_) in F1["knownTxt"].replace(",", "") and len(F1["verdicts"]) == min(40, len(it_)) and rk == sorted(rk), "page items %s known %s verdict ranks %s | want %d %d" % (F1["delta"], F1["known"], rk[:12], len(it_), kn_))
        D1 = CX.get("deepNow"); D2 = CX.get("deep"); did = CX.get("deepFocus")
        chk("go deep: shows a progress state first (or a cached result), then the L2/L3 panel", bool(D1) and D1["deepPanel"] in ("loading", "ready") and bool(D2) and D2["deepPanel"] == "ready", str((D1 and D1["deepPanel"], D2 and D2["deepPanel"])))
        try: dp_ = get("raw/deep?src=%s&concept=%s" % (urllib.parse.quote(src_k, safe=":"), urllib.parse.quote(did, safe="")))
        except Exception as e: dp_ = {"error": repr(e)}
        want_sec = ["Subconcepts (%d)" % len(dp_.get("subconcepts", [])), "Timeline (%d)" % len(dp_.get("timeline", [])), "Competing accounts (%d)" % len(dp_.get("accounts", [])), "Open questions (%d)" % len(dp_.get("open_questions", [])), "History (%d)" % len(dp_.get("history", []))]
        chk("go deep: the panel lists subconcepts, timeline, competing accounts, open questions, history with the counts of the deep feed, then card fill before -> after", bool(D2) and D2["deepSec"][:5] == want_sec and D2["deepSec"][-1].startswith("Card fill"), "page %s | want %s" % (D2 and D2["deepSec"], want_sec))
        dep_ = int(str(dp_.get("depth", "0"))[-1]) if str(dp_.get("depth", "0"))[-1:].isdigit() else 0
        chk("go deep: the depth ring of the concept updates (card and map node show L%d after, were L%s before)" % (dep_, CX["second"]["cardDepth"]), bool(D2) and D2["cardDepth"] == D2["focusDepth"] == max(dep_, CX["second"]["cardDepth"]) and D2["focusDepth"] >= CX["second"]["focusDepth"], "before card %s node %s | after card %s node %s | deep depth %s" % (CX["second"]["cardDepth"], CX["second"]["focusDepth"], D2 and D2["cardDepth"], D2 and D2["focusDepth"], dp_.get("depth")))
        chk("delta lines offer go deep (%s lines)" % (F1["lineDeep"]), (F1["lineDeep"] == min(40, len(it_)) and CX.get("lineDeep") is not None) or len(it_) == 0, str((F1["lineDeep"], CX.get("lineDeep"))))
        chk("concepts view at 1440x900: no page scroll before and after go deep", all(x and x["doc"][0] <= x["doc"][1] + 1 and x["doc"][2] <= x["doc"][3] + 1 for x in (F1, CX.get("second"), D2)), str([x and x["doc"] for x in (F1, CX.get("second"), D2)]))
    VB, VE, VC = CX.get("v_build"), CX.get("v_evidence"), CX.get("v_concepts")
    chk("Build view keeps the existing timeline (build bar and 'what each article added'); Evidence view keeps counters and evidence lists; Concepts view hides both", bool(VB and VE and VC) and VB["view"] == "build" and VB["bldVisible"] and VB["addedVisible"] and not VB["cvVisible"] and not VB["ctrVisible"] and VE["view"] == "evidence" and VE["ctrVisible"] and VE["evpVisible"] and VE["ansVisible"] and not VE["cvVisible"] and VC["view"] == "concepts" and VC["cvVisible"] and not VC["ctrVisible"], str(((VB and (VB["view"], VB["bldVisible"], VB["addedVisible"], VB["cvVisible"])), (VE and (VE["ctrVisible"], VE["evpVisible"], VE["cvVisible"])))))
    chk("Build and Evidence views fit 1440x900 with no page scroll", all(x and x["doc"][0] <= x["doc"][1] + 1 for x in (VB, VE)), str([x and x["doc"] for x in (VB, VE)]))
    GR = X.get("grow") or []
    if GR:
        okk = all(g and "ctr" in g for g in GR); sq = [g["seq"] for g in GR] if okk else []
        chk("staged area: stepping through %d articles grows the counters (seq %s)" % (len(GR), sq), okk and sq == sorted(set(sq)) and len(sq) > 1 and all(GR[i]["ctr"][c] <= GR[i + 1]["ctr"][c] for i in range(len(GR) - 1) for c in ("new", "reinforced", "contested")) and GR[-1]["ctr"]["new"] > GR[0]["ctr"]["new"], str([g["ctr"] for g in GR]) if okk else str(GR)[:200])
        chk("growth counters equal knowledge.json growth rows at each of those articles", okk and all(g["ctr"]["new"] == G[g["seq"]]["assertions"] and g["ctr"]["reinforced"] == G[g["seq"]]["reinforced"] and g["ctr"]["contested"] == G[g["seq"]]["contested"] for g in GR if g["seq"] in G), "")
over = [s for s in res["scroll"] if s["doc"][0] > s["doc"][1] + 1 or s["doc"][2] > s["doc"][3] + 1]
print("  page scroll at 1300x900: %s" % ("NONE" if not over else "; ".join("%s %s" % (s["label"], s["doc"]) for s in over))); bad += len(over)
print("  console/page errors: %s" % ("none" if not res["errs"] else "; ".join(res["errs"][:5]))); bad += len(res["errs"])
print("RESULT:", "PASS" if not bad else "FAIL (%d problems)" % bad); srv.shutdown(); sys.exit(1 if bad else 0)
