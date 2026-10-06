#!/usr/bin/env python3
"""service.py: start, stop, restart and inspect every service listed in /workspace/service.yaml.

Run it through ./service.sh. See the header of service.yaml for the config keys and
`./service.sh help` for the commands. Only the standard library and PyYAML are used.
"""
import os, re, sys, time, json, signal, shutil, subprocess, urllib.request, urllib.error

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is needed: python3 -m pip install pyyaml")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.environ.get("SVC_CONFIG") or os.path.join(ROOT, "service.yaml")
RUN = os.path.join(ROOT, "logs", "run")
TTY = sys.stdout.isatty()
C = {k: (v if TTY else "") for k, v in dict(g="\033[32m", r="\033[31m", y="\033[33m", d="\033[2m", b="\033[1m", z="\033[0m").items()}

def targets_text(cfg):
    S, P = cfg["services"], cfg["profiles"]; tags = sorted({t for s in S.values() for t in s["tags"]})
    return (f"  services   {' '.join(S)}\n  profiles   {' '.join(P)}   (a bare 'start' runs: {cfg.get('default_profile', '-')})\n  tags       {' '.join('tag:' + t for t in tags)}")


DETAIL = {
    "status": "status [target...]\n  Shows each service: port, up/down/loading, pid, uptime, plus extra copies on other ports and GPU memory.\n  ./service.sh                 everything\n  ./service.sh status world    one service\n  ./service.sh status models   one profile",
    "start": "start [target...]\n  Starts targets in dependency order and waits until each answers. Skips what is already up. No target = the default profile.\n  ./service.sh start                 the default profile\n  ./service.sh start demo            one service\n  ./service.sh start full            a profile\n  ./service.sh start test-world      a second engine on another port (a profile with a port)\n  ./service.sh start world --port 8130   same, ad hoc",
    "stop": "stop target...\n  Stops targets in reverse dependency order. A target is required. Asks first for heavy services (winnow, world, models); -y skips the question.\n  ./service.sh stop demo\n  ./service.sh stop models\n  ./service.sh stop tag:gpu -y",
    "restart": "restart target...\n  Stop, then start. A target is required. Use after editing code. Asks first for heavy services; -y skips.\n  ./service.sh restart demo          after editing demo/ code\n  ./service.sh restart world         after editing probes/world-engine code (loaded state is lost)\n  ./service.sh restart world --dry-run   show what would happen, change nothing",
    "logs": "logs service [-f]\n  Last 40 lines of a service's log; -f follows it.\n  ./service.sh logs world -f",
    "list": "list\n  Every service (port, kind, tags, what it is) and every profile.",
    "check": "check\n  Validates service.yaml: bad references, port clashes, missing commands or files, uninstalled systemd units. Run it after editing the file.",
}


def help_text(cfg, topic=None):
    if topic in DETAIL: return "  ./service.sh " + DETAIL[topic]
    if topic: return f"  no help for '{topic}'. Commands: {' '.join(DETAIL)}"
    t = targets_text(cfg) if cfg else ""
    return f"""{C['b']}service.sh{C['z']}: start, stop, restart and inspect everything in service.yaml

{C['b']}USAGE{C['z']}   ./service.sh <command> [target...] [options]

{C['b']}COMMANDS{C['z']}
  status   [target]   what is running (the default when you give no command)
  start    [target]   start things; no target = the default profile
  stop      target    stop things (a target is required)
  restart   target    stop then start (a target is required)
  logs      service   show a log; add -f to follow
  list                services, tags and profiles
  check               validate service.yaml after you edit it
  help     [command]  this page, or details and examples for one command (./service.sh help restart)

{C['b']}TARGETS{C['z']}  a service, a profile, or tag:<label>
{t}

{C['b']}OPTIONS{C['z']}
  -y           skip the question when stopping or restarting heavy services
  --dry-run    print what would run and change nothing (try it before a big restart)
  --port N     run one flexible service on another port, e.g. a test copy
  --force      stop a process even if its command line does not match the service

{C['b']}COMMON TASKS{C['z']}
  ./service.sh                         see everything
  ./service.sh start                   bring up the default set
  ./service.sh restart demo            reload the console after a code change
  ./service.sh restart world           reload the World Engine (asks first)
  ./service.sh stop models             free the GPU from the five models
  ./service.sh start test-world        a second engine on :8122 for testing
  ./service.sh logs world -f           watch the engine log

What is on, ports, start order and labels all live in service.yaml; edit it, then run ./service.sh check."""


