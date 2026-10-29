"""M6 tokenizer parity: runtime tokenizer (tokenizers, tokenizer.json) vs training tokenizer (transformers) on a file.

    python tokenizer_parity.py --tokenizer-dir runs/x/seed42/tokenizer --jsonl dev.jsonl [--runtime-tokenizer ship/x/tokenizer.json] --out parity.json

Both encode every item's `text` with no special tokens, no truncation, no padding (as train.py and runtime.py do).
Pass = 100% of items identical in ids AND offsets. Exit code 1 otherwise. The log holds item ids and token indices
of mismatches only (no text). Run it on every eval file (dev, gold, test) before the gate.
"""
import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import core  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tokenizer-dir", required=True, help="training tokenizer (transformers save_pretrained dir)")
    ap.add_argument("--runtime-tokenizer", help="tokenizer.json the runtime loads (default: <tokenizer-dir>/tokenizer.json)")
    ap.add_argument("--jsonl", required=True, nargs="+")
    ap.add_argument("--out", default="tokenizer_parity.json")
    ap.add_argument("--max-examples", type=int, default=20)
    a = ap.parse_args(argv)

    import tokenizers
    import transformers
    from tokenizers import Tokenizer
    from transformers import AutoTokenizer
    hf = AutoTokenizer.from_pretrained(a.tokenizer_dir)
    tj = a.runtime_tokenizer or str(pathlib.Path(a.tokenizer_dir) / "tokenizer.json")
    rt = Tokenizer.from_file(tj)
    rt.no_truncation()
    rt.no_padding()
    rep = {"training_tokenizer": a.tokenizer_dir, "runtime_tokenizer": tj, "runtime_tokenizer_sha256": core.sha256(tj),
           "transformers": transformers.__version__, "tokenizers": tokenizers.__version__, "files": {}}
    all_ok = True
    for path in a.jsonl:
        n = ok_ids = ok_offs = ntok = 0
        bad = []
        for it in core.read_jsonl(path):
            n += 1
            e = hf(it["text"], add_special_tokens=False, return_offsets_mapping=True)
            hi, ho = list(e["input_ids"]), [tuple(o) for o in e["offset_mapping"]]
            r = rt.encode(it["text"], add_special_tokens=False)
            ri, ro = list(r.ids), [tuple(o) for o in r.offsets]
            ntok += len(hi)
            same_i, same_o = hi == ri, ho == ro
            ok_ids += same_i
            ok_offs += same_o
            if not (same_i and same_o) and len(bad) < a.max_examples:
                first = next((k for k in range(min(len(hi), len(ri))) if hi[k] != ri[k] or ho[k] != ro[k]),
                             min(len(hi), len(ri)))
                bad.append({"id": it.get("id"), "first_diff_token": first, "n_train": len(hi), "n_runtime": len(ri),
                            "ids_equal": same_i, "offsets_equal": same_o})
        f = {"sha256": core.sha256(path), "items": n, "tokens": ntok, "ids_identical": ok_ids,
             "offsets_identical": ok_offs, "pass": n > 0 and ok_ids == n and ok_offs == n, "mismatches": bad}
        rep["files"][path] = f
        all_ok &= f["pass"]
        print(f"[parity] {path}: items {n} ids {ok_ids}/{n} offsets {ok_offs}/{n} pass {f['pass']}", flush=True)
    rep["pass"] = all_ok
    json.dump(rep, open(a.out, "w"), indent=1)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
