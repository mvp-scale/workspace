"""Topic shape test: embed four views of each article (title, first sentence, first 250 words, whole article = mean of 250-word chunks) with a general embedding (bge-base, untuned, 5090), reduce with UMAP (5 dims, cosine, 40 neighbours; umap-learn in an isolated folder), cluster with HDBSCAN eom: broad (min cluster 60) = major areas, specific (min cluster 15) = finer topics. Embeddings are cached by the first run (PCA version saved at topic_shape.v0.py).
Reports clusters, noise, purity against URL-section labels and the BitMob Domain (v6b) topic, names (distinctive words), agreement between views, and clusters that match none of our topics.
    /workspace/models/embed-zs/.venv/bin/python topic_shape.py [N] -> runs/harvest/topic_shape.json, runs/embeds/shape_<view>.npy"""
import json, re, sys, os, time, collections, itertools, warnings; sys.path.insert(0, os.environ["UMAP_PKGS"]); warnings.filterwarnings("ignore")
import numpy as np, umap
os.environ.setdefault("HF_HOME", "/workspace/data/hf"); os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from sklearn.cluster import HDBSCAN
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import normalized_mutual_info_score as NMI
N = int(sys.argv[1]) if len(sys.argv) > 1 else 5000; PFX = os.environ.get("SHAPE_PREFIX", "shape"); MODEL = os.environ.get("SHAPE_MODEL", "BAAI/bge-base-en-v1.5"); VIEWS = os.environ.get("SHAPE_VIEWS", "title,first_sentence,first_250_words,whole_article").split(","); OUTF = os.environ.get("SHAPE_OUT", "runs/harvest/topic_shape.json"); HW = os.environ.get("SHAPE_HW", "5090 for the embeddings")
R = [json.loads(l) for _, l in zip(range(N), open("runs/harvest/sample.jsonl"))]; X = [json.loads(l) for _, l in zip(range(N), open("runs/harvest/extract.jsonl"))]
assert all(a["row"] == b["row"] for a, b in zip(R, X))
def body_of(x, title): t = x["text"]; return t[len(title) + 2:] if t.startswith(title) else t
T = []; B = []
for r, x in zip(R, X): ti = re.sub(r"\s+", " ", r["title"] or "").strip(); T.append(ti); B.append(body_of(x, ti))
def first_sentence(b): m = re.search(r"(?<=[a-z0-9\"”’)])[.!?](?=\s+[A-Z“\"])", b[:600]); return b[:m.end()] if m else b[:300]
def words(b, k, a=0): w = b.split(); return " ".join(w[a:a + k])
texts = {"title": [t or b[:100] for t, b in zip(T, B)], "first_sentence": [first_sentence(b) or t for b, t in zip(B, T)], "first_250_words": [words(t + ". " + b, 250) for t, b in zip(T, B)]}
chunks = [[words(b, 250, a) for a in range(0, min(len(b.split()), 250 * 8), 250)] or [t] for t, b in zip(T, B)]
E = {v: np.load(f"runs/embeds/{PFX}_{v}.npy") for v in VIEWS}; embed_s = 0
hb.beat("topic-shape", where="[CPU]", task="T42", state="running", why="HDBSCAN topic shape with UMAP on 4 cached views of 5000 articles", success="topic_shape.json written, purity vs URL section and v6b topics reported")
sec = [(x["domain_label"] or {}).get("label") for x in X]; rd = [x["reader"]["topic_top2"][0] for x in X]
def purity(lab, ref):
    ok = [(l, r) for l, r in zip(lab, ref) if l >= 0 and r is not None]
    if not ok: return None, None, 0
    c = collections.defaultdict(collections.Counter)
    for l, r in ok: c[l][r] += 1
    return round(sum(max(v.values()) for v in c.values()) / len(ok), 3), round(NMI([r for _, r in ok], [l for l, _ in ok]), 3), len(ok)
CHOSEN = {}
def umap_for(view, nn):
    f = f"runs/embeds/{PFX}_{view}_umap{nn}.npy"
    if os.path.exists(f): return np.load(f)
    Z = umap.UMAP(n_components=5, n_neighbors=nn, min_dist=0.0, metric="cosine", random_state=42).fit_transform(E[view]); np.save(f, Z); return Z
