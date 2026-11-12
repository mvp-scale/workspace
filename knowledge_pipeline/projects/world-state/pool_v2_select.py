"""Lap two step 1: pick 2,000 pool articles for the next teacher batch with a topic mix that follows the Sonnet label store and with condition proposals from the change lexicon.
Topic of a pool article = the sparse topic head's top guess (a guess, not a label). Excludes ids already labelled by Sonnet and the first 1,000 gist items. At most 20 per publisher. Seeded.
Writes runs/harvest/pool_v2/select_2000.json and summary.json.   /workspace/models/embed-zs/.venv/bin/python pool_v2_select.py   (from projects/world-state)"""
import json, pickle, re, random, collections, numpy as np, os
os.makedirs("runs/harvest/pool_v2", exist_ok=True)
H = pickle.load(open("runs/expert1/sparse_heads_v1.pkl", "rb")); m = H["topic_model"]; W = np.ascontiguousarray(m.coef_.T.astype(np.float32)); b = m.intercept_.astype(np.float32); cl = np.array(m.classes_)
def top(x):
    z = np.asarray(H["topic_vec"].transform([x]).astype(np.float32) @ W).ravel() + b; return str(cl[int(z.argmax())])
store = collections.Counter(); done = set()
for l in open("runs/label_store/labels.jsonl"):
    r = json.loads(l)
    if r["family"] == "sonnet" and r.get("topic"): store[r["topic"]] += 1; done.add(r["item_id"])
first = {x["id"] for x in json.load(open("runs/harvest/trackC_prep/items_1000.json"))["items"]}
cond = {}
for l in open("runs/harvest/pool_v1/pool.jsonl"):
    r = json.loads(l); cond[r["item_id"]] = any(it["tool"] == "change-lexicon" for it in r["items"])
cand = []
for l in open("runs/harvest/sample.jsonl"):
    r = json.loads(l); i = "cc:" + (r.get("url") or ""); t = (r.get("text") or "")
    if i in done or i in first or len(t) < 800 or i not in cond: continue
    cand.append({"id": i, "publisher": r.get("domain") or "", "topic": top(re.sub(r"\s+", " ", (r.get("title") or "") + ". " + t)[:3000]), "cond": cond[i]})
n_store = sum(store.values()); want = 2000; tgt = {k: v / n_store * want for k, v in store.items()}
rng = random.Random(20261108); rng.shuffle(cand); pubn = collections.Counter(); got = collections.Counter(); sel = []
cand.sort(key=lambda c: (not c["cond"]))  # condition proposals first, stable after the shuffle
need_cond = int(0.25 * want); ncond = 0
for phase in ("cond", "rest"):
    for c in cand:
        if len(sel) >= want: break
        if c in sel and False: continue
        if phase == "cond" and not c["cond"]: continue
        if phase == "cond" and ncond >= need_cond: break
        if got[c["topic"]] >= round(tgt.get(c["topic"], 0)) or pubn[c["publisher"]] >= 20 or any(c["id"] == s["id"] for s in ()): continue
        if phase == "rest" and c["id"] in {s["id"] for s in sel[:0]}: continue
        sel.append(c); got[c["topic"]] += 1; pubn[c["publisher"]] += 1; ncond += c["cond"]
seen = set(); sel = [c for c in sel if not (c["id"] in seen or seen.add(c["id"]))]
cc = collections.Counter(c["topic"] for c in sel); pool_cc = collections.Counter(c["topic"] for c in cand)
short = {k: round(tgt[k] - cc.get(k, 0), 1) for k in tgt if tgt[k] - cc.get(k, 0) > 0.2 * tgt[k] and tgt[k] >= 5}
res = {"candidates": len(cand), "selected": len(sel), "culture_leisure_share_selected": round(cc["culture_leisure"] / max(len(sel), 1), 3), "culture_leisure_share_candidates": round(pool_cc["culture_leisure"] / len(cand), 3), "culture_leisure_share_store": round(store["culture_leisure"] / n_store, 3),
       "condition_proposal_share_selected": round(sum(c["cond"] for c in sel) / max(len(sel), 1), 3), "condition_proposal_share_candidates": round(sum(c["cond"] for c in cand) / len(cand), 3), "max_per_publisher": max(pubn.values()), "publishers": len(pubn), "topics_short_more_than_20pct": short, "seed": 20261108}
json.dump(sel, open("runs/harvest/pool_v2/select_2000.json", "w")); json.dump(res, open("runs/harvest/pool_v2/summary.json", "w"), indent=1); print(json.dumps(res))
