"""S4 export: fp32 ONNX + parity vs torch on dev, int8 options measured on dev, pick by a rule written first (M3/M4).

    python export.py --run-dir runs/x/seed42 [--checkpoint last.pt] [--config cfg.yaml] --out-dir ship/x

Runs on CPU (Kaggle CPU / the reference box), not the dev machine. Steps (pipeline/kaggle/student/int8_v2 and
int8_v2b, generalised):
  1. rebuild the student from run-dir/backbone + checkpoint (no download); export fp32 ONNX, opset 17, outputs
     `tags` [b, s, 3*nch] (+ `seq` [b, n_labels]); parity on dev: token tag agreement and max |logit| diff vs torch.
  2. graph: optimize auto/bert = ORT transformer optimizer (fuses Attention / SkipLayerNorm / Gelu into com.microsoft
     ops; those files run in ORT incl. onnxruntime-web but do NOT load in OpenVINO) or none (portable graph).
  3. write pick_rule.json (timestamped) BEFORE any option is scored.
  4. options: D0 dynamic per-tensor, D1 dynamic per-channel, QA partial (fused Attention / Q,K,V MatMuls only),
     S1 static QDQ per-channel MinMax on the calibration set, D1BC = D1 + output bias correction (mean fp32 - int8
     logit per output unit over calibration windows). Calibration text is never dev.
  5. per option: per-head dev exact-span agreement vs fp32, dev F1 vs gold and drop vs fp32 (+ paired bootstrap 95%
     interval), token flip rate vs fp32, 1-thread per-window latency p50/p95, size, sha, com.microsoft ops.
  6. pick: options with max per-head drop <= max_layer_drop (drop vs gold if dev has spans, else 1 - agreement),
     then lowest flip rate, then lowest p50. Writes model.int8.onnx (the pick), model.fp32.onnx, tokenizer.json,
     labels.json (runtime + web contract) and export_report.json.
"""
import argparse
import collections
import datetime as dt
import json
import os
import pathlib
import re
import shutil
import sys
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import core  # noqa: E402

T0 = time.time()
FUSABLE = {"bert", "roberta", "distilbert", "xlm-roberta", "electra", "mpnet"}


def log(*a):
    print(f"[export {time.time() - T0:6.0f}s]", *a, flush=True)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def session(path, threads=1):
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.intra_op_num_threads = threads
    so.inter_op_num_threads = 1
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    s = ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])
    for n in (64, 128, 256):
        x = np.ones((1, n), np.int64)
        s.run(None, {"input_ids": x, "attention_mask": x})
    return s


