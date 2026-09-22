#!/usr/bin/env python3
"""The Foundry -- command-line prototype of the factory-line idea-decomposition pipeline. Its own
folder, separate from demo/ and probes/, on purpose: this is not wired into the Scenario lab and
shouldn't be until the toolkit itself is proven out. See README.md for the tool vocabulary.

Pipeline, capped at five tools per README.md's "five tools, five variants" rule (tools/*.yaml has
the full spec; this is the code-level summary):

    Slicer    -- idea (<=500 chars) -> first-pass pieces, with depends_on edges and a business/
                 technical lens. STUBBED as hand-authored JSON in problems/*.json: no
                 ANTHROPIC_API_KEY exists yet, so there is no live per-request LLM call.
    Grinder   -- NOT BUILT YET. Would recursively re-slice a piece that's still too coarse. Also
                 where the old standalone Bouncer tool ended up (tools/grinder.yaml) -- its live
                 yes/no mechanism is Grinder's own atomic-threshold stopping check now.
    Sorter    -- Weigher and Welder merged (tools/sorter.yaml): scores each piece live (one noul +
                 one score question per piece per model, one real POST) and groups pieces by
                 shared need. Grouping itself is NOT built -- code below still works on a flat
                 piece list.
    Conveyor  -- deterministic sequencing of pieces by depends_on. Used here as the actual reading
                 order of the human-facing output, not just a backstage detail.
    Spotlight -- deterministic ranking: risk-plus-disagreement, reduced in the human-facing output
                 to "what to look at first," with no numbers attached.

Local, free, loaded models only. The hosted model (jev) is not an option here at all -- not just a
convention this script follows (like lab_decompose.py's), the environment's own permission
classifier blocks hosted spend from scripts outright.

OUTPUT PHILOSOPHY (per direct user correction -- read this before changing the rendering code):
the decomposition is the front-facing value, told as a story anyone can read without explanation --
no model names, no percentages, no legend leading the output. Per piece, the only thing that
surfaces is a plain verdict: did it clear a confidence bar, did the models agree. Models are never
named in the story -- only P0 (the hosted reference, never called) through P5 (the five local
models, in a fixed leaderboard-based order that never changes). All the numbers, the model
identities, and the raw per-model table still exist -- in a separate "technical detail" section
that comes AFTER the story, for verification, not as the lead.

    python3 foundry/funnel.py --list                       # numbered menu of problems/*.json
    python3 foundry/funnel.py                               # run every problem
    python3 foundry/funnel.py --problem 2                    # run by number (per --list)
    python3 foundry/funnel.py --problem standup-async         # or by id
    python3 foundry/funnel.py --models kev-4b semif
    python3 foundry/funnel.py --bouncer-variant strict        # the old, harder-to-satisfy phrasing
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
sys.path.insert(0, str(ROOT / "demo"))
import server  # noqa: E402

LEVELS5 = ["very low", "low", "medium", "high", "very high"]

# id -> (code, display name, published leaderboard accuracy %, hosted). Source: BRIDGE.md
# "Findings worth remembering" -- mean accuracy across probes/v2's 15 published sets (~1,400
# items). An external, already-measured ranking, not invented for Foundry.
MODEL_META = {
    "jev": ("JEV113", "Jev 1.13.0", 76.5, True),
    "semif": ("SEMIF4", "SemIf", 67.5, False),
    "kev-4b": ("KEV4B", "kev 4B", 66.8, False),
    "so1": ("OAJEV4", "open-alt-jev", 64.8, False),
    "laya": ("LAYA4H", "Laya", 58.4, False),
    "verdict": ("VERD2H", "Verdict", 46.7, False),
}
# Fixed P-number per model, by leaderboard rank -- P0 is always the hosted reference, P1 is
# always the best-performing local model, and so on. This mapping never changes between runs,
# even if a run only calls a subset of models (per user instruction: "we always have that same
# exact mapping").
MODEL_RANK = sorted(MODEL_META, key=lambda m: -MODEL_META[m][2])
MODEL_P = {m: f"P{i}" for i, m in enumerate(MODEL_RANK)}
ALL_LOCAL_MODELS = [m for m in MODEL_RANK if not MODEL_META[m][3]]

# Judgment calls, not measured constants -- how confident is "confident enough to build on," and
# how much spread between models counts as real disagreement rather than noise.
CONFIDENCE_THRESHOLD = 0.6
DISAGREEMENT_THRESHOLD = 0.3


def all_problem_files():
    return sorted((HERE / "problems").glob("*.json"))


def load_problems(selector=None):
    files = all_problem_files()
    if selector:
        if selector.isdigit():
            i = int(selector)
            if not (1 <= i <= len(files)):
                sys.exit(f"--problem {i} out of range -- run --list, there are {len(files)} problems")
            files = [files[i - 1]]
        else:
            files = [f for f in files if f.stem == selector]
            if not files:
                sys.exit(f"no problems/{selector}.json -- available: {[f.stem for f in all_problem_files()]}")
    problems = [json.loads(f.read_text()) for f in files]
    for p in problems:
        if len(p["idea"]) > 500:
            sys.exit(f"{p['id']}: idea is {len(p['idea'])} chars, over the 500-char cap")
    return problems


def print_list():
    for i, f in enumerate(all_problem_files(), 1):
        idea = json.loads(f.read_text())["idea"]
        print(f"  {i}. {f.stem:<24} {idea[:80]}{'...' if len(idea) > 80 else ''}")


# Two phrasings of the same yes/no question. "reasonable" is the default -- almost every piece
# Slicer produces is a prediction about future behavior, not a verifiable present fact, and
# "strict" asks for something no forward-looking claim can honestly satisfy ("true today, without
# further verification"). Comparing the two on shift-swap-marketplace showed strict was punishing
# precise models rather than measuring anything real -- see README.md's "Bouncer phrasing check."
# strict is kept as an explicit diagnostic mode, not the default.
BOUNCER_VARIANTS = {
    "reasonable": {
        "question": "is this a reasonable assumption to build the idea on, even if it hasn't been directly verified?",
        "true": "A reasonable assumption to build on, given what's described.",
        "false": "Not a reasonable assumption -- too big a leap, or contradicted by what's described.",
    },
    "strict": {
        "question": "is this claim well-supported enough to treat as true today, without further verification?",
        "true": "Well-supported enough to treat as true today.",
        "false": "Not yet supported -- still an assumption or unknown.",
    },
}


def bounce_question(idea, piece, variant):
    v = BOUNCER_VARIANTS[variant]
    return {"type": "noul",
            "instructions": f"Idea under evaluation: {idea}\n\nClaim: {piece['text']}\n\nQuestion: as the idea is described, {v['question']}",
            "criteria": {"true": v["true"], "false": v["false"]}}


def weigh_question(piece):
    return {"type": "score",
            "instructions": f"Claim: {piece['text']}\n\nQuestion: if this claim turns out false, how much does it damage the overall idea's viability?",
            "criteria": [f"{l} damage to viability if false" for l in LEVELS5]}


def bounce_and_weigh(idea, pieces, models, bouncer_variant):
    """Sorter's scoring half: one battery (both questions) per piece per model, one real POST
    each. Returns {piece_id: {model: {p, risk_0to1}}}. Silent -- no progress printing here, the
    caller decides what's worth showing."""
    results = {p["id"]: {} for p in pieces}
    for model in models:
        cfg = server.BACKENDS[model]
        if cfg.get("hosted"):
            continue
        for piece in pieces:
            q = {"bounce": bounce_question(idea, piece, bouncer_variant), "weigh": weigh_question(piece)}
            r = server.call(model, cfg, {"state": idea, "model": "jev-latest", "questions": q}, whole=True)
            if "error" in r:
                results[piece["id"]][model] = {"p": None, "risk_0to1": None, "error": r["error"]}
                continue
            answers = r.get("answers") or {}
            p = (answers.get("bounce") or {}).get("noul")
            score = (answers.get("weigh") or {}).get("score")
            risk = score / (len(LEVELS5) - 1) if score is not None else None
            results[piece["id"]][model] = {"p": p, "risk_0to1": risk}
    return results


