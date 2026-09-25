"""Live speaker-attributed transcription server (NVIDIA's coupled Nemotron-3-Diarization +
multitalker-parakeet pipeline -- see mt_pipeline.py and reference/SOURCES.md for the source of truth).

One persistent WebSocket per client at /ws:
  client -> server:  binary  = mono 16 kHz signed-16-bit PCM audio (any message size)
                     text    = JSON command: {"cmd":"get_settings"} | {"cmd":"reset"} | {"cmd":"flush"}
                               | {"cmd":"configure","settings":{...partial mt_pipeline.GUIDE keys...}}
                               | {"cmd":"reset_to_guide"}
                               | {"cmd":"ingest","kind":"youtube","url":...,"pace":"realtime"|"max"}
                               | {"cmd":"ingest","kind":"file","name":...,"pace":...} then binary FILE bytes, then
                                 {"cmd":"ingest_end"}   (binary frames are file bytes, not PCM, while a file ingest runs)
                               | (either ingest also takes "start_s" (skip ahead) and "length_s" (stop after))
                               | (add "play":true to either ingest, real-time pace only: the paced PCM comes back to the
                                 client as binary frames, the same bytes at the same moment the model receives them)
                               | {"cmd":"ingest_stop"}                          (see ingest.py for caps/allowlist)
  server -> client:  binary = PCM playback (only when ingest asked for play)
                     {"kind":"transcript","segments":[{speaker,start_time,end_time,words}],
                      "audio_s":float,"step_ms":float,"hop_ms":float}   after every completed model step
                     {"kind":"ingest","state":"started"|"running"|"done"|"stopped"|"error",pos_s?,error?}
                     {"kind":"settings"|"configured",...} / {"kind":"reset"|"flush",...} / {"kind":"error",...}

Per the guide: models are loaded once per process; each connection gets its own session (speaker
cache, ASR decoder state and transcript history are all session-specific).

    .venv/bin/python server.py      # http://127.0.0.1:8200  (ws at /ws)
"""
import asyncio
import json
import os
import time
import traceback
from pathlib import Path

import numpy as np
import websockets
from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.http11 import Response

import ingest as ing
import mt_pipeline as mt

HERE = Path(__file__).parent
PORT = int(os.environ.get("VOICE_PORT", "8200"))
HOST = os.environ.get("VOICE_HOST", "127.0.0.1")
CLIPS = {"warmup.pcm", "twovoice.pcm"}  # known-content test clips the page can replay without a mic
GUIDE_URL = "https://huggingface.co/nvidia/Nemotron-3-Diarization/blob/main/ASR_INTEGRATION_GUIDE.md"

asr_model = diar_model = None
settings_state = dict(mt.GUIDE)   # what new sessions are built with; starts at NVIDIA's guide values
hop_seconds = 1.12


def _http(status: int, body, ctype: str = "application/json") -> Response:
    if not isinstance(body, (bytes, bytearray)):
        body = json.dumps(body).encode()
    headers = Headers([("Content-Type", ctype), ("Content-Length", str(len(body)))])
    return Response(status, "OK" if status == 200 else "Error", headers, body)


def geometry() -> dict:
    meta = [dict(group=g, key=k, label=l, kind=kind, src=src, help=h, **extra) for g, k, l, kind, extra, src, h in mt.META]
    return {"asr_model": mt.ASR_MODEL, "diar_model": mt.DIAR_MODEL, "guide_url": GUIDE_URL,
            "values": settings_state, "guide": mt.GUIDE, "meta": meta, "hop_seconds": round(hop_seconds, 3)}


def _coerce(key: str, v):
    """Validate/normalize one incoming setting against its declared kind and range."""
    m = next(x for x in mt.META if x[1] == key)
    kind, extra = m[3], m[4]
    if kind == "toggle":
        return bool(v)
    v = float(v)
    if kind == "stops":
        if int(v) not in extra["stops"]:
            raise ValueError(f"{key} must be one of {extra['stops']}")
        return int(v)
    if not extra["min"] <= v <= extra["max"]:
        raise ValueError(f"{key} must be between {extra['min']} and {extra['max']}")
    return int(v) if float(extra["step"]).is_integer() else round(v, 4)


