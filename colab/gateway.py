#!/usr/bin/env python3
"""One model at a time behind one TypeSafe-compatible endpoint. Runs on a Colab GPU or any CUDA box.

  POST /v1/systemone   {"state", "questions", "images"?}  -> the loaded model's answer          (needs the key)
  GET  /v1/models      the catalog: what fits this GPU, what is loaded, load time              (needs the key)
  POST /admin/select   {"model": "<id>"}  unload the current model, load another               (needs the key)
  GET  /healthz        200 once a model is loaded, 503 while loading; no secrets

Every response carries X-Model; /v1/systemone also carries X-Latency-Ms (time inside the model). Standard library only.
A model is a recipe in models.json: kind "llama" (a GGUF through llama.cpp) or "proc" (setup commands, then a launch
command that serves /v1/systemone on ${port}). Selecting a model that does not fit the GPU is refused, not attempted.
Env: CLEF_NGL (llama.cpp GPU layers, default 999), CLEF_LOCAL (colon-separated folders that already hold GGUF files).
"""
import argparse, json, os, re, secrets, signal, subprocess, sys, threading, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAX_BODY = 32 * 1024 * 1024  # a few base64 images
HEADROOM_MIB = 800            # CUDA context and the desktop's share: a model must fit with this much to spare


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def gpu_info():
    """(name, total MiB) of GPU 0, or (None, 0) on a CPU-only box."""
    try:
        out = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], text=True, timeout=10)
        name, mib = out.strip().splitlines()[0].rsplit(",", 1)
        return name.strip(), int(mib)
    except Exception:
        return None, 0


def _die_with_parent():
    """The child is killed if the gateway dies (Linux PR_SET_PDEATHSIG). Safe because launches all come from one long-lived thread."""
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").prctl(1, signal.SIGTERM)
    except Exception:
        pass


class Server:
    """A model served by a child process that speaks /v1/systemone on a local port."""

    def __init__(self, entry, cfg):
        self.e, self.cfg, self.proc, self.port = entry, cfg, None, cfg["child_port"]
        self.headers = {"Content-Type": "application/json"}

    def launch(self, cmd, env=None, cwd=None, ready="/healthz", ready_headers=None, wait_s=1200):
        self.log_path = f'{self.cfg["work"]}/{self.e["id"]}.log'
        self.log_f = open(self.log_path, "w")
        self.proc = subprocess.Popen(cmd, env={**os.environ, **(env or {})}, cwd=cwd, stdout=self.log_f, stderr=subprocess.STDOUT,
                                     start_new_session=True, preexec_fn=_die_with_parent)
        for _ in range(wait_s):  # first start on a new GPU can be slow
            if self.proc.poll() is not None:
                tail = Path(self.log_path).read_text()[-600:]
                raise RuntimeError(f"server exited ({self.proc.returncode}); end of {self.log_path}: {tail}")
            try:
                urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{self.port}{ready}", headers=ready_headers or {}), timeout=2)
                return
            except urllib.error.HTTPError as e:
                if e.code < 500:  # up, just not happy with our probe (auth, method)
                    return
            except Exception:
                pass
            time.sleep(1)
        raise RuntimeError(f"server not healthy after {wait_s // 60} minutes; see {self.log_path}")

    def answer(self, body):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/systemone", body, self.headers)
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
                self.proc.wait(30)
            except Exception:
                try:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                except Exception:
                    pass
        self.proc = None


def fetch(repo, name, dest):
    """A file from the Hugging Face Hub, or from a local folder listed in CLEF_LOCAL."""
    for d in filter(None, os.environ.get("CLEF_LOCAL", "").split(":")):
        if (Path(d) / name).exists():
            return str(Path(d) / name)
    from huggingface_hub import hf_hub_download
    return hf_hub_download(repo, name, local_dir=dest)


class Llama(Server):
    """llama.cpp's llama-server: native /v1/systemone, batches across slots, text and images."""

    def start(self):
        e, c = self.e, self.cfg
        model = fetch(e["repo"], e["file"], c["weights"])
        cmd = [c["llama_bin"], "-m", model, "--host", "127.0.0.1", "--port", str(self.port), "--alias", e["id"],
               "-ngl", os.environ.get("CLEF_NGL", "999"), "-c", "65536", "-np", "4",
               "-b", "16384", "-ub", "16384"]  # a decision is scored in one batch, so it must fit (the model's max input is 16384 tokens)
        if e.get("mmproj"):
            cmd += ["--mmproj", fetch(e["repo"], e["mmproj"], c["weights"])]
        lib = str(Path(c["llama_bin"]).resolve().parent)
        self.launch(cmd, {"LD_LIBRARY_PATH": f'{lib}:{os.environ.get("LD_LIBRARY_PATH", "")}'}, ready="/health")


