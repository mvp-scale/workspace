# Code semantic language

Two separate processes, not one. The earlier tests in `_will_this_work.md` conflated them by
giving Jev the actual code every time — that only tests the first process below, never the
second, which is the one that actually matters for an agent skimming a codebase.

## Process 1 — Production (Jev does real analysis, hierarchically)

Jev looks at real code and scores it — but at the level of individual constructors, methods, and
signatures inside a file, not the file as one blob. Each unit gets its own small fingerprint (the
colored-circle signature validated earlier: security / quality / performance / testing /
architecture, each a single-glyph severity level).

The file-level comment block at the top is **not** a fresh Jev call over the whole file — it's a
rollup, aggregated from the method-level fingerprints already computed below it. Cheaper, and it
means the top-of-file signature is always a real summary of real per-method analysis, not a
separate, possibly-inconsistent judgment.

### Change detection and incremental rescoring

- **The agent detects change, not Jev.** When a method gets edited (visible from a diff), the
  agent marks that method's fingerprint stale — "zeroed out." The agent cannot itself write a new
  score; it can only flag that one is needed.
- **Only the changed unit gets rescored.** Jev re-runs on that one method, not the whole file.
  Every other method's fingerprint stays valid and cached.
- **The rollup regenerates from the (mostly cached, one freshly-scored) set of method fingerprints.**
- This makes quality scoring on-demand and incremental instead of wastefully re-running across an
  entire file (or codebase) on every change.

### What goes in (Process 1)

- Real source: each constructor/method/signature body, individually, when it's (re)scored.
- A "stale" flag per unit, set by the agent's own diff/change detection — not by Jev.

### What comes out (Process 1)

- One small fingerprint per unit (constructor/method/signature).
- One rolled-up fingerprint per file, aggregated from its units' fingerprints.

## Process 2 — Consumption (the actual pre-recon scan — no code involved)

This is the one I tested wrong. An agent (me, reading a file) sees only:
- the file name
- the already-produced comment block (file-level rollup fingerprint + per-engine timestamps)

**No source code at all** — that's the entire point. From just that, the agent should get a real,
useful sense of the file's depth/standing across the dimensions reported, without opening the file
further, without looking anything up, and without understanding the underlying quality standards
itself.

### What goes in (Process 2)

- Filename (and maybe path, for context — e.g. `auth/session.py` implies higher sensitivity than
  `scripts/one_off_report.py`)
- The comment block itself: the rolled-up fingerprint + timestamps, nothing else

### What comes out (Process 2)

- A read on how to treat the file — sensitive vs. not, safe to touch vs. needs care, trustworthy
  vs. needs a real look — derived purely from the fingerprint, with zero code access.

### Two ways this consumption actually gets used

1. **Jev-mediated**: feed the fingerprint (not the code) back to Jev and ask it to make a decision
   — e.g. "given this fingerprint, should this file block a merge?"
2. **Agent-baked-in**: the interpretation is just a fixed rule inside the agent's own instructions,
   no model call needed at all — e.g. "if the security position is 🔴, treat this file as
   sensitive and ask before editing it."

Both are legitimate and probably coexist: baked-in rules for cheap, common cases; a Jev call for
anything ambiguous enough to need real judgment on the fingerprint itself.

## What still needs testing

Process 1 (hierarchical per-method scoring + rollup + incremental rescoring) hasn't been tested at
all yet — everything tonight scored one function as a whole, not a hierarchy of units aggregating
upward.

Process 2 (fingerprint-only consumption, zero code) is the one that actually needs validating next:
does a synthetic fingerprint + filename alone produce a *good*, non-arbitrary "how do I treat this
file" read — from Jev, and/or does it stand on its own as a baked-in agent rule with no model call
required at all.

---

## ⚠️ Test 1 is INVALID as a test of semantic compaction — see Test 2 below

The `state` sent below spells out `security=red, quality=green, ...` in literal English words.
That means the model never had to decode a compact glyph at all — it just read plain text, which
tells us nothing about whether the compaction itself (the actual colored-circle emoji, with no
spelled-out translation) carries meaning on its own. Test 1's numbers are real, but they don't
measure what this file exists to measure. Kept below for the record; Test 2 is the corrected
version using the actual glyphs.

## Test 1 — filename + fingerprint only, no code anywhere, go/no-go judgment

Three files, each shown to the model as only a filename and its codehealth block. No source code
is present in the request at all.

### Exact request sent (identical to all three targets; only the URL and, for hosted jev, the
`Authorization: Bearer $TYPESAFE_API_KEY` header differ)

`state` (shown with real line breaks for readability — the actual bytes on the wire used proper
JSON `\n` escaping, this is not literally valid JSON as written):

```
Three files, each shown only as a filename plus its codehealth comment block -- no source
code is available or shown. Each comment block reports five dimensions in this fixed order:
security, quality, performance, testing, architecture. Each dimension is one colored circle:
red=critical, orange=poor, yellow=fair, green=good, blue=excellent.

File_1:
  path: auth/security_gateway.py
  codehealth: security=red, quality=green, performance=green, testing=green, architecture=green
  last verified: 2026-09-27T02:58:11Z

File_2:
  path: scripts/generate_monthly_report.py
  codehealth: security=red, quality=green, performance=green, testing=green, architecture=green
  last verified: 2026-09-27T02:58:11Z

File_3:
  path: auth/security_gateway.py
  codehealth: security=green, quality=green, performance=green, testing=red, architecture=green
  last verified: 2026-09-27T02:58:11Z
```

