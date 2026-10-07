"""How a model is served: a child process that speaks /v1/systemone on a local port.

Two kinds. "llama" runs llama.cpp's llama-server on a GGUF file. "proc" runs a recipe from models.json:
setup commands once, then a launch command. Both are started, probed until healthy, proxied to, and stopped here.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import DATA
from .catalog import gpu_info, gpu_used_mib
from .download import download

DOWNLOAD_TRIES = 3
SLOTS = 4  # requests the llama.cpp server works on at once (-np); more than this wait in its queue
PROBE_SECONDS = 1200  # a first start (installs, downloads, GPU kernel compile) can take many minutes
WARM_BODY = b'{"state": "warm-up", "questions": {"q": {"type": "noul", "instructions": "Is this a test?"}}}'


_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def last_line(path: str | Path, width: int = 110) -> str:
    """The latest meaningful line of a log: what a long step is doing right now. Progress bars rewrite one line with carriage returns, so
    the log is split on those too; colour codes are dropped; an empty or missing log gives an empty string."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 4096))
            text = f.read().decode("utf-8", "replace")
    except OSError:
        return ""
    for piece in reversed(re.split(r"[\r\n]+", _ANSI.sub("", text))):
        if piece.strip():
            return piece.strip()[:width]
    return ""


def with_model(body: bytes, model: str) -> bytes:
    """Add `"model"` to a request that lacks it. The TypeSafe wire format has the field and some servers (jeff) require it; callers of this
    gateway should not have to know. A body that is not a JSON object is passed through for the server to refuse."""
    try:
        data = json.loads(body)
    except ValueError:
        return body
    if not isinstance(data, dict) or "model" in data:
        return body
    return json.dumps({**data, "model": model}).encode()


def install_vendor(root: Path) -> None:
    """Copy the vendored model servers and benchmark adapters into the install root, where the recipes expect them.

    The scripts are replaced on every start so an upgraded package takes effect; environments and weights beside them are left alone.
    """
    source = DATA / "vendor"
    root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "dev-bench-setup.sh", root / "dev-bench-setup.sh")
    for folder in ("demo", "jevbench"):
        shutil.copytree(source / folder, root / folder, dirs_exist_ok=True)


RECENT_EVENT: tuple[float, str] = (0.0, "")  # the latest line logged, for the progress detail


def log(*args) -> None:
    global RECENT_EVENT
    RECENT_EVENT = (time.time(), " ".join(str(a) for a in args))
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


def require_gpu(llama_bin: str) -> None:
    """Refuse to continue unless there is a GPU and llama.cpp can see it. Models run on the GPU only: a CPU run would take
    minutes per answer, and nobody should wait through a download to find that out. JEVGW_ALLOW_CPU=1 is for development machines."""
    if os.environ.get("JEVGW_ALLOW_CPU") == "1":
        return
    if not gpu_info()[0]:
        raise RuntimeError(
            "no GPU on this machine. These models run on a GPU only. On Colab: Runtime > Change runtime type > T4 GPU."
        )
    if not gpu_visible(llama_bin):
        raise RuntimeError(
            "llama.cpp cannot see this machine's GPU (`llama-server --list-devices` shows no CUDA device), so it would run on the CPU, "
            "many times slower. Its CUDA libraries probably failed to load: run `ldd libggml-cuda.so | grep 'not found'` in "
            f"{Path(llama_bin).parent}. On Colab, step 3 of the notebook fetches the missing CUDA 12 libraries."
        )


def gpu_visible(llama_bin: str) -> bool:
    """True if llama.cpp can see a CUDA device.

    A build whose CUDA libraries fail to load does not fail: it runs on the CPU, many times slower, and says nothing.
    """
    lib = str(Path(llama_bin).resolve().parent)
    env = {**os.environ, "LD_LIBRARY_PATH": f"{lib}:{os.environ.get('LD_LIBRARY_PATH', '')}"}
    try:
        out = subprocess.run([llama_bin, "--list-devices"], env=env, capture_output=True, text=True, timeout=120).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "CUDA" in out