class Proc(Server):
    """Any model with a recipe: run its setup once, then its launch command."""

    def sub(self, s):
        return (s.replace("${ROOT}", self.cfg["root"]).replace("${HERE}", str(HERE)).replace("${port}", str(self.port)))

    def start(self):
        e, c = self.e, self.cfg
        env = {"JEV_ROOT": c["root"], "HF_HOME": f'{c["root"]}/data/models/hf-cache', "PATH": f'{os.path.expanduser("~")}/.local/bin:{os.environ["PATH"]}',
               **{k: self.sub(v) for k, v in e.get("env", {}).items()}}
        marker = Path(c["work"]) / f'{e["id"]}.setup-done'
        if e.get("setup") and not marker.exists():
            log(f'setup {e["id"]} (first time only; installs packages and downloads weights)')
            with open(f'{c["work"]}/{e["id"]}.setup.log', "w") as lf:
                for step in ["command -v uv >/dev/null || pip install -q uv", *map(self.sub, e["setup"])]:
                    r = subprocess.run(["bash", "-c", step], env={**os.environ, **env}, stdout=lf, stderr=subprocess.STDOUT)
                    if r.returncode:
                        raise RuntimeError(f'setup step failed ({r.returncode}): {step}; see {lf.name}')
            marker.touch()
        h = {k: self.sub(v) for k, v in e.get("headers", {}).items()}
        self.headers.update(h)
        self.launch([self.sub(x) for x in e["cmd"]], env, self.sub(e.get("cwd", c["root"])), e.get("health", "/healthz"), h)


KINDS = {"llama": Llama, "proc": Proc}


class Gateway:
    def __init__(self, catalog, cfg):
        self.catalog = {m["id"]: m for m in catalog}
        self.cfg, self.cur, self.cur_id, self.load_s, self.err, self.loading = cfg, None, None, None, None, None
        self.gpu, self.gpu_mib = gpu_info()
        self.pool = ThreadPoolExecutor(1)  # one long-lived thread does every launch (see _die_with_parent)

    def fits(self, m):
        need = m.get("vram_gib", 0) * 1024
        return need == 0 or need + HEADROOM_MIB <= self.gpu_mib

    def _select(self, mid):
        m = self.catalog[mid]
        if self.cur_id == mid and self.cur:
            return
        if m.get("kind") not in KINDS:
            raise RuntimeError(f'{mid} has no recipe yet ({m.get("status", "kind " + str(m.get("kind")))})')
        if not self.fits(m):
            raise MemoryError(f'{mid} needs about {m["vram_gib"]} GiB; this GPU ({self.gpu or "none"}) has {self.gpu_mib / 1024:.1f} GiB')
        self.loading, self.err = mid, None
        try:
            if self.cur:
                log("unload", self.cur_id)
                self.cur.stop()
                self.cur, self.cur_id = None, None
            log("load", mid)
            t = time.time()
            b = KINDS[m["kind"]](m, self.cfg)
            try:
                b.start()
            except Exception:
                b.stop()
                raise
            self.cur, self.cur_id, self.load_s = b, mid, round(time.time() - t, 1)
            log(f"ready {mid} in {self.load_s}s")
        except Exception as e:
            self.err = f"{type(e).__name__}: {e}"
            log("load failed:", self.err[:300])
            raise
        finally:
            self.loading = None

    def select(self, mid):
        if mid not in self.catalog:
            raise KeyError(mid)
        self.pool.submit(self._select, mid).result()

    def status(self):
        return {"gpu": self.gpu, "gpu_gib": round(self.gpu_mib / 1024, 1), "loaded": self.cur_id, "loading": self.loading, "load_s": self.load_s, "error": self.err,
                "models": [{**{k: v for k, v in m.items() if k not in ("setup", "cmd", "env", "headers", "cwd", "health")},
                            "fits": self.fits(m), "loaded": m["id"] == self.cur_id} for m in self.catalog.values()]}

    def shutdown(self):
        if self.cur:
            self.cur.stop()


