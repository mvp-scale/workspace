"""Pick the 60 test stories for the user's hand check (decision 2a, data/mm3-train/proof/decisions-131.md): 20 where the CPU reader and Clef
disagree on at least one atom, 20 where both say yes to at least one atom, 20 at random (fixed seed). Per story: the atoms where either says yes
(at most 3) plus one atom both say no, as a check. CPU reader = jury + multi-task (lowest of the voters' scores), each atom's cut-off chosen on
training stories (precision >= 0.8). Writes data/mm3-train/handcheck/items.json; the page never shows which side said what."""
import sys, os, json, glob, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import value_eval as V
S = np.load(f"{V.D}/proof/a1b2-scores.npz"); A = V.ATOMS; te = np.where(V.test)[0]
BASEV = (("glance_full", "a"), ("scholar_full", "b"), ("glance_lead", "agreed"))
Q = {}
for f in glob.glob("/workspace/newsreader/bitmob/batteries/*.json"):
    for c in json.load(open(f))["concerns"]:
        q = list(c["probes"].values())[0]; Q.setdefault(c["atom"], q.replace("Does the story in {file} ", "Does the story ").replace("Does {file} ", "Does the story "))
cpu = np.zeros((len(A), len(te)), bool); clef = np.array([V.L[n]["agreed"][te] for n in A])
for k, n in enumerate(A):
    s = np.minimum(np.minimum.reduce([V.PP[n][v] for v in BASEV]), S["Sg"][:, k]); c = V.prec_cut(s[V.TRN], V.L[n]["agreed"][V.TRN]); cpu[k] = s[te] >= c
rows = {r["id"]: r for r in map(json.loads, open(f"{V.D}/queue.jsonl"))}; rng = np.random.default_rng(42)
dis = [j for j in range(len(te)) if (cpu[:, j] != clef[:, j]).any()]; both = [j for j in range(len(te)) if (cpu[:, j] & clef[:, j]).any() and j not in dis]
pick = list(rng.permutation(dis)[:20]) + list(rng.permutation(both)[:20]); rest = [j for j in range(len(te)) if j not in pick]; pick += list(rng.permutation(rest)[:20])
drawn = {j: g for g, js in (("disagree", pick[:20]), ("both_yes", pick[20:40]), ("random", pick[40:])) for j in js}
items = []
for j in pick:
    i = V.ids[te[j]]; r = rows[i]; yes = [k for k in range(len(A)) if cpu[k, j] or clef[k, j]][:3]; no = [k for k in range(len(A)) if not cpu[k, j] and not clef[k, j]]
    atoms = yes + [int(rng.choice(no))]; rng.shuffle(atoms)
    items.append({"id": i, "title": r["title"], "source": r["source"], "text": " ".join(r["text"].split()[:250]), "group": drawn[j],
                  "atoms": [{"atom": A[k], "question": Q.get(A[k], A[k]), "cpu": bool(cpu[k, j]), "clef": bool(clef[k, j])} for k in atoms]})
rng.shuffle(items)
json.dump({"made": __import__("time").strftime("%Y-%m-%d %H:%M"), "items": items}, open(f"{V.D}/handcheck/items.json", "w"), indent=1)
print(len(items), "stories,", sum(len(x["atoms"]) for x in items), "questions;", {g: sum(x["group"] == g for x in items) for g in ("disagree", "both_yes", "random")})