def ort_runner(sess):
    names = [o.name for o in sess.get_outputs()]

    def f(x):
        o = sess.run(None, {"input_ids": x, "attention_mask": np.ones_like(x)})
        return o[0][0], (o[1][0] if len(names) > 1 else None)
    return f


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run-dir", required=True, help="train.py seed dir (last.pt, backbone/, tokenizer/, kit_meta.json)")
    ap.add_argument("--checkpoint", help="default: the one result.json picked")
    ap.add_argument("--config", help="override the config saved in the checkpoint (export block only is read)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--options", help="comma list, overrides export.options")
    a = ap.parse_args(argv)

    import onnx
    import torch
    from onnxruntime.quantization import (CalibrationDataReader, CalibrationMethod, QuantFormat, QuantType,
                                          quantize_dynamic, quantize_static)
    from transformers import AutoTokenizer
    sys.path.insert(0, str(HERE))
    import train as TR

    rd, out = pathlib.Path(a.run_dir), pathlib.Path(a.out_dir)
    work = out / "_options"
    work.mkdir(parents=True, exist_ok=True)
    ck_name = a.checkpoint or json.load(open(rd / "result.json"))["picked_checkpoint"]
    ck = torch.load(rd / ck_name, map_location="cpu", weights_only=False)
    cfg = ck["config"]
    if a.config:
        cfg["export"] = core.load_config(a.config).get("export", {})
    ex = cfg.get("export", {})
    meta = ck["meta"]
    chs, seq_labels = meta["channels"], meta["seq_labels"]
    W, STEP = cfg["window"]["size"], cfg["window"]["stride"]
    C, S = meta["cls_id"], meta["sep_id"]
    rep = {"task": "student-export", "at": now(), "run_dir": str(rd), "checkpoint": ck_name,
           "checkpoint_sha256": core.sha256(rd / ck_name), "epoch": ck["epoch"], "channels": chs,
           "seq_labels": seq_labels}
    log("CHECKPOINT", rep["checkpoint_sha256"][:12], "epoch", ck["epoch"])

    model = TR.make_student(cfg, len(chs), len(seq_labels), backbone_dir=str(rd / "backbone"))
    model.load_state_dict(ck["state_dict"])
    model.eval()
    tok = AutoTokenizer.from_pretrained(rd / "tokenizer")
    dev_items = core.read_jsonl(cfg["data"]["dev"], ex.get("dev_items"))
    dev, _ = TR.prepare(dev_items, tok, cfg, with_targets=False)
    cal_src = cfg["data"].get("calib") or cfg["data"]["train"]
    cal_items = core.read_jsonl(cal_src, ex.get("calib_items", 96))
    cal_rows = [r for it in cal_items
                for r in core.rows_of(C, S, tok(it["text"], add_special_tokens=False)["input_ids"], W, STEP)[1]]
    rep["data"] = {"dev_items": len(dev), "dev_has_gold": any(any(r["gold"].values()) for r in dev),
                   "calib_source": cal_src, "calib_items": len(cal_items), "calib_windows": len(cal_rows),
                   "dev_sha256": core.sha256(cfg["data"]["dev"]), "calib_sha256": core.sha256(cal_src)}

    # ---- 1. fp32 export + parity vs torch
    class Wrap(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, input_ids, attention_mask):
            return self.m(input_ids, attention_mask)

    fp = work / "raw.fp32.onnx"
    outs = ["tags", "seq"] if seq_labels else ["tags"]
    dyn = {"input_ids": {0: "b", 1: "s"}, "attention_mask": {0: "b", 1: "s"}, "tags": {0: "b", 1: "s"}}
    if seq_labels:
        dyn["seq"] = {0: "b"}
    dummy = torch.ones(1, 37, dtype=torch.long)
    torch.onnx.export(Wrap(model), (dummy, dummy), str(fp), input_names=["input_ids", "attention_mask"],
                      output_names=outs, dynamic_axes=dyn, opset_version=ex.get("opset", 17), dynamo=False)
    s_raw = session(fp)

    def torch_fn(x):
        with torch.no_grad():
            o = model(torch.from_numpy(x), torch.ones_like(torch.from_numpy(x)))
        return (o[0][0].numpy(), o[1][0].numpy()) if isinstance(o, tuple) else (o[0].numpy(), None)

    agree = ntok = 0
    maxdiff = 0.0
    for r in dev:
        if not r["ids"]:
            continue
        for row in r["rows"]:
            x = np.array([row], np.int64)
            lt, _ = torch_fn(x)
            lo, _ = ort_runner(s_raw)(x)
            maxdiff = max(maxdiff, float(np.abs(lt - lo).max()))
        tt, _ = core.predict(torch_fn, r["ids"], C, S, W, STEP)
        to, _ = core.predict(ort_runner(s_raw), r["ids"], C, S, W, STEP)
        agree += int((tt == to).all(1).sum())
        ntok += len(tt)
    par = round(agree / max(ntok, 1), 6)
    rep["parity_torch_vs_onnx_fp32"] = {"token_tag_agreement": par, "max_abs_logit_diff": round(maxdiff, 6),
                                        "tokens": ntok, "min_required": ex.get("parity_min_agreement", 0.999),
                                        "pass": par >= ex.get("parity_min_agreement", 0.999)}
    log("PARITY", json.dumps(rep["parity_torch_vs_onnx_fp32"]))
    if not rep["parity_torch_vs_onnx_fp32"]["pass"]:
        json.dump(rep, open(out / "export_report.json", "w"), indent=1)
        raise SystemExit("fp32 ONNX parity vs torch failed; fix export before quantizing")

    # ---- 2. graph optimisation
    bcfg = json.load(open(rd / "backbone" / "config.json"))
    mtype = bcfg.get("model_type", "")
    mode = ex.get("optimize", "auto")
    if mode == "auto":
        mode = "bert" if mtype in FUSABLE else "none"
    of = work / "opt.fp32.onnx"
    rep["graph"] = {"model_type": mtype, "optimize": mode}
    if mode == "bert":
        from onnxruntime.transformers.optimizer import optimize_model
        try:
            om = optimize_model(str(fp), model_type="bert", num_heads=bcfg.get("num_attention_heads", 12),
                                hidden_size=bcfg.get("hidden_size", 384))
            rep["graph"]["fused_ops"] = {k: v for k, v in om.get_fused_operator_statistics().items() if v}
            om.save_model_to_file(str(of))
        except Exception as e:  # noqa: BLE001
            rep["graph"]["optimizer_error"] = repr(e)[:300]
            shutil.copy(fp, of)
    else:
        shutil.copy(fp, of)
    g = onnx.load(str(of))
    rep["graph"]["nodes"] = len(g.graph.node)
    rep["graph"]["ops"] = dict(collections.Counter(n.op_type for n in g.graph.node))
    rep["graph"]["note"] = ("com.microsoft fused ops (Attention, SkipLayerNormalization, BiasGelu, ...) run in ORT "
                            "(Python, C/C++, Rust ort, onnxruntime-web) but do not load in OpenVINO; use "
                            "export.optimize: none for an OpenVINO-portable file")
    prod = {o: n for n in g.graph.node for o in n.output}
    last = prod[g.graph.output[0].name]
    if last.op_type == "Add":
        last = next((prod[i] for i in last.input if i in prod and prod[i].op_type == "MatMul"), last)
    head_nodes = [last.name]
    attn = [n.name for n in g.graph.node if n.op_type == "Attention"]
    qkv = [n.name for n in g.graph.node if n.op_type == "MatMul"
           and re.search(ex.get("qa_node_regex", r"(query|key|value|q_proj|k_proj|v_proj|Wqkv)"), n.name)]
    log("GRAPH", json.dumps({k: v for k, v in rep["graph"].items() if k != "note"}))

    # ---- 3. pick rule, on disk before scoring
    max_drop = float(ex.get("pick_rule", {}).get("max_layer_drop", 0.01))
    rule = {"written_at": now(), "max_layer_drop": max_drop,
            "rule": f"candidates = int8 options with max per-head dev drop <= {max_drop} (drop = fp32 F1 - option F1 "
                    "vs dev gold when dev has spans, else 1 - exact-span agreement with fp32); pick lowest dev token "
                    "flip rate vs fp32, then lowest 1-thread per-window p50. Dev only; fixed before any test scoring; "
                    "no override after test.",
            "options": (a.options.split(",") if a.options else ex.get("options", ["D0", "D1", "QA", "S1"]))}
    json.dump(rule, open(out / "pick_rule.json", "w"), indent=1)
    log("RULE", rule["rule"])

    # ---- reference fp32 on dev
    s32 = session(of)
    ref_tags = [core.predict(ort_runner(s32), r["ids"], C, S, W, STEP) if r["ids"] else (None, []) for r in dev]
    ref_spans = [core.decode(r["text"], r["offs"], t, chs) for r, (t, _) in zip(dev, ref_tags)]
    heads = list(dict.fromkeys(chs))
    gold = {h: [r["gold"].get(h, []) for r in dev] for h in heads}
    lat_rows = sorted((row for r in dev for row in r["rows"]), key=len, reverse=True)[:ex.get("latency_windows", 200)]

    def measure(name, path, desc):
        t1 = time.time()
        s = session(path)
        tags = [core.predict(ort_runner(s), r["ids"], C, S, W, STEP) if r["ids"] else (None, []) for r in dev]
        spans = [core.decode(r["text"], r["offs"], t, chs) for r, (t, _) in zip(dev, tags)]
        flips = n = 0
        seq_flip = seq_n = 0
        for (ta, sa), (tb, sb) in zip(ref_tags, tags):
            if ta is None:
                continue
            flips += int((ta != tb).sum())
            n += ta.size
            if sa:
                pa = core.sigmoid(core.pool_seq(sa)) >= 0.5
                pb = core.sigmoid(core.pool_seq(sb)) >= 0.5
                seq_flip += int((pa != pb).sum())
                seq_n += pa.size
        o = {"desc": desc, "bytes": os.path.getsize(path), "sha256": core.sha256(path),
             "dev_agreement_vs_fp32": {h: core.span_f1([x[h] for x in ref_spans], [x[h] for x in spans]) for h in heads},
             "dev_token_flip_rate": round(flips / max(n, 1), 6)}
        if seq_n:
            o["dev_seq_label_flip_rate"] = round(seq_flip / seq_n, 6)
        if rep["data"]["dev_has_gold"]:
            o["dev_f1"] = {h: core.span_f1(gold[h], [x[h] for x in spans]) for h in heads}
            if name != "fp32":
                f32 = opts["fp32"]["dev_f1"]
                o["dev_drop_vs_fp32"] = {h: round(f32[h] - o["dev_f1"][h], 6) for h in heads}
                o["dev_drop_ci95"] = {h: core.bootstrap_f1_diff(gold[h], [x[h] for x in ref_spans], [x[h] for x in spans])
                                      for h in heads}
                o["max_layer_drop"] = max(o["dev_drop_vs_fp32"].values())
        elif name != "fp32":
            o["max_layer_drop"] = round(1 - min(o["dev_agreement_vs_fp32"].values()), 6)
        s1 = session(path, 1)
        v = []
        for row in lat_rows:
            x = np.array([row], np.int64)
            t = time.perf_counter()
            s1.run(None, {"input_ids": x, "attention_mask": np.ones_like(x)})
            v.append((time.perf_counter() - t) * 1e3)
        o["window_ms_1thread"] = dict(core.stats(v), window_tokens=len(lat_rows[0]) if lat_rows else 0)
        ops = collections.Counter((nd.domain or "ai.onnx", nd.op_type) for nd in onnx.load(str(path)).graph.node)
        o["com_microsoft_ops"] = sorted({op for (d, op) in ops if d == "com.microsoft"})
        o["openvino_loadable"] = not o["com_microsoft_ops"]
        o["eval_s"] = round(time.time() - t1, 1)
        opts[name] = o
        log("OPT", name, json.dumps({k: o[k] for k in ("dev_agreement_vs_fp32", "dev_token_flip_rate",
                                                         "window_ms_1thread") if k in o}))

    class Reader(CalibrationDataReader):
        def __init__(self, rows):
            self.rows, self.i = rows, 0

        def get_next(self):
            if self.i >= len(self.rows):
                return None
            x = np.array([self.rows[self.i]], np.int64)
            self.i += 1
            return {"input_ids": x, "attention_mask": np.ones_like(x)}

        def rewind(self):
            self.i = 0

    def qdyn(path, per_channel, **kw):
        quantize_dynamic(str(of), str(path), weight_type=QuantType.QInt8, per_channel=per_channel,
                         extra_options={"DefaultTensorType": onnx.TensorProto.FLOAT}, **kw)
        return path

    def logit_mean(sess):
        acc, n = None, 0
        for r in cal_rows:
            x = np.array([r], np.int64)
            lg = sess.run(None, {"input_ids": x, "attention_mask": np.ones_like(x)})[0][0][1:-1]
            acc = lg.sum(0) if acc is None else acc + lg.sum(0)
            n += len(lg)
        return acc / n

    def bias_correct(src, path):
        import onnx.helper
        import onnx.numpy_helper
        corr = (logit_mean(s32) - logit_mean(session(src))).astype(np.float32)
        m = onnx.load(str(src))
        gout = m.graph.output[0].name
        pn = next(nd for nd in m.graph.node if gout in nd.output)
        pn.output[list(pn.output).index(gout)] = gout + "_prebc"
        m.graph.initializer.append(onnx.numpy_helper.from_array(corr, "bc_logit_shift"))
        m.graph.node.append(onnx.helper.make_node("Add", [gout + "_prebc", "bc_logit_shift"], [gout], name="bc_add"))
        onnx.save(m, str(path))
        rep.setdefault("bias_correction", {})[path.name] = {"max_abs_shift": round(float(np.abs(corr).max()), 4)}
        return path

    def qa(path):
        if attn:
            return qdyn(path, True, op_types_to_quantize=["Attention"])
        if not qkv:
            raise RuntimeError("QA: no fused Attention and no MatMul matches qa_node_regex")
        return qdyn(path, True, nodes_to_quantize=qkv)

    def static(path):
        quantize_static(str(of), str(path), Reader(cal_rows), quant_format=QuantFormat.QDQ, per_channel=True,
                        activation_type=QuantType.QUInt8, weight_type=QuantType.QInt8,
                        calibrate_method=CalibrationMethod.MinMax, op_types_to_quantize=["MatMul"],
                        nodes_to_exclude=head_nodes, extra_options={"DefaultTensorType": onnx.TensorProto.FLOAT})
        return path

    plan = {"D0": ("dynamic int8 per-tensor", lambda p: qdyn(p, False)),
            "D1": ("dynamic int8 per-channel", lambda p: qdyn(p, True)),
            "QA": ("partial: attention / Q,K,V int8 only, other MatMuls fp32", qa),
            "S1": ("static QDQ per-channel, MinMax on the calibration set, head MatMul fp32", static),
            "D1BC": ("D1 + output bias correction (calibration windows)",
                     lambda p: bias_correct(work / "D1.onnx" if (work / "D1.onnx").exists() else qdyn(work / "D1.onnx", True), p))}
    opts = {}
    measure("fp32", of, f"fp32 reference ({mode} graph)")
    for name in rule["options"]:
        if name not in plan:
            opts[name] = {"error": f"unknown option {name}"}
            continue
        desc, fn = plan[name]
        try:
            t1 = time.time()
            p = fn(work / f"{name}.onnx")
            q_s = round(time.time() - t1, 1)
            measure(name, p, desc)
            opts[name]["quantize_s"] = q_s
        except Exception as e:  # noqa: BLE001
            opts[name] = {"desc": desc, "error": repr(e)[:400]}
            log("OPT", name, "ERROR", repr(e)[:400])

    # ---- 6. pick by the rule written above
    cand = [n for n, o in opts.items() if n != "fp32" and "error" not in o and o["max_layer_drop"] <= max_drop]
    pick = min(cand, key=lambda n: (opts[n]["dev_token_flip_rate"], opts[n]["window_ms_1thread"]["p50"])) if cand else None
    rep["pick_rule"] = rule
    # M4: drop <= max_drop on every head and the paired 95% interval of the drop reaches 0 (no significant loss)
    inside = bool(pick) and all(lo <= 0 for lo, _ in opts[pick].get("dev_drop_ci95", {}).values())
    rep["pick"] = {"option": pick, "picked_at": now(), "candidates": cand, "m4_drop_inside_interval": inside,
                   "m4_pass": bool(pick) and inside}
    rep["options"] = opts
    log("PICK", pick, "candidates", cand)

    shutil.copy(of, out / "model.fp32.onnx")
    model_file = "model.fp32.onnx"
    if pick:
        shutil.copy(work / f"{pick}.onnx", out / "model.int8.onnx")
        model_file = "model.int8.onnx"
    shutil.copy(rd / "tokenizer" / "tokenizer.json", out / "tokenizer.json")
    sq = cfg["heads"].get("sequence") or {}
    labels = {"format": "student-kit/1", "model_file": model_file, "fp32_file": "model.fp32.onnx",
              "model_sha256": core.sha256(out / model_file), "tokenizer_file": "tokenizer.json",
              "tokenizer_sha256": core.sha256(out / "tokenizer.json"), "cls_id": C, "sep_id": S,
              "window": W, "stride": STEP, "channels": chs, "token_heads": meta["token_heads"],
              "sequence": ({"labels": seq_labels, "threshold": sq.get("threshold", 0.5), "pool": sq.get("pool", "max")}
                           if seq_labels else None),
              "inputs": ["input_ids", "attention_mask"], "outputs": outs, "quant_option": pick,
              "run_name": cfg.get("run_name"), "checkpoint_sha256": rep["checkpoint_sha256"]}
    json.dump(labels, open(out / "labels.json", "w"), indent=1)
    rep["files"] = {f: core.sha256(out / f) for f in ("model.fp32.onnx", model_file, "tokenizer.json", "labels.json")}
    rep["wall_s"] = round(time.time() - T0, 1)
    json.dump(rep, open(out / "export_report.json", "w"), indent=1, default=str)
    log("DONE", json.dumps(rep["files"]))
    if not pick:
        raise SystemExit("no int8 option passed the rule; shipped labels.json points at fp32")


if __name__ == "__main__":
    main()
