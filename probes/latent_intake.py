#!/usr/bin/env python3
"""Intake: measure whether one TypeSafe yes/no question can be answered locally, and how often.

Given a question (instructions + true/false criteria), Clef labels conversation windows from a fixed corpus
(data/embed-zs/intake/corpus: one-speaker windows, e5-small vectors, split by dialogue into a training stream and a
held-out test set). A logistic head on the frozen e5-small vector learns from the first N Clef labels of the stream. An
asymmetric confidence gate, set only on the stream's out-of-fold predictions, answers "no" below a floor and "yes" above a
ceiling; everything between goes to Clef. On the held-out windows we measure the share answered locally while the
cascade keeps >= 97% agreement with Clef and yes-class F1 >= 0.90 against Clef.

The tier follows from that number, nothing else: Local (Clef answers <= 25%), Hybrid (25-50%), Clef (> 50%, or the bar
cannot be met). The reason is measured too: positives available, and how unsure Clef itself is (mean binary entropy of
its P(yes); 1 = always 50/50).

    python probes/latent_intake.py --spec spec.json            # spec: {"id","name","instructions","criteria":{"true","false"}}
    python probes/latent_intake.py --spec spec.json --labels clef.jsonl   # reuse existing Clef labels {"id": window id, "p": P(yes)}
Writes data/embed-zs/intake/results/<id>.json (status updates while it runs).
"""
import argparse, json, math, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

BASE = Path("/workspace/data/embed-zs/intake"); CLEF = "http://127.0.0.1:8018/v1/systemone"
AGREE, F1MIN = 0.97, 0.90
NS = [100, 200, 400, 800, None]


def save(path, obj): tmp = path.with_suffix(".tmp"); tmp.write_text(json.dumps(obj)); tmp.replace(path)


def clef_label(texts, q, status):
    body = lambda t: json.dumps({"state": t, "questions": {"q": {"type": "noul", "instructions": q["instructions"], "criteria": q["criteria"]}}}).encode()
    def one(t):
        for _ in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(CLEF, body(t), {"Content-Type": "application/json"}), timeout=60) as r:
                    return float(json.loads(r.read())["answers"]["q"]["noul"])
            except Exception: time.sleep(1)
        return None
    out = []; t0 = time.time()
    with ThreadPoolExecutor(4) as ex:  # Clef runs 4 slots; one question per call (batching changes its answers)
        for i, p in enumerate(ex.map(one, texts), 1):
            out.append(p)
            if i % 10 == 0 or i == len(texts):
                rate = i / max(time.time() - t0, 1e-6)
                status(f"Clef labelling {i}/{len(texts)} · {rate:.0f}/s · about {max(0, (len(texts) - i) / rate):.0f} s left")
    return out


def f1(pred, y):
    tp = np.sum(pred & y); fp = np.sum(pred & ~y); fn = np.sum(~pred & y)
    return 2 * tp / (2 * tp + fp + fn) if tp else (1.0 if not y.any() and not pred.any() else 0.0)


def fit(X, y):
    if y.sum() < 2 or (~y).sum() < 2: return None
    return LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(X, y)


def gate(p, y):
    """Largest local share with cascade agreement >= AGREE and yes-F1 >= F1MIN on these (out-of-fold) predictions.
    Local answers no below lo and yes above hi; Clef (whose label is y) answers the rest."""
    qs = np.unique(np.quantile(p, np.linspace(0, 1, 41)))
    best = (0.0, -1.0, 2.0)
    for lo in qs:
        for hi in qs[qs >= lo]:
            loc = (p < lo) | (p > hi)
            pred = np.where(loc, p > hi, y)
            if (pred == y).mean() >= AGREE and f1(pred, y) >= F1MIN and loc.mean() > best[0]: best = (loc.mean(), lo, hi)
    return best