def handler(gw, key):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, extra=None):
            raw = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("X-Model", str(gw.cur_id))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(raw)

        def _authed(self):
            tok = self.headers.get("Authorization", "").removeprefix("Bearer ").strip() or self.headers.get("X-API-Key", "")
            if not secrets.compare_digest(tok, key):
                self._send(401, {"error": "missing or wrong API key (Authorization: Bearer <key>)"})
                return False
            return True

        def _body(self):
            n = int(self.headers.get("Content-Length", 0))
            if n > MAX_BODY:
                self._send(413, {"error": f"body over {MAX_BODY // 2**20} MB"})
                return None
            return self.rfile.read(n)

        def do_GET(self):
            if self.path.startswith("/healthz"):
                return self._send(200 if gw.cur else 503, {"ok": bool(gw.cur), "loaded": gw.cur_id, "loading": gw.loading})
            if self.path.startswith("/v1/models"):
                return self._send(200, gw.status()) if self._authed() else None
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._authed():
                return
            body = self._body()
            if body is None:
                return
            if self.path == "/admin/select":
                try:
                    gw.select(json.loads(body)["model"])
                except KeyError as e:
                    return self._send(404, {"error": f"unknown model {e}", "models": list(gw.catalog)})
                except MemoryError as e:
                    return self._send(409, {"error": str(e)})
                except Exception as e:
                    return self._send(500, {"error": str(e)[:1500]})
                return self._send(200, gw.status())
            if self.path == "/v1/systemone":
                b = gw.cur
                if not b:
                    return self._send(503, {"error": f"loading {gw.loading}" if gw.loading else "no model loaded yet"}, {"Retry-After": "10"})
                t = time.perf_counter()
                try:
                    code, out = b.answer(body)
                except Exception as e:
                    return self._send(500, {"error": f"{type(e).__name__}: {e}"})
                return self._send(code, out, {"X-Latency-Ms": f"{(time.perf_counter() - t) * 1000:.1f}"})
            self._send(404, {"error": "not found"})

        def log_message(self, *a):
            pass
    return H


def start_tunnel(port, dest, wait=60):
    """A free Cloudflare quick tunnel, for hosts that allow serving (testing only, no uptime promise). Returns (process, https URL).
    Do NOT use this to offer a service from Google Colab: see README, 'Terms'."""
    exe = Path(dest) / "cloudflared"
    if not exe.exists():
        urllib.request.urlretrieve("https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", exe)
        exe.chmod(0o755)
    p = subprocess.Popen([str(exe), "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    url, t0 = None, time.time()
    for line in p.stdout:
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
        if m:
            url = m.group(0)
            break
        if time.time() - t0 > wait or p.poll() is not None:
            break
    if not url:
        p.terminate()
        raise RuntimeError("no tunnel URL appeared; try again in a minute")
    threading.Thread(target=lambda: [None for _ in p.stdout], daemon=True).start()  # keep draining its log
    return p, url


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=str(HERE / "models.json"))
    ap.add_argument("--model", help="load this model at start")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--root", default=str(HERE / "vendor"), help="where models/ and data/ are installed (the JEV_ROOT layout)")
    ap.add_argument("--llama-bin", default=os.environ.get("LLAMA_BIN", "llama-server"))
    ap.add_argument("--work", default=str(HERE / "work"), help="logs, downloaded GGUF files, setup markers")
    ap.add_argument("--key", default=os.environ.get("GATEWAY_KEY") or secrets.token_urlsafe(18))
    ap.add_argument("--tunnel", action="store_true", help="free Cloudflare quick tunnel; only on a host whose terms allow serving")
    a = ap.parse_args()
    Path(a.work).mkdir(parents=True, exist_ok=True)
    cfg = {"llama_bin": a.llama_bin, "weights": a.work + "/weights", "work": a.work, "root": a.root, "child_port": a.port + 1}
    Path(cfg["weights"]).mkdir(parents=True, exist_ok=True)
    gw = Gateway(json.loads(Path(a.catalog).read_text())["models"], cfg)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), handler(gw, a.key))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    info = {"local": f"http://127.0.0.1:{a.port}", "key": a.key, "gpu": gw.gpu, "gpu_gib": round(gw.gpu_mib / 1024, 1)}
    if a.tunnel:
        _, info["url"] = start_tunnel(a.port, a.work)
    print("GATEWAY " + json.dumps(info), flush=True)
    try:
        if a.model:
            gw.select(a.model)
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        gw.shutdown()


if __name__ == "__main__":
    main()
