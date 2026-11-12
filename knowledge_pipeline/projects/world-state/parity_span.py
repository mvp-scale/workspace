"""Parity check (MM3-0002 flagged live versus harvest could differ): the span-rules output of analyze2.py (live) must equal rec["more_spans"] of extract.py (harvest) on the same articles.
Reads runs/harvest/sample.jsonl rows with 800+ characters (first 200 after the inventory shuffle seed). Writes runs/pulse/parity_span.json.
    /workspace/models/embed-zs/.venv/bin/python parity_span.py   (from projects/world-state)"""
import json, re, random, time, collections, sys
sys.path.insert(0, "."); import analyze2 as A2, extract as EX
from expert1_runtime import ExpertS
R = [r for r in map(json.loads, open("runs/harvest/sample.jsonl")) if len(r["text"] or "") >= 800]; random.Random(20261107).shuffle(R); R = R[:200]
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); X = A2.Analyzer(e.S, json.load(open("runs/pulse/field_table.json")), threads=8)
EX.init() if hasattr(EX, "init") else None
same = 0; diff = []; ms = []; kinds = collections.Counter()
for k, r in enumerate(R):
    body = re.sub(r"\s+", " ", r["text"])[:12000]; title = re.sub(r"\s+", " ", r["title"] or ""); date = (r["date"] or "")[:10] or None
    out = X.analyze(title, body, date); live = out["evidence"]["span_rules"]; ms.append(out["ms"]["span_rules_ms"])
    text = title + ". " + body; harv = EX.SR.spans(text, date + "T00:00:00Z" if date else None)
    hv = {"counts": dict(collections.Counter(x["kind"] for x in harv)), "items": [[x["kind"], x["s"], x["e"], x["value"]] for x in harv if x["kind"] != "number_word" or x["value"] is not None][:60]}
    kinds.update(live["counts"])
    if live["counts"] == hv["counts"] and live["items"] == hv["items"]: same += 1
    else: diff.append(k)
res = {"articles": len(R), "identical": same, "different": len(diff), "different_rows": diff[:20], "span_rules_ms_median": round(sorted(ms)[len(ms)//2], 3), "span_rules_ms_p95": round(sorted(ms)[int(len(ms)*0.95)], 3), "spans_found_by_kind": dict(kinds)}
json.dump(res, open("runs/pulse/parity_span.json", "w"), indent=1); print(json.dumps(res))
