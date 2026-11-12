"""Four numbers per head, read from result files (never typed): who settles it, how often, how right, how much is left for the teacher.
Writes runs/pulse/head_coverage.json. Not measured stays null with a reason. Run from projects/world-state."""
import json
R = "runs/pulse/"; cache = {}
def get(f, path):
    d = cache.setdefault(f, json.load(open(R + f)))
    for k in path.split("."): d = d[int(k)] if k.isdigit() else d[k]
    return d
E2E = "end2end_v6b-student_sealed.json"; MN = "anchor_mnds_fresh_v6b-student.json"; SS = "sparse_selective_flat.json"; TG = "topic_gate_mnds.json"
def n(f, k, **kw): return {"value": get(f, k), "src": f"{R}{f}#{k}", **kw}
NM = lambda why: {"value": None, "why": why}
heads = {
 "Domain (topic)": {
   "judge": "Sonnet agreement on the sealed set (1,499 items); human MN-DS labels on 1,600 fresh articles",
   "tools_settled": NM("no tool alone answers topic; the open-phrase gate method scores below the trained model"),
   "tools_accuracy": n(TG, "primary_pulse_assemble_method.top2_lenient_rate", note="topic gate method, two guesses, vs MN-DS human labels"),
   "model_answered": n(E2E, "topic_top2.answered_share.rate", note="BitMob Domain v6b"),
   "model_accuracy": n(E2E, "topic_top2.end_to_end_all.rate", note="two guesses vs Sonnet; one guess below"),
   "model_accuracy_human": n(MN, "top2_lenient_rate", note="two guesses vs MN-DS human labels"),
   "front_step": {"answered": n(SS, "share_070"), "right": n(SS, "right_070"), "note": "BitMob Domain sparse, candidate, not wired in"}},
 "Function (story type)": {
   "judge": "Sonnet agreement on the sealed set (1,499 items)",
   "tools_settled": NM("no tool alone answers story type; cue words do not separate fact from opinion (judge_gates.json#j3)"),
   "tools_accuracy": NM("not applicable"),
   "model_answered": n(E2E, "story_type.answered_share.rate"),
   "model_accuracy": n(E2E, "story_type.end_to_end_all.rate")},
 "Condition (present)": {
   "judge": "Sonnet agreement on the sealed set (1,499 items)",
   "tools_settled": NM("stated facts are proved per fact, not per article; the share of articles a tool settles is not measured"),
   "tools_accuracy": NM("not measured"),
   "model_answered": n(E2E, "condition_present.answered_share.rate"),
   "model_accuracy": n(E2E, "condition_present.agree_when_answered.rate", note="when it answers")},
 "Area": {"judge": "none", "tools_settled": NM("not built"), "tools_accuracy": NM("not built"), "model_answered": NM("name only, nothing trained"), "model_accuracy": NM("not built")},
 "Capability": {"judge": "none", "tools_settled": NM("not built"), "tools_accuracy": NM("not built"), "model_answered": NM("name only, nothing trained"), "model_accuracy": NM("not built")},
 "Novelty": {"judge": "none", "tools_settled": NM("not built"), "tools_accuracy": NM("not built"), "model_answered": NM("name only, nothing trained"), "model_accuracy": NM("not built")},
}
for h in heads.values():
    a = h["model_answered"].get("value")
    h["left_for_teacher"] = {"value": round(1 - a, 3), "src": h["model_answered"]["src"] + " (one minus)"} if a is not None else NM("no model")
json.dump(heads, open(R + "head_coverage.json", "w"), indent=1); print("ok", {k: (v["model_answered"].get("value"), v["model_accuracy"].get("value"), v["left_for_teacher"].get("value")) for k, v in heads.items()})
