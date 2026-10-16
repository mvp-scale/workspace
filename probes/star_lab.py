"""STAR framing lab, live: does framing the text change what the CPU classifier learns? Runs inside the CPU engine
(probes/cpu_engine.py) with its own encoder (e5-small, the engine's runtime), computed from the raw files when asked.

Method (stated before any run, shown on the page):
  data      published sets with human labels (probes/v2/<set>.jsonl). Anger, politeness, phishing train on their pools
            (data/embed-zs/pools/<set>.jsonl, probe texts excluded) and test on the published items; manipulation and
            persuasion have no pool, so 5-fold cross-validation inside the set. Contract clauses are excluded: their label
            depends on a statement inside each question, which a text-only classifier never sees.
  variants  bare text; STAR frame (frozen in probes/v2/star_states.json, written before any result); a generic frame of
            similar length (control); or a frame the viewer types. Only the encoder's input string changes.
  classifier  "line": one logistic regression per set, as in the engine; or "neighbours": the majority label of the 10
            training texts nearest by cosine (the "hits" view), same data, same rule.
  rule      STAR "helps" if accuracy rises >= 2 points with a 95% range above zero AND it beats the generic frame;
            "hurts" if it falls >= 2 points with the range below zero; otherwise "no measurable difference".
Every text carries its source (file:line). Vectors are cached in memory for this process only; nothing is written.
"""
import json, random, threading, time
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

ROOT = Path(__file__).resolve().parent.parent
V2, POOLS = ROOT / "probes" / "v2", ROOT / "data" / "embed-zs" / "pools"
SETS = {"emotion_anger": ("Anger", "pool"), "politeness_deference": ("Politeness", "pool"), "phishing": ("Phishing", "pool"),
        "manipulation_dialogue": ("Manipulation in dialogue", "cv"), "persuasion_appeals": ("Persuasion strategy (7 options)", "cv")}
RULE = {"min_points": 2.0}


def _read(path, text_key, label_key):
    rows = []
    for n, line in enumerate(open(path), 1):
        r = json.loads(line)
        rows.append({"text": r[text_key], "label": r[label_key], "source": f"{path.relative_to(ROOT)}:{n}", "id": r.get("id")})
    return rows


