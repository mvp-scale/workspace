---
name: captain
description: Captain pattern for long multi-iteration work (e.g. ontology-trainer rounds). One Sonnet captain loads the full context once, then launches crew (forks of itself, or fresh Haiku agents with self-contained commands) to run jobs; the main Opus session stays the decision maker. Use when the user says "captain", "crew", or asks to mine iterations with sub-agents.
---

# Captain pattern

Roles:
- **Bridge** (main session, Opus): decides. Reads captain reports, checks claims against the ledger / MM3 ids, answers questions, sends corrections to the captain with SendMessage. Does not re-read the starter context.
- **Captain** (Sonnet subagent, `.claude/agents/captain.md`): loads the whole working context once (GO.md, the domain skill, ledger items, code, logs), then runs the iteration loop by launching crew. Stays alive across iterations; the bridge continues it with SendMessage.
- **Crew**: one task each.
  - Needs the captain's context (judgement, reading results, writing a write-up) -> `fork` of the captain. A fork always runs on the captain's model: Sonnet `[S2]` (effort inherited).
  - Only has to launch or check a job -> fresh Haiku `[H1]` agent with a fully self-contained prompt: exact command, working dir, env, log path, the progress-event line, and what to report. Haiku gets no inherited context, so the prompt must stand alone.
  - Trivial one-liners (a `pgrep`, a `tail`) the captain runs itself; an agent per command is waste.

## Rules (all bind every role)
- Shortcode before every agent launch (`~/.claude/CLAUDE.md`): `[S2]`, `[H1]`, etc. Cheapest tier that plausibly succeeds. Flag fan-outs above ~6 agents to the bridge first.
- Fable-method rules (`CLAUDE.md`, `GO.md`): predict in the ledger before each run, score after; every claim cites a ledger item, a pinned file + command, or an MM3 id; no job over 1 hour (each `timeout` < 3000 s); every job posts progress events; kill by verified PID; no GPU / legacy models / hosted calls beyond what the method and user allow.
- Crew report back to the captain: what was launched (PID, log, timeout), or the result with file path and numbers. A crew report is checked, not trusted (`pgrep`, the result file, `ledger show`).
- Captain reports to the bridge in <= 10 lines: done, running (PID, ETA), results with evidence ids, decisions it needs. Keep/drop decisions, method changes and anything on the "waiting on the user" list go to the bridge, never decided by the captain.
- Nesting check: if the captain cannot launch agents (no Agent tool), it says so in its first report and does not silently do the crew's work itself.

## Launch (bridge side)
`[S2]` Agent, `subagent_type: captain` (or `general-purpose` with `model: sonnet` if the type is not loaded yet), prompt: "Read `.claude/skills/captain/SKILL.md` and act as captain for: <thread>. First: load context, report state, then <first task>."
