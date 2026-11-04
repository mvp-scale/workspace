# Expert contract v1 (2026-10-31)

Every CPU expert in the stack follows this contract, so a router can choose between experts and a new expert plugs in without rework.

## Input
- A document type name (expert 1: `news_item` = headline + short description + source).
- Plain text only. No images, no network, no GPU, no hosted model at serving.

## Output, per field
Each field returns `{answer, confidence, status}`.
- `status` is `answered` or `unknown`. `unknown` is a normal answer, never an error. Fields that cannot exist in an item (for example "the colour this article is about") stay `unknown`; they are never forced.
- `confidence` is the model's own probability, calibrated on a later-in-time batch.
- The answered/unknown cut is set per field so that running agreement on answered items stays at or above the field's bar.

## Fields for expert 1
topic (49), story type (4), condition present (38, yes / no / unknown), condition direction and size (only when present is `answered`), claim, evidence, attribution (`unknown` unless text has them).

## Serving limits
One CPU thread, under 50 ms per item. Current student reads in about 0.5 ms.

## Definition of done (v2)
No human gold. "Good" is agreement across independent layers, reported as agreement, never as accuracy.
1. Repeatable: same input, same output; seeds and versions recorded.
2. Per field: report the share answered, and the agreement on the answered items, measured on a later-in-time batch the model never saw.
3. Bar per field: the share of items answerable at 80% running agreement with an independent layer. The 80% is the owner's working figure; the lasting principle is downstream tolerance (ledger F-0020), measured for these outputs before ship.
4. Under 50 ms on one CPU thread, measured.
5. Snapshots: each new batch is scored by the previous version before it is added; a version that does not improve held-out agreement is rolled back.
6. Free, open-source, usable licences only.
7. Cost of the next expert versus this one is recorded (days, dollars) to show the factory is reusable.

## Router (not built)
Built only after two experts exist. Seed: the triage classifier.
