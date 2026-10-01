"""Shared helpers for the image-lab probe sets. New code only; imported by build_*.py."""
import math
import random
from datetime import date
from pathlib import Path

from PIL import Image

IMG_ROOT = Path("/workspace/data/image-lab/images")
MAX_SIDE = 1536
TODAY = date.today().isoformat()


def save_image(pil_image, task_id, index):
    """RGB JPEG, long side at most 1536 px. Returns a path relative to IMG_ROOT."""
    im = pil_image.convert("RGB")
    w, h = im.size
    long_side = max(w, h)
    if long_side > MAX_SIDE:
        scale = MAX_SIDE / long_side
        im = im.resize((max(1, int(round(w * scale))), max(1, int(round(h * scale)))), Image.LANCZOS)
    folder = IMG_ROOT / task_id
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{int(index):03d}.jpg"
    im.save(folder / name, format="JPEG", quality=88)
    return f"{task_id}/{name}"


def make_choice(question_text, options, correct, seed):
    opts = list(options)
    if correct not in opts:
        raise ValueError(f"correct {correct!r} not in options")
    if len(set(opts)) != len(opts):
        raise ValueError("duplicate options")
    if not 2 <= len(opts) <= 10:
        raise ValueError(f"choice needs 2 to 10 options, got {len(opts)}")
    rng = random.Random(seed)
    rng.shuffle(opts)
    question = {"type": "choice", "instructions": question_text, "criteria": {o: None for o in opts}}
    return question, opts, correct


def make_yesno(question_text, yes_text, no_text, answer_bool):
    question = {
        "type": "noul",
        "instructions": question_text,
        "criteria": {"true": yes_text, "false": no_text},
    }
    expected = "yes" if answer_bool else "no"
    return question, ["no", "yes"], expected


def provenance(source, source_id, url, license, label_origin, notes=""):
    return {
        "exclude_reason": None,
        "source": source,
        "source_id": source_id,
        "url": url,
        "license": license,
        "retrieved": TODAY,
        "label_origin": label_origin,
        "notes": notes,
    }


def decoy_numbers(value_string, n, seed):
    """n wrong amounts: same digits, same separators; one or two digits changed."""
    s = str(value_string)
    digit_idx = [i for i, c in enumerate(s) if c.isdigit()]
    if not digit_idx:
        raise ValueError(f"no digits in {value_string!r}")
    rng = random.Random(seed)
    out, seen = [], {s}
    guard = 0
    while len(out) < n and guard < 10000:
        guard += 1
        chars = list(s)
        k = min(1 if rng.random() < 0.5 else 2, len(digit_idx))
        for i in rng.sample(digit_idx, k):
            chars[i] = str((int(chars[i]) + rng.randint(1, 9)) % 10)
        cand = "".join(chars)
        if cand not in seen:
            seen.add(cand)
            out.append(cand)
    if len(out) < n:
        raise ValueError(f"could not make {n} decoys for {value_string!r}")
    return out


def wilson(k, n, z=1.96):
    """95% Wilson interval for k successes in n trials. Returns (low, high)."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = p + z2 / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return ((centre - margin) / denom, (centre + margin) / denom)
