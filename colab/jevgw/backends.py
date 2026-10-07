"""How a model is served: a child process that speaks /v1/systemone on a local port.

Two kinds. "llama" runs llama.cpp's llama-server on a GGUF file. "proc" runs a recipe from models.json:
setup commands once, then a launch command. Both are started, probed until healthy, proxied to, and stopped here.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

PROBE_SECONDS = 1200  # a first start (installs, downloads, GPU kernel compile) can take many minutes
WARM_BODY = b'{"state": "warm-up", "questions": {"q": {"type": "noul", "instructions": "Is this a test?"}}}'


def log(*args) -> None:
    print(time.strftime("%H:%M:%S"), *args, flush=True)


def _die_with_parent() -> None:
    """Kill the child if the gateway dies (Linux PR_SET_PDEATHSIG).

    Safe only because every launch comes from one long-lived thread: the signal fires when the thread that forked exits.
    """
    try:
        import ctypes

        ctypes.CDLL("libc.so.6").prctl(1, signal.SIGTERM)
    except (OSError, AttributeError):
        pass


class Server:
    """A model served by a child process."""

    def __init__(self, entry: dict, cfg: dict):
        self.entry, self.cfg, self.port = entry, cfg, cfg["child_port"]
        self.proc: subprocess.Popen | None = None
        self.headers = {"Content-Type": "application/json"}

    def launch(self, cmd, env=None, cwd=None, ready="/healthz", ready_headers=None, wait_s=PROBE_SECONDS) -> None:
        """Start the process and block until `ready` answers, or raise with the end of its log."""
        self.log_path = Path(self.cfg["work"]) / f"{self.entry['id']}.log"
        with open(self.log_path, "w") as log_file:
            self.proc = subprocess.Popen(
                cmd,
                env={**os.environ, **(env or {})},
                cwd=cwd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                preexec_fn=_die_with_parent,
            )
        for _ in range(wait_s):
            if self.proc.poll() is not None:
                raise RuntimeError(f"server exited ({self.proc.returncode}); end of {self.log_path}:\n{self._tail()}")
            if self._up(ready, ready_headers):
                return
            time.sleep(1)
        raise RuntimeError(f"server not healthy after {wait_s // 60} minutes; see {self.log_path}")

    def _tail(self, chars=600) -> str:
        return self.log_path.read_text()[-chars:]

    def _up(self, path, headers) -> bool:
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers=headers or {})
        try:
            urllib.request.urlopen(request, timeout=2)
            return True
        except urllib.error.HTTPError as err:
            return err.code < 500  # up, just not happy with our probe (auth, method)
        except OSError:
            return False

    def answer(self, body: bytes) -> tuple[int, bytes]:
        """Forward one /v1/systemone request. Returns (status, body)."""
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/systemone", body, self.headers)
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as err:
            return err.code, err.read()

    def warm(self) -> float:
        """One throwaway request so the first real call is not the cold one. Returns milliseconds; failures are ignored."""
        start = time.perf_counter()
        with contextlib.suppress(OSError):
            self.answer(WARM_BODY)
        return (time.perf_counter() - start) * 1000

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
                self.proc.wait(30)
            except (OSError, subprocess.TimeoutExpired):
                with contextlib.suppress(OSError):
                    os.killpg(self.proc.pid, signal.SIGKILL)
        self.proc = None


def fetch(repo: str, name: str, dest: str) -> str:
    """A file from the Hugging Face Hub, or from a folder listed in CLEF_LOCAL (colon-separated) that already holds it."""
    for folder in filter(None, os.environ.get("CLEF_LOCAL", "").split(":")):
        if (Path(folder) / name).exists():
            return str(Path(folder) / name)
    from huggingface_hub import hf_hub_download

    return hf_hub_download(repo, name, local_dir=dest)


class Llama(Server):
    """llama.cpp's llama-server: native /v1/systemone, batches across slots, text and images."""

    def start(self) -> None:
        entry, cfg = self.entry, self.cfg
        model = fetch(entry["repo"], entry["file"], cfg["weights"])
        cmd = [
            cfg["llama_bin"], "-m", model, "--host", "127.0.0.1", "--port", str(self.port), "--alias", entry["id"],
            "-ngl", os.environ.get("CLEF_NGL", "999"), "-c", "65536", "-np", "4",
            # a decision is scored in one batch, so it must fit: the model's maximum input is 16384 tokens
            "-b", "16384", "-ub", "16384",
        ]  # fmt: skip
        if entry.get("mmproj"):
            cmd += ["--mmproj", fetch(entry["repo"], entry["mmproj"], cfg["weights"])]
        lib = str(Path(cfg["llama_bin"]).resolve().parent)
        env = {"LD_LIBRARY_PATH": f"{lib}:{os.environ.get('LD_LIBRARY_PATH', '')}"}
        self.launch(cmd, env, ready="/health")


class Proc(Server):
    """Any model with a recipe: run its setup once, then its launch command."""

    def sub(self, text: str) -> str:
        return text.replace("${ROOT}", self.cfg["root"]).replace("${HERE}", self.cfg["here"]).replace("${port}", str(self.port))

    def start(self) -> None:
        entry, cfg = self.entry, self.cfg
        env = {
            "JEV_ROOT": cfg["root"],
            "HF_HOME": f"{cfg['root']}/data/models/hf-cache",
            "PATH": f"{os.path.expanduser('~')}/.local/bin:{os.environ['PATH']}",
            **{key: self.sub(value) for key, value in entry.get("env", {}).items()},
        }
        marker = Path(cfg["work"]) / f"{entry['id']}.setup-done"
        if entry.get("setup") and not marker.exists():
            self._setup(entry, env)
            marker.touch()
        headers = {key: self.sub(value) for key, value in entry.get("headers", {}).items()}
        self.headers.update(headers)
        cwd = self.sub(entry.get("cwd", cfg["root"]))
        self.launch([self.sub(part) for part in entry["cmd"]], env, cwd, entry.get("health", "/healthz"), headers)

    def _setup(self, entry: dict, env: dict) -> None:
        log(f"setup {entry['id']} (first time only: installs packages and downloads weights)")
        steps = ["command -v uv >/dev/null || pip install -q uv", *map(self.sub, entry["setup"])]
        setup_log = Path(self.cfg["work"]) / f"{entry['id']}.setup.log"
        with open(setup_log, "w") as out:
            for step in steps:
                result = subprocess.run(["bash", "-c", step], env={**os.environ, **env}, stdout=out, stderr=subprocess.STDOUT)
                if result.returncode:
                    raise RuntimeError(f"setup step failed ({result.returncode}): {step}; see {setup_log}")


KINDS = {"llama": Llama, "proc": Proc}
