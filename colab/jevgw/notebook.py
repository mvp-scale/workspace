"""Helpers for the Colab notebook. Every function is safe to call again: re-running a cell never needs an "undo" first.

setup()          check the GPU and disk, use your Hugging Face token if you added one, install the llama.cpp server
ensure_llama()   install the llama.cpp server, or notice it is already installed and working
start()          start the gateway, or reuse the one already running (same port, same key)
wait_ready()     load a model in the background, show download progress, retry a failed load
test()           time text, image and video calls against the loaded model
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

from . import DATA, __version__, catalog
from .backends import require_gpu
from .client import Client

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


def _require_gpu(binary: str) -> None:
    """The install is only good if llama.cpp sees the GPU. Models run on the GPU only."""
    require_gpu(binary)
    _say("llama.cpp sees the GPU")


def ensure_llama(t4_url: str = "") -> str:
    """The path to a working llama-server. A missing, half-downloaded or broken install is removed and done again."""
    binary = LLAMA_DIR / "bin" / "llama-server"
    if binary.exists() and _llama_works(binary):
        _say("llama.cpp is already installed:", binary)
        _require_gpu(str(binary))
        return str(binary)
    if LLAMA_DIR.exists():
        _say("removing a broken llama.cpp install and starting it again")
        shutil.rmtree(LLAMA_DIR)
    _say(
        "Installing llama.cpp for the Clef models: about 1-2 minutes, downloads roughly 700 MB (the engine plus the CUDA libraries it needs)..."
    )
    result = subprocess.run(
        ["bash", str(DATA / "setup_llama.sh")],
        capture_output=True,
        text=True,
        env={**os.environ, "LLAMA_DIR": str(LLAMA_DIR), "LLAMA_T4_URL": t4_url},
    )
    if result.stderr.strip():
        _say(result.stderr.strip())
    if result.returncode:
        raise RuntimeError("llama.cpp install failed; run this cell again to retry.\n" + (result.stdout + result.stderr)[-1500:])
    binary = result.stdout.strip().splitlines()[-1]
    _require_gpu(binary)
    return binary


# -- first cell: look at the machine --------------------------------------------------------------------------------------


def _meminfo_gib() -> tuple[float, float] | None:
    """(total, available) system RAM in GiB, or None where /proc is missing."""
    try:
        values = {
            line.split(":")[0]: int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines() if ":" in line
        }
        return values["MemTotal"] / 2**20, values["MemAvailable"] / 2**20
    except (OSError, KeyError, ValueError):
        return None


def _reachable(url: str, timeout: float = 10.0) -> bool:
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True  # it answered: the site is up, whatever it thinks of a HEAD request
    except OSError:
        return False


REQUIRED_TOOLS = (
    "bash",
    "curl",
    "git",
    "tar",
    "ldd",
)  # install llama.cpp, clone the model repositories, find missing CUDA libraries
OPTIONAL_TOOLS = ("ffmpeg", "ffprobe")  # only the video test needs these
APT_PACKAGE = {
    "bash": "bash",
    "curl": "curl",
    "git": "git",
    "tar": "tar",
    "ldd": "libc-bin",
    "ffmpeg": "ffmpeg",
    "ffprobe": "ffmpeg",
}


def _apt_install(tools: list[str]) -> None:
    """Install the Ubuntu packages that provide `tools`. Colab runs as root; elsewhere this may fail, and the caller reports what is missing."""
    env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
    packages = sorted({APT_PACKAGE[tool] for tool in tools})
    for command in (["apt-get", "update", "-qq"], ["apt-get", "install", "-y", "-qq", *packages]):
        with contextlib.suppress(OSError):
            subprocess.run(command, env=env, capture_output=True, timeout=600)


def ensure_tools() -> list[str]:
    """Check the tools and Python packages the notebook relies on, installing what is missing. Returns the optional ones still missing.

    Colab has all of these, so normally this just prints "ok". Anything required that cannot be installed stops here, before any large download.
    """
    missing = [tool for tool in REQUIRED_TOOLS + OPTIONAL_TOOLS if not shutil.which(tool)]
    if missing:
        _say(f"  Tools      installing {', '.join(missing)} (about a minute)...")
        _apt_install(missing)
        missing = [tool for tool in missing if not shutil.which(tool)]
    required = [tool for tool in missing if tool in REQUIRED_TOOLS]
    if required:
        raise SystemExit(
            f"  Missing tools that could not be installed: {', '.join(required)}. Install them (apt-get install ...) and run this cell again."
        )
    try:
        import PIL  # noqa: F401 - used by the image and video tests
    except ImportError:
        _say("  Tools      installing Pillow for the image test...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pillow"], capture_output=True)
    optional = [tool for tool in missing if tool in OPTIONAL_TOOLS]
    _say("  Tools      " + ("ok" if not optional else f"ok, except {', '.join(optional)}: the video test will be skipped"))
    return optional


MIN_DRIVER = 525  # NVIDIA's minimum driver for the CUDA 12 libraries llama.cpp is built with


def setup(t4_url: str = "") -> str:
    """Everything the first cell needs: checks the machine, then installs llama.cpp. Returns the llama-server path.

    Every check prints what it found. A machine that cannot work (no GPU, a driver too old for the CUDA libraries) stops here with the fix,
    before anything large is downloaded. Safe to run again.
    """
    _say("Checking this machine...")
    name, mib = catalog.gpu_info()
    if not name:
        raise SystemExit("  No GPU. Runtime > Change runtime type > T4 GPU, then run this cell again.")
    driver = subprocess.run(
        ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"], capture_output=True, text=True
    ).stdout.strip()
    if driver.split(".")[0].isdigit() and int(driver.split(".")[0]) < MIN_DRIVER:
        raise SystemExit(
            f"  The GPU driver ({driver}) is older than {MIN_DRIVER}, which the CUDA 12 libraries need. Pick a newer runtime."
        )
    _say(f"  GPU        {name}, {mib / 1024:.1f} GiB, driver {driver}: ok")
    total, _, free = shutil.disk_usage(WORK.parent if WORK.parent.exists() else "/")
    _say(f"  Disk       {free / 2**30:.0f} of {total / 2**30:.0f} GiB free (models need 5-13 GB each; only the last two stay)")
    if ram := _meminfo_gib():
        _say(f"  Memory     {ram[1]:.1f} of {ram[0]:.1f} GiB free")
    for label, url in (("GitHub", "https://github.com"), ("Hugging Face", "https://huggingface.co")):
        if not _reachable(url):
            raise SystemExit(f"  Cannot reach {label} ({url}). Check the runtime's internet access and run this cell again.")
    _say("  Network    GitHub and Hugging Face reachable: ok")
    ensure_tools()
    models = catalog.load(DATA / "models.json")
    fits = [m["id"] for m in models.values() if catalog.runnable(m) and catalog.fits(m, mib)]
    _say(f"  Models     {len(fits)} fit this GPU: {', '.join(fits)}")
    use_hf_token()
    return ensure_llama(t4_url)


# -- the Hugging Face token --------------------------------------------------------------------------------------------


def use_hf_token() -> bool:
    """Pass the Colab secret `HF_TOKEN` to downloads, if there is one. Works the same without. The token is never printed.

    Colab secrets (the key icon in the sidebar) are not environment variables, so the secret is read through `google.colab.userdata`.
    A signed-in download gets Hugging Face's higher rate limits, which helps with the multi-GiB model files.
    """
    if os.environ.get("HF_TOKEN"):
        _say("downloads will use your Hugging Face token (HF_TOKEN is set)")
        return True
    try:
        from google.colab import userdata

        token = userdata.get("HF_TOKEN")
    except Exception:  # noqa: BLE001 - not on Colab, no such secret, or notebook access not granted: all mean "no token"
        token = None
    if not token:
        _say(
            "No Hugging Face token found. Downloads still work, but a token gets you higher rate limits and faster downloads.\n"
            "To add one: Colab sidebar > key icon (Secrets) > Add new secret, name HF_TOKEN, value your token from "
            "huggingface.co/settings/tokens (a read token is enough) > turn on Notebook access. Then run this cell again."
        )
        return False
    os.environ["HF_TOKEN"] = token
    _say("downloads will use your Hugging Face token (from the Colab secret HF_TOKEN)")
    return True


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
    token = bool(os.environ.get("HF_TOKEN"))
    if (
        state
        and _alive(state["pid"])
        and _is_ours(state["port"])
        and key in ("", state["key"])
        and (state.get("token", False) or not token)
        and state.get("version") == __version__  # a gateway started by an older install would still run the old code
    ):
        client = Client(f"http://127.0.0.1:{state['port']}", state["key"])
        loaded = client.models().get("loaded")
        _say(
            f"The gateway is already running on port {state['port']}; reusing it"
            + (f" ({loaded} stays loaded)" if loaded else "")
        )
        _say(f"API key: {state['key']}")
        return client, {**state, "reused": True}
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
    state = {"pid": proc.pid, "port": port, "key": key, "token": token, "version": __version__}
    _state_file().write_text(json.dumps(state))
    _say(f"The gateway is running on port {port}")
    _say(f"API key: {key}")
    return Client(f"http://127.0.0.1:{port}", key), {**state, "reused": False}


def show_panel(info: dict, inline: bool = False) -> None:
    """Show where the Jev console is. On Colab that is a link that opens it as its own full browser tab (nothing to scroll past);
    `inline=True` also embeds it in the notebook. Anywhere else, its address is printed."""
    path = f"/#key={info['key']}"
    try:
        from google.colab import output
    except ImportError:
        _say(f"Jev console: http://127.0.0.1:{info['port']}{path}")
        return
    as_tab = getattr(output, "serve_kernel_port_as_window", None)
    if as_tab:
        as_tab(info["port"], path=path, anchor_text="Open the Jev console in its own tab")
    if inline or not as_tab:  # without the tab link (an older Colab), the embedded console is the only way
        output.serve_kernel_port_as_iframe(info["port"], path=path, height="650")


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


# -- testing a loaded model --------------------------------------------------------------------------------------------


def test(client: Client, image: str = "", video: str = "", n: int = 5) -> list[dict]:
    """Five timed calls (after one warm-up) with text, then an image and a video's frames if the loaded model takes them."""
    from . import client as calls

    loaded = next((m for m in client.models()["models"] if m["loaded"]), None)
    if not loaded:
        raise RuntimeError("no model is loaded: run the load cell first")
    rows = [calls.bench(client, "text, 3 questions", calls.TEXT, n)]
    if loaded.get("vision"):
        rows += calls.demo(client, image or None, video or None, frames=6, n=n, text=False)
    else:
        _say(f"{loaded['name']} takes text only: no image or video test")
    for row in filter(None, rows):
        _say(f"  {row['test']} -> {json.dumps(row['answers'])[:170]}")
    return [row for row in rows if row]


