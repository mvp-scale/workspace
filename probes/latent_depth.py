#!/usr/bin/env python3
"""Latent lab depth test: which KINDS of yes/no question can the CPU engine take over from Clef, and how well?

Fourteen questions in five depth levels, from words on the surface to facts about the world, all asked of the same
4,322 one-speaker conversation windows (data/embed-zs/intake/corpus; split by dialogue into a training stream and a
held-out test set). Clef (the local GPU server on :8018, never a hosted model) is the teacher: ten questions were already
labelled on every window; the four deeper ones are labelled here on a fixed random sample (1,000 stream + 500 test).

For each question, 3 shuffles of the stream x training sizes 100 / 300 / 1,000 / all: an e5-small logistic head (CPU)
learns from Clef's answers. Measured on held-out windows against Clef's answers:
  CPU only     accuracy next to the always-"no" baseline; yes caught (recall) and yes right (precision), with the
               yes threshold set on the training stream's out-of-fold scores (best F1), never on the test set
  ranking      AUC: how often a yes window scores above a no window
  with backup  share answered on the CPU while the cascade keeps >= 97% agreement and yes-F1 >= 0.90 with Clef
               (the same asymmetric gate as latent_intake.py, set on the stream)

    python probes/latent_depth.py label     # Clef labels for the new questions (resumable, ~6 min)
    python probes/latent_depth.py eval      # writes data/embed-zs/intake/depth.json (seconds)
"""
import json, sys, time
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).parent))
from latent_intake import gate, f1, clef_label

BASE = Path("/workspace/data/embed-zs/intake"); LAB = BASE / "labels"
SEED_DIR = Path("/tmp/claude-0/-workspace/7b3ad9cf-3881-44ec-8786-beddd1fbd06d/scratchpad/intake_seed")  # earlier full labels
LEVELS = ["Words on the surface", "What the speaker is doing", "Feelings and relationships", "Reading between the lines", "Facts about the world"]


def q(what, ex):
    return {"instructions": f"Does the text match this description: {what}",
            "criteria": {"true": f'The text matches: {what}. Example: "{ex}"', "false": f"The text does not match: {what}"}, "what": what}


QUESTIONS = [  # id, name, level, spec (existing ones are read from their spec files)
    ("price", "Mentions a price", 0, None), ("apology", "Apologises", 0, None),
    ("question", "Asks a question", 1, None), ("commitment", "Commits to something", 1, None), ("timelimit", "Sets a time limit", 1, None),
    ("disagree", "Pushes back", 1, None),
    ("empathy", "Shows empathy", 2, None), ("rapport", "Builds rapport", 2, None), ("blames", "Blames someone", 2, None),
    ("vague", "Gives a vague answer", 3, None),
    ("implies", "Hints without saying it", 3, q("the speaker hints at or implies something without saying it directly", "Well, some people would have called by now.")),
    ("sarcasm", "Is sarcastic", 3, q("the speaker is being sarcastic or ironic, saying the opposite of what they mean", "Oh great, another meeting. Just what I needed.")),
    ("persuade", "Tries to persuade", 3, q("the speaker tries to persuade or pressure someone to do something", "You really should sign up today, it will only help you.")),
    ("falsefact", "States a false fact", 4, q("the speaker states something about the world that is factually false", "The sun goes around the Earth once a year.")),
]


def spec_of(qid, sp):
    if sp is not None: return sp
    return json.load(open(SEED_DIR / f"{qid}.spec.json"))


def label():
    W = json.load(open(BASE / "corpus" / "windows.json")); split = json.load(open(BASE / "corpus" / "split.json"))
    rng = np.random.default_rng(7)
    ids = list(rng.choice(split["stream"], 1000, replace=False)) + list(rng.choice(split["test"], 500, replace=False))
    LAB.mkdir(parents=True, exist_ok=True)
    for qid, name, lvl, sp in QUESTIONS:
        out = LAB / f"depth-{qid}.jsonl"
        if sp is None:  # copy the existing full labels once
            if not out.exists(): out.write_text(open(SEED_DIR / f"{qid}.labels.jsonl").read())
            continue
        have = {json.loads(l)["id"] for l in open(out)} if out.exists() else set()
        todo = [int(i) for i in ids if int(i) not in have]
        t0 = time.time(); print(qid, "labelling", len(todo), flush=True)
        for k in range(0, len(todo), 200):  # chunks, so a stop loses little
            chunk = todo[k:k + 200]; ps = clef_label([W[i]["text"] for i in chunk], sp, lambda m: None)
            with open(out, "a") as f:
                for i, p in zip(chunk, ps):
                    if p is not None: f.write(json.dumps({"id": i, "p": p}) + "\n")
            print(f"  {qid} {k + len(chunk)}/{len(todo)} {time.time() - t0:.0f}s", flush=True)


