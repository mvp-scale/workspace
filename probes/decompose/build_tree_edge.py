#!/usr/bin/env python3
"""Reference plan for the decompose-and-loop demo: a real pitch, decomposed as a component work
breakdown (6 swimlanes) with an orthogonal SDLC phase per leaf (spike/decide/build/validate/
launch), real predecessor edges, and duration estimates -- so a forward/backward CPM pass can
compute the actual critical path, float and schedule sensitivity, instead of an authored "risk"
number standing in for one.

Design rationale (from an Opus review of the previous, weaker version, itself built from five
independent adversarial reviews): the schedule is not this pitch's binding constraint -- the
plan fits in about 13 of 20 working days with real slack. The binding constraint is a platform
assumption: whether many independent Cloudflare Worker isolates can act as one pool of
high-bandwidth memory. My own read is that they almost certainly cannot (isolates are
deliberately memory-isolated; there is no documented shared-memory primitive between them) --
stated as a belief with a stated spike to check it, not asserted as settled fact, since platform
specifics can change and this box has no verified outbound access to check live docs.

'critical_path' and 'dependency_ref' are no longer authored -- they are derived from the edge
graph, so the two can no longer silently disagree with each other or with a node's own prose.
'complexity_ref' is derived from 'duration_days' bands instead of being an independent unitless
guess. 'risk_ref'/'budget_ref' are gone entirely: a model's own 'risk' answer is used only for
cross-model agreement, never graded against a reference that was equally subjective.

Writes probes/decompose/tree_ref_edge.json.
"""
import json, math
from pathlib import Path

OUT = Path(__file__).parent / "tree_ref_edge.json"
PITCH = ("Exploit high-bandwidth RAM across many Cloudflare Edge Workers: explode a dataset too large for one "
         "machine into per-worker memory, run SIMD/MIMD-style anomaly detection and incremental training across "
         "workers, and persist only the deltas -- so a model can be trained on data that would not fit in one "
         "machine's memory. Target: live in 30 days.")
HORIZON_DAYS = 20  # 4 working weeks
DEP_OPTIONS = ["none", "needs-user-decision", "needs-other-item", "needs-external-check"]
PHASE_OPTIONS = ["spike", "decide", "build", "validate", "launch"]

# ---------- the plan: root, 6 swimlane groups, 24 leaves ----------
GROUPS = [
    dict(id="sys-platform", title="Platform limits", owner_role="platform-eng",
         text="What Cloudflare's Workers platform actually gives you, measured or looked up, before anything else is sized against it."),
    dict(id="sys-ingest", title="Ingest and sharding", owner_role="data-eng",
         text="Getting the source dataset in and split into per-worker chunks that fit inside the platform's real limits."),
    dict(id="sys-kernel", title="Per-worker compute", owner_role="ml-eng",
         text="The anomaly-detection kernel that runs inside one worker's own memory, and whether sharded detection is even accurate enough to ship."),
    dict(id="sys-orch", title="Cross-worker exchange", owner_role="platform-eng",
         text="Coordinating many independent workers and moving only the anomalous deltas between them, since there is no shared memory to pass full results through."),
    dict(id="sys-train", title="Model state and training", owner_role="ml-eng",
         text="Accumulating a trained model from a stream of deltas across many short-lived invocations, and persisting the running state between them."),
    dict(id="sys-ops", title="Correctness, operations and launch", owner_role="sre",
         text="What a working prototype still needs before it can run unattended: failure handling, observability, a real cost figure, and a launch path. Missing from the pitch as given."),
]

