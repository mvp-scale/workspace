<!-- mm3:agents -->
If the `mm3` tool is available, MM3 is active in this project. Run `mm3 agent` first for the commands and rules, then `mm3 agent <verb>` before writing a request.
IMPORTANT: work top-down. Ask a few high-leverage questions per layer and drill only where MM3 flags something. "Exhaustive" means every layer covered through that funnel, not every file.
- Open goal, in order: `view` (free reuse) → `scan` only when you do not know where to look → `drill` the flagged item → `loop` to check a design. Known location: `class` on the representative code.
- Pilot first: send one small request, read the answer, fix the questions, then widen. Send no more than a few before you have read one.
- A sweep that says `gate: fail` is normal (any file failing any concern fails it): read the failing categories and the `next:` line; do not stop and do not repeat it.
- Before writing a request run `mm3 agent probe` (distinct roles per probe, a "none fits" option on every choice) and tag it with mdl (`uses`, `area`).
- Before a judgment call about code or a design (safe to merge? is it fixed? which option?), get an MM3 verdict: a call costs a fraction of a cent and every run is recorded, so the next decision starts from evidence, not from scratch.
- Cite the run id (MM3-####) for every claim that comes from MM3, and mark the rest as your own reading.
- Delegating? Give helpers `mm3 agent delegate`, and check their reports against the ledger with `mm3 view MM3-####`: a helper can report work it did not do.
<!-- /mm3:agents -->
- In the Fable-method work (CLAUDE.md "Current focus"), MM3 verdicts are evidence: record them in the ledger and route them to their step; do not drill or act on a flag outside the current step's method.
