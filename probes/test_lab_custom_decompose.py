#!/usr/bin/env python3
"""Unit tests for lab_custom_decompose.py -- no models needed, a fake `ask` returns fixed,
deterministic answers derived by hashing (model, state, question id). Run with:

    python3 -m unittest probes.test_lab_custom_decompose -v

(run from /workspace so the package path resolves, or `cd probes && python3 -m unittest
test_lab_custom_decompose -v`).
"""
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_custom_decompose as lcd  # noqa: E402


def make_fake_ask(fail_models=None):
    fail_models = set(fail_models or [])
    calls = []

    def ask(model, item):
        calls.append((model, item["state"], tuple(sorted(item["questions"]))))
        if model in fail_models:
            return {"error": "fake failure for test"}
        answers = {}
        for qid, q in item["questions"].items():
            seed = int(hashlib.sha256(f"{model}|{qid}|{item['state'][:80]}".encode()).hexdigest()[:8], 16)
            if q["type"] == "noul":
                answers[qid] = {"noul": (seed % 1000) / 1000.0}
            elif q["type"] == "choice":
                opts = list(q["criteria"])
                pick = opts[seed % len(opts)]
                probs = {o: (0.55 if o == pick else 0.45 / max(1, len(opts) - 1)) for o in opts}
                answers[qid] = {"choice": pick, "probabilities": probs}
            elif q["type"] == "score":
                answers[qid] = {"score": seed % 5}
        return {"answers": answers, "latency_ms": 5, "cached": False}

    ask.calls = calls
    return ask


TEXT = "A tool that lets support agents see a customer's full order history in one screen."
WHO = "Support agents at a mid-size e-commerce company."


class LabCustomDecomposeTest(unittest.TestCase):
    def setUp(self):
        self.lib = lcd.load_library()

    def test_library_shape(self):
        self.assertEqual(len(self.lib["categories"]), 21)
        self.assertTrue(all(len(c["shape"] or "") for c in self.lib["categories"]))
        skel = lcd.skeleton(self.lib)
        self.assertEqual(skel["space"], 113)
        self.assertNotIn("domain_enrichment", skel)  # server-internal only, not sent to the client

    def test_budget_honoured_exactly_and_control_not_counted(self):
        ask = make_fake_ask()
        events = list(lcd.walk(TEXT, WHO, ["semif", "kev-4b"], budget=5, ask=ask, lib=self.lib))
        end = [e for e in events if e["t"] == "end"][0]
        self.assertEqual(end["spent"], 5)
        self.assertEqual(end["budget"], 5)
        self.assertEqual(end["reason"], "budget")
        control_events = [e for e in events if e["t"] == "control"]
        self.assertEqual(len(control_events), 1)
        self.assertEqual(control_events[0]["seq"], 0)

    def test_every_call_has_at_most_24_questions(self):
        ask = make_fake_ask()
        events = list(lcd.walk(TEXT, WHO, ["semif"], budget=30, ask=ask, lib=self.lib))
        calls = [e for e in events if e["t"] == "call"]
        self.assertTrue(calls)
        for c in calls:
            self.assertLessEqual(c["n_questions"], 24, c["node"])
            self.assertLessEqual(len(c["body"]["questions"]), 24, c["node"])

    def test_call_then_result_for_every_seq(self):
        ask = make_fake_ask()
        events = list(lcd.walk(TEXT, WHO, ["semif"], budget=15, ask=ask, lib=self.lib))
        seqs_with_call = {}
        for i, e in enumerate(events):
            if e["t"] == "call":
                seqs_with_call[e["seq"]] = i
        for e in events:
            if e["t"] in ("frame", "categories", "node") and e.get("seq"):
                self.assertIn(e["seq"], seqs_with_call, f"result for seq {e['seq']} with no preceding call")
                self.assertLess(seqs_with_call[e["seq"]], events.index(e), "call must precede its result")

    def test_deterministic(self):
        events_a = list(lcd.walk(TEXT, WHO, ["semif", "kev-4b"], budget=10, ask=make_fake_ask(), lib=self.lib))
        events_b = list(lcd.walk(TEXT, WHO, ["semif", "kev-4b"], budget=10, ask=make_fake_ask(), lib=self.lib))
        self.assertEqual(events_a, events_b)

    def test_failing_model_excluded_from_per_model_and_shown_in_errors(self):
        ask = make_fake_ask(fail_models={"kev-4b"})
        events = list(lcd.walk(TEXT, WHO, ["semif", "kev-4b"], budget=5, ask=ask, lib=self.lib))
        frame = [e for e in events if e["t"] == "frame"][0]
        self.assertIn("kev-4b", frame["errors"])
        self.assertNotIn("kev-4b", frame["domain"]["per_model"])
        self.assertIn("semif", frame["domain"]["per_model"])

    def test_three_no_answer_nodes_end_all_failed(self):
        ask = make_fake_ask(fail_models={"semif", "kev-4b"})
        events = list(lcd.walk(TEXT, WHO, ["semif", "kev-4b"], budget=20, ask=ask, lib=self.lib))
        end = [e for e in events if e["t"] == "end"][0]
        self.assertEqual(end["reason"], "all_failed")
        self.assertLess(end["spent"], 20)

    def test_polarity_guard_not_yet_true(self):
        ask = make_fake_ask()
        events = list(lcd.walk(TEXT, WHO, ["semif"], budget=8, ask=ask, lib=self.lib))
        cat_call = [e for e in events if e["t"] == "call" and e["node"] == "__categories__"][0]
        for qid, q in cat_call["body"]["questions"].items():
            self.assertIn("NOT yet true", q["instructions"], qid)
        node_calls = [e for e in events if e["t"] == "call" and e["node"] not in ("__frame__", "__categories__")]
        self.assertTrue(node_calls)

    def test_generator_exit_stops_further_calls(self):
        ask = make_fake_ask()
        gen = lcd.walk(TEXT, WHO, ["semif"], budget=30, ask=ask, lib=self.lib)
        for _ in range(6):
            next(gen)
        n_calls_before_close = len(ask.calls)
        gen.close()
        self.assertEqual(len(ask.calls), n_calls_before_close, "no further model calls should happen after the generator is closed")

    def test_leaf_battery_has_no_atomic_or_parallel(self):
        qs = lcd.leaf_questions("The system logs every failed login attempt.")
        self.assertEqual(set(qs), {"gate", "phase", "risk", "complexity", "dependency"})


if __name__ == "__main__":
    unittest.main()
