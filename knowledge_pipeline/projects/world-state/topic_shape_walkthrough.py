"""One article at a time: for a handful of articles, every step of the topic-shape pipeline with that article's own numbers (views, embedding values, nearest articles, UMAP coordinates, cluster at each level and view, label words present or not).
Uses the cached embeddings and UMAP files from topic_shape.py and the settings it chose (runs/harvest/topic_shape.json#chosen).
    UMAP_PKGS=<umap_pkgs> python topic_shape_walkthrough.py -> runs/harvest/topic_shape_walk.json"""
import sys, os, json, re, warnings, collections
sys.path.insert(0, os.environ["UMAP_PKGS"]); warnings.filterwarnings("ignore")
import numpy as np
from sklearn.cluster import HDBSCAN
N = 5000; VIEWS = ["title", "first_sentence", "first_250_words", "whole_article"]
S = json.load(open("runs/harvest/topic_shape.json")); R = [json.loads(l) for _, l in zip(range(N), open("runs/harvest/sample.jsonl"))]; X = [json.loads(l) for _, l in zip(range(N), open("runs/harvest/extract.jsonl"))]
T = []; B = []
for r, x in zip(R, X):
    ti = re.sub(r"\s+", " ", r["title"] or "").strip(); T.append(ti); B.append(x["text"][len(ti) + 2:] if x["text"].startswith(ti) else x["text"])
words = lambda b, k, a=0: " ".join(b.split()[a:a + k])
def first_sentence(b): m = re.search(r"(?<=[a-z0-9\"”’)])[.!?](?=\s+[A-Z“\"])", b[:600]); return b[:m.end()] if m else b[:300]
E = {v: np.load(f"runs/embeds/shape_{v}.npy") for v in VIEWS}; rd = [x["reader"]["topic_top2"][0] for x in X]; sec = [(x["domain_label"] or {}).get("label") for x in X]
labs = {}
for v in VIEWS:
    for lv in ("broad", "specific"):
        cfg = S["chosen"][v][lv]
        if cfg is None: continue
        Z = np.load(f"runs/embeds/shape_{v}_umap{cfg['nn']}.npy"); h = HDBSCAN(min_cluster_size=cfg["mcs"], min_samples=cfg["ms"], cluster_selection_method=cfg["method"], copy=True).fit(Z); labs[(v, lv)] = (h.labels_, h.probabilities_, Z)
for key in labs:  # the re-run must reproduce the cluster sizes in topic_shape.json
    k = f"{key[0]}/{key[1]}"; mine = sorted(collections.Counter(l for l in labs[key][0] if l >= 0).values(), reverse=True); theirs = sorted((c["size"] for c in S["all_clusters"].get(k, [])), reverse=True) if k in S["all_clusters"] else None
    if theirs is not None: assert mine[:len(theirs)] == theirs, ("cluster sizes differ", k)
cl = {k: {c["id"]: c for c in v} for k, v in S["all_clusters"].items()}
names = {}  # label words for any (view, level) from the naming of first_250_words only exist for the 4 saved keys
def label_of(view, lv, c):
    k = f"{view}/{lv}"
    return (cl.get(k, {}).get(c, {}).get("words") or [])[:5] if c >= 0 else None
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
_docs = [words(T[i] + ". " + B[i], 250) for i in range(N)]
_tv = TfidfVectorizer(stop_words=list(ENGLISH_STOP_WORDS | set("said says say new year years time like just also told one get got going make way back could would may still even week day days last first two three according people mr mrs ms".split())), min_df=3, max_df=0.2, token_pattern=r"[A-Za-z][A-Za-z]{2,}", sublinear_tf=True, lowercase=True)
_M = _tv.fit_transform(_docs).tocsr(); _voc = np.array(_tv.get_feature_names_out()); _df = np.asarray((_M > 0).sum(axis=0)).ravel()
def own_words(i, k=8):
    row = _M[i].toarray().ravel(); top = np.argsort(-row)[:k]; return [{"word": str(_voc[j]), "articles_with_it": int(_df[j]), "times_in_this_article": len(re.findall(r"\b" + re.escape(str(_voc[j])) + r"\b", _docs[i], re.I))} for j in top if row[j] > 0]
sim_all = E["first_250_words"] @ E["first_250_words"].T; np.fill_diagonal(sim_all, -1)
simtb = (E["title"] * E["first_250_words"]).sum(axis=1); lb, pb, Zb = labs[("first_250_words", "broad")]; ls, ps, Zs = labs[("first_250_words", "specific")]; lt = labs[("title", "broad")][0]
good = lambda i: len(T[i].split()) >= 5 and simtb[i] >= 0.65 and len(B[i].split()) >= 120
# who to show: typical, edge, noise, title and body disagree - distinct clusters where possible
pick = []; seen = set(); picked = set()
def take(cands, n, kind):
    c_ = 0
    for i in cands:
        if int(i) in picked or not good(i): continue
        key = lb[i]
        if kind != "noise" and key in seen: continue
        pick.append((int(i), kind)); picked.add(int(i)); seen.add(key); c_ += 1
        if c_ == n: break