# id, group, title, text, phase, duration_days, gate, predecessors[(id,type)], decision_owner,
# evidence, exit_criteria, target_metric, risk_reason, status
LEAVES = [
    dict(id="spike-memcap", group="sys-platform", title="Measure the per-isolate memory ceiling",
         text="Deploy a Worker that allocates memory until the platform kills it, on this account's real plan tier, and record the ceiling.",
         phase="spike", duration_days=0.5, duration_optimistic_days=0.25, duration_pessimistic_days=1.5,
         duration_basis="Optimistic: the kill signal is unambiguous and the ceiling is read off in one run. Pessimistic: the kill is a CPU-time limit, not a memory limit, and the measurement has to be redesigned to isolate the real cause.",
         gate=True, predecessors=[], evidence="platform_measurement",
         exit_criteria="A measured MB figure for this account's plan tier, not a documentation guess.",
         target_metric=dict(name="usable heap per isolate", unit="MB", needed=">= chunk size + working memory", assumed_today="~128 MB (unverified)"),
         risk_reason="Every downstream chunk-size decision is sized against this number; if it's much smaller than assumed, ingest has to change shape.",
         status="needs_measurement"),
    dict(id="spike-sharedmem", group="sys-platform", title="Measure worker-to-worker transfer",
         text="Try to move a block of data from one Worker invocation to another without a network-facing API, and measure whatever bandwidth is actually achieved -- or confirm no such path exists.",
         phase="spike", duration_days=1.0, duration_optimistic_days=0.5, duration_pessimistic_days=3.0,
         duration_basis="Optimistic: the docs already settle it -- no shared-memory primitive exists, confirmed and done. Pessimistic: this is the pitch's central claim, so it's worth trying several near-misses (SharedArrayBuffer, a KV race, a Durable Object as a mailbox) before writing down a confident 'no'.",
         gate=True, predecessors=[], evidence="platform_measurement",
         exit_criteria="Either a measured non-network transfer path with its bandwidth, or a documented confirmation none exists.",
         target_metric=dict(name="worker-to-worker bandwidth off the network path", unit="GB/s", needed="RAM-speed, as pitched", assumed_today="very likely none exists (isolates are memory-isolated)"),
         risk_reason="This is the pitch's central claim. If it's false as literally stated, the architecture is sharded-plus-network-exchange, not shared memory, and everything below is re-scoped, not merely delayed.",
         status="needs_measurement"),
    dict(id="feas-simd", group="sys-platform", title="Confirm WASM SIMD availability",
         text="Confirm the Workers runtime's WebAssembly engine supports the SIMD instruction proposal, and get a rough sense of realistic speedup for a numeric anomaly-detection kernel.",
         phase="spike", duration_days=0.5, duration_optimistic_days=0.25, duration_pessimistic_days=1.0,
         duration_basis="Low-stakes docs lookup either way; the only slippage risk is the docs being unclear about which runtime version ships the proposal.",
         gate=False, predecessors=[], evidence="docs",
         exit_criteria="Confirmed from current Cloudflare docs, with the speedup ballpark noted.",
         target_metric=dict(name="WASM SIMD support", unit="yes/no", needed="yes", assumed_today="yes, documented and shipped"),
         risk_reason="Low stakes and answerable by reading docs -- this part of the pitch is real.",
         status="documented"),
    dict(id="feas-fanout", group="sys-platform", title="Measure concurrency and fan-out ceilings",
         text="Measure the maximum simultaneous invocations and subrequests one deployment can sustain on this account's plan tier.",
         phase="spike", duration_days=0.5, duration_optimistic_days=0.25, duration_pessimistic_days=1.5,
         duration_basis="Pessimistic: the real ceiling is plan-tier-dependent and undocumented for the exact combination needed, so it may take a support ticket rather than a self-serve measurement.",
         gate=True, predecessors=[], evidence="platform_measurement",
         exit_criteria="A measured concurrent-invocation ceiling and subrequest limit for this account.",
         target_metric=dict(name="concurrent invocations x subrequests", unit="count", needed="ceiling x per-worker chunk >= dataset size", assumed_today="~1000 subrequests/request (unverified, plan-dependent)"),
         risk_reason="A generous per-isolate memory cap is worthless if only a handful of workers can run at once -- this is a platform limit, not an ingest design choice, which is why it moved here.",
         status="needs_measurement"),
    dict(id="feas-netcost", group="sys-platform", title="Measure exchange bandwidth and price",
         text="Measure achievable bytes/second and requests/second between a Worker and R2, and between a Worker and a Durable Object -- the channel every cross-worker exchange now has to use.",
         phase="spike", duration_days=1.0, duration_optimistic_days=0.5, duration_pessimistic_days=2.5,
         duration_basis="Two separate channels to benchmark (R2, Durable Objects), each with its own time-of-day variance; pessimistic case is re-running both to get a stable figure.",
         gate=True, predecessors=[("spike-sharedmem", "informs")], evidence="platform_measurement",
         exit_criteria="Measured MB/s and requests/s for both paths, plus their per-unit price.",
         target_metric=dict(name="Worker<->R2/Durable Object throughput", unit="MB/s, req/s", needed="enough to move the delta stream within the pass-time budget", assumed_today="R2 has no egress fee to Workers (documented); throughput unmeasured"),
         risk_reason="This is the replacement for shared memory. It doesn't kill the idea the way spike-sharedmem coming back negative would, but it sizes whether the re-scoped design can hit its own pass-time target.",
         status="needs_measurement"),

    dict(id="ingest-source", group="sys-ingest", title="Choose where the source dataset lives",
         text="Choose where the large source dataset is actually read from -- Cloudflare R2, an external object store, or a streamed feed.",
         phase="decide", duration_days=0.5, duration_optimistic_days=0.25, duration_pessimistic_days=2.0,
         duration_basis="Optimistic: a same-day call once the trade-off is laid out. Pessimistic: this needs the user's calendar, not more analysis -- decision tasks slip on availability, not difficulty.",
         gate=False, predecessors=[], decision_owner="user", evidence="decision",
         exit_criteria="One source chosen and reachable from a Worker.",
         target_metric=None, risk_reason="A real cost/latency trade-off (R2 has no egress fee to Workers; external storage may) that only the user can settle.",
         status="needs_decision"),
    dict(id="ingest-chunk", group="sys-ingest", title="Size the per-worker chunk",
         text="Decide chunk size once the real per-isolate memory ceiling and per-invocation time budget are both known, leaving headroom for the running process.",
         phase="decide", duration_days=1.0, duration_optimistic_days=0.5, duration_pessimistic_days=2.0,
         duration_basis="Only decidable once both upstream measurements land cleanly; if either was ambiguous this negotiation drags while a second measurement is sought.",
         gate=False, predecessors=[("spike-memcap", "fs"), ("spike-timebudget", "fs")], evidence="decision",
         exit_criteria="A chunk-size figure with its headroom margin stated.",
         target_metric=None, risk_reason="Made responsibly only once both ceilings it depends on are measured, not guessed.",
         status="needs_decision"),
    dict(id="ingest-loader", group="sys-ingest", title="Build the shard loader",
         text="Build the loader that reads one chunk into a Worker's own memory, inside both the measured memory ceiling and the measured time budget.",
         phase="build", duration_days=3.0, duration_optimistic_days=2.0, duration_pessimistic_days=5.0,
         duration_basis="First real implementation on the critical path; typical first-integration slip once the measured ceilings turn out tighter in practice than in a spike.",
         gate=False, predecessors=[("ingest-chunk", "fs"), ("ingest-source", "fs")], evidence="implementation",
         exit_criteria="Loads a chunk end-to-end within both measured ceilings, for every chunk in a real dataset.",
         target_metric=None, risk_reason="First real implementation on the critical path; blocked entirely on the two measurements above landing first.",
         status="to_build"),

    dict(id="kernel-algo", group="sys-kernel", title="Choose a streaming-friendly anomaly algorithm",
         text="Choose an anomaly-detection method that can run one chunk at a time with no view of the whole dataset, since no single worker ever sees more than its own shard.",
         phase="decide", duration_days=1.0, duration_optimistic_days=0.5, duration_pessimistic_days=2.5,
         duration_basis="Same calendar risk as any decision task, compounded by a real technical trade-off (streaming z-score/IQR vs. online isolation-forest vs. sketch-based) that has to actually be presented, not just asked.",
         gate=False, predecessors=[], decision_owner="user", evidence="decision",
         exit_criteria="One algorithm chosen with a stated reason it supports online/incremental scoring.",
         target_metric=None, risk_reason="A real design choice (streaming z-score/IQR variants, an online isolation-forest variant, a sketch-based method) with accuracy trade-offs the plan alone can't resolve.",
         status="needs_decision"),
    dict(id="spike-timebudget", group="sys-kernel", title="Measure the per-invocation compute budget",
         text="Run a realistic chunk of the chosen algorithm's computation inside a real Worker invocation and measure wall-clock time against the platform's per-invocation limit.",
         phase="spike", duration_days=1.0, duration_optimistic_days=0.5, duration_pessimistic_days=2.0,
         duration_basis="A representative chunk is hard to pick before the real loader exists; the pessimistic case is faking one, getting an unrepresentative number, and having to redo it once ingest-loader lands.",
         gate=True, predecessors=[("kernel-algo", "fs")], evidence="platform_measurement",
         exit_criteria="Measured wall-clock time for a representative chunk, compared against the platform's hard per-invocation limit.",
         target_metric=dict(name="compute time per chunk vs per-invocation CPU limit", unit="ms", needed="chunk compute time < platform limit", assumed_today="a hard per-invocation limit exists, plan-tier dependent"),
         risk_reason="If a chunk's workload doesn't fit one invocation, the plan needs smaller chunks or a multi-invocation pattern -- worth knowing in week 1, not week 3.",
         status="needs_measurement"),
    dict(id="kernel-impl", group="sys-kernel", title="Build and benchmark the SIMD kernel",
         text="Build the chosen anomaly-detection kernel in WASM with SIMD, and benchmark it against a plain (non-SIMD) version to confirm the speedup is real for this workload.",
         phase="build", duration_days=4.0, duration_optimistic_days=2.5, duration_pessimistic_days=7.0,
         duration_basis="The single most novel, highest-skill-risk build in the plan -- WASM SIMD tuning has a long, unpredictable tail even for an experienced engineer.",
         gate=False, predecessors=[("kernel-algo", "fs"), ("spike-timebudget", "fs"), ("feas-simd", "fs")], evidence="implementation",
         exit_criteria="Kernel measurably faster than a scalar baseline on a representative chunk, within the measured time budget.",
         target_metric=None, risk_reason="Only worth doing once the algorithm choice and the time-budget spike both say this is viable.",
         status="to_build"),
    dict(id="kernel-accuracy", group="sys-kernel", title="Validate accuracy against a single-machine baseline",
         text="Compare sharded, per-chunk online detection against a whole-dataset detector on the same data: does splitting the data cost real detection accuracy?",
         phase="validate", duration_days=3.0, duration_optimistic_days=2.0, duration_pessimistic_days=5.0,
         duration_basis="An unfavorable accuracy gap sends this back to kernel-algo for a second pass, not just a longer benchmark run -- the pessimistic case is one round-trip through that loop.",
         gate=False, predecessors=[("kernel-impl", "fs"), ("ingest-loader", "fs")], evidence="benchmark",
         exit_criteria="A measured accuracy gap (or lack of one) between sharded and whole-dataset detection, against a stated tolerance.",
         target_metric=None, risk_reason="The architecture can work perfectly and still be pointless if sharding costs too much detection accuracy. Nothing else in this plan asks this question.",
         status="to_validate"),

    dict(id="orch-primitive", group="sys-orch", title="Choose the coordination primitive",
         text="Pick how workers get coordinated and how work gets handed out: Durable Objects for stateful coordination, Queues for work distribution, or an external orchestrator outside Cloudflare.",
         phase="decide", duration_days=1.0, duration_optimistic_days=0.5, duration_pessimistic_days=2.5,
         duration_basis="A real architecture decision with cost/latency trade-offs; same calendar risk as other decision tasks.",
         gate=False, predecessors=[("spike-sharedmem", "fs"), ("feas-netcost", "informs")], decision_owner="user", evidence="decision",
         exit_criteria="One primitive chosen with its cost/latency trade-off stated.",
         target_metric=None, risk_reason="A real architecture decision with cost and latency trade-offs the plan can't make unilaterally.",
         status="needs_decision"),
    dict(id="orch-delta", group="sys-orch", title="Define the delta format",
         text="Define what each worker emits when it finds an anomaly -- small enough to move cheaply over the network, since that is now the only channel between workers.",
         phase="decide", duration_days=1.0, duration_optimistic_days=0.5, duration_pessimistic_days=1.5,
         duration_basis="A narrower decision than most here (format follows from the primitive already chosen), so the tail is shorter.",
         gate=False, predecessors=[("orch-primitive", "fs")], evidence="decision",
         exit_criteria="A delta schema with a stated size budget per record.",
         target_metric=None, risk_reason="Depends on which coordination primitive is chosen; a format cheap on Queues may be expensive on Durable Objects.",
         status="needs_decision"),
    dict(id="orch-reduce", group="sys-orch", title="Define the reduce step",
         text="Define how deltas from many independent workers get merged into one picture -- deduplicated, ordered, or aggregated as appropriate.",
         phase="decide", duration_days=2.0, duration_optimistic_days=1.0, duration_pessimistic_days=3.5,
         duration_basis="Ordering/dedupe guarantees are subtle and easy to under-scope on a first pass; pessimistic case is a second design pass once a gap is noticed.",
         gate=False, predecessors=[("orch-delta", "fs")], evidence="decision",
         exit_criteria="A reduce algorithm defined and its ordering/dedupe guarantees stated.",
         target_metric=None, risk_reason="A design detail that follows once the delta format is fixed.",
         status="needs_decision"),
    dict(id="orch-impl", group="sys-orch", title="Build dispatch and collect",
         text="Build the actual dispatch of chunks to workers and collection of their deltas, across the chosen coordination primitive.",
         phase="build", duration_days=4.0, duration_optimistic_days=2.5, duration_pessimistic_days=7.0,
         duration_basis="The first real exercise of the platform's true concurrency ceiling rather than an assumed one -- likely to surface surprises the fan-out spike didn't catch.",
         gate=False, predecessors=[("orch-reduce", "fs"), ("feas-fanout", "fs")], evidence="implementation",
         exit_criteria="Dispatches N workers and collects their deltas end-to-end, within the measured fan-out ceiling.",
         target_metric=None, risk_reason="The first implementation that actually exercises the platform's real concurrency ceiling, not an assumed one.",
         status="to_build"),

    dict(id="train-state", group="sys-train", title="Choose where accumulating state lives",
         text="Decide where the running model state is persisted between invocations, since Workers themselves are stateless and short-lived: Durable Objects, KV, R2, or an external database.",
         phase="decide", duration_days=1.0, duration_optimistic_days=0.5, duration_pessimistic_days=2.5,
         duration_basis="A consequential choice with a real consistency/latency trade-off; same calendar risk as other decision tasks.",
         gate=False, predecessors=[("orch-primitive", "informs")], decision_owner="user", evidence="decision",
         exit_criteria="One state store chosen with its consistency guarantee stated.",
         target_metric=None, risk_reason="A consequential choice (Durable Objects give strong consistency but add latency; KV/R2 are eventually consistent and cheaper) the plan can't make alone.",
         status="needs_decision"),
    dict(id="train-online", group="sys-train", title="Confirm the model supports incremental updates",
         text="Confirm the chosen model type can actually be updated incrementally from a stream of deltas, since a full retrain on every delta will not fit the time or memory budget.",
         phase="spike", duration_days=2.0, duration_optimistic_days=1.0, duration_pessimistic_days=4.0,
         duration_basis="If no online variant is documented for the chosen algorithm, this stops being a lookup and becomes its own small research task.",
         gate=False, predecessors=[("kernel-algo", "fs")], evidence="docs",
         exit_criteria="Confirmed online/incremental variant exists for the chosen algorithm, or an alternative chosen.",
         target_metric=None, risk_reason="Some anomaly-detection methods have well-known online variants, others don't -- unknowable until the algorithm is picked.",
         status="needs_measurement"),
    dict(id="train-impl", group="sys-train", title="Build state accumulation and reload",
         text="Build the accumulate/persist/reload cycle for the running model state across many independent, short-lived invocations.",
         phase="build", duration_days=3.0, duration_optimistic_days=2.0, duration_pessimistic_days=6.0,
         duration_basis="Concurrent-writer correctness is the plan's one stated coverage gap (see sys-train's covers_why below); this is where it actually has to get solved in code, which is where estimates most often blow out.",
         gate=False, predecessors=[("train-state", "fs"), ("train-online", "fs"), ("orch-impl", "ss")], evidence="implementation",
         exit_criteria="State survives across invocations and reflects every delta applied, under concurrent writers.",
         target_metric=None, risk_reason="Where the open concurrency question below actually has to be resolved in code, not just decided on paper.",
         status="to_build"),

    dict(id="ops-failure", group="sys-ops", title="Handle worker failure",
         text="Design for a worker dying mid-chunk or a delta going missing: retries, idempotent shard ids, at-least-once delivery with dedupe in the reduce step.",
         phase="build", duration_days=2.0, duration_optimistic_days=1.0, duration_pessimistic_days=4.0,
         duration_basis="Absent from the original pitch, so there's no prior design to build against -- real risk of discovering a second failure mode mid-implementation.",
         gate=False, predecessors=[("orch-impl", "ss")], evidence="implementation",
         exit_criteria="A killed worker's chunk gets retried and its delta (if any) is neither lost nor double-counted.",
         target_metric=None, risk_reason="Absent from the pitch as given; a distributed system that assumes every worker finishes is not a real distributed system.",
         status="to_build"),
    dict(id="ops-observability", group="sys-ops", title="Add per-pass observability",
         text="Emit per-pass metrics: shards completed, deltas emitted, bytes moved, invocation time, kill rate.",
         phase="build", duration_days=1.5, duration_optimistic_days=1.0, duration_pessimistic_days=2.5,
         duration_basis="Mostly wiring against metrics that already exist elsewhere in the build; modest tail.",
         gate=False, predecessors=[("orch-impl", "ss")], evidence="implementation",
         exit_criteria="A dashboard or log stream showing all five metrics for a real pass.",
         target_metric=None, risk_reason="Without this, ops-e2e and ops-costmodel have nothing real to measure against.",
         status="to_build"),
    dict(id="ops-costmodel", group="sys-ops", title="Build a real cost projection",
         text="Project cost per full pass and per day at target scale -- invocations, GB moved, Durable Object time -- against a budget the pitcher has to supply.",
         phase="validate", duration_days=1.0, duration_optimistic_days=0.5, duration_pessimistic_days=2.0,
         duration_basis="Depends on three upstream measurements; if any came in worse than assumed, the cost model has to be redone before it's a stated figure.",
         gate=False, predecessors=[("feas-netcost", "fs"), ("feas-fanout", "fs"), ("ingest-chunk", "fs")], evidence="benchmark",
         exit_criteria="A dollar figure per pass and per day, checked against a stated budget.",
         target_metric=None, risk_reason="Nowhere in the original pitch is there a cost figure at all; this is the fix.",
         status="to_validate"),
    dict(id="ops-e2e", group="sys-ops", title="Run end-to-end at target scale",
         text="Run the full pipeline on the full dataset at the target worker count, from a cold start.",
         phase="validate", duration_days=2.0, duration_optimistic_days=1.5, duration_pessimistic_days=4.0,
         duration_basis="The first point every prior piece has to actually work together, not just in isolation -- classic integration-day risk, where the pessimistic case is one full extra debugging pass.",
         gate=False, predecessors=[("kernel-accuracy", "fs"), ("train-impl", "fs"), ("ops-failure", "fs"), ("ops-observability", "fs")], evidence="benchmark",
         exit_criteria="One complete pass at target scale, cold start to finished delta set, with no unhandled failures.",
         target_metric=None, risk_reason="The first point every prior piece has to actually work together, not just in isolation.",
         status="to_validate"),
    dict(id="ops-launch", group="sys-ops", title="Deploy and launch",
         text="Deploy path, rollback plan, secrets and limits configuration, a runbook, and a go/no-go checklist.",
         phase="launch", duration_days=2.0, duration_optimistic_days=1.0, duration_pessimistic_days=3.5,
         duration_basis="The launch gate itself; pessimistic case is a rollback dry run or secrets/limits review turning up something that has to be fixed before go-live.",
         gate=False, predecessors=[("ops-e2e", "fs"), ("ops-costmodel", "fs")], evidence="implementation",
         exit_criteria="A deployed, rollback-capable system with a runbook a second engineer could follow.",
         target_metric=None, risk_reason="The launch gate itself; blocked on everything else landing.",
         status="to_build"),
]

