#!/usr/bin/env python3
"""Diagnostic, not the pipeline: settles whether ATOMIC_THRESHOLD (0.18) and the leaf atomic gate
itself are right, using the exact production question wording, against 90 known-atomic controls
(every gap_category_detail leaf -- each hand-authored as a single fact) and 21 known-compound
controls (the gap_categories themselves -- each structurally a category, by construction, per
layered_walk.py's own leaf-vs-category rule). Same method as the diagnostic that originally set
0.18 (5-vs-5 known-atomic/compound), scaled to the full real library instead of a handful of
hand-picked examples.

Chunks into multiple calls to stay under jeff's JEFF_MAX_QUESTIONS=64 cap (confirmed in
jeff/src/jeff/server/config.py). Records full per-model values -- this is exactly the kind of run
BRIDGE.md says the ledger should have been recording per-model all along.

    python3 foundry/diagnose_atomic_gate.py
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "demo"))
import server  # noqa: E402

MODELS = ["semif", "kev-4b", "so1"]  # same default as layered_walk.py -- a model that's down
                                      # (kev-4b, currently) is silently excluded per-call by
                                      # call_all's existing error tolerance, same as production.
CHUNK = 20  # NOT 40 (this diagnostic's first run): 40 questions/call is far larger than anything
            # this pipeline has ever actually sent (production tops out at 21, gap_categories'
            # own call) and pushed kev-4b into a CUDA OOM crash loop this session. 20 stays safely
            # under that already-proven-fine size.

ATOMIC_Q = ("{text}\n\nQuestion: is this a single, directly checkable requirement -- something a "
            "person could look at the real system and confirm yes or no, without first splitting "
            "it into separate sub-checks?")
ATOMIC_CRITERIA = {
    "true": "A single, directly checkable requirement -- one clear yes/no fact.",
    "false": "Still a category or a compound of more than one checkable thing -- needs to split further.",
}


def call_all(state, questions):
    out = {}
    for model in MODELS:
        cfg = server.BACKENDS[model]
        r = server.call(model, cfg, {"state": state, "model": "jev-latest", "questions": questions}, whole=True)
        if "error" not in r:
            out[model] = r["answers"]
        else:
            print(f"    ! {model} errored: {r.get('error')}", file=sys.stderr)
    return out


def chunks(items, n):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def main():
    world = yaml.safe_load((HERE / "tools" / "world-knowledge.yaml").read_text())

    leaves = []  # (qid, text, expected)
    for cat_id, detail in world.get("gap_category_detail", {}).items():
        for leaf in detail.get("tree", []):
            leaves.append((f"leaf::{leaf['id']}", leaf["text"], "atomic"))
    categories = [(f"cat::{c['id']}", c["text"], "compound") for c in world["gap_categories"]]

    all_items = leaves + categories
    print(f"{len(leaves)} known-atomic leaves, {len(categories)} known-compound categories, "
          f"{len(all_items)} total controls, models: {', '.join(MODELS)}\n")

    results = {}  # qid -> {"text":, "expected":, "per_model": {model: p}}
    state = "Evaluating a library of candidate requirement statements in the abstract, not against any specific idea."
    n_calls = 0
    for chunk in chunks(all_items, CHUNK):
        questions = {qid: {"type": "noul", "instructions": ATOMIC_Q.format(text=text), "criteria": ATOMIC_CRITERIA}
                     for qid, text, _ in chunk}
        per_model = call_all(state, questions)
        n_calls += 1
        print(f"  call {n_calls}: {len(chunk)} questions -> {len(per_model)}/{len(MODELS)} models answered")
        for qid, text, expected in chunk:
            pm = {m: a[qid]["noul"] for m, a in per_model.items() if (a.get(qid) or {}).get("noul") is not None}
            results[qid] = {"text": text, "expected": expected, "per_model": pm}

    out_path = HERE / "runs" / "atomic-gate-diagnostic.jsonl"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        for qid, r in results.items():
            means = list(r["per_model"].values())
            mean = sum(means) / len(means) if means else None
            spread = (max(means) - min(means)) if len(means) > 1 else 0.0
            f.write(json.dumps({"id": qid, **r, "mean": mean, "spread": spread}) + "\n")
    print(f"\nWrote {len(results)} results to {out_path}")

    # Summary
    def group_stats(expected):
        rows = [r for r in results.values() if r["expected"] == expected and r["per_model"]]
        means = [sum(r["per_model"].values()) / len(r["per_model"]) for r in rows]
        return rows, means

    atomic_rows, atomic_means = group_stats("atomic")
    compound_rows, compound_means = group_stats("compound")

    def stats(xs):
        if not xs:
            return None, None
        return sum(xs) / len(xs), (min(xs), max(xs))

    a_mean, a_range = stats(atomic_means)
    c_mean, c_range = stats(compound_means)
    print(f"\nATOMIC leaves   (n={len(atomic_means)}): mean={a_mean:.3f}  range={a_range}")
    print(f"COMPOUND cats   (n={len(compound_means)}): mean={c_mean:.3f}  range={c_range}")

    per_model_means = {m: [] for m in MODELS}
    for r in atomic_rows + compound_rows:
        for m in MODELS:
            if m in r["per_model"]:
                per_model_means[m].append((r["per_model"][m], r["expected"]))
    print("\nPer-model discrimination (mean score on atomic vs compound controls, and separation):")
    for m in MODELS:
        a = [p for p, e in per_model_means[m] if e == "atomic"]
        c = [p for p, e in per_model_means[m] if e == "compound"]
        am = sum(a) / len(a) if a else float("nan")
        cm = sum(c) / len(c) if c else float("nan")
        print(f"  {m:10s}  atomic-mean={am:.3f}  compound-mean={cm:.3f}  separation={am - cm:+.3f}")

    # Threshold sweep: find the value of ATOMIC_THRESHOLD that maximizes correct classification
    # (atomic >= t counted right, compound < t counted right) over the combined mean.
    all_scored = [(sum(r["per_model"].values()) / len(r["per_model"]), r["expected"])
                  for r in results.values() if r["per_model"]]
    best_t, best_acc = None, -1
    for t100 in range(0, 101):
        t = t100 / 100
        correct = sum(1 for p, e in all_scored if (p >= t) == (e == "atomic"))
        acc = correct / len(all_scored)
        if acc > best_acc:
            best_acc, best_t = acc, t
    current_t = 0.18
    current_acc = sum(1 for p, e in all_scored if (p >= current_t) == (e == "atomic")) / len(all_scored)
    print(f"\nCurrent ATOMIC_THRESHOLD=0.18 accuracy on these {len(all_scored)} controls: {current_acc:.1%}")
    print(f"Best possible single threshold: {best_t:.2f}, accuracy: {best_acc:.1%}")


if __name__ == "__main__":
    main()
