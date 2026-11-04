"""Self-shutdown guard for Kaggle notebooks. Paste (or import) at the top of every kernel script.

Kaggle's CLI cannot cancel a running notebook from outside, so the stop lives inside the notebook and works even if
our machine, session or watcher dies:
  - idle stop: no call to beat() for IDLE_MIN minutes  -> the process exits and Kaggle frees the GPU
  - hard stop: MAX_MIN minutes after start, whatever is happening -> exits
Defaults: idle 5 min, hard 20 min. Size max_min to about 2x the expected run and idle_min to about 3x the longest pause between beats.
`python3 runs.py summary` (next to this file) suggests settings from your own past runs.
Call beat("what just happened") after every batch / step / saved file; it also prints a timestamped heartbeat line.
It also prints machine-readable `[guard-ev] {...}` lines (start, first beat, end) that watch.sh copies into the run ledger. Standard library only.

    from guard import guard, beat      # or paste this file's body into the notebook
    guard(max_min=20, idle_min=5)
    ... beat(f"epoch {e} step {i}") ...
"""
import atexit, json, os, sys, threading, time

_last = [time.time()]
_st = {"start": None, "first": None, "beats": 0, "max_gap": 0.0, "ended": False}


def _ev(kind, **kw):
    print("[guard-ev] " + json.dumps({"ev": kind, "t": round(time.time(), 2), **kw}), flush=True)


def _ages():
    """Seconds the machine (kernel) and this process have been up when the guard starts; None where /proc is unreadable."""
    try:
        up = float(open("/proc/uptime").read().split()[0])
        tick = os.sysconf("SC_CLK_TCK")
        started = int(open("/proc/self/stat").read().rsplit(")", 1)[1].split()[19]) / tick
        return round(up, 1), round(up - started, 1)
    except Exception:
        return None, None


def beat(msg=""):
    now = time.time()
    if _st["start"] is not None:
        if _st["beats"] and now - _last[0] > _st["max_gap"]:
            _st["max_gap"] = now - _last[0]
        _st["beats"] += 1
        if _st["first"] is None and _st["beats"] == 2:          # beat 1 is "guard on"; beat 2 is the first real work
            _st["first"] = now
            _ev("first_beat", warmup_s=round(now - _st["start"], 1))
    _last[0] = now
    if msg:
        print(f"[guard {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _end(reason):
    if _st["ended"]: return
    _st["ended"] = True
    now = time.time()
    _ev("end", reason=reason, run_s=round(now - _st["start"], 1), beats=_st["beats"], max_gap_s=round(_st["max_gap"], 1),
        warmup_s=round(_st["first"] - _st["start"], 1) if _st["first"] else None)


def guard(max_min=20, idle_min=5, poll_s=15):
    start = _st["start"] = time.time()
    machine_up_s, process_up_s = _ages()
    _ev("start", max_min=max_min, idle_min=idle_min, machine_up_s=machine_up_s, process_up_s=process_up_s)
    atexit.register(_end, "normal")                              # normal script end; os._exit below skips atexit, so stops log first

    def watch():
        while True:
            time.sleep(poll_s)
            now = time.time()
            if now - start > max_min * 60:
                why, reason = f"hard stop: {max_min} min run limit reached", "hard_stop"
            elif now - _last[0] > idle_min * 60:
                why, reason = f"idle stop: no progress for {idle_min} min", "idle_stop"
            else:
                continue
            print(f"[guard {time.strftime('%H:%M:%S')}] {why}; exiting so Kaggle releases the GPU", flush=True)
            _end(reason)
            sys.stdout.flush(); sys.stderr.flush()
            os._exit(3)

    threading.Thread(target=watch, daemon=True).start()
    beat(f"guard on: hard stop {max_min} min, idle stop {idle_min} min")
