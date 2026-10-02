# Ontology cascade (version 3): predefined families, breadth first, then drill down

RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE. An ontology is a draft written from standard published criteria; a clinician must review it before any claim is made on it.

## The idea

After the gate, the model is asked a broad pool of questions that covers every family of finding a task could involve (breadth). Each family is a word that stands for a group of related observations, like a breadcrumb: "Fracture line", "Bone outline", "Hardware". If a family looks reasonably detectable, we drill into it with a few more questions about its sub-families (depth), then deeper still. The result is a findings report for each image (which families are present, with a confidence, and the sub-findings underneath), and a task answer derived from it.

This replaces choosing the next questions on the fly. The structure is fixed in advance; only how deep to go is decided by the evidence.

## Budget per image: 100 questions

| Step | Questions | Rule |
|---|---|---|
| Gate | 10 | If it fails, stop |
| Breadth | up to 40 | every root family's probes (2 or 3 each) |
| Depth | the rest, in batches of 10 | expand the families that look detectable (confidence 0.5 or more), or are on the fence (0.3 to 0.5), ranked by how much they matter to the answer first, then information-only families. Children get 4 to 6 probes each; grandchildren likewise |

## File format: `cascades/v3/<task>.json`

```json
{
  "task": "bone",
  "title": "Bone fracture",
  "status": "DRAFT: written from general criteria, needs clinician review",
  "pilot": "bone",
  "classes": ["fracture", "no fracture"],
  "map": {"yes": "fracture", "no": "no fracture"},
  "state_gate": "An image is attached.",
  "state_after_gate": "An image is attached. It is an X-ray of a limb or joint.",
  "gate": [{"id": "G1", "q": "Is this an X-ray?", "pass": "yes"}],
  "families": [
    {
      "id": "F1", "name": "Fracture line",
      "probes": [{"id": "F1.a", "q": "Is there a thin dark or bright line crossing a bone?"}],
      "supports": {"fracture": 1, "no fracture": -1},
      "truth": {"meta": "fracture_count", "rule": "> 0"},
      "children": [
        {"id": "F1.1", "name": "Line direction",
         "probes": [{"id": "F1.1.a", "q": "Does the line run across the bone, at a right angle to its length?"}],
         "supports": {"fracture": 1}, "truth": null, "children": []}
      ]
    }
  ]
}
```

- `classes`: for a yes/no task the two outcomes, with `map` from the task's `expected` ("yes" / "no") to a class. For a pick-one task, the class names are the labels, exactly as in the task's items, and `map` is omitted.
- `gate`: exactly 10 questions. `pass` is the answer that lets the image continue. The gate asks only whether this is the right kind of image (right modality, right body area, in focus, not obscured, not a drawing). Include questions an off-topic image (a balloon, a car, another kind of scan) would fail.
- `families`: 8 to 14 root families. Each has 2 or 3 `probes` (broad yes/no questions about the family) and optional `children` (sub-families, 4 to 6 probes each; grandchildren allowed, depth at most 3). At least 4 root families must have children. The total number of root probes must not exceed 40.
- `supports`: for a family that bears on the task's answer, the classes it points to when detected (+1) or away from (-1). A family with no `supports` (empty object) is information only: it is still asked and reported, because the point of the exercise is to learn what the model can detect (for example body part, view, hardware, image quality).
- `truth` (optional but wanted wherever the dataset has a matching column): how to score whether the model detected this family correctly, from the pilot item's `meta` dictionary: `{"meta": "<key>", "rule": "<python expression on the value v, for example v > 0, v == 'hand', v in ('a','b')>"}`.

## Question rules (from TypeSafe's guidance)

- One observation per question, short, explicit, answerable in a second by a knowledgeable person looking at the image.
- Positive polarity: a "yes" means the thing is present. Never "free of", "not", "without", "absence of".
- Concrete and visual. No subjective words (suspicious, abnormal-looking, concerning, severe, nice). Describe what is visible: shape, brightness, position, size relative to something in the image, edges, colour.
- Start with Is, Are, Does, Do, Can, Has or Have, and end with a question mark. At most 140 characters.
- Do not name the diagnosis the task asks for inside the gate. Probes may name findings (a fracture line, a cavity) as that is what a family is.
- Every id is unique across the whole file.

## Pilot file: `pilots/<task>.jsonl`

One JSON object per line: `id`, `image` (absolute path), `question` (exactly as the lab task asks it), `labels`, `expected`, `source_id`, and `meta`: a dictionary of every dataset-derived attribute available for that image (the columns the `truth` rules refer to). 40 to 100 images, balanced across the classes (binary: no class above 55%; multi-class: none above 40%), images resized to at most 1536 px on the long side and saved under `/workspace/data/image-lab/pilot/<task>/`.
