# AGENTS.md

You are working in a project run by the ledger kit. Read this before touching anything. `README.md` explains why the kit is built this way; this file is what you do.

## The rules you work by

1. **Write the ledger only through the tool.** Every change is `node cp.mjs <verb> ...`. Never edit `ledger.jsonl` by hand: each line is chained to the one before it, so a hand edit breaks the replay and `check` names it.
2. **Never edit a released contract version.** `contract/v<n>/` with a `release.yaml` is locked. To change anything, copy it to the next version, change that, and release it with `node cp.mjs release v<n> --by <who>`. Ask the owner before releasing; the contract is their word.
3. **Read one answer, never the whole file.** Use `ready`, `brief <id>` and `check`; do not read `ledger.jsonl` or the contract whole.
4. **No evidence, no claim.** `done` cites what proves it (`--evidence commit:<sha>`, `test:<file>`, `validate:<receipt>`); a task with a validator needs that validator's receipt. Use full 40-character commit shas.
5. **You never judge your own work.** A verdict comes from a different agent, against every acceptance criterion in the task's own words.
6. **A warning is information, not a stop.** When the tool replies `warned: <rule> (...; fix: ...)`, apply the fix next time; the warning is recorded. A refusal writes nothing: read its rule and fix, then try again.
7. **A miss is a post-mortem, not a new task.** When a verdict fails, record why with evidence; what to do about it is decided at a ceremony, from the pattern.

## Working a task

```bash
node cp.mjs ready                                   # the next task, in order (focus first, then journey order)
node cp.mjs brief T7                                # everything you need: where it sits, skills, validator, steps, acceptance, needs
node cp.mjs start T7 --who <you>
node cp.mjs step T7 1 --who <you>                   # close each step as it is done, in order
node cp.mjs note T7 "what you learned" --who <you>  # anything the next agent should know
node cp.mjs done T7 --who <you> --evidence commit:<sha> --evidence validate:<receipt>
```

Blocked? `node cp.mjs block T7 "the exact question or missing thing" --who <you>`, then pick the next ready task. Another agent may take over a blocked task with `start`.

Judging someone else's task: `node cp.mjs verdict T7 --result pass|fail --who <you> --evidence mm3:<run>`. A failed task gets a post-mortem from its owner.

## Shaping work

- Keep a task inside one capability, and a wave inside one domain. A task that spans capabilities gets a warning naming them: split it.
- Give every task two to four steps, each an outcome of at most 60 characters. One agent works the steps of one task in order; that is the token-efficient pattern.
- A bug names its severity (high, medium, low), blast radius (code, component, container, system) and capability. Its priority is computed; never type one. Only a high bug becomes a task; low and medium go to the pool.
- Name the shared space on every task when the project has a journey: `--stage`, `--domain`, `--capability`, `--goal`, using ids from the contract. An id the contract does not hold is refused.
- What comes first is set only at a ceremony, by a focus line with its reason: `node cp.mjs focus --order <capability or domain> --evidence <type:ref> "why it matters more now"`.

## Writing acceptance criteria

Every task carries its acceptance criteria and is judged against them in their own words, so write them to be judged. The full method, with its sources, is `methods/acceptance-criteria.md`; its core:

- Start from the outcome: who uses the result, for what decision, and what a false or a missed claim costs.
- Every measured criterion names its denominator (recall over actual positives, false alerts over all inputs) and its threshold's basis. A threshold with no basis is marked provisional, with an owner; it guides work and is not evidence of readiness.
- Keep what you learn from apart from what you are accepted on. An acceptance case you have studied and fixed against becomes a regression case; the next acceptance needs fresh evidence.
- Never change a criterion to make a failing result pass. Change the scope, the fallback or the approach, by a recorded decision.
- A ceremony decides one of: accept, continue (a bounded next change), inconclusive (gather evidence, claim nothing), plateau (change the approach) or stop (record what is unmet).

## Where things live

| Path | What it is | Who changes it |
|---|---|---|
| `contract/v<n>/` | the source of truth: journey, capabilities, experience, north star, rules | the owner, by a new released version |
| `ledger.jsonl` | the record of everything that happened | the tool, by appending |
| `cp.mjs`, `engine.mjs` | the tool and the rules it enforces | a change to the kit (below) |
| `viewer.html` | what people read: `node cp.mjs serve` | nobody; it reads the data |
| `examples/fixit/` | a complete made-up project to copy from | nobody |
| `methods/` | how to do a part of the work well (acceptance criteria) | a change to the kit |

## Extending the kit

Each change ends with `npm test`.

Four changes cover most needs. Each ends with `npm test` and, where it touches the contract, a new released version.

### Release a new contract version

A released version is never edited. To change anything in it:

```bash
cp -r contract/v1.0 contract/v1.1 && rm contract/v1.1/release.yaml
# edit contract/v1.1/...
node cp.mjs release v1.1 --by <who> --open "anything knowingly unfinished"
node cp.mjs verify
```

Readers move to v1.1 at once. Lines already in the ledger stay valid as long as the ids they name are still in the contract; `node cp.mjs check` says so.

### Add a stage, domain or capability

In a new version: add the stage to `journey.yaml` `stages` in its place in the customer's journey, add a domain under it (a noun, its goal, its definition: what it holds and what it does not), list the capability ids in the domain, and give each capability its own `capabilities/<id>.yaml` with its entities and goals. A goal's functions say how the capability achieves it; leave them empty until you know, and never fill them with create, read, update and delete.

### Add a field to a line

The engine accepts extra fields and keeps them; nothing else is needed to carry a field. To have the tool check it, add the check in `engine.mjs` `check()` as a warn-mode rule (below) and say what the field means in `rules/ledger.yaml` (a new contract version).

### Add a rule in warn mode

In `engine.mjs`, inside the line kind it applies to, call `soft(<rule name>, <what was wrong>, <the fix>)`. A rule called through `soft` starts in warn mode: the line goes through and the tool appends a warning line. Then:

1. Add a test in `test/engine.test.mjs` that the rule warns, and run `npm test`.
2. Name the rule and why in a new contract version's `rules/ledger.yaml`.
3. When it has warned on three separate tasks the viewer shows it ready to enforce; turn it on with a decision citing those warnings:

```bash
node cp.mjs decision D1 --rule <rule name> --mode enforce --evidence line:L41 --evidence line:L57 --evidence line:L90 "three tasks broke it"
```

A rule that must hold from the first line (letting it through would cost more to undo than to stop) goes in `DAY_ONE` in `engine.mjs` and in `rules/ledger.yaml` `enforcement.day_one`; a test holds the two lists equal.
