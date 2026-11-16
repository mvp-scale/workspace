---
description: Start a fresh session from the handoff file GO.md
---
FIRST MOVE (owner 2026-11-12): run `python3 /workspace/knowledge_pipeline/kit/live/session_start.py` and keep its output; it is the list of what is outstanding. Then read /workspace/GO.md in full and follow it. In the reply, after the 5 lines below, print its NEEDS YOU lines verbatim (one line each) and any CONTRACT, PAGES or UNSCORED lines that are not clean; if NEEDS YOU is empty say so. Never claim something is done or waiting on the owner without opening the raw ledger line (decision lines carry no task id).

Read /workspace/GO.md in full and follow it. Reply in at most 5 lines: what the open thread is and what you are doing now. Then re-enter the loop without waiting for a confirmation: run the first unblocked step under "Next" in GO.md, and arm the self-paced loop with ScheduleWakeup (prompt `/loop keep the knowledge pipeline loop going`). Stop and wait only if GO.md starts with HOLD, or the next step needs the owner's yes (money past the cap, deleting data, running third-party code, anything outward-facing). Changed 2026-11-01 at the owner's request; before that this command waited for a confirmation.
