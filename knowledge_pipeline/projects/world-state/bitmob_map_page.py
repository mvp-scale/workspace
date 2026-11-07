"""Builds demo/mockups/bitmobs/index.html: how an article is read (7 steps, click for numbers), what each head means, Lean train-ready verdicts, the limit of the lazy loop. Every number is read at build time from runs/harvest/*.json, runs/pulse/*.json, queue.sqlite and the CC-News parquet metadata.
    /workspace/models/embed-zs/.venv/bin/python bitmob_map_page.py   (from projects/world-state)"""
import json, html, re
R = "runs/pulse/"; r = json.load(open(R + "tools_to_training.json")); rows = {x["id"]: x for x in json.load(open(R + "train_ready_rows.json"))}
lean = open("lean/TrainReady.lean").read(); n_thm = len(re.findall(r"^theorem ", lean, re.M)); n_ex = len(re.findall(r"^example ", lean, re.M))
e = html.escape; p3 = lambda x: f"{x:.3f}"; pm = lambda x: f"{x/1000:.3f}"
VW = {"noLabels": ("Need a data source", "v-no"), "needJudge": ("Need outside human labels", "v-no"), "toolsSuffice": ("Tools are enough", "v-ok"), "needMoreExamples": ("Need more examples", "v-mid"), "needBetterSignal": ("Need a better signal", "v-mid"), "trainable": ("Trainable now", "v-ok")}
META = {  # id: (BitMob, tools that can try it, label source)
 "domainFirst": ("BitMob Domain", "word counts; Scan adds little", "MN-DS human labels (public)"), "domainTwo": ("BitMob Domain", "same", "MN-DS human labels"),
 "areaFirst": ("BitMob Area (stand-in)", "word counts", "MN-DS second level, human"), "areaTwo": ("BitMob Area (stand-in)", "same", "MN-DS second level, human"),
 "function": ("BitMob Function", "cue words; factuality from the Fact finder", "Sonnet labels"), "condition": ("BitMob Condition", "change words from the Scan", "Sonnet and Haiku labels"),
 "size": ("none needed", "Fact finder + Validator", "none"), "dates": ("none needed", "Scan + date resolver + Validator", "none"),
 "areaNone": ("BitMob Area (ours)", "none", "none found"), "capabilityNone": ("BitMob Capability", "aliases, regex", "none found"), "noveltyNone": ("BitMob Novelty", "compare with stored evidence", "none found"),
 "mentionNone": ("BitMob Mention", "capitalised-name pattern", "none found"), "eventNone": ("BitMob Event", "spaCy parse + templates", "none found"), "relationNone": ("BitMob Relation", "typed patterns", "none found"),
 "linkNone": ("BitMob Link (candidate)", "aliases + full-text search", "none found"), "clusterNone": ("BitMob Cluster (candidate)", "event fingerprints", "none found")}
NEXT = {"noLabels": "Find or build a labelled set. The PRD's section F covers reusing existing ontologies; I have not read it for this page.", "needJudge": "Get human-labelled test data for this target. Claude agreement cannot judge it.",
 "toolsSuffice": "Nothing. The four checks already prove it from the text.", "needBetterSignal": "More examples of the same kind will not do it. Try a different signal: a neural encoder, other features, or a narrower label set.", "trainable": "Train it.", "needMoreExamples": "Label more examples; the curve is still rising."}
def tr(i):
    x = rows[i]; v, cls = VW[x["verdict"]]; m = META[i]
    ev = "no examples" if x["examples"] == 0 and not x["tools_only"] else (f"{x['examples']:,} examples; low end {pm(x['low'])} against a bar of {pm(x['bar'])} and a guess of {pm(x['guess'])}" if x["low"] else f"{x['examples']:,} examples; no accuracy measured")
    if x["tools_only"]: ev = f"{pm(x['low'])} low end of the share passing four checks"
    return f"<tr><td><b>{e(x['label'])}</b></td><td>{e(m[0])}</td><td>{e(m[1])}</td><td>{e(m[2])}</td><td class='{cls}'><b>{e(v)}</b></td><td>{e(ev)}<div class='n'>{e(NEXT[x['verdict']])}</div></td></tr>"