def choose(view):
    """Same rule for every view: a setting is sane if it gives 8-80 clusters, at most 50 percent noise and no cluster above 35 percent; broad = best v6b-topic NMI among sane settings with 25 or fewer clusters, specific = best among those with 30 or more."""
    rows = []
    for nn in (15, 40):
        Z = umap_for(view, nn)
        for mcs, ms, method in itertools.product((15, 30, 60), (5, 10), ("eom", "leaf")):
            lab = HDBSCAN(min_cluster_size=mcs, min_samples=ms, cluster_selection_method=method, copy=True).fit_predict(Z); k = int(lab.max()) + 1
            if not (8 <= k <= 80) or (lab < 0).mean() > 0.5: continue
            sizes = collections.Counter(l for l in lab if l >= 0)
            if max(sizes.values()) / len(lab) > 0.35: continue
            rows.append({"nn": nn, "mcs": mcs, "ms": ms, "method": method, "clusters": k, "noise": round(float((lab < 0).mean()), 3), "nmi_v6b": purity(lab, rd)[1] or 0})
    out = {}
    for op, ok in (("broad", lambda r: r["clusters"] <= 25), ("specific", lambda r: r["clusters"] >= 30)):
        c = [r for r in rows if ok(r)]; out[op] = max(c, key=lambda r: r["nmi_v6b"]) if c else None
    CHOSEN[view] = out; return out
def run(view, op):
    cfg = CHOSEN[view][op] or choose(view)[op]
    if cfg is None: Z = umap_for(view, 40); h = HDBSCAN(min_cluster_size=60, min_samples=10, copy=True).fit(Z)
    else: Z = umap_for(view, cfg["nn"]); h = HDBSCAN(min_cluster_size=cfg["mcs"], min_samples=cfg["ms"], cluster_selection_method=cfg["method"], copy=True).fit(Z)
    return h.labels_, h.probabilities_, Z
for v_ in VIEWS: choose(v_); print("chosen", v_, CHOSEN[v_])
res = {}; keep = {}
for view in VIEWS:
    for method in ("broad", "specific"):
        lab, pr, Z = run(view, method); cfg = CHOSEN[view][method] or {}; mcs, ms = cfg.get("mcs"), cfg.get("ms"); keep[(view, method)] = (lab, pr, Z); k = int(lab.max()) + 1
        ps, ns, nsec = purity(lab, sec); pr_, nr, nrd = purity(lab, rd)
        res[f"{view}/{method}"] = {"clusters": k, "noise_share": round(float((lab < 0).mean()), 3), "purity_vs_url_section": ps, "nmi_vs_url_section": ns, "labelled_by_section": nsec, "purity_vs_v6b_topic": pr_, "nmi_vs_v6b_topic": nr, "min_cluster_size": mcs, "min_samples": ms, "setting": cfg}
        print(view, method, res[f"{view}/{method}"])
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
NEWS_STOP = set("said says say new year years time like just also told one get got going make way back could would may still even week day days last first two three according people percent mr mrs ms".split()) - {"percent"}
simtb = (E["title"] * E["first_250_words"]).sum(axis=1) if "title" in E and "first_250_words" in E else np.ones(N)
def good_title(i): return len(T[i].split()) >= 4 and simtb[i] >= 0.65
def art(i, pr): return {"title": T[i], "snippet": words(B[i], 38), "p": round(float(pr[i]), 2), "topic": rd[i], "section": sec[i], "url": R[i]["url"]}
def name_clusters(lab, pr, view_texts, topn=8):
    """Name = words that are common in the cluster and rare in the other clusters (c-TF-IDF). Presence is shown too: share of this cluster's articles that contain the word, against the share of all other articles."""
    cv = CountVectorizer(stop_words=list(ENGLISH_STOP_WORDS | NEWS_STOP), min_df=3, max_df=0.2, token_pattern=r"[A-Za-z][A-Za-z]{2,}"); M = cv.fit_transform(view_texts).tocsr(); Mb = (M > 0).tocsc(); vocab = np.array(cv.get_feature_names_out()); k = int(lab.max()) + 1
    cm = np.vstack([np.asarray(M[lab == c].sum(axis=0)).ravel() for c in range(k)]).astype(float); tf = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1); idf = np.log(1 + cm.sum() / np.maximum(cm.sum(axis=0), 1)); sc = tf * idf
    out = []
    for c in range(k):
        mem = np.where(lab == c)[0]; oth = np.where(lab != c)[0]; order = mem[np.argsort(-pr[mem])]; tr = collections.Counter(rd[i] for i in mem); sv = collections.Counter(sec[i] for i in mem if sec[i])
        top = np.argsort(-sc[c])[:topn]; wd = [{"word": str(vocab[j]), "in_cluster": round(float(Mb[:, j][mem].mean()), 3), "elsewhere": round(float(Mb[:, j][oth].mean()), 3)} for j in top]
        gtitles = [i for i in order if good_title(i)] or list(order); edge_pool = [i for i in mem[np.argsort(pr[mem])] if good_title(i)] or list(mem[np.argsort(pr[mem])])
        out.append({"id": c, "size": int(len(mem)), "mean_membership": round(float(pr[mem].mean()), 3), "words": [str(vocab[j]) for j in top], "words_detail": wd, "v6b_topics": [[t, n] for t, n in tr.most_common(3)], "top_topic_share": round(tr.most_common(1)[0][1] / len(mem), 3),
                    "url_sections": [[s_, n] for s_, n in sv.most_common(2)], "examples": [T[i] for i in gtitles[:3]], "member_idx": [int(i) for i in order[:200]], "members": {"central": [art(i, pr) for i in gtitles[:5]], "edge": [art(i, pr) for i in edge_pool[:3]]}})
    return out
