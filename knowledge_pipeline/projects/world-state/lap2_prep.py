"""Lap two preparation (CPU, no model calls): (1) 250 articles from the rebalanced selection with gists, for one teacher batch that tests the working Condition definition; (2) a DRAFT Area seed from what exists (17 news categories as Domains, our 49 topics as Areas), for the owner to edit.
Working Condition definition (not a confirmed contract): a thing, a kind and a direction that the article reports as having already changed, taken as the registered labeller's conditions field.
Writes runs/harvest/pool_v2/items_250.json and area_seed_draft.json.   /workspace/models/embed-zs/.venv/bin/python lap2_prep.py   (from projects/world-state)"""
import json, re, random, collections, numpy as np, warnings
warnings.filterwarnings("ignore")
from sentence_transformers import SentenceTransformer
import article_views as V
sel = json.load(open("runs/harvest/pool_v2/select_2000.json")); want = {x["id"]: x for x in sel}
rng = random.Random(20261108); ids = sorted(want); rng.shuffle(ids); pick = ids[:250]
m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 256
embed = lambda xs: m.encode(xs, batch_size=64, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float32)
need = set(pick); items = []
for l in open("runs/harvest/sample.jsonl"):
    r = json.loads(l); iid = "cc:" + (r.get("url") or "")
    if iid not in need: continue
    text = re.sub(r"[ \t]+", " ", r["text"])[:12000]; sents = V.split(re.sub(r"\s*\n\s*", " ", text))[:120]
    if len(sents) < 4: continue
    E = embed(sents); sel_ = V.coverage_pick(E, [len(s.split()) for s in sents], False); gist = " ".join(sents[j] for j in sorted(sel_))
    items.append({"id": iid, "text": (r["title"].strip().rstrip(".") + ". " + gist).strip(), "guess_topic": want[iid]["topic"], "condition_proposal": want[iid]["cond"]})
json.dump(items, open("runs/harvest/pool_v2/items_250.json", "w"))
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; cnt = collections.Counter()
for l in open("runs/label_store/labels.jsonl"):
    r = json.loads(l)
    if r["family"] == "sonnet" and r.get("topic"): cnt[r["topic"]] += 1
dom = collections.defaultdict(list)
for t, cats in M.items(): dom[cats[0] if cats else "unmapped"].append({"area": t, "labelled_items": cnt.get(t, 0), "also_under": cats[1:]})
seed = {"status": "DRAFT for the owner to edit; built from news topics, not from the owner's ontology", "domains": [{"domain": d, "areas": sorted(a, key=lambda x: -x["labelled_items"])} for d, a in sorted(dom.items())], "n_domains": len(dom), "n_areas": sum(len(a) for a in dom.values()), "source": "specs/topic_to_iptc_v1.json and runs/label_store/labels.jsonl"}
json.dump(seed, open("runs/harvest/pool_v2/area_seed_draft.json", "w"), indent=1); print(len(items), seed["n_domains"], seed["n_areas"], sum(i["condition_proposal"] for i in items))