def piece_verdict(piece_id, results):
    """Reduces a piece's per-model numbers to one plain-language read: did it clear the
    confidence bar, and did the models agree. This is the only thing the human-facing story ever
    shows per piece -- no decimals."""
    per_model = results.get(piece_id, {})
    ps = [v["p"] for v in per_model.values() if v.get("p") is not None]
    if not ps:
        return "no answer", 0.0, 0.0
    mean_p = sum(ps) / len(ps)
    disagreement = max(ps) - min(ps) if len(ps) > 1 else 0.0
    if mean_p >= CONFIDENCE_THRESHOLD and disagreement < DISAGREEMENT_THRESHOLD:
        return "Confident & aligned", mean_p, disagreement
    if mean_p >= CONFIDENCE_THRESHOLD:
        return "Confident, but the models disagree", mean_p, disagreement
    return "Not confident yet", mean_p, disagreement


def conveyor(pieces):
    """Deterministic topological order by depends_on. No model call. Doubles as the reading order
    of the human-facing story, not just a backstage detail."""
    by_id = {p["id"]: p for p in pieces}
    ordered, seen = [], set()
    def visit(pid):
        if pid in seen:
            return
        seen.add(pid)
        for dep in by_id[pid]["depends_on"]:
            visit(dep)
        ordered.append(pid)
    for p in pieces:
        visit(p["id"])
    return ordered


