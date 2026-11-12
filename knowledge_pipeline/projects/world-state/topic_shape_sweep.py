"""Settings sweep for topic_shape.py on the cached embeddings: PCA dims, min cluster size, min samples, eom/leaf. Reports clusters, noise, NMI against the v6b topic and the URL section.
    /workspace/models/embed-zs/.venv/bin/python topic_shape_sweep.py -> runs/harvest/topic_shape_sweep.json"""
import json, itertools, warnings, numpy as np, collections
warnings.filterwarnings("ignore")
from sklearn.decomposition import PCA
from sklearn.cluster import HDBSCAN
from sklearn.metrics import normalized_mutual_info_score as NMI
X = [json.loads(l) for l in open("runs/harvest/extract.jsonl")]; rd = [x["reader"]["topic_top2"][0] for x in X]; sec = [(x["domain_label"] or {}).get("label") for x in X]
rows = []
def nmi(lab, ref):
    ok = [(l, r) for l, r in zip(lab, ref) if l >= 0 and r is not None]
    return round(NMI([r for _, r in ok], [l for l, _ in ok]), 3) if len(ok) > 30 else None
for view in ("first_250_words", "title"):
    E = np.load(f"runs/embeds/shape_{view}.npy")
    for d in (5, 10, 30):
        Z = PCA(d, random_state=0).fit_transform(E)
        for mcs, ms, method in itertools.product((10, 25, 50), (2, 5), ("eom", "leaf")):
            lab = HDBSCAN(min_cluster_size=mcs, min_samples=ms, cluster_selection_method=method, copy=True).fit_predict(Z); k = int(lab.max()) + 1
            sizes = sorted(collections.Counter(l for l in lab if l >= 0).values(), reverse=True)
            rows.append({"view": view, "pca": d, "mcs": mcs, "ms": ms, "method": method, "clusters": k, "noise": round(float((lab < 0).mean()), 3), "largest_share": round(sizes[0] / len(lab), 3) if sizes else None, "nmi_v6b": nmi(lab, rd), "nmi_section": nmi(lab, sec)})
json.dump(rows, open("runs/harvest/topic_shape_sweep.json", "w"), indent=1)
good = [r for r in rows if 8 <= r["clusters"] <= 80 and r["noise"] <= 0.6 and (r["largest_share"] or 1) <= 0.35]
print(len(rows), "runs;", len(good), "with 8-80 clusters, noise<=60%, largest<=35%")
for r in sorted(good, key=lambda r: -(r["nmi_v6b"] or 0))[:12]: print(r)
