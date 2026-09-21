"""Measure the real GPU memory each model needs, one model at a time on an otherwise idle GPU.

    sudo-free, run as root:  systemctl stop kev-proxy kev jeff; (kill any kev.serve on :8010/:8011); python3 demo/vram.py

For every model we start it the way the console runs it, then sample nvidia-smi for that process (and its children) while a
workload runs: long single-question inputs (websec, up to 1,500 characters) and the 9-question call-monitor battery.
"loaded" is the process's memory after load and warm-up, before the workload; "peak" is the maximum seen. Both include the
CUDA context. In-process models run through the same jevbench command the benchmark used. Output: demo/vram.json.
"""
import json, os, re, signal, statistics, subprocess, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "probes" / "v2"
M = ROOT / "models"
OUT = ROOT / "demo" / "vram.json"
SMI = ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"]


def gpu_total():
    o = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader,nounits"], text=True).split(",")
    return o[0].strip(), int(o[1]), int(o[2])


def descendants(pid):
    kids = {}
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                ppid = int(open(f"/proc/{d}/stat").read().rsplit(")", 1)[1].split()[1])
                kids.setdefault(ppid, []).append(int(d))
            except (OSError, IndexError, ValueError):
                pass
    out, todo = {pid}, [pid]
    while todo:
        for k in kids.get(todo.pop(), []):
            if k not in out:
                out.add(k); todo.append(k)
    return out


def rss_mb(pids):
    total = 0
    for p in pids:
        try:
            total += int(re.search(r"VmRSS:\s+(\d+)", open(f"/proc/{p}/status").read()).group(1)) // 1024
        except (OSError, AttributeError):
            pass
    return total


class Sampler(threading.Thread):
    def __init__(self, pid):
        super().__init__(daemon=True); self.pid, self.stop, self.gpu, self.rss = pid, threading.Event(), [], []

    def run(self):
        while not self.stop.is_set():
            pids = descendants(self.pid)
            try:
                rows = subprocess.check_output(SMI, text=True).strip().splitlines()
                self.gpu.append(sum(int(r.split(",")[1]) for r in rows if r and int(r.split(",")[0]) in pids))
            except (subprocess.CalledProcessError, ValueError):
                pass
            self.rss.append(rss_mb(pids)); time.sleep(0.2)


def jl(name):
    return [json.loads(l) for l in (P / f"{name}.jsonl").read_text().splitlines()]


def post(url, body, headers=None, timeout=300):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def battery():
    first = lambda f: jl(f)[0]["question"]
    qs = {"manipulation": "manipulation_dialogue", "phishing": "phishing", "sarcasm": "sarcasm_isarcasm", "threat": "threat_civil", "anger": "emotion_anger",
          "fear": "emotion_fear", "politeness": "politeness_deference", "darkpatterns": "darkpatterns", "persuasion": "persuasion_appeals"}
    return {k: first(v) for k, v in qs.items()}


def served_workload(base, headers):
    """Long single-question inputs, then the 9-question battery on long states with 4 in flight."""
    web = [r for r in jl("websec")]
    bat = battery()
    for r in web[:3]:  # warm-up (kernel compilation, allocator)
        post(base + "/v1/systemone", {"state": r["state"], "model": "jev-latest", "questions": {"d": r["question"]}}, headers)
    yield "warm"
    for r in sorted(web, key=lambda r: -len(r["state"]))[:40]:
        post(base + "/v1/systemone", {"state": r["state"], "model": "jev-latest", "questions": {"d": r["question"]}}, headers)
    long_states = [r["state"] for r in sorted(jl("checklist_contractnli"), key=lambda r: -len(r["state"]))[:24]]
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda s: post(base + "/v1/systemone", {"state": s, "model": "jev-latest", "questions": bat}, headers), long_states))
    yield "done"


def wait_ready(url, headers, timeout=400):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=3); return time.time() - t0
        except Exception as e:
            if getattr(e, "code", 0) in (401, 403): return time.time() - t0
            time.sleep(1)
    raise TimeoutError(url)