def spotlight(pieces, results):
    """Rank pieces by (mean risk-if-false) + (cross-model disagreement). No forecast, no
    invented aggregate -- used only to pick "what to look at first" for the story; the raw
    numbers behind it live in the technical detail section, not the story itself."""
    rows = []
    for piece in pieces:
        per_model = results.get(piece["id"], {})
        ps = [v["p"] for v in per_model.values() if v.get("p") is not None]
        risks = [v["risk_0to1"] for v in per_model.values() if v.get("risk_0to1") is not None]
        if not ps or not risks:
            continue
        mean_risk = sum(risks) / len(risks)
        disagreement = max(ps) - min(ps) if len(ps) > 1 else 0.0
        rows.append({"id": piece["id"], "text": piece["text"], "mean_risk": mean_risk,
                      "disagreement": disagreement, "n_models": len(per_model)})
    rows.sort(key=lambda r: r["mean_risk"] + r["disagreement"], reverse=True)
    return rows


def render_table(pieces, results, models):
    """Technical-detail-only: one row per piece, one column per model, real numbers. Never shown
    in the human-facing story."""
    col_w = 16
    header = "piece".ljust(22) + "".join(f"{MODEL_META[m][0]:>{col_w}}" for m in models)
    lines = [header, "-" * len(header)]
    for piece in pieces:
        row = piece["id"].ljust(22)
        for m in models:
            v = results.get(piece["id"], {}).get(m, {})
            p, r = v.get("p"), v.get("risk_0to1")
            cell = f"{p:.2f}/{r:.2f}" if p is not None and r is not None else "err"
            row += f"{cell:>{col_w}}"
        lines.append(row)
    return "\n".join(lines)


