import csv, json
from pathlib import Path
H = Path(__file__).parent
N, M, K, B = "melanocytic nevus", "melanoma", "benign keratosis", "basal cell carcinoma"
meta = {r["image_id"]: r for r in csv.DictReader(open("/workspace/data/sources/image-lab/ham10000/HAM10000_metadata.csv"))}
REG = {"scalp": "head_neck", "face": "head_neck", "ear": "head_neck", "neck": "head_neck",
       "back": "trunk", "chest": "trunk", "abdomen": "trunk", "trunk": "trunk",
       "upper extremity": "arm_hand", "hand": "arm_hand",
       "lower extremity": "leg_foot", "foot": "leg_foot", "acral": "leg_foot"}
src = H / "pilots" / "skin.jsonl"
items = [json.loads(l) for l in src.read_text().split("\n") if l.strip()]
out = []
for it in items:
    r = meta[it["source_id"]]
    age = float(r["age"]) if r["age"] else None
    it["meta"] = {"dx": r["dx"], "localization": r["localization"], "age": age, "sex": r["sex"],
                  "region": REG.get(r["localization"], "other")}
    out.append(json.dumps(it, sort_keys=True))
src.write_text("\n".join(out) + "\n")

def P(fid, qs): return [{"id": f"{fid}.{chr(97+i)}", "q": q} for i, q in enumerate(qs)]
def fam(fid, name, probes, sup=None, children=(), truth=None):
    return {"id": fid, "name": name, "probes": P(fid, probes), "supports": sup or {}, "truth": truth, "children": list(children)}

