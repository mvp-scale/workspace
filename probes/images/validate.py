"""Check image-lab task files. Usage: python validate.py T | python validate.py all"""
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
IMG_ROOT = Path("/workspace/data/image-lab/images")
REQUIRED = ["id", "family", "state", "images", "question", "labels", "expected", "split", "group", "provenance"]
PROV = ["source", "url", "license", "label_origin"]
MAX_SIDE = 1536


def status_of(task):
    md = HERE / f"{task}.md"
    if not md.exists():
        return None
    for line in md.read_text(encoding="utf-8").splitlines():
        if line.startswith("Status:"):
            return line.split(":", 1)[1].strip().split()[0]
    return None


def is_exempt(status):
    if not status:
        return False
    return status == "BLOCKED" or status.startswith("NEEDS_")


def load_rows(path):
    rows, errors = [], []
    text = path.read_text(encoding="utf-8")
    if text.strip() == "":
        return rows, ["file is empty"]
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            errors.append(f"line {n}: blank")
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            errors.append(f"line {n}: invalid JSON ({e})")
    return rows, errors


def check_balance(rows):
    types = {r["question"]["type"] for r in rows}
    problems = []
    if types == {"noul"}:
        yes = sum(1 for r in rows if r["expected"] == "yes")
        if len(rows) == 25 and not 10 <= yes <= 15:
            problems.append(f"yes/no balance: {yes} yes out of {len(rows)} (want 10 to 15)")
    elif types == {"choice"}:
        counts = Counter(r["expected"] for r in rows)
        if rows:
            top, k = counts.most_common(1)[0]
            if k / len(rows) > 0.40:
                problems.append(f"choice balance: {top!r} is {k}/{len(rows)} ({k / len(rows):.0%} > 40%)")
    else:
        noul = [r for r in rows if r["question"]["type"] == "noul"]
        if noul:
            yes = sum(1 for r in noul if r["expected"] == "yes")
            half = len(noul) / 2
            slack = max(1, round(0.1 * len(noul)))
            if abs(yes - half) > slack:
                problems.append(f"yes/no subset: {yes} yes out of {len(noul)} (want about half)")
        groups = {}
        for r in rows:
            if r["question"]["type"] == "choice":
                groups.setdefault(r["question"]["instructions"], []).append(r["expected"])
        for instr, vals in groups.items():
            counts = Counter(vals)
            top, k = counts.most_common(1)[0]
            if k / len(vals) > 0.40:
                problems.append(f"choice balance on {instr!r}: {top!r} is {k}/{len(vals)}")
    return problems


def check_item(task, row, i, seen_ids, seen_images):
    problems = []
    missing = [k for k in REQUIRED if k not in row]
    if missing:
        return [f"item {i}: missing keys {missing}"]
    q = row["question"]
    if not isinstance(q, dict) or "type" not in q or "instructions" not in q or "criteria" not in q:
        problems.append(f"item {i}: question needs type, instructions, criteria")
        return problems
    if row["id"] in seen_ids:
        problems.append(f"item {i}: duplicate id {row['id']}")
    seen_ids.add(row["id"])
    if row["family"] != task:
        problems.append(f"item {i}: family {row['family']!r} != {task}")
    labels = row["labels"]
    expected = row["expected"]
    if expected not in labels:
        problems.append(f"item {i}: expected {expected!r} not in labels")
    crit = q["criteria"]
    if q["type"] == "noul":
        if labels != ["no", "yes"]:
            problems.append(f"item {i}: noul labels must be ['no', 'yes']")
        if set(crit) != {"true", "false"}:
            problems.append(f"item {i}: noul criteria keys must be true and false")
    elif q["type"] == "choice":
        if set(labels) != set(crit):
            problems.append(f"item {i}: labels do not match criteria keys")
        if not 2 <= len(labels) <= 10:
            problems.append(f"item {i}: choice has {len(labels)} options")
    else:
        problems.append(f"item {i}: unknown question type {q['type']!r}")
    prov = row["provenance"] if isinstance(row.get("provenance"), dict) else {}
    for key in PROV:
        if not prov.get(key):
            problems.append(f"item {i}: provenance missing {key}")
    images = row["images"]
    if not isinstance(images, list) or not images:
        problems.append(f"item {i}: images must be a non-empty list")
        return problems
    for rel in images:
        if rel in seen_images:
            problems.append(f"item {i}: duplicate image {rel}")
        seen_images.add(rel)
        path = IMG_ROOT / rel
        if not path.is_file():
            problems.append(f"item {i}: missing image {rel}")
            continue
        try:
            with Image.open(path) as im:
                im.load()
                w, h = im.size
        except Exception as e:
            problems.append(f"item {i}: image {rel} will not open ({e})")
            continue
        if max(w, h) > MAX_SIDE:
            problems.append(f"item {i}: image {rel} long side {max(w, h)} > {MAX_SIDE}")
    return problems


def rederive_check(task, rows):
    path = HERE / f"build_{task}.py"
    if not path.is_file():
        return [f"no build_{task}.py to rederive from"]
    spec = importlib.util.spec_from_file_location(f"build_{task}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, "rederive", None)
    if fn is None:
        return [f"build_{task}.py has no rederive(item)"]
    problems = []
    for row in rows:
        got = fn(row)
        if got != row["expected"]:
            problems.append(f"{row['id']}: rederive returned {got!r}, file has {row['expected']!r}")
    return problems


def check_task(task):
    status = status_of(task)
    path = HERE / f"{task}.jsonl"
    reasons = []
    if not path.is_file():
        if is_exempt(status):
            return True, f"PASS {task}: no items, status {status}"
        if status is None and not (HERE / f"{task}.md").exists():
            return True, f"PASS {task}: nothing built yet"
        return False, f"FAIL {task}: no jsonl (status {status})"
    rows, errors = load_rows(path)
    reasons.extend(errors)
    if is_exempt(status):
        if errors:
            return False, f"FAIL {task}: " + "; ".join(errors)
        return True, f"PASS {task}: {len(rows)} items, status {status} (count exemption)"
    if len(rows) != 25:
        reasons.append(f"expected 25 items, found {len(rows)} (status {status})")
    seen_ids, seen_images = set(), set()
    for i, row in enumerate(rows):
        if isinstance(row, dict):
            reasons.extend(check_item(task, row, i, seen_ids, seen_images))
        else:
            reasons.append(f"item {i}: not an object")
    if rows and not errors:
        reasons.extend(check_balance(rows))
    if not reasons and not is_exempt(status):
        try:
            reasons.extend(rederive_check(task, rows))
        except Exception as e:
            reasons.append(f"rederive crashed: {e}")
    if reasons:
        return False, f"FAIL {task}: " + "; ".join(reasons)
    return True, f"PASS {task}: 25 items, status {status or 'unspecified'}"


def tasks_for(arg):
    if arg != "all":
        return [arg]
    names = set()
    for p in HERE.glob("*.jsonl"):
        names.add(p.stem)
    for p in HERE.glob("t*.md"):
        names.add(p.stem)
    return sorted(names)


def main(argv):
    if len(argv) != 1:
        print("usage: python validate.py T | python validate.py all")
        return 2
    tasks = tasks_for(argv[0])
    if not tasks:
        print("PASS: no task files yet")
        return 0
    ok = True
    for task in tasks:
        passed, msg = check_task(task)
        print(msg)
        ok = ok and passed
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
