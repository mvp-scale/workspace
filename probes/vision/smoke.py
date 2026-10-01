"""One image, both routes: free-text chat (what can it see?) and typed /v1/systemone (what probabilities come back?)."""
import base64, io, json, sys, time, urllib.request
from PIL import Image, ImageDraw, ImageFont

BASE = "http://127.0.0.1:8091"
FONT = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"

def make():
    im = Image.new("RGB", (512, 384), "white"); d = ImageDraw.Draw(im)
    d.ellipse((60, 80, 200, 220), fill=(220, 30, 30))          # red circle, left
    d.rectangle((300, 160, 440, 300), fill=(30, 60, 220))      # blue square, right
    d.text((150, 320), "HELLO 42", fill="black", font=ImageFont.truetype(FONT, 40))
    im.save("images/smoke.png"); return im

def data_url(path):
    return "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()

def post(path, body):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=300) as r: out = json.load(r)
    return out, time.time() - t

make(); url = data_url("images/smoke.png")
chat, dt = post("/v1/chat/completions", {"model": "Winnow-12B", "max_tokens": 300, "messages": [{"role": "user", "content": [
    {"type": "image_url", "image_url": {"url": url}}, {"type": "text", "text": "Describe this image: shapes, colours, positions and any text."}]}]})
print(f"CHAT ({dt:.1f}s):", chat["choices"][0]["message"]["content"], "\n")
body = {"model": "Winnow-12B", "state": "An image is attached.", "winnow": {"images": [url]}, "questions": {
    "red_circle": {"type": "noul", "instructions": "Is there a red circle in the image?"},
    "blue_circle": {"type": "noul", "instructions": "Is there a blue circle in the image?"},
    "left_shape": {"type": "choice", "instructions": "What shape is on the left side?", "criteria": {"circle": None, "square": None, "triangle": None, "none": None}},
    "text": {"type": "choice", "instructions": "What does the text in the image say?", "criteria": {"HELLO 42": None, "GOODBYE 42": None, "HELLO 24": None, "no text": None}}}}
out, dt = post("/v1/systemone", body); print(f"SYSTEMONE ({dt:.1f}s):"); print(json.dumps(out, indent=1))