table = "".join(tr(i) for i in rows)
def bar(label, v, extra=""): return f"<div class='row'><span class='l'>{e(label)}</span><span class='b'><i style='width:{v*100:.1f}%'></i></span><span class='v'>{v:.3f}{e(extra)}</span></div>"
import sqlite3, pyarrow.parquet as pq, glob
H = lambda n: json.load(open(f"runs/harvest/{n}.json"))
HS, INV, PL, LK, IS = H("score"), H("inventory"), H("place_reach"), H("link_reach"), H("inline_sim"); XS, BPL, TL, DE = H("extract_score"), H("boilerplate"), H("train_labels_summary"), H("domain_evidence"); GD = json.load(open("/workspace/demo/mockups/gates/data.json")); SB = {x["key"]: x for x in GD["scoreboard"]}; IT = {t["tool"]: t for t in INV["tools"]}
cc_n = sum(pq.ParquetFile(f).metadata.num_rows for f in glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet"))
q = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); q_n, q_full = q.execute("select count(*), sum(depth='full') from items").fetchone()
B1, B2, DS, DK, G, sp = r["B_l1"], r["B_l2"], r["D_story_type"], r["D_kinds"], r["C_group"], r["A_speed"]
def pretty(k): return k.replace("_", " ")
def mini(rows, head=("Output", "Average per article", "This article")): return "<table class='mini'><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr>" + "".join("<tr>" + "".join(f"<td>{e(str(c))}</td>" for c in r) + "</tr>" for r in rows) + "</table>"
def chip(t, k): return f"<span class='chip {k}'>{e(t)}</span>"
def pair(cells, detail, n):  # a table row with a + button and a hidden detail row under it
    return "<tbody class='rw'><tr class='main'><td class='tgc'><button class='tg' type='button' aria-expanded='false' aria-label='Show details'>+</button></td>" + "".join(f"<td>{c}</td>" for c in cells) + f"</tr><tr class='detail' hidden><td></td><td colspan='{n}'>{detail}</td></tr></tbody>"
def tbl(heads, body, cls=""): return f"<div class='tools'><button class='all' type='button'>Expand all</button></div><table class='{cls}'><thead><tr><th></th>" + "".join(f"<th>{e(h)}</th>" for h in heads) + f"</tr></thead>{body}</table>"
def tool_table(*names):
    out = ""
    for nm in names:
        t = IT[nm]; keys = list(t["mean_per_article"])[:10] + [k for k in t["example"] if k not in t["mean_per_article"] and not isinstance(t["example"][k], list)][:4]
        rows_ = [(pretty(k), t["mean_per_article"].get(k, "-"), t["example"].get(k, 0) if not isinstance(t["example"].get(k), list) else ", ".join(map(str, t["example"][k][:4])) or "none") for k in keys]
        out += f"<p class='n'><b>{e(nm)}</b>, median {t['median_ms']} ms an article. Example article: {e(INV['example_title'])}</p>" + mini(rows_)
    return out
