"""S6 speed (M5): the four numbers, stage breakdown, process x thread layouts, CPU flags, same-machine rule.

    python bench.py --model-dir ship/x [--model-dir ship/y ...] --jsonl sample.jsonl [--vcpu 4] \
        [--items-per-min 600] [--out speed_report.json] [--compare old_speed_report.json]

Run on the reference hardware (Kaggle CPU / the target box), never to compare against a number from another
machine: every model being compared goes in ONE call (--model-dir repeated), so all numbers share one machine.
--compare only reports ratios when the other report's machine fingerprint (CPU model, vCPU count, flags) matches.
Measures, per model (method of pipeline/kaggle/ship/speed_v1 and bench/alt_bench_v1):
  window_ms_1thread  one ONNX call on a full window (window + 2 tokens), batch 1, 1 thread, after warm-up
  item_ms_1x1        per-item wall p50 / p95 / mean, 1 process x 1 thread, with stage breakdown
                     (tokenize / model / decode) and process CPU ms per item
  layouts            items/s for N x 1 (N spawned processes, 1 thread) and 1 x N (one process, N threads);
                     vCPU-s/item = N * wall / items (allocated) and measured process CPU s / item
  budget (M5)        per-item budget = 60000 * vcpu / items_per_min vCPU-ms; pass if the best layout's
                     allocated vCPU-ms/item <= budget (and p95 is reported beside it)
Use a representative sample with a fixed seed (first project: 1,000 items); state it in the report.
"""
import argparse
import hashlib
import json
import multiprocessing as mp
import os
import pathlib
import platform
import re
import subprocess
import sys
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import core  # noqa: E402
import runtime as RT  # noqa: E402

FLAGS = ("avx2", "avx512f", "avx512_vnni", "avx512vnni", "avx_vnni", "avxvnni", "avx512_bf16", "amx_bf16", "amx_int8",
         "amx_tile")


def cpu_info():
    info = {"platform": platform.platform(), "machine": platform.machine(), "vcpu": os.cpu_count(),
            "python": sys.version.split()[0]}
    model, flags = None, None
    try:
        txt = open("/proc/cpuinfo").read()
        model = re.search(r"model name\s*:\s*(.+)", txt).group(1).strip()
        flags = set(re.search(r"flags\s*:\s*(.+)", txt).group(1).split())
    except (OSError, AttributeError):
        pass
    if model is None and sys.platform == "darwin":
        try:
            model = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True,
                                   text=True).stdout.strip()
            flags = set(subprocess.run(["sysctl", "-n", "machdep.cpu.features", "machdep.cpu.leaf7_features"],
                                       capture_output=True, text=True).stdout.lower().split())
        except OSError:
            pass
    if flags is None:
        try:
            import cpuinfo  # py-cpuinfo, optional
            ci = cpuinfo.get_cpu_info()
            model = model or ci.get("brand_raw")
            flags = set(ci.get("flags", []))
        except ImportError:
            info["flags_note"] = "flags unknown: no /proc/cpuinfo and py-cpuinfo not installed"
    info["cpu"] = model or platform.processor()
    info["flags"] = sorted(f for f in FLAGS if flags and f in flags) if flags is not None else None
    info["vnni"] = bool(flags and flags & {"avx512_vnni", "avx512vnni", "avx_vnni", "avxvnni"})
    info["avx512"] = bool(flags and "avx512f" in flags)
    info["amx"] = bool(flags and flags & {"amx_int8", "amx_bf16", "amx_tile"})
    return info


