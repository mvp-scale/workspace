"""Gathers the result files of the 2026-11-07/08 foundations work into /workspace/demo/mockups/learned/data.json (the page reads every number from it). Nothing is computed here except counts from the gist-judging files and the label text length.
    /workspace/models/embed-zs/.venv/bin/python learned_page_data.py"""
import json, glob, collections, numpy as np
L = lambda p: json.load(open(p)); R = "runs/"
out = {"sources": {}}
def put(k, path, pick=None):
    d = L(path); out[k] = pick(d) if pick else d; out["sources"][k] = "knowledge_pipeline/projects/world-state/" + path
put("label_curve", R + "harvest/label_curve.json")
put("structure", R + "pulse/structure_test.json")
put("sparse", R + "pulse/sparse_expand_test.json")
put("ensemble", R + "pulse/ensemble_test.json")
put("teacher_topic", R + "harvest/teacher_gist/result.json")
put("teacher_story", R + "harvest/teacher_gist/story_result.json")
put("triples_v1", R + "harvest/relations/judged.json")
put("triples_v2", R + "harvest/relations/judged_v2.json")
put("carb", R + "harvest/relations/carb_score.json")
put("maven_trigger", R + "harvest/relations/maven_trigger.json")
put("maven_filter", R + "harvest/relations/maven_trigger_filter.json")
put("track_a", R + "harvest/relations/trackA_happened.json")
put("simplify", R + "harvest/relations/simplify.json", lambda d: {k: d[k] for k in ("sentences", "random_pair_cosine", "original_nearest_other_sentence_same_article", "variants", "negation")})
# gist judged by Sonnet and Opus as a reading aid (first test)
G = R + "harvest/gist_judging/"; key = {x["id"]: x for x in L(G + "key.json")}; res = {}
for n in ("sonnet", "opus"):
    j = L(G + f"judge_{n}.json"); c = collections.Counter(); sc = {"gist": [], "first": []}
    for x in j:
        k = key[x["id"]]; g = "A" if k["A_is"] == "gist" else "B"; f = "B" if g == "A" else "A"
        c["gist" if x["better"] == g else ("first" if x["better"] == f else "tie")] += 1; sc["gist"].append(x["score_" + g]); sc["first"].append(x["score_" + f])
    res[n] = {"gist_preferred": c["gist"], "first_sentences_preferred": c["first"], "tie": c["tie"], "mean_score_gist": round(float(np.mean(sc["gist"])), 2), "mean_score_first": round(float(np.mean(sc["first"])), 2), "articles": len(j)}
out["gist_for_humans"] = res; out["sources"]["gist_for_humans"] = "knowledge_pipeline/projects/world-state/" + G + "judge_sonnet.json, judge_opus.json, key.json"
# how long the labelled items are
ids = json.load(open(R + "embeds/bge_small_ids.json")); txt = {}
for p in ("data/pool.jsonl", "runs/pulse/queue_texts.jsonl"):
    for l in open(p):
        r = json.loads(l); txt[r["id"]] = r["text"]
for f in glob.glob("runs/**/items*.jsonl", recursive=True):
    try:
        for l in open(f):
            r = json.loads(l)
            if r.get("id") and r.get("text"): txt.setdefault(r["id"], r["text"])
    except Exception: pass
Ls = np.array([len(txt[i]) for i in ids if i in txt]); out["label_length"] = {"items": int(len(Ls)), "median_chars": int(np.median(Ls)), "share_over_600_chars": round(float((Ls > 600).mean()), 3)}; out["sources"]["label_length"] = "label items with a bge-small embedding; text from data/pool.jsonl, runs/pulse/queue_texts.jsonl, runs/**/items*.jsonl"
# session token counts reported by the harness when the labelling agents finished (L1109, L1111)
out["tokens"] = {"topic_full_text_four_agents": 339000, "topic_gist_one_agent": 79805, "story_full_text_two_agents": 167334, "story_gist_one_agent": 60172, "note": "usage reported by the harness at the end of each agent, ledger L1109 and L1111; includes agent overhead"}
json.dump(out, open("/workspace/demo/mockups/learned/data.json", "w")); print({k: (len(json.dumps(v)) if k != "sources" else "") for k, v in out.items()})
