# Kaggle kernel: Clef Flash Q4_K_M on llama.cpp b11430, one server per T4, then the SAME clef_label.py (D-0038). Input rows are given by the dataset (train OR test, never both).
import os, sys, json, glob, time, subprocess, tarfile, urllib.request
MAXMIN = int(os.environ.get("LABEL_MAX_MIN", "__MAXMIN__")); guard(max_min=MAXMIN, idle_min=6)
T0 = time.time(); NAME = "__NAME__"; WORKERS = __WORKERS__; LABEL_MIN = __LABELMIN__
def sh(c, **k): print("$", c, flush=True); return subprocess.run(c, shell=True, **k)
def phase(m): beat(m); print(f"[phase] {m} t={time.time() - T0:.0f}s", flush=True)
sh("find /kaggle/input -maxdepth 3 | head -30"); os.makedirs("/workspace", exist_ok=True)
tg = glob.glob("/kaggle/input/**/pkg.tar*", recursive=True)
if tg and os.path.isfile(tg[0]): tarfile.open(tg[0]).extractall("/workspace")
else:
    off = glob.glob("/kaggle/input/**/probes/persona/offline.py", recursive=True)[0]; root = off.rsplit("/probes/", 1)[0]; sh(f"cp -r {root}/. /workspace/")
phase("package extracted")
L = "https://github.com/ggml-org/llama.cpp/releases/download/b11430"
sh(f"mkdir -p /tmp/ll && cd /tmp/ll && curl -sL {L}/llama-b11430-bin-ubuntu-cuda-12.8-x64.tar.gz | tar xz && curl -sL {L}/cudart-llama-b11430-bin-ubuntu-cuda-12.8-x64.tar.gz | tar xz"); phase("llama.cpp downloaded")
BIN = glob.glob("/tmp/ll/llama-b11430/llama-server")[0]; LLD = os.path.dirname(BIN)
LIBS = ":".join({os.path.dirname(p) for p in glob.glob("/tmp/ll/**/libcudart*", recursive=True)} | {LLD})
if not os.path.exists(f"{LLD}/clef-flash-q4km"): os.symlink(BIN, f"{LLD}/clef-flash-q4km")
G = "/tmp/Cloudflare_clef-flash-Q4_K_M.gguf"; t = time.time()
sh(f"curl -sL -o {G} https://huggingface.co/bartowski/Cloudflare_clef-flash-GGUF/resolve/main/Cloudflare_clef-flash-Q4_K_M.gguf; ls -la {G}"); phase(f"gguf downloaded in {time.time() - t:.0f}s")
ng = len([l for l in subprocess.run("nvidia-smi -L", shell=True, capture_output=True, text=True).stdout.splitlines() if "GPU" in l]) or 1; print("GPUs:", ng, flush=True)
srv = []
for g in range(ng):      # one independent server per GPU (not a layer split): they run in parallel
    env = dict(os.environ, LD_LIBRARY_PATH=LIBS + ":" + os.environ.get("LD_LIBRARY_PATH", ""), CUDA_VISIBLE_DEVICES=str(g))
    srv.append(subprocess.Popen([f"{LLD}/clef-flash-q4km", "-m", G, "--alias", "clef-flash-q4km", "--host", "127.0.0.1", "--port", str(8018 + g), "-ngl", "999", "-c", "65536", "-np", "8", "-b", "8192", "-ub", "8192"], env=env, stdout=open(f"/kaggle/working/server{g}.log", "w"), stderr=subprocess.STDOUT))
for g in range(ng):
    for i in range(240):
        try: urllib.request.urlopen(f"http://127.0.0.1:{8018 + g}/health", timeout=2); break
        except Exception:
            time.sleep(2)
            if i % 5 == 0: beat("waiting for server")
    else: print(open(f"/kaggle/working/server{g}.log").read()[-3000:]); raise SystemExit("server did not start")
phase("servers up"); sh("nvidia-smi --query-gpu=name,memory.used --format=csv,noheader")
inp = glob.glob("/kaggle/input/**/stories.jsonl", recursive=True)[0]; rows = open(inp).read().splitlines()
procs = []; t = time.time()
for g in range(ng):
    part = f"/tmp/part{g}.jsonl"; open(part, "w").write("\n".join(rows[g::ng]) + "\n"); out = f"/kaggle/working/kaggle_{NAME}_g{g}.jsonl"
    procs.append((g, out, subprocess.Popen(f"cd /workspace && CLEF_PORT={8018 + g} WE_RULES=rules_v2 WORLD_GPU=0 python3 newsreader/bitmob/clef_label.py {part} {out} --n 100000 --workers {WORKERS} --minutes {LABEL_MIN} --job k{g}", shell=True)))
cnt = lambda: sum(sum(1 for _ in open(o)) for _, o, _ in procs if os.path.exists(o))
while any(p.poll() is None for _, _, p in procs): time.sleep(15); beat(f"labelling: {cnt()} done")
el = time.time() - t; k = cnt(); print(f"[rate] gpus={ng} workers/server={WORKERS} stories={k} wall={el:.0f}s stories_per_min={60 * k / el:.2f}", flush=True)
with open(f"/kaggle/working/kaggle_{NAME}.jsonl", "w") as f:
    for _, o, _ in procs: f.write(open(o).read() if os.path.exists(o) else "")
for p in srv: p.terminate()
phase("done")