# ------------------------------------------------------------------ config
def die(msg):
    print(f"{C['r']}error:{C['z']} {msg}", file=sys.stderr); sys.exit(1)


def load():
    try:
        cfg = yaml.safe_load(open(CONFIG))
    except Exception as e:
        die(f"cannot read {CONFIG}: {e}")
    cfg.setdefault("profiles", {}); cfg.setdefault("services", {})
    for n, s in cfg["services"].items():
        s.setdefault("kind", "proc"); s.setdefault("tags", []); s.setdefault("after", []); s.setdefault("boot", 60)
        s.setdefault("health", "/"); s.setdefault("heavy", False); s.setdefault("flex", False); s.setdefault("desc", "")
    return cfg


class Entry:
    """One thing to act on: a service on a port, with any per-profile env."""
    def __init__(self, name, port, env=None):
        self.name, self.port, self.env = name, port, env or {}

    def instance(self, cfg):
        base = cfg["services"][self.name].get("port")
        return self.name if self.port in (None, base) else f"{self.name}-{self.port}"


def expand(cfg, targets, _seen=None):
    """Targets -> ordered list of Entry (dependency order, config order otherwise)."""
    S, P = cfg["services"], cfg["profiles"]; out = []; _seen = _seen or set()

    def add_profile_item(item):
        if isinstance(item, dict):
            n = item.get("service") or item.get("name")
            if n not in S: die(f"profile entry names unknown service '{n}'")
            out.append(Entry(n, item.get("port", S[n].get("port")), item.get("env")))
        elif item in S:
            out.append(Entry(item, S[item].get("port")))
        elif item in P:
            if item in _seen: die(f"profile loop at '{item}'")
            for it in P[item]: add_profile_item_guard(it, item)
        else:
            die(f"'{item}' is not a service or profile (./service.sh list)")

    def add_profile_item_guard(it, via):
        _seen.add(via); add_profile_item(it); _seen.discard(via)

    for t in targets:
        if t.startswith("tag:"):
            hit = [n for n, s in S.items() if t[4:] in s["tags"]]
            if not hit: die(f"no service has tag '{t[4:]}'")
            out += [Entry(n, S[n].get("port")) for n in hit]
        else:
            add_profile_item(t)
    # unique by (name, port), then order by dependency
    uniq = {}
    for e in out: uniq.setdefault((e.name, e.port), e)
    order = {n: i for i, n in enumerate(S)}; items = sorted(uniq.values(), key=lambda e: order[e.name]); done, res = set(), []

    def visit(e):
        if (e.name, e.port) in done: return
        done.add((e.name, e.port))
        for a in S[e.name]["after"]:
            for o in items:
                if o.name == a: visit(o)
        res.append(e)
    for e in items: visit(e)
    return res


# ------------------------------------------------------------------ process helpers
def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def listeners():
    """port -> pid from ss."""
    out = {}
    for line in sh(["ss", "-ltnpH"]).splitlines():
        parts = line.split()
        if len(parts) < 4: continue
        m = re.search(r"pid=(\d+)", line); port = parts[3].rsplit(":", 1)[-1]
        if m: out.setdefault(int(port), int(m.group(1)))
    return out


def cmdline(pid):
    try: return open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="replace").strip()
    except OSError: return ""


def alive(pid):
    try: os.kill(pid, 0); return True
    except (OSError, TypeError): return False


def pidfile(cfg, e): return os.path.join(RUN, e.instance(cfg) + ".pid")


def find_pid(cfg, e, ls=None):
    pf = pidfile(cfg, e)
    if os.path.exists(pf):
        try:
            pid = int(open(pf).read().strip())
            if alive(pid): return pid
        except ValueError: pass
        os.remove(pf)
    return (ls if ls is not None else listeners()).get(e.port)


def looks_right(svc, pid, force):
    return force or re.search(svc.get("match", ".*"), cmdline(pid)) is not None


def health_ok(port, path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2) as r: return r.status < 500
    except urllib.error.HTTPError as e: return e.code < 500
    except Exception: return False


def etime(pid):
    return sh(["ps", "-o", "etime=", "-p", str(pid)]).strip() or "-"


def sub(s, e, port):
    return str(s).replace("${port}", str(port)).replace("${root}", ROOT)


