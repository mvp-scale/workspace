"""The standard-library downloader: complete files, resume from a partial file, checksum, missing files, retry."""

import hashlib
import http.server
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from jevgw import download

DATA = os.urandom(300_000)
SHA = hashlib.sha256(DATA).hexdigest()


class Handler(http.server.BaseHTTPRequestHandler):
    sha, honour_range, fail_first, hits = SHA, True, 0, []

    def do_GET(self):
        Handler.hits.append(self.headers.get("Range"))
        if self.path.endswith("missing.gguf"):
            return self.send_error(404)
        if Handler.fail_first > 0:
            Handler.fail_first -= 1
            self.send_response(200)
            self.send_header("Content-Length", str(len(DATA)))  # promise everything, send a little, hang up
            self.end_headers()
            self.wfile.write(DATA[:1000])
            return self.wfile.flush()
        start = int(self.headers["Range"].split("=")[1].rstrip("-")) if self.headers.get("Range") and Handler.honour_range else 0
        self.send_response(206 if start else 200)
        self.send_header("X-Linked-Etag", f'"{Handler.sha}"')
        self.send_header("Content-Length", str(len(DATA) - start))
        self.end_headers()
        self.wfile.write(DATA[start:])

    def log_message(self, *args):
        pass


class TestDownload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.env = mock.patch.dict(os.environ, {"JEVGW_HF_BASE": f"http://127.0.0.1:{cls.server.server_address[1]}"})
        cls.env.start()

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Handler.sha, Handler.honour_range, Handler.fail_first, Handler.hits = SHA, True, 0, []
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.folder = Path(self.dir.name)
        patch = mock.patch("time.sleep")  # no real back-off in tests
        patch.start()
        self.addCleanup(patch.stop)

    def get(self, name="m.gguf", **kw):
        return download.download("org/repo", name, self.folder, log=lambda *_: None, **kw)

    def test_downloads_and_leaves_no_partial_file(self):
        path = self.get()
        self.assertEqual(Path(path).read_bytes(), DATA)
        self.assertEqual(list((self.folder / ".partial").glob("*")), [])

    def test_a_complete_file_is_not_fetched_again(self):
        self.get()
        Handler.hits.clear()
        self.get()
        self.assertEqual(Handler.hits, [])

    def test_resumes_from_a_partial_file(self):
        part = self.folder / ".partial" / "m.gguf.incomplete"
        part.parent.mkdir()
        part.write_bytes(DATA[:100_000])
        self.assertEqual(Path(self.get()).read_bytes(), DATA)
        self.assertEqual(Handler.hits, ["bytes=100000-"])

    def test_a_server_that_ignores_the_range_restarts_cleanly(self):
        Handler.honour_range = False
        part = self.folder / ".partial" / "m.gguf.incomplete"
        part.parent.mkdir()
        part.write_bytes(DATA[:100_000])
        self.assertEqual(Path(self.get()).read_bytes(), DATA)

    def test_a_dropped_connection_is_retried_and_resumed(self):
        Handler.fail_first = 1
        self.assertEqual(Path(self.get()).read_bytes(), DATA)

    def test_wrong_checksum_deletes_the_partial_file_and_fails(self):
        Handler.sha = "0" * 64
        with self.assertRaises(OSError):
            self.get(tries=1)
        self.assertFalse((self.folder / "m.gguf").exists())
        self.assertFalse((self.folder / ".partial" / "m.gguf.incomplete").exists())

    def test_missing_file_is_a_clear_error_without_retries(self):
        with self.assertRaises(RuntimeError) as caught:
            self.get("missing.gguf")
        self.assertIn("404", str(caught.exception))
        self.assertEqual(len(Handler.hits), 1)


if __name__ == "__main__":
    unittest.main()
