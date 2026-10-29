# Task card: <ID> <short name>

Copy this file for each task, or put the same fields in one ledger `task` line. Fill every field **before** any
compute starts. A task without a stop rule doesn't launch.

| Field | Value |
|---|---|
| Package | P<n> (see `workstreams/README.md`) |
| Question | One sentence: what this task answers |
| Proven method + source | The published method this follows (paper, docs) or "none: exploratory, capped at <budget>" |
| Inputs | Datasets / files with sha or version |
| Output | Files produced; numbers only if they leave the private store |
| Definition of done | Measurable: e.g. "event-verb exact F1 lower 95% bound ≥ .535 on gold, scorer ffefe369" |
| Stop rule | When to stop even if not done: e.g. "2 variants without dev gain → stop and report" |
| Budget | GPU-h · CPU-h · API $ · agent tokens (each a cap) |
| Compute | Kaggle CPU / Kaggle GPU / local 3090 / local 5090 / API |
| Risk to check first | The cheapest test that could kill the idea (run it first) |
| Result | Filled after: numbers, ledger id, pass/fail per criterion |
