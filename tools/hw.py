#!/usr/bin/env python3
"""hw.py: one screen for the knowledge pipeline: machine load, then where its work is running. Local only, no API calls.

  python3 tools/hw.py            refresh every 15 s (Ctrl-C to stop)
  python3 tools/hw.py 10         refresh every 10 s
  python3 tools/hw.py --once     print once and exit

Top: GPU, VRAM, CPU, RAM, disk. Middle: WORK BY LOCATION ([5090] [CPU] [KAG] [API] [CON] [HOST]) from
knowledge_pipeline/runs-live/*.json (active jobs) plus live local processes. Bottom: recent finished runs and spend.
The pipeline's own poller (kit/live/poll_live.py, every 3 min) does the Kaggle/Console reads; this screen only reads its files.
"""
import glob, json, os, re, shutil, subprocess, sys, time, calendar

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G, Y, R, D, B, Z = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"
if not sys.stdout.isatty(): G = Y = R = D = B = Z = ""


def run(cmd):
    try: return subprocess.run(cmd, capture_output=True, text=True, timeout=10, cwd=ROOT).stdout
    except Exception: return ""


def cpu_times():
    f = open("/proc/stat").readline().split()[1:]
    v = list(map(int, f)); return sum(v), v[3] + v[4]  # total, idle+iowait


def bar(frac, w=20):
    frac = max(0, min(1, frac)); n = round(frac * w)
    c = G if frac < .6 else Y if frac < .85 else R
    return f"{c}{'█' * n}{D}{'░' * (w - n)}{Z}"


def snapshot():
    t0, i0 = cpu_times()
    procs0 = {}
    for p in os.listdir("/proc"):
        if p.isdigit():
            try: s = open(f"/proc/{p}/stat").read().rsplit(")", 1)[1].split(); procs0[int(p)] = int(s[11]) + int(s[12])
            except Exception: pass
    time.sleep(1)
    t1, i1 = cpu_times()
    dt = max(1, t1 - t0); cores = os.cpu_count() or 1
    cpu_frac = 1 - (i1 - i0) / dt
    hz = os.sysconf("SC_CLK_TCK")
    cpu_pid = {}
    for p, j0 in procs0.items():
        try:
            s = open(f"/proc/{p}/stat").read().rsplit(")", 1)[1].split()
            cpu_pid[p] = (int(s[11]) + int(s[12]) - j0) / hz * 100  # % of one core over the 1 s window
        except Exception: pass
    rss = {}
    for p in cpu_pid:
        try: rss[p] = int(re.search(r"VmRSS:\s+(\d+)", open(f"/proc/{p}/status").read()).group(1)) / 1048576
        except Exception: pass
    mem = {k: int(v.split()[0]) for k, v in (l.split(":") for l in open("/proc/meminfo"))}
    gpu = run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
               "--format=csv,noheader,nounits"]).strip().split(", ")
    apps = {}
    for l in run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"]).splitlines():
        a = l.split(", ")
        if len(a) == 2: apps[int(a[0])] = apps.get(int(a[0]), 0) + int(a[1])
    svc = []
    for l in run(["./service.sh", "status"]).splitlines():
        m = re.match(r"\s+(\S+)\s+(:\d+|-)\s+(up|loading|down)\s+(\d+|-)\s+(\S+)\s+(.*)", l)
        if m and m.group(3) != "down": svc.append((m.group(1), m.group(2), m.group(3), int(m.group(4)), m.group(5)))
    return dict(cpu=cpu_frac, cores=cores, load=os.getloadavg(), mem=mem, gpu=gpu, apps=apps, svc=svc, cpu_pid=cpu_pid, rss=rss)


KP = os.path.join(ROOT, "knowledge_pipeline")
ORDER = ["[5090]", "[CPU]", "[KAG]", "[API]", "[CON]", "[HOST]"]
NAMES = {"[5090]": "local GPU", "[CPU]": "local CPU", "[KAG]": "Kaggle (GPU or CPU kernels)", "[API]": "hosted API", "[CON]": "Console", "[HOST]": "hosted model"}
IGNORE = re.compile(r"claude|cursor|tmux|colab-mcp|tailscaled|node |hw\.py|bash$")


