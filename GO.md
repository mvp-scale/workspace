# GO — session handoff (overwritten at each handoff, never appended)

Written 2026-10-17. Read this, then CLAUDE.md only if needed. Memory (auto-loaded) has the standing rules.

## How to work with me (non-negotiable)
- **Short.** Lead with the point, a few lines, one question at the end. State a caveat once.
- **Do what I asked, nothing adjacent.** No side experiments, no reviving finished threads, no option menus I didn't ask for. If my words are ambiguous, ask in one line instead of guessing (last session misread "it can already do that" and ran an unasked Clef-vs-Jev test).
- **Prove, don't claim.** For a test I asked for: method + pass/fail first, real inputs and outputs after.
- **Validate small → I decide → then integrate.** Local only; no cloud artifacts unless asked.
- Never call hosted Jev without asking. Kill processes by verified PID, never `pkill -f`. One model registry (`demo/registry.py`); no hard-coded models.

## Where things stand
- Branch `world-engine-100-countries`, committed, nothing pushed. `./service.sh` for services; console :8100.
- Clef Flash Q4 (:8018) is the local model of record. MM3 can already use it.
- **BitMob is paused** (local CPU classifier, :8020). Conclusion: an embeddings limit. It is good at trained, repeated questions (tone, code-security wording: 73% on OWASP), bad at facts (world knowledge ~29%, near chance) and at judging new questions against new code. It answers every TypeSafe type, tagging each answer "trained" or "guess". Do not extend it unless I ask.
- MM3 = github.com/mvp-scale/mm3 (log copy in `_remove/`, uncommitted, mine).

## Open thread
None in progress. I paused to reset. Ask me what's next; don't propose a list.