`questions` (9 total: 3 files × 3 questions each — `concern` is `noul`, `primary` and `decision`
are `choice`):

```
concern_1:
  type: noul
  instructions: "Based only on its filename and codehealth block, is there reason to be concerned about File_1?"

primary_1:
  type: choice
  instructions: "Which dimension is the primary area of concern for File_1, if any?"
  criteria: [security, quality, performance, testing, architecture, none]

decision_1:
  type: choice
  instructions: "Should changes to File_1 proceed without further review (go), or should work pause for review first (no-go)?"
  criteria: [go, no-go]

concern_2:
  type: noul
  instructions: "Based only on its filename and codehealth block, is there reason to be concerned about File_2?"

primary_2:
  type: choice
  instructions: "Which dimension is the primary area of concern for File_2, if any?"
  criteria: [security, quality, performance, testing, architecture, none]

decision_2:
  type: choice
  instructions: "Should changes to File_2 proceed without further review (go), or should work pause for review first (no-go)?"
  criteria: [go, no-go]

concern_3:
  type: noul
  instructions: "Based only on its filename and codehealth block, is there reason to be concerned about File_3?"

primary_3:
  type: choice
  instructions: "Which dimension is the primary area of concern for File_3, if any?"
  criteria: [security, quality, performance, testing, architecture, none]

decision_3:
  type: choice
  instructions: "Should changes to File_3 proceed without further review (go), or should work pause for review first (no-go)?"
  criteria: [go, no-go]
```

The literal JSON body is `{"state": <the text block above>, "model": "jev-latest", "questions": <the 9 questions above, as one object keyed by id>}` — every `questions` entry follows the same shape as the wire format used all night: `{"type": ..., "instructions": ..., "criteria": {...}}` for `choice`, `{"type": "noul", "instructions": ...}` alone for `noul`.

### Full results — first run (concern + primary + decision, confidence only)

| | File_1 (security_gateway, security=🔴) | File_2 (monthly_report, security=🔴) | File_3 (security_gateway, testing=🔴) |
|---|---|---|---|
| **kev-4b** concern / primary / decision | 0.92 / security (0.99) / **go (0.58)** | 0.94 / security (0.99) / no-go (0.02) | 0.77 / testing (1.0) / no-go (0.32) |
| **semif** concern / primary / decision | 0.99 / security (0.998) / no-go (0.36) | 0.97 / security (0.986) / no-go (0.19) | 0.84 / testing (0.805) / no-go (0.36) |
| **hosted jev** concern / primary / decision | 0.94 / security (1.0) / no-go (1.0) | 0.83 / security (1.0) / no-go (1.0) | 0.88 / testing (1.0) / no-go (0.97) |

### Full results — second run, decision questions only, raw probabilities (verifying the odd
confidence numbers above weren't a parsing artifact)

Same `state`, only the three `decision_*` questions re-sent (identical `instructions`/`criteria`
as above), full raw response:

**kev-4b**
```
decision_1: choice=go     probabilities={go: 0.80, no-go: 0.20}
decision_2: choice=no-go  probabilities={go: 0.49, no-go: 0.51}
decision_3: choice=no-go  probabilities={go: 0.34, no-go: 0.66}
```

**semif**
```
decision_1: choice=no-go  probabilities={go: 0.32, no-go: 0.68}
decision_2: choice=no-go  probabilities={go: 0.41, no-go: 0.59}
decision_3: choice=no-go  probabilities={go: 0.32, no-go: 0.68}
```

**hosted jev**
```
decision_1: choice=no-go  probabilities={go: 0.00, no-go: 1.00}
decision_2: choice=no-go  probabilities={go: 0.00, no-go: 1.00}
decision_3: choice=no-go  probabilities={go: 0.01, no-go: 0.99}
```

### Findings

- **Dimension identification (`primary_*`) is perfect across all three models, every case** —
  security→security, security→security, testing→testing, all at 0.8-1.0 confidence. Filename +
  fingerprint alone, zero code, correctly localizes which dimension failed every single time.
- **Go/no-go judgment is not equally reliable.** kev-4b answered **"go" at 80% probability** for
  File_1 — a file literally named `security_gateway.py`, flagged with a critical security failure
  and nothing else wrong. On the low-stakes File_2 with the *identical* security flag, kev-4b was
  more cautious (49/51, essentially a coin flip) — its caution moved in the wrong direction
  relative to what the filename implies. semif and hosted jev both stayed correctly conservative
  (no-go) on every case; hosted jev was fully certain (1.00/1.00/0.99) every time.
- This was confirmed with two separate requests (first pass showed the same "go" pick for kev-4b
  at lower reported confidence; the raw-probability re-run shows it more strongly, 0.80) — not a
  one-off fluke or a parsing bug in how confidence was displayed.

