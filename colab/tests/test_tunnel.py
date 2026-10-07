"""The tunnel watchdog with a fake cloudflared: restarts, probe failures, and a stop that never waits on a backoff."""

import time
import unittest

from jevgw.tunnel import Tunnel, launch_cloudflared  # noqa: F401  (imported to prove the real launcher loads)


class FakeProc:
    def __init__(self):
        self.alive = True

    def poll(self):
        return None if self.alive else 1

    def terminate(self):
        self.alive = False

    kill = terminate

    def wait(self, timeout=None):
        return 0


class Launcher:
    def __init__(self, fail_after=None):
        self.calls, self.procs, self.fail_after = 0, [], fail_after

    def __call__(self, port, work):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise RuntimeError("no tunnel URL appeared")
        proc = FakeProc()
        self.procs.append(proc)
        return proc, f"https://run{self.calls}.trycloudflare.com", f"ready://{self.calls}"


def wait_for(cond, seconds=5.0):
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


class TestTunnel(unittest.TestCase):
    def test_start_status_stop(self):
        launcher = Launcher()
        tunnel = Tunnel(8000, ".", launcher, probe=lambda ready: True, interval=0.05)
        status = tunnel.start()
        self.assertEqual((status["running"], status["url"]), (True, "https://run1.trycloudflare.com"))
        self.assertEqual(tunnel.start()["url"], status["url"])  # starting twice does not launch twice
        self.assertEqual(launcher.calls, 1)
        status = tunnel.stop()
        self.assertEqual((status["running"], status["url"]), (False, None))

    def test_restarts_a_dead_tunnel_with_a_new_url(self):
        launcher = Launcher()
        tunnel = Tunnel(8000, ".", launcher, probe=lambda ready: True, interval=0.05)
        tunnel.start()
        launcher.procs[0].alive = False  # cloudflared died
        self.assertTrue(wait_for(lambda: tunnel.status()["restarts"] == 1))
        self.assertEqual(tunnel.status()["url"], "https://run2.trycloudflare.com")
        tunnel.stop()

    def test_restarts_after_repeated_probe_failures_only(self):
        launcher, answers = Launcher(), iter([False, True, False, False, False] + [True] * 50)
        tunnel = Tunnel(8000, ".", launcher, probe=lambda ready: next(answers), interval=0.03, failures=3)
        tunnel.start()
        self.assertTrue(wait_for(lambda: tunnel.status()["restarts"] == 1))
        self.assertEqual(launcher.calls, 2)  # one isolated failure was ignored; three in a row restarted it
        tunnel.stop()

    def test_probe_gets_the_local_ready_handle_not_the_public_url(self):
        seen = []
        tunnel = Tunnel(8000, ".", Launcher(), probe=lambda ready: seen.append(ready) or True, interval=0.03)
        tunnel.start()
        self.assertTrue(wait_for(lambda: seen))
        self.assertEqual(seen[0], "ready://1")  # a new hostname may not resolve for minutes; the probe must not need it
        tunnel.stop()

    def test_stop_returns_at_once_while_backing_off(self):
        launcher = Launcher(fail_after=1)  # the first launch works, every restart fails
        tunnel = Tunnel(8000, ".", launcher, probe=lambda ready: True, interval=0.03)
        tunnel.start()
        launcher.procs[0].alive = False
        self.assertTrue(wait_for(lambda: tunnel.status()["error"]))
        started = time.time()
        tunnel.stop()
        self.assertLess(time.time() - started, 2.0)  # the backoff is 5 s or more
        self.assertFalse(tunnel.status()["running"])


if __name__ == "__main__":
    unittest.main()
