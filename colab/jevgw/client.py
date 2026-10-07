"""A client for the gateway: text, image and video calls with response times.

    python -m jevgw.client --url http://127.0.0.1:8000 --key KEY --model clef-flash-q4km

Video goes in as sampled frames: /v1/systemone takes `images`, not a video file. Standard library, plus Pillow and ffmpeg
(both on Colab) for the built-in image and video samples.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import statistics
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

TEXT = {
    "state": "Our checkout started returning errors and orders are blocked.",
    "questions": {
        "team": {
            "type": "choice",
            "instructions": "Which team should handle this?",
            "criteria": {"billing": "Payments or invoices", "technical": "Bugs or outages"},
        },
        "urgency": {"type": "score", "instructions": "How urgent is it?", "criteria": ["Can wait", "This week", "Today"]},
        "outage": {"type": "noul", "instructions": "Is a service down?"},
    },
}


@dataclass
class Response:
    status: int
    data: dict
    headers: dict
    ms: float  # round trip, client side

    @property
    def model_ms(self) -> float:
        """Time inside the model server, as the gateway reports it (nan if it did not)."""
        return float(self.headers.get("X-Latency-Ms", "nan"))


class Client:
    def __init__(self, url: str = "http://127.0.0.1:8000", key: str = ""):
        self.url, self.key = url.rstrip("/"), key

    def call(self, method: str, path: str, body: dict | None = None, timeout: float = 300) -> Response:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            self.url + path, data, {"Content-Type": "application/json", "Authorization": f"Bearer {self.key}"}, method=method
        )
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status, raw, headers = response.status, response.read(), dict(response.headers)
        except urllib.error.HTTPError as err:
            status, raw, headers = err.code, err.read(), dict(err.headers)
        return Response(status, json.loads(raw or b"{}"), headers, (time.perf_counter() - start) * 1000)

    # -- one method per endpoint ---------------------------------------------------------------------------------------

    def systemone(self, body: dict) -> Response:
        return self.call("POST", "/v1/systemone", body)

    def models(self) -> dict:
        return self.call("GET", "/v1/models").data

    def stats(self) -> dict:
        return self.call("GET", "/v1/stats").data["stats"]

    def select(self, model: str, wait: bool = True) -> dict:
        """Load a model (the current one is unloaded first). Raises if refused.

        wait=True blocks until it answers. wait=False returns at once and the load runs in the background: watch `models()["progress"]`,
        or use `jevgw.notebook.wait_ready`. Asking again for a model that is loading or loaded does nothing.
        """
        response = self.call("POST", "/admin/select", {"model": model, "wait": wait}, timeout=3600)
        if response.status not in (200, 202):
            raise RuntimeError(f"{model}: HTTP {response.status}: {response.data.get('error')}")
        return response.data

    def unload(self) -> dict:
        return self.call("POST", "/admin/unload", {}).data

    def enable(self, model: str, enabled: bool = True) -> dict:
        return self.call("POST", "/admin/enable", {"model": model, "enabled": enabled}).data

    def tunnel(self, action: str | None = None) -> dict:
        """The tunnel's status, or "start" / "stop" it. Raises if it cannot start."""
        if action is None:
            return self.call("GET", "/v1/tunnel").data
        response = self.call("POST", "/admin/tunnel", {"action": action}, timeout=120)
        if response.status != 200:
            raise RuntimeError(f"tunnel {action}: HTTP {response.status}: {response.data.get('error')}")
        return response.data


# -- samples and timing --------------------------------------------------------------------------------------------------


def data_url(image, fmt: str = "JPEG") -> str:
    """A PIL image, or a path to one, as a data URL."""
    from PIL import Image

    img = image if hasattr(image, "save") else Image.open(image)
    buffer = io.BytesIO()
    img.convert("RGB").save(buffer, fmt, quality=90)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buffer.getvalue()).decode()