---

## Test 2 — the corrected version: actual colored-circle glyphs, no spelled-out words at all

Same 3 files, same 9 questions, same everything — the only change is `state` now contains the
real glyphs (🔴🟢) instead of the words `red`/`green`. The only text given alongside the glyphs is
the *positional* legend (which of the 5 slots is which dimension) — that's structural information
about ordering, not a definition of what a color means. No color is ever named in words anywhere
in this request.

### Exact request sent (identical to all three targets; only URL/auth header differ)

`state` (verbatim, real glyphs):

```
File_1: auth/security_gateway.py
# codehealth: 🔴🟢🟢🟢🟢  2026-09-27T02:58:11Z
# (fixed dimension order: security, quality, performance, testing, architecture)

File_2: scripts/generate_monthly_report.py
# codehealth: 🔴🟢🟢🟢🟢  2026-09-27T02:58:11Z
# (fixed dimension order: security, quality, performance, testing, architecture)

File_3: auth/security_gateway.py
# codehealth: 🟢🟢🟢🔴🟢  2026-09-27T02:58:11Z
# (fixed dimension order: security, quality, performance, testing, architecture)
```

`questions` — identical in shape and wording to Test 1 (same 9 questions, same ids, same
instructions text, same criteria lists); not repeated here since nothing about them changed.

### Full results, with complete probability distributions

**kev-4b**
```
File_1: concern=0.44  primary=none   {security:0.04, quality:0.09, performance:0.12, testing:0.10, architecture:0.16, none:0.50}
        decision=go   {go:0.52, no-go:0.48}
File_2: concern=0.13  primary=none   {security:0.15, quality:0.10, performance:0.07, testing:0.12, architecture:0.14, none:0.43}
        decision=go   {go:0.88, no-go:0.12}
File_3: concern=0.64  primary=none   {security:0.02, quality:0.12, performance:0.11, testing:0.11, architecture:0.12, none:0.51}
        decision=no-go {go:0.50, no-go:0.50}
```

**semif**
```
File_1: concern=0.35  primary=security {security:0.54, quality:0.20, performance:0.04, testing:0.02, architecture:0.15, none:0.04}
        decision=go   {go:0.73, no-go:0.27}
File_2: concern=0.41  primary=security {security:0.57, quality:0.27, performance:0.02, testing:0.01, architecture:0.06, none:0.07}
        decision=go   {go:0.78, no-go:0.22}
File_3: concern=0.59  primary=testing  {security:0.15, quality:0.09, performance:0.06, testing:0.53, architecture:0.15, none:0.01}
        decision=go   {go:0.56, no-go:0.44}
```

**hosted jev**
```
File_1: concern=0.72  primary=security {security:0.97, testing:0.0, architecture:0.0, performance:0.0, quality:0.0, none:0.03}
        decision=no-go {go:0.18, no-go:0.82}
File_2: concern=0.44  primary=security {security:0.78, none:0.21, performance:0.0, architecture:0.0, quality:0.0, testing:0.01}
        decision=no-go {go:0.31, no-go:0.69}
File_3: concern=0.69  primary=testing  {testing:1.0, all others:0.0}
        decision=no-go {go:0.09, no-go:0.91}
```

### Findings — this is the real result

| | kev-4b | semif | hosted jev |
|---|---|---|---|
| Correctly localizes which position is red | **Fails on all 3** (`primary=none` every time — the "none" bucket won by default) | Correct on all 3 (security/security/testing), moderate confidence (0.53-0.57) | Correct on all 3, strong confidence (0.78-1.0) |
| Go/no-go on File_1 (security gateway, security critical) | go (52/48 — coin flip) | **go (0.73)** — wrong | no-go (0.82) — correct |
| Go/no-go on File_2 (low-stakes, same flag) | go (0.88) — wrong | go (0.78) — wrong | no-go (0.69) — correct |
| Go/no-go on File_3 (security gateway, testing critical) | no-go (50/50 — coin flip) | go (0.56) — wrong | no-go (0.91) — correct |

**This is the finding that actually matters, and it's much starker than Test 1's (invalid)
result:**

- **kev-4b collapses almost completely** once forced to read real glyphs with no spelled-out
  translation — it can't even localize which position is red anymore (`none` wins every single
  time), and its go/no-go answers become near coin-flips.
- **semif still localizes the correct dimension** (security/security/testing, matching ground
  truth every time) — the position-reading skill survives — **but its safety judgment inverts**:
  it says "go" on all three files, including the security-gateway-with-critical-security-flaw
  case, where Test 1 (with spelled-out words) had it correctly saying "no-go." The compact
  encoding didn't just make it less confident — it flipped the actual decision to the unsafe one.
- **hosted jev is the only model that holds up under the real, compact encoding** — correct
  dimension localization at high confidence, and correct, appropriately cautious no-go on every
  case, closely matching its Test 1 behavior despite the much sparser input.
