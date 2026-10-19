"""Does the reading level of a question predict how well it works? Grade = Flesch-Kincaid grade level (syllables estimated by vowel groups).
1) Old battery (dial_attributes.csv, 880 stories): per attribute, Clef's agreement between its two wordings (F1) vs the wordings' grade.
2) Evidence batteries (2,341 stories): per atom, Clef's a~b agreement and CPU (Glance) F1 vs grade.
3) Zero-shot, the embedding engine reading the question itself: potion cosine(story, question) as a score, AUC against Clef's own answer
   to that question, vs the question's grade. Spearman correlations; negative = simpler wording works better."""
import json, os, sys, re, glob, csv, numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import f1_score, roc_auc_score
from model2vec import StaticModel
def syl(w):
    w = w.lower().strip(".,?!;:'\"()"); g = re.findall(r"[aeiouy]+", w); n = len(g) - (w.endswith("e") and len(g) > 1); return max(1, n)
def grade(q):
    q = q.replace("{file}", "the story"); ws = re.findall(r"[A-Za-z'’-]+", q); s = max(1, len(re.findall(r"[.?!]", q)))
    return 0.39 * len(ws) / s + 11.8 * sum(syl(w) for w in ws) / len(ws) - 15.59, len(ws), sum(syl(w) >= 3 for w in ws) / len(ws)
