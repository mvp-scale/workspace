"""Run the built image-lab tasks through Winnow and store per-item results.

    /workspace/kev/.venv/bin/python run_winnow.py [task_id ...] [--endpoint URL] [--force]

Reads  /workspace/probes/images/<task>.jsonl  and the images under /workspace/data/image-lab/images/.
Writes /workspace/data/image-lab/runs/winnow/<task>/results.jsonl (git-ignored). One request per item, no retries.
A request the server rejects is stored with "error" and counted as "could not run", never as wrong.
"""
import argparse, base64, json, time, urllib.error, urllib.request
from pathlib import Path

HERE = Path(__file__).parent
IMAGES = Path("/workspace/data/image-lab/images")
OUT = Path("/workspace/data/image-lab/runs/winnow")


def data_url(rel):
    raw = (IMAGES / rel).read_bytes()
    mime = "image/png" if rel.endswith(".png") else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def ask(endpoint, model, item):
    body = {"model": model, "state": item["state"], "winnow": {"images": [data_url(p) for p in item["images"]]},
            "questions": {"q": item["question"]}}
    req = urllib.request.Request(endpoint + "/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.load(r)
    return out["answers"]["q"], time.time() - t, (out.get("usage") or {}).get("input_tokens")


def score(item, ans):
    """predicted label, probability per label (same keys as item['labels'])."""
    if item["question"]["type"] == "noul":
        p = float(ans["noul"])
        return ("yes" if p >= 0.5 else "no"), {"no": 1 - p, "yes": p}
    probs = {k: float(v) for k, v in ans["probabilities"].items()}
    return ans["choice"], probs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks", nargs="*")
    ap.add_argument("--endpoint", default="http://127.0.0.1:8091")
    ap.add_argument("--model", default="Winnow-12B")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    files = [HERE / f"{t}.jsonl" for t in a.tasks] if a.tasks else sorted(HERE.glob("t[0-9][0-9]_*.jsonl"))
    for f in files:
        task = f.stem
        dest = OUT / task / "results.jsonl"
        if dest.exists() and not a.force:
            print(f"{task}: exists, skipped"); continue
        rows = []
        for item in (json.loads(l) for l in f.read_text().split("\n") if l.strip()):
            row = {"task_id": item["id"], "expected": item["expected"]}
            try:
                ans, dt, toks = ask(a.endpoint, a.model, item)
                pred, probs = score(item, ans)
                row.update(predicted=pred, probs=probs, correct=pred == item["expected"], p_correct=probs.get(item["expected"], 0.0),
                           latency_s=round(dt, 3), input_tokens=toks)
            except (urllib.error.URLError, KeyError, ValueError) as e:
                row.update(error=f"{type(e).__name__}: {e}"[:300])
            rows.append(row)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")
        ok = [r for r in rows if "error" not in r]
        print(f"{task}: {sum(r['correct'] for r in ok)}/{len(ok)} correct, {len(rows) - len(ok)} errors")


if __name__ == "__main__":
    main()
