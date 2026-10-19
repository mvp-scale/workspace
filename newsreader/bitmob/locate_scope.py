"""Locate's own job: where does a story land? Clef's scope answer (whole world / one country / one city or region) as truth, test split by id hash.
Compared: Glance alone, Locate features alone (spaCy entities + our country list + actor types), Locate countries-only (our regex: number of
distinct countries per part), and Glance + Locate. Accuracy on test stories where Clef's top option has probability >= 0.6 (Clef is clear)."""
import json, hashlib, re, csv, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
D = "/workspace/data/mm3-train"; F = f"{D}/features"; ids = json.load(open(f"{F}/ids.json")); first = {r["id"]: r for r in map(json.loads, open(f"{D}/queue.jsonl"))}
y = np.array([max(first[i]["answers"]["scope"], key=first[i]["answers"]["scope"].get) for i in ids]); conf = np.array([max(first[i]["answers"]["scope"].values()) for i in ids])
h = np.array([int(hashlib.sha256(i.encode()).hexdigest(), 16) % 5 for i in ids]); tr, te = h != 0, (h == 0) & (conf >= .6)
G = np.load(f"{F}/glance_full.npy"); Lc = np.load(f"{F}/locate.npy"); Lc = StandardScaler().fit(Lc[tr]).transform(Lc)
cn = [r["name"] for r in csv.DictReader(open("/workspace/probes/world-engine/data/countries_world100.csv"))]; CRE = re.compile(r"\b(" + "|".join(map(re.escape, sorted(cn, key=len, reverse=True))) + r")\b")
rows = [first[i] for i in ids]; C = np.array([[len(set(CRE.findall(p))) for p in (r["title"], " ".join(r["text"].split()[:80]), " ".join(r["text"].split()[80:1200]))] for r in rows], float)
print(f"test stories where Clef is clear: {te.sum()} · classes {dict(zip(*np.unique(y[te], return_counts=True)))}")
for name, X in (("Glance", G), ("Locate (spaCy + our lists)", Lc), ("Locate countries-only (our regex)", np.log1p(C)), ("Glance + Locate", np.hstack([G, Lc * 0.1]))):
    m = LogisticRegression(C=2, max_iter=4000, class_weight="balanced").fit(X[tr], y[tr]); print(f"  {name:36s} scope accuracy {np.mean(m.predict(X[te]) == y[te]):.3f}")
print(f"  {'always the most common answer':36s} scope accuracy {np.mean(y[te] == max(set(y[tr]), key=list(y[tr]).count)):.3f}")
