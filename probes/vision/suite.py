"""Vision probe suite for a /v1/systemone server with an image-capable model (Winnow-12B).

Every item is a synthetic image drawn here with a KNOWN answer (seeded, reproducible), asked as one typed question.
Categories isolate one skill each, so strengths and weaknesses show up by category, not as one blended number.
    python suite.py [--n 30] [--endpoint http://127.0.0.1:8091] [--out /workspace/data/vision-runs/winnow]
Runs only need the kev venv for Pillow:  /workspace/kev/.venv/bin/python suite.py
"""
import argparse, base64, io, json, math, os, random, statistics, subprocess, threading, time, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
COLORS = {"red": (220, 30, 30), "green": (30, 160, 60), "blue": (30, 60, 220), "yellow": (240, 210, 30), "purple": (130, 50, 170), "orange": (240, 130, 20)}
SHAPES = ["circle", "square", "triangle", "star"]
W, H = 512, 384

def canvas(): return Image.new("RGB", (W, H), "white")
def font(px): return ImageFont.truetype(FONT, px)

def draw_shape(d, kind, cx, cy, r, fill):
    if kind == "circle": d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)
    elif kind == "square": d.rectangle((cx - r, cy - r, cx + r, cy + r), fill=fill)
    elif kind == "triangle": d.polygon([(cx, cy - r), (cx - r, cy + r), (cx + r, cy + r)], fill=fill)
    else:
        pts = [(cx + (r if i % 2 == 0 else r * 0.45) * math.sin(i * math.pi / 5), cy - (r if i % 2 == 0 else r * 0.45) * math.cos(i * math.pi / 5)) for i in range(10)]
        d.polygon(pts, fill=fill)

def choice(q, labels, correct): return {"type": "choice", "instructions": q, "criteria": {l: None for l in labels}}, correct
def yesno(q, truth): return {"type": "noul", "instructions": q}, truth

# ---- one generator per category: (rng) -> (image, question spec, expected label) ----
def g_color(rng):
    c = rng.choice(list(COLORS)); im = canvas(); d = ImageDraw.Draw(im); draw_shape(d, "circle", rng.randint(150, 360), rng.randint(120, 260), rng.randint(60, 110), COLORS[c])
    q, a = choice("What colour is the shape?", list(COLORS), c); return im, q, a

def g_shape(rng):
    s = rng.choice(SHAPES); im = canvas(); d = ImageDraw.Draw(im); draw_shape(d, s, rng.randint(150, 360), rng.randint(130, 250), rng.randint(70, 110), COLORS[rng.choice(list(COLORS))])
    q, a = choice("What shape is shown?", SHAPES, s); return im, q, a

def g_count(rng):
    n = rng.randint(1, 9); im = canvas(); d = ImageDraw.Draw(im); placed = []
    while len(placed) < n:
        x, y = rng.randint(40, W - 40), rng.randint(40, H - 40)
        if all(math.hypot(x - a, y - b) > 62 for a, b in placed): placed.append((x, y))
    for x, y in placed: draw_shape(d, "circle", x, y, 24, COLORS["blue"])
    q, a = choice("How many circles are in the image?", [str(i) for i in range(1, 10)], str(n)); return im, q, a