def load_env_file(path):
    env = {}
    if path and os.path.exists(os.path.join(ROOT, path)):
        for line in open(os.path.join(ROOT, path)):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k, v = line.split("=", 1); v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"": v = v[1:-1]
            env[k.strip().removeprefix("export ").strip()] = v
    return env


def resolve_cmd(svc, e):
    argv = [sub(a, e, e.port) for a in svc["cmd"]]
    cwd = os.path.join(ROOT, svc.get("cwd", "."))
    exe = argv[0]
    if "/" in exe and not os.path.isabs(exe):                 # relative paths are relative to the cwd when it exists there, else to the repo root
        for base in (cwd, ROOT):
            if os.path.exists(os.path.join(base, exe)): argv[0] = os.path.join(base, exe); break
    for i, a in enumerate(argv[1:], 1):                       # file arguments written relative to the repo root
        p = os.path.join(ROOT, a)
        if not os.path.isabs(a) and not a.startswith("-") and "/" in a and os.path.exists(p): argv[i] = p
    return argv, cwd


def build_env(svc, e):
    env = dict(os.environ)
    env.update(load_env_file(svc.get("env_file")))
    for k, v in {**svc.get("env", {}), **e.env}.items(): env[k] = sub(v, e, e.port)
    if svc.get("path_prepend"): env["PATH"] = ":".join(svc["path_prepend"]) + ":" + env.get("PATH", "")
    return env


def logpath(cfg, e):
    svc = cfg["services"][e.name]; base = svc.get("log") or f"logs/{e.name}.log"
    inst = e.instance(cfg)
    if inst != e.name: base = re.sub(r"(\.log)?$", f"-{e.port}.log", base, 1)
    return os.path.join(ROOT, base)


# ------------------------------------------------------------------ actions
def confirm(msg, yes):
    if yes: return True
    if not sys.stdin.isatty(): die(f"{msg} -- add -y to confirm (not a terminal)")
    return input(f"{msg} [y/N] ").strip().lower().startswith("y")