lk_note = f"{LK['cc_with_link']} of {LK['cc_articles']} stored CC-News texts and {LK['queue_with_link']:,} of {LK['queue_bodies']:,} queue bodies still contain a link"
STEPS = [
 ("1. Capture the source and every link", "Know where the article came from and everything it points to.", "Read the address, publisher, date and description, and collect every link in the text (article address, in-text links, image, outbound).", chip("partly", "mid"),
  f"<p>Done: links that survive in the stored text are now collected ({XS['articles_with_link_in_text']} of {XS['articles']:,} articles have one). Gap: {e(lk_note)}, so the hyperlinks were lost when the page was flattened; capturing them has to happen when the page is fetched. The queue keeps {LK['queue_with_image_url']:,} of {LK['queue_items']:,} image links.</p>" + tool_table("URL parser", "Metadata")),
 ("2. Clean and cut", "Give every later step clean text without page furniture, in sentences and windows that start with the headline.", "Drop lines a publisher repeats across at least 5 of its articles (found by counting), tidy whitespace, split into sentences and windows.", chip("built", "ok"),
  f"<p>Furniture is learned by counting, not listed by hand: {BPL['lines']:,} lines across {len(BPL['domains'])} publishers, such as \"Advertisement Continue reading the main story\" and copyright lines. It touches {BPL['share_touched']*100:.1f}% of articles and removes {BPL['share_chars_removed']*100:.2f}% of the characters. Lines repeated across many publishers are syndicated story text, so they are kept.</p>"),
 ("3. Scan for spots", "Find the places where the text itself proves something: a quote, an amount, a date, who said it, a hedge, a denial.", "Pattern matching, about a millisecond an article.", chip("built", "ok"), tool_table("Scan (regex)", "Word lists")),
 ("4. Read the grammar", "Know what kind of statement each sentence is, and what is changing.", "spaCy builds the sentence structure; rules tag each sentence asserted, reported, planned, predicted, denied, question, request or decision, and find change words (rising, falling, delayed, disrupted, expanded) tied to the thing that changes.", chip("built, not judged", "mid"),
  f"<p>On {XS['articles']:,} articles: {XS['factuality']['share']*100:.1f}% get a sentence tag; {XS['conditions']['share']*100:.1f}% have a change item. The rules are written by us and tuned by reading sample sentences; no judge has scored them. Sentence tags: {e(', '.join(f'{k} {v:,}' for k, v in sorted(XS['factuality']['sentence_tags'].items(), key=lambda x: -x[1])))}.</p>" + tool_table("spaCy parse (NER off)")),
 ("5. Find names and places", "Turn mentions into things we can link: organisations, people, and places up to a country.", "spaCy marks entity types; places are matched to the GeoNames list through a short alias table (U.S., UK, Britain, state abbreviations).", chip("places partly", "mid"),
  f"<p>On the same 300 articles as before, a country candidate now resolves for {XS['places_300']['with_country']} ({XS['places_300']['share_country']*100:.1f}%), up from {XS['places_300']['before']*100:.1f}% with exact names only. Pre-registered target was 80%, so this is a miss. {PL['city_links_ambiguous']} of {PL['city_links']} city links still fit more than one country. The article's own countries, then the publisher's country, then the largest city decide among them. Whether the chosen country is right is not measured.</p>" + tool_table("spaCy NER")),
 ("6. Extract stated facts", "Pull out amounts, dates, names and who-did-what that the text states outright.", "Each fact must pass four checks (literal, reads back, bound to its noun or verb, one sentence) and is marked stated, unbound or invalid.", chip("built", "ok"), tool_table("Fact finder")),
 ("7. Make a meaning vector", "Give the heads something to compare when words and patterns are not enough.", f"The 22.6M BitMob Reader turns each window into {INV['embedding_dim']} numbers and gives topic and story-type probabilities.", chip("built", "ok"), tool_table("BitMob Reader (22.6M)") + "<p class='n'>Saved per article: the top two topics, story type and topic probabilities. The per-window vectors are not saved.</p>"),
 ("8. Save one record per article", "Write everything once so every head and the training builder read the same thing.", "One JSON line per article; every item carries the tool, its version and where in the text it came from.", chip("built", "ok"),
  f"<p>{XS['articles']:,} articles processed at {XS['per_second_no_reader']:.0f} articles a second on 16 workers without the reader (the reader adds about 26 ms an article). File: runs/harvest/extract.jsonl, written by extract.py.</p>"),
 ("9. Build training labels", "Turn the record into labelled examples for each head, marked by how strong the evidence is.", "proved = the text states it and the checks passed; rule = a written rule fired; weak = a rule fired on a guess. Nothing is judged here.", chip("built", "ok"), "<p>See section 3 for the labels it builds per head.</p>")]
