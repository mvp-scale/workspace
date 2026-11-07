"""T42 (pre-registered L1009): is the sparse topic result leakage? Same data and split as sparse_topic_human.py; SGD for speed.
    /workspace/models/embed-zs/.venv/bin/python sparse_leak_check.py   (from projects/world-state)"""
import json, random, collections, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
G = json.load(open('/workspace/data/anchors/mn_ds/gold_T28b.json')); cats = sorted({v['l1'] for v in G.values()})
rows = [json.loads(l) for l in open('/workspace/data/anchors/mn_ds/train.jsonl')]
U = [r for r in rows if r.get('category_level_1') in cats and (r.get('title') or '').strip() and (r.get('content') or '').strip()]
R = [r for r in U if len(r['content']) >= 800]; rng = random.Random(20261105); by = collections.defaultdict(list)
for r in R: by[r['category_level_1']].append(r)
S = []
for c in sorted(by): S += rng.sample(by[c], 100)
ids = {id(r) for r in S}; T = [r for r in U if id(r) not in ids]; tx = lambda r: r['title'] + '. ' + r['content']
def fit(train):
    v = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=300000, sublinear_tf=True); A = v.fit_transform([tx(r) for r in train])
    m = SGDClassifier(loss='log_loss', alpha=2e-6, max_iter=30, tol=None, random_state=0, n_jobs=6).fit(A, [r['category_level_1'] for r in train]); return v, m, A
def top2(v, m, items):
    P = m.predict_proba(v.transform([tx(r) for r in items])); o = np.argsort(-P, 1)[:, :2]; cl = np.array(m.classes_); y = np.array([r['category_level_1'] for r in items])
    return ((cl[o[:, 0]] == y) | (cl[o[:, 1]] == y)), (cl[o[:, 0]] == y)
def wil(k, n):
    p = k / n; z = 1.96; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return round((c - h) / d, 3), round((c + h) / d, 3)
out = {}
v, m, A = fit(T); t2, t1 = top2(v, m, S); out['all_train_within_two'] = round(float(t2.mean()), 4); out['all_train_first'] = round(float(t1.mean()), 4)
Q = v.transform([tx(r) for r in S]); best = np.array((Q @ A.T).max(axis=1).todense()).ravel()      # cosine: TF-IDF rows are L2-normalised
out['near_duplicate_share_cos_0_8'] = round(float((best >= 0.8).mean()), 4); out['near_duplicate_share_cos_0_5'] = round(float((best >= 0.5).mean()), 4)
lo = best < 0.5; out['within_two_where_nearest_below_0_5'] = round(float(t2[lo].mean()), 4); out['n_where_nearest_below_0_5'] = int(lo.sum())
src = collections.Counter(r['source'] for r in S); H = [s for s, _ in src.most_common(3)]; out['held_out_publishers'] = H
Tp = [r for r in T if r['source'] not in H]; Sp = [r for r in S if r['source'] in H]; v2, m2, _ = fit(Tp); a, b = top2(v2, m2, Sp)
out['publisher_holdout_n'] = len(Sp); out['publisher_holdout_within_two'] = round(float(a.mean()), 4); out['publisher_holdout_low'] = wil(int(a.sum()), len(Sp))[0]
Tt = [r for r in T if r['date'] < '2019-09-01']; St = [r for r in S if r['date'] >= '2019-09-01']; v3, m3, _ = fit(Tt); a, b = top2(v3, m3, St)
out['time_holdout_n'] = len(St); out['time_holdout_within_two'] = round(float(a.mean()), 4); out['time_holdout_low'] = wil(int(a.sum()), len(St))[0]
out['same_split_publisher_subset_within_two'] = round(float(t2[[r['source'] in H for r in S]].mean()), 4)
json.dump(out, open('runs/pulse/sparse_leak_check.json', 'w'), indent=1); print(json.dumps(out, indent=1))
