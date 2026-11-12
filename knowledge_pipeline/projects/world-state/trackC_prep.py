"""Track C preparation (nothing is run against any model): 1,000 pool articles with teacher input = title + gist.
CPU only. Gist = article_views.split + coverage_pick(E, W, False), k=4 sentences, budget 120 words, bge-small-en-v1.5 on CPU,
max_seq_length 256, text cut at 12000 characters and 120 sentences, as article_views.views() did for the gist test (V2, L1104/L1108).
    CUDA_VISIBLE_DEVICES= /workspace/models/embed-zs/.venv/bin/python trackC_prep.py -> runs/harvest/trackC_prep/"""
import os, sys, json, random, re, collections, statistics as st, warnings
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["CUDA_VISIBLE_DEVICES"] = ""; warnings.filterwarnings("ignore")
import numpy as np
from sentence_transformers import SentenceTransformer
sys.path.insert(0, "/workspace/knowledge_pipeline/kit/teacher")
import task_spec as TS
import article_views as V
W0 = "/workspace/knowledge_pipeline/projects/world-state"; OUT = f"{W0}/runs/harvest/trackC_prep"; SEED = 20261108; N = 1000; CAP_SHARE = 0.02; MIN_CHARS = 800; PUB_CAP = int(N * CAP_SHARE)
SPEC = f"{W0}/specs/world_state_v3b_nosize_sonnet.json"
# 1. label store: Sonnet-labelled ids
son = set(); non_cc = 0
for l in open(f"{W0}/runs/label_store/labels.jsonl"):
    r = json.loads(l)
    if r["family"] == "sonnet":
        if r["item_id"].startswith("cc:"): son.add(r["item_id"])
        else: non_cc += 1
non_cc_ids = len({json.loads(l)["item_id"] for l in open(f"{W0}/runs/label_store/labels.jsonl") if json.loads(l)["family"] == "sonnet" and not json.loads(l)["item_id"].startswith("cc:")})
# 2. candidates
pool = {}
for l in open(f"{W0}/runs/harvest/pool_v1/pool.jsonl"):
    r = json.loads(l); pool[r["row"]] = r["item_id"]
cand = []; stats = collections.Counter()
for l in open(f"{W0}/runs/harvest/sample.jsonl"):
    r = json.loads(l); iid = pool.get(r["row"])
    if iid is None: stats["not_in_pool"] += 1; continue
    if len(r["text"]) < MIN_CHARS: stats["under_800_chars"] += 1; continue
    if iid in son: stats["already_sonnet_labelled_cc"] += 1; continue
    cand.append((iid, r)); stats["eligible"] += 1
rng = random.Random(SEED); rng.shuffle(cand)
m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 256
embed = lambda xs: m.encode(xs, batch_size=64, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float32)
per = collections.Counter(); items = []; too_few = 0
for iid, r in cand:
    if len(items) >= N: break
    pub = r["domain"]
    if per[pub] >= PUB_CAP: continue
    text = re.sub(r"[ \t]+", " ", r["text"])[:12000]; sents = V.split(re.sub(r"\s*\n\s*", " ", text))[:120]
    if len(sents) < 4: too_few += 1; continue
    E = embed(sents); Wd = [len(s.split()) for s in sents]; sel = V.coverage_pick(E, Wd, False)
    gist = " ".join(sents[j] for j in sorted(sel)); per[pub] += 1
    items.append({"id": iid, "title": r["title"], "publisher": pub, "date": r["date"], "url": r["url"], "row": r["row"], "full_text_chars": len(r["text"]), "gist_sentence_numbers": [j + 1 for j in sorted(sel)], "gist": gist,
                  "text": (r["title"].strip().rstrip(".") + ". " + gist).strip()})
    if len(items) % 100 == 0: print(len(items), flush=True)