# the one genuine, still-unfilled coverage gap: sys-train's 3 children don't address concurrent writers
COVERS = {
    "root": (None, "Root node; no single 'covers' judgement applies to the whole pitch."),
    "sys-platform": (True, "Memory ceiling, shared memory, SIMD availability, fan-out and exchange cost are the five concrete platform facts the rest of the architecture depends on."),
    "sys-ingest": (True, "Source, chunk size and the loader that builds on them fully cover getting data from source to worker."),
    "sys-kernel": (True, "Algorithm choice, implementation and an accuracy check against a real baseline cover picking, building and validating the kernel."),
    "sys-orch": (True, "Coordination primitive, delta format, reduce step and the implementation that builds them cover moving deltas between workers."),
    "sys-train": (False, "Where state lives and whether the model updates incrementally are two real questions, but neither addresses what happens when several workers finish at the same moment and all try to write the accumulated state. Last-write-wins silently loses updates; a single serialising writer becomes a bottleneck for a design whose whole premise is many workers training at once. That is a real hole, and nothing else in this plan fills it."),
    "sys-ops": (True, "Failure handling, observability, a real cost figure and a launch path cover what a prototype needs before it can run unattended."),
}

OUT_OF_SCOPE_V1 = [
    ("Multi-tenancy and auth", "Nothing in the pitch names more than one user or dataset owner; adding access control before the architecture is even validated would be solving a problem that may not exist yet."),
    ("Autoscaling policy", "Cloudflare already autoscales Workers; a custom policy is only worth designing once ops-e2e shows the default behaviour is actually a problem."),
    ("Detector quality tuning beyond baseline parity", "kernel-accuracy asks 'does sharding cost accuracy', not 'is this the best possible detector' -- tuning belongs after the architecture is proven, not before."),
    ("Cold-start optimisation", "A slower first request per worker is a UX problem, not an architecture problem; irrelevant until ops-e2e shows it matters at target scale."),
]


