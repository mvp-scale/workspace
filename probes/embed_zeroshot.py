#!/usr/bin/env python3
"""Training-free test: can a ready-made embedding model answer our typed questions by similarity alone?

For each probe item (state, question, options with descriptions) the answer is the option whose description is most
similar (cosine) to the item. Nothing is trained or tuned on the items. Two ways of building the item's vector:

  instructed  the question goes in with the text ("Instruct: <question>\nQuery:<state>"), so the vector is shaped by it
  plain       the text alone, as a classic embedding classifier would see it

Writes per-item rows to <out>/<model>/<variant>/<set>.jsonl and prints accuracy per set.

    python probes/embed_zeroshot.py --model Qwen/Qwen3-Embedding-0.6B --device cuda --sets emotion_fear emotion_anger
"""
import argparse, json, time
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

PROBES = Path("/workspace/probes/v2")


def options(item):
    """(label, description) pairs in the item's label order. noul criteria are keyed true/false; labels are yes/no."""
    q = item["question"]
    crit = q.get("criteria") or {}
    if q["type"] == "noul":
        desc = {"yes": crit.get("true", "Yes. " + q["instructions"]), "no": crit.get("false", "No. " + q["instructions"])}
        return [(lab, desc[lab]) for lab in item["labels"]]
    return [(lab, crit.get(lab, lab)) for lab in item["labels"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--sets", nargs="+", required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--variants", nargs="+", default=["instructed", "plain"])
    ap.add_argument("--limit", type=int, default=0, help="first N items per set (0 = all)")
    ap.add_argument("--max-len", type=int, default=4096)
    ap.add_argument("--out", default="/workspace/data/embed-zs")
    a = ap.parse_args()

    kw = {"torch_dtype": torch.bfloat16} if a.device == "cuda" else {}
    t0 = time.perf_counter()
    m = SentenceTransformer(a.model, device=a.device, model_kwargs=kw)
    m.max_seq_length = min(a.max_len, m.max_seq_length or a.max_len)
    load_s = time.perf_counter() - t0
    qwen = "qwen3-embedding" in a.model.lower()
    tag = a.model.split("/")[-1]
    print(f"{tag} on {a.device}: loaded in {load_s:.1f}s, max_seq_length {m.max_seq_length}, threads {torch.get_num_threads()}")

    for variant in a.variants:
        for s in a.sets:
            items = [json.loads(l) for l in open(PROBES / f"{s}.jsonl")]
            items = items[: a.limit] if a.limit else items
            rows, ms = [], []
            for it in items:
                opts = options(it)
                if variant == "instructed":
                    query = f"Instruct: {it['question']['instructions']}\nQuery:{it['state']}" if qwen else f"{it['question']['instructions']} {it['state']}"
                else:
                    query = it["state"]
                t = time.perf_counter()
                v = m.encode([query] + [d for _, d in opts], normalize_embeddings=True, convert_to_numpy=True)
                if a.device == "cuda": torch.cuda.synchronize()
                ms.append((time.perf_counter() - t) * 1000)
                cos = (v[1:] @ v[0]).astype(float)
                pred = opts[int(np.argmax(cos))][0]
                rows.append({"id": it["id"], "type": it["question"]["type"], "expected": it["expected"], "predicted": pred,
                             "correct": pred == it["expected"], "cos": {lab: round(c, 5) for (lab, _), c in zip(opts, cos)},
                             "ms": round(ms[-1], 2)})
            d = Path(a.out) / tag / variant; d.mkdir(parents=True, exist_ok=True)
            with open(d / f"{s}.jsonl", "w") as f:
                for r in rows: f.write(json.dumps(r) + "\n")
            acc = sum(r["correct"] for r in rows) / len(rows)
            print(f"  {variant:<10} {s:<34} n={len(rows):<4} acc={acc:.3f}  median {np.median(ms):.0f} ms/item")


if __name__ == "__main__":
    main()
