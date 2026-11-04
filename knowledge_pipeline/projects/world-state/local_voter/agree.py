"""Raw agreement of the gpt-oss runs with Sonnet v3b and Haiku v3b labels. Fields: story_type, condition present (any listed vs none), topic. Stdlib only. Run: python3 -I agree.py"""
import json, os
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runs", "pulse")
def load(p):
    d = {}
    for l in open(os.path.join(R, p), encoding="utf-8"):
        if l.strip(): r = json.loads(l); d[r["item_id"]] = r["label"]
    return d
F = (("story type", lambda x: x["story_type"]), ("condition present", lambda x: bool(x["conditions"])), ("topic", lambda x: x["topic"]))
refs = {"Sonnet v3b": load("selfcons_v3b/labels.jsonl"), "Haiku v3b": load("selfcons_v3b_haiku/labels.jsonl")}
for run in ("selfcons_gptoss_low", "selfcons_gptoss_high", "selfcons_gemma4_off", "selfcons_gemma4_on", "selfcons_qwen36a3b_off", "selfcons_qwen38_27b_off", "selfcons_qwen36_27b_off"):
    p = os.path.join(run, "labels.jsonl")
    if not os.path.exists(os.path.join(R, p)): continue
    Q = load(p)
    for name, O in refs.items():
        ids = [i for i in Q if i in O]
        print(f"{run} vs {name}: {len(ids)} shared items of {len(Q)}")
        for fld, fn in F:
            a = sum(fn(Q[i]) == fn(O[i]) for i in ids)
            print(f"  {fld}: {a}/{len(ids)} = {100 * a / len(ids):.1f}%")
