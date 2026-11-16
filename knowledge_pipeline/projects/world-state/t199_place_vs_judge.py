"""T199: Place student (t182 out-of-fold probabilities, e5-small) scored against the text-derived place judge (t167) on the stories it answers, vs Jev on the same stories. Answer-line = lowest confidence line with 0.95 agreement vs Jev fitted on the full out-of-fold set (in-sample line, so read coverage as approximate).
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -u t199_place_vs_judge.py -> runs/pulse/t199/t199_place_vs_judge.json"""
import json, pathlib, runpy, numpy as np
OUT = pathlib.Path("runs/pulse/t199"); OUT.mkdir(parents=True, exist_ok=True)
g = runpy.run_path("t167_place_judge.py"); truth = {r["id"]: r["truth"] for r in g["rows"] if r["truth"]}
import os; os.environ["OUT"] = "runs/pulse/t182"; s = runpy.run_path("t182_selective_place.py")
ids, classes, P, yi, conf, agree = s["ids"], s["classes"], s["P"], s["yi"], s["conf"], s["agree"]; line = s["fit"](conf, agree)
pred = np.array([classes[k] for k in P.argmax(1)]); jev = np.array([classes[k] for k in yi]); ans = conf >= line
dec = np.array([i in truth for i in ids]); t = np.array([truth.get(i) for i in ids], dtype=object)
res = {"line": round(float(line), 3), "answered_share": round(float(ans.mean()), 3), "decidable_stories": int(dec.sum()), "decidable_answered": int((dec & ans).sum()),
       "student_acc_vs_judge_answered": round(float((pred[dec & ans] == t[dec & ans]).mean()), 3), "jev_acc_vs_judge_same_stories": round(float((jev[dec & ans] == t[dec & ans]).mean()), 3),
       "student_acc_vs_judge_all_decidable": round(float((pred[dec] == t[dec]).mean()), 3), "jev_acc_vs_judge_all_decidable": round(float((jev[dec] == t[dec]).mean()), 3)}
json.dump(res, open(OUT / "t199_place_vs_judge.json", "w"), indent=1); print(json.dumps(res))
