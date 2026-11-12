"""T141 (free CPU): the full BitMob tool pass (analyze2: reader, stated facts, span rules, decider) on the 100 articles of T135, joined with Jev's saved answers into one record per story. Checks the wiring end to end: tool outcomes and Jev outcomes side by side, tool evidence against Jev evidence.
    /workspace/models/embed-zs/.venv/bin/python t141_unified.py (from projects/world-state) -> runs/pulse/t141/unified_100.jsonl, t141_unified.json"""
import os, sys, json, re, time, pathlib, collections
sys.path.insert(0, "."); import analyze2 as A2
from expert1_runtime import ExpertS
OUT = pathlib.Path("runs/pulse/t141"); OUT.mkdir(parents=True, exist_ok=True)
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); X = A2.Analyzer(e.S, json.load(open("runs/pulse/field_table.json")), threads=8)
text = {}
for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl"): r = json.loads(l); text[r["id"]] = (r["title"], r["text"])
for l in open("/workspace/data/newsreader/labels/t135_ls_sample.jsonl"): r = json.loads(l); text[r["id"]] = (r["title"], r["body"])
for l in open("/workspace/data/anchors/mn_ds/items_fresh2.jsonl"): r = json.loads(l); text[r["id"]] = (r["text"].split(". ")[0][:200], r["text"])
rows = [json.loads(l) for l in open("/workspace/data/newsreader/labels/full-read-100.jsonl")]; rows = [r for r in rows if "error" not in r]
jev_lab = {json.loads(l)["item_id"]: json.loads(l) for l in open("runs/label_store/labels_jev_t135.jsonl")}
recs = []; t0 = time.time(); oc = collections.defaultdict(collections.Counter); ms = []
for r in rows:
    title, body = text[r["id"]]; date = (r.get("published") or "")[:10] or None
    if date and not re.match(r"\d{4}-\d\d-\d\d$", date): date = None
    try: tool = X.analyze(title, body, date)
    except Exception as ex: recs.append({"id": r["id"], "set": r["set"], "tool_error": repr(ex)[:150]}); continue
    for k, v in tool["fields"].items(): oc[k][v["outcome"]] += 1
    ms.append(tool.get("timing", {}).get("total_ms", 0) if isinstance(tool.get("timing"), dict) else 0)
    jl = jev_lab[r["id"]]; tp = tool["fields"]["topic"]["proposed"] or ""; st = tool["fields"]["story_type"]["proposed"]
    ev = tool["evidence"]; amounts = ev.get("stated_amounts") or []; dates = ev.get("stated_dates") or []
    recs.append({"id": r["id"], "set": r["set"], "tools": {"fields": tool["fields"], "stated_amounts": amounts, "stated_dates": dates, "span_rules": ev.get("span_rules"), "windows": ev.get("windows"), "encoder_skipped": ev.get("encoder_skipped")},
                 "jev": {"topic": jl["topic"], "story_type": jl["story_type"], "iptc_domain": jl["iptc_domain"], "conditions": [{k: c[k] for k in ("condition", "direction", "level", "evidence_sentence", "evidence_tool_spans")} for c in jl["conditions"]], "time_recent_p": round(r["answers_call1"]["time_recent"]["noul"], 3)},
                 "joint": {"topic_agree": jl["topic"] in [x.strip() for x in tp.split("/")], "story_type_agree": jl["story_type"] == st, "tool_has_amount": bool(amounts), "jev_has_size_level_notable_or_more": any(c["level"] in ("notable", "major", "severe", "extreme") for c in jl["conditions"]), "tool_has_date": bool(dates), "jev_recent": r["answers_call1"]["time_recent"]["noul"] >= 0.7}})
ok = [x for x in recs if "tool_error" not in x]; J = lambda k: round(sum(x["joint"][k] for x in ok) / max(len(ok), 1), 4)
def rel(a, b):   # how often the two sides agree on a yes/no
    return round(sum(x["joint"][a] == x["joint"][b] for x in ok) / max(len(ok), 1), 4)
res = {"stories": len(rows), "tool_ran": len(ok), "tool_errors": len(recs) - len(ok), "tool_outcomes_per_field": {k: dict(v) for k, v in oc.items()}, "topic_agreement_tool_vs_jev": J("topic_agree"), "story_type_agreement_tool_vs_jev": J("story_type_agree"),
       "stated_amount_present_vs_jev_size_notable_or_more_agreement": rel("tool_has_amount", "jev_has_size_level_notable_or_more"), "stated_date_present_vs_jev_recent_agreement": rel("tool_has_date", "jev_recent"),
       "share_with_stated_amount": J("tool_has_amount"), "share_with_stated_date": J("tool_has_date"), "seconds": round(time.time() - t0),
       "note": "Both sides are models or tools on the same text; agreement is not accuracy. 'change' and 'traits' have no extractor wired in analyze2 (known)."}
open(OUT / "unified_100.jsonl", "w").write("\n".join(json.dumps(x) for x in recs)); json.dump(res, open(OUT / "t141_unified.json", "w"), indent=1); print(json.dumps(res, indent=1))