class Lab:
    def __init__(self, encode_batch, encoder_name):
        self.enc, self.encoder = encode_batch, encoder_name
        self.star = json.loads((V2 / "star_states.json").read_text())
        self.cache, self.lock = {}, threading.Lock()

    # -- data and framing ------------------------------------------------------------------------------------------
    def items(self, s): return _read(V2 / f"{s}.jsonl", "state", "expected")
    def pool(self, s): return _read(POOLS / f"{s}.jsonl", "text", "label") if SETS[s][1] == "pool" else None

    def frame(self, kind, s, text, custom=None):
        if kind == "bare": return text
        f = custom if kind == "custom" else (self.star["sets"][s] if kind == "star" else self.star["filler"])
        return f"Situation: {f['situation']} Task: {f['task']} Text: {text}"

    def vecs(self, s, which, kind, custom=None):
        key = (s, which, kind, json.dumps(custom, sort_keys=True) if custom else None)
        with self.lock:
            if key not in self.cache:
                rows = self.items(s) if which == "items" else self.pool(s)
                self.cache[key] = self.enc([self.frame(kind, s, r["text"], custom) for r in rows])
            return self.cache[key]

    def sets(self):
        out = []
        for s, (name, mode) in SETS.items():
            it = self.items(s); p = self.pool(s)
            out.append({"id": s, "name": name, "mode": mode, "items": len(it), "pool": len(p) if p else None,
                        "labels": sorted({r["label"] for r in it}), "star": self.star["sets"][s]})
        return {"sets": out, "filler": self.star["filler"], "encoder": self.encoder, "rule": RULE,
                "excluded": {"checklist_contractnli": "its label depends on a statement inside each question, which a text-only classifier never sees"}}

    # -- one item: exact strings and nearest training texts, computed now ------------------------------------------
    def item(self, s, i, custom=None):
        items = self.items(s); it = items[i]; train = self.pool(s) or items
        kinds = ["bare", "star", "filler"] + (["custom"] if custom else [])
        out = {"set": s, "index": i, "record": it, "variants": {}}
        for k in kinds:
            q = self.enc([self.frame(k, s, it["text"], custom)])[0]
            T = self.vecs(s, "pool" if self.pool(s) else "items", k, custom if k == "custom" else None)
            sims = T @ q
            if not self.pool(s): sims[i] = -9          # cross-validation sets: never count the item itself
            top = np.argsort(-sims)[:10]
            out["variants"][k] = {"string": "query: " + self.frame(k, s, it["text"], custom),
                                  "nearest": [{"text": train[j]["text"][:200], "label": train[j]["label"], "similarity": round(float(sims[j]), 3), "source": train[j]["source"]} for j in top],
                                  "same_label_in_top10": int(sum(train[j]["label"] == it["label"] for j in top))}
        return out

    # -- a full run: train, test, compare, decide by the stated rule -----------------------------------------------
    @staticmethod
    def _fit_predict(kind_clf, Xtr, ytr, Xte):
        if kind_clf == "neighbours":       # majority label of the 10 most similar training texts (vectors are unit length)
            top = np.argsort(-(Xte @ Xtr.T), axis=1)[:, :10]; out = []
            for row in ytr[top]:
                labs, cnt = np.unique(row, return_counts=True); out.append(labs[np.argmax(cnt)])
            return np.array(out)
        return LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(Xtr, ytr).predict(Xte)

    def run(self, s, n=None, custom=None, clf_kind="line"):
        t0 = time.time(); items = self.items(s); y_te = np.array([r["label"] for r in items])
        kinds = ["bare", "star", "filler"] + (["custom"] if custom else [])
        right = {k: [] for k in kinds}
        if self.pool(s):
            pool = self.pool(s); y_pool = np.array([r["label"] for r in pool]); n = min(n or len(pool), len(pool))
            draws = 1 if n >= len(pool) else 3
            for d in range(draws):
                rng = np.random.default_rng(d); pos = np.where(y_pool == "yes")[0]; neg = np.where(y_pool != "yes")[0]
                idx = np.arange(len(pool)) if n >= len(pool) else np.concatenate([rng.choice(pos, n // 2, replace=False), rng.choice(neg, n - n // 2, replace=False)])
                for k in kinds:
                    Xp, Xt = self.vecs(s, "pool", k, custom if k == "custom" else None), self.vecs(s, "items", k, custom if k == "custom" else None)
                    right[k].append(self._fit_predict(clf_kind, Xp[idx], y_pool[idx], Xt) == y_te)
            setup = f"trained on {n} pool texts{' (3 random draws)' if draws > 1 else ''}, tested on the {len(items)} published items"
        else:
            for sh in range(3):
                for k in kinds:
                    X = self.vecs(s, "items", k, custom if k == "custom" else None); pred = np.empty(len(items), dtype=object)
                    for a, b in StratifiedKFold(5, shuffle=True, random_state=sh).split(X, y_te):
                        pred[b] = self._fit_predict(clf_kind, X[a], y_te[a], X[b])
                    right[k].append(pred == y_te)
            setup = f"5-fold cross-validation inside the {len(items)} items, 3 shuffles"
        per = {k: np.mean(v, axis=0) for k, v in right.items()}
        setup += "; classifier: " + ("vote of the 10 nearest training texts" if clf_kind == "neighbours" else "one logistic regression line (the engine's)")
        rng = random.Random(0); res = {"set": s, "setup": setup, "classifier": clf_kind, "accuracy": {k: round(float(v.mean()), 4) for k, v in per.items()}, "vs_bare": {}}
        for k in kinds[1:]:
            d = list(per[k] - per["bare"]); b = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(2000))
            res["vs_bare"][k] = {"points": round(100 * float(np.mean(d)), 1), "ci95": [round(100 * b[50], 1), round(100 * b[1949], 1)],
                                 "better": int(sum(x > 0 for x in d)), "worse": int(sum(x < 0 for x in d))}
        st, ctl = res["vs_bare"]["star"], res["accuracy"]["star"] - res["accuracy"]["filler"]
        res["verdict"] = ("STAR helps" if st["points"] >= RULE["min_points"] and st["ci95"][0] > 0 and ctl > 0 else
                          "STAR hurts" if st["points"] <= -RULE["min_points"] and st["ci95"][1] < 0 else "No measurable difference")
        res["per_item"] = [{"source": items[i]["source"], "label": items[i]["label"], "text": items[i]["text"][:160],
                            **{k: round(float(per[k][i]), 2) for k in kinds}} for i in range(len(items))]
        res["seconds"] = round(time.time() - t0, 1)
        return res

    # -- the viewer's own text and frame ---------------------------------------------------------------------------
    def try_text(self, s, text, custom=None):
        """Where a typed text lands among the training texts, and what the classifier says, bare vs framed (the set's
        STAR frame, or the viewer's own). Training texts are reframed the same way, as they would be in training."""
        train = self.pool(s) or self.items(s); y = np.array([r["label"] for r in train])
        out = {"set": s, "text": text, "variants": {}}
        for k in ["bare", "custom" if custom else "star"]:
            T = self.vecs(s, "pool" if self.pool(s) else "items", k, custom if k == "custom" else None)
            q = self.enc([self.frame(k, s, text, custom)])[0]; sims = T @ q; top = np.argsort(-sims)[:10]
            clf = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(T, y)
            pr = dict(zip(clf.classes_, clf.predict_proba(q[None])[0]))
            out["variants"][k] = {"string": "query: " + self.frame(k, s, text, custom), "prediction": max(pr, key=pr.get),
                                  "probabilities": {c: round(float(p), 3) for c, p in pr.items()},
                                  "nearest": [{"text": train[j]["text"][:200], "label": train[j]["label"], "similarity": round(float(sims[j]), 3), "source": train[j]["source"]} for j in top]}
        return out