- **Bottom line for the codehealth-block idea as actually specified**: the compact glyph-only
  annotation is not equally readable across models. It works — genuinely well — for hosted jev.
  For the two open-source models, going from spelled-out words to real compact glyphs cost real,
  measurable capability, and in semif's case specifically flipped a safety-relevant decision from
  correct to incorrect. If this system is meant to gate agent behavior (go/no-go), the choice of
  which model reads the compact annotation is not a minor implementation detail — it changes the
  actual answer.
---

## Test 3 — letter-grade and number-grade encodings (same scenario as Test 2)

Same 3 files, same 9 questions as Test 2, only the encoding changes: letters (A-F) in one
run, plain numbers (1-5) in the other, instead of colored-circle emoji.

### Letter-grade run — exact `state` sent

```
File_1: auth/security_gateway.py
# codehealth: F A A A A  2026-09-27T02:58:11Z
# (fixed dimension order: security, quality, performance, testing, architecture)
# (grade scale: F=critical, D=poor, C=fair, B=good, A=excellent)

File_2: scripts/generate_monthly_report.py
# codehealth: F A A A A  2026-09-27T02:58:11Z
# (fixed dimension order: security, quality, performance, testing, architecture)
# (grade scale: F=critical, D=poor, C=fair, B=good, A=excellent)

File_3: auth/security_gateway.py
# codehealth: A A A F A  2026-09-27T02:58:11Z
# (fixed dimension order: security, quality, performance, testing, architecture)
# (grade scale: F=critical, D=poor, C=fair, B=good, A=excellent)
```

### Number-grade run — exact `state` sent

```
File_1: auth/security_gateway.py
# codehealth: 1 5 5 5 5  2026-09-27T02:58:11Z
# (fixed dimension order: security, quality, performance, testing, architecture)
# (number scale: 1=critical, 2=poor, 3=fair, 4=good, 5=excellent)

File_2: scripts/generate_monthly_report.py
# codehealth: 1 5 5 5 5  2026-09-27T02:58:11Z
# (fixed dimension order: security, quality, performance, testing, architecture)
# (number scale: 1=critical, 2=poor, 3=fair, 4=good, 5=excellent)

File_3: auth/security_gateway.py
# codehealth: 5 5 5 1 5  2026-09-27T02:58:11Z
# (fixed dimension order: security, quality, performance, testing, architecture)
# (number scale: 1=critical, 2=poor, 3=fair, 4=good, 5=excellent)
```

### The 9 questions sent (identical wording/shape for both runs)

```
concern_1:
  type: noul
  instructions: "Based only on its filename and codehealth block, is there reason to be concerned about File_1?"

primary_1:
  type: choice
  instructions: "Which dimension is the primary area of concern for File_1, if any?"
  criteria: ['security', 'quality', 'performance', 'testing', 'architecture', 'none']

decision_1:
  type: choice
  instructions: "Should changes to File_1 proceed without further review (go), or should work pause for review first (no-go)?"
  criteria: [go, no-go]

concern_2:
  type: noul
  instructions: "Based only on its filename and codehealth block, is there reason to be concerned about File_2?"

primary_2:
  type: choice
  instructions: "Which dimension is the primary area of concern for File_2, if any?"
  criteria: ['security', 'quality', 'performance', 'testing', 'architecture', 'none']

decision_2:
  type: choice
  instructions: "Should changes to File_2 proceed without further review (go), or should work pause for review first (no-go)?"
  criteria: [go, no-go]

concern_3:
  type: noul
  instructions: "Based only on its filename and codehealth block, is there reason to be concerned about File_3?"

primary_3:
  type: choice
  instructions: "Which dimension is the primary area of concern for File_3, if any?"
  criteria: ['security', 'quality', 'performance', 'testing', 'architecture', 'none']

decision_3:
  type: choice
  instructions: "Should changes to File_3 proceed without further review (go), or should work pause for review first (no-go)?"
  criteria: [go, no-go]

```

### Full results

**Letter-grade run:**

| | File_1 concern/primary/decision | File_2 | File_3 |
|---|---|---|---|
| kev-4b | 0.53 / none (0.37) / **no-go** {go:0.39,no-go:0.61} | 0.38 / none (0.31) / go {go:0.58,no-go:0.42} | 0.49 / none (0.38) / **no-go** {go:0.44,no-go:0.56} |
| semif | 0.59 / security (0.15) / **no-go** {go:0.3775,no-go:0.6225} | 0.53 / security (0.50) / go {go:0.6792,no-go:0.3208} | 0.59 / testing (0.28) / **no-go** {go:0.3775,no-go:0.6225} |
| hosted jev | 0.91 / security (0.99) / **no-go** {go:0.0,no-go:1.0} | 0.65 / security (0.92) / **no-go** {go:0.03,no-go:0.97} | 0.76 / testing (1.00) / **no-go** {go:0.04,no-go:0.96} |

**Number-grade run:**

