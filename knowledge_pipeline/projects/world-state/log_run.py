"""Register finished runs in the viewer's job history (kit/live/heartbeat.py). Times come from the script and result file timestamps.
Usage in code: from log_run import done. Live job: heartbeat.beat(job, ...); finish with heartbeat.finish(job, ...)."""
import sys, os, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live"))
import heartbeat as hb
W = pathlib.Path(__file__).resolve().parent
iso = lambda p: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(W / p)))
def done(job, script, result, why, success, last, nxt, progress, state="done"):
    return hb.record(job, state, where="[CPU]", task="T8", started=iso(script), ended=iso(result), spent=0.0, progress=progress, last=last, why=why, success=success, next=nxt)
if __name__ == "__main__":
    R = [("t1-duplicate-leakage", "t1_dupes.py", "runs/structure/t1_dupes.json", "Do near-duplicate stories and later news inflate our scores?", "AUC falls under 0.01 when twins are kept together", "0.8618 to 0.8605 grouped; later news 0.84", "Label-error ranking", "24,775 items, 5-fold, twins at 0.5 and 0.8"),
    ("t2-doubtful-labels", "t2_suspects.py", "runs/structure/t2_suspects.json", "Does confidence in Haiku's own label find where Sonnet disagrees?", "Top 100 doubtful labels have 2x or more the Sonnet disagreement rate", "2.2x on positives, 2.9x on negatives", "Say unknown on doubtful items", "7,710 Sonnet-voted items"),
    ("t6-say-unknown", "t6b.py", "runs/structure/t6b.json", "Does answering only when confident lift agreement with Sonnet?", "Answered half beats full coverage by 0.10 or more", "Run 1 failed (my design); run 2 gain 0.0999, on the line", "Build the improvement loop", "7,710 voted items, 2 runs"),
    ("t7-improvement-loop", "loop.py", "runs/snapshots/loop_results.json", "Does the reader get better as data accumulates, and do source prior, headline or window help?", "AUC rises 0.01 or more from v1 to v4", "0.838 to 0.852 (+0.014); source +0.003; headline-only 0.815", "Try other levers", "5 date batches, snapshots v1 to v4"),
    ("t8-label-levers", "loop2.py", "runs/snapshots/loop2_results.json", "Do n-gram words, label pruning or soft labels beat the embedding student?", "Any lever gains 0.01 or more against Sonnet", "tfidf +0.044 vs Sonnet; pruning +0.009; soft labels +0.012 (noise)", "Tune the n-gram student", "v4 split, 1,466 voted test items"),
    ("t9-ngram-student", "loop3.py", "runs/snapshots/loop3_results.json", "What is the best sparse student and how fast is it?", "Gain 0.005 or more per addition; under 2 ms per item", "Words+chars 0.881 vs Haiku, 0.743 vs Sonnet; 0.46 ms; flags hurt", "Measure answered share per output", "v4 split, C chosen on batch 4"),
    ("t10-answered-share", "loop4.py", "runs/snapshots/loop4_results.json", "How much can each output answer at 80% agreement, and does the loop keep improving?", "Curve gains 0.02 or more; per-output share at 80% agreement", "Story type 100%, topic 52%, presence 40%; curve +0.028", "Raise topic", "learning curve and 3 outputs")]
    for r in R: print(r[0], done(*r))
