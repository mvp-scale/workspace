"""Helpers for the Colab notebook. Every function is safe to call again: re-running a cell never needs an "undo" first.

ensure_llama()   install the llama.cpp server, or notice it is already installed and working
start()          start the gateway, or reuse the one already running (same port, same key)
wait_ready()     load a model in the background, show download progress, retry a failed load
stop()           stop the gateway (and with it the model server and the tunnel)
reset()          stop everything and clear the half-finished state, optionally deleting downloaded models
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .client import Client

APP = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("JEVGW_WORK", "/content/work"))  # logs, state and downloaded models
LLAMA_DIR = Path(os.environ.get("JEVGW_LLAMA", "/content/llama"))


def _say(*parts) -> None:
    print(*parts, flush=True)


# -- llama.cpp ---------------------------------------------------------------------------------------------------------


def _llama_works(binary: Path) -> bool:
    try:
        env = {**os.environ, "LD_LIBRARY_PATH": f"{binary.parent}:{os.environ.get('LD_LIBRARY_PATH', '')}"}
        return subprocess.run([str(binary), "--version"], env=env, capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def ensure_llama(t4_url: str = "") -> str:
    """The path to a working llama-server. A missing, half-downloaded or broken install is removed and done again."""
    binary = LLAMA_DIR / "bin" / "llama-server"
    if binary.exists() and _llama_works(binary):
        _say("llama.cpp is already installed:", binary)
        return str(binary)
    if LLAMA_DIR.exists():
        _say("removing a broken llama.cpp install and starting it again")
        shutil.rmtree(LLAMA_DIR)
    _say("installing llama.cpp (about a minute)")
    result = subprocess.run(
        ["bash", str(APP / "setup_llama.sh")],
        capture_output=True,
        text=True,
        env={**os.environ, "LLAMA_DIR": str(LLAMA_DIR), "LLAMA_T4_URL": t4_url},
    )
    if result.stderr.strip():
        _say(result.stderr.strip())
    if result.returncode:
        raise RuntimeError("llama.cpp install failed; run this cell again to retry.\n" + (result.stdout + result.stderr)[-1500:])
    return result.stdout.strip().splitlines()[-1]


# -- the gateway process -----------------------------------------------------------------------------------------------


def _state_file() -> Path:
    return WORK / "gateway.json"


def _read_state() -> dict | None:
    try:
        return json.loads(_state_file().read_text())
    except (OSError, ValueError):
        return None


def _alive(pid: int) -> bool:
    """True if the process is running. A child of this kernel that has exited is reaped here, so it never looks alive."""
    try:
        if os.waitpid(pid, os.WNOHANG)[0]:
            return False
    except ChildProcessError:
        pass  # not our child: fall through to the plain check
    except OSError:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _is_ours(port: int) -> bool:
    """True if a jevgw gateway answers on the port (a 503 with its JSON body counts: it is up, just no model yet)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=3) as response:
            body = response.read()
    except urllib.error.HTTPError as err:
        body = err.read()
    except OSError:
        return False
    try:
        return "loaded" in json.loads(body)
    except ValueError:
        return False


def _free_port(preferred: int) -> int:
    for port in range(preferred, preferred + 50):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"no free port from {preferred} to {preferred + 49}")


