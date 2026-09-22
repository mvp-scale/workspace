#!/usr/bin/env python3
"""Reference tree for the decompose-and-loop worked example: docs/scenario-lab-plan.md, broken into
atomic work items by hand (I know this project's real status), 3-4 layers deep. Not a published
dataset -- our own private set (plan item 5), used to grade whether Jev-class models can judge a
decomposition the way the user's diagram describes: atomic?, does it cover its parent?, risk,
complexity, can it run in parallel?, what kind of dependency blocks it?

Two nodes have a genuine, documented coverage gap (not a contrived error): their children are the
plan's own item list, but the plan's own text says the requirement isn't actually met yet. Every
other reference label is my honest current call, checked against BRIDGE.md and git history, not
invented difficulty.

Writes probes/decompose/tree_ref.json. Re-run whenever the reference facts change.
"""
import json
from pathlib import Path

DEP = ["none", "needs-user-decision", "needs-other-item", "needs-external-check"]
OUT = Path(__file__).parent / "tree_ref.json"

# id, parent, title, text (context for the model), atomic, covers(group only), risk, complexity,
# parallel, dependency, status, why (not shown to the model; shown in the UI for transparency)
NODES = [
    dict(id="root", parent=None, kind="root", title="Scenario lab build-out",
         text="Build out the Scenario lab (demo/scenarios.html) so every loaded model can be run on every set and every test structure, offline with the full GPU and live through the demo server."),

    dict(id="g-layout", parent="root", kind="group", title="Layout",
         text="The overview page (models x sets heat map) needs its orientation, family labelling and colour scale settled."),
    dict(id="layout-1", parent="g-layout", kind="leaf", title="Flip overview orientation",
         text="Change the overview heat map from its current layout to models across the top (nine short codes) and sets down as rows, grouped under family headings, expandable in place to show per-model accuracy, calibration, confusion split and disagreement.",
         atomic=True, risk=0.6, complexity=0.35, parallel=True, dependency="needs-user-decision", status="blocked",
         why="Explicitly listed under 'Decisions needed' in the plan; current table still has sets as columns, models as rows, the opposite of what item 1 asks for."),
    dict(id="layout-2", parent="g-layout", kind="leaf", title="Family header strip",
         text="Above the overview heat map's column headers there is a thin coloured strip meant to label which columns belong to which family. Its labels are currently empty because they got truncated. Decide: give them real (short) labels, or remove the strip.",
         atomic=True, risk=0.25, complexity=0.15, parallel=True, dependency="needs-user-decision", status="not_started",
         why="Still literally empty in the running page; listed as an open decision in both the plan and BRIDGE.md."),
    dict(id="layout-3", parent="g-layout", kind="leaf", title="Chance-relative colour",
         text="The overview heat map's cell colour is computed relative to each set's chance rate, so a low-chance set (e.g. 13% for a 7-way choice) looks greener at the same raw accuracy as a high-chance set. Decide whether to keep showing it this way, or normalise it out.",
         atomic=True, risk=0.1, complexity=0.1, parallel=True, dependency="none", status="done",
         why="stepBg/heatBg in scenarios.html already compute colour relative to chance; this is live on every page load, not just proposed."),

    dict(id="g-sets", parent="root", kind="group", title="More sets",
         text="Add more published, labelled probe sets through the existing seeded-builder pipeline, and let the user add their own private sets."),
    dict(id="sets-4", parent="g-sets", kind="group", title="New published sets",
         text="Each new set is a seeded probes/v2/build_*.py from a published dataset, producing a .jsonl and a .md recording source, licence and label caveats. Candidate datasets, each its own unit of work:"),
    dict(id="sets-4-pii", parent="sets-4", kind="leaf", title="Gretel PII", text="Build a probe set from the Gretel synthetic PII dataset: does a message contain personally identifying information.",
         atomic=True, risk=0.5, complexity=0.35, parallel=True, dependency="needs-external-check", status="not_started",
         why="Not started; outbound access to the dataset host has never been verified from this box, per the plan's own caveat."),
    dict(id="sets-4-abcd", parent="sets-4", kind="leaf", title="ABCD support escalation", text="Build a probe set from the Action-Based Conversations Dataset: should this support conversation escalate to a human.",
         atomic=True, risk=0.5, complexity=0.4, parallel=True, dependency="needs-external-check", status="not_started", why="Not started; same unverified-access caveat as the other candidates."),
    dict(id="sets-4-prosocial", parent="sets-4", kind="leaf", title="ProsocialDialog", text="Build a probe set from ProsocialDialog: does a reply de-escalate or challenge a problematic statement safely.",
         atomic=True, risk=0.5, complexity=0.35, parallel=True, dependency="needs-external-check", status="not_started", why="Not started; same caveat."),
    dict(id="sets-4-toxicity", parent="sets-4", kind="leaf", title="Toxicity", text="Build a probe set for general toxicity detection from a published toxicity corpus, distinct from the civil-comments threat set already built.",
         atomic=True, risk=0.4, complexity=0.3, parallel=True, dependency="needs-external-check", status="not_started", why="Not started; not yet scoped beyond being named a candidate in the plan."),
    dict(id="sets-4-negotiation", parent="sets-4", kind="leaf", title="Negotiation", text="Build a probe set for negotiation tactics or outcomes from a published negotiation-dialogue dataset.",
         atomic=True, risk=0.55, complexity=0.45, parallel=True, dependency="needs-external-check", status="not_started",
         why="Not started; least scoped of the candidates, no specific source dataset picked yet in the plan."),
    dict(id="sets-5", parent="g-sets", kind="leaf", title="Private sets from the user's own data",
         text="Let the user add a small (a few dozen items) private labelled set from their own work, through the same pipeline as the published sets.",
         atomic=True, risk=0.4, complexity=0.2, parallel=True, dependency="needs-user-decision", status="not_started",
         why="Not started; explicitly needs the user to supply labelled examples before it can be built."),

    dict(id="g-structures", parent="root", kind="group", title="Structures",
         text="Add test structures beyond a single decision: batch performance, cascade, funnel, decompose-and-loop, incremental state, hierarchy, time, and a baseline for every claim."),
    dict(id="struct-6", parent="g-structures", kind="leaf", title="Batch performance",
         text="One state, a battery of 5 to 160 questions in one request; record latency, accuracy and where the context limit or question cap bites; local models first, hosted only after approval.",
         atomic=True, risk=0.1, complexity=0.35, parallel=True, dependency="none", status="done",
         why="Built and run on all 5 loaded models (probes/lab_batch.py, /api/batch-perf); results are in the lab now."),
    dict(id="struct-7", parent="g-structures", kind="leaf", title="Cascade (routing)",
         text="Route to a cheap model first and escalate to a stronger model only when the cheap model's confidence is low; measure accuracy against the share of items escalated.",
         atomic=True, risk=0.3, complexity=0.3, parallel=True, dependency="none", status="not_started",
         why="A first attempt was started and then deliberately reverted mid-build this session; nothing shipped."),
    dict(id="struct-8", parent="g-structures", kind="leaf", title="Funnel (Monte Carlo forecast)",
         text="Roll atomic typed answers up into a Monte Carlo forecast with an interval and a sensitivity ranking of which atoms drive it; needs labelled outcomes and a way to handle correlation between atoms.",
         atomic=True, risk=0.55, complexity=0.55, parallel=False, dependency="needs-other-item", status="in_progress",
         why="This tree's own risk forecast is the first real use of this structure, built today; depends on having genuine labelled outcomes, which is exactly what this tree's status field provides."),
    dict(id="struct-9", parent="g-structures", kind="leaf", title="Decompose and loop",
         text="Ask about the whole, split into pieces, recurse into the pieces that score high, and keep the whole score next to the pieces; for a complex problem this means a planner proposing work items and a judge scoring each one.",
         atomic=True, risk=0.5, complexity=0.6, parallel=False, dependency="none", status="in_progress",
         why="This tree is that structure, being built and scored today, after an earlier wrong version (turn-window splitting on dialogue text) was built and then reverted."),
    dict(id="struct-10", parent="g-structures", kind="leaf", title="Incremental state",
         text="Compare reading only the new words since the last check against re-reading the whole trailing window every time.",
         atomic=True, risk=0.35, complexity=0.4, parallel=True, dependency="none", status="not_started", why="Not started; not yet scoped beyond the one-line plan item."),
    dict(id="struct-11", parent="g-structures", kind="leaf", title="Hierarchy (gated questions)",
         text="Ask cheap gate questions first, and only ask the finer, more expensive questions when the gate opens.",
         atomic=True, risk=0.3, complexity=0.35, parallel=True, dependency="none", status="not_started", why="Not started."),
    dict(id="struct-12", parent="g-structures", kind="leaf", title="Time (onset, lag, false alarms)",
         text="Measure onset, escalation, detection lag and false alarms per minute over a time-ordered signal.",
         atomic=True, risk=0.5, complexity=0.55, parallel=True, dependency="needs-external-check", status="not_started",
         why="Not started; needs a time-series labelled source we don't have yet, unlike the other structures which reuse existing sets."),
    dict(id="struct-13", parent="g-structures", kind="leaf", title="Baseline for every claim",
         text="Every structure's claim needs a baseline (a generative LLM or a single-question classifier) run on the same items with intervals, so a structure that shows no gain is visible as such.",
         atomic=True, risk=0.6, complexity=0.35, parallel=False, dependency="needs-other-item", status="not_started",
         why="Not started for any structure shipped so far, including batch performance; each structure needs to be retrofitted with one."),

    dict(id="g-blind", parent="root", kind="group", title="Blind grading",
         text="A repeatable blind run: fixed seed, stratified draws, a sealed key, 60 to 100 items per set, grades revealed only after the run, triggered by a Run button in the lab."),
    dict(id="blind-14", parent="g-blind", kind="leaf", title="Repeatable blind run",
         text="Build the sealed-key blind-run mechanism and its Run button in the lab: fixed seed, stratified draws, 60 to 100 items per set, grades revealed only afterwards.",
         atomic=True, risk=0.45, complexity=0.55, parallel=True, dependency="none", status="not_started",
         why="Not started as a real feature; only a 12-item ad hoc trial exists, explicitly noted in the plan as too small to conclude anything."),

    dict(id="g-lineup", parent="root", kind="group", title="Lineup and benchmark",
         text="Keep the benchmark numbers trustworthy as the upstream projects and the loaded model lineup move: sync jevbench's scoring changes, update SemIf/OpenJev, decide on new candidate models, and report which model actually answered."),
    dict(id="lineup-15", parent="g-lineup", kind="leaf", title="Sync jevbench",
         text="Upstream jevbench is at least 8 commits ahead, up to v1.3.0, which changes scoring; decide whether stored results need to be re-scored before syncing.",
         atomic=True, risk=0.65, complexity=0.5, parallel=False, dependency="needs-user-decision", status="blocked",
         why="Explicitly 'decide before re-scoring' in the plan; a scoring change could silently invalidate every stored benchmark number, so this blocks other lineup work."),
    dict(id="lineup-16", parent="g-lineup", kind="leaf", title="Update SemIf/OpenJev",
         text="Upstream SemIf/OpenJev added a CPU backend, EXL3 quantisation and temperature calibration; pull these in.",
         atomic=True, risk=0.4, complexity=0.4, parallel=True, dependency="needs-other-item", status="not_started",
         why="Not started; depends on the jevbench sync decision above since scoring changes would affect it too."),
    dict(id="lineup-17", parent="g-lineup", kind="group", title="Candidate new models",
         text="Upstream has new candidate systems since this lineup was chosen. The GPU is nearly full (about 30 of 31.8 GiB with 5 models loaded), so adding any of these is a lineup decision, not just a download:"),
    dict(id="lineup-17-winnow", parent="lineup-17", kind="leaf", title="Winnow-12B Q8", text="Evaluate adding Winnow-12B (Q8 quantised) to the loaded lineup.",
         atomic=True, risk=0.55, complexity=0.3, parallel=True, dependency="needs-user-decision", status="not_started", why="Not started; GPU budget decision needed, same as the other candidates."),
    dict(id="lineup-17-reflex", parent="lineup-17", kind="leaf", title="reflex 4B", text="Evaluate adding reflex 4B to the loaded lineup.",
         atomic=True, risk=0.5, complexity=0.3, parallel=True, dependency="needs-user-decision", status="not_started", why="Not started; same GPU budget decision."),
    dict(id="lineup-17-openjev", parent="lineup-17", kind="leaf", title="Open-Jev 2B/9B", text="Evaluate adding the new Open-Jev 2B and 9B sizes, which sit alongside the SemIf/OpenJev already loaded as OAJEV4.",
         atomic=True, risk=0.5, complexity=0.3, parallel=True, dependency="needs-user-decision", status="not_started", why="Not started; same GPU budget decision, plus overlaps with the existing OAJEV4."),
    dict(id="lineup-17-djev", parent="lineup-17", kind="leaf", title="djev", text="Evaluate adding djev to the loaded lineup.",
         atomic=True, risk=0.55, complexity=0.3, parallel=True, dependency="needs-user-decision", status="not_started", why="Not started; least documented of the candidates, so also carries scoping risk."),
    dict(id="lineup-18", parent="g-lineup", kind="leaf", title="Report which model actually answered",
         text="Show, for every answer, which model process actually generated it, in case a server is misconfigured or mislabelled.",
         atomic=True, risk=0.15, complexity=0.15, parallel=True, dependency="none", status="done",
         why="/api/status already asks each running server its identity and flags a mismatch (identity_ok); the rail's live-dot tooltips and model tags read from it."),
]