def ts(v):
    try: return calendar.timegm(time.strptime(re.sub(r"\.\d+Z$", "Z", v), "%Y-%m-%dT%H:%M:%SZ"))  # accepts fractional seconds (ledger times carry milliseconds)
    except Exception: return None


def ago(sec):
    if sec is None: return "?"
    sec = int(sec)
    return f"{sec}s" if sec < 90 else f"{sec // 60}m" if sec < 5400 else f"{sec / 3600:.1f}h" if sec < 172800 else f"{sec // 86400}d"


def jobs_active():
    out = []
    for f in glob.glob(os.path.join(KP, "runs-live", "*.json")):
        try: out.append(json.load(open(f)))
        except Exception: pass
    return out


def history(n=2000):
    try: lines = open(os.path.join(KP, "runs-history.jsonl")).read().splitlines()[-n:]
    except Exception: return []
    r = []
    for l in lines:
        try: r.append(json.loads(l))
        except Exception: pass
    return r


def kaggle_left():
    try:
        d = json.load(open(os.path.join(ROOT, "demo/mockups/trainer/live.json")))
        for j in sorted(d.get("jobs", []), key=lambda j: j.get("ts", 0), reverse=True):
            m = re.search(r"GPU left: ([\d.]+)h", j.get("msg", ""))
            if m: return float(m.group(1)), time.time() - j.get("ts", 0)
    except Exception: pass
    return None


