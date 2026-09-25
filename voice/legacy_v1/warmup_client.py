import json, time, urllib.request

CHUNK_BYTES = 7680 * 2  # 7680 samples (480ms @16kHz s16le) -- matches pipeline.py's required exact stride
with open("warmup.pcm", "rb") as f:
    pcm = f.read()

urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8200/api/reset", b"", method="POST")).read()

for i in range(0, len(pcm), CHUNK_BYTES):
    sub = pcm[i:i + CHUNK_BYTES]
    t0 = time.time()
    req = urllib.request.Request("http://127.0.0.1:8200/api/chunk", sub, headers={"Content-Type": "application/octet-stream"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        dt = time.time() - t0
        print(f"chunk {i//CHUNK_BYTES}: {dt:.2f}s text={data.get('text')!r} final={data.get('is_final')}")
    except Exception as e:
        print(f"chunk {i//CHUNK_BYTES}: ERROR {type(e).__name__}: {e}")