async def process_request(connection, request):
    if request.path == "/ws":
        return None
    if request.path in ("/", "/mockup.html"):
        return _http(200, (HERE / "mockup.html").read_bytes(), "text/html; charset=utf-8")
    if request.path.startswith("/clip/") and request.path[6:] in CLIPS:
        return _http(200, (HERE / request.path[6:]).read_bytes(), "application/octet-stream")
    if request.path == "/api/status":
        import torch
        return _http(200, {"models_loaded": asr_model is not None,
                           "gpu_allocated_mb": round(torch.cuda.memory_allocated() / 1e6, 1),
                           "settings": geometry() if asr_model is not None else None})
    return _http(404, {"error": "not found"})


def new_session(settings):
    global hop_seconds
    s = mt.LiveMultitalkerSession(asr_model, diar_model, mt.SAMPLE_RATE, settings)
    hop_seconds = s.hop_samples / mt.SAMPLE_RATE
    return s


async def ws_handler(websocket):
    global settings_state
    print("client connected", flush=True)
    session = new_session(settings_state)
    queue: asyncio.Queue = asyncio.Queue()      # audio (bytes) and commands (dict), arrival order
    out_q: asyncio.Queue = asyncio.Queue()
    stats = {"msgs": 0, "steps": 0}
    step_ms = [0.0]                              # smoothed compute time per model step

    def snapshot() -> dict:
        return {"kind": "transcript", "segments": session.segments(),
                "audio_s": round(session.step_num * session.hop_samples / mt.SAMPLE_RATE, 2),
                "step_ms": round(step_ms[0], 1), "hop_ms": round(session.hop_samples / mt.SAMPLE_RATE * 1000)}

    await websocket.send(json.dumps({"kind": "settings", "settings": geometry()}))

    ingest = None                                # the active ing.Ingest, if any (one per session)

    async def emit(ev: dict):
        await out_q.put(ev)

    async def stop_ingest():
        nonlocal ingest
        if ingest is not None:
            was, ingest = ingest, None
            await was.stop()

    async def handle_ingest(item: dict):
        nonlocal ingest
        cmd = item["cmd"]
        if cmd == "ingest":
            if ingest is not None and ingest.active:
                await emit({"kind": "ingest", "state": "error", "error": "an ingest is already running; stop it first"})
                return
            pace = "max" if item.get("pace") == "max" else "realtime"
            kind = item.get("kind")
            async def send_audio(b: bytes):                # optional playback: the paced PCM, back to the page
                await out_q.put(b)
            ingest = ing.Ingest(queue, emit, send_audio if item.get("play") else None)
            if kind == "youtube":
                bad = ing.check_youtube_url(item.get("url"))
                if bad:
                    ingest = None
                    await emit({"kind": "ingest", "state": "error", "error": bad})
                    return
                await ingest.start_youtube(item["url"].strip(), pace, item.get("start_s"), item.get("length_s"))
            elif kind == "file":
                await ingest.start_file(str(item.get("name", ""))[:200], pace, item.get("start_s"), item.get("length_s"))
            else:
                ingest = None
                await emit({"kind": "ingest", "state": "error", "error": "kind must be 'youtube' or 'file'"})
        elif cmd == "ingest_end":
            if ingest is not None and ingest.kind == "file":
                await ingest.file_end()
        elif cmd == "ingest_stop":
            await stop_ingest()
            await emit({"kind": "ingest", "state": "stopped"})

    async def recv_loop():
        async for message in websocket:
            if isinstance(message, (bytes, bytearray)):
                stats["msgs"] += 1
                if ingest is not None and ingest.active:
                    if ingest.kind == "file":          # binary frames are file bytes during a file ingest
                        err = ingest.file_chunk(bytes(message))
                        if err:
                            await stop_ingest()
                            await emit({"kind": "ingest", "state": "error", "error": err})
                    continue                            # otherwise raw PCM is ignored while ingest owns the session
                await queue.put(bytes(message))
            elif isinstance(message, str):
                try:
                    item = json.loads(message)
                except json.JSONDecodeError:
                    continue
                if not isinstance(item, dict):
                    continue
                if str(item.get("cmd", "")).startswith("ingest"):
                    await handle_ingest(item)
                    continue
                if item.get("cmd") in ("reset", "configure", "reset_to_guide"):
                    await stop_ingest()
                await queue.put(item)
        await stop_ingest()
        await queue.put(None)

    async def inference_loop():
        nonlocal session
        global settings_state
        while True:
            item = await queue.get()
            if item is None:
                break
            try:
                if isinstance(item, dict):
                    cmd = item.get("cmd")
                    if cmd == "get_settings":
                        await out_q.put({"kind": "settings", "settings": geometry()})
                    elif cmd == "reset":
                        session = await asyncio.to_thread(new_session, settings_state)
                        await out_q.put({"kind": "reset", "ok": True})
                    elif cmd == "flush":
                        # push silence through so the last (<1 hop) of audio's words are emitted
                        await asyncio.to_thread(session.accept_audio, np.zeros(int(1.3 * mt.SAMPLE_RATE), dtype=np.int16))
                        await out_q.put(snapshot())
                        await out_q.put({"kind": "flush", "ok": True})
                    elif cmd == "_ingest_done":
                        await out_q.put({"kind": "ingest", "state": "done", "pos_s": item.get("pos_s")})
                    elif cmd in ("configure", "reset_to_guide"):
                        try:
                            incoming = dict(mt.GUIDE) if cmd == "reset_to_guide" else {
                                k: _coerce(k, v) for k, v in item.get("settings", {}).items() if k in mt.GUIDE}
                        except (ValueError, TypeError) as e:
                            await out_q.put({"kind": "configured", "ok": False, "settings": geometry(), "error": f"invalid setting: {e}"})
                            continue
                        new = {**settings_state, **incoming}
                        old = settings_state
                        try:
                            session = await asyncio.to_thread(new_session, new)
                            settings_state = new
                            await out_q.put({"kind": "configured", "ok": True, "settings": geometry()})
                        except Exception as e:
                            # NeMo mutates the shared models while building a session, so a failed build
                            # must be undone by rebuilding from the previous settings.
                            traceback.print_exc()
                            session = await asyncio.to_thread(new_session, old)
                            await out_q.put({"kind": "configured", "ok": False, "settings": geometry(),
                                             "error": f"NeMo rejected that combination ({type(e).__name__}: {e}); kept the previous settings"})
                    else:
                        await out_q.put({"kind": "error", "error": f"unknown cmd {cmd!r}"})
                    continue
                before, t = session.step_num, time.perf_counter()
                await asyncio.to_thread(session.accept_audio, np.frombuffer(item[: len(item) // 2 * 2], dtype=np.int16))
                n = session.step_num - before
                if n:
                    per = (time.perf_counter() - t) * 1000 / n
                    step_ms[0] = per if step_ms[0] == 0 else 0.7 * step_ms[0] + 0.3 * per
                    stats["steps"] += n
                    await out_q.put(snapshot())
            except Exception as e:
                traceback.print_exc()
                await out_q.put({"kind": "error", "error": f"{type(e).__name__}: {e}"})
        await out_q.put(None)

    async def send_loop():
        while True:
            r = await out_q.get()
            if r is None:
                break
            try:
                await websocket.send(r if isinstance(r, (bytes, bytearray)) else json.dumps(r))
            except websockets.exceptions.ConnectionClosed:
                break

    try:
        await asyncio.gather(recv_loop(), inference_loop(), send_loop())
    finally:
        print(f"client disconnected ({stats['msgs']} audio messages, {stats['steps']} steps)", flush=True)


async def main():
    global asr_model, diar_model
    print("loading models...", flush=True)
    asr_model, diar_model = mt.load_models()
    # First real step pays a one-time multi-second GPU warm-up (measured ~10 s); absorb it here.
    print("warming up...", flush=True)
    warm = new_session(settings_state)
    for _ in range(4):
        warm.accept_audio(np.zeros(mt.SAMPLE_RATE, dtype=np.int16))
    del warm
    print(f"serving on http://{HOST}:{PORT}  (audio + control websocket at /ws)", flush=True)
    async with serve(ws_handler, HOST, PORT, process_request=process_request, max_size=None) as server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
