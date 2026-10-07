#!/usr/bin/env python3
"""Call the gateway with text, an image and a video, and print response times.

    python try_it.py --url http://127.0.0.1:8000 --key KEY            # all three, with built-in samples
    python try_it.py --url ... --key ... --image my.jpg --video my.mp4 --frames 8

Video goes in as sampled frames: the server's /v1/systemone takes `images`, not a video file.
Standard library, plus Pillow and ffmpeg (both on Colab) for the built-in image and video samples.
"""
import argparse, base64, io, json, statistics, subprocess, tempfile, time, urllib.error, urllib.request
from pathlib import Path

TEXT = {"state": "Our checkout started returning errors and orders are blocked.",
        "questions": {"team": {"type": "choice", "instructions": "Which team should handle this?", "criteria": {"billing": "Payments or invoices", "technical": "Bugs or outages"}},
                      "urgency": {"type": "score", "instructions": "How urgent is it?", "criteria": ["Can wait", "This week", "Today"]},
                      "outage": {"type": "noul", "instructions": "Is a service down?"}}}


def _post(url, key, path, body, timeout=300):
    req = urllib.request.Request(url + path, json.dumps(body).encode(), {"Content-Type": "application/json", "Authorization": "Bearer " + key})
    t = time.perf_counter()
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        code, raw, hdr = r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        code, raw, hdr = e.code, e.read(), e.headers
    return code, json.loads(raw or b"{}"), (time.perf_counter() - t) * 1000, hdr


def select(url, key, model):
    """Load a model (unloads the current one). Returns the gateway's status."""
    return _post(url, key, "/admin/select", {"model": model}, timeout=1800)[1]


def data_url(path_or_img, fmt="JPEG"):
    from PIL import Image
    img = path_or_img if hasattr(path_or_img, "save") else Image.open(path_or_img)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, fmt, quality=90)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()


def sample_image():
    """An invoice-like picture with a known total, drawn here, so no third-party image is needed."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (640, 400), "white")
    d = ImageDraw.Draw(img)
    for i, line in enumerate(["ACME SUPPLIES", "Invoice 2024-0117", "Paper A4 x2       8.40", "Stapler           3.50", "TOTAL EUR       11.90"]):
        d.text((40, 40 + i * 50), line, fill="black")
    return img


def sample_video_frames(n=6):
    """A 4-second clip of a red square crossing the frame, made with ffmpeg, then sampled back into n frames."""
    from PIL import Image, ImageDraw
    tmp = Path(tempfile.mkdtemp())
    for i in range(40):
        im = Image.new("RGB", (320, 180), "white")
        ImageDraw.Draw(im).rectangle([10 + i * 7, 60, 50 + i * 7, 100], fill="red")
        im.save(tmp / f"f{i:03d}.png")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "10", "-i", str(tmp / "f%03d.png"), "-pix_fmt", "yuv420p", str(tmp / "clip.mp4")], check=True)
    return video_frames(tmp / "clip.mp4", n)


def video_frames(path, n=8):
    """n evenly spaced frames of a video as data URLs."""
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).strip())
    out = []
    for i in range(n):
        ts = dur * (i + 0.5) / n
        png = subprocess.check_output(["ffmpeg", "-loglevel", "error", "-ss", f"{ts:.3f}", "-i", str(path), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"])
        from PIL import Image
        out.append(data_url(Image.open(io.BytesIO(png))))
    return out


def bench(url, key, label, body, n=5):
    """One warm-up call, then n timed calls. Returns a row of numbers and prints it."""
    code, first, _, _ = _post(url, key, "/v1/systemone", body)
    if code != 200:
        print(f"{label:<28} HTTP {code}: {first.get('error', first)}")
        return None
    rt, sv = [], []
    for _ in range(n):
        code, _, ms, hdr = _post(url, key, "/v1/systemone", body)
        rt.append(ms)
        sv.append(float(hdr.get("X-Latency-Ms", "nan")))
    row = {"test": label, "n": n, "round_trip_p50_ms": round(statistics.median(rt)), "round_trip_max_ms": round(max(rt)), "model_p50_ms": round(statistics.median(sv)), "answers": first.get("answers", first)}
    print(f"{label:<28} p50 {row['round_trip_p50_ms']:>5} ms (max {row['round_trip_max_ms']:>5}), model {row['model_p50_ms']:>5} ms")
    return row


def demo(url, key, image=None, video=None, frames=6, n=5):
    """Text, image and video tests against whatever model is loaded."""
    info = _post(url, key, "/v1/models", {})  # POST is fine: the gateway only checks the key
    rows = [bench(url, key, "text, 3 questions", TEXT, n)]
    img = data_url(image) if image else data_url(sample_image())
    q = {"total": {"type": "choice", "instructions": "What is the total on this invoice?", "criteria": {"11.90": None, "61.90": None, "8.40": None}}}
    rows.append(bench(url, key, "image, 1 question", {"state": "An invoice.", "images": [img], "questions": q}, n))
    fr = video_frames(video, frames) if video else sample_video_frames(frames)
    vq = {"moving": {"type": "noul", "instructions": "Is a red square visible in these frames?"}}
    rows.append(bench(url, key, f"video as {len(fr)} frames", {"state": "Frames sampled evenly from one video.", "images": fr, "questions": vq}, n))
    return [r for r in rows if r]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--key", required=True)
    ap.add_argument("--model", help="load this model first")
    ap.add_argument("--image"); ap.add_argument("--video")
    ap.add_argument("--frames", type=int, default=6); ap.add_argument("-n", type=int, default=5)
    a = ap.parse_args()
    if a.model:
        t = time.time(); select(a.url, a.key, a.model); print(f"loaded {a.model} in {time.time() - t:.0f}s")
    for r in demo(a.url, a.key, a.image, a.video, a.frames, a.n):
        print(json.dumps(r["answers"])[:300])
