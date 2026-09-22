#!/usr/bin/env python3
"""Decompose and loop: does splitting a dialogue into trailing turn-windows and taking the
max beat scoring the whole text once?

The whole-text score is not re-run here; it is read from the set's existing stored run
(data/probe-runs-v2/<model>-manipulation_dialogue/), the same numbers the Scenario lab
already shows. This script only adds the decomposed side: for each item, split the state into
turns, score every trailing window of `--turns` turns (default 2, the window study's best
spot for manipulation) with the same question, and take the max probability as the
decomposed prediction. Keeps the whole-text score next to the pieces, as the plan asks.

  python3 probes/lab_decompose.py --model kev-4b --set manipulation_dialogue --n 40 --turns 2

Local models only: the hosted backend is refused here (spend goes through the UI). Records
are per item, resumable, and never written to data/bench/.
"""
import argparse, json, random, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demo"))
import server  # noqa: E402

PROBES = ROOT / "probes" / "v2"
RUNS = ROOT / "data" / "probe-runs-v2"
OUT = RUNS / "_decompose"
TURN_RE = re.compile(r"^(Person\d+|[A-Z][a-zA-Z]*):\s?(.*)$")


def load(set_id):
    return [json.loads(l) for l in (PROBES / f"{set_id}.jsonl").read_text().splitlines() if l.strip()]


def whole_scores(model, set_id):
    """{item id: {predicted, correct}} from the set's existing stored run; None if there is none."""
    p = RUNS / f"{model}-{set_id}" / "results.jsonl"
    if not p.exists():
        return None
    return {r["task_id"]: {"predicted": r["predicted"], "correct": r["correct"]} for r in map(json.loads, p.read_text().splitlines()) if r.get("ok")}


def split_turns(state):
    lines = [l for l in state.splitlines() if l.strip()]
    return lines if all(TURN_RE.match(l) for l in lines) else None  # only decompose real turn-structured dialogues


def windows(turns, k):
    return ["\n".join(turns[max(0, i - k + 1): i + 1]) for i in range(len(turns))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--set", default="manipulation_dialogue")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--turns", type=int, default=2, help="trailing turns per window (window study: 2-3 turns is best)")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    cfg = server.BACKENDS[a.model]
    if cfg.get("hosted"):
        sys.exit("refusing: hosted model runs only through the UI")
    items = load(a.set)
    whole = whole_scores(a.model, a.set)
    if whole is None:
        sys.exit(f"no stored whole-text run for {a.model} on {a.set}; run demo/bench.sh or demo/bench-batch.sh first")
    rnd = random.Random(a.seed)
    rnd.shuffle(items)
    items = [it for it in items if split_turns(it["state"])][: a.n]
    if not items:
        sys.exit("no turn-structured items in this set (expected 'Speaker: text' lines)")
    d = OUT / a.set / a.model
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"results-k{a.turns}.jsonl"
    done = set()
    if path.exists():
        done = {r["item"] for r in map(json.loads, path.read_text().splitlines()) if not r.get("error")}
    with path.open("a") as out:
        for it in items:
            if it["id"] in done or it["id"] not in whole:
                continue
            turns = split_turns(it["state"])
            wins = windows(turns, a.turns)
            probs, err = [], None
            for w in wins:
                r = server.call(a.model, cfg, {"state": w, "model": "jev-latest", "questions": {"q0": it["question"]}}, whole=True)
                ans = (r.get("answers") or {}).get("q0")
                if "error" in r or not ans or ans.get("noul") is None:
                    err = r.get("error") or "no answer"; break
                probs.append(ans["noul"])
            rec = {"set": a.set, "model": a.model, "item": it["id"], "turns_k": a.turns, "n_windows": len(wins),
                   "expected": it["expected"], "whole_predicted": whole[it["id"]]["predicted"], "whole_correct": whole[it["id"]]["correct"]}
            if err:
                rec["error"] = err
            else:
                dec_p = max(probs)
                dec_pred = "yes" if dec_p >= 0.5 else "no"
                rec.update(decomposed_p=dec_p, decomposed_predicted=dec_pred, decomposed_correct=(dec_pred == it["expected"]),
                           window_probs=probs, calls=len(wins))
            out.write(json.dumps(rec) + "\n"); out.flush()
    recs = [json.loads(l) for l in path.read_text().splitlines()]
    ok = [r for r in recs if not r.get("error")]
    n = len(ok)
    print(f"{a.model} / {a.set} / k={a.turns}: {n} ok, {len(recs) - n} failed")
    if n:
        wa = sum(r["whole_correct"] for r in ok) / n
        da = sum(r["decomposed_correct"] for r in ok) / n
        calls = sum(r["calls"] for r in ok) / n
        print(f"  whole accuracy      {wa:.2f}  (1 call/item)")
        print(f"  decomposed accuracy {da:.2f}  ({calls:.1f} calls/item avg)")


if __name__ == "__main__":
    main()