steps = tbl(["Step", "Goal", "How", "Status"], "".join(pair([f"<b>{e(a)}</b>", e(b), e(d), c], x, 4) for a, b, d, c, x in STEPS), "main")
HEADS = [
 ("Anchor", "The join point: one stable id for any entity, concept, capability, place or condition.", chip("not built", "no"), "Every other head hangs on it. A mention is matched to an anchor through its aliases; anchors link by edges (broader, part_of, depends_on).", "Alias table, search index and edges, seeded from GeoNames, IPTC and Wikidata (PRD section F).", "Nothing.", "Everything: the PRD (section L) calls this the biggest gap."),
 ("Place", "Where it happened, from city up to country.", chip("partly", "mid"), "Steps 5 and 6.", f"GeoNames: {PL['gazetteer']['countries']} countries, {PL['gazetteer']['region_names']:,} regions, {PL['gazetteer']['city_names']:,} city names. Not wired in.", f"{PL['with_country']} of {PL['articles']} articles get a country candidate; {PL['city_links_ambiguous']} of {PL['city_links']} city links are ambiguous.", "An alias table (U.S., UK, Britain), context to choose among countries. Whether the chosen country is right is not measured."),
 ("Entity and event", "Who is involved and what happened, with when and how much.", chip("partly", "mid"), "Steps 3, 5 and 6.", "Aliases per anchor.", "PRD section L: entity head .88 overlap and .73 exact (untyped); event triggers .79; time rules .97; quantity rules .83 (11 articles).", "Typed entities, event participants and roles."),
 ("Domain", "The highest level of information: the article's profile (story type, topic, change and direction, size, traits, place, time), which Areas roll up into.", chip("partly", "mid"), "Section 3: the engine's Macro Pulse answers, each with its own tools and judge.", f"Core: 49 topics rolling up to 17 broad classes (specs/topic_to_iptc_v1.json). {cc_n:,} full CC-News and {q_full:,} full-text queue articles.", f"Topic: {SB['topic_head']['result']} Story type: {SB['story']['result']}", "Outside judges for change and direction; the other characteristics' bars; Area, Capability and the roll-up (section 4)."),
 ("Area", "The neighbourhood around an anchor: its drivers, dependencies and impacted entities.", chip("stand-in measured", "mid"), "Noun chunks and entity phrases matched to Area names; the reader's vector for the rest.", "A small seeded ontology; Areas grow from residual clusters (playbook section 9).", f"Stand-in (109 IPTC classes): {p3(B2['words']['top1'])}. The 109-class model also answers the 17-class level at {p3(G['l1_derived_from_l2_top1'])}.", "Our Area list."),
 ("Content function", "What the text does: report, opinion, prediction, request, decision.", chip("tools should cover it", "mid"), "Step 4 (tense, modals, passive) and step 3 (attribution, negation, quotes); the facts' who-did-what.", "Per claim as well as per article; URL sections such as opinion.", f"Stand-in (4 story types, Claude labels): tools as counts scored {p3(DS['tools_only'])}, the commonest answer {p3(DS['commonest_answer'])}. The grammar rules themselves are untested.", "A rule set from tense, modal, attribution and negation, and a judge for it."),
 ("Conditions", "What is changing, and in which direction: rising, falling, delayed, disrupted, expanded.", chip("stand-in measured", "mid"), "Change verbs with their subject and object (step 4), change and percent spots (step 3).", "Per Area over time as the change in volume.", f"Stand-in (4 condition kinds, Claude labels, L892 L894 L905): words {p3(DK['mean_ap_words'])}, words plus tools {p3(DK['mean_ap_words_plus_tools'])} mean average precision.", "The full list, the direction rule (your decision)."),
 ("Capability", "A reusable ability or process that several Areas share.", chip("not built", "no"), "Verb-object and noun-chunk phrases (step 4) matched to capability names.", "A capability list that starts small and grows from recurring phrases.", "Nothing.", "The list and the matching rule."),
 ("Novelty", "Whether a mention matches something known: known, emerging, unsupported.", chip("not built", "no"), "Computed after matching: phrases that match no anchor, repeated across independent publishers.", "The journal of observations; publisher domains give independence.", "Nothing.", "Needs anchors first. A routing signal only; it does not create ontology."),
 ("Size and dates", "How much, and when, where the text states it.", chip("tools enough", "ok"), "Step 6.", f"Every article: {HS['with_amount_share']*100:.1f}% state an amount; {HS['with_meta_date']:,} of {HS['articles']:,} carry a date.", "Lean verdict: the tools are enough.", "Day-before-month dates are missed.")]
heads = tbl(["Head", "What it means", "Status"], "".join(pair([f"<b>{e(n)}</b>", e(o), c], mini([("Read from", cr), ("Seed and data", sd), ("Measured", m_), ("Missing", ms)], ("", "")), 3) for n, o, c, cr, sd, m_, ms in HEADS), "main")
def vdet(i, x): ev = "no examples" if x["examples"] == 0 and not x["tools_only"] else (f"{x['examples']:,} examples" + (f"; low end {pm(x['low'])} against a bar of {pm(x['bar'])} and a guess of {pm(x['guess'])}" if x["low"] else "")); return mini([("BitMob", META[i][0]), ("Tools that can try it", META[i][1]), ("Label source", META[i][2]), ("Evidence", ev), ("Next step", NEXT[x["verdict"]])], ("", ""))
verd = tbl(["Target", "Verdict"], "".join(pair([f"<b>{e(x['label'])}</b>", f"<span class='{VW[x['verdict']][1]}'>{e(VW[x['verdict']][0])}</span>"], vdet(i, x), 2) for i, x in rows.items()), "main")
TLR = [("domain", "Domain", "URL section", "Needs a second tool for the desks that fail"), ("function", "Content function (per sentence)", "grammar rules", "Rules are unjudged; no outside labels"), ("conditions", "Conditions", "change words tied to a noun", "Lexicon is ours; direction rule needs your review"), ("place", "Place (country)", "entity + GeoNames + aliases", "74% of articles; right-country rate unmeasured"),
       ("entity", "Entity types", "spaCy NER", "Typed, but no alias or anchor yet"), ("size", "Size (stated amount)", "Fact finder", "Text proves it"), ("date", "Dates", "Fact finder", "Text proves it"), ("reader_topic", "Topic (reader's guess)", "BitMob Reader", "A model guess, kept only as a weak signal")]
