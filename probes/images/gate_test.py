"""Does the gate stop images of the wrong kind? Runs ONLY the 10 gate questions on off-topic images (including near misses such as another
radiograph type) and on the task's own pilot images. RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE.
    /workspace/kev/.venv/bin/python gate_test.py
"""
import json, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import cascade2 as c
from cascade import url, post, noul
LAB = Path("/workspace/data/image-lab/images")
NEG = {"skin": ["t09_vehicle_damage", "t15_produce_fresh_rotten", "t23_crop_disease", "t42_chest_xray", "t41_bone_fracture", "t45_pathology_patch"],
       "dental": ["t42_chest_xray", "t41_bone_fracture", "t47_brain_mri", "t40_skin_lesion", "t09_vehicle_damage", "t46_endoscopy"],
       "chest": ["t41_bone_fracture", "t44_dental_xray", "t47_brain_mri", "t40_skin_lesion", "t09_vehicle_damage", "t17_logo_present"]}
def gate(spec, path):
    a = post(url(path), spec["state_gate"], {g["id"]: noul(g["q"]) for g in spec["gate"]})
    asked = {k: float(v["noul"]) for k, v in a.items()}
    return c.gate_ok(spec, asked), asked
out = {}
for name in ("skin", "dental", "chest"):
    spec, items = c.load(name)
    pos = [i["image"] for i in items][:40]
    neg = [(t, str(p)) for t in NEG[name] for p in sorted((LAB / t).glob("*.jpg"))[:6]]
    with ThreadPoolExecutor(4) as ex:
        rp = list(ex.map(lambda p: gate(spec, p), pos)); rn = list(ex.map(lambda tp: gate(spec, tp[1]), neg))
    byt = {}
    for (t, _), (ok, _) in zip(neg, rn): byt.setdefault(t, [0, 0]); byt[t][0] += (not ok); byt[t][1] += 1
    pr = sum(not ok for ok, _ in rp)
    out[name] = {"own_images": len(rp), "own_rejected": pr, "off_topic": len(rn), "off_topic_rejected": sum(not ok for ok, _ in rn), "by_source": {t: f"{a}/{b} rejected" for t, (a, b) in byt.items()}}
    print(f"{name}: own pilot images wrongly stopped {pr}/{len(rp)} | off-topic images stopped {sum(not ok for ok, _ in rn)}/{len(rn)} | by source: {out[name]['by_source']}")
json.dump(out, open("/workspace/data/image-lab/runs/winnow-cascade2/gate-test.json", "w"), indent=1)
