"""Score harvest v0 against the pre-registration (L1030). Writes runs/harvest/score.json."""
import json, collections, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
H = [json.loads(l) for l in open("runs/harvest/labels.jsonl")]; S = {r["row"]: r for r in map(json.loads, open("runs/harvest/sample.jsonl"))}; n = len(H)
M = [json.loads(l) for l in open("/workspace/data/anchors/mn_ds/train.jsonl")]
k1 = next(k for k in M[0] if "level" in k and "1" in k) if not "category_level_1" in M[0] else "category_level_1"
M = [m for m in M if m.get(k1) and m.get("content")]
vec = TfidfVectorizer(ngram_range=(1, 2), max_features=300000, sublinear_tf=True); X = vec.fit_transform([(m["title"] or "") + ". " + m["content"] for m in M]); clf = LinearSVC(C=0.5).fit(X, [m[k1] for m in M])
D = [h for h in H if "domain_label" in h]; pred = clf.predict(vec.transform([(S[h["row"]]["title"] or "") + ". " + (S[h["row"]]["text"] or "") for h in D]))
ok = np.array([p == h["domain_label"]["label"] for p, h in zip(pred, D)]); by = collections.defaultdict(list)
for h, o in zip(D, ok): by[h["domain_label"]["label"]].append(o)
res = {"articles": n, "domain_label": len(D), "domain_label_share": round(len(D) / n, 4), "agree_overall": round(float(ok.mean()), 4), "agree_by_class": {k: [len(v), round(float(np.mean(v)), 3)] for k, v in by.items()},
       "function_label": sum("function_label" in h for h in H), "with_amount": sum(bool(h["amounts"]) for h in H), "with_amount_share": round(sum(bool(h["amounts"]) for h in H) / n, 4), "with_date": sum(bool(h["dates"]) for h in H), "with_meta_date": sum(bool(h["date"]) for h in H),
       "function_classes": dict(collections.Counter(h["function_label"]["label"] for h in H if "function_label" in h)), "text_k1_key": k1}
json.dump(res, open("runs/harvest/score.json", "w"), indent=1); print(json.dumps(res, indent=1))
conf = collections.defaultdict(collections.Counter); ex = collections.defaultdict(list)
for h, p, o in zip(D, pred, ok):
    L = h["domain_label"]["label"]; conf[L][p] += 1
    if not o and len(ex[L]) < 4: ex[L].append((h["domain_label"]["evidence"], p, S[h["row"]]["title"][:70]))
for L in ("arts, culture, entertainment and media", "economy, business and finance", "lifestyle and leisure", "science and technology"): print(L, conf[L].most_common(4)); [print("   ", e) for e in ex[L]]
ev = collections.defaultdict(lambda: [0, 0])
for h, o in zip(D, ok): ev[h["domain_label"]["evidence"]][0] += 1; ev[h["domain_label"]["evidence"]][1] += int(o)
print({k: (v[0], round(v[1] / v[0], 2)) for k, v in sorted(ev.items(), key=lambda x: -x[1][0])[:14]})
