#!/usr/bin/env python3
"""CPU time per call for each embedding model, measured alone (run when nothing else is using the CPU).

One call = encode one input on the CPU with option vectors already cached. Two inputs: a short comment and a
dialogue, each the question plus the text as probes/embed_sweep.py formats it; median of 15 after 3 warm-ups.
Writes cpu_ms into data/embed-zs/sweep/<model>.json (the sweep's own timing can be inflated by concurrent jobs).

    python probes/embed_timing.py BAAI/bge-small-en-v1.5 ...
"""
import json, os, statistics, sys, time
from pathlib import Path

import torch
sys.path.insert(0, str(Path(__file__).parent))
from embed_sweep import PROBES, OUT, fmt, load

for model in sys.argv[1:]:
    fq, _ = fmt(model); m = load(model, "cpu"); res = {}
    for s in ("emotion_anger", "manipulation_dialogue"):
        items = [json.loads(l) for l in open(PROBES / f"{s}.jsonl")][:15]
        qs = [fq(i["question"]["instructions"], i["state"]) for i in items]
        for q in qs[:3]: m.encode([q])
        ts = []
        for q in qs:
            t = time.perf_counter(); m.encode([q]); ts.append((time.perf_counter() - t) * 1000)
        res[s] = round(statistics.median(ts), 2)
    f = OUT / f"{model.split('/')[-1]}.json"
    if f.exists():
        d = json.load(open(f)); d["cpu_ms"] = res; d["cpu_note"] = f"measured alone, {torch.get_num_threads()} threads, plain PyTorch"; json.dump(d, open(f, "w"), indent=1)
    print(f"{model.split('/')[-1]:<34} short {res['emotion_anger']:8.1f} ms   dialogue {res['manipulation_dialogue']:8.1f} ms", flush=True)
    del m
