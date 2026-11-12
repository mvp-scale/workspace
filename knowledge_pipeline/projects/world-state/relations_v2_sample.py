"""Fresh blind sample of 40 triples from extractor v2 (same 9 articles; excludes anything judged in L1092). -> runs/harvest/relations/judge_items_v2.json"""
import json, random, warnings; warnings.filterwarnings("ignore")
import spacy, spo_chains as S
R = "runs/harvest/relations"; nlp = spacy.load("en_core_web_sm"); A = json.load(open("runs/harvest/article_topics.json"))["articles"]
old = json.load(open(f"{R}/judge_items.json")); seen = {(o["sentence"], o["subject"], o["object"]) for o in old}; pool = []
for a in A:
    T = S.extract(nlp, a["sentences"]); S.merge_aliases(T)
    for t in T:
        if t["s"] and t["o"] and not t["s_pronoun"] and not t["o_pronoun"] and (a["sentences"][t["sent"]], t["s"], t["o"]) not in seen:
            pool.append({"title": a["title"], "sentence": a["sentences"][t["sent"]], "subject": t["s"], "relation": t["p"] + (" [negated]" if t["neg"] else "") + (" [modal: " + ",".join(t["modal"]) + "]" if t["modal"] else "") + (" [when: " + "; ".join(t["when"]) + "]" if t.get("when") else ""), "object": t["o"]})
random.Random(20261109).shuffle(pool); items = pool[:40]
for i, it in enumerate(items): it["id"] = f"v{i+1}"
json.dump([{k: v for k, v in it.items() if k != "title"} for it in items], open(f"{R}/judge_items_v2.json", "w"), indent=1); print(len(pool), "in pool;", len(items), "sampled")
