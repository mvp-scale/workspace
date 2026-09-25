"""Rough standalone mockup: live mic -> Nemotron-3-Diarization + Parakeet streaming ASR.

Not wired into the demo console yet -- this is the "get it working" step before integrating
into flow.html's transcript-source abstraction (buildTimeline/runner.feed).

Audio and control messages share a single persistent WebSocket (/ws): binary messages are raw
PCM audio, text messages are JSON commands ({"cmd": "get_settings"} / {"cmd": "configure",
"settings": {...}}). A single long-lived connection avoids the fragility of repeated HTTP POSTs
through any intermediary (proxy/tunnel/port-forward) -- every ~480ms opening a new connection
meant any single stalled request could get the next one refused/reset before it ever reached the
application. GET / and GET /api/status are served on the same port via websockets'
process_request hook, so nothing new needs to be port-forwarded.

    .venv/bin/python server.py      # http://127.0.0.1:8200  (ws at /ws)

Single session: one mic at a time, no auth, loopback only by default.
"""
import asyncio
import json
import os
import traceback
from pathlib import Path

import websockets
from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.http11 import Response

import pipeline

HERE = Path(__file__).parent
PORT = int(os.environ.get("VOICE_PORT", "8200"))
HOST = os.environ.get("VOICE_HOST", "127.0.0.1")


def _http(status: int, body, ctype: str = "application/json") -> Response:
    if not isinstance(body, (bytes, bytearray)):
        body = json.dumps(body).encode()
    headers = Headers([("Content-Type", ctype), ("Content-Length", str(len(body)))])
    return Response(status, "OK" if status == 200 else "Error", headers, body)


async def process_request(connection, request):
    if request.path == "/ws":
        return None  # let the websocket handshake proceed
    if request.path in ("/", "/mockup.html"):
        return _http(200, (HERE / "mockup.html").read_bytes(), "text/html; charset=utf-8")
    if request.path == "/warmup.pcm":
        return _http(200, (HERE / "warmup.pcm").read_bytes(), "application/octet-stream")
    if request.path == "/api/status":
        import torch
        body = {
            "diar_loaded": pipeline._diar is not None,
            "asr_loaded": pipeline._asr is not None,
            "gpu_allocated_mb": round(torch.cuda.memory_allocated() / 1e6, 1),
            "gpu_reserved_mb": round(torch.cuda.memory_reserved() / 1e6, 1),
        }
        if pipeline._diar is not None:
            body["settings"] = pipeline.effective_settings()
        return _http(200, body)
    return _http(404, {"error": "not found"})


async def handle_command(cmd: dict) -> dict:
    if cmd.get("cmd") == "get_settings":
        return {"kind": "settings", "settings": pipeline.effective_settings(),
                "defaults": pipeline.DEFAULT_SETTINGS, "presets": pipeline.PRESETS}
    if cmd.get("cmd") == "reset":
        pipeline.reset()
        return {"kind": "reset", "ok": True}
    if cmd.get("cmd") == "configure":
        try:
            settings = await asyncio.to_thread(pipeline.configure, cmd.get("settings", {}))
            return {"kind": "configured", "ok": True, "settings": settings}
        except Exception as e:
            traceback.print_exc()
            return {"kind": "configured", "ok": False, "error": f"{type(e).__name__}: {e}"}
    return {"kind": "error", "error": f"unknown cmd {cmd.get('cmd')!r}"}


async def ws_handler(websocket):
    # Three decoupled loops (recv / inference / send) connected by queues, matching NVIDIA's own
    # labs-Voice-Agent pipeline (diarization inference backgrounded via asyncio.to_thread so the
    # pipeline isn't blocked) and a real production streaming-Parakeet deployment (recv_loop only
    # buffers, inference_loop is the sole consumer, send_loop is independent). Doing the model
    # calls inline in the recv loop -- what this file did before -- blocks audio intake itself
    # for the duration of every inference call, which is what produced laggy/stalling behavior:
    # the mic-side buffer backs up while a chunk is still being processed.
    print("client connected", flush=True)
    pipeline.reset()
    await websocket.send(json.dumps({"kind": "settings", "settings": pipeline.effective_settings(),
                                      "defaults": pipeline.DEFAULT_SETTINGS, "presets": pipeline.PRESETS}))
    queue: asyncio.Queue = asyncio.Queue()  # audio (bytes) and commands (dict), in arrival order
    result_q: asyncio.Queue = asyncio.Queue()
    n_msg = n_result = 0

    async def recv_loop():
        nonlocal n_msg
        async for message in websocket:
            if isinstance(message, (bytes, bytearray)):
                n_msg += 1
                await queue.put(message)
            elif isinstance(message, str):
                try:
                    await queue.put(json.loads(message))
                except json.JSONDecodeError:
                    pass
        await queue.put(None)  # sentinel: client closed

    async def inference_loop():
        nonlocal n_result
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, dict):
                await result_q.put(await handle_command(item))
                continue
            try:
                results = await asyncio.to_thread(pipeline.feed, item)
            except Exception as e:
                traceback.print_exc()
                await result_q.put({"kind": "error", "error": f"{type(e).__name__}: {e}"})
                continue
            for r in results:
                n_result += 1
                await result_q.put(r)
        await result_q.put(None)

    async def send_loop():
        while True:
            r = await result_q.get()
            if r is None:
                break
            try:
                await websocket.send(json.dumps(r))
            except websockets.exceptions.ConnectionClosed:
                break

    try:
        await asyncio.gather(recv_loop(), inference_loop(), send_loop())
    finally:
        print(f"client disconnected ({n_msg} messages, {n_result} results)", flush=True)


async def main():
    print("loading models and warming up (first-inference JIT/kernel-autotune cost, separate "
          "from weight loading, absorbed here rather than on a live user's first chunk)...")
    pipeline.load()
    print(f"serving on http://{HOST}:{PORT}  (audio + control websocket at /ws)")
    async with serve(ws_handler, HOST, PORT, process_request=process_request, max_size=None) as server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
