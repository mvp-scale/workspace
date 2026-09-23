#!/usr/bin/env python3
"""Hierarchy: a cheap gate question, asked to every item live; the existing stored multi-way
choice answer is reused as the "detail" battery only when the gate says yes -- no re-ask needed.

Built on persuasion_appeals (Persuasion for Good) -- the one published set here with a genuine
"none" class (20 of 140 items) alongside its 6 real technique labels, so a cheap binary gate
("any persuasion technique at all?") has something real to be graded against, distinct from and
complementary to cascade (which escalates across models; this escalates across questions within
one model).

Needs the demo server (python3 demo/server.py) for /api/batch, and the already-stored
persuasion_appeals results at data/probe-runs-v2/<model>-persuasion_appeals/results.jsonl (run
demo/bench.sh or demo/bench-batch.sh first if missing).

    python3 probes/lab_hierarchy.py --backend semif
"""
import argparse, json, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBES = ROOT / "probes" / "v2"
RUNS = ROOT / "data" / "probe-runs-v2"
OUT = ROOT / "data" / "probe-runs-v2" / "_hierarchy"

GATE_Q = {
    "type": "noul",
    "instructions": "Question: does this text use a deliberate technique to persuade the reader of something -- an appeal to emotion, logic, credibility, a personal story, a foot-in-the-door request, or similar -- or is it a neutral statement with no persuasive intent?",
    "criteria": {"true": "Uses a deliberate persuasion technique.", "false": "A neutral statement; no persuasive intent."},
}


def load_items():
    return [json.loads(l) for l in (PROBES / "persuasion_appeals.jsonl").read_text().splitlines() if l.strip()]


def load_flat_results(backend):
    p = RUNS / f"{backend}-persuasion_appeals" / "results.jsonl"
    if not p.is_file():
        sys.exit(f"no stored persuasion_appeals results for {backend} at {p} -- run demo/bench.sh or bench-batch.sh first")
    return {r["task_id"]: r for r in map(json.loads, p.read_text().splitlines()) if r.get("ok")}


def batch(backend, items, base):
    req = urllib.request.Request(base + "/api/batch", json.dumps({"backend": backend, "items": items}).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True)
    ap.add_argument("--base", default="http://127.0.0.1:8100")
    a = ap.parse_args()

    items = load_items()
    flat = load_flat_results(a.backend)
    missing = [it["id"] for it in items if it["id"] not in flat]
    if missing:
        sys.exit(f"{len(missing)} items have no stored flat result for {a.backend} -- run the flat benchmark first")

    print(f"{len(items)} items, asking the gate question live on {a.backend}...", flush=True)
    reqs = [{"state": it["state"], "questions": {"gate": GATE_Q}} for it in items]
    t0 = time.time()
    res = batch(a.backend, reqs, a.base)
    print(f"  done in {time.time() - t0:.0f}s", flush=True)

    records = []
    for it, r in zip(items, res):
        if "error" in r:
            records.append({"id": it["id"], "error": r["error"]})
            continue
        gate_p = r["answers"]["gate"]["noul"]
        flat_r = flat[it["id"]]
        probs = dict(flat_r.get("probs") or {})
        probs_no_none = {k: v for k, v in probs.items() if k != "none"}
        detail_pred = max(probs_no_none, key=probs_no_none.get) if probs_no_none else None
        gate_fires = gate_p is not None and gate_p >= 0.5
        expected = it["expected"]
        hier_pred = ("none" if not gate_fires else detail_pred) if expected == "none" else (detail_pred if gate_fires else "none")
        records.append({
            "id": it["id"], "expected": expected, "gate_p": gate_p, "gate_fires": gate_fires,
            "flat_pred": flat_r.get("predicted"), "flat_correct": bool(flat_r.get("correct")),
            "detail_pred": detail_pred, "hier_pred": hier_pred, "hier_correct": hier_pred == expected,
            "flat_latency_s": flat_r.get("latency_s"),
        })

    ok = [r for r in records if "error" not in r]
    n = len(ok)
    hier_acc = sum(r["hier_correct"] for r in ok) / n if n else 0
    flat_acc = sum(r["flat_correct"] for r in ok) / n if n else 0
    gate_acc = sum((r["gate_fires"] == (r["expected"] != "none")) for r in ok) / n if n else 0
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / f"{a.backend}.json"
    out_path.write_text(json.dumps({
        "backend": a.backend, "n": n, "n_failed": len(records) - n,
        "hier_accuracy": hier_acc, "flat_accuracy": flat_acc, "gate_accuracy": gate_acc,
        "records": records,
    }, indent=1))
    print(f"flat accuracy (existing, full 7-way choice): {flat_acc:.3f}")
    print(f"gate accuracy (any-technique vs none, live): {gate_acc:.3f}")
    print(f"hierarchical accuracy (live gate + reused stored detail): {hier_acc:.3f}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
