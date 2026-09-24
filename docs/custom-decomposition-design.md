# Custom decomposition: design

Written 2026-09-23 as the design pass that `docs/scenario-lab-structures-plan.md` ("Custom
decomposition, design delegated separately") points to. It is meant to be built from directly:
every decision below is made, with its reason. Open questions that need a person are at the end,
and none of them blocks v1.

Grounded in: `demo/scenarios.html` (the `STRUCTURES` rail, `renderDecomposeTree`, `ganttBoard`,
`S()`, `buildTreeView`), `demo/static/app.css`, `demo/static/app.js`, `demo/server.py` (`call`,
`one_item`, `batch`, `status`, the handler), `probes/lab_decompose.py` (`battery`, `grade`),
`foundry/README.md`, `foundry/PLAN.md`, `BRIDGE.md`, `foundry/layered_walk.py`,
`foundry/funnel.py`, `foundry/tools/world-knowledge.yaml`, `foundry/tools/slicer.yaml`, a real
ledger (`foundry/runs/oncall-rotation-layered-walk.jsonl`) and the measured latencies in
`data/probe-runs-v2/_batch/` (via `server.batch_perf()`).

---

## 1. Methodology: foundry's Slicer + Grinder for structure, lab_decompose's leaf battery for annotation

**Decision: a hybrid, but a specific one.** Foundry's walk decides *which* library items apply and
in what order. `lab_decompose.py`'s leaf battery, minus the questions that only mattered for
grading, describes each requirement the walk reaches. Neither method works alone here:

- **lab_decompose alone can't work.** `battery()` asks questions *about nodes of a tree that
  already exists* (`probes/decompose/tree_ref_edge.json`, hand-authored). Freeform user text has no
  tree. The only ways to get one are for Claude to write it (forbidden by foundry's one rule, and
  exactly the "grading your own homework" failure in foundry's Lessons learned) or to generate it
  (these models return probabilities, not text). So lab_decompose can't supply the structure.
- **Foundry alone wastes its leaf call on a check that doesn't work.** In `layered_walk.py` a
  visited leaf gets one call whose only question is `atomic`. `foundry/PLAN.md` records the
  diagnostic: on 90 known-atomic leaves against 21 known-compound categories, atomic and compound
  scores are separated by **+0.006**. At `ATOMIC_THRESHOLD=0.18` the check is right 21.6% of the
  time; calling everything atomic would be right 81.1% of the time. The real ledger agrees: of 78
  grinder nodes in the oncall-rotation run, 32 ended `uncertain` and 18 `needs_split_no_library`.
  Every library tree is depth 1 (world-knowledge.yaml's own comment), so a leaf that fails the
  check has nowhere left to split anyway. The atomic answer changes nothing and is noise.
- **The hybrid spends that same leaf call on something useful.** Library leaves were written to be
  atomic (the no-"and"/"or" rule), so a reached leaf is simply a requirement. Its one call becomes
  lab_decompose's reference-free leaf questions: `gate`, `phase`, `risk`, `complexity`,
  `dependency`. `battery()` already asked these; `grade()` compared them with hand-authored
  `*_ref` fields that don't exist here. Without the grading they are still meaningful, typed
  descriptions of each requirement. The call count stays the same and the output gets much
  richer.

What carries over from foundry exactly (parity matters; see the acceptance test in §5):
intake = the user's text plus an optional "who it's for" (foundry's two-question intake); the
Slicer frame call (domain and audience `choice`, 10 `profile_probes`, `depth_estimate`);
margin-based `choice_trust`; the `domain_enrichment` lookup; the 21-category "is this NOT yet
true" call; shape-guaranteed seeding (`SHAPE_TOPK=1`, `GUARANTEED_BONUS=10`); composite priority
`0.7·gap + 0.3·profile boost`; one shared max-priority queue; `CHILD_MIN_SANITY=0.05`; a hard
call budget where **one call is one node, however many models answer**; combining by mean, with
spread = max − min; and `DISAGREEMENT_THRESHOLD=0.3` (from `funnel.py`).

The one rule carries over unchanged. **Only the user's text is specific to the idea.** Every
sentence the page shows as part of the decomposition is library text from
`foundry/tools/world-knowledge.yaml` (21 categories, 90 requirements) or a fixed question.
The models only choose among items and score them. They never write anything, and the UI has to
make that plain (§3.6).

### What replaces grading, since there is no ground truth

Scorecards, "model agreed/disagreed with my call", Wilson intervals and red "wrong" cells all
assume a correct answer, and none exists here. Four things are honest to show instead, all
computed from this run's own numbers:

1. **Agreement.** For every number, show the spread between models (max − min), not just the
   mean. At spread ≥ 0.3 (`funnel.DISAGREEMENT_THRESHOLD`) the item is marked *models split*,
   the same bucket foundry calls "needs a decision". Per-model values are always one click away.
2. **Lift over a blank control.** Real relevance scores are compressed: in the oncall ledger every
   child of `nonfunctional-performance` scored between 0.54 and 0.58. A raw 0.56 says nothing about
   the user's text. So the 21-category call also runs once on a fixed, generic **control intake**
   (`"Idea: a software product.\n\nWho this is for: its users."`). The page shows **lift** =
   per-model p(text) − p(control), averaged across models. Lift is the part of a score the user's
   text caused. The control is fixed generic content, so it's allowed. `one_item`'s cache keys on
   content, so after the first run the control costs nothing. It does not count against the walk
   budget, which keeps foundry parity. Lift is shown on screen but doesn't set priority, again for
   parity.
3. **Did each model discriminate?** A model whose 21 category scores span less than 0.10
   (max − min) is flagged "didn't discriminate on this text". This is the same idea as
   `decomposeStory().alwaysNo` in scenarios.html, and it's the failure foundry's README warns
   averaging hides ("cross-model disagreement can mean one model isn't discriminating at all").
   The 0.10 is a first attempt and is labelled as one in the code.
4. **Scope.** The library is shaped around software requirements (SRS/arc42 shapes), and "anything"
   includes text it doesn't fit, like a personal problem or a policy question. The frame call
   carries one extra generic `noul`, `scope`: "Does this text describe something a person or team
   would build, change or run: a product, service, system or process?" If the mean is below 0.4,
   a `callout warn` reads "This library is for buildable things; these results may not mean
   much for this text." It warns but doesn't block, since the question itself hasn't been
   validated.

The page says the rest directly: *"There are no right answers here. This shows which library
items the models picked for your text, how strongly, and whether they agreed. It doesn't show
whether they were right."* It also refuses a schedule, as lab_decompose and foundry's
`monte-carlo.yaml` both do: no durations exist, so no dates, critical path or forecast are
computed.

---

## 2. Live API

### 2.1 New module: `probes/lab_custom_decompose.py` (reuse foundry's pattern, not its code)

**Don't import `foundry/layered_walk.py`.** It mutates a module-global `MODELS`, writes a ledger
file keyed by `--idea` from inside the walk, prints progress, imports `funnel` and `server` through
`sys.path` hacks, and calls models one after another. `foundry/README.md` also says the pipeline
is "not wired into the Scenario lab, and shouldn't be until this is proven out further." **Do
read its library data** (`world-knowledge.yaml`, and `slicer.yaml`'s `by-domain` questions)
directly, read-only. A copy would create two libraries to keep in sync, and world-knowledge.yaml's
own header says that duplication is what it was created to end. Every run records the
library's sha256, so a run always says which library version it used. (Open question 1 covers the
README line.)

The module is named `lab_*` to match `lab_batch.py` and `lab_decompose.py`. It uses only the
standard library plus `yaml`, imported lazily. `yaml` is PyYAML 6.0.3 in `/usr/bin/python3`,
which server.py already runs under. If the import fails, the endpoints return 503 with
`"PyYAML missing"`, and server.py stays stdlib-only at import time.

**It must not import `server`.** `lab_decompose.py` does `import server`. When server.py runs as
`__main__`, importing a module that imports `server` loads a *second* copy with its own
`BACKENDS` and `_cache`. So the walk takes its model call as an injected function:

```python
# probes/lab_custom_decompose.py -- public surface
LIBRARY_PATH = ROOT / "foundry" / "tools" / "world-knowledge.yaml"
SLICER_PATH  = ROOT / "foundry" / "tools" / "slicer.yaml"
CONTROL_INTAKE = "Idea: a software product.\n\nWho this is for: its users."
SPACE = 113            # 1 frame + 1 categories + 21 category nodes + 90 leaves (foundry/PLAN.md)
MAX_TEXT, MAX_WHO = 4000, 1000
# constants copied verbatim from layered_walk.py / funnel.py / lab_decompose.py, each with a
# "copied from <file>:<name>, keep in sync" comment and a unit test asserting equality where importable:
SHAPE_TOPK, GUARANTEED_BONUS, CHILD_MIN_SANITY = 1, 10.0, 0.05
W_GAP, W_PROFILE = 0.7, 0.3
DOMAIN_AUDIENCE_MIN, DOMAIN_AUDIENCE_MARGIN = 0.3, 0.15
DISAGREEMENT_THRESHOLD = 0.3
FLAT_RANGE = 0.10      # new, first attempt: a model whose 21 category scores span < this is flagged
SCOPE_WARN = 0.40      # new, first attempt
LEVELS5, PHASE_CRITERIA  # verbatim from lab_decompose.py

def load_library() -> dict        # {"sha256", "shapes": [...], "categories": [{id,text,shape,children:[{id,text}]}],
                                  #  "profile_probes": [...], "domain_enrichment", "pain_points", "delights",
                                  #  "customer_journey", "by_domain_questions"}  -- cached by file mtime
def skeleton(lib) -> dict         # client-safe subset for GET /api/decompose-library (see 2.3)
def walk(text, who, models, budget, ask, lib=None):   # generator of event dicts (see 2.4)
    # ask(model_id, item) -> server.one_item-shaped result: {"answers": {...}, "latency_ms", "cached"?} or {"error"}
```

Inside `walk`, each call goes to all selected models **at once** (`ThreadPoolExecutor(len(models))`,
the same pattern as `/api/compare`). Nodes run **in order**: the priority queue has to be popped
one node at a time, and running one node at a time keeps the GPU load to one battery per model,
which matters after BRIDGE.md's kev-4b OOM. That OOM was caused by 40 questions in one call. The
largest call here has 21 questions (the category call), and the module asserts `len(questions)
<= 24` for every call.

**The five calls and their exact text.** Polarity is where foundry went wrong twice, so the text
is fixed here:

| Call | State | Questions |
|---|---|---|
| frame (1) | `base` = `f"Idea: {text}"` + (`f"\n\nWho this is for: {who}"` if who) | `domain`, `audience` (slicer.yaml by-domain, verbatim); `profile::<id>` ×10 (world-knowledge, verbatim, as in `classify_domain_audience_and_profile`); `depth_estimate` (verbatim `DEPTH_CRITERIA`); **`scope`** (new, text in §1). 14 questions. |
| control (0 budget) | `CONTROL_INTAKE` | the same 21 category questions as below |
| categories (1) | `enriched` = base + foundry's enrichment sentence when `choice_trust(domain) and choice_trust(audience)`, verbatim from `layered_walk.main()` | 21 × foundry's `classify_root` question, verbatim: `<category text>\n\nQuestion: is this NOT yet true for this idea as currently described -- i.e., is this a real, unaddressed gap?` |
| category node (≤21) | `enriched + "\n\nGaps already identified for this idea (confirmed NOT yet true, i.e. real, unaddressed gaps so far): " + <category text>` (foundry's `process_node` breadcrumb, verbatim) | one `child::<id>` per library child, verbatim from foundry's `classify_node`. 4–5 questions. No `atomic`, because a category has children and so can't be atomic, which is foundry's own structural rule. |
| leaf (≤90) | `enriched + "\n\nA gap already identified for this idea (confirmed NOT yet true): " + <category text> + " Specifically, not yet true: " + <leaf text> + "\n\nWork item: make this requirement true for this idea."` | the five below. |

Leaf battery. It is `lab_decompose.battery()` with "this item" changed to "this work item", and
with `atomic` (see §1) and `parallel` dropped. `parallel` asks about "siblings in its group", and
here the siblings are whichever library items the queue happened to reach, which isn't a real
group:

```python
LEAF_BATTERY = {
  "gate": noul("Question: if this work item turns out harder or different than expected, does the overall design of the idea have to change shape -- not just take longer?",
               true="A surprise here would force a redesign, not just a delay.", false="A surprise here would only cost time, not change the design."),
  "phase": choice("Question: which of these best describes this work item?", PHASE_CRITERIA),          # spike/decide/build/validate/launch
  "risk": score("Question: if this work item is left undone or wrong, how likely is it to make the overall idea run behind schedule (delay or rework)?",
                [f"{l} risk of schedule delay or rework" for l in LEVELS5]),
  "complexity": score("Question: how complex is this work item to actually do?", [f"{l} complexity" for l in LEVELS5]),
  "dependency": choice("Question: what mainly stands between this work item and being done?", {   # lab_decompose's options, verbatim
      "none": ..., "needs-user-decision": ..., "needs-other-item": ..., "needs-external-check": ...}),
}
```

Each question's `instructions` is prefixed with `<leaf text>\n\n`, following lab_decompose's
`node["text"] + "\n\nQuestion: ..."`.

**CLI**, for the lab's "every structure has an offline runner" rule:
`python3 probes/lab_custom_decompose.py --text-file idea.txt [--who "..."] [--intake foundry/ideas/<id>.json] --models semif,kev-4b,so1 --budget 60 --out data/probe-runs-v2/_custom_decompose/<slug>.jsonl`.
It writes exactly the event stream from §2.4, one per line. It does `import server` itself, as
lab_decompose does, and passes `ask=lambda m, it: server.one_item(m, server.BACKENDS[m], it)`.
The output stays outside `data/bench/`.

> **Update:** the CLI and server originally refused any `hosted` backend here (cost-safety
> default, since a live run could otherwise make unbounded paid calls with no budget-ledger tie-in).
> `jev` is now allowed, since the run's own `budget` parameter (3-113 calls total) already bounds
> the cost regardless of which models are selected.

### 2.2 Server wiring (`demo/server.py`, about 60 lines)

```python
sys.path.insert(0, str(ROOT / "probes")); import lab_custom_decompose as lcd   # near the top, after ROOT
_decompose_lock = threading.Lock()
```

- `GET /api/decompose-library` → `lcd.skeleton(lcd.load_library())`. The page uses it to draw the
  whole candidate map before any call.
- `GET /api/decompose-examples` → `[{"id", "idea", "customer"}]` from `foundry/ideas/*.json`.
  These are the 7 existing intakes, which are the only content foundry allows Claude to author, so
  the page gets example chips without anyone writing anything new. It reads only `idea` and
  `customer`, even though some files have a `pieces` field.
- `POST /api/decompose-live`, which streams (§2.4).

Validation, in this order:

| Condition | Response |
|---|---|
| bad JSON, `text` empty or > 4000, `who` > 1000, `budget` not an int in 3..113, `models` not a non-empty list of ≤5 | 400 `{"error": "need JSON {text, who?, models:[...], budget:3-113}"}` |
| a model not in `BACKENDS` | 404 `unknown backend X` |
| a model not `up` in `status()` | 409 `X is not loaded` |
| `_decompose_lock.acquire(blocking=False)` fails | 409 `another decomposition is running; try again when it finishes` |
| PyYAML missing | 503 |

Streaming, which is the one new mechanism in server.py. `BaseHTTPRequestHandler` defaults to
HTTP/1.0, so a response with no `Content-Length` followed by closing the connection is valid,
and `fetch` can read it bit by bit:

```python
def _stream(self, events):
    self.send_response(200)
    self.send_header("Content-Type", "application/x-ndjson")
    self.send_header("Cache-Control", "no-store")
    self.end_headers()
    self.close_connection = True
    try:
        for ev in events:
            self.wfile.write((json.dumps(ev) + "\n").encode()); self.wfile.flush()
    except (BrokenPipeError, ConnectionResetError):
        pass                       # client pressed Stop or navigated away
    finally:
        events.close()             # GeneratorExit inside walk(): no further model calls are made
        _decompose_lock.release()
```

The server's `ask` is `lambda m, item: one_item(m, BACKENDS[m], item)`, so the walk reuses the
existing content cache. That gives **"Spend N more" for free**: running again with `budget + N`
on the same text replays the first `budget` calls from cache, since the walk is deterministic
(same answers give the same heap order, and ties break on the insertion counter). The model only
does new work for the extra calls. No server-side session state is needed. `_cache` is unbounded
and in memory, which is fine for a local demo. Note it in a code comment.

### 2.3 `GET /api/decompose-library` response

```json
{
  "sha256": "9f2c…",
  "space": 113,
  "shapes": ["functional","non-functional","architectural","user-story","technical-spec","operational"],
  "categories": [
    {"id": "functional-core-capability", "shape": "functional",
     "text": "The system performs every action its users need in order to complete the task it exists for.",
     "children": [{"id": "func-action-inventory", "text": "The requirements name every action a user can perform in the system."}, "…"]}
  ],
  "profile_probes": [{"id": "sensitive-data", "text": "…", "boosts": ["nonfunctional-data-protection", "…"]}],
  "questions": {"leaf": ["gate","phase","risk","complexity","dependency"], "phase_options": ["spike","decide","build","validate","launch"]}
}
```

The library order is the order in the YAML. The radial layout (§3) depends on it, so layout is
deterministic and matches across runs.

### 2.4 The event stream (NDJSON, one object per line; the CLI ledger has the same shape)

Every event has `t` (type) and `seq` (the budget-counted call number, or `0` for events that
aren't calls). Every combined value has the same shape, so the client can recompute it for any
subset of models: `V = {"mean": float|null, "spread": float|null, "per_model": {model: float}}`.

```jsonc
{"t":"start","run_id":"c7e1…","library_sha256":"9f2c…","models":["semif","kev-4b","so1"],"budget":60,"space":113,
 "base_state_chars":412}
{"t":"call","seq":1,"node":"__frame__","n_questions":14,"body":{/* exact /v1/systemone body sent */}}
{"t":"frame","seq":1,"domain":{"choice":"workflow-automation","confidence":0.55,"probabilities":{…},"trusted":true},
 "audience":{…},"profile":{"sensitive-data":V,…},"depth":V,"scope":V,"enrichment":{"applied":true,"domain":"workflow-automation"},
 "latency_ms":{"semif":930,"kev-4b":210,"so1":910},"cached":false,"errors":{}}
{"t":"control","seq":0,"categories":{"functional-core-capability":V,…},"cached":true}
{"t":"call","seq":2,"node":"__categories__","n_questions":21,"body":{…}}
{"t":"categories","seq":2,"items":{"functional-core-capability":
   {"gap":V,"lift":V,"boost":0.86,"composite":0.61,"guaranteed":true,"queue_rank":3},…},
 "flat_models":["verdict"],"latency_ms":{…},"cached":false,"errors":{}}
{"t":"call","seq":3,"node":"nonfunctional-performance","kind":"category","n_questions":4,"body":{…}}
{"t":"node","seq":3,"id":"nonfunctional-performance","kind":"category",
 "children":{"nfr-latency-target":{"rel":V,"pushed":true},…},"latency_ms":{…},"cached":false,"errors":{}}
{"t":"call","seq":9,"node":"nfr-latency-target","kind":"leaf","parent":"nonfunctional-performance","n_questions":5,"body":{…}}
{"t":"node","seq":9,"id":"nfr-latency-target","kind":"leaf","parent":"nonfunctional-performance",
 "answers":{"gate":V,"risk":V,"complexity":V,
            "phase":{"choice":"decide","confidence":0.48,"probabilities":{…},"per_model":{"semif":"decide",…}},
            "dependency":{"choice":"needs-user-decision",…}},
 "split":["risk"],            // keys whose spread >= DISAGREEMENT_THRESHOLD
 "latency_ms":{…},"cached":false,"errors":{"kev-4b":"HTTP 500: …"}}
{"t":"end","spent":60,"budget":60,"fresh_calls":41,"cached_calls":19,"reason":"budget",   // budget|exhausted|all_failed
 "frontier":[{"id":"ops-runbook-owner","kind":"leaf","priority":0.52},…]}                   // what "spend more" would reach next, in order
```

Rules:
- `score` answers are normalised to 0..1 (`score / 4`), as lab_decompose's `risk_0to1` is.
- If one model fails, that's non-fatal. It goes in `errors`, is left out of `per_model`, and the
  node is still emitted. If *every* model fails a call, that node is emitted with `"status":
  "no_answer"`, as foundry's `call_failed` handles it. Three `no_answer` nodes in a row end the
  run with `reason: "all_failed"` so it doesn't spend the budget on a dead lineup. This follows
  CLAUDE.md's warning that a server still starting gives silent 0% results.
- A `call` event is always emitted before its result. The client needs it to show the node as in
  flight.
- A **stop** (client disconnect) produces no `end` event, because the socket is gone. The client
  marks the run "stopped at call N" itself.

---

## 3. Visual design: an orbit map of the whole library

### 3.1 Why a radial map

`buildTreeView`'s `.dtree` shows *what was chosen*. This feature can show something more
interesting: **everything that could have been chosen, lighting up as the models choose.** The
library is fixed and known before any call: 6 shapes, 21 categories, 90 requirements, 113
possible calls. So the page can draw the whole candidate space at once as ghosts and fill it in
as each call returns. Three things follow from that:

- **It's honest by design.** Unvisited and low-relevance items stay visible as ghosts, so the
  viewer sees the choice being made, not a tree that looks like it was written for them.
- **Layout is fixed.** Every requirement always sits at the same angle, so two runs (two ideas, or
  one idea through different models) produce comparable "fingerprints". The stretch goals build on
  this (§5).
- **Budget becomes something you can see.** The outer ring *is* the 113-call space.

A force-directed layout was rejected: it's non-deterministic, it would put the same item in a
different place every run, and it needs a physics library the page doesn't load. An indented tree
was rejected as the main view because it already exists. It stays as the accessible Outline view
(§3.5).

### 3.2 Geometry (one inline SVG, `viewBox="0 0 1000 1000"`, center 500,500, built with the page's `S()`)

Angles come from **slots**. Each of the 90 leaves gets one slot and each category boundary gets
one empty slot as a gap: 90 + 21 = 111 slots, 360/111 ≈ 3.24° each, in library order, starting at
−90° (12 o'clock) and going clockwise. A category sits at the mean angle of its leaves. A shape
wedge spans its categories' slots. So wedge size is proportional to the number of requirements,
which avoids the usual sunburst problem of equal wedges misrepresenting how much is in each.

| Ring | Radius | Element | Encoding |
|---|---|---|---|
| Center | r 72 | `circle.dl-core` + 2–3 `tspan` lines: the first ~70 characters of the user's text, then an ellipsis | Once the frame arrives: domain and audience captions below it (`text.dl-cap`), e.g. "workflow-automation · 55%". If `trusted` is false, the caption is shown in `--text-3` with "(not trusted, margin < 0.15)". |
| Profile halo | r 92–100 | 10 arcs of 30° each, with 6° gaps | Opacity = profile mean. `<title>` = probe text plus mean and spread. |
| Shape band | r 118–146 | 6 `path.dl-wedge` annular sectors | Fill `color-mix(in srgb, var(--sK) 16%, var(--surface))` where K = shape index 1..6 (the series tokens, which app.css allows for charts). The shape name follows the arc on a `textPath` in `--text-2`. |
| Category ring | r 235 | 21 `g.dl-node.cat` | Circle radius 5 + 13·clamp01(lift.mean / 0.3). Fill `color-mix(var(--sK) {20 + 60·gap.mean}%, var(--surface))`. **Guaranteed** categories get a 2px `var(--accent)` outline. The queue rank is a small number just outside the circle. |
| Category links | | `path.dl-link` from the core edge to each category | Quadratic curve. Stroke `var(--sK)`, width 0.6 + 3·gap.mean, and 25% opacity until the category node is visited. |
| Leaf ring | r 385 | 90 `g.dl-node.leaf` | Four states (below). |
| Leaf links | | `path.dl-link` from category to leaf | Cubic curve in polar coordinates: `M P(a_cat, 247) C P(a_cat, 310) P(a_leaf, 310) P(a_leaf, 373)`. Width 0.5 + 2.5·rel.mean. **Dashed** (`stroke-dasharray: 3 2`) when rel.spread ≥ 0.3. |
| Leaf labels | r 400+ | `text.dl-lbl` only for *visited* leaves | A short label taken mechanically from the id, not written by anyone: drop the first `-` segment and turn hyphens into spaces (`nfr-latency-target` → "latency target"). Rotated to point radially, and flipped 180° on the left half so it reads left to right. 9.5px. |
| Budget gauge | r 462–476 | 113 `path.dl-tick` segments, one per possible call, clockwise from 12 o'clock | Spent fresh = `var(--accent)`. Spent from cache = `color-mix(var(--accent) 45%, var(--surface-2))`. Within budget but not yet spent = `var(--border-strong)`. Beyond budget = `var(--border)` at 50% opacity. The in-flight tick pulses. A center label below the core reads "41 of 60 calls · 113 possible". |

Leaf node states, where the circle radius is 3.5 + 5.5·rel.mean:

| State | Look |
|---|---|
| `ghost`: never pushed (parent not visited, or rel < 0.05) | 2.5px circle, no fill, `stroke: var(--border-strong)`, dotted |
| `queued`: pushed, battery not yet run | hollow circle, `stroke: var(--sK)` 1.5px |
| `visited` | filled with `heatRisk(risk.mean)`. **That function already exists** in scenarios.html and mixes `--bad` into `--surface-2`. |
| `gate` (visited, gate.mean ≥ 0.5) | an extra ring at r+3, `stroke: var(--bad)` 2px, the same meaning and colour as `.gantt .bar.gate` |
| `split` (any answer spread ≥ 0.3) | node outline dashed `var(--text-2)`, plus a `<title>` line naming which question split |
| `in-flight` | `circle.dl-scan` at r+6: `stroke: var(--accent)`, `stroke-dasharray: 4 3`, spinning with `@keyframes dl-spin` |

Every `g.dl-node` has `tabindex="0"`, `role="button"`, an `aria-label` (library text plus a
summary of its numbers) and a `<title>` for hover, following `ganttBoard`'s `<title>`
convention. Clicking it or pressing Enter selects it (§3.4).

### 3.3 Motion (CSS only, driven by events)

- Nodes are drawn at their final radius and start at `transform: scale(0)` (`transform-box:
  fill-box; transform-origin: center`), moving to `scale(1)` over 350 ms with an ease-out-back
  curve. This uses transform rather than animating `r` so it behaves the same in every engine.
- Links "draw" when a node's call resolves. On creation they get `stroke-dasharray = length`
  (from `getTotalLength()`) and `stroke-dashoffset = length`, then offset → 0 over 450 ms.
  Children are staggered by 40 ms each, so a category visibly "sprouts" its 4–5 requirements.
- On the `call` event, the target node gets `.dl-scan` and its gauge tick gets `.pulse`. On the
  result, both are removed and the node changes state.
- **Pacing:** events go into a client-side play queue. Live (uncached) events play as soon as they
  arrive. `cached: true` events are spaced 70 ms apart, so a "Spend 20 more" replay fast-forwards
  visibly instead of snapping.
- `@media (prefers-reduced-motion: reduce)`: every `.dl-*` transition and animation is off, and
  states change immediately.
- Print: the map prints in its final state, and the controls are hidden (extend the existing
  `@media print` rule).

### 3.4 Layout around the map

The view uses the `.weGrid` pattern (2fr / 1fr, one column under 860px), with a new class
`.dlGrid` so `.weGrid` isn't overloaded:

- **Left (2fr):** a toolbar with a `.segmented` view switch, [Map | Outline] in v1 and Board /
  Numbers later, then the view itself (`overflow-x:auto`; `svg.dl-map` gets `width:100%;
  max-width:880px; height:auto`), then a legend row using the existing `.legend` and `.swatch`
  conventions: "fill = risk if left undone", "red ring = could force a redesign", "dashed = models
  split (spread ≥ 0.3)", "dotted = never reached", "outer ring = calls: spent / budget / possible".
- **Right (1fr), `.dlPanel` (sticky, `top: 52px`, like `.rail`):** the selected node.
  - A breadcrumb in `.small.muted`: shape → category → requirement. A `.dbadge` marks the
    provenance: **"library text"**.
  - The item's library text in `h4` at 17px, as `workedExampleBody`'s focus heading does.
  - For a category: gap mean, lift, boost, composite, guaranteed yes/no, and per-model values in a
    compact `table.data` using `mtagShort(m)` for each row.
  - For a leaf: a 5-row table (gate, phase, risk, complexity, dependency) with one column per
    model plus a mean column. Per-model cells show the raw value. Cells whose question split get
    `class="below"`, the existing red. The header note reads "red = models split here, not
    'wrong'; there is no right answer to compare against".
  - A "Request" `details` holding the exact `/v1/systemone` body from the `call` event, in
    `pre.notes`, with a "Copy" button (`Jev.copy`). This matches the Request tab on the Conversation
    flow page.
  - With nothing selected, the panel shows the **read-out** (§3.6).

### 3.5 Outline view (v1, also the accessible and phone fallback)

This is the same data as the map, rendered as `.dtree`/`details.dgroup`/`.dnode`. Reuse
`buildTreeView`'s structure, but write a new `buildCustomOutline(state)` rather than overloading
the old one, because the old one's `nodeScore` is about grading.

- Shape → category → leaf. Only visited and queued items are shown. A last collapsed `details`
  holds "Not reached (N)" with the ghosts.
- `.ddot` shows **rel/gap mean** filled with a new `heatAcc(p)` =
  `color-mix(in srgb, var(--accent) ${Math.round(p*55)}%, var(--surface-2))`. It deliberately
  doesn't use `heat01`: that function's green/red means right/wrong, which would be a false claim
  here.
- Badges: phase (`.dbadge`), `gate` (the existing inline red dbadge style in scenarios.html's
  worked-example code), `models split` (`.dbadge` in `--text-2`).
- Under 640px the default view is Outline and the Map is one tab away, since 90 leaf dots at phone
  width are about 6px apart. The map is still usable there, just not the best first view.

### 3.6 Read-out and provenance cards (above the map once a run ends; the read-out updates live)

**"How this was built"** is a card using the same `.srcgrid` and `srcNote`-style pattern as
decompose-and-loop, with three sources:

1. **Your text.** "The only input about your idea. Nothing else on this page was written for it."
2. **The library.** `foundry/tools/world-knowledge.yaml` (sha shown). "21 requirement categories
   and 90 requirements, hand-written once, generic and reused for every idea. The models chose
   from it; they didn't add to it."
3. **Model numbers.** `probes/lab_custom_decompose.py` → `POST /v1/systemone`. "N live calls to
   M loaded models: typed yes/no, choice and 0–4 scale answers. No prose."

**Read-out** is a `card bottomline`. That class is already defined in scenarios.html. Every
sentence is a template filled from the stream: numbers plus library text, and nothing written for
the idea. Each line appears only when its data exists:

- "Reached **V of 111** library items in **S of B** calls (**F** new, **C** from cache)."
- "Strongest pull from your text, compared with a blank idea: **<category text>** (lift +0.18)."
  This is the category with the top `lift.mean`. The next two are listed in `.small`.
- "Shape with the most weight: **<shape>**." This is the shape with the highest mean `gap.mean`
  across its visited categories.
- "Highest risk if left undone: **<leaf text>**, where N of M models also said a surprise here
  could force a redesign." This is the top visited leaf by `risk.mean`. The gate count comes from
  `per_model`.
- "The models split (spread ≥ 0.3) on **K of V** items they answered." This line links to the
  Outline, filtered.
- `callout warn`, for each flagged model: "<CODE> gave all 21 categories nearly the same score
  (range 0.06), so it didn't tell them apart on this text." This goes before the numbers, not
  under them.
- `callout warn` when scope is below 0.4 (text in §1).
- The closing line in `.small.muted`: "No right answers exist for your idea, so nothing here is
  scored as right or wrong. No schedule is computed either, because no durations exist."

**Update, later session**: the "no schedule" rule above still holds in its original sense -- no
*measured* schedule is possible for arbitrary text, for the reasons stated in §1. What changed:
`demo/scenarios.html`'s `customScheduleSection()` now derives an *estimated* schedule from the
live `complexity`/`dependency` answers already described above, through one disclosed,
fixed rule (duration bands from live complexity, category order from the live priority queue,
parallel-by-default within a category). It is never presented as measured, is loudly labeled as a
stated rule wherever it appears, and reuses `demo/scenarios.html`'s Monte Carlo (schedule risk)
rendering (`mcGanttBoard`/`mcHistogram`) client-side, with no extra model calls. See BRIDGE.md for
the fuller reasoning and the user decision that authorized this.

---

## 4. Interaction model

### 4.1 Before a run (the input card, `div.card` at the top of the view)

- `textarea#dlText` with 6 rows, `maxlength=4000`, and the placeholder "Paste an idea, a pitch, a
  requirement or a problem statement". A live counter reads "412 / 4000".
- `input[type=text]#dlWho` (optional), labelled "Who is it for? (optional)", which maps to foundry's
  `customer`.
- **Examples:** a `.pillrow` of `.pill` buttons from `/api/decompose-examples`, labelled by id
  ("oncall-rotation", …). A click fills both fields. The note next to them: "Real intakes from
  foundry/ideas."
- **Models:** a `.pillrow` of `.pill` toggles, **any loaded model, local or hosted**. It's built
  from `Jev.status()` and refreshed through `Jev.onStatus`, and each pill shows `mtagShort(id)`.
  The default selection is semif, kev-4b and so1 (P1–P3, following foundry's `MODELS` and its
  report_v2 grounding), whichever of them are loaded. laya and verdict can be selected but show a
  `.dbadge` "weak on published sets", with a `title` citing report_v2 (56.9% and 46.7%). `jev`
  shows a `.dbadge` "paid" (billed per call, unlike the local models). A one-line `.legend` states
  that every selected model is asked at once per node, and when more than one is selected their
  answers are combined to drive the decomposition while each model's own answer is kept for
  comparison. If no model is loaded, the Run button is disabled and an `empty()` state says "No
  models are loaded. Start the local models with `demo/lineup.sh up`, or set `TYPESAFE_API_KEY`
  for the hosted model."
- **Budget:** the existing `.slider` pattern with a range from 3 to 113, step 1, default 113 (the
  full library) -- at local-model speeds a full run is a couple of seconds, so there's no reason to
  default to a partial one. Under it, a `.legend` reads "113 = every item in the library. One call
  asks all selected models at once." Next to it is an **estimate**. It's computed from
  measured seconds per question for each model (the p50 at size 20 from `/api/batch-perf`: semif
  67 ms, so1 66 ms, kev-4b 15 ms, laya 397 ms, verdict 258 ms per question), taking the slowest
  selected model, and assuming 14 + 21 questions for the first two calls and 5 for each later one.
  Once three calls have returned, it switches to the observed rate ("≈ 14 s left").
- **Run** (`btn primary`). The text field is saved in `localStorage` as a draft for convenience,
  wrapped in try/catch. The draft is never put in the URL hash (it may be long or private). The
  hash is just `set=custom`.

### 4.2 During a run

- Run becomes **Stop** (`btn`). Stop calls `AbortController.abort()`. The server gets a
  `BrokenPipeError` and stops making calls (§2.2), and the partial map stays with a `callout`
  reading "Stopped at call 23 of 60."
- A status line (`p.small`, `aria-live="polite"`, updated at most once a second) reads "Call 23 of
  60 · asking about **Operational: incident response** · 3 models · last call 340 ms".
- The inputs are disabled. The map and the read-out update with each event (§3.3).
- If a model fails, a small `.badge.warn` with "KEV4B: 3 errors" appears on the toolbar, with the
  messages in its `title`. The run continues.
- If the user navigates away (hashchange), `show()` has to abort the run. Add a module-level
  `let CUSTOM_ABORT = null;`, call `CUSTOM_ABORT?.abort()` at the top of `show()`, and set it in
  the custom view's run handler. The existing `TOK` guard doesn't cover an open stream.
- **409 busy** shows an `empty()` state saying "another decomposition is running" with a retry
  button.

### 4.3 After a run

- **Spend N more:** buttons for +20 and "all (113)", shown when `end.frontier` is non-empty. They
  run again with the larger budget, and the cache makes the earlier calls replay quickly (§2.2).
  The `end.frontier` list is shown as "Next in line if you spend more: …", showing the top 5 items
  by library text.
- **Download run:** saves the raw event lines as `.jsonl` via `Jev.download`. This is the same
  shape the CLI writes, so a run from the page and a run from the CLI can be compared line by line.
- Clicking or focusing a node selects it (§3.4). Pressing Esc clears the selection.
- **Change the text and run again:** the map resets to ghosts. The fixed layout makes the
  difference visible straight away.

---

## 5. v1 scope and stretch goals

### v1: one focused session, in this order

1. **`probes/lab_custom_decompose.py`** (about 280 lines): `load_library`, `skeleton`, the five
   call builders, `walk()` as a generator, lift/flat/scope, and the CLI.
2. **`probes/test_lab_custom_decompose.py`**, stdlib `unittest`, with no models: a fake `ask`
   returning fixed answers. Check that: the budget is honoured exactly (`spent == budget`, the
   control isn't counted); every call has ≤ 24 questions; the event order is `call` → result for
   every seq; the walk is deterministic (two runs give identical event lists); a failing model is
   left out of `per_model` and shows in `errors`; three `no_answer` nodes end with `all_failed`;
   state strings contain "NOT yet true" and never the solved-state phrasing without it (the
   polarity guard); and `GeneratorExit` stops further `ask` calls. Run it with
   `python3 -m unittest probes/test_lab_custom_decompose.py`.
3. **`demo/server.py`**: the three endpoints, `_stream`, the lock and the validation table.
4. **`demo/scenarios.html`**:
   - Add `["custom", "Custom decomposition", "orbit"]` to `STRUCTURES`, **as the last entry**
     (other work is adding funnel/incremental/hierarchy/time entries in parallel, so append and
     don't reorder).
   - Add `RAIL_ICONS.orbit = "M12 9.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5|M12 3v3.5|M12 17.5V21|M3 12h3.5|M17.5 12H21|M5.6 5.6l2.5 2.5|M15.9 15.9l2.5 2.5"`.
   - Add a `show()` branch:
     `mount(box, () => Promise.all([api("/api/decompose-library"), api("/api/decompose-examples")]), renderCustom)`,
     plus the `CUSTOM_ABORT` guard.
   - Add `renderCustom`, `orbitMap(lib)` (it returns `{svg, apply(event), select(id)}`),
     `buildCustomOutline`, `customReadout`, `customDetail` and `heatAcc`.
   - Add `.dl-*`, `.dlGrid` and `.dlPanel` CSS to the page `<style>` block, using tokens only.
5. **Live acceptance check** (needs the lineup up; see open question 3):
   - Run the CLI on `--intake foundry/ideas/oncall-rotation.json --models semif,kev-4b,so1 --budget 60`.
     Its **visited node ids, in order,** must equal `foundry/layered_walk.py --idea
     oncall-rotation --budget 60`'s `grinder_node` order. If they differ, treat that as a bug.
     The one expected source of difference is the added `scope` question in the frame call, and
     the backends answer each question in isolation. This parity check is the evidence that the
     port is faithful.
   - Then **read the rendered read-out sentences by hand** (foundry's lesson: "the tools ran
     live" isn't the same as "the output is coherent").
   - Then check `results`/`errors` for silent failures.

v1 does not include: Board, Numbers, the model-subset toggle, lift for children, and the side-by-side
compare.

### Stretch, in priority order

1. **Board view:** 5 phase columns (spike, decide, build, validate, launch) of visited leaves as
   small cards, sorted by `risk.mean`, with gate and split badges. It's a DOM grid only. It gives
   a readout that looks like a plan without inventing dates, and says so in its caption.
2. **Model-subset toggle:** pills above the map that recompute every `mean`/`spread` client-side
   from `per_model`, for example to drop a flagged model. The caption has to say that *which items
   were visited* came from the full set, because the walk order was fixed during the run.
3. **Numbers view:** every node × question × model as a `Jev.sortable` table with `Jev.csv` export.
4. **Compare two texts:** two runs overlaid on the same fixed layout. Leaves are drawn as
   half-discs (left half = run A, right half = run B), and categories get a lift-difference ring.
   The fixed layout is what makes this possible.
5. **Replay a saved ledger:** load a CLI or page `.jsonl` file and play it through the same
   `apply(event)` path.
6. **Control lift for children:** 21 more control calls (cached forever) so leaf relevance also
   gets a lift instead of a raw, compressed score.
7. **An escalation rung:** optionally send only the "models split" leaves to the hosted model.
   This is foundry/PLAN.md's candidate rung, and it's billed, so it needs explicit per-run consent
   in the UI. It depends on open question 2 in foundry's PLAN ("whether to spend hosted P0 on
   escalation"), so it isn't decided here.

### What v1 claims, and doesn't

v1 shows **which items of a fixed, generic requirements library the loaded models chose for your
text, in what order, how strongly, and whether they agreed.** It doesn't claim the
decomposition is correct or complete, that relevance scores are calibrated (they're compressed,
and that's why lift exists), that the leaf annotations were validated against anything (only
lab_decompose's hand-authored tree ever graded these question types, on 31 nodes), or that any
schedule follows from them.

---

## 6. Open questions for a human

None of these blocks v1. Each has a default that the build uses unless someone says otherwise.

1. **Reading foundry's library from the Scenario lab.** `foundry/README.md` says foundry is "not
   wired into the Scenario lab, and shouldn't be until this is proven out further." This design
   reads its *data* (world-knowledge.yaml and slicer.yaml), not its pipeline code. *Default:* go
   ahead, and update that README line to "its library is read, read-only, by
   `probes/lab_custom_decompose.py`." If you'd rather keep them fully separate, the fallback is a
   JSON snapshot of the library under `probes/decompose/`, which brings back the two-copies
   problem.
2. **A library for things other than software.** The 21 categories are software-requirement
   shaped. Text like "should I move cities" gets the scope warning but is still walked through
   SRS categories. A second generic library (for example project/plan or
   decision-analysis categories) would be new hand-authored generic content, which the one rule
   allows but someone has to decide to write and review. *Default:* v1 ships software-only, with
   the scope warning.
3. **Nothing local is loaded right now.** `/api/status` at the time of writing shows every local
   backend "Not loaded" (only the hosted `jev` is up). The live acceptance check in §5 needs the
   lineup started with `demo/lineup.sh up`, kev-4b first. That's the user's call per BRIDGE.md.
   Everything before step 5 can be built and unit-tested without models. Don't restart
   `demo/server.py` while an experiment is running through it.
4. **Dropping the leaf `atomic` check here, while foundry still uses it.** foundry/PLAN.md lists
   "drop the leaf atomic gate" as pending kev-4b's data, and the evidence so far (+0.006
   separation) points to dropping it. *Default:* this feature drops it now, and says so on the
   page (in the "How this was built" card: "requirements are atomic by how the library was written;
   the models' atomic check was measured at noise level and isn't used"). If kev-4b's data later
   says otherwise, putting it back means adding one question to the leaf battery.
