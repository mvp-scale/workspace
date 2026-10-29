"""Offline tests for kit/teacher (mocked clients only; no network, no key).

    python -m unittest discover -s knowledge_pipeline/kit/teacher/tests -v
"""
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parent
sys.path.insert(0, str(KIT))
import task_spec as TS  # noqa: E402
import candidates as C  # noqa: E402
import claude_batch as CB  # noqa: E402
import open_model as OM  # noqa: E402
import qualify as Q  # noqa: E402

SPEC = KIT / "examples" / "span_task.json"
ITEMS = [{"id": "s1", "text": "The Port Authority of Belmar said it will reopen the dock after repairs."},
         {"id": "s 2", "text": "Farmers in Oskel protested and asked the Regional Board for talks."}]
PRICES = {"status": "TO_BE_VERIFIED", "batch_discount": 0.5,
          "models": {"claude-haiku-5-5": {"input": 1.0, "cache_read": 0.1, "cache_write_5m": 1.25, "output": 5.0}}}
FAKE_KEY = "sk-ant-test-0000000000"


def cands_for(spec, items):
    P = C.from_config(spec.candidates)
    return {it["id"]: (CB.sha(it["text"]), C.propose(it["text"], P)) for it in items}


def good_reply(cands):
    d = {c["id"]: ("ORG" if c["layer"] == "ENTITY" else "Y") for c in cands}
    return json.dumps({"d": d, "add": []})


class Msg(dict):
    """SDK-like message as a dict (claude_batch.g reads keys or attributes)."""


def msg(text, mid="msg_1", stop="end_turn", usage=None):
    return Msg(id=mid, model="claude-haiku-5-5", stop_reason=stop, content=[{"type": "text", "text": text}],
               usage=usage or {"input_tokens": 100, "cache_creation_input_tokens": 0,
                               "cache_read_input_tokens": 900, "output_tokens": 50})


class FakeBatches:
    def __init__(self, replies):
        self.replies, self.created, self.retrieved = replies, [], 0

    def create(self, requests):
        self.created.append(requests)
        return {"id": f"msgbatch_{len(self.created)}", "processing_status": "in_progress"}

    def retrieve(self, bid):
        self.retrieved += 1
        return {"id": bid, "processing_status": "ended" if self.retrieved > 1 else "in_progress",
                "request_counts": {"processing": 0}}

    def results(self, bid):
        reqs = self.created[int(bid.split("_")[1]) - 1]
        for r in reqs:
            yield {"custom_id": r["custom_id"], "result": {"type": "succeeded", "message": self.replies(r)}}


class FakeMessages:
    def __init__(self, replies, sync_replies=None):
        self.batches = FakeBatches(replies)
        self.sync_replies, self.calls = sync_replies or replies, []

    def create(self, **params):
        self.calls.append(params)
        return self.sync_replies({"params": params})


class FakeClient:
    def __init__(self, replies, sync_replies=None):
        self.messages = FakeMessages(replies, sync_replies)


def user_cands(params):
    """Recover the candidate ids from a request (they are the required keys of the reply schema)."""
    req = params["output_config"]["format"]["schema"]["properties"]["d"]["required"]
    return [{"id": i, "layer": "ENTITY" if params["output_config"]["format"]["schema"]["properties"]["d"]
             ["properties"][i]["enum"][0] == "PER" else "EVENT"} for i in req]


def reply_ok(r):
    return msg(good_reply(user_cands(r["params"])), mid="msg_" + r.get("custom_id", "sync"))


class TestSpec(unittest.TestCase):
    def test_example_spec_loads_and_caches(self):
        s = TS.load(SPEC)
        self.assertEqual(s.mode, "verify")
        self.assertGreaterEqual(s.prefix_tokens_est(), TS.MIN_CACHE_TOKENS)
        self.assertIn("synthetic", s.system_text())

    def test_open_schema_refused(self):
        d = json.loads(SPEC.read_text(encoding="utf-8"))
        d["output_schema"]["additionalProperties"] = True
        with self.assertRaises(TS.SpecError):
            TS.TaskSpec(d)

    def test_validate(self):
        sc = {"type": "object", "additionalProperties": False, "required": ["a"],
              "properties": {"a": {"type": "string", "enum": ["x", "y"]}, "n": {"type": "integer", "minimum": 0}}}
        self.assertEqual(TS.validate({"a": "x", "n": 3}, sc), [])
        self.assertTrue(TS.validate({"a": "z"}, sc))            # enum
        self.assertTrue(TS.validate({}, sc))                    # required
        self.assertTrue(TS.validate({"a": "x", "b": 1}, sc))    # additionalProperties false
        self.assertTrue(TS.validate({"a": "x", "n": True}, sc))  # bool is not an integer
        self.assertTrue(TS.validate({"a": "x", "n": -1}, sc))   # minimum (local only)
        self.assertNotIn("minimum", json.dumps(TS.api_schema(sc)))


