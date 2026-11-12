"""T100: contract fit of SENTiVENT (CC BY 4.0, scoring only) as a one-sided presence anchor. Reads every validation and test sentence once with the registered reader (v6b-student, field condition_present) and reports the yes rate on sentences with an asserted, non-negated, non-modal event (anchor positives: something happened) and on sentences with no event annotation (control; company-event annotation only, so a no is not proof of no change). Nothing is trained on the data.
    OUT=<folder> /workspace/models/embed-zs/.venv/bin/python -u t100_sentivent.py -> <OUT>/t100_sentivent.json"""
import os, sys, json, pathlib
sys.path.insert(0, "."); from expert1_runtime import ExpertS
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t100")); OUT.mkdir(parents=True, exist_ok=True); NP = int(os.environ.get("NP", 0))
A = pathlib.Path("/workspace/data/anchors/sentivent/data/sentivent_unified_sentence"); e = ExpertS("runs/expert1/expert1_v6b_student.pkl")
rows = [json.loads(l) for sp in ("validation", "test") for l in open(A / f"{sp}.jsonl")]
if NP: rows = rows[:NP]
def positive(r): return any(a.get("kind") == "event" and a.get("realis") == "asserted" and not a.get("negated") and not a.get("modality") for a in r["annotations"])
def negative(r): return not any(a.get("kind") == "event" for a in r["annotations"])
res = {"sentences": len(rows)}
for name, f in (("positive", positive), ("control", negative)):
    sel = [r for r in rows if f(r)]; yes = no = unk = short = 0
    for r in sel:
        o = e.read(r["text"])["condition_present"]
        if o.get("status") == "unknown" and o.get("answer") is None: short += 1
        elif o.get("status") != "answered": unk += 1
        elif o["answer"]: yes += 1
        else: no += 1
    n = yes + no
    res[name] = {"items": len(sel), "answered": n, "yes": yes, "no": no, "unknown": unk, "too_short": short, "yes_rate_of_answered": round(yes / n, 4) if n else None, "answered_share": round(n / max(len(sel), 1), 4)}
res["lift_positive_over_control"] = round(res["positive"]["yes_rate_of_answered"] - res["control"]["yes_rate_of_answered"], 4) if res["positive"]["yes_rate_of_answered"] is not None and res["control"]["yes_rate_of_answered"] is not None else None
res["note"] = "One-sided anchor: a positive is an asserted, non-negated, non-modal event mention; a control sentence has no event annotation but may still report a change. Sentences are body sentences of business news, the reader was trained on headline plus teaser."
json.dump(res, open(OUT / "t100_sentivent.json", "w"), indent=1); print(json.dumps(res, indent=1))
