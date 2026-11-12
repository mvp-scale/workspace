#!/usr/bin/env python3
"""Poll Console sessions, Console batches and Kaggle kernels (read only, no model calls) and write their heartbeats.
    python poll_live.py [--once] [--every 180]
Rows: [CON] session-<id8>, [API] batch-<id8> (created in the last 6 h), [KAG] kernels named kp-*. Key: secrets/vault.env, piped to ant on
stdin, never printed. Exits only when killed (kill by verified PID)."""
import argparse, json, pathlib, subprocess, sys, time, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from heartbeat import beat, record, drop, prune, watch_pids, watch_untracked
VAULT = pathlib.Path("/workspace/secrets/vault.env")


def kaggle_env():
    """Kaggle API token from the environment, else the first ~/.kaggle/*.token file (never printed). No interactive login."""
    import os
    env = dict(os.environ)
    for l in VAULT.read_text().splitlines():                      # the vault first: KAGGLE_API_TOKEN=...
        if l.startswith("KAGGLE_API_TOKEN="): env["KAGGLE_API_TOKEN"] = l.split("=", 1)[1].strip().strip("'\""); break
    if not env.get("KAGGLE_API_TOKEN"):
        for f in sorted(pathlib.Path.home().joinpath(".kaggle").glob("*.token")):
            env["KAGGLE_API_TOKEN"] = f.read_text().strip(); break
    return env


def key():
    for l in VAULT.read_text().splitlines():
        if l.startswith("ANTHROPIC_API_KEY="): return l.split("=", 1)[1].strip().strip("'\"")


def ant(*args):
    r = subprocess.run(["ant", *args, "--api-key-stdin", "--format", "json"], input=key(), capture_output=True, text=True, timeout=60)
    t, out, i, dec = r.stdout, [], 0, json.JSONDecoder()
    i = t.find("{")
    while 0 <= i < len(t):
        while i < len(t) and t[i] in " \n\r\t,[]": i += 1
        if i >= len(t): break
        o, i = dec.raw_decode(t, i); out.append(o)
    return out


def age_h(ts):
    try: return (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() / 3600
    except Exception: return 1e9


a_every = 180


def poll():
    for s in ant("beta:sessions", "list", "--limit", "20"):
        if age_h(s.get("updated_at") or s.get("created_at") or "") > 24: continue
        u, b, job = s.get("usage") or {}, s.get("budget") or {}, f"session-{s['id'][-8:]}"
        spent = float((u.get("list_cost") or {}).get("amount") or 0)
        cap = float(((b.get("max_list_cost") or {}).get("amount")) or 0) / 100 or None
        if s.get("status") == "running":
            beat(job, where="[CON]", state="running", progress=(s.get("agent") or {}).get("name"), spent=spent, cap=cap, last=s.get("title") or "")
        else:                                       # idle = its work is finished: one history record, no active row
            record(job, "done", where="[CON]", started=s.get("created_at"), ended=s.get("updated_at"), progress=(s.get("agent") or {}).get("name"), spent=spent, last=s.get("title") or "")
            drop(job)
    for b in ant("beta:messages:batches", "list", "--limit", "20"):         # batches are detail of their parent job: shown only in flight
        if age_h(b.get("created_at") or "") > 6: continue
        c, job = b.get("request_counts") or {}, f"batch-{b['id'][-8:]}"
        if b.get("processing_status") == "ended": drop(job)
        else: beat(job, where="[API]", state="running", progress=f"{c.get('succeeded', 0)} ok / {c.get('processing', 0)} waiting / {c.get('errored', 0)} err", last="Message Batch in flight")
    try:
        r = subprocess.run(["kaggle", "kernels", "list", "--mine", "--search", "kp-", "--csv"], capture_output=True, text=True, timeout=60, env=kaggle_env())
        csv = r.stdout.splitlines(); csv = csv[next((i for i, l in enumerate(csv) if l.startswith("ref,")), len(csv)):]   # the CLI prints version warnings first
        r.stdout = "\n".join(csv)
        if r.returncode == 0 and not r.stdout.startswith("ref,"):                  # logged in, no kp-* kernels yet: nothing to show
            drop("kaggle"); r.stdout = ""
        elif r.returncode != 0:
            beat("kaggle", where="[KAG]", state="failed", last="Kaggle API token missing or rejected (put KAGGLE_API_TOKEN=... in secrets/vault.env)", progress="no kernel status until then"); r.stdout = ""
        else: drop("kaggle")
        for line in r.stdout.splitlines()[1:]:
            ref, title = (line.split(",") + ["", ""])[:2]
            st = subprocess.run(["kaggle", "kernels", "status", ref], capture_output=True, text=True, timeout=60, env=kaggle_env()).stdout.strip(); job = f"kaggle-{ref.split('/')[-1][:24]}"
            st = next((l for l in reversed(st.splitlines()) if "status" in l.lower() and not l.lower().startswith("warning")), st.splitlines()[-1] if st else "")  # the CLI prints version warnings first
            if "running" in st.lower() or "queued" in st.lower(): beat(job, where="[KAG]", state="running" if "running" in st.lower() else "queued", last=st[:120], progress=title, every_s=a_every)
            else: record(job, "done" if "complete" in st.lower() else "failed", where="[KAG]", last=st[:120], progress=title); drop(job)
    except Exception as e:
        beat("kaggle", where="[KAG]", state="failed", last=f"kaggle poll failed: {type(e).__name__}")
    watch_pids(); watch_untracked()
    prune()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--once", action="store_true"); ap.add_argument("--every", type=int, default=180); a = ap.parse_args()
    while True:
        try: subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve().parent / "tick.py")], capture_output=True, timeout=180)  # Training tab + Kaggle heartbeat mirror
        except Exception: pass
        try: poll(); beat("poller", where="[CPU]", state="running", last="polling Console sessions, batches, Kaggle", progress=f"every {a.every}s", every_s=a.every)
        except Exception as e: beat("poller", where="[CPU]", state="failed", last=f"{type(e).__name__}: {str(e)[:100]}")
        if a.once: break
        time.sleep(a.every)
