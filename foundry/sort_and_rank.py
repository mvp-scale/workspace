#!/usr/bin/env python3
"""Connects Sorter/Conveyor/Spotlight (funnel.py) to layered_walk.py's actual output -- the real
gap this session had left open: funnel.py only ever read problems/*.json, and layered_walk.py
never wrote to it. Takes the atomic requirements from a run's ledger, scores them live with
funnel.bounce_and_weigh (unmodified -- proven, not touched), then does the deterministic parts
that don't need a live call: Sorter.by-risk-tier grouping, Conveyor.risk-first ordering, and all
five Spotlight variants where the data to support them actually exists.

Two Spotlight variants and two Conveyor variants are reported as blocked, honestly, not faked:
downstream-impact and Conveyor.dependency-order/parallel-lanes need depends_on, which nothing in
this repo infers; audience-weighted needs a per-piece audience tag, which nothing currently sets
(by-domain classifies the whole idea, not each piece). Conveyor.duration-weighted/critical-path
need a real duration source that doesn't exist -- not attempted at all, per the standing rule
against inventing one.

    python3 foundry/layered_walk.py --idea oncall-rotation   # must run first
    python3 foundry/sort_and_rank.py --idea oncall-rotation
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "demo"))
import funnel  # noqa: E402

ALL_MODELS = ["semif", "kev-4b", "so1", "laya", "verdict", "jev"]  # same as layered_walk.py --
                                                                     # no code-level exclusion of
                                                                     # jev; funnel.bounce_and_weigh
                                                                     # already calls server.call the
                                                                     # same way for every backend.
MODELS = ["semif", "kev-4b", "so1"]  # same corrected default as layered_walk.py; overwritten by
                                       # --models in main()


def load_ledger(idea):
    path = HERE / "runs" / f"{idea}-layered-walk.jsonl"
    if not path.exists():
        sys.exit(f"no ledger at {path} -- run layered_walk.py --idea {idea} first")
    return [json.loads(l) for l in open(path) if l.strip()]


def atomic_pieces(records):
    return [{"id": "::".join(r["path"]), "text": r["full_text"], "depends_on": [], "category": r["path"][0]}
            for r in records if r["type"] == "grinder_node" and r["status"] == "atomic"]


def mean_risk(piece_id, results):
    per_model = results.get(piece_id, {})
    rs = [v["risk_0to1"] for v in per_model.values() if v.get("risk_0to1") is not None]
    return sum(rs) / len(rs) if rs else None


def by_risk_tier(pieces, results):
    """Sorter.by-risk-tier: three fixed bins by mean risk-if-false, per tools/sorter.yaml."""
    tiers = {"must-resolve-first": [], "worth-checking": [], "low-stakes": []}
    for p in pieces:
        risk = mean_risk(p["id"], results)
        if risk is None:
            continue
        tier = "must-resolve-first" if risk >= 0.6 else "worth-checking" if risk >= 0.3 else "low-stakes"
        tiers[tier].append((p, risk))
    for t in tiers:
        tiers[t].sort(key=lambda pr: -pr[1])
    return tiers


def parse_models(spec):
    """Same convention as layered_walk.py's --models: comma-separated P-numbers and/or raw
    backend ids, e.g. --models P0,P1 or --models jev,semif."""
    p_to_model = {p: m for m, p in funnel.MODEL_P.items()}
    result = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if token in p_to_model:
            result.append(p_to_model[token])
        elif token in ALL_MODELS:
            result.append(token)
        else:
            sys.exit(f"unknown model '{token}' -- use a P-number ({', '.join(sorted(p_to_model))}) or a backend id ({', '.join(ALL_MODELS)})")
    if not result:
        sys.exit(f"--models '{spec}' resolved to no models")
    return result


def main():
    global MODELS
    ap = argparse.ArgumentParser()
    ap.add_argument("--idea", required=True)
    ap.add_argument("--bouncer", default="reasonable", choices=list(funnel.BOUNCER_VARIANTS))
    ap.add_argument("--models", default=None,
                     help="comma-separated P-numbers or backend ids, jev included -- e.g. "
                          "--models P0,P1. Match what layered_walk.py used for this ledger if "
                          "you want an apples-to-apples run.")
    a = ap.parse_args()
    if a.models:
        MODELS = parse_models(a.models)

    records = load_ledger(a.idea)
    meta = next(r for r in records if r["type"] == "run_meta")
    pieces = atomic_pieces(records)
    if not pieces:
        print(f"No atomic requirements in this ledger yet -- nothing for Sorter to score. Run layered_walk.py --idea {a.idea} again, or build more gap_category_detail libraries.")
        return

    tools_used = {}  # tool.variant -> (ran: bool, note: str) -- printed as an honest accounting at the end

    print(f"TOOL: Sorter.scoring_primitive (bounce+weigh+resource fanned together, {len(pieces)} pieces x {len(MODELS)} models)")
    results = funnel.bounce_and_weigh(meta["idea"], pieces, MODELS, a.bouncer)
    tools_used["Sorter.scoring_primitive"] = (True, f"scored {len(pieces)} pieces, bouncer variant '{a.bouncer}'")

    print(f"\nSORTER -- scored, bouncer variant '{a.bouncer}'")
    rows = []
    for p in pieces:
        per_model = results.get(p["id"], {})
        ps = [v["p"] for v in per_model.values() if v.get("p") is not None]
        risks = [v["risk_0to1"] for v in per_model.values() if v.get("risk_0to1") is not None]
        effort = funnel.mean_effort(p["id"], results)
        if not ps or not risks:
            continue
        mean_p, mean_risk = sum(ps) / len(ps), sum(risks) / len(risks)
        rows.append({"piece": p, "supported_p": mean_p, "risk": mean_risk, "effort": effort or 0.0,
                     "disagreement": max(ps) - min(ps) if len(ps) > 1 else 0.0})
    rows.sort(key=lambda r: -r["risk"])

    # Persist Sorter's output -- previously printed to terminal scrollback and nothing else,
    # which meant no diagnostic or downstream analysis (e.g. a Monte Carlo sensitivity pass) could
    # ever be run against it after the fact. Same lesson as the ledger's per-model values.
    sort_path = HERE / "runs" / f"{a.idea}-sort.jsonl"
    with open(sort_path, "w") as f:
        f.write(json.dumps({"type": "sort_meta", "idea": a.idea, "models": MODELS, "bouncer": a.bouncer}) + "\n")
        for r in rows:
            per_model = results.get(r["piece"]["id"], {})
            f.write(json.dumps({
                "type": "sort_piece", "id": r["piece"]["id"], "text": r["piece"]["text"],
                "category": r["piece"]["category"], "supported_p": r["supported_p"],
                "risk": r["risk"], "effort": r["effort"], "disagreement": r["disagreement"],
                "per_model": {m: v for m, v in per_model.items()},
            }) + "\n")
    print(f"  (Sorter output persisted: {sort_path})")

    w = max((len(r["piece"]["text"]) for r in rows), default=10)
    w = min(w, 70)
    print(f"{'requirement':<{w}}  {'supported':>9}  {'risk':>6}  {'effort':>6}  {'disagree':>8}")
    for r in rows:
        t = r["piece"]["text"]
        t = t if len(t) <= w else t[:w - 3] + "..."
        print(f"{t:<{w}}  {r['supported_p']:>9.2f}  {r['risk']:>6.2f}  {r['effort']:>6.2f}  {r['disagreement']:>8.2f}")

    print("\nTOOL: Sorter.by-risk-tier (grouping, deterministic, no live call)")
    tiers = by_risk_tier(pieces, results)
    for tier, items in tiers.items():
        print(f"  {tier}: {len(items)}")
        for p, risk in items:
            print(f"    - [{risk:.2f}] {p['text'][:80]}")
    tools_used["Sorter.by-risk-tier"] = (True, f"{sum(len(v) for v in tiers.values())} pieces grouped into 3 tiers")
    tools_used["Sorter.by-domain / by-audience / by-layer / by-phase"] = (False, "not run -- need per-piece domain/audience/layer/phase tags that nothing currently sets (by-domain classifies the whole idea, not each requirement)")

    print("\nTOOL: Conveyor.risk-first (sequence groups, highest risk first -- ignores dependency, none exists)")
    for tier in ["must-resolve-first", "worth-checking", "low-stakes"]:
        if tiers[tier]:
            print(f"  {tier} ({len(tiers[tier])})")
    tools_used["Conveyor.risk-first"] = (True, "sequenced by Sorter's risk tiers")
    tools_used["Conveyor.dependency-order / parallel-lanes"] = (False, "BLOCKED -- depends_on is empty for every piece, no inference built")
    tools_used["Conveyor.duration-weighted / critical-path"] = (False, "NOT ATTEMPTED -- no real duration source exists; not faking one")

    print("\nTOOL: Spotlight (risk-plus-disagreement, disagreement-only, risk-only -- three of five variants)")
    def show(label, key_fn):
        ranked = sorted(rows, key=key_fn, reverse=True)
        print(f"  {label}: " + ", ".join(r["piece"]["text"][:40] for r in ranked[:3]) + (" ..." if len(ranked) > 3 else ""))
    show("risk-plus-disagreement (default)", lambda r: r["risk"] + r["disagreement"])
    show("disagreement-only", lambda r: r["disagreement"])
    show("risk-only", lambda r: r["risk"])
    tools_used["Spotlight.risk-plus-disagreement / disagreement-only / risk-only"] = (True, f"ranked {len(rows)} pieces, 3 sort keys")
    tools_used["Spotlight.downstream-impact"] = (False, "BLOCKED -- needs depends_on, none exists")
    tools_used["Spotlight.audience-weighted"] = (False, "BLOCKED -- needs a per-piece audience tag; by-domain classifies the whole idea, not each piece")

    print("\nTOOLS USED THIS RUN")
    for tool, (ran, note) in tools_used.items():
        print(f"  {'✓' if ran else '✗'} {tool}: {note}")
    print("  (Slicer and Grinder ran in layered_walk.py, the previous command -- not repeated here.)")


if __name__ == "__main__":
    main()
