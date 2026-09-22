#!/usr/bin/env python3
"""Reference tree for the decompose-and-loop demo, take two: not this project's own plan (too
meta to tell a story with), but a real pitch -- exploit high-bandwidth RAM across many Cloudflare
Edge Workers to explode a dataset too large for one machine into memory, run SIMD/MIMD-style
anomaly detection and incremental training across workers, and persist only the deltas. Target:
live in 30 days.

Same mechanism as build_tree.py (planner splits by hand, 'atomic' asked live at every node,
covers/risk/budget/complexity/parallel/dependency on the rest), different ground truth: this is a
brand-new idea, not a project with real history, so 'status' is not done/blocked -- it is whether
each question is already answerable from documentation (known), needs a live experiment
(needs_spike), needs a choice only the user can make (needs_decision), or isn't needed for a
30-day MVP (deferred). 'critical_path' marks the handful of items that gate everything else --
that is the real answer to "what do we need immediately."

My own honest technical read, not invented difficulty: Cloudflare Workers isolates are
memory-capped per invocation and do not expose shared or pooled physical memory between isolates
-- cross-worker communication goes over the network (Durable Objects / Queues / KV / R2), not at
local RAM bandwidth. WASM SIMD inside one isolate is real and shipped. That gap -- "high-bandwidth
memory... across edge workers" read as a literal shared memory pool -- is the single highest-
stakes assumption in the pitch, and it is marked needs_spike + critical_path here, not asserted
as fact, because platform specifics change and deserve a live check before 30 days get bet on it.

Writes probes/decompose/tree_ref_edge.json.
"""
import json
from pathlib import Path

DEP = ["none", "needs-user-decision", "needs-other-item", "needs-external-check"]
OUT = Path(__file__).parent / "tree_ref_edge.json"
PITCH = ("Exploit high-bandwidth RAM across many Cloudflare Edge Workers: explode a dataset too large for one "
         "machine into per-worker memory, run SIMD/MIMD-style anomaly detection and incremental training across "
         "workers, and persist only the deltas -- so a model can be trained on data that would not fit in one "
         "machine's memory. Target: live in 30 days.")