def cpm(nodes_by_id, edges_type):
    """Forward/backward pass over finish-to-start and start-to-start edges. 'informs' edges are
    treated as soft start-to-start for scheduling (they don't block starting) but kept distinct in
    edges_type for rendering. Returns per-id {es, ef, ls, lf, float, on_critical}."""
    order = []
    seen = set()
    def visit(nid):
        if nid in seen:
            return
        seen.add(nid)
        for p, _ in nodes_by_id[nid].get("predecessors", []):
            visit(p)
        order.append(nid)
    for nid in nodes_by_id:
        visit(nid)
    es, ef = {}, {}
    for nid in order:
        n = nodes_by_id[nid]
        start = 0.0
        for p, typ in n.get("predecessors", []):
            start = max(start, ef[p] if typ == "fs" else es[p])
        es[nid] = start
        ef[nid] = start + n["duration_days"]
    span = max(ef.values()) if ef else 0.0
    lf, ls = {}, {}
    successors = {nid: [] for nid in nodes_by_id}
    for nid in nodes_by_id:
        for p, typ in nodes_by_id[nid].get("predecessors", []):
            successors[p].append((nid, typ))
    for nid in reversed(order):
        n = nodes_by_id[nid]
        finish = span
        for s, typ in successors[nid]:
            # fs: this node must finish by the successor's latest start.
            # ss/informs: this node's *start* must be by the successor's latest start, i.e.
            # finish <= ls[s] + this node's own duration (using the successor's LATEST start,
            # already computed since successors precede nid in this reversed topological order --
            # using es[s] here was a bug: it let a same-day "informs" successor cap this node's
            # finish below its own earliest finish, producing impossible negative float).
            bound = ls[s] if typ == "fs" else ls[s] + n["duration_days"]
            finish = min(finish, bound)
        lf[nid] = finish
        ls[nid] = finish - n["duration_days"]
    out = {}
    for nid in nodes_by_id:
        flt = round(ls[nid] - es[nid], 3)
        out[nid] = {"earliest_start_day": round(es[nid], 2), "earliest_finish_day": round(ef[nid], 2),
                     "latest_start_day": round(ls[nid], 2), "latest_finish_day": round(lf[nid], 2),
                     "total_float_days": flt, "on_critical_path": flt <= 1e-6}
    return out, span


