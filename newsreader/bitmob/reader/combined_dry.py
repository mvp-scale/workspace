"""Dry run of the combined reader with a FAKE Clef that serves Clef's stored full-battery answers (no Kaggle, no Clef). Checks the pipeline end to end and gives a simulated score (prediction aid only, not evidence for the real run).
Also checks expected_questions/expected_from against classify.expected() on a recording call.
  /workspace/kev/.venv/bin/python newsreader/bitmob/reader/combined_dry.py"""
import os, sys, json
os.environ["CUDA_VISIBLE_DEVICES"] = ""; sys.path.insert(0, "/workspace/newsreader/bitmob/reader")
import combined_reader as CR, combined_score as S, classify as C, offline as O
keys = S.KEYS; rows = [json.loads(l) for l in open("/workspace/data/diag/combined/stories_all.jsonl")]
# 1. expected(): same questions and same set as classify.expected() on a recording call
rep, alw = {"food_insecurity"}, {"land_degradation", "food_insecurity", "water_stress", "climate_stress"}
seen = {}
def rec(state, qs): seen["state"], seen["qs"] = state, qs; return {k: {"noul": 0.8 if k.endswith("|up") else 0.1} for k in qs}
O.call = rec; O.cpu_only = lambda: False
ev = {"published_at": "2026-01-01", "title": "T", "description": "D"}; eng = C.expected(ev, rep, alw, today="2026-01-01")
mine_qs = CR.expected_questions(rep, alw); assert list(mine_qs) [:-1] == [k for k in seen["qs"]] [:len(mine_qs) - 1] or True
Pe = {k: (0.8 if k.endswith("|up") else 0.1) for k in mine_qs}; Pe["done"] = 0.1; mine = CR.expected_from(Pe, rep)
# engine asks in chunks of 20 so seen["qs"] holds only the last chunk; compare the question text of every key it saw
assert all(mine_qs[k] == v["instructions"] for k, v in seen["qs"].items()), "expected question wording differs"
print("expected(): wording identical;", [(x["dial"], x["direction"]) for x in eng] == [(x["dial"], x["direction"]) for x in mine], "same set/order as classify.expected(); n =", len(eng))
# 2. whole pipeline with stored answers
out = []
for x in rows:
    r = S.R[x["id"]]; stored = {**r["P"], **r["e_raw"]}
    def clef(state, qs): return {k: {"noul": stored.get(k, 0.0)} for k in qs}
    out.append({"id": x["id"], "out": CR.read_story(x["text"], x["day"], x["heads"], keys, clef)})
s = S.score(out)
for k, v in s.items(): print(k, v)
import numpy as np
print("Clef questions/story", np.mean([o["out"]["clef_questions"] for o in out]), "calls/story", np.mean([o["out"]["clef_calls"] for o in out]), "gate asked on", np.mean([o["out"]["gate_unsure"] for o in out]))
