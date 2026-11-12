"""One-off: writes the finished lap-two rounds into the Live tab's history (runs-history.jsonl) with their prediction as the success line, the result as the last line, and the ledger ids. Started = the prediction note's time, ended = the score note's time. Safe to rerun (a job and start time are written once)."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); import heartbeat as hb
ts = {}
for l in open("/workspace/knowledge_pipeline/.ledger/ledger.jsonl"):
    try: r = json.loads(l)
    except Exception: continue
    if r.get("id"): ts[r["id"]] = r.get("ts")
ROUNDS = [
 ("round-pool-v1-toolchain", "T43", "L1140", "L1144", "Read 20,000 articles with the whole toolchain", "Predicted 1,500 to 4,000 articles a minute and most articles with a checked item", "20,000 articles in 243 s (4,931 a minute); 92.0% have a checked amount or date. Faster than predicted (range missed)", "Pool rebalance"),
 ("round-pool-rebalance", "T43", "L1164", "L1169", "Rebalance the next teacher batch", "Predicted culture and leisure at most 16%, no topic more than 20% short", "1,482 of 2,000 chosen; culture and leisure 10.7% (hit); several topics ran out (miss)", "Teacher batch on the rebalanced items"),
 ("round-track-c-labels", "T44", "L1153", "L1156", "Teacher labels on 1,000 gists (session tokens)", "Predicted gist and full text agree on 75 to 90% of topics and 80 to 92% of story types", "Topic 83.0% (hit), story type 94.0% (above range). 1,000 labels, strength weak", "More labels moved nothing (R4)"),
 ("round-m2-teacher-494", "T44", "L1175", "L1178", "Teacher batch of 494 rebalanced gists", "Predicted 7 to 15% carry a condition, culture and leisure 16% or less", "Condition share 4.9% (miss, low); culture and leisure 12.1% (hit)", "Stability test"),
 ("round-s-stability", "T44", "L1181", "L1182", "Do independent labellers agree on conditions", "Predicted kappa 0.30 to 0.60; the sharper rule at least 0.10 higher", "Kappa 0.80 under the registered prompt (miss, high); rule A 0.72 (no help). My claim of labeller instability was wrong and is corrected", "Condition definition is the owner's"),
 ("round-r1-sparse-first", "T45", "L1117", "L1119", "Sparse topic head answers the surest half", "Predicted chain topic score 0.78 to 0.83", "Chain 79.8% against 79.9% for the big model alone (hit); half the slow-model calls skippable", "Story-type sparse head (R2)"),
 ("round-r2-story-head", "T45", "L1132", "L1134", "Sparse story-type head, and both heads at once", "Predicted chain near the big model alone", "Story 91.5% against 91.5%; both heads answer 27.7% (hit); weak on forecast and opinion", "Wire into the live path (R3)"),
 ("round-r3-wiring", "T45", "L1135", "L1137", "Wire the sparse heads into the live chain", "Predicted 15 to 35% skipped, same answers, faster", "22% skipped, same answers; first run 21 times slower (library call, fixed), rerun 75.0 to 60.5 ms", "Whole-chain score on human labels"),
 ("round-m3-condition-head", "T45", "L1175", "L1177", "A CPU model for whether an article has a condition", "Predicted F1 0.45 to 0.70", "F1 0.64 against Sonnet (hit); always saying yes gets 0.20. Agreement, not outside truth", "Needs the Condition definition confirmed"),
 ("round-r6-calibrated", "T45", "L1218", "L1221", "Thresholds from a calibration set (MM3-0005 finding)", "Predicted story within 0.01 of 0.915, both heads answer 20 to 35%", "Story 91.5%; both heads answer 29.2%; topic 91.9% against 92.2% (all hit)", "Independent review of the lap"),
 ("round-exit-whole-chain", "T46", "L1146", "L1147", "Whole chain on 1,600 human-labelled articles", "Predicted 0.75 to 0.83, heads on within 0.02, skip 20 to 50%", "Topic 79.3% off, 79.5% on (hit); skip 17.7% (miss, low); decider answers 61 to 64%", "Topic setting check"),
 ("round-r5-threshold", "T46", "L1161", "L1162", "Is a lower topic setting better (split-half)", "Predicted the rule picks 400 or 450", "Picked 300 and 500 (miss): accuracy barely moves, so the setting trades coverage for a little accuracy", "Fresh slice (M1)"),
 ("round-m1-fresh-slice", "T46", "L1175", "L1176", "Fresh MN-DS slice, scored once", "Predicted 700 answers 56 to 66% at 0.80 to 0.85", "700: 67.5% answered at 82.7% (share just above range); 500 narrowly fails; 600 read off this slice", "Second fresh slice (F)"),
 ("round-f-second-slice", "T46", "L1181", "L1209", "Second fresh slice, 600 validated", "Predicted 600 answers 77 to 88% at 0.79 to 0.83", "600: 82.5% answered at 80.8% (hit); 500 stays under 0.80; working decision 600", "Owner may veto (T48)"),
 ("review-mm3-t43-t47", "T47", "L1217", "L1226", "Independent MM3 review of T43 to T47", "A different actor judges each task against its own criteria", "All five pass (MM3-0004, 0007, 0009, 0010, 0011); first pass found gaps in four of five, all fixed", "Opus progress review"),
]
import re
whole = lambda v: re.sub(r"\.\d+Z$", "Z", v) if v else v   # the status tool reads whole seconds only
n = 0
for job, task, p, s, why, succ, last, nxt in ROUNDS:
    ok = hb.record(job, "done", where="[CPU] [SESS]", task=task, started=whole(ts.get(p)) or hb.now(), ended=whole(ts.get(s)) or hb.now(), progress=f"{p} prediction, {s} score", last=last, why=why, success=succ, next=nxt)
    n += bool(ok)
print("history records written:", n, "of", len(ROUNDS))
