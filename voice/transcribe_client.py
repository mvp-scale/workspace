#!/usr/bin/env python3
"""Transcribe one audio file through the running voice server, the same way the Conversation flow page does it.

Used by the console's POST /v1/audio/transcriptions (demo/server.py), which runs it with this folder's .venv so the
console itself stays standard-library only. Protocol (server.py docstring): connect to /ws, send
{"cmd":"ingest","kind":"file","pace":"max"} then the file bytes, then {"cmd":"ingest_end"}; read transcript snapshots
until the ingest says done; send {"cmd":"flush"} so the last words come out; print the final segments as JSON.

    .venv/bin/python transcribe_client.py FILE [--url ws://127.0.0.1:8200/ws] [--timeout 600]
"""
import argparse, asyncio, json, sys, time

import websockets

CHUNK = 256 * 1024


async def run(path, url, timeout):
    t0 = time.time(); last = None; audio_s = 0.0
    async with websockets.connect(url, max_size=None, open_timeout=10) as ws:
        await ws.send(json.dumps({"cmd": "ingest", "kind": "file", "name": path.rsplit("/", 1)[-1], "pace": "max"}))
        with open(path, "rb") as f:
            while (b := f.read(CHUNK)): await ws.send(b)
        await ws.send(json.dumps({"cmd": "ingest_end"}))
        done = False
        while time.time() - t0 < timeout:
            msg = await asyncio.wait_for(ws.recv(), timeout=max(1.0, timeout - (time.time() - t0)))
            if isinstance(msg, bytes): continue
            m = json.loads(msg)
            if m.get("kind") == "transcript":
                last = m["segments"]; audio_s = m.get("audio_s", audio_s)
                if done: break                                   # the snapshot that answers the flush
            elif m.get("kind") == "ingest":
                if m.get("state") == "error": raise RuntimeError(m.get("error") or "ingest failed")
                if m.get("state") in ("done", "stopped") and not done:
                    done = True; await ws.send(json.dumps({"cmd": "flush"}))
            elif m.get("kind") == "error": raise RuntimeError(m.get("error") or "voice server error")
        else:
            raise TimeoutError(f"no final transcript within {timeout} s")
    segs = [{"speaker": s.get("speaker"), "start": round(float(s.get("start_time", 0)), 2), "end": round(float(s.get("end_time", 0)), 2),
             "text": (s.get("words") if isinstance(s.get("words"), str) else " ".join(map(str, s.get("words") or []))).strip()} for s in (last or [])]
    speakers = {}
    for s in segs:  # the server's own speaker labels become V1, V2 ... in order of first appearance, as on the flow page
        s["speaker"] = speakers.setdefault(s["speaker"], f"V{len(speakers) + 1}")
    return {"text": " ".join(s["text"] for s in segs if s["text"]), "segments": segs, "duration": round(audio_s, 2),
            "processing_s": round(time.time() - t0, 2)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("file"); ap.add_argument("--url", default="ws://127.0.0.1:8200/ws"); ap.add_argument("--timeout", type=float, default=600)
    a = ap.parse_args()
    try: print(json.dumps(asyncio.run(run(a.file, a.url, a.timeout))))
    except Exception as e: print(json.dumps({"error": f"{type(e).__name__}: {e}"})); sys.exit(1)