| | File_1 concern/primary/decision | File_2 | File_3 |
|---|---|---|---|
| kev-4b | 0.77 / testing (0.42) / **no-go** {go:0.34,no-go:0.66} | 0.05 / none (0.63) / go {go:0.9,no-go:0.1} | 0.91 / testing (0.92) / no-go {go:0.44,no-go:0.56} |
| semif | 0.53 / testing (0.24) / go {go:0.5622,no-go:0.4378} | 0.38 / none (0.32) / go {go:0.7773,no-go:0.2227} | 0.78 / testing (0.92) / **no-go** {go:0.3486,no-go:0.6514} |
| hosted jev | 0.88 / security (0.98) / **no-go** {go:0.02,no-go:0.98} | 0.51 / security (0.86) / **no-go** {go:0.12,no-go:0.88} | 0.77 / testing (1.00) / **no-go** {go:0.08,no-go:0.92} |

(bold = correct per ground truth: File_1/File_2 flagged dimension is security, File_3 is testing; File_1 and File_3 should be no-go given a critical flag is present; File_2's correct call is debatable/open since it's a low-stakes file with the same critical security flag -- treated here as should-still-be-no-go since the flag itself is critical regardless of file.)


---

## Test 4 - 15 supportive noul probes per file + crosscutting-concern pick + decision

Same 3 files as Test 3 (letter grades). Instead of one `primary` choice question per file,
this asks 3 orthogonal `noul` probes per dimension (direct / contextual / inverse) x 5
dimensions = 15 `noul` questions per file, plus one `crosscutting` choice question and one
`decision` choice question -- 17 questions per file, 51 total in one request.

### Exact `state` sent (all three files, identical across all three model targets)

```
File_1: auth/security_gateway.py
# codehealth: F A A A A  2026-09-27T02:58:11Z
# (fixed dimension order: security, quality, performance, testing, architecture)
# (grade scale: F=critical, D=poor, C=fair, B=good, A=excellent)

File_2: scripts/generate_monthly_report.py
# codehealth: F A A A A  2026-09-27T02:58:11Z
# (fixed dimension order: security, quality, performance, testing, architecture)
# (grade scale: F=critical, D=poor, C=fair, B=good, A=excellent)

File_3: auth/security_gateway.py
# codehealth: A A A F A  2026-09-27T02:58:11Z
# (fixed dimension order: security, quality, performance, testing, architecture)
# (grade scale: F=critical, D=poor, C=fair, B=good, A=excellent)
```

### Every one of the 51 questions sent, exactly as sent, no abbreviation

