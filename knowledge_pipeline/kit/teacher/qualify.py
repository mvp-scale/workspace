"""Teacher qualification (D4): pilot a teacher on <= 50 gold items, score with knowledge_pipeline/kit/eval, decide.
D4 = teacher vs gold clears the student gate (lower 95% bound >= 0.8 x IAA) on every layer it labels.

    python qualify.py --spec SPEC --gold gold.jsonl --iaa iaa.json --out RUN/qualify --teacher claude [--key-file F]
    python qualify.py --spec SPEC --gold gold.jsonl --iaa iaa.json --out RUN/qualify --teacher open \\
        --base-url http://localhost:8000/v1 --model qwen2.5-32b-instruct
    python qualify.py ... --labels RUN/qualify/labels.jsonl      # score existing pilot labels only (no calls)

gold.jsonl rows: {id, text, spans: [{start, end, label, layer?}]} (frozen gold from S2; never the test split used for
the student's final claim). iaa.json: {score layer: IAA} (or gate.py GATES, or agreement.py output); the layers listed are the layers the teacher must pass.
--score-on picks the score layer name of a span: label (default) | layer | layer_label ("ENTITY:PER").
Claude pilots run synchronously (claude_batch --sync semantics, spec cap applies). Exit 0 = D4 pass, 1 = fail,
4 = evaluator missing. Report: OUT/teacher_gate.json (+ score.json).
"""
import argparse
import importlib
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
EVAL = HERE.parent / "eval"
for _p in (str(HERE), str(EVAL)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import task_spec as TS  # noqa: E402
import claude_batch as CB  # noqa: E402
import candidates as C  # noqa: E402

MAX_PILOT = 50
GATE_FACTOR = 0.8


def span_key(s, on):
    return {"label": s.get("label", ""), "layer": s.get("layer", ""),
            "layer_label": f"{s.get('layer', '')}:{s.get('label', '')}"}[on]


def to_doc(rows, on, get_spans):
    return {"items": [{"id": str(r["id"]), "spans": [{"start": s["start"], "end": s["end"], "label": span_key(s, on)}
                                                    for s in get_spans(r)]} for r in rows]}


def score(cand, ref, out):
    """kit/eval/score_spans.score when importable; else shell out to the CLI; else TODO (None)."""
    try:
        S = importlib.import_module("score_spans")
        return S.score(cand, ref), "kit/eval/score_spans.py:score"
    except ImportError:
        pass
    cli = EVAL / "score_spans.py"
    if not cli.exists():
        return None, "TODO: knowledge_pipeline/kit/eval/score_spans.py missing; D4 cannot be decided"
    cp, rp, sp = out / "cand.json", out / "ref.json", out / "score.json"
    CB.write_json(cp, cand)
    CB.write_json(rp, ref)
    subprocess.run([sys.executable, "-I", str(cli), str(cp), str(rp), "--out", str(sp)], check=True)
    return json.loads(sp.read_text(encoding="utf-8")), "kit/eval/score_spans.py (CLI)"


def gate_spec(iaa, mode):
    """iaa.json -> gate.py GATES {"layers": {L: {"mode", "iaa"|"gate"}}}. Accepts {L: IAA}, a GATES doc, or an
    agreement.py output (layers[L][mode].f1)."""
    lay = iaa.get("layers", iaa) if isinstance(iaa, dict) else {}
    out = {}
    for L, v in lay.items():
        if isinstance(v, (int, float)):
            out[L] = {"mode": mode, "iaa": float(v)}
        elif isinstance(v, dict) and ("iaa" in v or "gate" in v):
            out[L] = {"mode": mode, **v}
        elif isinstance(v, dict) and mode in v:
            out[L] = {"mode": mode, "iaa": v[mode]["f1"]}
    return {"layers": out}


def gates(sc, gs):
    """kit/eval/gate.check -> {"pass", "layers"}; inline fallback with the same rule if gate.py is absent."""
    try:
        G = importlib.import_module("gate")
        return G.check(sc, gs)["M1"], "kit/eval/gate.py:check"
    except ImportError:
        pass
    # TODO: fallback only while kit/eval/gate.py is absent (rule M1/D4: lower 95% bound >= 0.8 x IAA).
    res = {}
    for L, g in gs["layers"].items():
        r = (sc.get("layers", {}).get(L) or {}).get(g["mode"]) or {}
        gate = g["gate"] if "gate" in g else round(GATE_FACTOR * g["iaa"], 4)
        res[L] = {"mode": g["mode"], "iaa": g.get("iaa"), "gate": gate, "f1": r.get("f1"), "lo": r.get("lo"),
                  "hi": r.get("hi"), "pass": r.get("lo") is not None and r["lo"] >= gate}
    return {"pass": bool(res) and all(x["pass"] for x in res.values()), "layers": res}, "inline fallback (TODO)"


def run_teacher(a, spec, items, out):
    """Pilot labels for items (text only, gold stripped). -> labels rows."""
    cands = None
    if spec.mode == "verify":
        if a.cands:
            cands = CB.load_cands(a.cands)
        else:
            P = C.from_config(spec.candidates)
            cands = {str(it["id"]): (CB.sha(it["text"]), C.propose(it["text"], P)) for it in items}
    if a.teacher == "claude":
        reqs = CB.build_requests(spec, items, cands, skip=CB.done_ids(out))
        key = CB.read_key(a.key_file)
        R = CB.Run(spec, out, CB.make_client(key), CB.load_prices(a.prices), a.cap_usd, run_name="qualify")
        R.run_sync(reqs)
        if R.stopped:
            print(f"STOPPED {R.stopped}")
    else:
        import open_model as OM
        import os
        reqs = OM.build(spec, items, cands, skip=CB.done_ids(out))
        key = os.environ.get(a.api_key_env) if a.api_key_env else None
        OM.OpenRun(spec, out, a.base_url, a.model, a.guided, a.workers, a.cap_usd, a.usd_per_hour, key).run(reqs)
    return CB.read_jsonl(out / "labels.jsonl")


def decide(spec, gold, labels, iaa, on, mode, out, teacher):
    by = {r["item_id"]: r for r in labels}
    cand = to_doc([{"id": g["id"]} for g in gold], on,
                  lambda r: (by.get(str(r["id"])) or {}).get("label", {}).get("spans", []))
    ref = to_doc(gold, on, lambda r: r.get("spans", []))
    sc, scorer = score(cand, ref, out)
    if sc is None:
        print(scorer)
        return 4, None
    CB.write_json(out / "score.json", sc)
    gs = gate_spec(iaa, mode)
    if not gs["layers"]:
        raise SystemExit("iaa file names no layers: D4 needs a gate for every layer the teacher labels")
    gt, gimpl = gates(sc, gs)
    models = sorted({r["provenance"]["model"] for r in labels})
    rep = {"acceptance": "D4", "teacher": teacher, "models": models, "prompt_version": spec.prompt_version,
           "spec_sha256": spec.sha256, "n_gold": len(gold), "n_labelled": sum(str(g["id"]) in by for g in gold),
           "score_on": on, "mode": mode, "scorer": scorer, "scorer_sha": (sc.get("meta") or {}).get("scorer_sha"),
           "gate_impl": gimpl, "gate_rule": "lower 95% bound >= 0.8 x IAA, every layer in iaa", "gates": gt,
           "decision": "PASS" if gt.get("pass") else "FAIL", "date": CB.now()}
    CB.write_json(out / "teacher_gate.json", rep)
    for L, x in (gt.get("layers") or {}).items():
        print(f"{L}: f1={x.get('f1')} lo={x.get('lo')} gate={x.get('gate')} {'pass' if x.get('pass') else 'FAIL'}")
    print(f"D4 {rep['decision']} ({teacher} {models} {spec.prompt_version}) -> {out / 'teacher_gate.json'}")
    return (0 if gt.get("pass") else 1), rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--iaa", required=True, help="JSON {score layer: IAA}")
    ap.add_argument("--out", required=True)
    ap.add_argument("--teacher", choices=["claude", "open"], default="claude")
    ap.add_argument("--labels", help="score these pilot labels; no teacher calls")
    ap.add_argument("--cands")
    ap.add_argument("--n", type=int, default=MAX_PILOT)
    ap.add_argument("--score-on", choices=["label", "layer", "layer_label"], default="label")
    ap.add_argument("--mode", choices=["exact", "overlap"], default="exact")
    ap.add_argument("--key-file")
    ap.add_argument("--prices", default=str(CB.PRICES))
    ap.add_argument("--cap-usd", type=float)
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--model")
    ap.add_argument("--guided", default="json_schema")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--usd-per-hour", type=float, default=0.0)
    ap.add_argument("--api-key-env")
    a = ap.parse_args(argv)
    if a.n > MAX_PILOT:
        raise SystemExit(f"pilot is <= {MAX_PILOT} items (S3)")
    spec = TS.load(a.spec)
    gold = CB.read_jsonl(a.gold)[: a.n]
    iaa = json.loads(pathlib.Path(a.iaa).read_text(encoding="utf-8"))
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.labels:
        labels = CB.read_jsonl(a.labels)
    else:
        if a.teacher == "open" and not a.model:
            raise SystemExit("--teacher open needs --model")
        labels = run_teacher(a, spec, [{"id": g["id"], "text": g["text"]} for g in gold], out)
    teacher = a.teacher if not a.labels else (labels[0]["provenance"]["teacher"] if labels else "?")
    return decide(spec, gold, labels, iaa, a.score_on, a.mode, out, teacher)[0]


if __name__ == "__main__":
    sys.exit(main())
