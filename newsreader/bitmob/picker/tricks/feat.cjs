// usage: node feat.cjs in.jsonl out.jsonl ; compromise lemma-pattern + wink sentiment/negation features
const fs=require('fs');const path=require('path');
const R=require('module').createRequire(path.join(__dirname,'../js/x.cjs'));const nlp=R('compromise');
const wink=R('wink-nlp');const model=R('wink-eng-lite-web-model');
const w=wink(model);const its=w.its;
const UP='{rise}|{rose}|{surge}|{soar}|{jump}|{climb}|{increase}|{grow}|{double}|{spike}|{hike}|{raise}|{gain}';
const DN='{fall}|{drop}|{plunge}|{slump}|{decline}|{decrease}|{cut}|{slash}|{reduce}|{shrink}|{lose}|{tumble}|{sink}';
const SC='(shortage|scarcity|crisis|deficit|strain|squeeze|backlog|disruption|outage|ban|shock)';
const pats={up_val:`(${UP}) * #Value`,dn_val:`(${DN}) * #Value`,up_pct:`(${UP}) * (percent|%)`,dn_pct:`(${DN}) * (percent|%)`,
 val_pct_chg:`#Value (percent|%) (${UP}|${DN})`,scar:SC,rec:'record (high|low|level)',neg_chg:`(not|no|n't|without) (${UP}|${DN})`,
 amt_chg:`(${UP}|${DN}) (by|to|from|of) #Value`};
const rows=fs.readFileSync(process.argv[2],'utf8').split('\n').filter(Boolean).map(JSON.parse);
const out=fs.createWriteStream(process.argv[3]);
for(const r of rows){const t=(r.state_text||'').slice(0,6000);const c=nlp(t);const f={id:r.id};
 for(const [k,p] of Object.entries(pats)){try{f[k]=c.match(p).length}catch(e){f[k]=0}}
 // sentence level: share of sentences having a change word AND a number
 let sc=0,ns=0;c.sentences().forEach(s=>{ns++;if(s.has('('+UP+'|'+DN+'|'+SC+')')&&s.has('#Value'))sc++});f.sent_chg_num=sc;f.sent_frac=ns?sc/ns:0;
 f.vneg=c.verbs().isNegative().length;f.nverbs=c.verbs().length;f.fut=c.verbs().if('#FutureTense').length;f.past=c.verbs().if('#PastTense').length;
 const d=w.readDoc(t);let neg=0,sent=[];d.sentences().each(s=>{sent.push(s.out(its.sentiment));});
 d.tokens().each(x=>{if(x.out(its.negationFlag))neg++});
 f.neg_tok=neg;f.sent_mean=sent.length?sent.reduce((a,b)=>a+b,0)/sent.length:0;f.sent_min=sent.length?Math.min(...sent):0;f.sent_max=sent.length?Math.max(...sent):0;
 out.write(JSON.stringify(f)+'\n');}
out.end();
