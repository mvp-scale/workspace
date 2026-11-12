"""Why did broad mode give 12 clusters at 5 UMAP dims but 4 at 10+? Shows where the 5-dim clusters went at 10 dims, and re-tunes the broad setting at each size.
    UMAP_PKGS=<umap_pkgs> python topic_shape_dims_merge.py -> runs/harvest/topic_shape_dims_merge.json"""
import sys, os, json, warnings, collections, itertools
sys.path.insert(0, os.environ["UMAP_PKGS"]); warnings.filterwarnings("ignore")
import numpy as np, umap
from sklearn.cluster import HDBSCAN
from sklearn.metrics import normalized_mutual_info_score as NMI
S = json.load(open("runs/harvest/topic_shape.json")); X = [json.loads(l) for l in open("runs/harvest/extract.jsonl")]; sec = [(x["domain_label"] or {}).get("label") for x in X]
E = np.load("runs/embeds/shape_first_250_words.npy"); names = {c["id"]: c for c in S["all_clusters"]["first_250_words/broad"]}
def nmi(lab):
    ok = [(l, r) for l, r in zip(lab, sec) if l >= 0 and r is not None]; return round(NMI([r for _, r in ok], [l for l, _ in ok]), 3)
Z = {d: umap.UMAP(n_components=d, n_neighbors=40, min_dist=0.0, metric="cosine", random_state=42).fit_transform(E) for d in (5, 10, 15)}
def broad(d, mcs=60, ms=10): return HDBSCAN(min_cluster_size=mcs, min_samples=ms, copy=True).fit_predict(Z[d])
l5, l10 = broad(5), broad(10); big = collections.Counter(l10[l10 >= 0]).most_common(1)[0][0]; rows = []
for c in range(int(l5.max()) + 1):
    m = l5 == c; go = collections.Counter(l10[m]); rows.append({"id5": c, "size": int(m.sum()), "words": names[c]["words"][:6] if c in names else None, "example": names[c]["examples"][0] if c in names else None, "share_into_big_blob_at_10": round(go[big] / m.sum(), 3), "share_noise_at_10": round(go[-1] / m.sum(), 3)})
retune = []
for d in (5, 10, 15):
    for mcs, ms in itertools.product((15, 30, 60), (5, 10)):
        lab = broad(d, mcs, ms); sz = collections.Counter(lab[lab >= 0]); retune.append({"umap_dims": d, "min_cluster_size": mcs, "min_samples": ms, "clusters": int(lab.max()) + 1, "noise": round(float((lab < 0).mean()), 3), "largest_share": round(max(sz.values()) / len(lab), 3) if sz else None, "nmi_section": nmi(lab)})
json.dump({"what": "first 250 words, bge-base, UMAP 40 neighbours, HDBSCAN eom", "clusters_at_5": int(l5.max()) + 1, "clusters_at_10": int(l10.max()) + 1, "big_blob_size_at_10": int((l10 == big).sum()), "where_5_dim_clusters_went": rows, "retune": retune}, open("runs/harvest/topic_shape_dims_merge.json", "w"), indent=1)
for r in rows: print(r["size"], r["words"][:4], "-> into blob", r["share_into_big_blob_at_10"])
for r in retune: print(r)
