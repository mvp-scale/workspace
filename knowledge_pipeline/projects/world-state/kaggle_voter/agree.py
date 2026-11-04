"""Raw agreement of the Qwen voter with Sonnet r1 (runs/p7b/*/labels.jsonl) and Haiku r1 (runs/p7/*/labels.jsonl).
Fields: story_type, condition present (any condition listed vs none), topic. Stdlib only. Run: python3 -I agree.py"""
import glob, json, os, sys
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runs")
def load(pat):
    d = {}
    for f in sorted(glob.glob(os.path.join(R, pat))):
        for l in open(f, encoding="utf-8"):
            if l.strip(): r = json.loads(l); d[r["item_id"]] = r["label"]
    return d
# optional args: voter labels path, Sonnet pattern, Haiku pattern (relative to runs/); default is the Qwen vs r1 comparison
A = sys.argv[1:] or ["pulse/selfcons_qwen/labels.jsonl", "p7b/*/labels.jsonl", "p7/*/labels.jsonl"]
Q = load(A[0])
for name, pat in (("Sonnet", A[1]), ("Haiku", A[2])):
    O = load(pat); ids = [i for i in Q if i in O]
    print(f"{name}: {len(ids)} shared items of {len(Q)} Qwen-labelled")
    for fld, fn in (("story type", lambda x: x["story_type"]), ("condition present", lambda x: bool(x["conditions"])), ("topic", lambda x: x["topic"])):
        a = sum(fn(Q[i]) == fn(O[i]) for i in ids)
        print(f"  {fld}: {a}/{len(ids)} = {100 * a / len(ids):.1f}%" if ids else f"  {fld}: no shared items")