# -- loading a model ---------------------------------------------------------------------------------------------------


def _clock(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 60}m{seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s"


def _describe(status: dict) -> str:
    progress = status.get("progress") or {}
    if progress.get("phase") == "downloading":
        total, done = progress["total_gib"], progress["done_gib"]
        return f"downloading {done:.1f} of {total:.1f} GiB ({done / total:.0%})" if total else "downloading"
    if progress.get("phase") == "installing":
        total = progress.get("total_gib")
        size = f", about {total:.0f} GB" if total else ""
        return f"installing its Python environment and weights (first time only{size}; a few minutes)"
    return "starting the model server (the first start on a T4 compiles GPU code and takes about a minute)"


def preflight(client: Client, model: str, status: dict | None = None) -> None:
    """Print what this load needs against what the machine has, before anything is downloaded. Raises if it cannot work."""
    status = status or client.models()
    entry = next((m for m in status["models"] if m["id"] == model), None)
    if entry is None:
        raise RuntimeError(
            f"unknown model {model!r}; the choices are: {', '.join(m['id'] for m in status['models'] if m['runnable'])}"
        )
    _say(f"Pre-flight for {entry['name']} ({model}):")
    free_gpu, need_gpu = status.get("gpu_free_gib"), entry.get("vram_gib") or 0
    if not entry["runnable"] or not entry["enabled"] or not entry["fits"]:
        why = entry.get("status") or (
            "it is disabled in the panel"
            if not entry["enabled"]
            else f"it needs about {need_gpu} GiB and this GPU has {status['gpu_gib']} GiB"
        )
        raise RuntimeError(f"  {model} cannot be loaded here: {why}.")
    loaded = status.get("loaded")
    reclaim = (
        next((m.get("vram_gib") or 0 for m in status["models"] if m["id"] == loaded), 0) if loaded and loaded != model else 0
    )
    available = (
        None if free_gpu is None else min(status["gpu_gib"], free_gpu + reclaim)
    )  # loading unloads the current model first
    if available is not None and available < need_gpu:
        raise RuntimeError(
            f"  GPU memory: {model} needs about {need_gpu} GiB but only {available:.1f} GiB would be free: something else is using the GPU. "
            "Run cell 6 with 'reset', or Runtime > Restart session, then try again."
        )
    after = f" (after unloading {loaded})" if reclaim else ""
    _say(
        f"  GPU memory   needs about {need_gpu} GiB, {'?' if available is None else f'{available:.1f}'} GiB free of {status['gpu_gib']}{after}: ok"
    )
    size, disk = entry.get("disk_gib") or 0, status.get("disk")
    if entry.get("cached"):
        _say("  Disk         already downloaded: nothing to fetch")
    elif disk:
        if size and disk["free_gib"] < size + 3:
            _say(
                f"  Disk         needs about {size:.0f} GB, {disk['free_gib']} GiB free: older models will be deleted to make room"
            )
        else:
            _say(f"  Disk         needs about {size:.0f} GB, {disk['free_gib']} GiB free: ok")
        if not _reachable("https://huggingface.co"):
            raise RuntimeError(
                "  Network      cannot reach huggingface.co: check the runtime's internet access and run this cell again."
            )
    token = (
        "your Hugging Face token is used"
        if os.environ.get("HF_TOKEN")
        else "no Hugging Face token: downloads work but are slower"
    )
    typical = (
        "a minute or less" if entry.get("cached") else f"typically {entry.get('first_run_min', 'a few')} minutes the first time"
    )
    _say(f"  Time         {typical}  ({token})")


def _wait_ready(client: Client, model: str, timeout: float, poll: float, retries: int, heartbeat: float) -> dict:
    status = client.models()
    if status["loaded"] == model:
        _say(f"{model} is already loaded (load {status['load_s']} s). Nothing to do.")
        return status
    preflight(client, model, status)
    if status["loaded"]:
        _say(f"  (loading {model} unloads {status['loaded']} first; only one model fits on the GPU at a time)")
    started = time.monotonic()
    deadline, failures, last_phase, last_beat, last_note = started + timeout, 0, "", started, ""
    while status["loading"] and status["loading"] != model and time.monotonic() < deadline:
        _say(f"  {status['loading']} is still loading; waiting for it to finish first...")
        time.sleep(poll)
        status = client.models()
    client.select(model, wait=False)
    while time.monotonic() < deadline:
        status = client.models()
        now = time.monotonic()
        if status["loaded"] == model:
            _say(
                f"\nReady: {model} is loaded ({_clock(now - started)} in total; load {status['load_s']} s, warm-up {status['warm_ms']} ms). "
                f"Free disk {status['disk']['free_gib']} GiB.\n"
            )
            return status
        if status["loading"] == model:
            phase = _describe(status)
            detail = (status.get("progress") or {}).get("detail")
            if phase != last_phase:
                _say(f"  [{_clock(now - started)}] {phase}")
                last_phase, last_beat = phase, now
            elif (status.get("progress") or {}).get("phase") == "downloading" and detail and detail != last_note:
                _say(f"  [{_clock(now - started)}] {detail}")  # for example a dropped connection being retried
                last_note = detail
            elif now - last_beat >= heartbeat:
                _say(
                    f"  [{_clock(now - started)}] still working: {phase.split(' (')[0].split(';')[0]}"
                    + (f"   > {detail}" if detail else "")
                )
                last_beat = now
        else:  # not loading and not loaded: it failed or was unloaded
            failures += 1
            if failures > retries:
                raise RuntimeError(f"{model} failed to load {failures} times. Last error: {status.get('error')}")
            _say(f"  Load failed: {status.get('error')}\n  Retrying ({failures}/{retries})...")
            client.select(model, wait=False)
            last_phase = ""
        time.sleep(poll)
    raise TimeoutError(
        f"{model} was not ready after {timeout / 60:.0f} minutes; run this cell again to keep waiting (nothing is lost)"
    )


def wait_ready(
    client: Client, model: str, timeout: float = 3600, poll: float = 5, retries: int = 2, heartbeat: float = 30
) -> dict:
    """Load `model` in the background and wait for it, saying what is happening. Run it again at any point: it picks up where things are.

    Prints a pre-flight check first, then a line whenever the phase changes and a heartbeat (elapsed time and the latest line of the install or
    server log) every `heartbeat` seconds, so a long step never looks stuck. If another model is still loading it waits for that one first.
    A load that fails (a dropped download, a crashed server) is retried up to `retries` times; the last error is raised.
    """
    try:
        return _wait_ready(client, model, timeout, poll, retries, heartbeat)
    except KeyboardInterrupt:
        _say("\nStopped waiting. The model keeps loading in the background: run this cell again to rejoin it.")
        raise


# -- the last step: how to use the console -----------------------------------------------------------------------------


def console(client: Client, info: dict) -> None:
    """Show the Jev console, as its own tab, and say what to do with it."""
    try:
        loaded = client.models().get("loaded") or "no model yet (use the Load button, or run the load cell)"
    except OSError:
        _say("The gateway is not running (it was stopped or reset). Run cell 2 to start it, then this cell again.")
        return
    show_panel(info)
    _say(f"""
Open the link above: the Jev console opens as its own page, so you can keep it beside the notebook. Model on the GPU now: {loaded}

 Models         Load, Unload, Enable, Disable and Delete files. One model is on the GPU at a time; loading another unloads the
                current one. "On disk" shows what is already downloaded.
 Try a model    Pick Text, Image or Video, edit the state and the questions, press Run (or Run x5 for timings). The questions are
                typed: noul = a yes/no probability, choice = pick one label, score = a number on a scale you describe.
 Response times p50 and p95 for each model since the gateway started. The header shows the GPU, free disk and the loaded model.
 Public address Cell 5 turns on a Cloudflare address (off by default; read its note). The same console is served there, so you can manage
                the gateway from any browser without the notebook: open it and enter your API key. Every action needs the key.

 From code in this notebook ({client.url}, key {info["key"]}):
     client.systemone({{"state": "Our checkout is failing.", "questions": {{"outage": {{"type": "noul", "instructions": "Is a service down?"}}}}}}).data

 Something stuck?  Run the cell again (it is safe), or cell 6 with 'reset'.""")