class Server:
    """A model served by a child process."""

    def __init__(self, entry: dict, cfg: dict):
        self.entry, self.cfg, self.port = entry, cfg, cfg["child_port"]
        self.proc: subprocess.Popen | None = None
        self.headers = {"Content-Type": "application/json"}
        self._local = threading.local()  # one kept-alive connection per gateway worker thread

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
        """Forward one /v1/systemone request. Returns (status, body).

        Each gateway worker thread keeps one connection open to the model server instead of opening a new one per call (about 45 ms
        saved on every request). A connection the server closed while idle is replaced once; anything else is raised.
        """
        if self.entry.get("default_model"):
            body = with_model(body, self.entry["default_model"])
        for attempt in (1, 2):
            conn = getattr(self._local, "conn", None)
            if conn is None:
                conn = self._local.conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=300)
            try:
                conn.request("POST", "/v1/systemone", body, self.headers)
                response = conn.getresponse()
                return response.status, response.read()
            except (http.client.RemoteDisconnected, BrokenPipeError, ConnectionResetError, http.client.CannotSendRequest):
                conn.close()
                self._local.conn = None
                if attempt == 2:
                    raise
            except Exception:
                conn.close()
                self._local.conn = None
                raise
        raise AssertionError("unreachable")

    def expected_gpu_mib(self) -> float:
        """The least GPU memory the loaded model should hold, in MiB. 0 skips the check."""
        return 0.0

    def verify_gpu(self, used_before: int | None) -> None:
        """After the model is loaded and has answered once, the GPU must hold it: its memory use must have grown by most of the model's size.

        Read from nvidia-smi, not from a log whose wording changes between builds. A model that went to the CPU leaves the GPU untouched and
        would answer far too slowly.
        """
        used_after, expected = gpu_used_mib(), self.expected_gpu_mib()
        if os.environ.get("JEVGW_ALLOW_CPU") == "1" or used_before is None or used_after is None or not expected:
            return
        if used_after - used_before < 0.6 * expected:
            raise RuntimeError(
                f"{self.entry['id']} started but the GPU holds only {max(used_after - used_before, 0)} MiB more than before, against about "
                f"{expected:.0f} MiB expected: it is running on the CPU. Stopped; see {self.log_path}"
            )

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
    """A file from the Hugging Face Hub (see download.py: standard library only), or from a folder listed in CLEF_LOCAL (colon-separated) that already holds it."""
    for folder in filter(None, os.environ.get("CLEF_LOCAL", "").split(":")):
        if (Path(folder) / name).exists():
            return str(Path(folder) / name)
    return download(repo, name, dest, DOWNLOAD_TRIES, log=log)


class Llama(Server):
    """llama.cpp's llama-server: native /v1/systemone, batches across slots, text and images."""

    def start(self) -> None:
        entry, cfg = self.entry, self.cfg
        require_gpu(cfg["llama_bin"])  # before anything is downloaded
        model = fetch(entry["repo"], entry["file"], cfg["weights"])
        cmd = [
            cfg["llama_bin"], "-m", model, "--host", "127.0.0.1", "--port", str(self.port), "--alias", entry["id"],
            "-ngl", "999", "-c", "65536", "-np", str(SLOTS),
            # a decision is scored in one batch, so it must fit: the model's maximum input is 16384 tokens
            "-b", "16384", "-ub", "16384",
        ]  # fmt: skip
        if entry.get("mmproj"):
            cmd += ["--mmproj", fetch(entry["repo"], entry["mmproj"], cfg["weights"])]
        lib = str(Path(cfg["llama_bin"]).resolve().parent)
        env = {"LD_LIBRARY_PATH": f"{lib}:{os.environ.get('LD_LIBRARY_PATH', '')}"}
        self.launch(cmd, env, ready="/health")

    def expected_gpu_mib(self) -> float:
        return (self.entry.get("file_gib", 0) + self.entry.get("mmproj_gib", 0)) * 1024


class Proc(Server):
    """Any model with a recipe: run its setup once, then its launch command."""

    def expected_gpu_mib(self) -> float:
        """The measured resident size on a T4 (`resident_gib`), else 30% of the peak, which includes working memory."""
        return (self.entry.get("resident_gib") or 0.3 * self.entry.get("vram_gib", 0)) * 1024

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
                    raise RuntimeError(
                        f"setup step failed ({result.returncode}): {step}\n  last line: {last_line(setup_log, 200)}\n  full log: {setup_log}"
                    )


KINDS = {"llama": Llama, "proc": Proc}
