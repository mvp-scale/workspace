#!/usr/bin/env python3
"""Summarise probes/embed_zeroshot.py runs next to Clef Flash, Clef Flash Q4 and Jev on the same items.

acc   share answered right (chance: 1/number of options, or the majority share for yes/no sets)
auc   yes/no sets only: how often a random 'yes' item scores higher than a random 'no' item (0.5 = no signal, 1 = perfect).
      It ignores where the yes/no cut-off sits, so it shows whether the embedding carries the signal even when every
      answer lands on one side.
"""
import json, sys
from pathlib import Path

ROOT, RUNS = Path("/workspace/data/embed-zs"), Path("/workspace/data/probe-runs-v2")
REF = ["clef-flash", "clef-flash-q4km", "jev"]


def jl(p): return [json.loads(l) for l in open(p)] if p.exists() else []


def auc(rows):
    pos = [r["cos"]["yes"] - r["cos"]["no"] for r in rows if r["expected"] == "yes"]
    neg = [r["cos"]["yes"] - r["cos"]["no"] for r in rows if r["expected"] == "no"]
    if not pos or not neg: return None
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def ref_auc(rows, exp):
    pos = [r["probs"].get("yes", 0) for r in rows if exp.get(r["task_id"]) == "yes" and r.get("probs")]
    neg = [r["probs"].get("yes", 0) for r in rows if exp.get(r["task_id"]) == "no" and r.get("probs")]
    if not pos or not neg: return None
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def main():
    sets = sys.argv[1:] or sorted({p.stem for p in ROOT.glob("*/*/*.jsonl")})
    runs = sorted(f"{m.name}/{v.name}" for m in ROOT.iterdir() for v in m.iterdir())
    f = lambda x: "  -  " if x is None else f"{x*100:4.0f}%"
    print(f"{'set':<30}{'chance':>7}" + "".join(f"{r.replace('Qwen3-Embedding-', 'Q').replace('all-MiniLM-L6-v2', 'MiniLM').replace('instructed', 'ins').replace('plain', 'pln'):>12}" for r in runs) + "".join(f"{r:>17}" for r in REF))
    for s in sets:
        items = jl(Path("/workspace/probes/v2") / f"{s}.jsonl")
        if not items: continue
        noul = items[0]["question"]["type"] == "noul"
        chance = max(sum(i["expected"] == "yes" for i in items), sum(i["expected"] == "no" for i in items)) / len(items) if noul else 1 / len(items[0]["labels"])
        line = f"{s:<30}{f(chance):>7}"
        for r in runs:
            rows = jl(ROOT / r / f"{s}.jsonl")
            if not rows: line += f"{'':>12}"; continue
            acc = sum(x["correct"] for x in rows) / len(rows)
            line += f"{f(acc) + ('/' + f(auc(rows)).strip() if noul else ''):>12}"
        for m in REF:
            rows = [x for x in jl(RUNS / f"{m}-{s}" / "results.jsonl") if x.get("ok")]
            if not rows: line += f"{'':>17}"; continue
            acc = sum(x["correct"] for x in rows) / len(rows)
            line += f"{f(acc) + ('/' + f(ref_auc(rows, {i['id']: i['expected'] for i in items})).strip() if noul else ''):>17}"
        print(line)
    print("\ncells: accuracy, and for yes/no sets accuracy/auc. ins = question given with the text, pln = text alone.")


if __name__ == "__main__":
    main()