# Coverage for the group/root nodes: honest, and two (structures, lineup) are genuinely incomplete
# per the plan's own text, not invented for difficulty.
COVERS = {
    "root": (None, "Root node; no single 'covers' judgement applies to the whole plan."),
    "g-layout": (True, "All three layout items are accounted for by layout-1/2/3; nothing in the plan's Layout section is left out."),
    "g-sets": (True, "Both the published-set pipeline (item 4, with its five candidates) and private sets (item 5) are covered."),
    "g-structures": (False, "struct-13 (a baseline for every claim) is listed as a child, but the plan's own text says every claim needs one and none of the shipped structures (batch performance, this tree) has one yet -- the requirement 'every structure ships with a baseline' is not actually met by its children as executed so far."),
    "g-blind": (True, "The single blind-run item is the whole of this section."),
    "g-lineup": (False, "lineup-15 (sync jevbench) is explicitly undecided ('decide before re-scoring'), so the group's own goal -- keep the leaderboard trustworthy while the lineup and upstream scoring evolve -- is not yet met by its children; lineup-16 depends on that same open decision."),
    "sets-4": (True, "The five candidate datasets are exactly the plan's own candidate list; nothing added or left out."),
    "lineup-17": (True, "The four candidate models are exactly the plan's own candidate list."),
}


