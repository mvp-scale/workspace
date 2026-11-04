"""Builds the v3 codebook specs from the frozen v2 specs: boundary tests for story type, condition presence and size (ledger L537).
Run: python3 -I specs/make_spec_v3.py   (v2 files are never touched; v3 files are new frozen versions with their own sha)"""
import json, hashlib, pathlib
H = pathlib.Path(__file__).resolve().parent
NEW = {
 3: "story_type: decide by the main claim of the item. 'fact' if the main claim reports something that has happened or been announced (an announcement that was made is a fact, even when a named person made it). 'forecast' if the main claim is about the future: a prediction, expectation or projection. 'opinion' if the main claim is someone's judgment, view or advice that cannot be checked as true or false. 'unclear' only if you cannot tell which of these the main claim is.",
 5: "conditions: list a condition only if the item reports that the condition itself has already changed, up or down, for the people or place it is about. A plan, a warning, a reaction, a statement of intent or a possible future effect does not count, and neither does an effect you infer from background knowledge. List the condition the item reports changing; do not add neighbouring conditions it might also affect. A condition appears at most once. Use the condition ids below. direction 'up' means the condition rises as defined by its 'up' meaning; 'down' means it falls.",
 7: "Be conservative. Ask what exactly the item says has changed. If it names no change in a listed condition, leave conditions empty. Do not guess from background knowledge about the world. An item about a person, sport or entertainment with no effect on any condition has an empty list.",
}
LEVEL_ADD = " Judge the level from how many people are affected and how directly, as the item states it, not from dramatic wording. Choose notable only if the item itself shows that many people would notice (for example a nationwide price rise or the closure of a major service); choose minor for a local or narrow change; choose major only if the item shows daily life changing for many people."
out = {}
for who in ("sonnet", "haiku"):
    s = json.load(open(H / f"world_state_v2_frozen_{who}.json")); g = list(s["guideline"])
    for i, t in NEW.items(): g[i] = t
    g[6] = g[6] + LEVEL_ADD
    s["guideline"] = g; s["name"] = f"world_state_v3_codebook_{who}"; s["prompt_version"] = "ws-v3-codebook"
    p = H / f"world_state_v3_codebook_{who}.json"; p.write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
    out[who] = hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps(out))
