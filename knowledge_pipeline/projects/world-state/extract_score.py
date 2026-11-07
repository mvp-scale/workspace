"""Score extraction record v0 against L1042. Writes runs/harvest/extract_score.json."""
import json, random, collections
from multiprocessing import Pool
import extract as X
R5 = [json.loads(l) for l in open("runs/harvest/extract.jsonl")]; n = len(R5)
run = json.load(open("runs/harvest/extract_run.json")); bp = json.load(open("runs/harvest/boilerplate.json"))
tags = collections.Counter(); cond = collections.Counter(); how = collections.Counter(); ent = collections.Counter(); tag_art = 0; cond_art = 0; ctry_art = 0; place_art = 0; link_art = 0; rm_art = 0; ms = []
for r in R5:
    c = r["function"]["counts"]; tags.update(c); tag_art += any(k != "unknown" for k in c); cond.update(i["condition"] for i in r["conditions"]["items"]); cond_art += bool(r["conditions"]["items"])
    how.update(p["how"] or "unlinked" for p in r["places"]["items"]); ctry_art += bool(r["places"]["countries"]); place_art += bool(r["places"]["items"]); link_art += bool(r["source"]["links_in_text"]); rm_art += r["clean"]["boilerplate_lines_removed"] > 0; ms.append(r["ms"]); ent.update(r["entities"]["counts"])
# L1038 comparison: same 300 articles as place_reach.py
S = [r for r in map(json.loads, open("runs/harvest/sample.jsonl")) if len(r["text"] or "") >= 800]; random.Random(20261107).shuffle(S); S = S[:300]
with Pool(16, initializer=X.init) as P: o300 = P.map(X.work, S, chunksize=5)
c300 = sum(bool(r["places"]["countries"]) for r in o300); p300 = sum(bool(r["places"]["items"]) for r in o300)
res = {"articles": n, "tools_seconds": run["tools_seconds"], "per_second_no_reader": run["per_second_no_reader"], "boilerplate": {"share_touched_20k": bp["share_touched"], "share_chars_removed_20k": bp["share_chars_removed"], "articles_with_removed_line_in_5k": rm_art},
       "places_300": {"with_place": p300, "with_country": c300, "share_country": round(c300 / 300, 4), "before": 0.6933}, "factuality": {"articles_with_tag": tag_art, "share": round(tag_art / n, 4), "sentence_tags": dict(tags)}, "conditions": {"articles_with_item": cond_art, "share": round(cond_art / n, 4), "items_by_condition": dict(cond)},
       "place_methods": dict(how), "articles_with_country": ctry_art, "articles_with_place": place_art, "articles_with_link_in_text": link_art, "entity_types": dict(ent.most_common(10)), "median_ms_per_article_one_thread": sorted(ms)[len(ms) // 2]}
json.dump(res, open("runs/harvest/extract_score.json", "w"), indent=1); print(json.dumps(res, indent=1))
