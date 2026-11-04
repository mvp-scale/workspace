"""Tests for note_guard E5 (source check). python3 test_note_guard.py"""
import json, os, sys, tempfile, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); import note_guard as g
d = tempfile.mkdtemp(); f = os.path.join(d, "score.json"); json.dump({"topic": {"rate": 0.79, "n": [1, 2.5]}, "story": 0.9186}, open(f, "w")); open(os.path.join(d, "bad.json"), "w").write("not json")
ok = lambda t: not any(x.startswith("E5") for x in g.check(t)); bad = lambda t, w: any(x.startswith("E5") and w in x for x in g.check(t))
cases = [("correct number passes", ok(f"topic 0.790 (src: {f}#topic.rate)")), ("rounding to the quoted decimals passes", ok(f"story 0.919 (src: {f}#story)")), ("two decimals passes", ok(f"story 0.92 (src: {f}#story)")),
         ("list index resolves", ok(f"second 2.5 (src: {f}#topic.n.1)")), ("wrong number is blocked", bad(f"topic 0.791 (src: {f}#topic.rate)", "holds")), ("number off by one in the third decimal blocked", bad(f"story 0.918 (src: {f}#story)", "holds")),
         ("missing key is blocked", bad(f"topic 0.790 (src: {f}#topic.rte)", "key not found")), ("missing file is blocked", bad("topic 0.790 (src: /nonexistent/x.json#a)", "not found")), ("non-JSON file is blocked", bad(f"x 1 (src: {d}/bad.json#a)", "readable")),
         ("a note with no source token is untouched by E5", ok("topic 0.790 from somewhere")), ("a relative path under world-state resolves to the real score file", ok("topic 0.790 (src: runs/pulse/end2end_v6b-student_devq.json#topic_top1.end_to_end_all.rate)")), ("the real score file rejects a wrong number", bad("topic 0.800 (src: runs/pulse/end2end_v6b-student_devq.json#topic_top1.end_to_end_all.rate)", "holds"))]
fails = [n for n, r in cases if not r]; [print(("PASS " if r else "FAIL ") + n) for n, r in cases]; sys.exit(1 if fails else 0)
