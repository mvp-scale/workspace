#!/usr/bin/env python3
"""World-state labelling pipeline. One file, one stage per command, read top to bottom.

    python pipeline.py status              what exists, what has been spent
    python pipeline.py spec                rebuild + validate the labelling spec (free)
    python pipeline.py dry   [N]           build N requests offline and print the worst-case cost (free)
    python pipeline.py smoke               3 items, synchronous (pennies); proves key, model, schema
    python pipeline.py pilot  --yes        the 300 frozen-test stories, as a batch (capped at the spec cap)
    python pipeline.py compare             teacher labels vs Clef labels on those 300 (free)
    python pipeline.py bulk N --cap USD --yes   N pool stories as batches
    python pipeline.py export              turn labels into the Kaggle training files (free)

Rules: every paid stage prints its estimate first and refuses to run without --yes. Every run writes into runs/<name>/
(labels.jsonl, spend.jsonl). The key is read from secrets/vault.env by the kit's labeller and is never printed.
"""
import argparse, json, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[1] / "kit" / "teacher"
PY = str(HERE.parent / ".venv" / "bin" / "python")          # isolated env with the anthropic package
KEYFILE = "/workspace/secrets/vault.env"
SPEC = HERE / "specs" / "world_state_v1.json"
POOL, PILOT = HERE / "data" / "pool.jsonl", HERE / "data" / "pilot300.jsonl"
CLEF = pathlib.Path("/workspace/data/clef-labels/test_fast300.jsonl")


def run(cmd, **kw):
    print("$", " ".join(str(c) for c in cmd if c != KEYFILE), flush=True)
    return subprocess.run([str(c) for c in cmd], check=False, **kw).returncode


def label(items, out, extra=()):
    return run([PY, KIT / "claude_batch.py", "--spec", SPEC, "--items", items, "--out", out, "--key-file", KEYFILE, *extra])


def spent(out):
    f = pathlib.Path(out) / "spend.jsonl"
    return sum(json.loads(l).get("usd", 0) for l in f.read_text().splitlines() if l.strip()) if f.exists() else 0.0


def first(path, n):
    sub = HERE / "data" / f"first{n}.jsonl"
    sub.write_text("".join(open(path, encoding="utf-8").readlines()[:n]), encoding="utf-8")
    return sub


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("stage"); ap.add_argument("n", nargs="?", type=int, default=3)
    ap.add_argument("--yes", action="store_true"); ap.add_argument("--cap", type=float); a = ap.parse_args()
    s = a.stage
    if s == "status":
        for p in (POOL, PILOT, SPEC):
            print(f"{p.relative_to(HERE)}: {sum(1 for _ in open(p, encoding='utf-8')) if p.suffix == '.jsonl' else 'ok'}" if p.exists() else f"{p.name}: MISSING")
        for r in sorted((HERE / "runs").glob("*")):
            print(f"run {r.name}: {sum(1 for _ in open(r / 'labels.jsonl')) if (r / 'labels.jsonl').exists() else 0} labels, ${spent(r):.4f} spent")
    elif s == "spec":
        run([sys.executable, "-I", HERE / "specs" / "make_spec.py"], cwd=HERE / "specs"); run([sys.executable, "-I", KIT / "task_spec.py", SPEC])
    elif s == "dry":
        return run([PY, KIT / "claude_batch.py", "--spec", SPEC, "--items", first(POOL, a.n), "--out", HERE / "runs" / "dry", "--dry-run"])
    elif s == "smoke":
        return label(first(PILOT, 3), HERE / "runs" / "smoke", ["--sync", "--limit", "3"])
    elif s == "pilot":
        if not a.yes: print("Estimate first: run `dry` on the pilot, then add --yes."); return 2
        return label(PILOT, HERE / "runs" / "pilot")
    elif s == "compare":
        return run([sys.executable, "-I", HERE / "compare_clef.py", HERE / "runs" / "pilot" / "labels.jsonl", CLEF])
    elif s == "bulk":
        if not a.yes or a.cap is None: print("bulk needs --cap USD and --yes (read the estimate from `dry` first)."); return 2
        return label(first(POOL, a.n), HERE / "runs" / f"bulk{a.n}", ["--cap-usd", str(a.cap)])
    elif s == "export":
        return run([sys.executable, "-I", HERE / "export_kaggle.py"])
    else:
        ap.error("unknown stage")


if __name__ == "__main__":
    sys.exit(main() or 0)