def g_position(rng):
    quad = rng.choice(["top-left", "top-right", "bottom-left", "bottom-right"]); im = canvas(); d = ImageDraw.Draw(im)
    x = rng.randint(40, W // 2 - 40) + (W // 2 if "right" in quad else 0); y = rng.randint(30, H // 2 - 30) + (H // 2 if "bottom" in quad else 0)
    draw_shape(d, "circle", x, y, 26, COLORS["red"]); d.line((W // 2, 0, W // 2, H), fill=(200, 200, 200), width=2); d.line((0, H // 2, W, H // 2), fill=(200, 200, 200), width=2)
    q, a = choice("Which quadrant contains the red dot?", ["top-left", "top-right", "bottom-left", "bottom-right"], quad); return im, q, a

def _word(rng): return "".join(rng.choice("ABCDEFGHKLMNPRSTUVWXYZ") for _ in range(5))
def _ocr(rng, px, blur=0.0, noise=0.0):
    w = _word(rng); im = canvas(); d = ImageDraw.Draw(im); f = font(px); tw = d.textlength(w, font=f)
    d.text(((W - tw) / 2, H / 2 - px / 2), w, fill="black", font=f)
    if blur: im = im.filter(ImageFilter.GaussianBlur(blur))
    if noise:
        px_ = im.load()
        for _ in range(int(W * H * noise)):
            x, y = rng.randrange(W), rng.randrange(H); v = rng.randint(0, 255); px_[x, y] = (v, v, v)
    decoys = [_word(rng) for _ in range(3)]; opts = decoys + [w]; rng.shuffle(opts)
    q, a = choice("Which word is written in the image?", opts, w); return im, q, a
def g_ocr_large(rng): return _ocr(rng, 64)
def g_ocr_small(rng): return _ocr(rng, 14)
def g_ocr_blur(rng): return _ocr(rng, 48, blur=2.5)
def g_ocr_noise(rng): return _ocr(rng, 48, noise=0.12)

def g_digits(rng):
    n = str(rng.randint(100, 999)); im = canvas(); d = ImageDraw.Draw(im); f = font(96); d.text(((W - d.textlength(n, font=f)) / 2, 140), n, fill="black", font=f)
    opts = {n}
    while len(opts) < 4: opts.add(str(rng.randint(100, 999)))
    opts = sorted(opts); q, a = choice("What number is written?", opts, n); return im, q, a

def g_arith(rng):
    a_, b_ = rng.randint(2, 9), rng.randint(2, 9); txt = f"{a_} + {b_} ="; im = canvas(); d = ImageDraw.Draw(im); f = font(80); d.text(((W - d.textlength(txt, font=f)) / 2, 150), txt, fill="black", font=f)
    ans = a_ + b_; opts = sorted({ans, ans + 1, ans - 1, ans + 2}); q, a = choice("What is the answer to the sum in the image?", [str(o) for o in opts], str(ans)); return im, q, a

def g_size(rng):
    big = rng.choice(["left", "right"]); r1, r2 = (90, rng.randint(40, 70)) if big == "left" else (rng.randint(40, 70), 90)
    im = canvas(); d = ImageDraw.Draw(im); draw_shape(d, "circle", 120, 190, r1, COLORS["green"]); draw_shape(d, "circle", 390, 190, r2, COLORS["green"])
    q, a = choice("Which circle is larger?", ["left", "right"], big); return im, q, a

def g_chart(rng):
    vals = rng.sample(range(20, 180), 4); im = canvas(); d = ImageDraw.Draw(im)
    for i, v in enumerate(vals):
        x0 = 70 + i * 100; d.rectangle((x0, 330 - v * 1.6, x0 + 60, 330), fill=COLORS["blue"]); d.text((x0 + 22, 340), "ABCD"[i], fill="black", font=font(28))
    top = "ABCD"[vals.index(max(vals))]; q, a = choice("Which bar is the tallest?", list("ABCD"), top); return im, q, a

def g_presence(rng):
    truth = rng.random() < 0.5; im = canvas(); d = ImageDraw.Draw(im)
    for _ in range(rng.randint(3, 5)):  # distractors: never a green triangle
        k, c = rng.choice(SHAPES), rng.choice([c for c in COLORS if c != "green"] if True else COLORS)
        if k == "triangle" and c == "green": continue
        draw_shape(d, k, rng.randint(50, W - 50), rng.randint(50, H - 50), rng.randint(25, 45), COLORS[c])
    if truth: draw_shape(d, "triangle", rng.randint(60, W - 60), rng.randint(60, H - 60), 40, COLORS["green"])
    q, a = yesno("Is there a green triangle in the image?", truth); return im, q, a

CATEGORIES = {"colour": g_color, "shape": g_shape, "count": g_count, "position": g_position, "ocr_large": g_ocr_large, "ocr_small_14px": g_ocr_small, "ocr_blurred": g_ocr_blur,
              "ocr_noisy": g_ocr_noise, "digits": g_digits, "arithmetic": g_arith, "relative_size": g_size, "chart_reading": g_chart, "presence_yes_no": g_presence}

def url_of(im):
    b = io.BytesIO(); im.save(b, "PNG"); return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()

def ask(endpoint, model, im, q):
    body = {"model": model, "state": "An image is attached.", "winnow": {"images": [url_of(im)]}, "questions": {"q": q}}
    req = urllib.request.Request(endpoint + "/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json"}); t = time.time()
    with urllib.request.urlopen(req, timeout=300) as r: out = json.load(r)
    return out["answers"]["q"], time.time() - t, out.get("usage", {}).get("input_tokens")

def gpu_sampler(stop, samples):
    while not stop.is_set():
        try: samples.append(sum(int(x) for x in subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], text=True).split()))
        except Exception: pass
        time.sleep(0.25)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=30); ap.add_argument("--endpoint", default="http://127.0.0.1:8091")
    ap.add_argument("--model", default="Winnow-12B"); ap.add_argument("--out", default="/workspace/data/vision-runs/winnow"); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--only", nargs="*"); a = ap.parse_args()
    out = Path(a.out); (out / "images").mkdir(parents=True, exist_ok=True); rows = []
    stop, gpu = threading.Event(), []; threading.Thread(target=gpu_sampler, args=(stop, gpu), daemon=True).start()
    for cat, gen in CATEGORIES.items():
        if a.only and cat not in a.only: continue
        rng = random.Random(f"{a.seed}-{cat}")
        for i in range(a.n):
            im, q, expected = gen(rng); name = f"{cat}-{i:03d}.png"; im.save(out / "images" / name)
            ans, dt, toks = ask(a.endpoint, a.model, im, q)
            if q["type"] == "noul": p_yes = ans["noul"]; pred = p_yes >= 0.5; p_correct = p_yes if expected else 1 - p_yes
            else: pred = ans["choice"]; p_correct = ans["probabilities"].get(expected, 0.0)
            rows.append({"category": cat, "image": name, "question": q["instructions"], "expected": expected, "predicted": pred, "correct": pred == expected, "p_correct": p_correct, "latency_s": dt, "input_tokens": toks})
        r = [x for x in rows if x["category"] == cat]; print(f"{cat:18s} {sum(x['correct'] for x in r):3d}/{len(r)}  mean p(correct)={statistics.mean(x['p_correct'] for x in r):.2f}  p50 {statistics.median(x['latency_s'] for x in r) * 1000:.0f} ms", flush=True)
    stop.set(); (out / "results.jsonl").write_text("\n".join(json.dumps(x) for x in rows) + "\n")
    tot = sum(x["correct"] for x in rows); print(f"TOTAL {tot}/{len(rows)}  GPU used during run: min {min(gpu)} max {max(gpu)} MiB (whole card)")

if __name__ == "__main__":
    main()