```
# --- File_1 (auth/security_gateway.py) ---
direct_security_1:
  type: noul
  instructions: "Does the security position in the codehealth block for File_1 show a failing (F) grade?"

context_security_1:
  type: noul
  instructions: "Given the name and path of File_1, would a failing security grade be especially concerning here?"

inverse_security_1:
  type: noul
  instructions: "Is it safe to assume there is no security concern for File_1?"

direct_quality_1:
  type: noul
  instructions: "Does the quality position in the codehealth block for File_1 show a failing (F) grade?"

context_quality_1:
  type: noul
  instructions: "Given the name and path of File_1, would a failing quality grade be especially concerning here?"

inverse_quality_1:
  type: noul
  instructions: "Is it safe to assume there is no quality concern for File_1?"

direct_performance_1:
  type: noul
  instructions: "Does the performance position in the codehealth block for File_1 show a failing (F) grade?"

context_performance_1:
  type: noul
  instructions: "Given the name and path of File_1, would a failing performance grade be especially concerning here?"

inverse_performance_1:
  type: noul
  instructions: "Is it safe to assume there is no performance concern for File_1?"

direct_testing_1:
  type: noul
  instructions: "Does the testing position in the codehealth block for File_1 show a failing (F) grade?"

context_testing_1:
  type: noul
  instructions: "Given the name and path of File_1, would a failing testing grade be especially concerning here?"

inverse_testing_1:
  type: noul
  instructions: "Is it safe to assume there is no testing concern for File_1?"

direct_architecture_1:
  type: noul
  instructions: "Does the architecture position in the codehealth block for File_1 show a failing (F) grade?"

context_architecture_1:
  type: noul
  instructions: "Given the name and path of File_1, would a failing architecture grade be especially concerning here?"

inverse_architecture_1:
  type: noul
  instructions: "Is it safe to assume there is no architecture concern for File_1?"

crosscutting_1:
  type: choice
  instructions: "Which dimension represents the primary cross-cutting concern for File_1, if any?"
  criteria: [security, quality, performance, testing, architecture, "no major concerns"]

decision_1:
  type: choice
  instructions: "Should changes to File_1 proceed without further review (go), or should work pause for review first (no-go)?"
  criteria: [go, no-go]

# --- File_2 (scripts/generate_monthly_report.py) ---
direct_security_2:
  type: noul
  instructions: "Does the security position in the codehealth block for File_2 show a failing (F) grade?"

context_security_2:
  type: noul
  instructions: "Given the name and path of File_2, would a failing security grade be especially concerning here?"

inverse_security_2:
  type: noul
  instructions: "Is it safe to assume there is no security concern for File_2?"

direct_quality_2:
  type: noul
  instructions: "Does the quality position in the codehealth block for File_2 show a failing (F) grade?"

context_quality_2:
  type: noul
  instructions: "Given the name and path of File_2, would a failing quality grade be especially concerning here?"

inverse_quality_2:
  type: noul
  instructions: "Is it safe to assume there is no quality concern for File_2?"

direct_performance_2:
  type: noul
  instructions: "Does the performance position in the codehealth block for File_2 show a failing (F) grade?"

context_performance_2:
  type: noul
  instructions: "Given the name and path of File_2, would a failing performance grade be especially concerning here?"

inverse_performance_2:
  type: noul
  instructions: "Is it safe to assume there is no performance concern for File_2?"

direct_testing_2:
  type: noul
  instructions: "Does the testing position in the codehealth block for File_2 show a failing (F) grade?"

context_testing_2:
  type: noul
  instructions: "Given the name and path of File_2, would a failing testing grade be especially concerning here?"

inverse_testing_2:
  type: noul
  instructions: "Is it safe to assume there is no testing concern for File_2?"

direct_architecture_2:
  type: noul
  instructions: "Does the architecture position in the codehealth block for File_2 show a failing (F) grade?"

context_architecture_2:
  type: noul
  instructions: "Given the name and path of File_2, would a failing architecture grade be especially concerning here?"

inverse_architecture_2:
  type: noul
  instructions: "Is it safe to assume there is no architecture concern for File_2?"

crosscutting_2:
  type: choice
  instructions: "Which dimension represents the primary cross-cutting concern for File_2, if any?"
  criteria: [security, quality, performance, testing, architecture, "no major concerns"]

decision_2:
  type: choice
  instructions: "Should changes to File_2 proceed without further review (go), or should work pause for review first (no-go)?"
  criteria: [go, no-go]

# --- File_3 (auth/security_gateway.py) ---
direct_security_3:
  type: noul
  instructions: "Does the security position in the codehealth block for File_3 show a failing (F) grade?"

context_security_3:
  type: noul
  instructions: "Given the name and path of File_3, would a failing security grade be especially concerning here?"

inverse_security_3:
  type: noul
  instructions: "Is it safe to assume there is no security concern for File_3?"

direct_quality_3:
  type: noul
  instructions: "Does the quality position in the codehealth block for File_3 show a failing (F) grade?"

context_quality_3:
  type: noul
  instructions: "Given the name and path of File_3, would a failing quality grade be especially concerning here?"

inverse_quality_3:
  type: noul
  instructions: "Is it safe to assume there is no quality concern for File_3?"

direct_performance_3:
  type: noul
  instructions: "Does the performance position in the codehealth block for File_3 show a failing (F) grade?"

context_performance_3:
  type: noul
  instructions: "Given the name and path of File_3, would a failing performance grade be especially concerning here?"

inverse_performance_3:
  type: noul
  instructions: "Is it safe to assume there is no performance concern for File_3?"

direct_testing_3:
  type: noul
  instructions: "Does the testing position in the codehealth block for File_3 show a failing (F) grade?"

context_testing_3:
  type: noul
  instructions: "Given the name and path of File_3, would a failing testing grade be especially concerning here?"

inverse_testing_3:
  type: noul
  instructions: "Is it safe to assume there is no testing concern for File_3?"

direct_architecture_3:
  type: noul
  instructions: "Does the architecture position in the codehealth block for File_3 show a failing (F) grade?"

context_architecture_3:
  type: noul
  instructions: "Given the name and path of File_3, would a failing architecture grade be especially concerning here?"

inverse_architecture_3:
  type: noul
  instructions: "Is it safe to assume there is no architecture concern for File_3?"

crosscutting_3:
  type: choice
  instructions: "Which dimension represents the primary cross-cutting concern for File_3, if any?"
  criteria: [security, quality, performance, testing, architecture, "no major concerns"]

decision_3:
  type: choice
  instructions: "Should changes to File_3 proceed without further review (go), or should work pause for review first (no-go)?"
  criteria: [go, no-go]

```


### Full raw results, every value

**kev-4b** (input_tokens=1647)

```
File_1 (flagged dimension per the mask: security):
  security     direct=0.98  context=0.96  inverse=0.14
  quality      direct=0.51  context=0.59  inverse=0.78
  performance  direct=0.34  context=0.42  inverse=0.74
  testing      direct=0.57  context=0.60  inverse=0.66
  architecture direct=0.42  context=0.56  inverse=0.97
  crosscutting = security (confidence 0.82)
  decision = no-go  probabilities={'go': 0.39, 'no-go': 0.61}

File_2 (flagged dimension per the mask: security):
  security     direct=0.93  context=0.31  inverse=0.50
  quality      direct=0.25  context=0.20  inverse=0.97
  performance  direct=0.05  context=0.17  inverse=0.88
  testing      direct=0.08  context=0.24  inverse=0.76
  architecture direct=0.04  context=0.19  inverse=0.97
  crosscutting = no major concerns (confidence 0.28)
  decision = go  probabilities={'go': 0.58, 'no-go': 0.42}

File_3 (flagged dimension per the mask: testing):
  security     direct=0.21  context=0.95  inverse=0.12
  quality      direct=0.50  context=0.71  inverse=0.84
  performance  direct=0.40  context=0.57  inverse=0.85
  testing      direct=0.94  context=0.71  inverse=0.76
  architecture direct=0.58  context=0.66  inverse=0.97
  crosscutting = security (confidence 0.35)
  decision = no-go  probabilities={'go': 0.43, 'no-go': 0.57}

```