NODES = [
    dict(id="root", parent=None, kind="root", title="Edge-RAM anomaly training pipeline", text=PITCH),

    dict(id="sys-feas", parent="root", kind="group", title="Platform feasibility spike",
         text="Before building anything else: confirm whether Cloudflare Workers actually provide the memory-bandwidth and cross-worker memory-sharing primitives this architecture assumes."),
    dict(id="feas-mem", parent="sys-feas", kind="group", title="Per-isolate memory ceiling",
         text="Confirm the actual memory limit one Cloudflare Worker isolate gets today, and whether any Cloudflare product or plan tier offers more, since every downstream chunk size depends on this number.",
         status="needs_spike", critical_path=True,
         why="Documented, but the exact current figure needs checking against live docs and this account's plan before anything is sized against it."),
    dict(id="spike-memcap", parent="feas-mem", kind="leaf", title="Week-1 spike: allocate-until-killed test",
         text="Deploy a Worker that allocates memory until the platform kills it, on this account's actual plan tier, and record the real ceiling.",
         atomic=True, risk=0.35, budget=0.15, complexity=0.15, parallel=True, dependency="none", status="needs_spike", critical_path=True,
         why="Cheapest possible way to replace a documentation guess with a measured number; half a day of work, gates every sizing decision after it."),
    dict(id="feas-shared", parent="sys-feas", kind="group", title="Shared or pooled memory across workers",
         text="Confirm whether two Cloudflare Worker isolates can read or write the same physical memory directly, at anything close to local RAM bandwidth -- or whether all cross-worker data movement necessarily goes over the network.",
         status="needs_spike", critical_path=True,
         why="My own read: Workers isolates are deliberately memory-isolated for security; there is no documented shared-memory fabric between them, so 'RAM speed across edge workers' as literally pitched is very likely not a real primitive. That belief could be wrong or stale, and it is the single highest-consequence assumption in the whole pitch, so it gets a live spike rather than being asserted as fact."),
    dict(id="spike-sharedmem", parent="feas-shared", kind="leaf", title="Week-1 spike: cross-worker transfer benchmark",
         text="Try to move a block of data from one Worker invocation to another without going through a network-facing API, and measure whatever bandwidth is actually achieved.",
         atomic=True, risk=0.6, budget=0.2, complexity=0.3, parallel=True, dependency="none", status="needs_spike", critical_path=True,
         why="If this comes back at network speed, not RAM speed, the architecture needs reframing now -- as sharded compute with network-exchanged deltas, not shared memory -- before 29 more days are spent building on the wrong assumption."),
    dict(id="feas-simd", parent="sys-feas", kind="leaf", title="WASM SIMD availability",
         text="Confirm the Workers runtime's WebAssembly engine supports the SIMD instruction proposal, and get a rough sense of the realistic speedup for a numeric anomaly-detection kernel.",
         atomic=True, risk=0.25, budget=0.15, complexity=0.15, parallel=True, dependency="none", status="known", critical_path=False,
         why="This part of the pitch is real and shipped (V8's WASM SIMD proposal); lower stakes, and answerable by reading current docs rather than a live spike."),

    dict(id="sys-ingest", parent="root", kind="group", title="Ingest and sharding",
         text="Split the source dataset into per-worker chunks that fit inside whatever the real memory ceiling turns out to be, and dispatch them to many workers in parallel."),
    dict(id="ingest-chunk", parent="sys-ingest", kind="leaf", title="Chunk sizing against the memory ceiling",
         text="Decide chunk size once the real per-isolate memory ceiling is known, leaving headroom for the running process, not just the raw data.",
         atomic=True, risk=0.35, budget=0.2, complexity=0.2, parallel=False, dependency="needs-other-item", status="needs_decision", critical_path=False,
         why="A direct decision, but it cannot be made responsibly until feas-mem's real number exists."),
    dict(id="ingest-source", parent="sys-ingest", kind="leaf", title="Where the source dataset lives",
         text="Choose where the large source dataset is actually read from -- Cloudflare R2, an external object store, or a streamed feed -- and how far a Worker can read into it per invocation.",
         atomic=True, risk=0.3, budget=0.35, complexity=0.3, parallel=True, dependency="needs-user-decision", status="needs_decision", critical_path=False,
         why="An architecture choice with real cost implications (R2 has no egress fee to Workers, external storage may), not something the plan itself has data to force."),
    dict(id="ingest-fanout", parent="sys-ingest", kind="leaf", title="Worker fan-out limits",
         text="Confirm how many Workers a single request can realistically fan out to in parallel, given Cloudflare's subrequest and concurrency limits on this account's plan.",
         atomic=True, risk=0.4, budget=0.25, complexity=0.2, parallel=True, dependency="needs-external-check", status="needs_spike", critical_path=False,
         why="Documented but plan-tier-dependent; determines whether 'many workers in parallel' means dozens or thousands for this account."),

    dict(id="sys-kernel", parent="root", kind="group", title="In-memory compute kernel",
         text="Run a vectorised (SIMD) anomaly-detection pass over each worker's own chunk, inside that worker's own memory, within the platform's per-invocation time budget."),
    dict(id="kernel-algo", parent="sys-kernel", kind="leaf", title="Pick a streaming-friendly anomaly algorithm",
         text="Choose an anomaly-detection method that can run one chunk at a time with no view of the whole dataset (online/incremental), since no single worker ever sees more than its own shard.",
         atomic=True, risk=0.5, budget=0.2, complexity=0.5, parallel=True, dependency="needs-user-decision", status="needs_decision", critical_path=False,
         why="A real design choice (e.g. streaming z-score/IQR variants, an online isolation-forest variant, or a sketch-based method) with accuracy trade-offs the plan alone can't resolve."),
    dict(id="kernel-budget", parent="sys-kernel", kind="group", title="Per-invocation compute budget",
         text="Measure the real CPU and wall-clock time one Worker invocation gets, and compare it against how much computation the chosen kernel actually needs per chunk.",
         status="needs_spike", critical_path=True,
         why="Workers have a hard per-invocation time limit; 'run all my high computation' inside one invocation is only true if the chunk's workload actually fits that limit, which has not been measured."),
    dict(id="spike-timebudget", parent="kernel-budget", kind="leaf", title="Week-1 spike: representative workload timing",
         text="Run a realistic chunk of the actual computation inside a real Worker invocation and measure wall-clock time against the platform's per-invocation limit.",
         atomic=True, risk=0.55, budget=0.25, complexity=0.25, parallel=True, dependency="none", status="needs_spike", critical_path=True,
         why="If a chunk's workload doesn't fit one invocation, the plan needs smaller chunks or a multi-invocation pattern per chunk -- worth knowing in week 1, not week 3."),
    dict(id="kernel-impl", parent="sys-kernel", kind="leaf", title="Implement and benchmark the SIMD kernel",
         text="Build the chosen anomaly-detection kernel in WASM with SIMD, and benchmark it against a plain (non-SIMD) version to confirm the speedup is real for this workload.",
         atomic=True, risk=0.3, budget=0.3, complexity=0.6, parallel=False, dependency="needs-other-item", status="deferred", critical_path=False,
         why="Real implementation work; only worth doing once the algorithm choice and the time-budget spike both say this is viable, so it is not a week-1 item."),

    dict(id="sys-orch", parent="root", kind="group", title="Cross-worker orchestration and delta exchange",
         text="Coordinate many independent Workers -- each running the same kernel on different data, the MIMD part of the pitch -- and move only the anomalous deltas between them, since there is no shared memory to pass full results through.\nListed child items: Choose the coordination primitive, Define the delta format, Define the reduce step."),
    dict(id="orch-primitive", parent="sys-orch", kind="leaf", title="Choose the coordination primitive",
         text="Pick how workers get coordinated and how work gets handed out: Durable Objects for stateful coordination, Queues for work distribution, or an external orchestrator outside Cloudflare.",
         atomic=True, risk=0.4, budget=0.4, complexity=0.4, parallel=True, dependency="needs-user-decision", status="needs_decision", critical_path=False,
         why="A real architecture decision with cost and latency trade-offs the plan can't make unilaterally."),
    dict(id="orch-delta", parent="sys-orch", kind="leaf", title="Define the delta format",
         text="Define what each worker actually emits when it finds an anomaly -- small enough to move cheaply over the network, since that is now the only channel between workers.",
         atomic=True, risk=0.35, budget=0.2, complexity=0.3, parallel=False, dependency="needs-other-item", status="needs_decision", critical_path=False,
         why="Depends on both the coordination primitive and on feas-shared's real answer about what channel exists at all."),
    dict(id="orch-reduce", parent="sys-orch", kind="leaf", title="Define the reduce step",
         text="Define how deltas from many independent workers get merged into one picture -- deduplicated, ordered, or aggregated as appropriate.",
         atomic=True, risk=0.35, budget=0.2, complexity=0.35, parallel=False, dependency="needs-other-item", status="deferred", critical_path=False,
         why="A design detail that follows once the coordination primitive is chosen; not needed to de-risk the plan in week 1."),

    dict(id="sys-train", parent="root", kind="group", title="Incremental training and persistence",
         text="Accumulate a trained model from a stream of deltas arriving from many short-lived invocations, and persist the running state somewhere that survives between them."),
    dict(id="train-state", parent="sys-train", kind="leaf", title="Where the accumulating state lives",
         text="Decide where the running model state is persisted between invocations, since Workers themselves are stateless and short-lived: Durable Objects, KV, R2, or an external database.",
         atomic=True, risk=0.45, budget=0.35, complexity=0.35, parallel=True, dependency="needs-user-decision", status="needs_decision", critical_path=False,
         why="A real, consequential choice (Durable Objects give strong consistency but add latency; KV/R2 are eventually consistent and cheaper) the plan can't make alone."),
    dict(id="train-online", parent="sys-train", kind="leaf", title="Confirm the model type supports incremental updates",
         text="Confirm the chosen model type can actually be updated incrementally from a stream of deltas, since a full retrain on every delta will not fit the time or memory budget.",
         atomic=True, risk=0.5, budget=0.3, complexity=0.4, parallel=True, dependency="needs-other-item", status="needs_spike", critical_path=False,
         why="Depends on kernel-algo's choice; some anomaly-detection methods have well-known online variants, others don't, and that isn't knowable until the algorithm is picked."),
]

