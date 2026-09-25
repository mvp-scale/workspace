"""End-to-end test of the WebSocket audio path, mimicking mockup.html's send pattern: real speech
audio sent as a stream of small (4096-sample, ~256ms) messages -- NOT pre-aligned to the model's
required exact strides -- to prove the server-side pipeline.feed() accumulator handles arbitrary
message boundaries correctly."""
import asyncio
import json
import time

import websockets

CALLBACK_SAMPLES = 4096  # matches mockup.html's ScriptProcessorNode buffer size
BYTES_PER_SAMPLE = 2


async def main():
    with open("warmup.pcm", "rb") as f:
        pcm = f.read()
    step = CALLBACK_SAMPLES * BYTES_PER_SAMPLE

    async with websockets.connect("ws://127.0.0.1:8200/ws", max_size=None) as ws:
        async def sender():
            for off in range(0, len(pcm), step):
                await ws.send(pcm[off : off + step])
                await asyncio.sleep(CALLBACK_SAMPLES / 16000)  # real-time pacing
            await asyncio.sleep(1)  # let trailing results arrive
            await ws.close()

        send_task = asyncio.create_task(sender())
        t0 = time.time()
        n = 0
        try:
            async for message in ws:
                data = json.loads(message)
                n += 1
                print(f"result {n} @ {time.time()-t0:.2f}s: text={data.get('text')!r} "
                      f"final={data.get('is_final')} error={data.get('error')}")
        except websockets.exceptions.ConnectionClosed:
            pass
        await send_task
        print(f"done, {n} results over {time.time()-t0:.2f}s")


asyncio.run(main())
