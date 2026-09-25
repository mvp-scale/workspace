"""Server-side audio ingest for the voice server: a YouTube link or an uploaded file becomes 16 kHz mono
s16le PCM (via ffmpeg) fed into a session's queue. No shell is ever used; every argument is a list item.

YouTube: yt-dlp (stdout) -> pipe -> ffmpeg (stdin) -> PCM.   File: bytes from the websocket -> private temp file -> ffmpeg.
"""
import asyncio
import os
import shutil
import signal
import sys
import tempfile
import time
from urllib.parse import urlparse

RATE = 16000
CHUNK = RATE * 2                      # 1 s of PCM per read
YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be",
            "youtube-nocookie.com", "www.youtube-nocookie.com"}
MAX_AUDIO_S = int(os.environ.get("VOICE_INGEST_MAX_S", 2 * 3600))
MAX_FILE_BYTES = int(os.environ.get("VOICE_INGEST_MAX_BYTES", 300 * 1024 * 1024))
FIRST_BYTE_TIMEOUT_S = 90             # yt-dlp extraction + first audio
STALL_TIMEOUT_S = 60                  # no audio for this long once running
QUEUE_HIGH = 3                        # "max" pace: feed only while the session queue is this shallow



def ffmpeg_cmd(src: str) -> list:
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", src, "-vn",
            "-t", str(MAX_AUDIO_S), "-f", "s16le", "-ar", str(RATE), "-ac", "1", "pipe:1"]


def check_youtube_url(url) -> str | None:
    """Return a user-facing refusal, or None if the URL is acceptable."""
    if not isinstance(url, str) or len(url) > 2048:
        return "that is not a valid URL"
    try:
        u = urlparse(url.strip())
    except ValueError:
        return "that is not a valid URL"
    if u.scheme != "https":
        return "only https YouTube links are accepted"
    if u.username or u.password or u.port not in (None, 443):
        return "that URL form is not accepted"
    if (u.hostname or "").lower() not in YT_HOSTS:
        return "only YouTube links are accepted (youtube.com, youtu.be)"
    return None


def _kill(proc):
    """SIGKILL the process group, then close asyncio's transport: with the stdout reader cancelled and
    unread data buffered, reading is paused, EOF is never seen and proc.wait() would hang until timeout."""
    if proc is None:
        return
    if proc.returncode is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    transport = getattr(proc, "_transport", None)
    if transport is not None:
        transport.close()