def measure_served(name, cmd, env, cwd, base, ready_url, headers):
    proc = subprocess.Popen(cmd, env={**os.environ, **env}, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    smp = Sampler(proc.pid); smp.start(); t0 = time.time()
    try:
        load_s = wait_ready(ready_url, headers); time.sleep(3)
        idle = list(smp.gpu)
        stages = served_workload(base, headers); next(stages)
        loaded = statistics.median(smp.gpu[-8:]) if smp.gpu else 0; mark = len(smp.gpu)
        next(stages, None)
        work = smp.gpu[mark:] or [0]
        return {"kind": "server", "load_s": round(load_s, 1), "gpu_loaded_mb": int(loaded), "gpu_peak_mb": max(smp.gpu or [0]), "gpu_workload_peak_mb": max(work),
                "cpu_rss_peak_mb": max(smp.rss or [0]), "workload_s": round(time.time() - t0 - load_s, 1)}
    finally:
        smp.stop.set(); os.killpg(proc.pid, signal.SIGTERM); proc.wait(timeout=60); time.sleep(4)


def measure_inprocess(name, adapter, endpoint, extra=()):
    env = {**os.environ, "HF_HOME": str(ROOT / "data/models/hf-cache"), "JEVBENCH_WARM_LOAD": "1", "PYTHONPATH": str(ROOT / "jevbench")}
    out = Path("/tmp/vram-run") / name
    subprocess.run(["rm", "-rf", str(out)])
    cmd = [str(M / name / ".venv/bin/python"), "-m", "jevbench.cli", "run", "--tasks", str(P / "websec.jsonl"), "--adapter", adapter, "--endpoint", endpoint, "--model", name,
           *extra, "--cost-basis", "local_cpu_no_provider_tariff", "--reserve-usd", "0", "--cap-usd", "1", "--results", f"{out}/r.jsonl", "--raw-dir", f"{out}/raw",
           "--ledger", f"{out}/l.jsonl", "--manifest", f"{out}/m.json"]
    t0 = time.time()
    proc = subprocess.Popen(cmd, env=env, cwd=ROOT / "jevbench", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    smp = Sampler(proc.pid); smp.start(); log = proc.communicate()[0]; smp.stop.set(); time.sleep(0.5)
    m = re.search(r"warm load ([\d.]+)s", log); half = smp.gpu[len(smp.gpu) // 2:] or [0]
    return {"kind": "in-process", "load_s": float(m.group(1)) if m else None, "gpu_loaded_mb": int(statistics.median(half)), "gpu_peak_mb": max(smp.gpu or [0]),
            "gpu_workload_peak_mb": max(smp.gpu or [0]), "cpu_rss_peak_mb": max(smp.rss or [0]), "workload_s": round(time.time() - t0, 1), "items": 80}


def main():
    name, total0, total = gpu_total()
    if total0 > 600:
        sys.exit(f"GPU is not idle ({total0} MiB in use). Stop the model servers first.")
    kev_env = {"HF_HOME": str(ROOT / "data/kev/hf-cache"), "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}
    kevpy = str(ROOT / "kev/.venv/bin/python")
    jobs = {
        "jeff": lambda: measure_served("jeff", [str(ROOT / "jeff/.venv/bin/jeff")], {"JEFF_HOST": "127.0.0.1", "JEFF_PORT": "8000", "JEFF_API_KEYS": "devkey", "JEFF_DEVICE": "cuda",
                 "JEFF_MODEL": str(ROOT / "data/jeff/models/gliformer-large-v1"), "HF_HOME": str(ROOT / "data/jeff/hf-cache")}, ROOT / "jeff", "http://127.0.0.1:8000", "http://127.0.0.1:8000/healthz", {"Authorization": "Bearer devkey"}),
        "kev-0.5b": lambda: measure_served("kev-0.5b", [kevpy, "-m", "kev.serve", "--run", str(ROOT / "data/kev/runs/kev"), "--port", "8008"], kev_env, ROOT / "kev", "http://127.0.0.1:8008", "http://127.0.0.1:8008/v1/models", {}),
        "kev-0.8b": lambda: measure_served("kev-0.8b", [kevpy, "-m", "kev.serve", "--run", "jaredpalmer/kev-0.8b", "--port", "8011"], kev_env, ROOT / "kev", "http://127.0.0.1:8011", "http://127.0.0.1:8011/v1/models", {}),
        "kev-4b": lambda: measure_served("kev-4b", [kevpy, "-m", "kev.serve", "--run", "jaredpalmer/kev-4b", "--port", "8010"], kev_env, ROOT / "kev", "http://127.0.0.1:8010", "http://127.0.0.1:8010/v1/models", {}),
        "semif": lambda: measure_inprocess("semif", "semif_direct", "Qwen/Qwen3.5-4B", ["--revision", subprocess.check_output("ls " + str(ROOT / "data/models/hf-cache/hub/models--Qwen--Qwen3.5-4B/snapshots"), shell=True, text=True).split()[0]]),
        "so1": lambda: measure_inprocess("so1", "so1_decider", "Qwen/Qwen3.5-4B"),
        "laya": lambda: measure_inprocess("laya", "laya_local", str(ROOT / "data/models/laya")),
        "verdict": lambda: measure_inprocess("verdict", "verdict_local", str(ROOT / "data/models/verdict")),
    }
    for tag, run, port in (("kev-4b", "jaredpalmer/kev-4b", "8010"), ("kev-0.8b", "jaredpalmer/kev-0.8b", "8011"), ("kev-0.5b", str(ROOT / "data/kev/runs/kev"), "8008")):
        jobs[tag + "-bf16"] = (lambda tag=tag, run=run, port=port: measure_served(tag + "-bf16", [kevpy, str(ROOT / "demo/serve_kev.py"), "--run", run, "--port", port], {**kev_env, "KEV_DTYPE": "bf16"},
                               ROOT / "kev", f"http://127.0.0.1:{port}", f"http://127.0.0.1:{port}/v1/models", {}))
    only = sys.argv[1:] or [k for k in jobs if not k.endswith("-bf16")]
    res = json.loads(OUT.read_text())["models"] if OUT.exists() and sys.argv[1:] else {}
    for k in only:
        print(f"== {k}", flush=True)
        res[k] = jobs[k](); print("  ", res[k], flush=True)
    OUT.write_text(json.dumps({"gpu": name, "gpu_total_mb": total, "measured": time.strftime("%Y-%m-%d"),
        "method": "nvidia-smi per-process memory (includes the CUDA context) sampled every 0.2 s while the model handles long single-question inputs and the 9-question battery (served models) or the 80-item websec set (in-process models). loaded = after load and warm-up; peak = maximum seen.",
        "models": res}, indent=2))


if __name__ == "__main__":
    main()