def render(s):
    now = time.time()
    out = [f"{B}KNOWLEDGE PIPELINE{Z}  {time.strftime('%H:%M:%S')}  {D}local only, no API calls{Z}"]
    if len(s["gpu"]) >= 6:
        name, util, used, tot, temp, pw = s["gpu"][:6]; used, tot = int(used), int(tot)
        out.append(f"GPU  {bar(int(util) / 100)} {util:>3}%  {name.replace('NVIDIA GeForce ', '')}  {temp}C {float(pw):.0f}W   VRAM {bar(used / tot, 12)} {used / 1024:.1f}/{tot / 1024:.1f} GiB  {B}{(tot - used) / 1024:.1f} free{Z}")
    else: out.append("GPU  not available")
    c = s["cores"]; m = s["mem"]; ut = (m["MemTotal"] - m["MemAvailable"]) / 1048576; tt = m["MemTotal"] / 1048576
    out.append(f"CPU  {bar(s['cpu'])} {s['cpu'] * 100:>3.0f}%  {B}{(1 - s['cpu']) * c:.0f} of {c} cores free{Z}   load {s['load'][0]:.1f}   RAM {bar(ut / tt, 12)} {ut:.0f}/{tt:.0f} GiB  {B}{m['MemAvailable'] / 1048576:.0f} free{Z}")
    du = shutil.disk_usage(ROOT)
    out.append(f"DISK {bar(du.used / du.total)} {du.used / du.total * 100:>3.0f}%  {B}{du.free / 1e12:.2f} TB free{Z} of {du.total / 1e12:.1f} TB   {D}(/workspace){Z}")
    kl = kaggle_left()
    if kl: out.append(f"KAG  GPU quota left {B}{kl[0]:.1f} h{Z}  {D}(as of last Kaggle job, {ago(kl[1])} ago){Z}")

    act = jobs_active(); by = {k: [] for k in ORDER}
    for j in act: by.setdefault(j.get("where", "?").split("+")[0], []).append(j)
    poll = next((j for j in act if j.get("job") == "poller"), None)
    pa = now - ts(poll["updated"]) if poll and ts(poll.get("updated", "")) else None
    out.append("")
    try:
        hrow = json.load(open("/workspace/knowledge_pipeline/runs-live/health.json")); hcol = {"ok": G, "warn": Y, "bad": R}.get(hrow.get("level"), "")
        out.append(f"{B}HEALTH{Z}  {hcol}{hrow.get('progress', '?')}{Z}  {D}({ago(now - ts(hrow['updated']))} ago){Z}" + (f"\n        {D}{hrow['last']}{Z}" if hrow.get("last") and hrow["last"] != "no flags" else ""))
    except Exception: out.append(f"{R}HEALTH  not reporting (poller or health.py is not running){Z}")
    out.append(f"{B}WORK BY LOCATION{Z}  {D}poller: " + (f"{'ok' if pa is not None and pa < 600 else R + 'STALE'}{D}, updated {ago(pa)} ago" if poll else f"{R}not running{D} (Kaggle/Console rows will be old)") + f"{Z}")
    # local processes: GPU users and busy CPU work, by location
    procs = {k: [] for k in ORDER}
    svcpids = {x[3] for x in s["svc"]}
    for pid, mib in s["apps"].items():
        procs["[5090]"].append((pid, f"{mib / 1024:.1f} GiB VRAM"))
    for pid, cp in sorted(s["cpu_pid"].items(), key=lambda x: -x[1])[:12]:
        if cp < 25 or pid in s["apps"]: continue
        try: cmd = open(f"/proc/{pid}/cmdline").read().replace("\0", " ")
        except Exception: continue
        if IGNORE.search(cmd[:80]): continue
        procs["[CPU]"].append((pid, f"{cp:.0f}% of a core"))
    for loc in ORDER:
        jobs = [j for j in by.get(loc, []) if j.get("job") != "poller"]
        if not jobs and not procs[loc]: out.append(f"{D}{loc:<7}{NAMES[loc]:<13}idle{Z}"); continue
        out.append(f"{B}{loc:<7}{NAMES[loc]}{Z}")
        for j in jobs:
            age = now - ts(j.get("updated", "")) if ts(j.get("updated", "")) else None
            lim = None if j.get("state") in ("idle", "waiting") else 900 if j.get("service") else max(600, 2.5 * float(j["every_s"])) if j.get("every_s") else 600  # per-job update expectation (every_s, service, idle), same rule as the ledger viewer
            stale = f"{R} STALE {ago(age)}{Z}" if age is not None and lim is not None and age > lim else ""
            sp = f"  ${j['spent']:.2f}" + (f"/${j['cap']:.0f}" if j.get("cap") else "") if j.get("spent") else ""
            out.append(f"   {j.get('state', '?'):<8}{j.get('job', '?')[:28]:<29}{ago(now - ts(j['started'])) if ts(j.get('started', '')) else '?':>6} {'running' if j.get('state') == 'running' else 'NOT RUNNING (' + str(j.get('state', '?')) + ')'}{sp}  {D}{str(j.get('progress') or j.get('last') or '')[:48]}{Z}{stale}")
        for pid, what in procs[loc]:
            try: cmd = open(f"/proc/{pid}/cmdline").read().replace("\0", " ")
            except Exception: cmd = "?"
            cmd = re.sub(r"^/workspace/(\./)?", "", cmd)
            out.append(f"   {'service' if pid in svcpids else 'job':<8}{cmd[:44]:<45}{what}")
    # finished runs
    h = history(); recent = [r for r in h if r.get("ended")][-5:]
    day = [r for r in h if ts(r.get("ended", "")) and now - ts(r["ended"]) < 86400]
    spent = sum(r.get("spent") or 0 for r in day)
    out.append("")
    out.append(f"{B}LAST 24 H{Z}  {len(day)} runs finished, ${spent:.2f} hosted spend (hosted review runs are not counted)   " + "  ".join(f"{k} {sum(1 for r in day if (r.get('where') or '').startswith(k))}" for k in ORDER if any((r.get('where') or '').startswith(k) for r in day)))
    for r in reversed(recent):
        col = G if r.get("state") == "done" else R
        out.append(f"   {col}{r.get('state', '?'):<8}{Z}{(r.get('where') or '-'):<13}{r.get('job', '?')[:20]:<21}{ago(now - ts(r['ended'])):>5} ago  {D}{str(r.get('last') or '')[:60]}{Z}")
    # services last, one line
    up = [n for n, _, st, _, _ in s["svc"]]
    out.append("")
    out.append(f"{D}services up ({len(up)}): {' '.join(up)}   details: ./service.sh status{Z}")
    return "\n".join(out)


def main():
    a = [x for x in sys.argv[1:] if x != "--once"]
    once = "--once" in sys.argv
    every = float(a[0]) if a else 15.0
    try:
        while True:
            txt = render(snapshot())
            if once: print(txt); return
            print("\033[2J\033[H" + txt + f"\n\n{D}every {every:g} s, Ctrl-C to stop{Z}", flush=True)
            time.sleep(max(0, every - 1))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