COVERS = {
    "root": (None, "Root node; no single 'covers' judgement applies to the whole pitch."),
    "sys-feas": (True, "Memory ceiling, shared memory, and SIMD availability are the three concrete platform facts the rest of the architecture depends on; nothing else about platform feasibility is being assumed here."),
    "sys-ingest": (True, "Chunk sizing, source location, and fan-out limits are the three questions that fully determine how data gets from source to worker."),
    "sys-kernel": (True, "Algorithm choice, time budget, and implementation cover picking, sizing, and building the kernel."),
    "sys-orch": (False, "The three children cover choosing the mechanism and the data format, but not failure handling -- what happens when a worker crashes mid-computation, or a delta is lost -- which any real coordination layer needs and none of the three children address."),
    "sys-train": (True, "Where state lives and whether the model supports incremental updates are the two questions that determine whether 'train across many short-lived invocations' is coherent at all."),
    "feas-mem": (True, "The one child (the spike) is the entire resolution path for this question."),
    "feas-shared": (True, "The one child (the spike) is the entire resolution path for this question."),
    "kernel-budget": (True, "The one child (the spike) is the entire resolution path for this question."),
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
            if "Listed child items" not in str(n["text"]):
                n["text"] = n["text"] + (f"\nListed child items: {kids}." if kids else "")
            n["atomic_ref"] = False if n["kind"] == "group" else None
            n.setdefault("critical_path", any(by_id[c].get("critical_path") for c in n["children"]))
            n.setdefault("status", None)
            n.setdefault("why", None)
            for k in ("risk_ref", "budget_ref", "complexity_ref", "parallel_ref", "dependency_ref"):
                n[k] = None
        else:
            n["covers_ref"] = None
            n["covers_why"] = None
            n["atomic_ref"] = n.pop("atomic")
            n["risk_ref"] = n.pop("risk")
            n["budget_ref"] = n.pop("budget")
            n["complexity_ref"] = n.pop("complexity")
            n["parallel_ref"] = n.pop("parallel")
            n["dependency_ref"] = n.pop("dependency")
        out.append(n)
    assert all(n["dependency_ref"] in DEP or n["dependency_ref"] is None for n in out)
    OUT.write_text(json.dumps({"dep_options": DEP, "pitch": PITCH, "nodes": out}, indent=1))
    print(f"{len(out)} nodes -> {OUT}")


if __name__ == "__main__":
    main()
