#!/usr/bin/env python3
"""Time: onset lag and false-alarm rate over a running conversation.

No dialogue in probes/v2/manipulation_windows.json carries a turn-level onset label -- only a
whole-dialogue manipulative/not label (confirmed by reading the file: dialogue keys are
id/source_id/turns/n_turns/manipulative/technique/vulnerability/label_scope, no per-turn field).
Fabricating a per-turn "true onset" would violate this project's own rule against inventing labels
the data doesn't have.

What's real and doesn't need one: replay each dialogue turn by turn over the "full so far" window
(the same manipulation question used everywhere else), and measure, self-referentially against the
model's own running score --
  - detection lag: for a manipulative dialogue, how early (as a share of the dialogue) the running
    score first crosses 0.5 and never drops back below it before the end (a "committed" alarm, not
    a one-turn blip);
  - false-alarm rate: for a non-manipulative dialogue, how often the running score crosses 0.5 at
    all, per 10 turns (there is no real-world timestamp in this data, so "per minute" would be a
    fabricated unit -- "per 10 turns" is what the data actually supports).

Needs the demo server (python3 demo/server.py) for /api/batch, and probes/v2/manipulation_windows.json.

    python3 probes/lab_time.py --backend semif [--limit 200]
"""
import argparse, json, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "probe-runs-v2" / "_time"


def question():
    first = json.loads((ROOT / "probes/v2/manipulation_dialogue.jsonl").read_text().splitlines()[0])
    return first["question"]


def render(turns):
    return "\n".join(f'{t["speaker"]}: {t["text"]}' for t in turns)


def batch(backend, items, base):
    req = urllib.request.Request(base + "/api/batch", json.dumps({"backend": backend, "items": items}).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True)
    ap.add_argument("--limit", type=int, default=200, help="use only the first N dialogues (dataset is already balanced by construction)")
    ap.add_argument("--base", default="http://127.0.0.1:8100")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    data = json.loads((ROOT / "probes/v2/manipulation_windows.json").read_text())
    dialogues = (data["dialogues"] if isinstance(data, dict) else data)[: a.limit]
    q = question()

    jobs = []  # (dialogue index, turn end)
    for di, d in enumerate(dialogues):
        for k in range(1, len(d["turns"]) + 1):
            jobs.append((di, k))
    print(f"{len(dialogues)} dialogues, {len(jobs)} calls on {a.backend} (window = everything so far)", flush=True)

    probs, t0 = {}, time.time()
    for i in range(0, len(jobs), 200):
        chunk = jobs[i : i + 200]
        states = [render(dialogues[di]["turns"][:k]) for di, k in chunk]
        res = batch(a.backend, [{"state": s, "questions": {"m": q}} for s in states], a.base)
        for (di, k), r in zip(chunk, res):
            if "error" in r:
                sys.exit(f"call failed: {r['error']}")
            probs[(di, k)] = r["answers"]["m"]["noul"]
        print(f"  {min(i + 200, len(jobs))}/{len(jobs)} ({time.time() - t0:.0f}s)", flush=True)

    dialogue_records = []
    for di, d in enumerate(dialogues):
        n = len(d["turns"])
        series = [probs[(di, k)] for k in range(1, n + 1)]
        manipulative = bool(d["manipulative"])
        rec = {"id": d["id"], "n_turns": n, "manipulative": manipulative, "series": series}
        if manipulative:
            onset_turn = None
            for k in range(n):
                if all(v >= 0.5 for v in series[k:]):
                    onset_turn = k + 1
                    break
            rec["onset_turn"] = onset_turn
            rec["onset_lag_share"] = (onset_turn / n) if onset_turn else None
            rec["never_committed"] = onset_turn is None
        else:
            crossings = sum(1 for k in range(1, n) if series[k] >= 0.5 > series[k - 1]) + (1 if series[0] >= 0.5 else 0)
            rec["false_alarm_crossings"] = crossings
            rec["false_alarms_per_10_turns"] = (crossings / n) * 10
        dialogue_records.append(rec)

    manip = [r for r in dialogue_records if r["manipulative"]]
    non = [r for r in dialogue_records if not r["manipulative"]]
    committed = [r for r in manip if not r["never_committed"]]
    summary = {
        "backend": a.backend, "n_dialogues": len(dialogues), "n_manipulative": len(manip), "n_non_manipulative": len(non),
        "mean_onset_lag_share": sum(r["onset_lag_share"] for r in committed) / len(committed) if committed else None,
        "share_never_committed": (len(manip) - len(committed)) / len(manip) if manip else None,
        "mean_false_alarms_per_10_turns": sum(r["false_alarms_per_10_turns"] for r in non) / len(non) if non else None,
        "share_with_any_false_alarm": sum(1 for r in non if r["false_alarm_crossings"] > 0) / len(non) if non else None,
    }
    Path(a.out).mkdir(parents=True, exist_ok=True)
    slug = a.backend.replace("/", "-")
    out_path = Path(a.out) / f"{slug}.json"
    out_path.write_text(json.dumps({**summary, "dialogues": dialogue_records}, indent=1))
    print(f"\nmean onset lag (share of dialogue, committed alarms only): {summary['mean_onset_lag_share']}")
    print(f"share of manipulative dialogues never committing to an alarm: {summary['share_never_committed']}")
    print(f"mean false alarms per 10 turns (non-manipulative dialogues): {summary['mean_false_alarms_per_10_turns']}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
