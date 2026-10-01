"""Business-document vision suite: invoices, receipts, purchase orders and forms, generated with KNOWN field values.

Mid-market pipelines this stands in for: document triage, invoice field checks, form completeness (signature / checkbox).
Each item is one typed question about one generated document. Every document is rendered in four quality levels
(clean, skewed, low-res, scan = grayscale + noise + shadow) so accuracy can be read against image quality.
    /workspace/kev/.venv/bin/python business.py [--n 40] [--endpoint http://127.0.0.1:8091]
"""
import argparse, json, random, statistics, threading
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import suite
from suite import font, ask, gpu_sampler, choice, yesno

W, H = 800, 1040
VENDORS = ["Northwind Supply", "Bluefin Logistics", "Harbor Office Goods", "Summit Print Works", "Cedar & Pine Catering", "Orion IT Services", "Maple Tool Rental", "Redwood Freight"]
ITEMS = ["Paper reams", "Toner cartridge", "Courier service", "Laptop stand", "Consulting hours", "Safety gloves", "Pallet wrap", "Coffee beans", "Cable kit", "Freight charge"]
KINDS = ["INVOICE", "RECEIPT", "PURCHASE ORDER", "STATEMENT"]

def money(v): return f"${v:,.2f}"

def render_doc(rng, kind=None, total_over=None, po=None, paid=None):
    kind = kind or rng.choice(KINDS); vendor = rng.choice(VENDORS); num = f"{rng.randint(10000, 99999)}"
    lines = [(rng.choice(ITEMS), rng.randint(1, 9), rng.choice([12.5, 40, 75, 120, 249, 310])) for _ in range(rng.randint(2, 4))]
    total = sum(q * p for _, q, p in lines)
    if total_over is not None:  # force the total to the wrong/right side of $1,000 by adding a filler line
        gap = 1000 - total
        if total_over and total <= 1000: lines.append(("Setup fee", 1, round(gap + rng.randint(50, 400), 2)))
        if not total_over and total > 1000: lines, total = [("Paper reams", 2, 40)], 80
        total = sum(q * p for _, q, p in lines)
    has_po = rng.random() < 0.5 if po is None else po; is_paid = rng.random() < 0.5 if paid is None else paid
    im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im)
    d.text((50, 40), kind, fill="black", font=font(48)); d.text((50, 110), vendor, fill=(60, 60, 60), font=font(28))
    d.text((50, 170), f"No. {num}", fill="black", font=font(26)); d.text((450, 170), f"Date: 2026-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", fill="black", font=font(26))
    d.text((50, 215), f"PO: {rng.randint(1000, 9999)}" if has_po else "PO: ______", fill="black", font=font(26))
    y = 300; d.line((50, y - 12, W - 50, y - 12), fill="black", width=2)
    for name, q, p in lines:
        d.text((50, y), name, fill="black", font=font(24)); d.text((420, y), f"{q} x {money(p)}", fill="black", font=font(24)); d.text((640, y), money(q * p), fill="black", font=font(24)); y += 46
    d.line((50, y + 8, W - 50, y + 8), fill="black", width=2); d.text((420, y + 30), "TOTAL", fill="black", font=font(30)); d.text((600, y + 30), money(total), fill="black", font=font(34))
    if is_paid: d.rectangle((120, 820, 420, 920), outline=(200, 30, 30), width=8); d.text((160, 835), "PAID", fill=(200, 30, 30), font=font(64))
    return im, dict(kind=kind, num=num, total=total, has_po=has_po, is_paid=is_paid)

def render_form(rng, signed=None, terms=None, named=None):
    signed = rng.random() < 0.5 if signed is None else signed; named = rng.random() < 0.5 if named is None else named
    ticks = [rng.random() < 0.5 for _ in range(4)]
    if terms is not None: ticks[3] = terms
    im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im); d.text((50, 40), "SERVICE REQUEST FORM", fill="black", font=font(40))
    d.text((50, 150), "Full name:", fill="black", font=font(26)); d.line((230, 180, 720, 180), fill="black", width=2)
    if named: d.text((240, 145), rng.choice(["Maria Lopez", "John Carter", "Priya Patel", "Li Wei"]), fill=(20, 20, 120), font=font(28))
    labels = ["Request urgent service", "Send email confirmation", "Add on-site inspection", "I accept the terms and conditions"]
    for i, (lab, t) in enumerate(zip(labels, ticks)):
        y = 260 + i * 70; d.rectangle((60, y, 100, y + 40), outline="black", width=3); d.text((125, y + 4), lab, fill="black", font=font(26))
        if t: d.line((66, y + 22, 82, y + 36), fill=(20, 20, 120), width=6); d.line((82, y + 36, 98, y + 4), fill=(20, 20, 120), width=6)
    d.text((50, 640), "Signature:", fill="black", font=font(26)); d.rectangle((50, 680, 500, 800), outline="black", width=3)
    if signed:
        pts = [(70 + i * 12, 740 + rng.randint(-28, 28)) for i in range(34)]; d.line(pts, fill=(20, 20, 120), width=4)
    return im, dict(signed=signed, named=named, ticks=ticks, terms=ticks[3], count=sum(ticks))