def start(llama_bin: str, keep: int = 2, port: int = 8000, key: str = "") -> tuple[Client, dict]:
    """Start the gateway, or reuse the running one. Returns (client, {"port", "key", "reused"}). The key is printed.

    `key` is the API key to use; leave it empty to get a random one. A running gateway with a different key is replaced.
    A gateway left by an earlier run of this cell is reused if it still answers, and stopped if it does not. A busy port is skipped.
    """
    state = _read_state()
    if state and _alive(state["pid"]) and _is_ours(state["port"]) and key in ("", state["key"]):
        _say(f"the gateway is already running on port {state['port']}; reusing it")
        _say(f"API key: {state['key']}")
        return Client(f"http://127.0.0.1:{state['port']}", state["key"]), {**state, "reused": True}
    stop()
    WORK.mkdir(parents=True, exist_ok=True)
    port, key = _free_port(port), key or secrets.token_urlsafe(12)
    log_path = WORK / "gateway.log"
    with open(log_path, "w") as log:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "jevgw",
                "--port",
                str(port),
                "--key",
                key,
                "--llama-bin",
                llama_bin,
                "--work",
                str(WORK),
                "--keep",
                str(keep),
            ],
            cwd=APP,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    for _ in range(60):
        if proc.poll() is not None:
            raise RuntimeError(f"the gateway exited ({proc.returncode}); run this cell again.\n{log_path.read_text()[-1500:]}")
        if _is_ours(port):
            break
        time.sleep(1)
    else:
        proc.terminate()
        raise RuntimeError(f"the gateway did not answer within a minute; see {log_path}")
    state = {"pid": proc.pid, "port": port, "key": key}
    _state_file().write_text(json.dumps(state))
    _say(f"the gateway is running on port {port}")
    _say(f"API key: {key}")
    return Client(f"http://127.0.0.1:{port}", key), {**state, "reused": False}


def show_panel(info: dict) -> None:
    """The control panel inside the notebook (on Colab), or its address anywhere else."""
    try:
        from google.colab import output

        output.serve_kernel_port_as_iframe(info["port"], path=f"/#key={info['key']}", height="900")
    except ImportError:
        _say(f"panel: http://127.0.0.1:{info['port']}/#key={info['key']}")


def stop() -> None:
    """Stop the gateway if one is running. The model server and the tunnel stop with it. Does nothing if none is."""
    state = _read_state()
    if state and _alive(state["pid"]):
        with contextlib.suppress(OSError):
            os.kill(state["pid"], signal.SIGTERM)
        for _ in range(40):
            if not _alive(state["pid"]):
                break
            time.sleep(0.5)
        else:
            with contextlib.suppress(OSError):
                os.kill(state["pid"], signal.SIGKILL)
    _state_file().unlink(missing_ok=True)


def reset(delete_models: bool = False) -> None:
    """Stop everything and clear the half-finished state, so the next cells start clean. Downloaded models stay unless asked."""
    stop()
    for name in ("gateway.json", "gateway.log", "requests.jsonl", "disk.json"):
        (WORK / name).unlink(missing_ok=True)
    if delete_models:
        shutil.rmtree(WORK / "weights", ignore_errors=True)
    _say("reset done" + (" (downloaded models deleted)" if delete_models else " (downloaded models kept)"))


# -- loading a model ---------------------------------------------------------------------------------------------------


def _describe(status: dict) -> str:
    progress = status.get("progress") or {}
    if progress.get("phase") == "downloading":
        total, done = progress["total_gib"], progress["done_gib"]
        return f"downloading {done:.1f} of {total:.1f} GiB ({done / total:.0%})" if total else "downloading"
    return "starting the model server (the first start on a T4 can take several minutes)"


def wait_ready(client: Client, model: str, timeout: float = 3600, poll: float = 5, retries: int = 2) -> dict:
    """Load `model` in the background and wait for it, printing progress. Run it again at any point: it picks up where things are.

    A load that fails (a dropped download, a crashed server) is retried up to `retries` times; the last error is raised.
    Refusals (does not fit this GPU, not enough disk, disabled) raise at once with the reason.
    """
    deadline, failures, last_line = time.time() + timeout, 0, ""
    client.select(model, wait=False)
    while time.time() < deadline:
        status = client.models()
        if status["loaded"] == model:
            _say(
                f"\n{model} is loaded (load {status['load_s']} s, warm-up {status['warm_ms']} ms). Free disk {status['disk']['free_gib']} GiB."
            )
            return status
        if status["loading"] == model:
            line = f"  {model}: {_describe(status)}"
            if line != last_line:
                _say(line)
                last_line = line
        else:  # not loading and not loaded: it failed or was unloaded
            failures += 1
            if failures > retries:
                raise RuntimeError(f"{model} failed to load {failures} times. Last error: {status.get('error')}")
            _say(f"  load failed ({status.get('error')}); retrying ({failures}/{retries})")
            client.select(model, wait=False)
        time.sleep(poll)
    raise TimeoutError(f"{model} was not ready after {timeout / 60:.0f} minutes; run this cell again to keep waiting")