def sample_image():
    """An invoice-like picture with a known total, drawn here, so no third-party image is needed."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (640, 400), "white")
    draw = ImageDraw.Draw(img)
    lines = ["ACME SUPPLIES", "Invoice 2024-0117", "Paper A4 x2       8.40", "Stapler           3.50", "TOTAL EUR       11.90"]
    for i, line in enumerate(lines):
        draw.text((40, 40 + i * 50), line, fill="black")
    return img


def video_frames(path, count: int = 8) -> list[str]:
    """`count` evenly spaced frames of a video, as data URLs."""
    from PIL import Image

    duration = float(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
        ).strip()
    )
    frames = []
    for i in range(count):
        at = duration * (i + 0.5) / count
        png = subprocess.check_output(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-ss",
                f"{at:.3f}",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "png",
                "-",
            ]
        )
        frames.append(data_url(Image.open(io.BytesIO(png))))
    return frames


def sample_video_frames(count: int = 6) -> list[str]:
    """A 4-second clip of a red square crossing the frame, made with ffmpeg, sampled back into frames."""
    from PIL import Image, ImageDraw

    folder = Path(tempfile.mkdtemp())
    for i in range(40):
        frame = Image.new("RGB", (320, 180), "white")
        ImageDraw.Draw(frame).rectangle([10 + i * 7, 60, 50 + i * 7, 100], fill="red")
        frame.save(folder / f"f{i:03d}.png")
    clip = folder / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-framerate",
            "10",
            "-i",
            str(folder / "f%03d.png"),
            "-pix_fmt",
            "yuv420p",
            str(clip),
        ],
        check=True,
    )
    return video_frames(clip, count)


def bench(client: Client, label: str, body: dict, n: int = 5) -> dict | None:
    """One warm-up call, then n timed calls. Prints and returns a row, or None if the call failed."""
    first = client.systemone(body)
    if first.status != 200:
        print(f"{label:<28} HTTP {first.status}: {first.data.get('error', first.data)}")
        return None
    runs = [client.systemone(body) for _ in range(n)]
    round_trip = [r.ms for r in runs]
    row = {
        "test": label,
        "n": n,
        "round_trip_p50_ms": round(statistics.median(round_trip)),
        "round_trip_max_ms": round(max(round_trip)),
        "model_p50_ms": round(statistics.median(r.model_ms for r in runs)),
        "answers": first.data.get("answers", first.data),
    }
    print(
        f"{label:<28} p50 {row['round_trip_p50_ms']:>5} ms (max {row['round_trip_max_ms']:>5}), model {row['model_p50_ms']:>5} ms"
    )
    return row


def demo(client: Client, image=None, video=None, frames: int = 6, n: int = 5, text: bool = True) -> list[dict]:
    """Text, image and video tests against whatever model is loaded."""
    rows = [bench(client, "text, 3 questions", TEXT, n)] if text else []
    invoice = {
        "total": {
            "type": "choice",
            "instructions": "What is the total on this invoice?",
            "criteria": {"11.90": None, "61.90": None, "8.40": None},
        }
    }
    rows.append(
        bench(
            client,
            "image, 1 question",
            {"state": "An invoice.", "images": [data_url(image or sample_image())], "questions": invoice},
            n,
        )
    )
    shots = video_frames(video, frames) if video else sample_video_frames(frames)
    moving = {"moving": {"type": "noul", "instructions": "Is a red square visible in these frames?"}}
    rows.append(
        bench(
            client,
            f"video as {len(shots)} frames",
            {"state": "Frames sampled evenly from one video.", "images": shots, "questions": moving},
            n,
        )
    )
    return [row for row in rows if row]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--key", required=True)
    ap.add_argument("--model", help="load this model first")
    ap.add_argument("--image")
    ap.add_argument("--video")
    ap.add_argument("--frames", type=int, default=6)
    ap.add_argument("-n", type=int, default=5, help="timed calls per test")
    args = ap.parse_args()
    client = Client(args.url, args.key)
    if args.model:
        start = time.time()
        client.select(args.model)
        print(f"loaded {args.model} in {time.time() - start:.0f}s")
    for row in demo(client, args.image, args.video, args.frames, args.n):
        print(json.dumps(row["answers"])[:300])


if __name__ == "__main__":
    main()
