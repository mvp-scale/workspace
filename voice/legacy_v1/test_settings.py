"""One-off verification of the new WS control channel: initial settings push, reset, configure,
and confirm audio still decodes correctly after a live reconfigure."""
import asyncio
import json

import websockets


async def main():
    async with websockets.connect("ws://127.0.0.1:8200/ws", max_size=None) as ws:
        print("initial:", json.loads(await ws.recv()))

        await ws.send(json.dumps({"cmd": "get_settings"}))
        print("get_settings:", json.loads(await ws.recv()))

        await ws.send(json.dumps({"cmd": "reset"}))
        print("reset:", json.loads(await ws.recv()))

        # Tweak one real parameter and confirm it reconfigures without crashing.
        await ws.send(json.dumps({"cmd": "configure", "settings": {"diar_chunk_right_context": 4}}))
        print("configuring...")
        msg = json.loads(await ws.recv())
        print("configured:", msg)
        assert msg["kind"] == "configured" and msg["ok"], "configure failed"
        assert msg["settings"]["diar_chunk_right_context"] == 4, "setting didn't take effect"

        # Send a real audio clip through post-reconfigure and confirm text still decodes.
        with open("warmup.pcm", "rb") as f:
            pcm = f.read()
        step = 8192
        texts = []
        for off in range(0, len(pcm), step):
            await ws.send(pcm[off : off + step])
        await asyncio.sleep(0.5)
        try:
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                if msg.get("kind") == "asr" and msg.get("text"):
                    texts.append(msg["text"])
        except asyncio.TimeoutError:
            pass
        print("post-reconfigure ASR texts:", texts)
        assert texts, "no text decoded after reconfigure!"
        print("PASS")


asyncio.run(main())
