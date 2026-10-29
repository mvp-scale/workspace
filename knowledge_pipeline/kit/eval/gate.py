"""Quality gate (M1) + gate report (templates/gate-report.md). Stdlib only.

Inputs:
  SCORE : score_spans.py output (layers[L][mode] = {f1, lo, hi, ...}).
  GATES : {"layers": {"PER": {"mode": "overlap", "iaa": 0.82}, "ORG": {"mode": "exact", "gate": 0.5}}}
          gate = 0.8 x iaa unless "gate" is given. Or --agreement IAA.json (agreement.py spans output) + --mode:
          every layer in IAA becomes a gate with iaa = its F1 in that mode.
  META  : optional {"task", "model", "model_sha", "test_set", "picked_on", "hardware", "speed": {measure: value},
          "verdict": [lines]} for the header and speed rows; scorer sha defaults to the score file's.
Pass per layer = lower bound of the 95% interval >= gate (M1). A gated layer missing from SCORE fails.
Output: JSON {"M1": {"pass", "layers": {...}}} on stdout; the markdown report with --md PATH (or --md - for stdout).
Exit 1 when any gated layer fails (scriptable).

CLI:
  python gate.py SCORE GATES [--meta META] [--md report.md]
  python gate.py SCORE --agreement iaa.json --mode overlap [--md -]
  python gate.py --sha
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import score_spans as S  # noqa: E402

GATE_K = 0.8


def gates_from_agreement(iaa, mode):
    return {"layers": {L: {"mode": mode, "iaa": v[mode]["f1"]} for L, v in S._read(iaa)["layers"].items()}}


def check(score, gates):
    sc, gs = S._read(score)["layers"], S._read(gates)["layers"]
    out = {}
    for L, g in gs.items():
        m = g.get("mode", "overlap")
        gate = g["gate"] if "gate" in g else round(GATE_K * g["iaa"], 4)
        r = sc.get(L, {}).get(m)
        if r is None:
            out[L] = {"mode": m, "iaa": g.get("iaa"), "gate": gate, "f1": None, "lo": None, "hi": None,
                      "pass": False, "why": "layer missing from score"}
            continue
        ok = r["lo"] is not None and r["lo"] >= gate
        out[L] = {"mode": m, "iaa": g.get("iaa"), "gate": gate, "f1": r["f1"], "lo": r["lo"], "hi": r["hi"], "pass": ok}
    return {"M1": {"pass": all(v["pass"] for v in out.values()) and bool(out), "layers": out}}


def _c(x):
    return "" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))


def report(res, score, meta=None):
    meta, sm = meta or {}, S._read(score).get("meta", {})
    lines = [f"# Gate report: {meta.get('task', '<task ID>')} {meta.get('model', '<model name>')}", "",
             "| Item | Value |", "|---|---|",
             f"| Model file + sha | {meta.get('model_sha', '')} |",
             f"| Scorer + sha | `{sm.get('tool', 'kit/eval/score_spans.py')}` {meta.get('scorer_sha', sm.get('scorer_sha', ''))} |",
             f"| Test set + sha, size | {meta.get('test_set', '')}{', ' if meta.get('test_set') else ''}{sm.get('n_items', '')} items |",
             f"| Model picked on | {meta.get('picked_on', 'dev only (rule written before scoring test)')} |",
             f"| Hardware for speed | {meta.get('hardware', '')} |", "",
             "## Quality (one row per layer)", "",
             f"| Layer | Metric | Score | 95% interval (bootstrap by item, n={sm.get('n_boot', '')}, seed {sm.get('seed', '')}) "
             "| IAA | Gate (0.8 × IAA) | Pass on lower bound? |",
             "|---|---|---|---|---|---|---|"]
    for L, v in res["M1"]["layers"].items():
        iv = "" if v["lo"] is None else f"{v['lo']:.3f} – {v['hi']:.3f}"
        lines.append(f"| {L} | {v['mode']} F1 | {_c(v['f1'])} | {iv} | {_c(v['iaa'])} | {_c(v['gate'])} | "
                     f"{'pass' if v['pass'] else 'FAIL' + (' (' + v['why'] + ')' if 'why' in v else '')} |")
    speed = meta.get("speed", {})
    rows = ["ms per model call (window size)", "ms per typical item, p50 / p95", "vCPU-s per item",
            "items/s on N vCPU (process × thread layout)", "$ per million items (at stated vCPU price)"]
    lines += ["", "## Speed and cost", "", "| Measure | Value |", "|---|---|"]
    lines += [f"| {k} | {speed.get(k, '')} |" for k in rows + [k for k in speed if k not in rows]]
    fails = [L for L, v in res["M1"]["layers"].items() if not v["pass"]]
    lines += ["", "## Verdict", "",
              f"- M1 (every gated layer: lower bound ≥ 0.8 × IAA): {'pass' if res['M1']['pass'] else 'FAIL'}"
              + (f" — failing: {', '.join(fails)}" if fails else "")]
    lines += [f"- {x}" for x in meta.get("verdict", [])]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("score", nargs="?")
    ap.add_argument("gates", nargs="?")
    ap.add_argument("--agreement")
    ap.add_argument("--mode", choices=list(S.MODES), default="overlap")
    ap.add_argument("--meta")
    ap.add_argument("--md")
    ap.add_argument("--sha", action="store_true")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if a.sha:
        print(S.sha(__file__))
        return
    if not a.score or not (a.gates or a.agreement):
        ap.error("need SCORE and GATES (or --agreement)")
    gates = S._read(a.gates) if a.gates else gates_from_agreement(a.agreement, a.mode)
    res = check(a.score, gates)
    res["meta"] = {"tool": "kit/eval/gate.py", "sha": S.sha(__file__)}
    md = report(res, a.score, S._read(a.meta) if a.meta else None)
    if a.md == "-":
        print(md)
    else:
        if a.md:
            pathlib.Path(a.md).write_text(md, encoding="utf-8")
        print(json.dumps(res, indent=1))
    sys.exit(0 if res["M1"]["pass"] else 1)


if __name__ == "__main__":
    main()