assert len(items) == N, len(items)
meta = {"v": "trackC-items-v1", "seed": SEED, "n": N, "min_text_chars": MIN_CHARS, "publisher_cap": PUB_CAP, "publisher_cap_share": CAP_SHARE, "max_per_publisher_used": max(per.values()), "publishers": len(per),
        "gist_settings": {"selector": "article_views.coverage_pick (greedy facility-location coverage, gist.py rules, lean/GistSelect.lean)", "sentences": 4, "word_budget": 120, "forced_first_sentence": False, "embedding": "BAAI/bge-small-en-v1.5 CPU, max_seq_length 256, normalised", "sentence_split": "article_views.split", "text_cut": "12000 chars, first 120 sentences", "min_sentences": 4, "same_as": "variants_build.py V2 gist used for runs/harvest/teacher_gist items_B_gist.json (L1104, L1108)"},
        "teacher_input_text": "title + '. ' + gist (the earlier test gave headline plus gist; the registered labeller input_template is 'ITEM {id}\\n<text>\\n{text}\\n</text>')",
        "selection": stats and dict(stats), "skipped_fewer_than_4_sentences": too_few,
        "label_store_check": {"sonnet_cc_ids_in_store": len(son), "sonnet_non_cc_item_ids_not_checkable": non_cc_ids, "note": "nq:/nr:/q: ids cannot be mapped to sample rows (pool_v1 summary); so overlap with those could not be checked"}}
json.dump({"meta": meta, "items": items}, open(f"{OUT}/items_1000.json", "w"), indent=1, ensure_ascii=False)
# batch input file in the format claude_batch.py reads (id, text)
with open(f"{OUT}/items_1000.jsonl", "w") as f:
    for it in items: f.write(json.dumps({"id": it["id"], "text": it["text"]}, ensure_ascii=False) + "\n")
# 3. prompt: registered spec, copied; a tag-only copy for ws-gist-v1
spec = json.load(open(SPEC)); spec2 = dict(spec); spec2["name"] = "world_state_gist_v1_sonnet"; spec2["prompt_version"] = "ws-gist-v1"; spec2["cap_usd"] = 2.0
json.dump(spec2, open(f"{OUT}/spec_ws_gist_v1_sonnet.json", "w"), indent=1, ensure_ascii=False)
ts = TS.load(SPEC); sysx = ts.system_text(); open(f"{OUT}/prompt_system.txt", "w").write(sysx)
ex3 = [{"id": it["id"], "user_message": ts.user_text({"id": it["id"], "text": it["text"]}), "gist_words": len(it["gist"].split())} for it in items[:3]]
json.dump({"registered_spec": SPEC, "model": spec["model"], "prompt_version_registered": spec["prompt_version"], "prompt_version_new": "ws-gist-v1", "max_tokens": spec["max_tokens"], "input_template": spec["input_template"],
           "system_prompt_file": f"{OUT}/prompt_system.txt", "system_prompt_chars": len(sysx), "system_prompt_sha256_of_spec_minus_tag_note": "spec copy differs from registered spec only in name, prompt_version, cap_usd",
           "output_schema": spec["output_schema"], "few_shot_examples_inside_system_prompt": len(spec["examples"]), "three_items_as_sent": ex3,
           "reply_for_each_item": "JSON object only: topic (one of 49 ids), story_type (fact|forecast|opinion|unclear), claim (<=220 chars), conditions (0..6 of {condition, direction up|down, level minor..extreme}); not yet produced, nothing was run"}, open(f"{OUT}/prompt_and_schema.json", "w"), indent=1, ensure_ascii=False)
# 4. token counts: calibrate chars/token on the measured batch run (sonnet_pool6k parts 1-3)
R = f"{W0}/runs/pulse/sonnet_pool6k"; ids = {}
for k in (1, 2, 3):
    for l in open(f"{R}/items_part{k}.jsonl"): r = json.loads(l); ids[r["id"]] = r["text"]
