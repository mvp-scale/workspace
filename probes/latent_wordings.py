#!/usr/bin/env python3
"""Latent lab: does asking the same question several ways help the CPU engine?

The CPU engine never reads a question's wording: each question is a classifier trained on Clef's answers. So "asking
several ways" has to happen at training time: Clef (local GPU, :8018, never hosted) answers each of 5 wordings of the
same question, one e5-small classifier is trained per wording, and their answers are averaged.

Two questions (mentions a price: easy; pushes back: harder) x 5 wordings, on a fixed random sample of the intake corpus:
1,000 training-stream windows and 500 held-out test windows (other dialogues). Wording 1 is the library question; its
labels come from the full depth-test labels. Measured on the 500 test windows against two references:
  - Clef with the library wording (what the engine is trained to copy)
  - Clef's consensus: the mean of its P(yes) over the 5 wordings (Clef asked 5 ways)
For: each single wording's classifier, the average of the 5 classifiers, and one classifier trained on the consensus.

    python probes/latent_wordings.py label     # ~8,000 Clef calls, resumable
    python probes/latent_wordings.py eval      # writes data/embed-zs/intake/wordings.json
"""
import json, sys, time
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).parent))
from latent_intake import gate, f1, clef_label
from backends import teacher
from latent_depth import thr_from_oof, spec_of, LAB, BASE


def w(ins, true, false): return {"instructions": ins, "criteria": {"true": true, "false": false}}


WORDINGS = {
    "price": [None,  # the library wording (depth-price labels)
              w("Does the speaker talk about money or what something costs?", "The speaker talks about money or a cost.", "The speaker does not talk about money or a cost."),
              w("Is an amount of money, a fee or a budget referred to in this text?", "An amount of money, a fee or a budget is referred to.", "No amount of money, fee or budget is referred to."),
              w("Does the speaker bring up how much something costs or how much they can spend?", "The speaker brings up a cost or how much they can spend.", "The speaker does not bring up a cost or spending."),
              w("Is there any reference to payment, pricing, spending or a dollar amount?", "There is a reference to payment, pricing, spending or a dollar amount.", "There is no reference to payment, pricing, spending or a dollar amount.")],
    "disagree": [None,
                 w("Does the speaker object to or reject what the other person said?", "The speaker objects to or rejects what was said.", "The speaker does not object to or reject what was said."),
                 w("Is the speaker pushing back, saying no, or arguing against something?", "The speaker pushes back, says no, or argues against something.", "The speaker does not push back, say no, or argue."),
                 w("Does the speaker express disagreement?", "The speaker expresses disagreement.", "The speaker does not express disagreement."),
                 w("Does the speaker resist or challenge a suggestion, claim or request?", "The speaker resists or challenges a suggestion, claim or request.", "The speaker does not resist or challenge anything.")],
}
NAMES = {"price": "Mentions a price", "disagree": "Pushes back"}


def sample():
    split = json.load(open(BASE / "corpus" / "split.json")); rng = np.random.default_rng(11)
    return [int(i) for i in rng.choice(split["stream"], 1000, replace=False)], [int(i) for i in rng.choice(split["test"], 500, replace=False)]


def wording(qid, k): return spec_of(qid, None) if k == 0 else WORDINGS[qid][k]


def labels(qid, k):
    f = LAB / (f"depth-{qid}.jsonl" if k == 0 else f"word-{qid}-{k}.jsonl")
    return {int(r["id"]): float(r["p"]) for r in map(json.loads, open(f))} if f.exists() else {}


def label():
    W = json.load(open(BASE / "corpus" / "windows.json")); tr, te = sample(); ids = tr + te
    for qid in WORDINGS:
        for k in range(1, 5):
            meta = LAB / f"word-{qid}-{k}.meta.json"; tid = teacher()
            if meta.exists() and json.loads(meta.read_text())["teacher"] != tid:  # never mix two teachers in one label file
                raise SystemExit(f"word-{qid}-{k} was labelled by {json.loads(meta.read_text())['teacher']}, not {tid}")
            meta.write_text(json.dumps({"teacher": tid}))
            have = labels(qid, k); todo = [i for i in ids if i not in have]; t0 = time.time()
            for c in range(0, len(todo), 250):
                chunk = todo[c:c + 250]; ps = clef_label([W[i]["text"] for i in chunk], wording(qid, k), lambda m: None)
                with open(LAB / f"word-{qid}-{k}.jsonl", "a") as f:
                    for i, p in zip(chunk, ps):
                        if p is not None: f.write(json.dumps({"id": i, "p": p}) + "\n")
                print(f"{qid} wording {k + 1}: {c + len(chunk)}/{len(todo)} {time.time() - t0:.0f}s", flush=True)


