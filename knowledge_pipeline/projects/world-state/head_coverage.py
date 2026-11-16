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
 "Area": {"judge": "none yet; MN-DS as scoring-only needs the owner yes (ledger L2462)", "tools_settled": NM("organic Area not built; the live topic head carries the seed list (Domain row); topic vocabularies per seed topic in runs/pulse/t219/t219_frames.json (ledger L2470)"), "tools_accuracy": NM("no outside truth; publisher agreement test in runs/pulse/t216/t216_lanes.json (ledger L2464)"), "model_answered": NM("name only, nothing trained"), "model_accuracy": NM("not built")},
 "Capability": {"judge": "none: no outside truth exists for it (ledger L2462); recurrence over time and a reading of the pairs only", "tools_settled": n("t230/capability_tiers.json", "t222_pairs_recurring", note="RECURRING pairs: verb-object pairs held in 3+ Areas that are listed in BOTH the older and the newer half of the corpus (3+ distinct days each); 348 more pairs of the 371 are CANDIDATE only (event-bound or unproven). STABILITY, NOT ACCURACY: publisher halves share 0.44 of their top 100 pairs but that test shares events (t221); the date split shares 0.11 by article counts (t228) and 0.37 by distinct days (t229), so only about 25 pairs recur; rows are pseudo-labels (ledger L2496 to L2500)"), "tools_accuracy": NM("no outside truth, so no accuracy can be stated"), "model_answered": NM("no model trained: rows are pseudo-labels, owner decision open (ledger L2477)"), "model_accuracy": NM("not built")},
 "Novelty": {"judge": "none", "tools_settled": NM("not built"), "tools_accuracy": NM("not built"), "model_answered": NM("name only, nothing trained"), "model_accuracy": NM("not built")},
 "Function (opinion or fact, CheckThat)": {
   "judge": "CheckThat human labels on 2,076 sentences; teacher Jev (AUC 0.868); answer-when-sure rule: at most 0.25% false positives and 5% misses against the teacher label",
   "tools_settled": NM("no tool alone separates opinion from fact"),
   "tools_accuracy": NM("not applicable"),
   "model_answered": n("t179/t184_combined_encoders_selective.json", "v6b+bge+e5.coverage_mean", note="three small encoders joined, against Jev's label, grouped by story; on a time-shifted test (newest 30% of stories, Nov 2 to 5) 56.8% at true-positive rate 0.948 and false positives 0.0011 (t185_time_shift.json); coverage still rises with training rows: 27% at 1,000, 41% at 4,000, 49% at 8,000, 57% at 15,700 and 62% at 51,000 with diminishing returns (t186_learning_curve.json, t187_scaled_curve.json); with whole feeds held out (48 of 60 feeds, 6,056 sentences) 48.2% at true-positive rate 0.951 and false positives 0.0033, a little over the 0.0025 line (runs/pulse/t201/t201_feed_shift.json); fitting the yes-line at quota 0.0015 instead brings it to 47.1% coverage at false positives 0.0023, inside the line (runs/pulse/t202/t202_fp_margin.json)"),
   "model_accuracy": n("t179/t183_hybrid_vs_gold.json", "student_bal_acc_vs_gold_on_answered", note="balanced accuracy against human labels on the rows it answers (v6b student, 35% coverage); the teacher scores 0.792 on the same rows, hybrid loses 0.003")},
 "Place (region, 8 options)": {
   "judge": "teacher Jev place_region on 1,600 queue stories; text-derived judge (country and city names in the text, t167) on 745 decidable stories. The judge reads the same text as the student, so it is a proxy and partly circular",
   "tools_settled": NM("not measured"),
   "tools_accuracy": NM("not measured"),
   "model_answered": n("t182/t182_selective_place.json", "mean_coverage", note="e5-small linear head against Jev's label, line fitted on one random half and tested on the other, 10 half-splits; mean agreement with Jev 0.951, worst split 0.926"),
   "model_accuracy": n("t223/t223_place_fresh.json", "accuracy_answered_decidable", note="1,000 queue stories the student was not fitted on; of 414 the text judge can decide, it answers 260 and agrees on 93.5% (95% interval 90.4 to 96.5%); on the decidable ones it defers it is 44.2%; majority class 21.5%. Judge reads the same country-name cues, so a proxy. Earlier in-sample-line figure: 0.914 on 499 stories (t199)")},
 "Engine questions (328 keys, vs Clef)": {
   "judge": "Clef's own answers (agreement, not human truth) on 8,545 stories read as the engine reads them (title plus description); one logistic head per key on the v6b embedding, yes-line fitted at false-positive quota 0.0010 on out-of-fold training scores",
   "tools_settled": NM("not measured"),
   "tools_accuracy": NM("not measured"),
   "model_answered": n("t209/t209_triage_state_text.json", "tolerance_saving_worst", note="share of all 328 questions x stories the CPU answers when sure, counting only keys that hold true-positive rate 0.90 and false-positive rate 0.0025 on stories it did not train on; the lower of two shifted tests (newest 30% by day: 32.7%; whole publishers held out: 35.8%); 286 of 328 keys tested, the rest have under 10 training positives and count as zero; the earlier 2,488 full-article stories gave 9.6% (t206), the gain is mostly more labelled stories on the engine's own input text (t209). BARE-NOISE-BAND CHECK (NOT tolerance (d), NOT an F-0020 result; the band's median is 0.019 points and the recorded tolerance (d) has a median of 1.13 points, about 50 times larger; corrected L2448): replaying 800 held-out stories through the engine's own arithmetic with this router (CPU when sure, Clef otherwise) keeps only 7.8% of engine outputs inside the Step 1 noise band (median 3.1 times the band, max 31.7), and an all-CPU reader 3.9% (t211); per-key tolerance does not add up across 328 keys; a sweep of ten answer-line settings (stricter quotas, answering only a sure NO) reaches at best 30.6% of outputs inside the band while answering 38.2% of cells, and none reaches half (t212); BARE-BAND CALIBRATION (same caveat): Clef's own single-wording reading replayed against its two-wording reading lands 0.0% (wording 0) and 11.1% (wording 1) of outputs inside the same band, median 44.6 and 13.7 times the band, so the band is stricter than Clef's own self-agreement and the CPU router's best setting (30.6%, median 2.4 times) sits closer to Clef than Clef's single wording does (t213)"),
   "model_accuracy": NM("agreement with Clef only: pooled true-positive rate 0.932 and false-positive rate 0.0013 (time split), 0.935 and 0.0012 (publisher split) on held-out stories; no human truth for these questions")},
 "Clef attributes, 15 with at least 200 positives": {
   "judge": "Clef's own answers on 2,488 stories (agreement, not human truth)",
   "tools_settled": NM("not measured"),
   "tools_accuracy": NM("not measured"),
   "model_answered": n("t182/t182_attribute_selective.json", "summary.mean_coverage", note="mean over 15 attributes, range 24 to 68 percent; false-positive tails noisy"),
   "model_accuracy": NM("no human truth for these questions; agreement with Clef is held at true-positive rate 0.95 by the rule; jointly, a story has on average 5.7 of the 15 answered and only 0.04% have all 15 (t190_joint_coverage.json)")},
}
for h in heads.values():
    a = h["model_answered"].get("value")
    h["left_for_teacher"] = {"value": round(1 - a, 3), "src": h["model_answered"]["src"] + " (one minus)"} if a is not None else NM("no model")
json.dump(heads, open(R + "head_coverage.json", "w"), indent=1); print("ok", {k: (v["model_answered"].get("value"), v["model_accuracy"].get("value"), v["left_for_teacher"].get("value")) for k, v in heads.items()})
