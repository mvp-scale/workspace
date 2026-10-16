#!/usr/bin/env python3
"""Does a properly defined state object help? Only the state changes; the question, the model and the items stay fixed.

Variants of `state` for every item of six published sets (human labels):
  bare    the text as published (how every benchmark result so far was measured)
  star    {"situation": ..., "task": ..., "action": <the text>}: STAR-style, the question being the result; one situation and
          task per set, written before any result and frozen in probes/v2/star_states.json
  filler  the same keys and about the same length, with no information (separates "the right context" from "more words /
          structure")
Scored against the human labels: accuracy (yes/no: P(yes) > 0.5; choice: the top option), AUC for yes/no, and per-item
paired wins/losses against bare with a bootstrap 95% interval on the accuracy difference.

    python probes/star_state_test.py [--model clef-flash-q4km] [--sets a,b]   # writes data/probe-runs-v2/_star/<model>.json
"""
import argparse, json, random, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, "/workspace/demo")
import backends

V2 = Path("/workspace/probes/v2"); OUT = Path("/workspace/data/probe-runs-v2/_star")
SETS = ["emotion_anger", "politeness_deference", "phishing", "manipulation_dialogue", "persuasion_appeals", "checklist_contractnli"]


def states(item, star):
    s, f = star["sets"][item["family_set"]], star["filler"]
    return {"bare": item["state"],
            "star": {"situation": s["situation"], "task": s["task"], "action": item["state"]},
            "filler": {"situation": f["situation"], "task": f["task"], "action": item["state"]}}


def ask(model, state, q):
    for _ in range(3):
        try: return backends.ask(model, state, {"q": q}, timeout=120)["q"]
        except Exception: time.sleep(1)
    return None


def right(item, a):
    if a is None: return None
    if item["question"].get("type", "noul") == "noul": return (a.get("noul", 0) > 0.5) == (item["expected"] == "yes")
    pr = a.get("probabilities") or {}
    return bool(pr) and max(pr, key=pr.get) == item["expected"]


def auc(ps, ys):
    pos = [p for p, y in zip(ps, ys) if y]; neg = [p for p, y in zip(ps, ys) if not y]
    if not pos or not neg: return None
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--model", default="clef-flash-q4km"); ap.add_argument("--sets", default=",".join(SETS)); a = ap.parse_args()
    star = json.load(open(V2 / "star_states.json")); items = []
    for s in a.sets.split(","):
        for l in open(V2 / f"{s}.jsonl"):
            it = json.loads(l); it["family_set"] = s; items.append(it)
    jobs = [(i, v, st) for i, it in enumerate(items) for v, st in states(it, star).items()]
    t0 = time.time()
    with ThreadPoolExecutor(4) as ex:   # Clef runs 4 slots; one question per request
        answers = list(ex.map(lambda j: ask(a.model, j[2], items[j[0]]["question"]), jobs))
    print(f"{len(jobs)} calls in {time.time() - t0:.0f} s, {sum(x is None for x in answers)} failed", flush=True)
    res = {}
    for (i, v, _), ans in zip(jobs, answers): res.setdefault(i, {})[v] = ans
    out = {"model": a.model, "sets": {}, "made": time.time()}
    rng = random.Random(0)
    for s in a.sets.split(",") + ["ALL"]:
        idx = [i for i, it in enumerate(items) if s == "ALL" or it["family_set"] == s]
        R = {v: [right(items[i], res[i][v]) for i in idx] for v in ("bare", "star", "filler")}
        ok = [k for k in range(len(idx)) if all(R[v][k] is not None for v in R)]
        row = {"n": len(ok)}
        for v in R: row[v] = round(sum(R[v][k] for k in ok) / len(ok), 4)
        for v in ("star", "filler"):
            d = [int(R[v][k]) - int(R["bare"][k]) for k in ok]
            boots = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(2000))
            row[v + "_vs_bare"] = {"diff": round(sum(d) / len(d), 4), "ci95": [round(boots[50], 4), round(boots[1949], 4)],
                                   "wins": sum(x > 0 for x in d), "losses": sum(x < 0 for x in d)}
        if s != "ALL" and items[idx[0]]["question"].get("type", "noul") == "noul":
            ys = [items[i]["expected"] == "yes" for i in idx]
            row["auc"] = {v: round(auc([(res[i][v] or {}).get("noul", 0.5) for i in idx], ys), 4) for v in R}
        out["sets"][s] = row
        print(f"{s:24s} n={row['n']:3d}  bare {row['bare']:.3f}  star {row['star']:.3f}  filler {row['filler']:.3f}  "
              f"star-bare {row['star_vs_bare']['diff']:+.3f} {row['star_vs_bare']['ci95']} (+{row['star_vs_bare']['wins']}/-{row['star_vs_bare']['losses']})  "
              f"filler-bare {row['filler_vs_bare']['diff']:+.3f}" + (f"  AUC {row['auc']}" if 'auc' in row else ""), flush=True)
    OUT.mkdir(parents=True, exist_ok=True); json.dump(out, open(OUT / f"{a.model}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