def sensitivity(nodes_by_id, factor):
    scaled = {nid: {**n, "duration_days": n["duration_days"] * factor} for nid, n in nodes_by_id.items()}
    _, span = cpm(scaled, None)
    return round(span, 2)


def blocks_count(nodes_by_id):
    """Transitive successor count per node -- how much of the plan a delay here drags with it."""
    successors = {nid: [] for nid in nodes_by_id}
    for nid in nodes_by_id:
        for p, _ in nodes_by_id[nid].get("predecessors", []):
            successors[p].append(nid)
    out = {}
    for nid in nodes_by_id:
        seen = set()
        stack = list(successors[nid])
        while stack:
            s = stack.pop()
            if s in seen:
                continue
            seen.add(s)
            stack.extend(successors[s])
        out[nid] = len(seen)
    return out


def derive_dependency_ref(n):
    if n.get("decision_owner") == "user":
        return "needs-user-decision"
    if any(t == "fs" for _, t in n.get("predecessors", [])):
        return "needs-other-item"
    if n.get("evidence") == "platform_measurement":
        return "needs-external-check"
    return "none"


def derive_parallel_ref(n, nodes_by_id):
    """A node is parallel with its group siblings iff no sibling is among its transitive predecessors."""
    preds = set()
    stack = [p for p, _ in n.get("predecessors", [])]
    while stack:
        p = stack.pop()
        if p in preds:
            continue
        preds.add(p)
        stack.extend(q for q, _ in nodes_by_id[p].get("predecessors", []))
    siblings = {m["id"] for m in nodes_by_id.values() if m.get("group") == n.get("group") and m["id"] != n["id"]}
    return not (preds & siblings)