os.environ["WE_RULES"] = "rules_v2"; sys.path.insert(0, "/workspace/probes/world-engine"); import classify as C
lab = [json.loads(l) for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl")]
g1, a1, n1 = [], [], []
for (d, dirn), attrs in C.ATTRS.items():
    for i, a in enumerate(attrs):
        k0, k1 = f"a|{d}|{dirn}|{i}|0", f"a|{d}|{dirn}|{i}|1"
        if k0 not in lab[0]["P"]: continue
        x = np.array([r["P"][k0] >= .5 for r in lab]); y = np.array([r["P"][k1] >= .5 for r in lab])
        if x.sum() + y.sum() < 6: continue
        g1.append((grade(a["question_1"])[0] + grade(a["question_2"])[0]) / 2); n1.append((grade(a["question_1"])[1] + grade(a["question_2"])[1]) / 2); a1.append(f1_score(x, y))
print(f"1) old battery, {len(a1)} attributes: grade median {np.median(g1):.1f}; Spearman(grade, Clef self-agreement) = {spearmanr(g1, a1)[0]:+.2f} (p={spearmanr(g1, a1)[1]:.3f}); (words, agreement) = {spearmanr(n1, a1)[0]:+.2f}")
ev = {}
for f in glob.glob("/workspace/data/mm3-train/eval-evidence-v*.json"): ev.update(json.load(open(f))["atoms"])
qs = {}
for f in glob.glob("/workspace/newsreader/bitmob/batteries/evidence-v*.json"):
    for c in json.load(open(f))["concerns"]: qs[c["atom"]] = c["probes"]
g2, t2, c2 = [], [], []
for atom, e in ev.items():
    g2.append((grade(qs[atom]["a"])[0] + grade(qs[atom]["b"])[0]) / 2); t2.append(e["teacher_self_f1"]); c2.append(e["cpu_f1"])
print(f"2) evidence atoms, {len(g2)}: grade median {np.median(g2):.1f} (old battery {np.median(g1):.1f}); Spearman(grade, Clef self-agreement) = {spearmanr(g2, t2)[0]:+.2f} (p={spearmanr(g2, t2)[1]:.3f})")
ok = [i for i, c in enumerate(c2) if c is not None]; print(f"   Spearman(grade, CPU F1) = {spearmanr([g2[i] for i in ok], [c2[i] for i in ok])[0]:+.2f} over {len(ok)} atoms with a CPU score")
# 3) zero-shot: the engine reads the question
D = "/workspace/data/mm3-train"; rows = {r["id"]: r for r in map(json.loads, open(f"{D}/queue.jsonl"))}; pm = StaticModel.from_pretrained("minishlab/potion-base-32M")
g3, auc3 = [], []
for f in glob.glob(f"{D}/queue-evidence-v*.jsonl"):
    qrows = [json.loads(l) for l in open(f)]; ids = [r["id"] for r in qrows if r["id"] in rows]; Q = {r["id"]: r for r in qrows}
    X = pm.encode([rows[i]["title"] + ". " + rows[i]["text"] for i in ids]); X /= np.linalg.norm(X, axis=1, keepdims=True)
    name = f.split("queue-")[1][:-6]
    for c in json.load(open(f"/workspace/newsreader/bitmob/batteries/{name}.json"))["concerns"]:
        for ang in ("a", "b"):
            q = c["probes"][ang].replace("Does {file} ", "").replace("Does the story in {file} ", "").rstrip("?"); v = pm.encode([q])[0]; v /= np.linalg.norm(v)
            y = np.array([Q[i]["answers"][f"{c['atom']}|{ang}"] >= .5 for i in ids])
            if 5 <= y.sum() <= len(y) - 5: g3.append(grade(c["probes"][ang])[0]); auc3.append(roc_auc_score(y, X @ v))
print(f"3) zero-shot (engine reads the question), {len(auc3)} questions: AUC median {np.median(auc3):.2f}; Spearman(grade, AUC) = {spearmanr(g3, auc3)[0]:+.2f} (p={spearmanr(g3, auc3)[1]:.3f})")
lo, hi = np.percentile(g3, 33), np.percentile(g3, 67)
print(f"   simplest third (grade <= {lo:.1f}): AUC {np.median([a for g, a in zip(g3, auc3) if g <= lo]):.2f} · hardest third (grade >= {hi:.1f}): AUC {np.median([a for g, a in zip(g3, auc3) if g >= hi]):.2f}")
# 4) concreteness proxy: does the question name examples (a list of 3+ items or "such as")? Old battery vs evidence atoms, Clef self-agreement.
ex = lambda q: ("such as" in q) or len(re.findall(r",", q)) >= 2
o_ex = [a for (d, dirn), attrs in C.ATTRS.items() for i, at in enumerate(attrs) for a in [None]]
rows1 = []
for (d, dirn), attrs in C.ATTRS.items():
    for i, at in enumerate(attrs):
        k0, k1 = f"a|{d}|{dirn}|{i}|0", f"a|{d}|{dirn}|{i}|1"
        if k0 not in lab[0]["P"]: continue
        x = np.array([r["P"][k0] >= .5 for r in lab]); y = np.array([r["P"][k1] >= .5 for r in lab])
        if x.sum() + y.sum() >= 6: rows1.append((ex(at["question_1"]) or ex(at["question_2"]), f1_score(x, y)))
rows2 = [(ex(qs[a]["a"]) or ex(qs[a]["b"]), e["teacher_self_f1"]) for a, e in ev.items()]
for name, rs in (("old battery", rows1), ("evidence atoms", rows2)):
    w = [v for e_, v in rs if e_]; wo = [v for e_, v in rs if not e_]
    print(f"4) {name}: names examples {len(w)} (Clef self-agreement median {np.median(w) if w else float('nan'):.2f}) vs no examples {len(wo)} ({np.median(wo) if wo else float('nan'):.2f})")
# 5) do the two wordings mean the same thing? cosine(question 1, question 2) from Scholar (e5-small) vs Clef self-agreement, old battery + evidence atoms
from sentence_transformers import SentenceTransformer
st = SentenceTransformer("intfloat/e5-small-v2", device="cpu")
def sim(a, b):
    v = st.encode(["query: " + a.replace("{file}", "the story"), "query: " + b.replace("{file}", "the story")], normalize_embeddings=True); return float(v[0] @ v[1])
s_old, a_old = [], []
for (d, dirn), attrs in C.ATTRS.items():
    for i, at in enumerate(attrs):
        k0, k1 = f"a|{d}|{dirn}|{i}|0", f"a|{d}|{dirn}|{i}|1"
        if k0 not in lab[0]["P"]: continue
        x = np.array([r["P"][k0] >= .5 for r in lab]); y = np.array([r["P"][k1] >= .5 for r in lab])
        if x.sum() + y.sum() >= 6: s_old.append(sim(at["question_1"], at["question_2"])); a_old.append(f1_score(x, y))
s_new = [sim(qs[a]["a"], qs[a]["b"]) for a in ev]; a_new = [ev[a]["teacher_self_f1"] for a in ev]
S, A = s_old + s_new, a_old + a_new
print(f"5) wording pairs: same-meaning score median old {np.median(s_old):.3f} vs evidence {np.median(s_new):.3f}; Spearman(same-meaning, Clef self-agreement) = {spearmanr(S, A)[0]:+.2f} (p={spearmanr(S, A)[1]:.4f}, n={len(S)})")
q = np.percentile(S, [33, 67]); print(f"   least alike third: agreement {np.median([a for s, a in zip(S, A) if s <= q[0]]):.2f} · most alike third: {np.median([a for s, a in zip(S, A) if s >= q[1]]):.2f}")
