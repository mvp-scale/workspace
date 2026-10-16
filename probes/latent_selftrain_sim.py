#!/usr/bin/env python3
"""Simulate the self-training loop: a local CPU model that learns from the teacher's answers as traffic arrives.

Traffic: the 4,322 conversation windows of the intake corpus, in a random order, each a request asking 9 yes/no questions
(the depth-test questions with enough yes cases). The teacher is Clef Flash Q4: its stored answers stand in for Jev, so the
replay costs nothing. Rules, per question, exactly as the loop would run them:
  - the teacher answers everything until the question graduates; every teacher answer becomes a lesson
  - every 100 new lessons, once there are >= 200 lessons with >= 30 yes and >= 30 no: retrain (logistic head), set the
    confidence band on the lessons' out-of-fold scores, graduate only if the band holds the bar (>= 97% agreement and
    yes-F1 >= 0.90 against the teacher; small tolerance as in the intake)
  - graduated: answer locally outside the band; inside it ask the teacher (a new lesson); also send a random 5% of the
    confident answers to the teacher as an audit (also a lesson). Local answers never become lessons.
Encoders: A = static (potion-base-8M, ~0.2 ms per text), B = e5-small int8 (~4 ms), and A->B = static first, e5 only for a
text where some question's static head was unsure, then the teacher. A text is encoded once for all its questions.
Every delivered answer is scored against the teacher's stored answer (the truth this loop can know).

    python probes/latent_selftrain_sim.py      # writes data/embed-zs/intake/selftrain_sim.json
"""
import json, sys, time
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).parent))
from latent_intake import gate, f1, AGREE, F1MIN

BASE = Path("/workspace/data/embed-zs/intake"); LAB = BASE / "labels"
QS = ["price", "question", "commitment", "disagree", "empathy", "rapport", "blames", "vague", "apology"]
MS = {"A": 0.2, "B": 4.0}   # measured CPU ms per text (latent_selftrain notes: potion 0.16-0.3 ms, e5-small int8 3.5-4.3 ms)
AUDIT, EVERY, MIN_N, MIN_POS = 0.05, 100, 200, 30


class Head:
    """One question's learner on one encoder: lessons, a fitted head, a band, graduated or not."""
    def __init__(self, E): self.E, self.idx, self.y, self.clf, self.lo, self.hi, self.grad, self.since = E, [], [], None, -1.0, 2.0, False, 0

    def learn(self, i, yes):
        self.idx.append(i); self.y.append(yes); self.since += 1
        if self.since >= EVERY: self.since = 0; self.refit()

    def refit(self):
        y = np.array(self.y); n = len(y)
        if n < MIN_N or y.sum() < MIN_POS or (~y).sum() < MIN_POS: return
        X = self.E[self.idx]; oof = np.zeros(n)
        for a, b in StratifiedKFold(5, shuffle=True, random_state=0).split(X, y):
            oof[b] = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced").fit(X[a], y[a]).predict_proba(X[b])[:, 1]
        share, lo, hi = gate(oof, y)
        loc = (oof < lo) | (oof > hi); casc = np.where(loc, oof > hi, y)
        ok = share > 0 and (casc == y).mean() >= AGREE - 0.01 and f1(casc, y) >= F1MIN - 0.02
        self.clf = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced").fit(X, y)
        self.lo, self.hi, self.grad = lo, hi, bool(ok)

    def read(self, i):
        """'yes' / 'no' when graduated and confident, else None (ask the teacher)."""
        if not self.grad: return None
        p = self.clf.predict_proba(self.E[i:i + 1])[0, 1]
        return "yes" if p > self.hi else "no" if p < self.lo else None


def simulate(encs, labels, order, seed):
    """encs: list of embedding matrices tried in turn (A, or B, or A then B). Returns the trace."""
    rng = np.random.default_rng(seed); tiers = [{q: Head(E) for q in QS} for E in encs]
    stats = {"answers": 0, "local": 0, "local_right": 0, "delivered_right": 0, "teacher": 0, "cpu_ms": 0.0, "by_tier": [0] * len(encs)}
    trace = []
    for t, i in enumerate(order, 1):
        truth = {q: labels[q][i] for q in QS}
        pending = list(QS)
        for k, heads in enumerate(tiers):
            if not pending: break
            stats["cpu_ms"] += MS["A" if len(encs) == 2 and k == 0 else ("A" if encs[k] is ENC["A"] else "B")]
            still = []
            for q in pending:
                ans = heads[q].read(i)
                if ans is None: still.append(q); continue
                audit = rng.random() < AUDIT
                stats["answers"] += 1; stats["local"] += 1; stats["by_tier"][k] += 1
                right = (ans == "yes") == truth[q]; stats["local_right"] += right; stats["delivered_right"] += right
                if audit:   # the audit asks the teacher too; its answer becomes a lesson for every tier
                    stats["teacher"] += 1
                    for hs in tiers: hs[q].learn(i, truth[q])
            pending = still
        for q in pending:   # the teacher answers what no tier was confident about
            stats["answers"] += 1; stats["teacher"] += 1; stats["delivered_right"] += 1
            for hs in tiers: hs[q].learn(i, truth[q])
        if t % 250 == 0 or t == len(order):
            trace.append({"requests": t, "local_share": round(stats["local"] / stats["answers"], 4),
                          "delivered_agree": round(stats["delivered_right"] / stats["answers"], 4),
                          "local_agree": round(stats["local_right"] / max(1, stats["local"]), 4),
                          "teacher_calls": stats["teacher"], "cpu_ms_per_request": round(stats["cpu_ms"] / t, 2),
                          "graduated": sum(tiers[-1][q].grad for q in QS) if len(tiers) == 1 else [sum(h[q].grad for q in QS) for h in tiers],
                          "by_tier": list(stats["by_tier"])})
    return trace


if __name__ == "__main__":
    W = json.load(open(BASE / "corpus" / "windows.json")); texts = [w["text"] for w in W]
    ENC = {"B": np.load(BASE.parent / "engine" / "emb_e5_int8.npy")}
    t0 = time.time()
    from model2vec import StaticModel
    P = StaticModel.from_pretrained("minishlab/potion-base-8M").encode(texts); ENC["A"] = P / np.linalg.norm(P, axis=1, keepdims=True)
    print(f"static vectors for {len(texts)} texts in {time.time() - t0:.1f} s", flush=True)
    labels = {}
    for q in QS:
        P_ = {int(r["id"]): float(r["p"]) > 0.5 for r in map(json.loads, open(LAB / f"depth-{q}.jsonl"))}
        labels[q] = np.array([P_.get(i, False) for i in range(len(texts))])
    out = {}
    for name, encs in (("A static", [ENC["A"]]), ("B e5-small", [ENC["B"]]), ("A->B tiered", [ENC["A"], ENC["B"]])):
        runs = []
        for seed in (0, 1, 2):
            order = np.random.default_rng(100 + seed).permutation(len(texts))
            t0 = time.time(); runs.append(simulate(encs, labels, order, seed)); print(f"{name} seed {seed}: {time.time() - t0:.0f} s; end {runs[-1][-1]}", flush=True)
        out[name] = runs
    json.dump({"questions": QS, "requests": len(texts), "rules": {"audit": AUDIT, "retrain_every": EVERY, "min_lessons": MIN_N, "min_each": MIN_POS,
               "bar": {"agree": AGREE, "yes_f1": F1MIN}}, "cpu_ms": MS, "runs": out}, open(BASE / "selftrain_sim.json", "w"))