def run(spec, labels=None):
    out_path = BASE / "results" / f"{spec['id']}.json"
    res = {"spec": spec, "status": "starting", "started": time.time()}
    status = lambda m: (res.update(status=m), save(out_path, res))
    W = json.load(open(BASE / "corpus" / "windows.json")); E = np.load(BASE / "corpus" / "emb_e5.npy")
    split = json.load(open(BASE / "corpus" / "split.json"))
    stream, test = np.array(split["stream"]), np.array(split["test"])
    rng = np.random.default_rng(0)
    random_ids = None
    if labels is None:
        # half random (keeps the yes-rate honest), half the windows nearest to the question (where positives are)
        from sentence_transformers import SentenceTransformer
        status("loading the encoder and finding windows close to the question")
        enc = SentenceTransformer("intfloat/e5-small-v2", device="cpu")
        qtext = spec.get("what") or spec["instructions"]
        qv = enc.encode(["query: " + qtext + (" " + spec["example"] if spec.get("example") else "")], normalize_embeddings=True)[0]
        def pick(pool, n):
            pool = rng.permutation(pool); r = pool[: n // 2]
            rest = pool[n // 2:]; near = rest[np.argsort(-(E[rest] @ qv))][: n - n // 2]
            mix = np.empty(len(r) + len(near), dtype=int); mix[0::2][: len(r)] = r; mix[1::2][: len(near)] = near  # interleave
            return mix, set(int(i) for i in r)
        stream, rs = pick(stream, spec.get("n_stream", 800)); test, rt = pick(test, spec.get("n_test", 500))
        random_ids = rs | rt
        ids = np.concatenate([stream, test])
        ps = clef_label([W[i]["text"] for i in ids], spec, status)
        P = {int(i): p for i, p in zip(ids, ps) if p is not None}
    else:
        P = {int(r["id"]): float(r["p"]) for r in map(json.loads, open(labels))}
        stream = rng.permutation(stream)
    stream = np.array([i for i in stream if i in P]); test = np.array([i for i in test if i in P])
    status("training and simulating")
    ys = np.array([P[i] > 0.5 for i in stream]); yt = np.array([P[i] > 0.5 for i in test])
    allp = np.array([P[i] for i in np.concatenate([stream, test])]); pc = np.clip(allp, 1e-6, 1 - 1e-6)
    entropy = float(np.mean(-(pc * np.log2(pc) + (1 - pc) * np.log2(1 - pc))))
    curve = []; last = None
    for n in NS:
        m = len(stream) if n is None else min(n, len(stream))
        if n is not None and n >= len(stream): continue
        idx = stream[:m]; y = ys[:m]
        row = {"n": int(m), "positives": int(y.sum())}
        clf = fit(E[idx], y)
        if clf is None or y.sum() < 5:
            row.update(local_share=0.0, agree=None, yes_f1=None, note="too few positives to train"); curve.append(row); continue
        oof = np.zeros(m)
        k = int(min(5, y.sum(), (~y).sum()))
        for tr, te in StratifiedKFold(k, shuffle=True, random_state=0).split(E[idx], y):
            c = fit(E[idx][tr], y[tr]); oof[te] = c.predict_proba(E[idx][te])[:, 1] if c is not None else 0.5
        share, lo, hi = gate(oof, y)
        pt = clf.predict_proba(E[test])[:, 1]
        loc = (pt < lo) | (pt > hi); pred = np.where(loc, pt > hi, yt)
        from sklearn.metrics import roc_auc_score
        row.update(local_share=round(float(loc.mean()), 4), agree=round(float((pred == yt).mean()), 4), yes_f1=round(float(f1(pred, yt)), 4),
                   lo=round(float(lo), 4), hi=round(float(hi), 4), auc_vs_clef=round(float(roc_auc_score(yt, pt)), 4) if 0 < yt.sum() < len(yt) else None)
        curve.append(row)
        last = (clf, lo, hi, pt, loc)
    final = curve[-1]
    if last is None: final = {"local_share": 0.0, "agree": None, "yes_f1": None}
    clef_share = 1 - final["local_share"]; ok = final.get("agree") is not None and final.get("yes_f1") is not None and final["agree"] >= AGREE - 0.01 and final["yes_f1"] >= F1MIN - 0.02
    enough = ys.sum() >= 30
    tier = "Local" if ok and enough and clef_share <= 0.25 else "Hybrid" if ok and enough and clef_share <= 0.50 else "Clef"
    reasons = [f"Clef would answer {clef_share:.0%} of held-out windows; cascade agreement with Clef {final['agree'] if final.get('agree') is not None else 0:.1%}, yes-F1 {final['yes_f1'] if final.get('yes_f1') is not None else 0:.2f} (bar {AGREE:.0%} and {F1MIN:.2f})"]
    if ys.sum() == 0: reasons.append("Clef found no examples of this in the corpus (chat and film dialogue), even among the windows closest to the question: it needs windows from your own calls")
    elif not enough: reasons.append(f"only {int(ys.sum())} positive examples in the training stream: below the 30 needed to trust the local model")
    elif not ok: reasons.append(f"misses the quality bar on held-out windows, so Clef keeps answering")
    if entropy > 0.5: reasons.append(f"Clef is unsure on this question itself (mean entropy {entropy:.2f}, 1 = coin flip): a more concrete wording may help")
    first_local = next((r["n"] for r in curve if r.get("agree") is not None and 1 - r["local_share"] <= 0.25), None)
    ex = []
    if last is not None:
        clf, lo, hi, pt, loc = last
        order = rng.permutation(len(test))
        for kind, cond in (("local yes", lambda j: loc[j] and pt[j] > hi), ("local no", lambda j: loc[j] and pt[j] < lo), ("asks Clef", lambda j: not loc[j])):
            picks = [j for j in order if cond(j)][:3]
            for j in picks:
                i = int(test[j]); ex.append({"route": kind, "text": W[i]["text"], "local_p": round(float(pt[j]), 3), "clef_p": round(P[i], 3)})
    res.update(status="done", finished=time.time(), tier=tier, reasons=reasons, base_rate=round(float(np.mean([P[i] > 0.5 for i in P if random_ids is None or i in random_ids])), 4), enriched=random_ids is not None,
               positives_stream=int(ys.sum()), teacher_entropy=round(entropy, 3), teacher_unsure=round(float(np.mean((allp > 0.2) & (allp < 0.8))), 4),
               clef_calls=None if labels else int(len(P)), first_n_local=first_local, curve=curve, examples=ex,
               gate={"no_below": final.get("lo"), "yes_above": final.get("hi")}, n_test=int(len(test)), quality_bar={"agree": AGREE, "yes_f1": F1MIN})
    save(out_path, res)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--labels"); a = ap.parse_args()
    r = run(json.load(open(a.spec)), a.labels)
    print(r["spec"]["id"], r["tier"], f"Clef answers {1 - r['curve'][-1]['local_share']:.0%}", r["reasons"])
