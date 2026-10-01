# t05_form_completeness

Status: SYNTH

## Recon

No external dataset. Images are drawn by `render_form` and `degrade` in `/workspace/probes/vision/business.py`. `render_form` returns the image and a dict with `signed`, `named`, `ticks`, `terms` and `count`. `degrade` applies `clean`, `skew`, `lowres` or `scan`.

## Labels

Every answer is the value used to draw that image (`label_origin`: generator value). Seed 5. Each item has its own seed string, so `rederive` redraws that one item and reads the dict again.

Five questions, five images each:

| Question | Type | Answer |
|---|---|---|
| Has the form been signed? | yes/no | `signed` |
| Is the box for accepting the terms ticked? | yes/no | `terms` |
| Is the full name field filled in? | yes/no | `named` |
| Are two or more checkboxes ticked? | yes/no | `count >= 2` |
| How many checkboxes are ticked? | choice 0 to 4 | `count` |

The extra question is the fourth row. It uses the same `count` field as the tick-count question. Chance rate 50% for yes/no and 20% for the five count options.

Yes/no answers are set by the builder (10 yes and 10 no across the 20 yes/no items) and then passed into `render_form`, so the drawing matches the label. The five count items use counts 0, 1, 2, 3 and 4 once each. Quality levels cycle `clean`, `skew`, `lowres`, `scan` (7, 6, 6 and 6 images).

Licence: generated in this workspace. URL: `file:///workspace/probes/vision/business.py`

## Caveats

`lowres` images are one third of the 800×1040 canvas. `scan` adds blur, noise and a shadow. The fifth question is not one of the four named in the spec; the spec asks for one more question from the same dict.