**semif** (input_tokens=19281)

```
File_1 (flagged dimension per the mask: security):
  security     direct=0.92  context=0.95  inverse=0.05
  quality      direct=0.65  context=0.71  inverse=0.08
  performance  direct=0.53  context=0.62  inverse=0.18
  testing      direct=0.53  context=0.68  inverse=0.29
  architecture direct=0.50  context=0.71  inverse=0.22
  crosscutting = security (confidence 0.66)
  decision = no-go  probabilities={'go': 0.3775, 'no-go': 0.6225}

File_2 (flagged dimension per the mask: security):
  security     direct=0.56  context=0.68  inverse=0.59
  quality      direct=0.44  context=0.62  inverse=0.59
  performance  direct=0.50  context=0.59  inverse=0.53
  testing      direct=0.50  context=0.59  inverse=0.62
  architecture direct=0.41  context=0.56  inverse=0.71
  crosscutting = security (confidence 0.66)
  decision = go  probabilities={'go': 0.6792, 'no-go': 0.3208}

File_3 (flagged dimension per the mask: testing):
  security     direct=0.53  context=0.95  inverse=0.03
  quality      direct=0.47  context=0.62  inverse=0.07
  performance  direct=0.44  context=0.56  inverse=0.25
  testing      direct=0.59  context=0.68  inverse=0.27
  architecture direct=0.53  context=0.75  inverse=0.25
  crosscutting = architecture (confidence 0.2)
  decision = no-go  probabilities={'go': 0.3775, 'no-go': 0.6225}

```

**hosted-jev** (input_tokens=2009)

```
File_1 (flagged dimension per the mask: security):
  security     direct=0.99  context=0.95  inverse=0.02
  quality      direct=0.04  context=0.66  inverse=0.51
  performance  direct=0.05  context=0.57  inverse=0.50
  testing      direct=0.08  context=0.64  inverse=0.13
  architecture direct=0.03  context=0.50  inverse=0.70
  crosscutting = security (confidence 0.99)
  decision = no-go  probabilities={'go': 0.0, 'no-go': 1.0}

File_2 (flagged dimension per the mask: security):
  security     direct=0.98  context=0.33  inverse=0.07
  quality      direct=0.02  context=0.40  inverse=0.51
  performance  direct=0.03  context=0.32  inverse=0.53
  testing      direct=0.06  context=0.44  inverse=0.23
  architecture direct=0.03  context=0.29  inverse=0.71
  crosscutting = security (confidence 0.84)
  decision = no-go  probabilities={'go': 0.02, 'no-go': 0.98}

File_3 (flagged dimension per the mask: testing):
  security     direct=0.02  context=0.85  inverse=0.41
  quality      direct=0.02  context=0.55  inverse=0.67
  performance  direct=0.04  context=0.45  inverse=0.66
  testing      direct=0.98  context=0.78  inverse=0.03
  architecture direct=0.02  context=0.42  inverse=0.72
  crosscutting = testing (confidence 0.97)
  decision = no-go  probabilities={'go': 0.04, 'no-go': 0.96}

```

### Internal-consistency check (|direct - (1-inverse)|; >0.30 flagged) -- this is the
depth the layered design was built to surface, not visible from any single question

**kev-4b**

| File | Dimension | direct | inverse | 1-inverse | gap | flagged dim? | inconsistent? |
|---|---|---|---|---|---|---|---|
| File_1 | security | 0.98 | 0.14 | 0.86 | 0.12 | **yes** | consistent |
| File_1 | quality | 0.51 | 0.78 | 0.22 | 0.29 | no | consistent |
| File_1 | performance | 0.34 | 0.74 | 0.26 | 0.08 | no | consistent |
| File_1 | testing | 0.57 | 0.66 | 0.34 | 0.23 | no | consistent |
| File_1 | architecture | 0.42 | 0.97 | 0.03 | 0.39 | no | **INCONSISTENT** |
| File_2 | security | 0.93 | 0.50 | 0.50 | 0.43 | **yes** | **INCONSISTENT** |
| File_2 | quality | 0.25 | 0.97 | 0.03 | 0.22 | no | consistent |
| File_2 | performance | 0.05 | 0.88 | 0.12 | 0.07 | no | consistent |
| File_2 | testing | 0.08 | 0.76 | 0.24 | 0.16 | no | consistent |
| File_2 | architecture | 0.04 | 0.97 | 0.03 | 0.01 | no | consistent |
| File_3 | security | 0.21 | 0.12 | 0.88 | 0.67 | no | **INCONSISTENT** |
| File_3 | quality | 0.50 | 0.84 | 0.16 | 0.34 | no | **INCONSISTENT** |
| File_3 | performance | 0.40 | 0.85 | 0.15 | 0.25 | no | consistent |
| File_3 | testing | 0.94 | 0.76 | 0.24 | 0.70 | **yes** | **INCONSISTENT** |
| File_3 | architecture | 0.58 | 0.97 | 0.03 | 0.55 | no | **INCONSISTENT** |

