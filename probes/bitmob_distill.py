"""Make BitMob mobs from field-specific encoders (model2vec distill: each vocabulary token through the encoder, PCA to 256
dimensions, SIF weighting), on the CPU. Saves models/bitmob-mobs/<id>/ and adds the mob to data/bitmob/members.json.
Run: HF_HOME=/workspace/data/hf models/embed-zs/.venv/bin/python probes/bitmob_distill.py [id ...]
"""
import json, sys, time, pathlib
from model2vec.distill import distill

ROOT = pathlib.Path("/workspace"); MOBS = ROOT / "models" / "bitmob-mobs"; CFG = ROOT / "data" / "bitmob" / "members.json"
SOURCES = {
    "medical-pubmedbert": ("microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext", "medical"),
    "legal-bert":         ("nlpaueb/legal-bert-base-uncased", "legal"),
    "finance-finbert":    ("ProsusAI/finbert", "finance"),
    "science-scibert":    ("allenai/scibert_scivocab_uncased", "science (SciBERT)"),
}
for mid in sys.argv[1:] or SOURCES:
    src, dom = SOURCES[mid]; out = MOBS / mid
    if not (out / "model.safetensors").exists():
        t0 = time.time(); m = distill(model_name=src, pca_dims=256, device="cpu"); m.save_pretrained(str(out))
        print(f"{mid}: distilled {src} in {time.time() - t0:.0f} s -> {out}", flush=True)
    cfg = json.loads(CFG.read_text())
    if mid not in [x["id"] for x in cfg["members"]]:
        mb = round(sum(f.stat().st_size for f in out.iterdir()) / 1e6)
        cfg["members"].append({"id": mid, "kind": "static", "source": str(out), "domain": dom, "mb": mb, "dim": 256, "made_from": src})
        CFG.write_text(json.dumps(cfg, indent=1)); print(f"{mid}: added to members.json ({mb} MB)", flush=True)