wrap = lambda i, t: ts.user_text({"id": i, "text": t}); tot_chars = sum(len(wrap(i, t)) for i, t in ids.items()) - 0
use = collections.Counter(); nb = 0; mans = 0
for k in (1, 2, 3):
    for l in open(f"{R}/part{k}/spend.jsonl"):
        r = json.loads(l)
        for a, b in r["usage"].items(): use[a] += b
        if r["mode"] == "batch": nb += r["n"]; mans += r["usd"]
labs = [json.loads(l) for k in (1, 2, 3) for l in open(f"{R}/part{k}/labels.jsonl")]
out_tok = [x.get("usage", {}).get("output_tokens") for x in labs]; out_tok = [x for x in out_tok if x]
batch_rows = [x for x in labs if x["provenance"].get("mode") == "batch"]
cache_read_per_req = use["cache_read_input_tokens"] / max(1, nb)
# per-request uncached input tokens measured: input_tokens / n requests (batch rows only reported in sums); chars per token on the user message
unc = sum(json.loads(l)["usage"]["input_tokens"] for k in (1, 2, 3) for l in open(f"{R}/part{k}/spend.jsonl") if json.loads(l)["mode"] == "batch")
cpt = tot_chars / unc
calib = {"source": f"{R}/part1..3/spend.jsonl", "requests_batch": nb, "uncached_input_tokens_total": unc, "user_message_chars_total_all_6000_items": tot_chars, "chars_per_token_measured": round(cpt, 3), "note": "chars of the rendered user message (ITEM id + text wrapper) over API-counted uncached input tokens (batch rows); the 5985 labelled items vs 6000 sent makes this a close, not exact, ratio",
         "output_tokens_total_batch": use["output_tokens"], "output_tokens_per_label_mean": round(use["output_tokens"] / max(1, sum(r["n"] for k in (1, 2, 3) for l in open(f"{R}/part{k}/spend.jsonl") for r in [json.loads(l)] )), 1),
         "cache_read_tokens_per_request": round(cache_read_per_req, 0), "measured_usd_total": round(sum(json.loads(l)["usd"] for k in (1, 2, 3) for l in open(f"{R}/part{k}/spend.jsonl")), 4), "items_labelled": len(labs)}
out_per = np.array(out_tok); calib["output_tokens_per_label_median"] = float(np.median(out_per)); calib["output_tokens_per_label_p95"] = float(np.percentile(out_per, 95))
msgtok = lambda it: len(wrap(it["id"], it["text"])) / cpt
gt = np.array([msgtok(it) for it in items]); full_gt = np.array([min(it["full_text_chars"], 8000) for it in items]) / cpt
price = json.load(open("/workspace/knowledge_pipeline/kit/teacher/prices.json")); p = price["models"]["claude-sonnet-5-5"]; disc = price["batch_discount"]
nsys = int(round(cache_read_per_req))
def cost(n, per_in, per_out, sysrd, batches):
    inp = n * per_in / 1e6 * p["input"] * disc; rd = n * sysrd / 1e6 * p["cache_read"] * disc; o = n * per_out / 1e6 * p["output"] * disc; wr = batches * sysrd / 1e6 * p["cache_write_1h"] * disc
    return inp, rd, o, wr
rows = []; mean_in = float(gt.mean()); mean_out = calib["output_tokens_per_label_mean"]
for n in (1000, 2000, 3000, 4000):
    sc = n / N; b = max(1, int(np.ceil(n / 500))); i, rd, o, wr = cost(n, mean_in, mean_out, nsys, b)
    rows.append({"articles": n, "gist_tokens_in_per_article_median": round(float(np.median(gt)), 1), "gist_tokens_in_total_estimate": round(mean_in * n), "output_tokens_total": round(mean_out * n), "cached_prompt_read_tokens_total": nsys * n, "batches_of_500": b,
                 "usd_input_uncached_est": round(i, 3), "usd_cached_prompt_read_est": round(rd, 3), "usd_output_est": round(o, 3), "usd_cache_write_est": round(wr, 3), "usd_total_batch_est": round(i + rd + o + wr, 2),
                 "usd_total_if_not_batch_est": round((i + rd + o + wr) / disc, 2)})
