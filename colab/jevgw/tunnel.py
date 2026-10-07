"""A free Cloudflare quick tunnel to the gateway, kept alive by a watchdog.

Quick tunnels are for testing: no uptime guarantee, 200 in-flight requests, no Server-Sent Events, and the URL changes every
time the tunnel restarts. The watchdog restarts a dead or disconnected tunnel and reports the new URL.

Health is read from cloudflared's own local /ready endpoint (live connections to Cloudflare's edge), never by fetching the public
hostname: a brand-new hostname can fail to resolve for minutes behind a caching resolver, and a probe that depends on it would
restart a healthy tunnel in a loop.
"""

from __future__ import annotations

import json
import platform
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from .backends import log

URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
RELEASE = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def probe_ready(ready_url: str) -> bool:
    """True if cloudflared reports at least one live connection to the edge."""
    try:
        with urllib.request.urlopen(ready_url, timeout=5) as response:
            return json.load(response).get("readyConnections", 0) >= 1
    except (OSError, ValueError):
        return False


def launch_cloudflared(port: int, work: str, wait: int = 60):
    """Start cloudflared for http://127.0.0.1:port. Returns (process, https URL, local /ready URL).

    Raises RuntimeError if no URL appears. Returns once the tunnel reports a live connection, or after 20 s regardless.
    """
    exe = Path(work) / "cloudflared"
    if not exe.exists():
        arch = "arm64" if platform.machine() in ("aarch64", "arm64") else "amd64"
        urllib.request.urlretrieve(RELEASE.format(arch=arch), exe)
        exe.chmod(0o755)
    ready_url = f"http://127.0.0.1:{_free_port()}/ready"
    metrics = ready_url.removeprefix("http://").removesuffix("/ready")
    # http2: QUIC (UDP) is blocked on some networks, and the automatic fallback can be slow or stick.
    cmd = [
        str(exe),
        "tunnel",
        "--no-autoupdate",
        "--protocol",
        "http2",
        "--metrics",
        metrics,
        "--url",
        f"http://127.0.0.1:{port}",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    deadline, url = time.time() + wait, None
    for line in proc.stdout:  # the URL is printed on stderr, merged here
        found = URL_PATTERN.search(line)
        if found:
            url = found.group(0)
            break
        if time.time() > deadline or proc.poll() is not None:
            break
    if not url:
        proc.terminate()
        raise RuntimeError("no tunnel URL appeared; Cloudflare may be rate-limiting, try again in a minute")
    threading.Thread(target=lambda: [None for _ in proc.stdout], daemon=True).start()  # keep draining its log
    for _ in range(20):
        if probe_ready(ready_url):
            break
        time.sleep(1)
    return proc, url, ready_url


class Tunnel:
    """Start, stop and watch a tunnel. `launcher` and `probe` can be replaced in tests."""

    def __init__(
        self, port: int, work: str, launcher=launch_cloudflared, probe=probe_ready, interval: float = 20.0, failures: int = 3
    ):
        self.port, self.work, self.launcher, self.probe = port, work, launcher, probe
        self.interval, self.max_failures = interval, failures
        self.proc = None
        self.url: str | None = None
        self.ready: str | None = None
        self.since: float | None = None
        self.restarts = 0
        self.error: str | None = None
        self._want = False
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._watchdog: threading.Thread | None = None

    def start(self) -> dict:
        with self._lock:
            self._want = True
            if not self._running():
                self._launch()
            if not self._watchdog or not self._watchdog.is_alive():
                self._watchdog = threading.Thread(target=self._watch, daemon=True, name="tunnel-watchdog")
                self._watchdog.start()
            return self.status()

    def stop(self) -> dict:
        self._want = False  # before taking the lock, so a watchdog that is backing off wakes up and lets go
        self._wake.set()
        with self._lock:
            self._kill()
            self.url = self.since = None
            return self.status()

    def status(self) -> dict:
        return {"running": self._running(), "url": self.url, "restarts": self.restarts, "error": self.error,
                "up_s": None if self.since is None else round(time.time() - self.since)}  # fmt: skip

    def _running(self) -> bool:
        return bool(self.proc) and self.proc.poll() is None

    def _launch(self) -> None:
        self.proc, self.url, self.ready = self.launcher(self.port, self.work)
        self.since, self.error = time.time(), None
        log("tunnel up", self.url)

    def _kill(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def _watch(self) -> None:
        bad, delay = 0, 5.0
        while self._want:
            self._wake.wait(self.interval)
            self._wake.clear()
            backoff = 0.0
            with self._lock:
                if not self._want:
                    return
                bad = 0 if self._running() and self.probe(self.ready) else bad + 1
                if self._running() and bad < self.max_failures:
                    continue  # healthy, or one probe failure not yet repeated enough to act on
                log("tunnel down; restarting" if not self._running() else "tunnel disconnected from the edge; restarting")
                self._kill()
                try:
                    self._launch()
                    self.restarts, bad, delay = self.restarts + 1, 0, 5.0
                except RuntimeError as err:
                    self.error, backoff, delay = str(err), delay, min(delay * 2, 120.0)
                    log("tunnel restart failed:", err)
            if backoff:
                self._wake.wait(backoff)  # outside the lock: stop() must never wait on this
