"""T30 step 2: own checkable test for the forecast story type (one sided: can refute a forecast call, never confirm one). Sealed items, v6b-student calls and Sonnet labels.
    /workspace/models/embed-zs/.venv/bin/python forecast_cue_test.py   (from projects/world-state)"""
import json, re, sys
sys.path.insert(0, "."); from expert1_runtime import ExpertS
CUE = re.compile(r"\b(will|would|expected to|expects?|expected|forecasts?|forecast|projected|projects|projections?|predicts?|predicted|likely to|set to|plans? to|poised to|could|may|might|by 20\d\d|next (year|month|week|quarter|decade)|in the coming|outlook|to rise|to fall|to reach|to hit)\b", re.I)
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
items = {r["id"]: r["text"] for r in J("runs/pulse/sealed_items.jsonl")}; son = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); F = []; allcue = 0
for i, t in items.items():
    if i not in son: continue
    if e.read(t)["story_type"]["answer"] == "forecast": F.append(i)
SF = [i for i in son if son[i].get("story_type") == "forecast" and i in items]
share = lambda L: (sum(1 for i in L if CUE.search(items[i])), len(L))
a, na = share(F); b, nb = share(SF); both = [i for i in F if i in set(SF)]
res = {"v6b_forecast_calls": na, "with_cue": a, "rate": round(a / na, 3), "sonnet_forecast_labels": nb, "sonnet_with_cue": b, "sonnet_rate": round(b / nb, 3), "v6b_and_sonnet_forecast": len(both), "cue_free_v6b_forecast_calls": [{"id": i, "text": items[i][:160]} for i in F if not CUE.search(items[i])], "cue_share_in_all_items": round(sum(1 for t in items.values() if CUE.search(t)) / len(items), 3)}
json.dump(res, open("runs/pulse/forecast_cue_test.json", "w"), indent=1); print({k: v for k, v in res.items() if k != "cue_free_v6b_forecast_calls"}); print(len(res["cue_free_v6b_forecast_calls"]), "cue free calls")
for x in res["cue_free_v6b_forecast_calls"][:6]: print(" -", x["text"])
