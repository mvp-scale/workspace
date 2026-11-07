"""Direction read from the story's own change words (pre-registered L951). No training. Hand-written lexicon of rising and falling words (listed below, disclosed). A story gets 'up' or 'down' when one side leads in the first 600 characters, else 'unknown'. Truth for scoring is Sonnet ws-v2-frozen direction labels on stories whose conditions all share one direction; Haiku on the overlap is the second labeller.
    python3 direction_gate.py   (from projects/world-state)"""
import json, glob, re, collections
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
UP = r"\b(?:ris(?:e|es|ing|en)|rose|rais(?:e|ed|es|ing)|increas(?:e|ed|es|ing)|surg(?:e|ed|es|ing)|soar(?:s|ed|ing)?|jump(?:s|ed|ing)?|climb(?:s|ed|ing)?|spik(?:e|ed|es|ing)|grow(?:s|ing)?|grew|growth|higher|hik(?:e|ed|es|ing)|worsen(?:s|ed|ing)?|escalat(?:e|ed|es|ing)|expand(?:s|ed|ing)?|highest|gain(?:s|ed|ing)?|mount(?:s|ed|ing)|spread(?:s|ing)?|intensif(?:y|ied|ies|ying))\b"
DOWN = r"\b(?:fall(?:s|ing|en)?|fell|drop(?:s|ped|ping)?|declin(?:e|ed|es|ing)|decreas(?:e|ed|es|ing)|plung(?:e|ed|es|ing)|slump(?:s|ed|ing)?|slid(?:e|es|ing)?|sink(?:s|ing)?|sank|cuts?|cutting|slash(?:es|ed|ing)?|reduc(?:e|ed|es|ing|tion)|lower|lowest|eas(?:e|ed|es|ing)|shrink(?:s|ing)?|shrank|dwindl(?:e|ed|es|ing)|tumbl(?:e|ed|es|ing))\b"
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
S, H = {}, {}
for f in glob.glob("runs/**/labels.jsonl", recursive=True):
    if "label_store" in f: continue
    for r in J(f):
        pv = r.get("provenance") or {}; m = pv.get("model", ""); v = pv.get("prompt_version", ""); cs = (r.get("label") or {}).get("conditions", [])
        if not cs: continue
        ds = {x["direction"] for x in cs if x.get("direction") in ("up", "down")}
        if "sonnet" in m and v == "ws-v2-frozen": S[r["item_id"]] = ds
        if "haiku" in m: H[r["item_id"]] = ds
ids = [i for i, d in S.items() if len(d) == 1 and i in pool]; mixed = sum(1 for i, d in S.items() if len(d) > 1)
def read(t, lead=1):
    t = re.sub(r"\s+", " ", t)[:600]; u = len(re.findall(UP, t, re.I)); d = len(re.findall(DOWN, t, re.I))
    return "up" if u - d >= lead else "down" if d - u >= lead else "unknown"
res = {"labelled_single_direction": len(ids), "labelled_mixed_skipped": mixed, "share_up": round(sum(1 for i in ids if "up" in S[i]) / len(ids), 3), "lexicon_up_words": len(UP.split("|")), "lexicon_down_words": len(DOWN.split("|"))}
for lead in (1, 2):
    pred = {i: read(pool[i], lead) for i in ids}; ans = [i for i in ids if pred[i] != "unknown"]; ok = sum(1 for i in ans if {pred[i]} == S[i])
    pc = {}
    for c in ("up", "down"):
        real = [i for i in ids if S[i] == {c}]; got = [i for i in ans if pred[i] == c]; tp = sum(1 for i in got if S[i] == {c}); pc[c] = {"real": len(real), "answered_as": len(got), "precision": round(tp / max(len(got), 1), 3) if got else None, "share_of_real_found": round(tp / max(len(real), 1), 3)}
    both = [i for i in ans if i in H and len(H[i]) == 1]; agreeH = sum(1 for i in both if {pred[i]} == H[i]); agreeSH = sum(1 for i in both if S[i] == H[i])
    res[f"lead_{lead}"] = {"coverage": round(len(ans) / len(ids), 3), "precision_when_answered": round(ok / max(len(ans), 1), 3), "per_class": pc, "vs_haiku_items": len(both), "agree_with_haiku": round(agreeH / max(len(both), 1), 3), "sonnet_haiku_agree_same_items": round(agreeSH / max(len(both), 1), 3)}
json.dump(res, open("runs/pulse/direction_gate.json", "w"), indent=1); print(json.dumps(res, indent=1))