def degrade(im, level, rng):
    if level == "clean": return im
    if level == "skew": return im.rotate(rng.choice([-5, -3, 3, 5]), expand=False, fillcolor="white", resample=Image.BICUBIC)
    if level == "lowres": return im.resize((W // 3, H // 3), Image.BILINEAR)
    g = im.convert("L").rotate(rng.uniform(-2, 2), fillcolor=255).filter(ImageFilter.GaussianBlur(1.0)); px = g.load()  # scan: gray, slight skew, blur, noise, edge shadow
    for _ in range(int(W * H * 0.05)): px[rng.randrange(W), rng.randrange(H)] = rng.randint(90, 255)
    for x in range(W):
        for y in range(0, 60, 3): px[x, y] = int(px[x, y] * (0.75 + y / 240))
    return g.convert("RGB")

LEVELS = ["clean", "skew", "lowres", "scan"]

def others(rng, correct, pool, k=3):
    opts = {correct}
    while len(opts) < k + 1: opts.add(pool())
    opts = sorted(opts); return opts

def c_doc_type(rng, lv):
    im, f = render_doc(rng); q, a = choice("What type of document is this?", KINDS, f["kind"]); return im, q, a
def c_total_threshold(rng, lv):
    over = rng.random() < 0.5; im, f = render_doc(rng, total_over=over); q, a = yesno("Is the total amount more than $1,000?", f["total"] > 1000); return im, q, a
def c_po(rng, lv):
    im, f = render_doc(rng); q, a = yesno("Does the document contain a purchase order number?", f["has_po"]); return im, q, a
def c_number(rng, lv):
    im, f = render_doc(rng); opts = others(rng, f["num"], lambda: str(rng.randint(10000, 99999))); q, a = choice("What is the document number?", opts, f["num"]); return im, q, a
def c_total_read(rng, lv):
    im, f = render_doc(rng); t = money(f["total"]); opts = others(rng, t, lambda: money(f["total"] + rng.choice([-1, 1]) * rng.choice([10, 25, 50, 100, 200]))); q, a = choice("What is the total amount?", opts, t); return im, q, a
def c_paid(rng, lv):
    im, f = render_doc(rng); q, a = yesno("Is the document stamped PAID?", f["is_paid"]); return im, q, a
def c_signature(rng, lv):
    im, f = render_form(rng); q, a = yesno("Has the form been signed?", f["signed"]); return im, q, a
def c_checked(rng, lv):
    im, f = render_form(rng); q, a = choice("How many checkboxes are ticked?", ["0", "1", "2", "3", "4"], str(f["count"])); return im, q, a
def c_terms(rng, lv):
    im, f = render_form(rng); q, a = yesno("Is the box for accepting the terms and conditions ticked?", f["terms"]); return im, q, a
def c_named(rng, lv):
    im, f = render_form(rng); q, a = yesno("Is the full name field filled in?", f["named"]); return im, q, a

CATS = {"doc_type": c_doc_type, "total_over_1000": c_total_threshold, "po_number_present": c_po, "read_doc_number": c_number, "read_total": c_total_read, "paid_stamp": c_paid,
        "form_signed": c_signature, "form_ticks_count": c_checked, "form_terms_ticked": c_terms, "form_name_filled": c_named}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=40); ap.add_argument("--endpoint", default="http://127.0.0.1:8091"); ap.add_argument("--model", default="Winnow-12B")
    ap.add_argument("--out", default="/workspace/data/vision-runs/winnow-business"); ap.add_argument("--seed", type=int, default=0); a = ap.parse_args()
    out = Path(a.out); (out / "images").mkdir(parents=True, exist_ok=True); rows = []
    stop, gpu = threading.Event(), []; threading.Thread(target=gpu_sampler, args=(stop, gpu), daemon=True).start()
    for cat, gen in CATS.items():
        rng = random.Random(f"{a.seed}-{cat}")
        for i in range(a.n):
            lv = LEVELS[i % 4]; im, q, expected = gen(rng, lv); im = degrade(im, lv, rng); name = f"{cat}-{i:03d}-{lv}.png"; im.save(out / "images" / name)
            ans, dt, toks = ask(a.endpoint, a.model, im, q)
            if q["type"] == "noul": p_yes = ans["noul"]; pred = p_yes >= 0.5; pc = p_yes if expected else 1 - p_yes
            else: pred = ans["choice"]; pc = ans["probabilities"].get(expected, 0.0)
            rows.append({"category": cat, "level": lv, "image": name, "question": q["instructions"], "expected": expected, "predicted": pred, "correct": pred == expected, "p_correct": pc, "latency_s": dt, "input_tokens": toks})
        r = [x for x in rows if x["category"] == cat]
        print(f"{cat:18s} {sum(x['correct'] for x in r):3d}/{len(r)}  " + "  ".join(f"{lv} {sum(x['correct'] for x in r if x['level'] == lv)}/{sum(1 for x in r if x['level'] == lv)}" for lv in LEVELS)
              + f"  tokens~{int(statistics.mean(x['input_tokens'] or 0 for x in r))}  p50 {statistics.median(x['latency_s'] for x in r) * 1000:.0f} ms", flush=True)
    stop.set(); (out / "results.jsonl").write_text("\n".join(json.dumps(x) for x in rows) + "\n")
    print("BY QUALITY: " + "  ".join(f"{lv} {sum(x['correct'] for x in rows if x['level'] == lv)}/{sum(1 for x in rows if x['level'] == lv)}" for lv in LEVELS))
    print(f"TOTAL {sum(x['correct'] for x in rows)}/{len(rows)}  GPU whole-card during run: min {min(gpu)} max {max(gpu)} MiB")

if __name__ == "__main__":
    main()