big = [c for c in sorted(collections.Counter(lb[lb >= 0]), key=lambda c: -(lb == c).sum())]
take([i for c in big[:6] for i in sorted(np.where(lb == c)[0], key=lambda i: -pb[i])[:5]], 4, "typical")
take([i for c in big[:8] for i in sorted(np.where(lb == c)[0], key=lambda i: pb[i])[:5]], 3, "edge")
take([i for i in np.where(lb < 0)[0][:400]], 3, "noise")
names_b = {c: set(cl["first_250_words/broad"][c]["words"][:3]) for c in cl["first_250_words/broad"]}; names_t = {c: set(cl["title/broad"][c]["words"][:3]) for c in cl["title/broad"]}
dis = [i for i in range(N) if lb[i] >= 0 and lt[i] >= 0 and i not in picked and not (names_b[int(lb[i])] & names_t[int(lt[i])]) and pb[i] > 0.7]
take(dis[::7], 3, "title and body in different clusters")
out = []
for i, kind in pick:
    nn = np.argsort(-sim_all[i])[:5]; zd = np.linalg.norm(Zb - Zb[i], axis=1); zd[i] = 1e9; z15 = np.argsort(zd)[:15]; bw = cl["first_250_words/broad"].get(int(lb[i])); sw = cl["first_250_words/specific"].get(int(ls[i]))
    def words_in(c):
        if not c: return []
        txt = (T[i] + " " + words(B[i], 250)).lower(); return [{"word": w["word"], "in_this_article": bool(re.search(r"\b" + re.escape(w["word"]) + r"\b", txt)), "in_cluster": w["in_cluster"], "elsewhere": w["elsewhere"]} for w in c["words_detail"][:6]]
    per_view = []
    for v in VIEWS:
        for lv in ("broad",):
            if (v, lv) not in labs: continue
            l_, p_, _ = labs[(v, lv)]; per_view.append({"view": v, "cluster": int(l_[i]), "membership": round(float(p_[i]), 2), "label": label_of(v, lv, int(l_[i])), "cluster_size": int((l_ == l_[i]).sum()) if l_[i] >= 0 else None})
    nw = len(B[i].split())
    out.append({"idx": int(i), "kind": kind, "domain": R[i]["domain"], "date": (X[i]["source"]["date"] or "date not recorded"), "title": T[i], "first_sentence": first_sentence(B[i]), "first_250_words": words(T[i] + ". " + B[i], 250), "total_words": nw, "chunks": min(-(-nw // 250), 8),
                "embedding": {"dims": int(E["first_250_words"].shape[1]), "first_values": [round(float(v), 3) for v in E["first_250_words"][i][:8]], "length": round(float(np.linalg.norm(E["first_250_words"][i])), 3), "nearest": [{"title": T[j], "similarity": round(float(sim_all[i, j]), 3), "cluster": int(lb[j])} for j in nn], "median_similarity_to_all": round(float(np.median(sim_all[i])), 3), "max_similarity": round(float(sim_all[i].max()), 3)},
                "own_words": own_words(i), "squeezed": [round(float(v), 2) for v in Zb[i]], "umap_neighbours_same_cluster": int(sum(1 for j in z15 if lb[i] >= 0 and lb[j] == lb[i])), "umap_neighbours_noise": int(sum(1 for j in z15 if lb[j] < 0)),
                "broad": {"cluster": int(lb[i]), "membership": round(float(pb[i]), 2), "size": int((lb == lb[i]).sum()) if lb[i] >= 0 else None, "label": (bw or {}).get("words", [])[:5], "label_words": words_in(bw), "our_list_says": (bw or {}).get("v6b_topics", []), "our_list_top_share": (bw or {}).get("top_topic_share")},
                "specific": {"cluster": int(ls[i]), "membership": round(float(ps[i]), 2), "size": int((ls == ls[i]).sum()) if ls[i] >= 0 else None, "label": (sw or {}).get("words", [])[:5], "label_words": words_in(sw), "our_list_says": (sw or {}).get("v6b_topics", []), "our_list_top_share": (sw or {}).get("top_topic_share")},
                "per_view": per_view, "our_reader_topic": rd[i], "url_section": sec[i], "title_body_similarity": round(float(simtb[i]), 3)})
json.dump({"v": "topic-shape-walk-v0", "model": S["embedding"], "reduction": S["reduction"], "articles": out}, open("runs/harvest/topic_shape_walk.json", "w"), indent=1)
for a in out: print(a["kind"], "|", a["title"][:55], "| broad", a["broad"]["cluster"], a["broad"]["label"][:3], a["broad"]["membership"], "| same-cluster nbrs", a["umap_neighbours_same_cluster"], "/15")
