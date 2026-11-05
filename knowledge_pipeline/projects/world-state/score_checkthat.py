"""T30: v6b-student story type against CheckThat! English subjectivity (objective versus subjective sentences), internal scoring only (CC BY-NC-SA 4.0).
    /workspace/models/embed-zs/.venv/bin/python score_checkthat.py   (from projects/world-state)"""
import csv, json, math, sys, collections
sys.path.insert(0, "."); from expert1_runtime import ExpertS
D = "/workspace/data/anchors/checkthat_subj/"; rows = {}
for f in ("train_en", "dev_en", "dev_test_en", "test_en_labeled"):
    for r in csv.DictReader(open(D + f + ".tsv", encoding="utf-8"), delimiter="\t"): rows[r["sentence_id"]] = (r["sentence"], r["label"])
items = [{"id": "ct:" + i, "text": t} for i, (t, l) in rows.items()]; gold = {"ct:" + i: l for i, (t, l) in rows.items()}
with open(D + "items_T30.jsonl", "w") as f:
    for x in items: f.write(json.dumps(x) + "\n")
json.dump(gold, open(D + "gold_T30.json", "w"))
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); pred = {}; conf = {}
for x in items:
    r = e.read(x["text"]); pred[x["id"]] = r["story_type"]["answer"]
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(max(c - h, 0), 3), round(c + h, 3)]
def score(subj_set):
    S = [i for i, l in gold.items() if l == "SUBJ"]; O = [i for i, l in gold.items() if l == "OBJ"]
    ts = sum(pred[i] in subj_set for i in S); to = sum(pred[i] not in subj_set for i in O); ba = (ts / len(S) + to / len(O)) / 2
    se = 0.5 * math.sqrt((ts / len(S)) * (1 - ts / len(S)) / len(S) + (to / len(O)) * (1 - to / len(O)) / len(O))
    return {"subj_recall": [ts, len(S), round(ts / len(S), 3), wil(ts, len(S))], "obj_recall": [to, len(O), round(to / len(O), 3), wil(to, len(O))], "balanced_accuracy": round(ba, 3), "ci95": [round(ba - 1.96 * se, 3), round(ba + 1.96 * se, 3)]}
res = {"n": len(items), "story_type_distribution": dict(collections.Counter(pred.values())), "primary_subj_is_opinion": score({"opinion"}), "secondary_subj_is_opinion_or_unclear": score({"opinion", "unclear"}), "by_gold_label_story_distribution": {l: dict(collections.Counter(pred[i] for i, g in gold.items() if g == l)) for l in ("OBJ", "SUBJ")}}
json.dump(res, open("runs/pulse/anchor_checkthat_v6b-student.json", "w"), indent=1); print(json.dumps(res))
