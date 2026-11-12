"""T103: document-level contract fit of SENTiVENT as a one-sided presence anchor (T100 found the registered reader answers no on every body sentence; this separates text shift from field meaning). Each of the 288 documents is read as the reader is trained to see an article: the title plus the first two sentences. Positive: an asserted, non-negated, non-modal event mention starts inside that window. Control: no event mention of any kind starts inside it. Scoring only, nothing is trained on the data; condition_present of the registered reader (v6b-student).
    OUT=<folder> NP=<max docs> /workspace/models/embed-zs/.venv/bin/python -u t103_sentivent_doc.py -> <OUT>/t103_sentivent_doc.json"""
import os, sys, json, re, pathlib
sys.path.insert(0, "."); from expert1_runtime import ExpertS
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t103")); OUT.mkdir(parents=True, exist_ok=True); NP = int(os.environ.get("NP", 0))
A = pathlib.Path("/workspace/data/anchors/sentivent/data/sentivent_unified_document"); e = ExpertS("runs/expert1/expert1_v6b_student.pkl")
docs = [json.loads(l) for sp in ("train", "validation", "test") for l in open(A / f"{sp}.jsonl")]
if NP: docs = docs[:NP]
def window(text):
    title, _, body = text.partition("\n"); sents = re.split(r"(?<=[.!?])\s+", body.strip())
    first = " ".join(sents[:2]); start = text.index(first[:30], len(title)) if first[:30] in text[len(title):] else len(title) + 1
    return (title.strip() + ". " + first).strip(), start + len(first)
def starts(a):
    try: return min(c[0] for c in a["span"]["chars"])
    except Exception: return 10 ** 9
res = {"documents": len(docs)}
groups = {"positive": [], "control": []}
for d in docs:
    rt, end = window(d["text"]); evs = [a for a in d["annotations"] if a.get("kind") == "event" and starts(a) < end]
    if any(a.get("realis") == "asserted" and not a.get("negated") and not a.get("modality") for a in evs): groups["positive"].append(rt)
    elif not evs: groups["control"].append(rt)
for name, items in groups.items():
    yes = no = unk = 0
    for t in items:
        o = e.read(t)["condition_present"]
        if o.get("status") != "answered": unk += 1
        elif o["answer"]: yes += 1
        else: no += 1
    n = yes + no
    res[name] = {"items": len(items), "answered": n, "yes": yes, "no": no, "unknown": unk, "yes_rate_of_answered": round(yes / n, 4) if n else None}
p, c = res["positive"]["yes_rate_of_answered"], res["control"]["yes_rate_of_answered"]
res["lift_positive_over_control"] = round(p - c, 4) if p is not None and c is not None else None
res["note"] = "One-sided anchor: positives are documents with an asserted event inside title plus two sentences; controls have no event mention there but may still report a change later. Business news about companies only. Compare T100 (body sentences)."
json.dump(res, open(OUT / "t103_sentivent_doc.json", "w"), indent=1); print(json.dumps(res, indent=1))