def run_problem(problem, models, bouncer_variant="reasonable"):
    idea, pieces = problem["idea"], problem["pieces"]
    by_id = {p["id"]: p for p in pieces}
    results = bounce_and_weigh(idea, pieces, models, bouncer_variant)
    order = conveyor(pieces)
    ranked = spotlight(pieces, results)
    verdicts = {pid: piece_verdict(pid, results) for pid in by_id}

    story = []
    def s(line=""):
        print(line)
        story.append(line)

    s(f"\n{'=' * 70}\nTHE IDEA\n{'=' * 70}")
    s(f'"{idea}"')
    s()
    s("HOW IT BREAKS DOWN")
    s("-" * 70)
    for lens_name, heading in (("business", "Business"), ("technical", "Technical")):
        pids = [pid for pid in order if by_id[pid].get("lens") == lens_name]
        if not pids:
            continue
        s(f"\n{heading}:")
        for i, pid in enumerate(pids, 1):
            label, _, _ = verdicts[pid]
            s(f"  {i}. {by_id[pid]['text']}")
            s(f"     -> {label}")
    untagged = [pid for pid in order if by_id[pid].get("lens") not in ("business", "technical")]
    if untagged:
        s("\nUntagged:")
        for i, pid in enumerate(untagged, 1):
            label, _, _ = verdicts[pid]
            s(f"  {i}. {by_id[pid]['text']}")
            s(f"     -> {label}")

    s("\nWHAT NEEDS ANSWERING FIRST")
    s("-" * 70)
    for r in ranked[:3]:
        label, _, _ = verdicts[r["id"]]
        why = "the models don't agree with each other on this" if "disagree" in label \
            else "the models don't think this can be assumed yet" if label == "Not confident yet" \
            else "confirming this first unblocks the most of what depends on it"
        s(f"  - {r['text']}\n    ({why})")

    print("\n" + "=" * 70)
    print("TECHNICAL DETAIL (for verification -- not required reading)")
    print("=" * 70)
    print("Models checked, fixed order (P-number always means the same model, across every run):")
    for m in MODEL_RANK:
        code, name, pct, hosted = MODEL_META[m]
        note = "reference only, never called from this script" if hosted \
            else "checked this run" if m in models else "not checked this run"
        print(f"  {MODEL_P[m]}  {code:<8}{name:<16}{note}")
    print(f"\nBouncer phrasing: {bouncer_variant} -- {BOUNCER_VARIANTS[bouncer_variant]['question']}")
    print(f"Confidence bar: mean supported-p >= {CONFIDENCE_THRESHOLD}. Disagreement bar: model spread >= {DISAGREEMENT_THRESHOLD}.\n")
    print("Raw supported-p / risk-if-false, by model:")
    print(render_table(pieces, results, models))
    print(f"\nDependency order: {' -> '.join(order)}")
    print("\nSpotlight (raw): risk + disagreement, descending:")
    for r in ranked:
        print(f"  {r['id']:<22} risk={r['mean_risk']:.2f}  disagreement={r['disagreement']:.2f}  ({r['n_models']} models)")

    pipeline = {"id": problem["id"], "idea": idea, "models": models, "bouncer_variant": bouncer_variant,
                "slicer": {"source": problem.get("source"), "pieces": pieces},
                "sorter": results, "verdicts": {pid: v[0] for pid, v in verdicts.items()},
                "conveyor": order, "spotlight": ranked}
    write_run(problem["id"], bouncer_variant, pipeline, "\n".join(story))
    return pipeline


def write_run(problem_id, bouncer_variant, pipeline, story_text):
    """Own folder per run, never clobbered: <problem_id>__<bouncer_variant>__<timestamp>/
    pipeline.json (full detail) + story.md (the human-facing story only, no technical detail)."""
    run_dir = RUNS / f"{problem_id}__{bouncer_variant}__{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "pipeline.json").write_text(json.dumps(pipeline, indent=1))
    (run_dir / "story.md").write_text(f"```\n{story_text}\n```\n")
    print(f"\n  -> wrote {run_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="numbered menu of problems/*.json, then exit")
    ap.add_argument("--problem", help="a number from --list, a problem id, or omit for every problem")
    ap.add_argument("--models", nargs="+", default=ALL_LOCAL_MODELS, choices=ALL_LOCAL_MODELS)
    ap.add_argument("--bouncer-variant", default="reasonable", choices=list(BOUNCER_VARIANTS),
                     help="reasonable (default) = 'a reasonable assumption to build on'; "
                          "strict = 'true today, without further verification' -- kept as an "
                          "explicit diagnostic, see README.md's 'Bouncer phrasing check'")
    a = ap.parse_args()
    if a.list:
        print_list()
        return
    problems = load_problems(a.problem)
    for problem in problems:
        run_problem(problem, a.models, a.bouncer_variant)


if __name__ == "__main__":
    main()