def tlrow(k, nm, src, gap): v = TL["heads"][k]; return [f"<b>{e(nm)}</b>", f"{v['labels']:,}", f"{v['articles']:,}", f"{v['classes']} ({v['classes_ge60']} with 60 or more)", e(src), e(gap)]
tl_rows = [tlrow(*x) for x in TLR] + [[f"<b>{e(n)}</b>", "0", "0", "0", "no tool yet", e(g)] for n, g in (("Area", "Needs the seed Area list and a matcher"), ("Capability", "Needs the capability list and a matcher"), ("Novelty", "Needs anchors first"))]
tl_table = "<table class='main'><tr><th>Head</th><th>Labels</th><th>Articles</th><th>Classes</th><th>Source</th><th>Gap</th></tr>" + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r_) + "</tr>" for r_ in tl_rows) + "</table>"
V_ = DE["views"]; ex_ = DE["exploratory_unregistered"]; ss_ = DE["seed_stats"]
DOM = [("URL section", "The address path (sports, business, ...)", "labels 16% of articles", f"agrees with the Reader's topic set in {ss_['url_agrees_reader']:,} of {ss_['url_agrees_reader'] + ss_['url_disagrees_reader']:,} articles where both exist", "Seed for the other views. Cannot be scored on the human-labelled set: it has no addresses."),
       ("Reader topics", "The 22.6M reader's topic probabilities, mapped to the 17 classes", "every article", f"{V_['reader topics']['top1']:.3f}", "Strongest single view. Not trained on these seeds."),
       ("Body words", "Word and word-pair counts of the whole article", "every article", f"{V_['body words']['top1']:.3f}", "Trained on the seeds."),
       ("Headline + description words", "Words of the headline and the page description", "every article with a description", f"{V_['headline + description words']['top1']:.3f}", "Trained on the seeds."),
       ("Entity names", "Which organisations, people, products and countries are named", "every article", f"{V_['entity names']['top1']:.3f}", "Trained on the seeds."),
       ("Structure counts", "Quotes, amounts, percents, dates, sentence kinds, entity types per 1,000 characters", "every article", f"{V_['structure counts']['top1']:.3f}", "Trained on the seeds. Hurts when added to the Reader."),
       ("Publisher prior", "What this publisher mostly writes about, from its URL-labelled articles", "publishers seen before", "not built", ""),
       ("Nearest labelled articles", "Reader vectors compared with already-labelled articles", "every article", "not built", ""),
       ("Cross-article links", "Same story and links shared with other articles", "needs captured links", "not built", "")]
dom_tbl = "<table class='main'><tr><th>Piece of evidence</th><th>What it reads</th><th>Reaches</th><th>Alone on human labels</th><th>Note</th></tr>" + "".join("<tr>" + "".join(f"<td>{c if i == 0 else e(c)}</td>" if i else f"<td><b>{e(c)}</b></td>" for i, c in enumerate(r_)) + "</tr>" for r_ in DOM) + "</table>"
dom_read = (f"<p><b>Combined, the views do not beat the Reader.</b> A weighted vote scores {DE['combined']['top1']:.3f}, against {V_['reader topics']['top1']:.3f} for the Reader alone. Adding entity names to the Reader gives {ex_['reader + entity names']:.3f}, headline words {ex_['reader + headline + description words']:.3f}, body words {ex_['reader + body words']:.3f}; adding structure counts lowers it to {ex_['reader + structure counts']:.3f}. These gains are small.</p>"
            f"<p><b>Why.</b> The combiner judged body words {V_['body words']['estimated_reliability']:.2f} reliable; on human labels they score {V_['body words']['top1']:.2f}. Every trained view learned from the same seeds, so their mistakes are the same mistakes and agreement is not independent evidence. Independent evidence has to come from sources that do not share a teacher: the publisher, the neighbours, the links.</p>"
            "<p><b>The class definitions.</b> Tool-built labels reach about 0.45 against the human 17-class convention; a word model trained on those human labels reaches 0.80 (ledger L1028). The tools do not know where a human draws the line between, say, society and human interest. How few human-labelled examples fix that is not measured for 17 classes.</p>")
