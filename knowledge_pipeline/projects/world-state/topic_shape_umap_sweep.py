"""UMAP + HDBSCAN settings sweep on the cached embeddings (umap-learn installed in an isolated folder, not the shared venv).
    PYTHONPATH=<umap_pkgs> python topic_shape_umap_sweep.py -> runs/harvest/topic_shape_umap_sweep.json"""
import sys, os, json, itertools, warnings, collections
sys.path.insert(0, os.environ["UMAP_PKGS"]); warnings.filterwarnings("ignore")
import numpy as np, umap
from sklearn.cluster import HDBSCAN
from sklearn.metrics import normalized_mutual_info_score as NMI
X = [json.loads(l) for l in open("runs/harvest/extract.jsonl")]; rd = [x["reader"]["topic_top2"][0] for x in X]; sec = [(x["domain_label"] or {}).get("label") for x in X]
def nmi(lab, ref):
    ok = [(l, r) for l, r in zip(lab, ref) if l >= 0 and r is not None]
    return round(NMI([r for _, r in ok], [l for l, _ in ok]), 3) if len(ok) > 30 else None
rows = []
for view in ("first_250_words", "title"):
    E = np.load(f"runs/embeds/shape_{view}.npy")
    for nn in (15, 40):
        Z = umap.UMAP(n_components=5, n_neighbors=nn, min_dist=0.0, metric="cosine", random_state=42).fit_transform(E)
        np.save(f"runs/embeds/shape_{view}_umap{nn}.npy", Z)
        for mcs, ms, method in itertools.product((15, 30, 60), (5, 10), ("eom", "leaf")):
            lab = HDBSCAN(min_cluster_size=mcs, min_samples=ms, cluster_selection_method=method, copy=True).fit_predict(Z); k = int(lab.max()) + 1
            sizes = sorted(collections.Counter(l for l in lab if l >= 0).values(), reverse=True)
            rows.append({"view": view, "n_neighbors": nn, "mcs": mcs, "ms": ms, "method": method, "clusters": k, "noise": round(float((lab < 0).mean()), 3), "largest_share": round(sizes[0] / len(lab), 3) if sizes else None, "nmi_v6b": nmi(lab, rd), "nmi_section": nmi(lab, sec)})
json.dump(rows, open("runs/harvest/topic_shape_umap_sweep.json", "w"), indent=1)
good = [r for r in rows if 8 <= r["clusters"] <= 80 and r["noise"] <= 0.5 and (r["largest_share"] or 1) <= 0.35]
print(len(rows), "runs;", len(good), "sane")
for r in sorted(good, key=lambda r: -(r["nmi_v6b"] or 0))[:12]: print(r)