def complexity_band(duration_days):
    if duration_days < 1:
        return 0.0
    if duration_days == 1:
        return 0.25
    if duration_days == 2:
        return 0.5
    if duration_days <= 4:
        return 0.75
    return 1.0


def main():
    by_id = {n["id"]: dict(n) for n in LEAVES}
    for nid, n in by_id.items():
        n["kind"] = "leaf"
    # validate every 'why'/'risk_reason' mention of a real node id is a stated predecessor (guards
    # against the ingest-chunk/feas-mem class of contradiction from the previous version)
    import re
    id_pat = re.compile(r"\b([a-z]+-[a-z]+(?:-[a-z]+)?)\b")
    for n in by_id.values():
        preds = {p for p, _ in n.get("predecessors", [])}
        mentioned = {m for m in id_pat.findall(n.get("risk_reason", "") + " " + n.get("text", "")) if m in by_id and m != n["id"]}
        # informational only in this pass; real guard is the predecessors list itself being authoritative
        del mentioned

    cpm_out, span = cpm(by_id, None)
    blocks = blocks_count(by_id)
    sens = {"1.0": span, "1.5": sensitivity(by_id, 1.5), "2.0": sensitivity(by_id, 2.0)}
    critical_path_ids = [nid for nid in sorted(by_id, key=lambda k: cpm_out[k]["earliest_start_day"]) if cpm_out[nid]["on_critical_path"]]

    nodes = []
    root = dict(id="root", parent=None, kind="root", title="Edge-RAM anomaly training pipeline", text=PITCH,
                layer=0, children=[g["id"] for g in GROUPS], covers_ref=COVERS["root"][0], covers_why=COVERS["root"][1],
                atomic_ref=None, risk_reason=None, status=None, gate=False, phase=None)
    nodes.append(root)
    for g in GROUPS:
        kids = [n["id"] for n in LEAVES if n["group"] == g["id"]]
        covers, why = COVERS[g["id"]]
        nodes.append(dict(id=g["id"], parent="root", kind="group", title=g["title"],
                           text=g["text"] + f"\nListed child items: {', '.join(by_id[k]['title'] for k in kids)}.",
                           layer=1, children=kids, covers_ref=covers, covers_why=why, atomic_ref=False,
                           owner_role=g["owner_role"], risk_reason=None, status=None, gate=False, phase=None))
    for n in LEAVES:
        node = dict(n)
        node["parent"] = node.pop("group")
        node["kind"] = "leaf"
        node["layer"] = 2
        node["children"] = []
        node["covers_ref"] = None
        node["covers_why"] = None
        node["atomic_ref"] = True
        node["dependency_ref"] = derive_dependency_ref(n)
        node["parallel_ref"] = derive_parallel_ref(n, by_id)
        node["complexity_ref"] = complexity_band(n["duration_days"])
        node.setdefault("decision_owner", None)
        node["predecessors"] = [{"id": p, "type": t} for p, t in n.get("predecessors", [])]
        node.update(cpm_out[n["id"]])
        node["week"] = math.ceil((cpm_out[n["id"]]["earliest_start_day"] + 0.01) / 5) if cpm_out[n["id"]]["earliest_start_day"] < HORIZON_DAYS else None
        node["blocks_count"] = blocks[n["id"]]
        nodes.append(node)

    OUT.write_text(json.dumps({
        "dep_options": DEP_OPTIONS, "phase_options": PHASE_OPTIONS, "pitch": PITCH,
        "horizon_working_days": HORIZON_DAYS, "days_per_week": 5,
        "schedule": {"span_days": span, "critical_path": critical_path_ids, "float_days": round(HORIZON_DAYS - span, 1), "sensitivity": sens},
        "out_of_scope_v1": [{"title": t, "why": w} for t, w in OUT_OF_SCOPE_V1],
        "nodes": nodes,
    }, indent=1))
    print(f"{len(nodes)} nodes -> {OUT}")
    print(f"span {span} of {HORIZON_DAYS} working days, float {round(HORIZON_DAYS - span, 1)}, critical path: {' -> '.join(critical_path_ids)}")
    print(f"sensitivity: {sens}")


if __name__ == "__main__":
    main()