class TestCandidates(unittest.TestCase):
    def test_merge_ids_and_assemble(self):
        s = TS.load(SPEC)
        text = ITEMS[0]["text"]
        cs = C.propose(text, C.from_config(s.candidates))
        self.assertEqual([c["id"] for c in cs], [f"c{i}" for i in range(1, len(cs) + 1)])
        for c in cs:
            self.assertEqual(text[c["start"]:c["end"]], c["text"])
        sc = C.verify_schema(cs, s.verify["labels"])
        reply = {"d": {c["id"]: ("X" if c["layer"] == "ENTITY" else "Y") for c in cs},
                 "add": [{"layer": "ENTITY", "text": "Belmar", "label": "LOC"}]}
        self.assertEqual(TS.validate(reply, sc), [])
        self.assertTrue(TS.validate({"d": {}, "add": []}, sc))  # every id is required
        label, stats, errs = s.finalize(ITEMS[0], reply, cs)
        self.assertEqual(errs, [])
        add = [x for x in label["spans"] if x["src"] == "add"][0]
        self.assertEqual(text[add["start"]:add["end"]], "Belmar")


class TestClaudeBatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = pathlib.Path(self.tmp.name) / "run"
        self.spec = TS.load(SPEC)
        self.C = cands_for(self.spec, ITEMS)

    def tearDown(self):
        self.tmp.cleanup()

    def test_request_building(self):
        reqs = CB.build_requests(self.spec, ITEMS, self.C)
        self.assertEqual(len(reqs), 2)
        p = reqs[0]["params"]
        self.assertEqual(p["system"][-1]["cache_control"], {"type": "ephemeral", "ttl": "1h"})
        self.assertEqual(len(p["system"]), 1)
        self.assertEqual(p["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(TS.closed(p["output_config"]["format"]["schema"]), [])
        self.assertIn("CANDIDATES", p["messages"][0]["content"])
        self.assertEqual(p["system"][0]["text"], self.spec.system_text())
        for r in reqs:  # custom ids legal; "s 2" is hashed
            self.assertRegex(r["cid"], CB.CID_RE.pattern)
        self.assertNotEqual(reqs[1]["cid"], "s 2")

    def test_dry_run_offline(self):
        items = pathlib.Path(self.tmp.name) / "items.jsonl"
        CB.append_jsonl(items, ITEMS)
        cf = pathlib.Path(self.tmp.name) / "c.jsonl"
        CB.append_jsonl(cf, [{"id": k, "text_sha256": h, "candidates": c} for k, (h, c) in self.C.items()])
        buf = io.StringIO()
        with mock.patch.object(CB, "make_client", side_effect=AssertionError("no client in dry run")), \
                redirect_stdout(buf):
            rc = CB.main(["--spec", str(SPEC), "--items", str(items), "--cands", str(cf), "--out", str(self.out),
                          "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("2 requests", buf.getvalue())
        self.assertFalse(self.out.exists())

    def test_batch_run_provenance_and_spend(self):
        reqs = CB.build_requests(self.spec, ITEMS, self.C)
        cl = FakeClient(reply_ok)
        R = CB.Run(self.spec, self.out, cl, PRICES, cap_usd=10, log=lambda *a: None, sleep=lambda s: None)
        self.assertEqual(R.run_batches(reqs), 2)
        labels = CB.read_jsonl(self.out / "labels.jsonl")
        self.assertEqual({r["item_id"] for r in labels}, {"s1", "s 2"})
        pv = labels[0]["provenance"]
        for k in ("teacher", "model", "prompt_version", "request_id", "custom_id", "batch_id", "date", "spec_sha256",
                  "text_sha256", "mode"):
            self.assertTrue(pv.get(k), k)
        self.assertEqual(pv["prompt_version"], "span-v1")
        self.assertNotIn("text", labels[0])
        sp = CB.read_jsonl(self.out / "spend.jsonl")
        self.assertEqual(len(sp), 1)
        self.assertEqual(set(sp[0]["usage"]) >= {"input_tokens", "cache_creation_input_tokens",
                                                 "cache_read_input_tokens", "output_tokens"}, True)
        self.assertEqual(sp[0]["prices_status"], "TO_BE_VERIFIED")
        # 2 x (100 in x 1.0 + 900 read x 0.1 + 50 out x 5.0) / 1e6 x 0.5
        self.assertAlmostEqual(sp[0]["usd"], 2 * (100 + 90 + 250) / 1e6 * 0.5, places=8)
        # resume: nothing resubmitted
        R2 = CB.Run(self.spec, self.out, cl, PRICES, cap_usd=10, log=lambda *a: None, sleep=lambda s: None)
        R2.run_batches(CB.build_requests(self.spec, ITEMS, self.C, skip=CB.done_ids(self.out)))
        self.assertEqual(len(cl.messages.batches.created), 1)

    def test_malformed_retried_once_sync(self):
        reqs = CB.build_requests(self.spec, ITEMS, self.C)
        bad = lambda r: msg('{"d": {}, "add": []', mid="bad")  # noqa: E731  truncated JSON
        cl = FakeClient(bad, sync_replies=reply_ok)
        R = CB.Run(self.spec, self.out, cl, PRICES, cap_usd=10, log=lambda *a: None, sleep=lambda s: None)
        self.assertEqual(R.run_batches(reqs), 2)
        self.assertEqual(len(cl.messages.calls), 2)  # one retry per malformed row
        modes = {r["provenance"]["mode"] for r in CB.read_jsonl(self.out / "labels.jsonl")}
        self.assertEqual(modes, {"sync_retry"})
        # still malformed after the retry -> rejects, no second retry
        out2 = pathlib.Path(self.tmp.name) / "run2"
        cl2 = FakeClient(bad)
        R = CB.Run(self.spec, out2, cl2, PRICES, cap_usd=10, log=lambda *a: None, sleep=lambda s: None)
        self.assertEqual(R.run_batches(reqs), 0)
        self.assertEqual(len(cl2.messages.calls), 2)
        self.assertEqual(len(CB.read_jsonl(out2 / "rejects.jsonl")), 2)

    def test_truncated_reply_rejected(self):
        cs = self.C["s1"][1]
        _, _, errs = CB.check_row(self.spec, ITEMS[0], cs, good_reply(cs), "max_tokens")
        self.assertTrue(errs)

    def test_spend_cap_stops(self):
        reqs = CB.build_requests(self.spec, ITEMS, self.C)
        one = CB.estimate(reqs[0], PRICES, self.spec.model)[0]
        cl = FakeClient(reply_ok)
        R = CB.Run(self.spec, self.out, cl, PRICES, cap_usd=one * 0.5, log=lambda *a: None, sleep=lambda s: None)
        self.assertEqual(R.run_batches(reqs), 0)
        self.assertEqual(cl.messages.batches.created, [])
        self.assertIn("cap", R.stopped)
        # cap fits one request: chunk trimmed to 1, then the run stops
        out2 = pathlib.Path(self.tmp.name) / "run2"
        cl2 = FakeClient(reply_ok)
        R = CB.Run(self.spec, out2, cl2, PRICES, cap_usd=one * 1.5, log=lambda *a: None, sleep=lambda s: None)
        R.run_batches(reqs)
        self.assertEqual(len(cl2.messages.batches.created[0]), 1)
        self.assertTrue(R.stopped)
        self.assertLessEqual(CB.spend_total(out2 / "spend.jsonl"), one * 1.5)
        # sync mode: refuses the call itself
        out3 = pathlib.Path(self.tmp.name) / "run3"
        cl3 = FakeClient(reply_ok)
        R = CB.Run(self.spec, out3, cl3, PRICES, cap_usd=0.0, log=lambda *a: None)
        R.run_sync(reqs)
        self.assertEqual(cl3.messages.calls, [])

    def test_key_never_printed(self):
        kf = pathlib.Path(self.tmp.name) / "vault.env"
        kf.write_text(f"OTHER=1\nANTHROPIC_API_KEY={FAKE_KEY}\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            self.assertEqual(CB.read_key(str(kf)), FAKE_KEY)
        self.assertNotIn(FAKE_KEY, CB.scrub(f"401 bad key {FAKE_KEY}", FAKE_KEY))


class TestOpenModel(unittest.TestCase):
    def test_guided_body_loop_guard_and_provenance(self):
        spec = TS.load(SPEC)
        Cs = cands_for(spec, ITEMS)
        reqs = OM.build(spec, ITEMS, Cs)
        b = OM.body(spec, "sys", "user", 100, reqs[0]["schema"], "qwen", "json_schema")
        self.assertEqual(b["response_format"]["type"], "json_schema")
        self.assertIn("guided_json", OM.body(spec, "s", "u", 9, reqs[0]["schema"], "q", "vllm"))
        self.assertIsNotNone(OM.find_loop('{"a": 1}' + "abcdefghij-klmnopqrst," * 40))
        calls = []

        def post(url, payload, headers, timeout):
            calls.append(payload)
            ids = payload["response_format"]["json_schema"]["schema"]["properties"]["d"]["required"]
            enum = payload["response_format"]["json_schema"]["schema"]["properties"]["d"]["properties"]
            d = {i: ("ORG" if "ORG" in enum[i]["enum"] else "Y") for i in ids}
            text = json.dumps({"d": d, "add": []}) if len(calls) > 1 else "x" * 10 + "loop-loop-loop-loop-" * 60
            return {"id": f"cmpl-{len(calls)}", "model": "qwen-test", "usage": {"prompt_tokens": 10,
                                                                                "completion_tokens": 5},
                    "choices": [{"message": {"content": text}, "finish_reason": "stop"}]}

        with tempfile.TemporaryDirectory() as t:
            R = OM.OpenRun(spec, t, "http://localhost:8000/v1", "qwen-test", workers=1, post=post, log=lambda *a: None)
            self.assertEqual(R.run(reqs), 2)
            self.assertEqual(len(calls), 3)  # first reply looped -> one retry
            lab = CB.read_jsonl(pathlib.Path(t) / "labels.jsonl")
            self.assertEqual(lab[0]["provenance"]["teacher"], "open")
            self.assertEqual(lab[0]["provenance"]["endpoint"], "localhost:8000")
            self.assertTrue(lab[0]["provenance"]["request_id"])
            self.assertEqual(len(CB.read_jsonl(pathlib.Path(t) / "spend.jsonl")), 1)


class TestQualify(unittest.TestCase):
    def test_decide_with_existing_labels(self):
        spec = TS.load(SPEC)
        gold = [{"id": "g1", "text": "Mayor Ana Reyes said so.",
                 "spans": [{"start": 0, "end": 15, "label": "PER", "layer": "ENTITY"}]}]
        labels = [{"item_id": "g1", "label": {"spans": [{"layer": "ENTITY", "start": 0, "end": 15,
                                                          "text": "Mayor Ana Reyes", "label": "PER", "src": "cand"}]},
                   "provenance": {"teacher": "claude", "model": "claude-haiku-5-5"}}]
        with tempfile.TemporaryDirectory() as t, redirect_stdout(io.StringIO()):
            rc, rep = Q.decide(spec, gold, labels, {"PER": 0.8}, "label", "exact", pathlib.Path(t), "claude")
            self.assertEqual(rc, 0)
            self.assertEqual(rep["decision"], "PASS")
            self.assertEqual(rep["acceptance"], "D4")
            rc, rep = Q.decide(spec, gold, [], {"PER": 0.8}, "label", "exact", pathlib.Path(t), "claude")
            self.assertEqual((rc, rep["decision"]), (1, "FAIL"))

    def test_pilot_capped_at_50(self):
        with self.assertRaises(SystemExit):
            Q.main(["--spec", str(SPEC), "--gold", "x", "--iaa", "y", "--out", "z", "--n", "51"])


if __name__ == "__main__":
    unittest.main()