class Ingest:
    """One ingest run. `queue` receives PCM bytes then two dict commands (flush, _ingest_done);
    `emit(dict)` sends a progress/state event to the client."""

    def __init__(self, queue, emit, audio_out=None):
        self.queue, self.emit, self.audio_out = queue, emit, audio_out   # audio_out: optional async fn(bytes) for browser playback
        self.procs, self.tasks = [], []
        self.kind = None
        self.file_q: asyncio.Queue | None = None
        self.file_bytes = 0
        self.stopping = False
        self.pos_s = 0.0
        self.stderr = b""
        self.err_tasks = []
        self.attempt, self.url = 0, None
        self.yt_proc, self.yt_stderr = None, b""
        self.finished = False
        self.spool = self.spool_dir = self.spool_path = None
        self.pace = "realtime"

    @property
    def active(self) -> bool:
        return self.kind is not None and not self.finished

    async def start_youtube(self, url, pace):
        self.kind, self.url = "youtube", url
        await self._spawn_youtube(pace, None)

    async def _spawn_youtube(self, pace, client):
        """client: a yt-dlp YouTube player client to force (used for the one retry after an HTTP 403)."""
        url = self.url
        extra = ["--extractor-args", f"youtube:player_client={client}"] if client else []
        yt_args = [sys.executable, "-m", "yt_dlp", "-f", "bestaudio/best", "--no-playlist", "--no-warnings",
                   "--socket-timeout", "20", "--js-runtimes", "node", *extra,
                   "--match-filter", "is_live", "--match-filter", f"duration<=?{MAX_AUDIO_S}", "-o", "-", "--", url]
        r, w = os.pipe()
        yt = await asyncio.create_subprocess_exec(*yt_args, stdout=w, stderr=asyncio.subprocess.PIPE,
                                                  stdin=asyncio.subprocess.DEVNULL, start_new_session=True)
        os.close(w)
        ff = await asyncio.create_subprocess_exec(*ffmpeg_cmd("pipe:0"), stdin=r, stdout=asyncio.subprocess.PIPE,
                                                  stderr=asyncio.subprocess.PIPE, start_new_session=True)
        os.close(r)
        self.procs += [yt, ff]
        self.yt_proc = yt
        self.err_tasks = [asyncio.create_task(self._drain_err(yt)), asyncio.create_task(self._drain_err(ff))]
        self.tasks += self.err_tasks + [asyncio.create_task(self._feed(ff, pace, yt))]

    async def start_file(self, name, pace):
        """Uploaded bytes are spooled to a private temp file and decoded from there when the upload ends:
        MP4/M4A keep their index at the end and cannot be read from a pipe."""
        self.kind, self.pace = "file", pace
        self.spool_dir = tempfile.mkdtemp(prefix="voice-ingest-")
        self.spool_path = os.path.join(self.spool_dir, "upload.bin")
        self.spool = open(self.spool_path, "wb")
        await self.emit({"kind": "ingest", "state": "uploading", "name": name})

    def file_chunk(self, data: bytes) -> str | None:
        """Accept uploaded file bytes; returns an error string if over the cap."""
        if self.tasks:                    # upload already ended; ignore stray frames
            return None
        self.file_bytes += len(data)
        if self.file_bytes > MAX_FILE_BYTES:
            return f"file is over the {MAX_FILE_BYTES / 2**20:.3g} MB limit"
        self.spool.write(data)
        return None

    async def file_end(self):
        if self.spool is None or self.tasks:
            return
        self.spool.close()
        ff = await asyncio.create_subprocess_exec(*ffmpeg_cmd(self.spool_path), stdin=asyncio.subprocess.DEVNULL,
                                                  stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                  start_new_session=True)
        self.procs.append(ff)
        self.err_tasks = [asyncio.create_task(self._drain_err(ff))]
        self.tasks += self.err_tasks + [asyncio.create_task(self._feed(ff, self.pace, None))]

    def _cleanup(self):
        self.finished = True
        if self.spool is not None:
            try:
                self.spool.close()
            except Exception:
                pass
        if self.spool_dir:
            shutil.rmtree(self.spool_dir, ignore_errors=True)

    async def _drain_err(self, proc):
        data = await proc.stderr.read()
        if proc is self.yt_proc:
            self.yt_stderr = data[-4000:]
        else:
            self.stderr = data[-4000:]

    async def _feed(self, ff, pace, yt):
        t0, sent, last_prog, total, carry, retried = time.monotonic(), 0.0, 0.0, 0, b"", False
        await self.emit({"kind": "ingest", "state": "started", "source": self.kind, "pace": pace})
        try:
            while True:
                try:
                    data = await asyncio.wait_for(ff.stdout.read(CHUNK),
                                                  FIRST_BYTE_TIMEOUT_S if total == 0 else STALL_TIMEOUT_S)
                except asyncio.TimeoutError:
                    await self._fail("timed out waiting for audio" + (" from YouTube" if yt else " from the file"))
                    return
                if not data:
                    break
                total += len(data)
                data, carry = carry + data, b""
                if len(data) % 2:              # pipe reads can split a 16-bit sample; never send half of one
                    data, carry = data[:-1], data[-1:]
                if not data:
                    continue
                if pace == "realtime":
                    delay = t0 + sent - time.monotonic()
                    if delay > 0:
                        await asyncio.sleep(delay)
                else:
                    while self.queue.qsize() > QUEUE_HIGH:
                        await asyncio.sleep(0.05)
                if self.audio_out is not None and pace == "realtime":
                    await self.audio_out(data)     # same bytes, same moment as the model gets them
                await self.queue.put(data)
                sent += len(data) / 2 / RATE
                self.pos_s = sent
                if sent - last_prog >= 1.0:
                    last_prog = sent
                    await self.emit({"kind": "ingest", "state": "running", "pos_s": round(sent, 1)})
            await ff.wait()
            if yt is not None:
                await yt.wait()
            await asyncio.gather(*self.err_tasks, return_exceptions=True)
            if total == 0:
                if yt is not None and self.attempt == 0 and "403" in self.yt_stderr.decode("utf-8", "replace"):
                    retried = True                # YouTube's 403 is intermittent and client-specific: retry once on mweb
                    self.attempt = 1
                    for p in self.procs:
                        _kill(p)
                    self.procs, self.yt_stderr, self.stderr = [], b"", b""
                    await self.emit({"kind": "ingest", "state": "retrying", "note": "YouTube refused (HTTP 403); trying another client"})
                    await self._spawn_youtube(pace, "mweb")
                    return
                await self._fail(self._explain())
                return
            await self.queue.put({"cmd": "flush"})
            await self.queue.put({"cmd": "_ingest_done", "pos_s": round(sent, 1)})
        except asyncio.CancelledError:
            raise
        finally:
            if not retried:
                for p in self.procs:
                    _kill(p)
                self._cleanup()

    def _explain(self) -> str:
        err = (self.yt_stderr + b"\n" + self.stderr).decode("utf-8", "replace")
        low = err.lower()
        yt_errs = [l for l in self.yt_stderr.decode("utf-8", "replace").splitlines() if l.startswith("ERROR")]
        if "does not pass filter" in low:
            return f"video is longer than the {MAX_AUDIO_S // 60} min limit"
        if "sign in" in low or "confirm you" in low or "bot" in low:
            return "YouTube asked for sign-in / bot check; the link cannot be fetched from this machine"
        if "private video" in low or "unavailable" in low or "not available" in low:
            return "that video is unavailable (private, removed or region-blocked)"
        if "http error 403" in low or "403" in low:
            return "YouTube refused the download (HTTP 403) on two clients; try again in a minute or use another video"
        if yt_errs and not any(k in low for k in ("does not pass filter",)):
            return "YouTube fetch failed: " + yt_errs[-1][:200]
        if "invalid data" in low or "moov atom" in low or "could not find codec" in low:
            return "could not read that audio (unsupported or unseekable format)"
        last = [l for l in err.strip().splitlines() if l.strip()][-1:] 
        return "no audio could be read" + (f": {last[0][:200]}" if last else "")

    async def _fail(self, msg):
        for p in self.procs:
            _kill(p)
        if not self.stopping:
            await self.emit({"kind": "ingest", "state": "error", "error": msg})

    async def stop(self):
        self.stopping = True
        self._cleanup()
        for p in self.procs:
            _kill(p)
        for t in self.tasks:
            t.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        for p in self.procs:
            try:
                await asyncio.wait_for(p.wait(), 5)
            except Exception:
                pass
