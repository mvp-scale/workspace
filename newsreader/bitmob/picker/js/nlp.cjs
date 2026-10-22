// usage: node nlp.cjs in.jsonl out.jsonl  (rows {id,state_text}); emits lemmas + counts
const fs=require('fs');const nlp=require('compromise');const wink=require('wink-nlp');const model=require('wink-eng-lite-web-model');
const w=wink(model);const its=w.its;
const rows=fs.readFileSync(process.argv[2],'utf8').split('\n').filter(Boolean).map(JSON.parse);
const out=fs.createWriteStream(process.argv[3]);
for(const r of rows){const t=(r.state_text||'').slice(0,6000);
 const d=w.readDoc(t);
 const lem=d.tokens().filter(x=>x.out(its.type)==='word').out(its.lemma).map(s=>s.toLowerCase());
 const ents=d.entities().out(its.type);const cnt={};for(const e of ents)cnt[e]=(cnt[e]||0)+1;
 const c=nlp(t);
 out.write(JSON.stringify({id:r.id,lem,ents:cnt,nsent:d.sentences().length(),
  n_num:c.numbers().length,n_pct:c.match('#Value (percent|%)').length+ (t.match(/\d\s?%/g)||[]).length,n_money:c.money().length,
  n_verbs:c.verbs().length,n_past:c.verbs().if('#PastTense').length,n_people:c.people().length,n_places:c.places().length,n_orgs:c.organizations().length})+'\n');}
out.end();