**semif**

| File | Dimension | direct | inverse | 1-inverse | gap | flagged dim? | inconsistent? |
|---|---|---|---|---|---|---|---|
| File_1 | security | 0.92 | 0.05 | 0.95 | 0.03 | **yes** | consistent |
| File_1 | quality | 0.65 | 0.08 | 0.92 | 0.27 | no | consistent |
| File_1 | performance | 0.53 | 0.18 | 0.82 | 0.29 | no | consistent |
| File_1 | testing | 0.53 | 0.29 | 0.71 | 0.18 | no | consistent |
| File_1 | architecture | 0.50 | 0.22 | 0.78 | 0.28 | no | consistent |
| File_2 | security | 0.56 | 0.59 | 0.41 | 0.15 | **yes** | consistent |
| File_2 | quality | 0.44 | 0.59 | 0.41 | 0.03 | no | consistent |
| File_2 | performance | 0.50 | 0.53 | 0.47 | 0.03 | no | consistent |
| File_2 | testing | 0.50 | 0.62 | 0.38 | 0.12 | no | consistent |
| File_2 | architecture | 0.41 | 0.71 | 0.29 | 0.12 | no | consistent |
| File_3 | security | 0.53 | 0.03 | 0.97 | 0.44 | no | **INCONSISTENT** |
| File_3 | quality | 0.47 | 0.07 | 0.93 | 0.46 | no | **INCONSISTENT** |
| File_3 | performance | 0.44 | 0.25 | 0.75 | 0.31 | no | **INCONSISTENT** |
| File_3 | testing | 0.59 | 0.27 | 0.73 | 0.14 | **yes** | consistent |
| File_3 | architecture | 0.53 | 0.25 | 0.75 | 0.22 | no | consistent |

**hosted-jev**

| File | Dimension | direct | inverse | 1-inverse | gap | flagged dim? | inconsistent? |
|---|---|---|---|---|---|---|---|
| File_1 | security | 0.99 | 0.02 | 0.98 | 0.01 | **yes** | consistent |
| File_1 | quality | 0.04 | 0.51 | 0.49 | 0.45 | no | **INCONSISTENT** |
| File_1 | performance | 0.05 | 0.50 | 0.50 | 0.45 | no | **INCONSISTENT** |
| File_1 | testing | 0.08 | 0.13 | 0.87 | 0.79 | no | **INCONSISTENT** |
| File_1 | architecture | 0.03 | 0.70 | 0.30 | 0.27 | no | consistent |
| File_2 | security | 0.98 | 0.07 | 0.93 | 0.05 | **yes** | consistent |
| File_2 | quality | 0.02 | 0.51 | 0.49 | 0.47 | no | **INCONSISTENT** |
| File_2 | performance | 0.03 | 0.53 | 0.47 | 0.44 | no | **INCONSISTENT** |
| File_2 | testing | 0.06 | 0.23 | 0.77 | 0.71 | no | **INCONSISTENT** |
| File_2 | architecture | 0.03 | 0.71 | 0.29 | 0.26 | no | consistent |
| File_3 | security | 0.02 | 0.41 | 0.59 | 0.57 | no | **INCONSISTENT** |
| File_3 | quality | 0.02 | 0.67 | 0.33 | 0.31 | no | **INCONSISTENT** |
| File_3 | performance | 0.04 | 0.66 | 0.34 | 0.30 | no | consistent |
| File_3 | testing | 0.98 | 0.03 | 0.97 | 0.01 | **yes** | consistent |
| File_3 | architecture | 0.02 | 0.72 | 0.28 | 0.26 | no | consistent |


### Findings

Summary of inconsistency counts (out of 15 dimension-checks per model, 5 per file × 3 files):
- kev-4b: 6 inconsistent (1 in File_1, 1 in File_2, 4 in File_3) — and critically, **one of them is on
  the actually-flagged dimension itself** (File_2's security check: direct=0.93 says "yes, failing,"
  inverse=0.50 is a coin flip on "is it safe to assume no issue" — the model contradicts itself on
  the one dimension that matters most).
- semif: 3 inconsistent, all clustered in File_3 (the case it also got the crosscutting pick wrong
  on — the inconsistency and the wrong answer co-occur, which is itself a useful signal).
- hosted jev: 8 inconsistent — the highest raw count — but **every single one is on a dimension
  that is not actually flagged** (it hedges between direct≈0.02-0.08 and inverse≈0.5-0.7 on the
  "nothing's wrong here" dimensions). On the one dimension that is actually flagged, every time,
  its gap is ≤0.05 — essentially perfect self-agreement exactly where it counts.

So raw inconsistency count alone would rank hosted jev as the *least* self-consistent model — the
opposite of the right conclusion. What matters is *where* the inconsistency falls: kev-4b's lands
on the critical dimension itself (the dangerous kind); hosted jev's lands only on the dimensions
that don't matter (the safe kind). No single confidence number or single choice question could
have surfaced this distinction — it only exists because of the redundant, orthogonal probes.