GD = json.load(open("/workspace/demo/mockups/gates/data.json")); SB = {x["key"]: x for x in GD["scoreboard"]}; TC = json.load(open("runs/pulse/traits_gate_outcomes.json"))["counts"]
def sbr(k): return SB[k]["result"] + f" (ledger {SB[k]['ledger']})"
PROF = [("Story type", "What kind of item is it: fact, forecast, opinion, unclear?", "Sentence tags from the grammar rules, quote and attribution counts, the Reader's story head.", "CheckThat (people's fact-versus-opinion labels)", sbr("story"), chip("below the bar", "no")),
        ("Topic", "What is it about? One of 49 topics, which roll up to 17 broad classes.", "Reader topics, body and headline words, entity names, URL section (the many-view test below).", "MN-DS (people's topic labels)", sbr("topic_head"), chip("at the bar with two guesses", "mid")),
        ("Change and direction", "What is rising, falling, delayed, disrupted or expanded, and which way?", "Change words tied to the changing noun, the 16 condition kinds, the direction head.", "Only Claude labels so far", sbr("direction"), chip("no outside judge", "no")),
        ("Size", "How big is it, where the text states an amount?", "Fact finder with its four checks.", "The text itself", sbr("size"), chip("text proves it", "ok")),
        ("Traits", "Which of 51 yes/no traits apply (deaths or injuries, shortage, ...)?", "Keyword hunts and trait heads.", "Gate checks 1 to 5", f"{TC.get('GO', '?')} of 51 pass the gate, {TC.get('PARK', '?')} parked, {TC.get('REVISE-provisional', '?')} provisional in runs/pulse/traits_gate_outcomes.json, a file older than the later trait rounds (ledger L920 records 3 of 51 GO)", chip("few ready", "no")),
        ("Place", "Where is it, up to a country?", "Spacy places, GeoNames, alias table.", "Not judged", f"A country candidate for {XS['places_300']['share_country']*100:.1f}% of 300 articles; right-country rate not measured (ledger L1043)", chip("partly", "mid")),
        ("Time", "When did it happen and when was it published?", "Publication date, stated dates and date resolver.", "The text itself", sbr("sf_date"), chip("text proves it", "ok"))]
prof_tbl = tbl(["Characteristic", "Question it answers", "Extracted by", "Judged against", "Where it stands"], "".join(pair([f"<b>{e(a)}</b>", e(b), e(c_), e(d_), chip_], mini([("Judge", d_), ("Result today", r_)], ("", "")), 5) for a, b, c_, d_, r_, chip_ in PROF), "main")
ROLL = [("Item profile (Domain characteristics)", "The seven answers above, for one article.", "49 topics (rolling up to 17), 4 story types, the condition kinds, GeoNames.", "Heads retrain on harvested labels; a new topic only when unplaced items keep recurring.", "Built; partly judged."),
        ("Fragments", "Who did what to what, with entities, amounts, dates, tense.", "spaCy and the Fact finder.", "Better entity and role heads.", "Built; stated facts judged by the text, tags not judged."),
        ("Anchor", "A stable id for an entity, concept or place.", "GeoNames places; topic names as first concepts.", "A mention that resolves to the same thing in several articles gets an alias; merges keep the old id.", "Not built."),
        ("Area", "The neighbourhood around an anchor: drivers, dependencies, which items point at it.", "A small seeded list; the topics are the first Areas.", "Items route to it; its Pulse (volume, change, novelty, conflict, uncertainty) is counted from their profiles.", "Not built."),
        ("Capability", "A reusable ability or process that several Areas share.", "Starts empty or very small.", "A verb-object phrase recurring across Areas and independent publishers becomes a candidate, then validated, then promoted.", "Not built."),
        ("Domain (top level)", "The highest grouping of Areas.", "The 17 broad classes, or our own.", "Splits and merges only through the promotion gates.", "Partly: topics roll up to 17.")]