def thr_from_oof(oof, y):
    best = (0.5, -1)
    for t in np.unique(np.quantile(oof, np.linspace(0.5, 0.995, 60))):
        s = f1(oof > t, y)
        if s > best[1]: best = (t, s)
    return best[0]


def evaluate():
    E = np.load(BASE / "corpus" / "emb_e5.npy"); split = json.load(open(BASE / "corpus" / "split.json"))
    stream0, test0 = np.array(split["stream"]), np.array(split["test"])
    rows = []
    for qid, name, lvl, sp in QUESTIONS:
        sp = spec_of(qid, sp)
        P = {int(r["id"]): float(r["p"]) for r in map(json.loads, open(LAB / f"depth-{qid}.jsonl"))}
        stream = np.array([i for i in stream0 if i in P]); test = np.array([i for i in test0 if i in P])
        yt = np.array([P[i] > 0.5 for i in test]); pt = np.clip([P[i] for i in test], 1e-6, 1 - 1e-6)
        ent = float(np.mean(-(pt * np.log2(pt) + (1 - pt) * np.log2(1 - pt))))
        sizes = sorted({min(n, len(stream)) for n in (100, 300, 1000, len(stream))})
        curve = []
        for n in sizes:
            runs = []
            for sd in range(3):
                idx = np.random.default_rng(sd).permutation(stream)[:n]; y = np.array([P[i] > 0.5 for i in idx])
                if y.sum() < 5 or (~y).sum() < 5: runs.append(None); continue
                k = int(min(5, y.sum())); oof = np.zeros(n)
                for tr, te in StratifiedKFold(k, shuffle=True, random_state=0).split(E[idx], y):
                    oof[te] = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(E[idx][tr], y[tr]).predict_proba(E[idx][te])[:, 1]
                clf = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(E[idx], y)
                p = clf.predict_proba(E[test])[:, 1]; t = thr_from_oof(oof, y); pred = p > t
                _, lo, hi = gate(oof, y); loc = (p < lo) | (p > hi); casc = np.where(loc, p > hi, yt)
                tp = int((pred & yt).sum())
                runs.append({"acc": float((pred == yt).mean()), "auc": float(roc_auc_score(yt, p)) if 0 < yt.sum() < len(yt) else None,
                             "recall": tp / max(1, int(yt.sum())), "precision": tp / max(1, int(pred.sum())), "f1": float(f1(pred, yt)),
                             "cpu_share": float(loc.mean()), "casc_agree": float((casc == yt).mean()), "positives": int(y.sum())})
            ok = [r for r in runs if r]
            agg = {"n": int(n), "runs": len(ok)}
            for key in ("acc", "auc", "recall", "precision", "f1", "cpu_share", "casc_agree", "positives"):
                v = [r[key] for r in ok if r[key] is not None]
                agg[key] = None if not v else {"mean": round(float(np.mean(v)), 4), "min": round(float(np.min(v)), 4), "max": round(float(np.max(v)), 4)}
            curve.append(agg)
        rows.append({"id": qid, "name": name, "level": lvl, "level_name": LEVELS[lvl], "what": sp.get("what") or sp["instructions"],
                     "instructions": sp["instructions"], "n_stream": int(len(stream)), "n_test": int(len(test)),
                     "yes_rate": round(float(yt.mean()), 4), "test_yes": int(yt.sum()), "always_no": round(float(1 - yt.mean()), 4),
                     "clef_unsure": round(ent, 3), "curve": curve})
        last = curve[-1]
        print(f"{name:26s} L{lvl} yes {yt.mean():5.1%} ({int(yt.sum())}) | n={last['n']} acc {last['acc'] and last['acc']['mean']} vs no {1 - yt.mean():.3f} "
              f"| caught {last['recall'] and last['recall']['mean']} right {last['precision'] and last['precision']['mean']} | CPU share {last['cpu_share'] and last['cpu_share']['mean']}", flush=True)
    json.dump({"levels": LEVELS, "questions": rows, "made": time.time(), "encoder": "intfloat/e5-small-v2 (CPU)", "teacher": "Clef Flash Q4 (local GPU)",
               "bar": {"agree": 0.97, "yes_f1": 0.90}}, open(BASE / "depth.json", "w"))


if __name__ == "__main__":
    {"label": label, "eval": evaluate}[sys.argv[1]]()