main = {}
for view, method in [p for p in (("first_250_words", "broad"), ("first_250_words", "specific"), ("title", "broad"), ("whole_article", "broad")) if p[0] in VIEWS]:
    lab, pr, Z = keep[(view, method)]; cl = name_clusters(lab, pr, texts["first_250_words"]); main[f"{view}/{method}"] = sorted(cl, key=lambda c: -c["size"])
    # clusters that match none of our topics: spread across topics (top share < 0.40)
    res[f"{view}/{method}"]["clusters_split_across_topics"] = [c["id"] for c in cl if c["top_topic_share"] < 0.40 and c["size"] >= 40]
# agreement between views (title vs body views): best-match cluster mapping
def agree(a, b):
    la, lb = keep[a][0], keep[b][0]; best = {}
    for c in range(int(la.max()) + 1):
        cnt = collections.Counter(lb[(la == c) & (lb >= 0)]); best[c] = cnt.most_common(1)[0][0] if cnt else None
    both = (la >= 0) & (lb >= 0); same = sum(1 for i in np.where(both)[0] if best[la[i]] == lb[i]); changed = [int(i) for i in np.where(both)[0] if best[la[i]] != lb[i]]
    return {"both_clustered": int(both.sum()), "agree": same, "agree_share": round(same / max(int(both.sum()), 1), 3), "either_noise_share": round(float((~both).mean()), 3), "changed_idx": changed}
ag = {}; chg = {}
for a, b in [p for p in ((("title", "broad"), ("first_250_words", "broad")), (("first_sentence", "broad"), ("first_250_words", "broad")), (("first_250_words", "broad"), ("whole_article", "broad")), (("title", "broad"), ("whole_article", "broad")), (("title", "specific"), ("first_250_words", "specific")), (("first_250_words", "specific"), ("whole_article", "specific"))) if p[0][0] in VIEWS and p[1][0] in VIEWS]:
    r = agree(a, b); key = f"{a[0]} vs {b[0]} ({a[1]})"; chg[key] = r.pop("changed_idx"); ag[key] = r; print(key, r)
rng = np.random.default_rng(7); sample_changed = []
cn = {c["id"]: c for c in main["first_250_words/broad"]}
for i in rng.choice(chg["title vs first_250_words (broad)"], size=min(30, len(chg["title vs first_250_words (broad)"])), replace=False) if chg["title vs first_250_words (broad)"] else []:
    la, lb = keep[("title", "broad")][0][i], keep[("first_250_words", "broad")][0][i]
    sample_changed.append({"title": T[i], "snippet": words(B[i], 40), "title_cluster": int(la), "body_cluster": int(lb), "body_words": cn[int(lb)]["words"][:5] if int(lb) in cn else None, "url": R[i]["url"]})
sim = (E["title"] * E["first_250_words"]).sum(axis=1); qs = {f"p{q}": round(float(np.percentile(sim, q)), 3) for q in (5, 25, 50, 75, 95)}; low = np.argsort(sim)[:25]
title_body = {"what": "cosine between each article's title vector and first-250-words vector (bge-base); low = headline and story differ", "quantiles": qs, "lowest": [{"title": T[i], "snippet": words(B[i], 40), "sim": round(float(sim[i]), 3), "url": R[i]["url"]} for i in low]}
out = {"v": "topic-shape-v1", "embedding_dims": int(E[VIEWS[0]].shape[1]), "title_body_similarity": title_body, "articles": N, "embedding": MODEL + " (untuned, " + HW + ")", "reduction": "UMAP 5 dims, cosine, 40 neighbours, min_dist 0 (umap-learn 0.5.12 in an isolated folder)", "embed_seconds": "see the embedding run", "settings_chosen_by": "per view, same rule: sane = 8-80 clusters, noise <= 50%, largest cluster <= 35%; broad = best NMI against v6b topic among sane with <= 25 clusters, specific = best among sane with >= 30 clusters. URL-section NMI is not used to choose.", "chosen": CHOSEN, "runs": res, "agreement": ag, "top_clusters": {k: v[:12] for k, v in main.items()}, "all_clusters": {k: [{kk: vv for kk, vv in c.items() if kk != "member_idx"} for c in v] for k, v in main.items()}, "changed_sample": sample_changed,
       "labels": {"url_section_labelled": sum(1 for s in sec if s), "v6b_topics": len(set(rd))}}
json.dump(out, open(OUTF, "w"), indent=1); hb.finish("topic-shape", "done", last=f"{N} articles, embedded in {embed_s}s", progress="topic_shape.json")
