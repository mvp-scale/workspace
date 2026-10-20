"""Proof table: real held-out stories (never trained on), Jev's label vs the CPU model's prediction, per ontology layer.
Model: e5-small-v2 frozen + logistic regression per element (as in bakeoff_baseline.py), same 80/20 split (seed 0).
Prints a table and writes <set>-examples.md. Run (CPU): CUDA_VISIBLE_DEVICES= HF_HUB_OFFLINE=1 /workspace/models/embed-zs/.venv/bin/python newsreader/bitmob/show_examples.py data/trainset/night1.jsonl [N]"""
import sys, json, random, collections, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sentence_transformers import SentenceTransformer
F = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 20
R = [json.loads(l) for l in open(F)]
E = SentenceTransformer("intfloat/e5-small-v2", device="cpu").encode(["query: " + r["input"] for r in R], batch_size=64, normalize_embeddings=True, show_progress_bar=False)
tr, te = train_test_split(np.arange(len(R)), test_size=0.2, random_state=0)
TYPES = ("happened", "announced", "opinion", "forecast")
tc = collections.Counter(r["topic"] for r in R); topic = np.array([r["topic"] if tc[r["topic"]] >= 20 else "other" for r in R])
cc = collections.Counter(r["country"] for r in R); top = {c for c, _ in cc.most_common(15)}; country = np.array([r["country"] if r["country"] in top else "other" for r in R])
kc = collections.Counter(k for r in R for k in r["target_keys"]); KEYS = [k for k, n in kc.items() if n >= 30]
fit = lambda y: LogisticRegression(max_iter=2000, class_weight="balanced").fit(E[tr], y[tr])
m_type = {g: fit(np.array([r["P"][f"g|{g}"] >= 0.5 for r in R])) for g in TYPES}
m_topic, m_country = fit(topic), fit(country)
m_key = {k: fit(np.array([k in r["target_keys"] for r in R])) for k in KEYS}
# show: half random held-out stories, half held-out stories where Jev found condition keys (so key detection is visible)
rng = random.Random(3); te = list(te); withk = [i for i in te if R[i]["target_keys"]]
pick = rng.sample(te, N // 2) + rng.sample([i for i in withk if i not in te[:0]], N - N // 2)
rows, tot = [], collections.Counter()
for i in pick:
    r, e = R[i], E[i:i + 1]
    jt = {g for g in TYPES if r["P"][f"g|{g}"] >= 0.5}; pt = {g: m_type[g].predict_proba(e)[0, 1] for g in TYPES}; pts = {g for g, p in pt.items() if p >= 0.5}
    ptop = m_topic.predict(e)[0]; ptop_p = m_topic.predict_proba(e).max(); pco = m_country.predict(e)[0]
    jk = set(r["target_keys"]) & set(KEYS); untrained = set(r["target_keys"]) - set(KEYS)
    pk = {k: m_key[k].predict_proba(e)[0, 1] for k in KEYS}; pks = {k for k, p in pk.items() if p >= 0.5}
    hit, miss, fa = jk & pks, jk - pks, pks - jk
    tot.update({"type_ok": jt == pts, "topic_ok": ptop == topic[i], "country_ok": pco == country[i], "keys_jev": len(jk), "keys_hit": len(hit), "keys_missed": len(miss), "false_alarms": len(fa), "untrained": len(untrained), "n": 1})
    rows.append((r["title"][:70], r["source"],
                 f"{'✓' if jt == pts else '✗'} Jev {','.join(sorted(jt)) or '-'} / model {','.join(sorted(pts)) or '-'}",
                 f"{'✓' if ptop == topic[i] else '✗'} Jev {topic[i]} / model {ptop} ({ptop_p:.2f})",
                 f"{'✓' if pco == country[i] else '✗'} Jev {country[i]} / model {pco}",
                 "; ".join([f"✓ {k} ({pk[k]:.2f})" for k in sorted(hit)] + [f"✗ missed {k} ({pk[k]:.2f})" for k in sorted(miss)] +
                           [f"✗ false alarm {k} ({pk[k]:.2f})" for k in sorted(fa)] + [f"– no model {k}" for k in sorted(untrained)]) or "✓ none (Jev none, model none)"))
md = ["| # | Headline (source) | Story type | Topic | Country | Condition keys (model probability) |", "|---|---|---|---|---|---|"]
for n, (h, s, ty, tp, co, ks) in enumerate(rows, 1): md.append(f"| {n} | {h} ({s}) | {ty} | {tp} | {co} | {ks} |")
summary = (f"\nOn these {tot['n']} held-out stories: story type exact {tot['type_ok']}/{tot['n']}, topic {tot['topic_ok']}/{tot['n']}, country {tot['country_ok']}/{tot['n']}; "
           f"condition keys Jev found (trained keys) {tot['keys_jev']}: model caught {tot['keys_hit']}, missed {tot['keys_missed']}, false alarms {tot['false_alarms']}; "
           f"keys with no model (too few examples) {tot['untrained']}.")
open(F.replace(".jsonl", "-examples.md"), "w").write(f"# Held-out examples: Jev label vs CPU model (e5-small frozen + logistic regression)\n\nReal stories from {F}, never used in training. Threshold 0.5. ✓ match, ✗ mismatch, – no model.\n\n" + "\n".join(md) + "\n" + summary + "\n")
for n, (h, s, ty, tp, co, ks) in enumerate(rows, 1): print(f"\n{n}. {h}  [{s}]\n   type:    {ty}\n   topic:   {tp}\n   country: {co}\n   keys:    {ks}")
print(summary)