gate = [
 ("Is this a close-up image of human skin?", "yes"),
 ("Is there a single skin lesion near the centre of the image?", "yes"),
 ("Is the lesion in sharp focus?", "yes"),
 ("Does the image show a magnified view with fine surface structures visible, as in dermoscopy?", "yes"),
 ("Is more than half of the lesion covered by hair, a ruler, a marker or an air bubble?", "no"),
 ("Is the whole lesion inside the frame, with all of its edge visible?", "yes"),
 ("Is the lesion a different colour from the skin around it?", "yes"),
 ("Does the image mainly show an object, animal, vehicle, food or room?", "no"),
 ("Is the image an X-ray, CT slice or other grey-scale scan of the inside of the body?", "no"),
 ("Is the image a photograph or scan rather than a drawing, diagram or screenshot?", "yes"),
]
fams = [
 fam("F1", "Global pattern", [
   "Does the lesion show one repeated pattern across most of its area?",
   "Does the lesion show two or more different patterns in different areas?",
   "Is the lesion mostly one flat, uniform patch of colour?"],
   {N: 1, M: 1, K: 0, B: 0}, [
   fam("F1.1", "Pattern types", [
     "Is a reticular network of lines the main pattern?",
     "Are round globules the main pattern?",
     "Is a cobblestone arrangement of closely packed globules the main pattern?",
     "Is a starburst arrangement of streaks around the edge the main pattern?",
     "Is a smooth, structureless area the main pattern?"], {N: 1, M: -1, K: 0, B: 0})]),
 fam("F2", "Symmetry", [
   "Does the lesion look the same when mirrored across its long axis?",
   "Does the lesion look the same when mirrored across the axis at a right angle to it?",
   "Are the colours spread evenly around the centre of the lesion?"],
   {N: 1, M: -1, K: 0, B: 0}, [
   fam("F2.1", "Asymmetry detail", [
     "Are the two halves of the lesion different in outline?",
     "Are the two halves of the lesion different in colour?",
     "Are the two halves of the lesion different in internal structures?",
     "Is one end of the lesion much wider than the other end?"], {N: -1, M: 1})]),
 fam("F3", "Border", [
   "Is the edge of the lesion a smooth, continuous curve?",
   "Does the edge of the lesion have notches or indentations?",
   "Does the edge of the lesion fade gradually into the surrounding skin?"],
   {N: 1, M: -1, K: 0, B: 0}, [
   fam("F3.1", "Border sharpness", [
     "Does the colour stop abruptly at the edge of the lesion along its full outline?",
     "Does the colour stop abruptly along only part of the outline?",
     "Does the lesion edge look blurred when compared with the surrounding skin?",
     "Does a thin pale rim run along the edge of the lesion?",
     "Does a dark rim run along the edge of the lesion?"], {N: 0, M: 1, K: 1, B: 0}),
   fam("F3.2", "Border outline shape", [
     "Is the outline of the lesion close to a circle or oval?",
     "Does the outline have scalloped, wavy edges?",
     "Does the outline have finger-like projections?",
     "Does the outline have a straight edge segment?",
     "Does the outline look as if it was pasted or stuck onto the skin?"], {N: 1, M: -1, K: 0, B: 0})]),
 fam("F4", "Colours", [
   "Does the lesion contain light brown areas?",
   "Does the lesion contain dark brown or black areas?",
   "Does the lesion contain red, white, blue or grey areas?"],
   {N: 0, M: 1, K: 0, B: 0}, [
   fam("F4.1", "Number of colours", [
     "Does the lesion contain only one colour?",
     "Does the lesion contain three or more different colours?",
     "Does the lesion contain five or more different colours?",
     "Is the colour darker at the centre than at the edge?",
     "Are the colours arranged in patches rather than blending smoothly?"], {N: -1, M: 1, K: 0, B: 0}),
   fam("F4.2", "Specific colours", [
     "Does the lesion contain a black area?",
     "Does the lesion contain a blue-grey area?",
     "Does the lesion contain a red area?",
     "Does the lesion contain a white area?",
     "Does the lesion contain a yellow or orange area?",
     "Does the lesion contain a light tan area?"], {M: 1, B: 1, N: -1, K: 0})]),
 fam("F5", "Pigment network", [
   "Are fine brown lines forming a net of small holes visible?",
   "Are the lines of the net the same thickness across the lesion?",
   "Do the net lines get thinner towards the edge of the lesion?"],
   {N: 1, M: 0, K: 0, B: -1}, [
   fam("F5.1", "Network regularity", [
     "Are the holes of the net all about the same size?",
     "Are the lines of the net evenly spaced?",
     "Do the lines of the net vary in thickness?",
     "Do the lines of the net end abruptly at the edge?",
     "Does the net cover less than half of the lesion?"], {N: 1, M: -1}, [
     fam("F5.1.1", "Network colour", [
       "Are the net lines all the same shade of brown?",
       "Are some net lines black and others light brown?",
       "Are some net lines grey?",
       "Are the net lines broken into short pieces?"], {N: 1, M: -1})]),
   fam("F5.2", "Network gaps", [
     "Does the net have areas where the lines are missing?",
     "Are there areas of white inside the net?",
     "Does the net have thick, dark lines?",
     "Does the net have lines that look like branches?"], {M: 1, N: -1})]),
 fam("F6", "Dots and globules", [
   "Are small round dots visible in the lesion?",
   "Are larger round or oval globules visible in the lesion?",
   "Are the dots or globules spread evenly across the lesion?"],
   {N: 1, M: 0, K: 0, B: 0}, [
   fam("F6.1", "Dot and globule layout", [
     "Are the dots or globules all about the same size?",
     "Are the dots or globules all about the same colour?",
     "Are the dots or globules mainly in the centre of the lesion?",
     "Are the dots or globules mainly at the edge of the lesion?",
     "Are the dots or globules gathered in one cluster?"], {N: -1, M: 1}),
   fam("F6.2", "Dot colour", [
     "Are the dots black?",
     "Are the dots brown?",
     "Are the dots blue-grey?",
     "Are the dots red?"], {M: 1, B: 1, N: 0})]),
 fam("F7", "Streaks", [
   "Are lines that run outward from the edge of the lesion visible?",
   "Are the outward lines tipped with small bulbs?",
   "Do the outward lines occur around the whole edge?"],
   {M: 1, N: 0, K: 0, B: 0}, [
   fam("F7.1", "Streak layout", [
     "Are the outward lines in only one part of the edge?",
     "Are the outward lines the same length?",
     "Are the outward lines spaced regularly?",
     "Are the outward lines dark brown or black?",
     "Do the outward lines join into a continuous ring?"], {M: 1, N: -1})]),
 fam("F8", "Blue-white structures", [
   "Is a blue-grey or milky-white veil-like area visible?",
   "Are white shiny lines visible?",
   "Are blue-grey spots visible?"],
   {M: 1, B: 1, N: -1, K: 0}, [
   fam("F8.1", "Blue-white veil", [
     "Is the blue-white area raised above the skin?",
     "Does the blue-white area cover the centre of the lesion?",
     "Is the blue-white area on top of a darker area?",
     "Is the blue-white area patchy in shape?",
     "Does the blue-white area cover more than half of the lesion?"], {M: 1, N: -1}),
   fam("F8.2", "Blue-grey spots and ovoid nests", [
     "Are blue-grey round spots scattered in the lesion?",
     "Are large blue-grey oval areas present, with a clear edge?",
     "Are the blue-grey spots arranged like a leaf or a wheel?",
     "Does a blue-grey area touch the edge of the lesion?"], {B: 1, M: 1, N: -1}),
   fam("F8.3", "Shiny white lines", [
     "Are white lines visible that cross each other at right angles?",
     "Are white lines visible only in some viewing angles?",
     "Are the white lines short and straight?",
     "Are white clods visible?"], {M: 1, B: 0, N: 0})]),
 fam("F9", "Vascular structures", [
   "Are red vessels visible in the lesion?",
   "Do any red vessels branch like the limbs of a tree?",
   "Are red dots or loops visible in the lesion?"],
   {B: 1, M: 0, N: -1, K: 0}, [
   fam("F9.1", "Vessel shape", [
     "Are the red vessels thick near the middle and thinner at the tips, with many branches?",
     "Are the red vessels short and curved?",
     "Are the red vessels shaped like commas?",
     "Are the red vessels shaped like hairpins?",
     "Are the red vessels arranged in a ring?",
     "Are the red vessels dots in a regular pattern?"], {B: 1, N: -1}),
   fam("F9.2", "Vessel background", [
     "Do the vessels lie on a white background?",
     "Do the vessels lie on a pink background?",
     "Do the vessels lie on a brown background?",
     "Are the vessels visible only at the edge of the lesion?"], {B: 1})]),
 fam("F10", "Surface scale and keratin", [
   "Are flaky or crusty bits visible on the surface?",
   "Are round yellow or white plugs visible on the surface?",
   "Does the surface look waxy, like stuck-on wax?"],
   {K: 1, M: 0, N: 0, B: 0}, [
   fam("F10.1", "Keratin plugs and cysts", [
     "Are round white or yellow-white blobs visible on the surface?",
     "Are dark round plugs visible in the surface openings?",
     "Do the blobs have a clear, sharp edge?",
     "Are the blobs scattered across the lesion?",
     "Are the blobs bigger than the dots of any pigment network?"], {K: 1, N: 0}),
   fam("F10.2", "Surface texture", [
     "Does the lesion surface have fine cracks or folds like a brain?",
     "Does the lesion surface look rough or scaly?",
     "Is a dry scab visible on the lesion?",
     "Does the lesion surface look smooth and glossy?"], {K: 1, B: 0})]),
 fam("F11", "Regression", [
   "Are areas of white scar-like colour visible inside the lesion?",
   "Are fine grey or blue-grey dots visible in a patch of the lesion?"],
   {M: 1, N: -1, K: 0, B: 0}),
 fam("F12", "Ulcer and erosion", [
   "Is there an area of red or brown crust on the lesion?",
   "Is a raw, open area visible on the lesion?"],
   {B: 1, M: 0, N: 0, K: 0}),
 fam("F13", "Hair and artefacts", [
   "Are hairs visible on or around the lesion?",
   "Is a ruler, marker ink or other drawn object visible?",
   "Are air bubbles or glare spots visible?"], {}),
 fam("F14", "Body site", [
   "Does the skin around the lesion show wrinkles, hair follicles or pores typical of the face?",
   "Does the image show a visible part of an ear, a nose, a nail or a lip?"], {}, truth={"meta": "region", "rule": "v == 'head_neck'"}),
]
# drop zero supports
def clean(f):
    f["supports"] = {k: v for k, v in f["supports"].items() if v}
    for c in f["children"]: clean(c)
for f in fams: clean(f)
o = {"task": "skin", "title": "Skin lesion (dermoscopy). RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE",
     "status": "DRAFT: written from standard dermoscopy criteria (ABCD rule, 7-point checklist, pattern analysis), needs dermatologist review",
     "pilot": "skin", "classes": [N, M, K, B],
     "state_gate": "An image is attached.",
     "state_after_gate": "An image is attached. It is a dermoscopy image of one skin lesion.",
     "gate": [{"id": f"G{i+1}", "q": q, "pass": p} for i, (q, p) in enumerate(gate)],
     "families": fams}
(H / "cascades" / "v3").mkdir(exist_ok=True, parents=True)
(H / "cascades" / "v3" / "skin.json").write_text(json.dumps(o, indent=1))
