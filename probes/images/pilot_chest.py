"""Add meta to pilots/chest.jsonl (pneumonia_type, width, height, orientation)."""
import json
from pathlib import Path
from PIL import Image
p = Path(__file__).parent / "pilots" / "chest.jsonl"
out = []
for l in p.read_text().splitlines():
    if not l.strip(): continue
    it = json.loads(l)
    sid = it["source_id"]
    if it["expected"] == "no": t = "none"
    elif "_bacteria_" in sid: t = "bacterial"
    elif "_virus_" in sid: t = "viral"
    else: t = "unknown"
    w, h = Image.open(it["image"]).size
    it["meta"] = {"pneumonia_type": t, "width": w, "height": h,
                  "orientation": "portrait" if h > w else "landscape" if w > h else "square"}
    out.append(it)
p.write_text("".join(json.dumps(i, sort_keys=True) + "\n" for i in out))
from collections import Counter
print(len(out), Counter(i["expected"] for i in out), Counter(i["meta"]["pneumonia_type"] for i in out), Counter(i["meta"]["orientation"] for i in out))
