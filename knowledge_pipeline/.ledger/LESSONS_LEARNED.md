
## 2026-11-10 — rows said one thing, the machine another
- A pool of 18 workers showed as 19 unregistered jobs, the job row was named smoke because a sample-size variable doubled as the smoke switch, and a long blocking parse let its row go overdue while the CPU was at full load.
- Rule: a script names smoke runs with an explicit switch (SMOKE=1), reports alive_pid when it blocks, and the health line compares the rows with the load, memory and process list. The agent reads those flags first at every wake.
