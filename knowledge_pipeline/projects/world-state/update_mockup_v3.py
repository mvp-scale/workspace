import json, pathlib
p = pathlib.Path("flow_mockup_template_v2.html"); s = p.read_text(encoding="utf-8")
if "STUDENT_BLOCK" in s: raise SystemExit("already applied")
r4 = json.load(open("runs/snapshots/loop4_results.json")); r5 = json.load(open("runs/snapshots/loop5_results.json")); r6 = json.load(open("runs/snapshots/loop6_results.json"))
# 7 step cards
s = s.replace("grid-template-columns:repeat(6,1fr);gap:26px", "grid-template-columns:repeat(7,1fr);gap:24px")
new_step = '''{t:"Small CPU student",s:"partial",why:"Read the item for real: topic, story type, condition present.",big:"0.5 ms",cap:"per item, one thread; words + character n-grams",in:"Headline + description.",does:"Sparse word and character n-grams into a linear model; static embedding added for topic.",learned:"Story type is at teacher level. Topic and condition present are below it. Structure flags helped nothing inside this model."},'''
s = s.replace('{t:"Route by disagreement"', new_step + '{t:"Route by disagreement"', 1)
s = s.replace('{t:"Snapshot and learn",s:"notbuilt",why:"Prove the knowledge keeps getting better.",big:"—",cap:"nothing built, nothing shown",in:"Each new batch.",does:"Freeze versions; score the next batch before adding it.",learned:"Needs a second batch. Answers \'is it continuously improving?\'"}',
 '{t:"Snapshot and learn",s:"partial",why:"Prove the knowledge keeps getting better.",big:"+0.028",cap:"score gain from 5,000 to 20,000 items (v1 to v4)",in:"Each new batch, in date order.",does:"Train on earlier batches, score the next unseen one, save a snapshot.",learned:"It improves, slowly, and flattens. Rollback and the second-batch rule are not automated yet."}')
s = s.replace("Under 1 ms an item, so it can sit in front of everything.", "Fast enough to sit in front of everything.")
# student panel
panel = '''<h2>STUDENT_BLOCK Where the student stands now</h2>
<p class="sub">Agreement with Sonnet on later items the model never saw. The red line is how well the two teachers agree with each other. Agreement, not accuracy.</p>
<div class="grid2"><div class="card"><h3>Full coverage</h3><div id="b4"></div></div><div class="card"><h3>Share of items it can answer while staying at 80% agreement</h3><div id="b5"></div><p class="mut" style="font-size:12px">Topic uses the best student (words + embeddings). Single answer vs top-two choices.</p></div></div>
'''
s = s.replace("<h2>The hard part", panel + "<h2>The hard part", 1)
t1 = r6["top1"]; t2 = r6["top2"]
js = f'''bars("b4",[["Story type",{r4["outputs"]["story_type"]["full_agreement"]},"0.913",0.923],["Topic",{r5["tfidf_plus_embeddings"]["vs_sonnet_voted"]},"{r5["tfidf_plus_embeddings"]["vs_sonnet_voted"]}",{r5["teachers_agree_voted"]}],["Condition present",{r4["outputs"]["presence"]["full_agreement"]},"{r4["outputs"]["presence"]["full_agreement"]}",{r4["outputs"]["presence"]["teachers_agree"]}]],0.5,1.0);
bars("b5",[["Story type",{r4["outputs"]["story_type"]["share_at_80"]},"{round(r4["outputs"]["story_type"]["share_at_80"]*100)}%"],["Topic, one answer",{t1["share_at_80"]},"{round(t1["share_at_80"]*100)}%"],["Topic, top two",{t2["share_at_80"]},"{round(t2["share_at_80"]*100)}%"],["Condition present",{r4["outputs"]["presence"]["share_at_80"]},"{round(r4["outputs"]["presence"]["share_at_80"]*100)}%"]],0,1);
'''
s = s.replace("// walkthrough", js + "// walkthrough", 1)
s = s.replace("rows.forEach(r=>{const d=el(\"div\",\"row\");", "rows.forEach(r=>{const kp=(r[3]!==undefined)?r[3]:keep;const d=el(\"div\",\"row\");", 1)
s = s.replace("if(keep!==undefined){const k=el(\"div\",\"mark\");k.style.left=Math.round((keep-lo)/(hi-lo)*100)+\"%\";t.append(k)}", "if(kp!==undefined){const k=el(\"div\",\"mark\");k.style.left=Math.round((kp-lo)/(hi-lo)*100)+\"%\";t.append(k)}", 1)
# tools rows
s = s.replace('["4 Triage","model2vec potion-base-8M + scikit-learn","A static embedding feeds a logistic regression that guesses \'names a condition\'"', '["4 Triage and student","scikit-learn TF-IDF (words 1-2, characters 3-5) + logistic regression; model2vec potion-base-8M for topic","Sparse n-grams are the student; the static embedding adds meaning for topic only"')
s = s.replace("STUDENT_BLOCK ", "")
s = s.replace("<h2>Where the student stands now</h2>", "<!--STUDENT_BLOCK--><h2>Where the student stands now</h2>")
p.write_text(s, encoding="utf-8"); print("applied")