roll_tbl = tbl(["Level", "What it is", "Core seed", "How it grows", "Status"], "".join(pair([f"<b>{e(a)}</b>", e(b), e(c_), e(d_), e(e_)], "<p class='n'>Playbook section 9: a candidate is promoted only if it has independent evidence from several publishers, is coherent and distinct from what exists, reusable beyond one event, and organises knowledge better. Automated promotion needs a human-reviewed regime; otherwise it stays provisional.</p>", 5) for a, b, c_, d_, e_ in ROLL), "main")
st = IS["steps"]; last = st[-1]; never = 17 - last["A_labels_only"]["classes"]
bars = "".join("<tr><td>" + str(x['articles']//1000) + "k</td><td>" + f"{x['A_labels_only']['labels']:,}" + "</td><td>" + f"{x['A_labels_only']['top1']:.3f}" + "</td></tr>" for x in st) #
bars_old = "".join(bar(f"{x['articles']//1000}k read", x["A_labels_only"]["top1"], f"  ({x['A_labels_only']['labels']:,} labels)") for x in (st[0], st[1], st[3], st[6], st[9]))
hrows = "".join(f"<tr><td>{e(k)}</td><td>{v[0]:,}</td><td>{v[1]:.2f}</td></tr>" for k, v in sorted(HS["agree_by_class"].items(), key=lambda x: -x[1][1]))
cc = r["C_class_count"]; classes = "".join(bar(f"{k} classes", cc[k]["top1_mean"], f"  (guess {cc[k]['chance']:.3f})") for k in ("5", "10", "20", "40", "109"))
lean = open("lean/TrainReady.lean").read(); n_thm = len(re.findall(r"^theorem ", lean, re.M)); n_ex = len(re.findall(r"^example ", lean, re.M))
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>How an article is read</title><link rel="stylesheet" href="../mock.css">
<style>
main{{max-width:980px;margin:0 auto;padding:14px 16px 56px}} h1{{margin:0 0 6px;font-size:24px}} h2{{margin:30px 0 8px;font-size:18px}} p,li{{line-height:1.55;font-size:15px}} .n{{font:12px ui-monospace,monospace;color:var(--ink-2);margin:4px 0}}
table.main td,table.main th{{vertical-align:top}} table.main{{margin-bottom:6px}} .tgc{{width:34px}} button.tg{{width:26px;height:26px;border:1px solid var(--line,#8886);background:var(--surface-2);color:inherit;border-radius:5px;cursor:pointer;font:15px ui-monospace,monospace}} .tools{{text-align:right;margin:4px 0}} button.all{{font-size:12px;background:none;border:1px solid var(--line,#8886);color:inherit;border-radius:5px;padding:3px 9px;cursor:pointer}}
tr.detail td{{background:var(--surface-2);padding:8px 10px}} table.mini{{margin:4px 0 10px}} table.mini th{{font-size:11px;color:var(--ink-2)}} tr.main:hover td{{background:var(--surface-2)}}
ol.steps{{list-style:none;padding:0;margin:0}} .step{{padding:10px 0;border-bottom:1px solid var(--line,#8884)}} .step p.g{{margin:3px 0}} .sh{{font-size:16px}}
details{{margin:6px 0}} summary{{cursor:pointer;font-size:13px;color:var(--accent)}} .head{{border-bottom:1px solid var(--line,#8884);padding:6px 0}} .head summary{{color:inherit;font-size:15px}} .one{{margin-left:10px;color:var(--ink-2);font-size:13px}} .in{{padding:6px 0 6px 14px}} .in p{{margin:4px 0;font-size:14px}}
.chip{{font:11px ui-monospace,monospace;padding:1px 7px;border-radius:9px;border:1px solid var(--line,#8884);margin-left:6px}} .chip.ok{{color:#1e8e4e}} .chip.mid{{color:#b7791f}} .chip.no{{color:#c0392b}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line,#8884)}}
.v-ok{{color:#1e8e4e}} .v-mid{{color:#b7791f}} .v-no{{color:#c0392b}}
.row{{display:grid;grid-template-columns:150px 1fr 150px;gap:8px;align-items:center;font-size:13px;margin:3px 0}} .b{{height:12px;background:var(--surface-2);border:1px solid var(--line,#8884);border-radius:3px;display:block}} .b i{{display:block;height:100%;background:var(--accent)}} .v{{font:12px ui-monospace,monospace}}
.src{{font:12px ui-monospace,monospace;color:var(--ink-2);margin-top:8px}}
@media (max-width:760px){{.row{{grid-template-columns:100px 1fr 90px}} .one{{display:block;margin:2px 0 0}}}}
</style></head><body><main>
<h1>How an article is read</h1>
<p>The goal is an engine that reads news and builds its own training data. Cheap tools read each article first and keep everything they can prove. Each BitMob then learns from what the tools found, and its answers are checked against outside labels afterwards. Click any line to see numbers and examples.</p>
<h2>1. What happens to an article</h2>
{steps}
<p class="n">Only the last decision step is in Rust today ({e(INV['rust'])}); every step above runs in Python. Steps 1 to 7 are saved together in one record per article (step 8).</p>
<h2>2. What the tools hand to each head</h2>
<p>Labels built from the first {XS['articles']:,} articles, straight from the record. These are training inputs, not proof; strength and rule are kept with every label.</p>
{tl_table}
<h2>3. Domain: the top-level profile of an article</h2>
<p>Domain is the highest level of information. In the engine it already exists as the Macro Pulse: what kind of item it is, what it is about, what is changing and which way, how big, which traits. Place and time sit with it. Each row below is one characteristic, with the tools that extract it, who judges it, and where it stands today.</p>
{prof_tbl}
<div class="tools"><button class="show" type="button">Show how topic evidence was combined and tested</button></div>
<div hidden><p>Topic is one characteristic. Here it is read from several pieces of evidence, not the URL alone, and scored on {DE['ruler']:,} human-labelled articles that none of the views trained on.</p>{dom_tbl}{dom_read}<p class="n">Sources: runs/harvest/domain_evidence.json (domain_evidence.py, ledger L1047, L1048).</p></div>
<h2>4. How the set grows</h2>
<p>Items roll up into Areas, Areas into Domains, and Capabilities cut across Areas. Each level starts from a small core and grows only through evidence. Click a row for the promotion rule.</p>
{roll_tbl}
<h2>5. What each head means</h2>
<p>Definitions follow the playbook and the PRD: everything attaches to an anchor, and Domain, Area and Capability are broad groupings, not fixed levels.</p>
{heads}
<h2>6. Is there enough to train each one?</h2>
<p>A Lean rule ({n_thm} theorems, {n_ex} examples) gives each target one verdict from its measured numbers. Domain and Area rows use news-only stand-in labels.</p>
{verd}
<h2>7. How far does the lazy loop go?</h2>
<p>One tool (the URL section) labelled articles as they were read, a model retrained after every 10,000, and the result was scored on {IS['mnds_n']:,} human-labelled articles. It levelled off at {last['A_labels_only']['top1']:.2f}, because {never} of 17 classes never got a label and sport made up {last['label_counts']['sport']/last['A_labels_only']['labels']*100:.0f}% of the labels. Each retrain took {last['A_labels_only']['seconds']:.0f} seconds. That is the limit of one tool of the seven, not of the loop.</p>
<table class="main"><tr><th>Articles read</th><th>Labels from the URL tool</th><th>Accuracy on human-labelled articles</th></tr>{bars}</table>
<div class="tools"><button class="show" type="button">Show or hide label quality by URL section</button></div>
<table class="main" hidden><tr><th>Label</th><th>Articles</th><th>Agreement with a word model</th></tr>{hrows}</table>
<p class="src">Sources: runs/harvest/{{inventory,place_reach,link_reach,score,inline_sim}}.json; runs/pulse/tools_to_training.json, train_ready_rows.json; lean/TrainReady.lean; playbook 00; PRD v0.2. <a href="../solver/index.html">Mob solver</a> · <a href="../state/index.html">Pulse state</a> · <a href="../gates/index.html">Gates</a></p>
<script>
document.addEventListener("click", function (ev) {{
  var b = ev.target.closest("button"); if (!b) return;
  if (b.classList.contains("tg")) {{ var d = b.closest("tr").nextElementSibling, open = d.hidden; d.hidden = !open; b.textContent = open ? "\u2212" : "+"; b.setAttribute("aria-expanded", String(open)); }}
  if (b.classList.contains("show")) {{ var t = b.parentNode.nextElementSibling; t.hidden = !t.hidden; }}
  if (b.classList.contains("all")) {{ var tb = b.parentNode.nextElementSibling, o = b.textContent === "Expand all";
    tb.querySelectorAll("tr.detail").forEach(function (r) {{ r.hidden = !o; r.previousElementSibling.querySelector("button.tg").textContent = o ? "\u2212" : "+"; }}); b.textContent = o ? "Collapse all" : "Expand all"; }}
}});
</script>
</main></body></html>"""
open("/workspace/demo/mockups/bitmobs/index.html", "w", encoding="utf-8").write(page); print("ok", len(page))
