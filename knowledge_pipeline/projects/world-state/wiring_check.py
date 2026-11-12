"""Wiring check for the sparse heads in analyze2.py: the same 200 articles with the heads off and on. Reports the share of articles where the encoder is skipped, median milliseconds per article both ways, and how often the story type and topic answers are the same both ways.
Not a score against truth (see runs/pulse/round2_story_cascade.json for that). Writes runs/pulse/wiring_check.json.
    /workspace/models/embed-zs/.venv/bin/python wiring_check.py   (from projects/world-state)"""
import json, re, random, sys, statistics
sys.path.insert(0, "."); import analyze2 as A2
from expert1_runtime import ExpertS
R = [r for r in map(json.loads, open("runs/harvest/sample.jsonl")) if len(r["text"] or "") >= 800]; random.Random(20261107).shuffle(R); R = R[:200]
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); FT = json.load(open("runs/pulse/field_table.json"))
X0 = A2.Analyzer(e.S, FT, threads=8); X1 = A2.Analyzer(e.S, FT, threads=8, sparse="runs/expert1/sparse_heads_v2.pkl")
t0 = []; t1 = []; sk = 0; same_s = same_t = 0; sk_same_s = sk_same_t = 0
for r in R:
    body = re.sub(r"\s+", " ", r["text"])[:12000]; title = re.sub(r"\s+", " ", r["title"] or ""); date = (r["date"] or "")[:10] or None
    a = X0.analyze(title, body, date); b = X1.analyze(title, body, date); t0.append(a["ms"]["total_ms"]); t1.append(b["ms"]["total_ms"])
    ss = a["fields"]["story_type"]["proposed"] == b["fields"]["story_type"]["proposed"]; st = a["fields"]["topic"]["proposed"].split(" / ")[0] == b["fields"]["topic"]["proposed"].split(" / ")[0]
    same_s += ss; same_t += st
    if b["evidence"]["encoder_skipped"]: sk += 1; sk_same_s += ss; sk_same_t += st
n = len(R); res = {"articles": n, "encoder_skipped_share": round(sk / n, 3), "median_ms_heads_off": round(statistics.median(t0), 1), "median_ms_heads_on": round(statistics.median(t1), 1), "story_same_all": round(same_s / n, 3), "topic_first_same_all": round(same_t / n, 3), "story_same_on_skipped": round(sk_same_s / max(sk, 1), 3), "topic_first_same_on_skipped": round(sk_same_t / max(sk, 1), 3), "note": "agreement between the two modes, not accuracy against truth"}
json.dump(res, open("runs/pulse/wiring_check.json", "w"), indent=1); print(json.dumps(res))