def fingerprint(ci):
    key = json.dumps({"cpu": ci["cpu"], "vcpu": ci["vcpu"], "flags": ci["flags"]}, sort_keys=True)
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def window_ms(rt, items, n=300):
    rows = []
    for it in items:
        ids, _ = rt.encode(it["text"])
        if len(ids) >= rt.W:
            rows.append([rt.C] + ids[:rt.W] + [rt.S])
        if len(rows) >= 50:
            break
    synthetic = not rows
    if synthetic:   # no item fills a window: repeat the longest item's pieces
        ids = max((rt.encode(it["text"])[0] for it in items), key=len) or [rt.C]
        rows = [[rt.C] + (ids * (rt.W // max(len(ids), 1) + 1))[:rt.W] + [rt.S]]
    xs = [np.array([r], np.int64) for r in rows]
    for x in xs[:5] * 4:
        rt.run_window(x)
    v = []
    for i in range(n):
        x = xs[i % len(xs)]
        t = time.perf_counter()
        rt.run_window(x)
        v.append((time.perf_counter() - t) * 1e3)
    return dict(core.stats(v), window_tokens=len(rows[0]), repeated_ids=synthetic)


def run_layout(model_dir, items, procs, threads):
    """-> wall, list of timings dicts"""
    items = [dict(it, _timings=True) for it in items]
    if procs == 1:
        RT._init(model_dir, threads)
        for it in items[:5]:
            RT._one(it)
        w0 = time.perf_counter()
        res = [RT._one(it) for it in items]
        return time.perf_counter() - w0, [r["timings_ms"] for r in res]
    with mp.get_context("spawn").Pool(procs, initializer=RT._init, initargs=(model_dir, threads)) as pool:
        pool.map(RT._one, items[:procs * 2])   # warm every worker
        w0 = time.perf_counter()
        res = pool.map(RT._one, items, chunksize=1)
        wall = time.perf_counter() - w0
    return wall, [r["timings_ms"] for r in res]


def summarise(wall, tm, procs, threads):
    n = len(tm)
    return {"layout": f"{procs}x{threads}", "processes": procs, "threads": threads, "items": n,
            "items_per_s": round(n / wall, 3), "wall_s": round(wall, 2),
            "vcpu_s_per_item_allocated": round(procs * threads * wall / n, 4),
            "cpu_s_per_item_measured": round(sum(t["cpu_ms"] for t in tm) / n / 1e3, 4),
            "item_ms": core.stats([t["total_ms"] for t in tm])}


def bench_model(model_dir, items, vcpu):
    rt = RT.Runtime(model_dir, threads=1)
    rep = {"model_dir": str(model_dir), "model_sha256": rt.model_sha256, "versions": rt.versions,
           "window_ms_1thread": window_ms(rt, items)}
    for it in items[:5]:
        rt.predict(it["text"], it.get("id", "x"))
    tm = []
    for it in items:
        t = {}
        c0 = time.process_time()
        rt.predict(it["text"], it.get("id", "x"), timings=t)
        t["cpu_ms"] = (time.process_time() - c0) * 1e3
        tm.append(t)
    rep["item_ms_1x1"] = {k: core.stats([t[k] for t in tm])
                          for k in ("total_ms", "tokenize_ms", "model_ms", "decode_ms", "cpu_ms")}
    rep["item_ms_1x1"]["windows_per_item"] = core.stats([t["windows"] for t in tm])
    rep["item_ms_1x1"]["tokens_per_item"] = core.stats([t["tokens"] for t in tm])
    tot = sum(t["total_ms"] for t in tm)
    rep["stage_share"] = {k: round(sum(t[k] for t in tm) / tot, 4) for k in ("tokenize_ms", "model_ms", "decode_ms")}
    del rt
    rep["layouts"] = {}
    for procs, threads in sorted({(vcpu, 1), (1, vcpu), (1, 1)}):
        wall, ltm = run_layout(model_dir, items, procs, threads)
        rep["layouts"][f"{procs}x{threads}"] = summarise(wall, ltm, procs, threads)
        print(f"[bench] {model_dir} {procs}x{threads}", json.dumps(rep["layouts"][f"{procs}x{threads}"]), flush=True)
    best = max(rep["layouts"].values(), key=lambda r: r["items_per_s"])
    rep["best_layout"] = best["layout"]
    rep["four_numbers"] = {"ms_per_window_1thread_p50": rep["window_ms_1thread"]["p50"],
                           "ms_per_item_p50": rep["item_ms_1x1"]["total_ms"]["p50"],
                           "ms_per_item_p95": rep["item_ms_1x1"]["total_ms"]["p95"],
                           "vcpu_s_per_item": best["vcpu_s_per_item_allocated"],
                           "items_per_s": best["items_per_s"], "layout": best["layout"]}
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model-dir", required=True, action="append", help="repeat to bench several on one machine")
    ap.add_argument("--jsonl", required=True, help="representative sample {id, text}")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--vcpu", type=int, default=os.cpu_count())
    ap.add_argument("--items-per-min", type=float, help="owner target (task card) for the M5 budget")
    ap.add_argument("--budget-vcpu", type=int, help="vCPU of the target box (default --vcpu)")
    ap.add_argument("--compare", help="earlier speed_report.json; ratios only if the machine matches")
    ap.add_argument("--out", default="speed_report.json")
    a = ap.parse_args(argv)
    items = core.read_jsonl(a.jsonl, a.limit)
    ci = cpu_info()
    rep = {"task": "student-speed", "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "machine": ci,
           "machine_fingerprint": fingerprint(ci), "sample": {"file": a.jsonl, "sha256": core.sha256(a.jsonl),
                                                              "items": len(items)},
           "vcpu_used": a.vcpu, "models": {}}
    print("[bench] machine", json.dumps(ci), flush=True)
    for md in a.model_dir:
        rep["models"][md] = bench_model(md, items, a.vcpu)
    if a.items_per_min:
        bv = a.budget_vcpu or a.vcpu
        budget = 60000.0 * bv / a.items_per_min
        rep["m5"] = {"items_per_min_target": a.items_per_min, "vcpu": bv, "budget_vcpu_ms_per_item": round(budget, 2),
                     "per_model": {md: {"vcpu_ms_per_item": round(m["four_numbers"]["vcpu_s_per_item"] * 1e3, 2),
                                        "p95_ms": m["four_numbers"]["ms_per_item_p95"],
                                        "pass": m["four_numbers"]["vcpu_s_per_item"] * 1e3 <= budget}
                                   for md, m in rep["models"].items()},
                     "note": "evaluator checks this on the reference hardware named on the task card"}
    if a.compare:
        old = json.load(open(a.compare))
        same = old.get("machine_fingerprint") == rep["machine_fingerprint"]
        rep["compare"] = {"file": a.compare, "same_machine": same}
        if same:
            rep["compare"]["ratios_items_per_s"] = {
                md: {omd: round(m["four_numbers"]["items_per_s"] / om["four_numbers"]["items_per_s"], 3)
                     for omd, om in old["models"].items()} for md, m in rep["models"].items()}
        else:
            rep["compare"]["note"] = ("different machine fingerprint: no ratios. Re-run both models in one bench.py "
                                      "call (--model-dir A --model-dir B) on one machine")
    json.dump(rep, open(a.out, "w"), indent=1)
    print("[bench] done", json.dumps({md: m["four_numbers"] for md, m in rep["models"].items()}), flush=True)


if __name__ == "__main__":
    main()