def do_start(cfg, e, o):
    svc = cfg["services"][e.name]; k = svc["kind"]; dry = o["dry"]
    if k == "systemd":
        unit = svc.get("unit", e.name)
        if sh(["systemctl", "is-active", unit]).strip() == "active":
            print(f"  {e.name}: already up"); return
        cmd = ["systemctl", "start"] + ([] if svc.get("blocking") else ["--no-block"]) + [unit]
        if dry: print(f"  {e.name}: would run {' '.join(cmd)}"); return
        subprocess.run(cmd); print(f"  {e.name}: {C['g']}starting{C['z']} (systemd; logs/{e.name}.log)"); return
    if k == "script":
        cmd = [os.path.join(ROOT, svc["script"]), "start"]
        if dry: print(f"  {e.name}: would run {' '.join(cmd)}"); return
        subprocess.run(cmd, cwd=ROOT); return
    ls = listeners(); pid = find_pid(cfg, e, ls)
    if dry and (e.name, e.port) in o.get("stopping", set()): pid = None      # a dry-run restart: pretend the stop happened
    if pid:
        if looks_right(svc, pid, o["force"]): print(f"  {e.name}: already up (pid {pid}, :{e.port})"); return
        die(f"port {e.port} is held by pid {pid} ({cmdline(pid)[:70]}) which is not {e.name}; stop it first or use --port")
    argv, cwd = resolve_cmd(svc, e)
    if dry:
        print(f"  {e.name}: would run (cwd {os.path.relpath(cwd, ROOT)}) {' '.join(shlex_quote(a) for a in argv)}  env: {json.dumps({k: sub(v, e, e.port) for k, v in {**svc.get('env', {}), **e.env}.items()})}")
        return
    for a in svc["after"]:
        dep = cfg["services"].get(a)
        if dep and dep["kind"] == "proc" and not health_ok(dep.get("port"), dep.get("health", "/")):
            print(f"  {C['y']}note:{C['z']} {a} is not answering on :{dep.get('port')}; {e.name} may need it")
    os.makedirs(RUN, exist_ok=True); lf = logpath(cfg, e); os.makedirs(os.path.dirname(lf), exist_ok=True)
    with open(lf, "ab") as log:
        log.write(f"\n===== {e.instance(cfg)} start {time.strftime('%F %T')} =====\n".encode()); log.flush()
        try:
            p = subprocess.Popen(argv, cwd=cwd, env=build_env(svc, e), stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        except OSError as ex:
            print(f"  {e.name}: {C['r']}could not launch{C['z']}: {ex}"); return
    open(pidfile(cfg, e), "w").write(str(p.pid))
    for _ in range(int(svc["boot"])):
        if health_ok(e.port, svc["health"]):
            print(f"  {e.name}: {C['g']}up{C['z']} pid {p.pid}, http://127.0.0.1:{e.port}  (log: {os.path.relpath(lf, ROOT)})"); return
        if p.poll() is not None:
            os.remove(pidfile(cfg, e)); print(f"  {e.name}: {C['r']}exited during start{C['z']}; last log lines:")
            for line in open(lf, errors="replace").read().splitlines()[-8:]: print("      " + line)
            return
        time.sleep(1)
    print(f"  {e.name}: {C['y']}started (pid {p.pid}) but not answering yet{C['z']}; still loading? ./service.sh logs {e.name}")


def shlex_quote(a):
    return a if re.fullmatch(r"[\w@%+=:,./-]+", a) else "'" + a.replace("'", "'\\''") + "'"


def do_stop(cfg, e, o):
    svc = cfg["services"][e.name]; k = svc["kind"]; dry = o["dry"]
    if svc.get("stop"):
        if dry: print(f"  {e.name}: would run {svc['stop']}"); return
        subprocess.run(svc["stop"], shell=True, cwd=ROOT); print(f"  {e.name}: stopped (custom stop)"); return
    if k == "systemd":
        unit = svc.get("unit", e.name)
        if sh(["systemctl", "is-active", unit]).strip() != "active": print(f"  {e.name}: not running"); return
        if dry: print(f"  {e.name}: would run systemctl stop {unit}"); return
        subprocess.run(["systemctl", "stop", unit]); print(f"  {e.name}: stopped"); return
    if k == "script":
        cmd = [os.path.join(ROOT, svc["script"]), "stop"]
        if dry: print(f"  {e.name}: would run {' '.join(cmd)}"); return
        subprocess.run(cmd, cwd=ROOT); return
    pid = find_pid(cfg, e)
    if not pid:
        if os.path.exists(pidfile(cfg, e)) and not dry: os.remove(pidfile(cfg, e))
        print(f"  {e.name}: not running"); return
    if not looks_right(svc, pid, o["force"]):
        die(f"pid {pid} on :{e.port} does not look like {e.name} ({cmdline(pid)[:70]}); refusing to kill (use --force)")
    if dry: print(f"  {e.name}: would stop pid {pid} ({cmdline(pid)[:60]})"); return
    os.kill(pid, signal.SIGTERM)
    for _ in range(int(svc.get("stop_timeout", 30)) * 2):
        if not alive(pid): break
        time.sleep(0.5)
    if alive(pid): os.kill(pid, signal.SIGKILL); time.sleep(0.5)
    if os.path.exists(pidfile(cfg, e)): os.remove(pidfile(cfg, e))
    print(f"  {e.name}: stopped (was pid {pid})")


def do_restart(cfg, e, o):                                          # only called for services that define `restart:`
    cmd = cfg["services"][e.name]["restart"]
    if o["dry"]: print(f"  {e.name}: would run {cmd}"); return
    subprocess.run(cmd, shell=True, cwd=ROOT); print(f"  {e.name}: restarted (custom restart)")


def row(cfg, e, ls, extra=""):
    svc = cfg["services"][e.name]; k = svc["kind"]; pid = None; h = ""; up = "-"
    if k == "systemd":
        unit = svc.get("unit", e.name)
        if sh(["systemctl", "is-active", unit]).strip() == "active":
            v = sh(["systemctl", "show", "-p", "MainPID", "--value", unit]).strip(); pid = int(v) if v.isdigit() and int(v) else None
            st, col = ("up", "g") if health_ok(e.port, svc["health"]) else ("loading", "y")
        else: st, col = "down", "d"
    elif k == "script":
        out = sh([os.path.join(ROOT, svc["script"]), "status"]).strip().splitlines()
        on = bool(out) and "not running" not in out[0]; st, col = ("up", "g") if on else ("down", "d"); h = out[0] if on else ""
    else:
        pid = find_pid(cfg, e, ls)
        if not pid: st, col = "down", "d"
        else:
            st, col = ("up", "g") if health_ok(e.port, svc["health"]) else ("loading", "y")
            if not looks_right(svc, pid, False): st, col, h = "other", "r", f"pid {pid} is not {e.name}!"
    if pid: up = etime(pid)
    port = f":{e.port}" if e.port else "-"
    print(f"  {e.name:<8} {port:<6} {C[col]}{st:<9}{C['z']} {str(pid or '-'):<8} {up:<10} {h or svc['desc']}{extra}")


def cmd_status(cfg, entries):
    ls = listeners()
    print(f"  {'SERVICE':<8} {'PORT':<6} {'STATE':<9} {'PID':<8} {'UPTIME':<10} WHAT")
    for e in entries: row(cfg, e, ls)
    known = {(e.name, e.port) for e in entries}
    for n, s in cfg["services"].items():                         # extra copies: same command, other port
        if s["kind"] != "proc" or not s.get("flex"): continue
        for line in sh(["pgrep", "-f", s.get("match", "$^")]).split():
            pid = int(line)
            if pid == os.getpid(): continue
            port = next((p for p, q in ls.items() if q == pid), None)
            if port and port != s.get("port") and (n, port) not in known: row(cfg, Entry(n, port), ls, f" {C['y']}(extra copy){C['z']}")
    smi = sh(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"]).strip()
    if smi: print(f"  {C['d']}GPU memory: {smi}{C['z']}")


def cmd_list(cfg):
    print(f"  {'SERVICE':<8} {'PORT':<6} {'KIND':<8} {'TAGS':<22} WHAT")
    for n, s in cfg["services"].items(): print(f"  {n:<8} {(':' + str(s['port'])) if s.get('port') else '-':<6} {s['kind']:<8} {','.join(s['tags']):<22} {s['desc']}")
    print(f"\n  PROFILES (default: {cfg.get('default_profile', '-')})")
    for p, items in cfg["profiles"].items():
        names = [i if isinstance(i, str) else f"{i.get('service')}:{i.get('port', '')}" for i in items]
        print(f"  {p:<12} {' '.join(names)}")


def cmd_check(cfg):
    S, P, bad, notes = cfg["services"], cfg["profiles"], [], []
    if cfg.get("default_profile") not in P: bad.append(f"default_profile '{cfg.get('default_profile')}' is not a profile")
    ports = {}
    for n, s in S.items():
        if s["kind"] not in ("proc", "systemd", "script"): bad.append(f"{n}: kind must be proc, systemd or script")
        if s.get("port"): ports.setdefault(s["port"], []).append(n)
        for a in s["after"]:
            if a not in S: bad.append(f"{n}: after '{a}' is not a service")
        try: re.compile(s.get("match", ""))
        except re.error as ex: bad.append(f"{n}: match regex: {ex}")
        if s["kind"] == "proc":
            if not s.get("cmd"): bad.append(f"{n}: proc needs cmd"); continue
            argv, cwd = resolve_cmd(s, Entry(n, s.get("port")))
            if not os.path.isdir(cwd): bad.append(f"{n}: cwd {os.path.relpath(cwd, ROOT)} not found")
            if not (os.path.exists(argv[0]) or shutil.which(argv[0])): bad.append(f"{n}: command not found: {argv[0]}")
            for a in argv[1:]:
                if a.startswith(ROOT) and not os.path.exists(a): bad.append(f"{n}: file not found: {os.path.relpath(a, ROOT)}")
            if s.get("env_file") and not os.path.exists(os.path.join(ROOT, s["env_file"])): notes.append(f"{n}: env_file {s['env_file']} missing (keys it holds will be unset)")
        elif s["kind"] == "systemd":
            if not os.path.exists(f"/etc/systemd/system/{s.get('unit', n)}.service"): bad.append(f"{n}: systemd unit {s.get('unit', n)}.service not installed (demo/lineup.sh install)")
        elif s["kind"] == "script" and not os.path.exists(os.path.join(ROOT, s.get("script", ""))): bad.append(f"{n}: script {s.get('script')} not found")
    for p, ns in ports.items():
        if len(ns) > 1: bad.append(f"port {p} used by {', '.join(ns)}")
    for p, items in P.items():
        try: expand(cfg, [p])
        except SystemExit: bad.append(f"profile {p} has a bad entry")
        for i in items:
            if isinstance(i, dict) and i.get("port") and not S.get(i.get("service"), {}).get("flex"): bad.append(f"profile {p}: {i.get('service')} is not flex, cannot take a port")
    for n in notes: print(f"  {C['y']}note{C['z']}  {n}")
    for b in bad: print(f"  {C['r']}FAIL{C['z']}  {b}")
    print(f"  {len(S)} services, {len(P)} profiles: " + (f"{C['r']}{len(bad)} problem(s){C['z']}" if bad else f"{C['g']}ok{C['z']}"))
    return 1 if bad else 0


# ------------------------------------------------------------------ main
def main(argv):
    o = {"yes": False, "force": False, "dry": False, "port": None}; args = []; follow = False; it = iter(argv)
    for a in it:
        if a in ("-y", "--yes"): o["yes"] = True
        elif a == "--force": o["force"] = True
        elif a == "--dry-run": o["dry"] = True
        elif a == "--port":
            v = next(it, None)
            if not (v and v.isdigit()): die("--port needs a number")
            o["port"] = int(v)
        elif a.startswith("--port="): o["port"] = int(a.split("=", 1)[1])
        elif a in ("-f", "--follow"): follow = True
        elif a in ("-h", "--help"): args.insert(0, "help")
        else: args.append(a)
    cmd, targets = (args[0] if args else "status"), args[1:]
    if cmd == "help":
        try: cfg0 = load()
        except SystemExit: cfg0 = None
        print(help_text(cfg0, targets[0] if targets else None)); return 0
    cfg = load()
    if cmd == "list": cmd_list(cfg); return 0
    if cmd == "check": return cmd_check(cfg)
    if cmd == "logs":
        if not targets or targets[0] not in cfg["services"]: die("usage: ./service.sh logs <service> [-f]   (services: " + " ".join(cfg["services"]) + ")")
        svc = cfg["services"][targets[0]]; e = Entry(targets[0], o["port"] or svc.get("port")); lf = logpath(cfg, e)
        if svc["kind"] == "systemd" and not os.path.exists(lf): lf = os.path.join(ROOT, "logs", f"{targets[0]}.log")
        if not os.path.exists(lf): die(f"no log yet: {lf}")
        os.execvp("tail", ["tail", "-n", "40"] + (["-f"] if follow else []) + [lf])
    if cmd not in ("status", "start", "stop", "restart"):
        print(f"{C['r']}unknown command '{cmd}'{C['z']}\n"); print(help_text(cfg)); return 1
    if cmd in ("stop", "restart") and not targets:
        print(f"{C['r']}{cmd} needs a target.{C['z']} Pick one:\n{targets_text(cfg)}\n\n  e.g. ./service.sh {cmd} demo      more: ./service.sh help {cmd}"); return 1
    if cmd == "start" and not targets: targets = [cfg.get("default_profile") or die("no default_profile in service.yaml")]
    if cmd == "status" and not targets: targets = ["full", "share"] if "full" in cfg["profiles"] else list(cfg["services"])
    entries = expand(cfg, targets)
    if o["port"]:
        if len(entries) != 1 or not cfg["services"][entries[0].name].get("flex"): die("--port needs exactly one flexible service (flex: true)")
        entries[0].port = o["port"]
    if cmd == "status":
        cmd_status(cfg, entries); print(f"\n  {C['d']}Next: ./service.sh start | stop <target> | restart <target> | logs <service> | help{C['z']}"); return 0
    if o["dry"]: print(f"  {C['d']}dry run: nothing will be changed{C['z']}")
    heavy = [e.name for e in entries if cfg["services"][e.name]["heavy"] and e.port == cfg["services"][e.name].get("port")]
    if cmd in ("stop", "restart") and heavy and not o["dry"] and not confirm(f"{cmd} {' '.join(heavy)}? (loaded state is lost; models take a while to come back)", o["yes"]):
        print("cancelled"); return 0
    if cmd == "stop":
        for e in reversed(entries): do_stop(cfg, e, o)
    elif cmd == "restart":
        pending = []
        for e in reversed(entries):                                   # stop in reverse dependency order; a service with its own `restart:` handles itself
            if cfg["services"][e.name].get("restart"): do_restart(cfg, e, o)
            else: do_stop(cfg, e, o); pending.append(e); o.setdefault("stopping", set()).add((e.name, e.port))
        for e in reversed(pending): do_start(cfg, e, o)               # then start in dependency order
    elif cmd == "start":
        for e in entries: do_start(cfg, e, o)
    if not o["dry"]: print(); cmd_status(cfg, entries); print(f"\n  {C['d']}./service.sh help {cmd}  for more examples{C['z']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
