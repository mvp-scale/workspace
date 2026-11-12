"""Does the UMAP output size matter? Same embeddings (first 250 words and title, bge-base and bge-small), UMAP to 5, 10, 15, 30 dims, fixed HDBSCAN broad (min cluster 60, min samples 10, eom) and specific (15, 10, eom).
    UMAP_PKGS=<umap_pkgs> python topic_shape_dims_sweep.py -> runs/harvest/topic_shape_dims_sweep.json"""
import sys, os, json, warnings, collections
sys.path.insert(0, os.environ["UMAP_PKGS"]); warnings.filterwarnings("ignore")
import numpy as np, umap
from sklearn.cluster import HDBSCAN
from sklearn.metrics import normalized_mutual_info_score as NMI
X = [json.loads(l) for l in open("runs/harvest/extract.jsonl")]; rd = [x["reader"]["topic_top2"][0] for x in X]; sec = [(x["domain_label"] or {}).get("label") for x in X]
def nmi(lab, ref):
    ok = [(l, r) for l, r in zip(lab, ref) if l >= 0 and r is not None]
    return round(NMI([r for _, r in ok], [l for l, _ in ok]), 3) if len(ok) > 30 else None
rows = []
for model, pfx in (("bge-base 768d", "shape"), ("bge-small 384d", "shape_small")):
    for view in ("first_250_words", "title"):
        E = np.load(f"runs/embeds/{pfx}_{view}.npy")
        for d in (5, 10, 15, 30):
            Z = umap.UMAP(n_components=d, n_neighbors=40, min_dist=0.0, metric="cosine", random_state=42).fit_transform(E)
            for op, (mcs, ms) in (("broad", (60, 10)), ("specific", (15, 10))):
                lab = HDBSCAN(min_cluster_size=mcs, min_samples=ms, copy=True).fit_predict(Z); sz = collections.Counter(l for l in lab if l >= 0)
                rows.append({"model": model, "view": view, "umap_dims": d, "level": op, "clusters": int(lab.max()) + 1, "noise": round(float((lab < 0).mean()), 3), "largest_share": round(max(sz.values()) / len(lab), 3) if sz else None, "nmi_section": nmi(lab, sec), "nmi_v6b": nmi(lab, rd)})
                print(rows[-1], flush=True)
json.dump(rows, open("runs/harvest/topic_shape_dims_sweep.json", "w"), indent=1)
