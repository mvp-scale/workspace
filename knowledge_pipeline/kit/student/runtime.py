"""S7 runtime: text in, spans (char offsets) + sequence labels + model sha out. CPU, onnxruntime + tokenizers + numpy.

    python runtime.py --model-dir DIR < item.txt > out.json
    python runtime.py --model-dir DIR --jsonl in.jsonl --workers 4 [--threads 1] > out.jsonl

    from runtime import Runtime
    rt = Runtime("DIR"); out = rt.predict(text, item_id="x")

DIR = export.py output: labels.json (contract), the model file it names, tokenizer.json. Ships with core.py and
requirements.txt (pinned). Student path exactly as pipeline/ship/we_classifier.py: tokenizer.json via `tokenizers`
(no truncation, no padding, no special tokens), windows of `window` pieces step `stride` with [CLS]/[SEP], one ONNX
call per window, each token tagged by the window where it is most central, BIO decode per channel, word-boundary snap,
a head = union of its channels. JSONL mode: N spawned worker processes x T ORT threads each (default 1 thread when
workers > 1; on 4 vCPU 4 x 1 beat 1 x 4 by 1.7x in the first project), outputs in input order.
Output per item: {"id", "spans": [{"start", "end", "label", "text"}] sorted by (start, end, head order),
"labels": [...], "label_probs": {...} (only with a sequence head), "model_sha256"}. Deterministic unless --timings.
"""
import argparse
import json
import pathlib
import sys
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import core  # noqa: E402


class Runtime:
    def __init__(self, model_dir, threads=4, expect_sha=None):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        md = pathlib.Path(model_dir)
        self.spec = json.load(open(md / "labels.json", encoding="utf-8"))
        mp = md / self.spec["model_file"]
        self.model_sha256 = core.sha256(mp)
        want = expect_sha or self.spec.get("model_sha256")
        if want and not self.model_sha256.startswith(want):
            raise ValueError(f"model sha {self.model_sha256[:12]} != {want[:12]}")
        self.tok = Tokenizer.from_file(str(md / self.spec.get("tokenizer_file", "tokenizer.json")))
        self.tok.no_truncation()
        self.tok.no_padding()
        self.C, self.S = int(self.spec["cls_id"]), int(self.spec["sep_id"])
        self.W, self.STEP = int(self.spec["window"]), int(self.spec["stride"])
        self.chs = self.spec["channels"]
        self.heads = list(dict.fromkeys(self.chs))
        self.seq = self.spec.get("sequence")
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.sess = ort.InferenceSession(str(mp), so, providers=["CPUExecutionProvider"])
        self.n_out = len(self.sess.get_outputs())
        self.versions = {"onnxruntime": ort.__version__, "numpy": np.__version__,
                         "tokenizers": __import__("tokenizers").__version__, "python": sys.version.split()[0]}
        for n in (64, 128, 256):   # warm-up
            x = np.ones((1, n), np.int64)
            self.sess.run(None, {"input_ids": x, "attention_mask": x})

    def run_window(self, x):
        o = self.sess.run(None, {"input_ids": x, "attention_mask": np.ones_like(x)})
        return o[0][0], (o[1][0] if self.n_out > 1 else None)

    def encode(self, text):
        e = self.tok.encode(text, add_special_tokens=False)
        return list(e.ids), [tuple(o) for o in e.offsets]

    def predict(self, text, item_id="item", timings=None):
        """timings: optional dict, filled with tokenize_ms / model_ms / decode_ms / total_ms / windows"""
        t0 = time.perf_counter()
        ids, offs = self.encode(text)
        t1 = time.perf_counter()
        if ids:
            tags, seqs = core.predict(self.run_window, ids, self.C, self.S, self.W, self.STEP)
        else:
            tags, seqs = None, []
        t2 = time.perf_counter()
        spans = core.decode(text, offs, tags, self.chs)
        order = {h: i for i, h in enumerate(self.heads)}
        flat = sorted(((a, b, h) for h, v in spans.items() for a, b in v), key=lambda s: (s[0], s[1], order[s[2]]))
        out = {"id": item_id, "spans": [{"start": int(a), "end": int(b), "label": h, "text": text[a:b]}
                                        for a, b, h in flat]}
        if self.seq:
            lg = core.pool_seq(seqs, self.seq.get("pool", "max"))
            p = core.sigmoid(lg) if lg is not None else np.zeros(len(self.seq["labels"]))
            out["labels"] = [l for l, v in zip(self.seq["labels"], p) if v >= self.seq.get("threshold", 0.5)]
            out["label_probs"] = {l: round(float(v), 6) for l, v in zip(self.seq["labels"], p)}
        out["model_sha256"] = self.model_sha256
        if timings is not None:
            t3 = time.perf_counter()
            timings.update(tokenize_ms=(t1 - t0) * 1e3, model_ms=(t2 - t1) * 1e3, decode_ms=(t3 - t2) * 1e3,
                           total_ms=(t3 - t0) * 1e3, windows=len(core.starts_of(len(ids), self.W, self.STEP)) if ids else 0,
                           tokens=len(ids))
        return out


# ----------------------------------------------------------------------------- many items, N processes
_R = None


def _init(model_dir, threads):
    global _R
    _R = Runtime(model_dir, threads)


def _one(it):
    tm = {} if it.get("_timings") else None
    c0 = time.process_time()
    out = _R.predict(it["text"], it.get("id", "item"), timings=tm)
    if tm is not None:
        tm["cpu_ms"] = (time.process_time() - c0) * 1e3
        out["timings_ms"] = {k: round(v, 3) for k, v in tm.items()}
    return out


def predict_many(items, model_dir, workers=4, threads=1, timings=False):
    """Yield outputs in input order; workers > 1 = that many spawned processes with `threads` ORT threads each."""
    items = [dict(it, _timings=timings) for it in items]
    if workers <= 1:
        _init(model_dir, threads)
        yield from map(_one, items)
        return
    import multiprocessing as mp
    with mp.get_context("spawn").Pool(workers, initializer=_init, initargs=(model_dir, threads)) as pool:
        yield from pool.imap(_one, items, chunksize=1)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Text (stdin / --text-file) or --jsonl {id, text} in, spans JSON out.")
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--text-file")
    ap.add_argument("--jsonl")
    ap.add_argument("--id", default="item")
    ap.add_argument("--threads", type=int, default=None, help="ORT threads per process (default 4, or 1 with workers)")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--timings", action="store_true", help="add timings_ms (output no longer deterministic)")
    a = ap.parse_args(argv)
    out = sys.stdout
    if hasattr(out, "reconfigure"):
        out.reconfigure(encoding="utf-8", newline="\n")
    if a.jsonl:
        thr = a.threads or (1 if a.workers > 1 else 4)
        rows = core.read_jsonl(a.jsonl)
        for o in predict_many(rows, a.model_dir, a.workers, thr, a.timings):
            out.write(json.dumps(o, ensure_ascii=False) + "\n")
        return
    text = open(a.text_file, encoding="utf-8", newline="").read() if a.text_file else sys.stdin.read()
    json.dump(Runtime(a.model_dir, a.threads or 4).predict(text, a.id), out, ensure_ascii=False)
    out.write("\n")


if __name__ == "__main__":
    main()