def head(E, idx, y):
    oof = np.zeros(len(idx))
    for a, b in StratifiedKFold(5, shuffle=True, random_state=0).split(E[idx], y):
        oof[b] = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(E[idx][a], y[a]).predict_proba(E[idx][b])[:, 1]
    clf = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(E[idx], y)
    return clf, oof


def score(p_test, oof, y_train, ref):
    t = thr_from_oof(oof, y_train); _, lo, hi = gate(oof, y_train); pred = p_test > t; loc = (p_test < lo) | (p_test > hi); casc = np.where(loc, p_test > hi, ref)
    return {"auc": round(float(roc_auc_score(ref, p_test)), 4), "agree": round(float((pred == ref).mean()), 4), "yes_f1": round(float(f1(pred, ref)), 4),
            "cpu_share": round(float(loc.mean()), 4), "cascade_agree": round(float((casc == ref).mean()), 4)}


def evaluate():
    E = np.load(BASE / "corpus" / "emb_e5.npy"); tr0, te0 = sample(); out = []
    for qid in WORDINGS:
        L = [labels(qid, k) for k in range(5)]
        tr = np.array([i for i in tr0 if all(i in l for l in L)]); te = np.array([i for i in te0 if all(i in l for l in L)])
        Ptr = np.array([[l[i] for i in tr] for l in L]); Pte = np.array([[l[i] for i in te] for l in L])
        cons_tr, cons_te = Ptr.mean(0) > 0.5, Pte.mean(0) > 0.5
        refs = {"library wording": Pte[0] > 0.5, "Clef asked 5 ways": cons_te}
        heads = []
        for k in range(5):
            y = Ptr[k] > 0.5; clf, oof = head(E, tr, y); heads.append((clf.predict_proba(E[te])[:, 1], oof, y))
        avg_p = np.mean([h[0] for h in heads], 0); avg_oof = np.mean([h[1] for h in heads], 0)
        cclf, coof = head(E, tr, cons_tr); cons_p = cclf.predict_proba(E[te])[:, 1]
        res = {"id": qid, "name": NAMES[qid], "n_train": int(len(tr)), "n_test": int(len(te)),
               "wordings": [wording(qid, k)["instructions"] for k in range(5)],
               "yes_rate": [round(float((Pte[k] > 0.5).mean()), 4) for k in range(5)],
               "clef_wordings_agree": round(float(np.mean([((Pte[a] > 0.5) == (Pte[b] > 0.5)).mean() for a in range(5) for b in range(a + 1, 5)])), 4),
               "clef_vs_consensus": [round(float(((Pte[k] > 0.5) == cons_te).mean()), 4) for k in range(5)], "results": {}}
        for rname, ref in refs.items():
            # every system's yes threshold and gate are set on the training stream against the matching training labels
            ytr = Ptr[0] > 0.5 if rname == "library wording" else cons_tr
            r = {"one wording (library)": score(heads[0][0], heads[0][1], ytr if rname == "library wording" else heads[0][2], ref),
                 "best other single wording": None,
                 "average of 5 wordings": score(avg_p, avg_oof, ytr, ref),
                 "one classifier on Clef's 5-way consensus": score(cons_p, coof, ytr, ref)}
            singles = [score(heads[k][0], heads[k][1], heads[k][2], ref) for k in range(1, 5)]
            r["best other single wording"] = max(singles, key=lambda s: s["yes_f1"]); r["single wordings (all 5)"] = [score(heads[0][0], heads[0][1], heads[0][2], ref)] + singles
            res["results"][rname] = r
        out.append(res)
        print(json.dumps({k: v for k, v in res.items() if k != "results"})[:400])
        for rname, r in res["results"].items():
            print(" vs", rname)
            for sname in ("one wording (library)", "best other single wording", "average of 5 wordings", "one classifier on Clef's 5-way consensus"):
                print(f"   {sname:42s}", r[sname])
    json.dump({"questions": out, "made": time.time(), "encoder": "intfloat/e5-small-v2 (CPU)", "teacher": "Clef Flash Q4 (local GPU)"}, open(BASE / "wordings.json", "w"))


if __name__ == "__main__":
    {"label": label, "eval": evaluate}[sys.argv[1]]()