alt_in = float(np.mean([len(wrap(it["id"], it["text"])) / 4.0 for it in items])); alt = {n: round(sum(cost(n, alt_in, mean_out, nsys, max(1, int(np.ceil(n / 500))))), 2) for n in (1000, 2000, 3000, 4000)}
left = 70 - 67.7
fi = float(full_gt.mean())
heldout = cost(100, fi, mean_out, nsys, 1) ; held_full = sum(heldout)
heldout_gist = sum(cost(100, mean_in, mean_out, nsys, 1))
costj = {"v": "trackC-cost-v1", "all_dollar_figures": "ESTIMATES: list prices from kit/teacher/prices.json (status TO_BE_VERIFIED, not confirmed against the live pricing page), batch discount 0.5; the Console bill is the truth",
         "price_source": "/workspace/knowledge_pipeline/kit/teacher/prices.json#models.claude-sonnet-5-5", "usd_per_million_tokens_standard": p, "batch_discount": disc, "tokenizer_assumption": f"no tokenizer is installed for Claude; chars per token = {round(cpt,3)}, measured on the earlier Sonnet batch run (calibration block); the earlier gist test (L1109, L1111) itself counted observed session tokens of agents, not text tokens, so there is no tokenizer figure to copy", "calibration": calib,
         "gist_input_tokens_per_article": {"definition": "rendered user message (ITEM id wrapper + title + gist) chars over chars_per_token", "median": round(float(np.median(gt)), 1), "mean": round(mean_in, 1), "p95": round(float(np.percentile(gt, 95)), 1), "total_1000": round(float(gt.sum())), "median_gist_words": float(np.median([len(i["gist"].split()) for i in items]))},
         "full_article_input_tokens_per_article_for_comparison_8000_char_cap": {"mean": round(fi, 1), "ratio_full_over_gist_mean": round(fi / mean_in, 2)},
         "rows": rows, "rows_alt_if_4_chars_per_token": {"mean_input_tokens": round(alt_in, 1), "usd_total_batch_est": alt, "why": "the measured 2.3 chars per token is inflated by URL ids in the item id (cc:http://...); prose tokenises near 4, so this is the low end"}, "measured_cross_check": {"usd_per_item_short_items_measured": round(calib["measured_usd_total"] / calib["items_labelled"], 5), "source": "runs/pulse/sonnet_pool6k/part1..3/spend.jsonl (6000 short headline-plus-teaser items, batch)"}, "hosted_cap": {"cap_usd": 70, "spent_usd_per_GO_md": 67.7, "left_usd": round(left, 2), "source": "/workspace/GO.md lines 15 and 22 (the task named GOES.md; no such file, GO.md holds the figure); owner reconciles against the Console bill",
                                      "fits": {str(r["articles"]): r["usd_total_batch_est"] <= left for r in rows}},
         "heldout_check_100_full_article_labels": {"extra_labels": 100, "usd_est": round(held_full, 3), "note": "100 articles read in full (cut at 8000 chars) by the same spec; the gist labels for the same 100 come from the main run (already paid)"}}
json.dump(costj, open(f"{OUT}/cost_table.json", "w"), indent=1)
json.dump(items[:100] and [{"id": it["id"], "title": it["title"], "full_text_chars": it["full_text_chars"]} for it in rng.sample(items, 100)], open(f"{OUT}/heldout_100_ids.json", "w"), indent=1)
print(json.dumps({k: costj[k] for k in ("gist_input_tokens_per_article", "full_article_input_tokens_per_article_for_comparison_8000_char_cap", "rows", "hosted_cap", "heldout_check_100_full_article_labels")}, indent=1)); print(json.dumps(calib, indent=1)); print(meta["selection"], too_few, len(per), max(per.values()), non_cc_ids)
