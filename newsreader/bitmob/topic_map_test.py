"""Extract-then-map test on topic (T-0014). CPU only.

Arms, scored on pilot50 against the stories where Jev and Sonnet chose the same topic (the reference):
  Z     e5 story embedding -> nearest topic definition (no LLM, no training)
  K     spaCy open phrases (topic_phrases.py) -> e5 -> summed similarity to each topic (headline 1.0, description 0.5)
  H     Haiku open phrases (never shown the ontology) -> same mapping (first phrase 1.0, others 0.5)
  M     frozen e5 story embedding + logistic regression trained on night1 Jev topics
  M+K   M with K's 49 topic similarities added as features
Then on night1 (seeded 8,000 / 2,000 split, reference = Jev's direct topic): M vs M+K.
  CUDA_VISIBLE_DEVICES= models/embed-zs/.venv/bin/python newsreader/bitmob/topic_map_test.py
"""
import json, time, random
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression

D, T = "/workspace/data/jury/pilot50/", "/workspace/data/topic-test/"
L = lambda f: [json.loads(l) for l in open(f)]
defs = json.load(open(D + "topic-defs.json")); ids = [d["id"] for d in defs]
e5 = SentenceTransformer("intfloat/e5-small-v2", device="cpu")
enc = lambda xs: e5.encode(["query: " + x for x in xs], batch_size=128, normalize_embeddings=True, show_progress_bar=False)
TV = enc([f"{d['name']}: {d['definition']}" for d in defs])
story_text = lambda r: f"{r['title']}. {(r.get('description') or '')[:250]}"


def map_phrases(groups):
    """groups: per story a list of (phrase, weight). Returns per-story 49-topic score vectors and per-phrase best similarity."""
    flat = [p for g in groups for p, _ in g]; V = enc(flat) if flat else np.zeros((0, TV.shape[1])); S = V @ TV.T
    out, best, i = [], [], 0
    for g in groups:
        v = np.zeros(len(ids))
        for p, w in g: v += w * S[i]; best.append((p, float(S[i].max()), ids[int(S[i].argmax())])); i += 1
        out.append(v / max(1e-9, sum(w for _, w in g)) if g else v)
    return np.array(out), best


def k_groups(rows):
    return [[(p["text"], 1.0 if p["where"] == "headline" else 0.5) for p in r["phrases"]] for r in rows]


# ---- train M and M+K on night1 ----
night = L("/workspace/data/trainset/night1.jsonl"); nph = {r["id"]: r for r in L(T + "night1-phrases.jsonl")}
t0 = time.perf_counter(); XN = enc([story_text(r) for r in night]); t_story = (time.perf_counter() - t0) / len(night)
t0 = time.perf_counter(); KN, _ = map_phrases(k_groups([nph[r["id"]] for r in night])); t_k = (time.perf_counter() - t0) / len(night)
yN = np.array([r["topic"] for r in night]); idx = list(range(len(night))); random.Random(7).shuffle(idx); tr, te = idx[:8000], idx[8000:]
fit = lambda X: LogisticRegression(max_iter=2000, C=4.0).fit(X[tr], yN[tr])
M = fit(XN); MK = fit(np.hstack([XN, KN]))
night_res = {"M": float((M.predict(XN[te]) == yN[te]).mean()), "M+K": float((MK.predict(np.hstack([XN, KN])[te]) == yN[te]).mean()),
             "Z": float((np.array(ids)[(XN[te] @ TV.T).argmax(1)] == yN[te]).mean()), "K": float((np.array(ids)[KN[te].argmax(1)] == yN[te]).mean())}

# ---- pilot50 ----
st = sorted(L(D + "stories.jsonl"), key=lambda r: r["n"])
jev = {r["n"]: r["topic"] for r in L(D + "jev.jsonl")}; son = {r["n"]: r["topic"] for r in L(D + "sonnet-ids.jsonl")}; hai = {r["n"]: r["topic"] for r in L(D + "haiku-ids.jsonl")}
pph = {r["id"]: r for r in L(T + "pilot50-phrases.jsonl")}; hop = {r["n"]: r["topics"] for r in L(D + "haiku-open-topics.jsonl")}
XP = enc([story_text(r) for r in st]); KP, kbest = map_phrases(k_groups([pph[r["id"]] for r in st]))
HP, hbest = map_phrases([[(p, 1.0 if i == 0 else 0.5) for i, p in enumerate(hop[r["n"]])] for r in st])
A = np.array(ids)
arms = {"Z (e5 zero-shot)": A[(XP @ TV.T).argmax(1)], "K (CPU phrases -> map)": A[KP.argmax(1)], "H (Haiku open -> map)": A[HP.argmax(1)],
        "M (e5 classifier)": M.predict(XP), "M+K (classifier + phrase map)": MK.predict(np.hstack([XP, KP]))}
ns = [r["n"] for r in st]; cons = [i for i, n in enumerate(ns) if jev[n] == son[n]]
rows = []
for name, pred in arms.items():
    rows.append({"arm": name, "consensus": int(sum(pred[i] == jev[ns[i]] for i in cons)), "of": len(cons),
                 "jev": int(sum(pred[i] == jev[n] for i, n in enumerate(ns))), "sonnet": int(sum(pred[i] == son[n] for i, n in enumerate(ns)))})
for nm, src in (("Sonnet direct", son), ("Haiku direct", hai), ("Jev direct", jev)):
    rows.append({"arm": nm, "consensus": sum(src[ns[i]] == jev[ns[i]] for i in cons), "of": len(cons), "jev": sum(src[n] == jev[n] for n in ns), "sonnet": sum(src[n] == son[n] for n in ns)})

per_item = [{"n": n, "title": st[i]["title"][:80], "jev": jev[n], "sonnet": son[n], "haiku_open": hop[n], "H": arms["H (Haiku open -> map)"][i],
             "K": arms["K (CPU phrases -> map)"][i], "M": arms["M (e5 classifier)"][i]} for i, n in enumerate(ns)]
low = sorted(hbest, key=lambda x: x[1])[:12]
res = {"pilot50": rows, "night1_heldout_2000_vs_jev": night_res, "ms_per_story": {"e5 story": round(1000 * t_story, 2), "phrase map": round(1000 * t_k, 2)},
       "lowest_similarity_haiku_phrases": low, "jev_other_share_night1": float((yN == "other").mean())}
json.dump({"result": res, "per_item": per_item}, open(T + "topic-map-result.json", "w"), indent=1, default=str)
for r in rows: print(f"{r['arm']:32s} consensus {r['consensus']}/{r['of']}  vs Jev {r['jev']}/50  vs Sonnet {r['sonnet']}/50")
print("night1 held-out vs Jev:", {k: round(v, 3) for k, v in night_res.items()}); print("ms/story:", res["ms_per_story"])
print("Jev 'other' share night1:", round(res["jev_other_share_night1"], 3)); print("lowest-similarity Haiku phrases:"); [print("  ", x) for x in low]