def main():
    by_id = {n["id"]: n for n in NODES}
    children = {}
    for n in NODES:
        children.setdefault(n["parent"], []).append(n["id"])
    layer = {}
    def depth(nid):
        if nid not in layer:
            n = by_id[nid]
            layer[nid] = 0 if n["parent"] is None else depth(n["parent"]) + 1
        return layer[nid]
    out = []
    for n in NODES:
        n = dict(n)
        n["layer"] = depth(n["id"])
        n["children"] = children.get(n["id"], [])
        if n["kind"] in ("root", "group"):
            covers, why = COVERS[n["id"]]
            n["covers_ref"] = covers
            n["covers_why"] = why
            kids = ", ".join(by_id[c]["title"] for c in n["children"])
            n["text"] = n["text"] + (f"\nListed child items: {kids}." if kids else "")
            n["atomic_ref"] = False if n["kind"] == "group" else None  # a group is compound by construction; no single call for the root
            for k in ("risk_ref", "complexity_ref", "parallel_ref", "dependency_ref", "status", "why"):
                n.setdefault(k, None)
        else:
            n["covers_ref"] = None
            n["covers_why"] = None
            n["atomic_ref"] = n.pop("atomic")
            n["risk_ref"] = n.pop("risk")
            n["complexity_ref"] = n.pop("complexity")
            n["parallel_ref"] = n.pop("parallel")
            n["dependency_ref"] = n.pop("dependency")
        out.append(n)
    assert all(n["dependency_ref"] in DEP or n["dependency_ref"] is None for n in out)
    OUT.write_text(json.dumps({"dep_options": DEP, "nodes": out}, indent=1))
    print(f"{len(out)} nodes -> {OUT}")


if __name__ == "__main__":
    main()
